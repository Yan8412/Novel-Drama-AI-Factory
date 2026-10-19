"""Read-only native QA provenance bridge; no new QA verdict or rewrite authority.

The supported native profile has a frame-based QA report, its original extraction
record, a delivery receipt and an existing canonical Compiler receipt. All paths
are explicitly selected by the caller; paths embedded in evidence are never
followed. Output contains private evidence and must stay outside the public repo.
"""
from collections import Counter
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from .feedback_adapter import (Artifact, DEFAULT_ADAPTER_ENABLED, ROUTES, _json,
                               json_sha256, propose_revision, sha256_bytes,
                               validate_candidate_input)

_FILES = {'qa', 'timeline', 'source', 'source_prompt', 'effective_prompt',
          'delivery', 'canonical', 'compiled', 'ffprobe'}


class MissingEvidence(ValueError):
    pass


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _hash(value):
    _require(isinstance(value, str) and re.fullmatch(r'[a-fA-F0-9]{64}', value),
             'INVALID_SHA256')
    return value.lower()


def _identity(info):
    # Windows path stat infers executable permission bits from the filename;
    # fstat has no filename. Compare file type, identity, size and modification.
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode), info.st_size, info.st_mtime_ns


def _path(value):
    _require(isinstance(value, str) and Path(value).is_absolute(), 'ABSOLUTE_LOCAL_PATH_REQUIRED')
    p = Path(value)
    _require(not str(p).startswith(('\\\\', '//')), 'REMOTE_PATH_NOT_ALLOWED')
    for part in (p, *p.parents):
        entry = part.lstat()
        _require(not stat.S_ISLNK(entry.st_mode) and not (
            getattr(entry, 'st_file_attributes', 0) & 0x400), 'LINK_OR_REPARSE_POINT')
    _require(p.is_file(), 'REGULAR_FILE_REQUIRED')
    return p


def _read(ref):
    _require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'EXACT_FILE_REFERENCE_REQUIRED')
    expected = _hash(ref['sha256'])
    p = _path(ref['path'])
    before = p.stat()
    _require(before.st_size <= 256 * 1024 * 1024, 'FILE_SIZE_LIMIT')
    with p.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        _require(_identity(opened) == _identity(before), 'FILE_CHANGED_BEFORE_READ')
        data = stream.read(256 * 1024 * 1024 + 1)
        _require(_identity(opened) == _identity(os.fstat(stream.fileno())), 'FILE_CHANGED_DURING_READ')
    _require(_identity(before) == _identity(_path(str(p)).stat()), 'FILE_CHANGED_AFTER_READ')
    _require(sha256_bytes(data) == expected, 'FILE_SHA256_MISMATCH')
    return data


def _same_path(a, b):
    return isinstance(a, str) and isinstance(b, str) and os.path.normcase(
        os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _time(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('INVALID_PTS')
    value = Decimal(str(value))
    _require(value.is_finite() and value >= 0, 'INVALID_PTS')
    return value


def _artifact(ref, value):
    if not isinstance(value, bytes):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(',', ':'), allow_nan=False).encode('utf-8')
    return Artifact(ref, value, sha256_bytes(value))


def _probe(files, timeline):
    _require(_hash(timeline['ffprobe_sha256']) == _hash(files['ffprobe']['sha256']),
             'PROBE_TOOL_DIFFERS_FROM_NATIVE_EXTRACTION')
    command = [files['ffprobe']['path'], '-v', 'error', '-protocol_whitelist', 'file',
               '-f', 'mov', '-select_streams', 'v:0',
               '-show_frames', '-show_entries',
               'frame=best_effort_timestamp_time:format=duration', '-of', 'json',
               files['source']['path']]
    run = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                         timeout=60, check=False,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    _require(run.returncode == 0 and not run.stderr.strip(), 'LOCAL_PROBE_FAILED')
    data = _json(run.stdout)
    pts = [_time(f['best_effort_timestamp_time']) for f in data['frames']]
    duration = _time(data['format']['duration'])
    _require(bool(pts) and duration > 0 and pts[-1] <= duration and
             all(a < b for a, b in zip(pts, pts[1:])), 'LIVE_PTS_ORDER_OR_DURATION_INVALID')
    return pts, duration, {'executable_sha256': files['ffprobe']['sha256'].lower(),
                           'stdout_sha256': sha256_bytes(run.stdout),
                           'frame_count': len(pts), 'exit_code': 0,
                           'scope': 'LOCAL_READ_ONLY_FFPROBE_NO_FRAME_OUTPUT'}


def _export(manifest, state):
    _require(isinstance(manifest, dict) and set(manifest) == {
        'files', 'frames', 'gate_id', 'failure_type', 'rule_clause'}, 'EXACT_MANIFEST_REQUIRED')
    files = manifest['files']
    _require(isinstance(files, dict) and not set(files) - _FILES, 'UNKNOWN_FILE_ROLE')
    if set(files) != _FILES:
        raise MissingEvidence('REQUIRED_NATIVE_OR_COMPILER_FILES_UNAVAILABLE')
    raw = {name: _read(ref) for name, ref in files.items()}
    evidence = {name: dict(ref, sha256=sha256_bytes(raw[name]), bytes=len(raw[name]))
                for name, ref in files.items()}
    qa, timeline, delivery, canonical, compiled = (
        _json(raw[name]) for name in ('qa', 'timeline', 'delivery', 'canonical', 'compiled'))
    if qa.get('schema_version') != 'S1FinalFrameBasedQAResultV1':
        raise MissingEvidence('UNSUPPORTED_NATIVE_QA_PROFILE_NOT_A_NEW_VERDICT')
    gates = qa['gates']
    _require(isinstance(gates, list) and all(isinstance(g, dict) for g in gates), 'QA_GATES_REQUIRED')
    ids = [g['gate_id'] for g in gates]
    _require(all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids),
             'DUPLICATE_OR_INVALID_NATIVE_QA_ID')
    if manifest['gate_id'] not in ids:
        raise MissingEvidence('NATIVE_QA_ID_NOT_FOUND')
    gate = deepcopy(gates[ids.index(manifest['gate_id'])])
    _require(all(g['result'] in ('PASS', 'FAIL', 'INCONCLUSIVE', 'UNVERIFIED') for g in gates),
             'UNKNOWN_NATIVE_VERDICT')
    counts = dict(Counter(g['result'] for g in gates))
    _require(qa['counts'] == counts, 'NATIVE_COUNTS_MISMATCH')
    _require(isinstance(qa['reviewer'], str) and bool(qa['reviewer'].strip()) and
             isinstance(qa['production_approval'], str), 'NATIVE_REVIEWER_AND_APPROVAL_REQUIRED')
    native_id = evidence['qa']['sha256'] + '#' + gate['gate_id']
    state['native_export'] = {
        'native_qa': {'id': native_id, 'gate_id': gate['gate_id'], 'gate': gate,
                      'counts': counts, 'reviewer': qa['reviewer'],
                      'approval': qa['production_approval'],
                      'schema_version': qa['schema_version'],
                      'evidence_level': 'EXISTING_NATIVE_QA_NOT_A_NEW_VISUAL_REVIEW'},
        'files': evidence,
        'uncertainties': {'world_disappearance_mechanism': 'UNVERIFIED',
                          'active_assistance': 'UNVERIFIED', 'load_transfer': 'UNVERIFIED'},
        'source_authority': 'LOCAL_RECORD_PROVENANCE_NOT_CRYPTOGRAPHIC_AUTHORSHIP',
        'formal_qa_mutation': False,
    }
    source_hash = evidence['source']['sha256']
    _require(_hash(qa['source']['sha256']) == source_hash == _hash(timeline['source_sha256'])
             == _hash(delivery['output']['sha256']), 'NATIVE_VIDEO_BINDING_MISMATCH')
    _require(_same_path(qa['source']['path'], files['source']['path']) and
             _same_path(delivery['output']['path'], files['source']['path']) and
             _same_path(delivery['qa_report'], files['qa']['path']), 'DELIVERY_QA_OR_SOURCE_PATH_MISMATCH')
    fingerprints = delivery['fingerprints']
    _require(_hash(fingerprints['source_prompt_sha256']) == evidence['source_prompt']['sha256'] and
             _hash(fingerprints['effective_prompt_sha256']) == evidence['effective_prompt']['sha256'],
             'DELIVERY_PROMPT_BINDING_MISMATCH')
    source_prompt, effective = raw['source_prompt'], raw['effective_prompt']
    if source_prompt == effective:
        relation = 'EXACT_BYTES'
    elif source_prompt == effective + b'\n' and not effective.endswith(b'\n'):
        relation = 'SOURCE_HAS_ONE_ADDITIONAL_TERMINAL_LF'
    else:
        raise ValueError('UNREVIEWED_SOURCE_EFFECTIVE_TRANSFORMATION')
    _require(_hash(compiled['trace']['canonical_task_sha256']) == json_sha256(canonical),
             'CANONICAL_COMPILER_BINDING_MISMATCH')
    _require(compiled['prompt'].encode('utf-8') == source_prompt, 'COMPILER_SOURCE_BYTES_MISMATCH')
    baseline = {'intent': deepcopy(canonical['shot_intent']['data']),
                'bindings': [deepcopy(r['data']['compiler_binding']) for r in canonical['reference_bindings']],
                'preflight': deepcopy(compiled['preflight'])}
    state['native_export']['prompt_binding'] = {
        'source_sha256': evidence['source_prompt']['sha256'],
        'effective_sha256': evidence['effective_prompt']['sha256'], 'relation': relation,
        'scope': 'EXISTING_DELIVERY_RECEIPT_NOT_A_NEW_PROVIDER_READBACK',
        'canonical_sha256': json_sha256(canonical), 'baseline_input_sha256': json_sha256(baseline)}
    pts, duration, probe = _probe(files, timeline)
    recorded = timeline['source_probe']['frames']
    _require(len(recorded) == len(pts) and _time(timeline['source_probe']['format']['duration']) == duration,
             'LIVE_NATIVE_TIMELINE_MISMATCH')
    for i, frame in enumerate(recorded):
        _require(type(frame['zero_based_frame_index']) is int and frame['zero_based_frame_index'] == i and
                 _time(frame['best_effort_timestamp_time']) == pts[i] and
                 _time(frame['pts_time']) == pts[i], 'FRAME_INDEX_PTS_MISMATCH')
    selected = manifest['frames']
    _require(isinstance(selected, list) and all(isinstance(f, dict) and set(f) == {
        'frame', 'path', 'sha256'} for f in selected), 'EXACT_FRAME_REFERENCES_REQUIRED')
    numbers = [f['frame'] for f in selected]
    _require(all(type(i) is int and 0 <= i < len(pts) for i in numbers) and
             len(set(numbers)) == len(numbers), 'DUPLICATE_OR_INVALID_SELECTED_FRAME')
    frame_refs = {f['frame']: {'path': f['path'], 'sha256': f['sha256']} for f in selected}
    observations = gate['evidence']
    if not observations:
        raise MissingEvidence('NATIVE_FAILURE_FRAMES_MISSING')
    expected_frames = [f['frame_index'] for f in observations]
    _require(len(set(expected_frames)) == len(expected_frames) and
             set(expected_frames) == set(numbers), 'NATIVE_SELECTED_FRAME_SET_MISMATCH')
    frame_proofs = []
    for obs in observations:
        i = obs['frame_index']
        _require(type(i) is int and 0 <= i < len(pts), 'INVALID_NATIVE_FRAME_INDEX')
        rec, ref = recorded[i], frame_refs[i]
        data = _read(ref)
        _require(_time(obs['actual_pts_seconds']) == pts[i], 'QA_FRAME_PTS_MISMATCH')
        _require(_same_path(obs['file'], ref['path']) and _same_path(rec['extracted_file'], ref['path']),
                 'UNPROVEN_FRAME_RELOCATION')
        _require(sha256_bytes(data) == _hash(rec['extracted_sha256']), 'NATIVE_FRAME_BYTES_MISMATCH')
        frame_proofs.append({'frame': i, 'pts_s': float(pts[i]),
                             'native_pts': obs['actual_pts_seconds'],
                             'path': ref['path'], 'sha256': sha256_bytes(data)})
    state['native_export'].update(frames=frame_proofs, probe=probe,
                                  video_sha256=source_hash, actual_pts_s=[str(t) for t in pts])
    state['native_integrity'] = 'VERIFIED_BYTES_AND_REFERENCES'
    clause = manifest['rule_clause']
    _require(isinstance(clause, str) and bool(clause.strip()), 'RULE_CLAUSE_REQUIRED')
    _require(manifest['failure_type'] in ROUTES, 'UNKNOWN_FAILURE_ROUTE')
    # This native gate names screen continuity; never route it as physical force.
    if gate['gate_id'].endswith('_PROP_THREAT_CONTINUITY'):
        _require(manifest['failure_type'] == 'PROP_SCREEN_CONTINUITY', 'NATIVE_GATE_ROUTE_MISMATCH')
    state['native_export']['rule_mapping'] = {
        'native_gate_id': gate['gate_id'], 'native_criterion': gate['unchanged_criterion'],
        'failure_type': manifest['failure_type'], 'selected_clause': clause,
        'provenance': 'CALLER_SELECTED_LITERAL_RULE_REQUIRES_HUMAN_REVIEW',
        'semantic_alignment': 'UNVERIFIED', 'approval': 'NOT_GRANTED',
        'scope': 'Literal coverage is checked; relevance to the QA failure needs semantic review.'}
    if clause not in source_prompt.decode('utf-8') or clause not in effective.decode('utf-8'):
        raise MissingEvidence('RULE_NOT_LITERAL_IN_BOTH_PROMPTS_NOT_PROOF_OF_TEXT_GAP')
    interval = [float(pts[min(numbers)]), float(pts[max(numbers)])]
    # This is a derived observation envelope. It preserves the native QA result;
    # kind=OBSERVED is the adapter wire vocabulary, not a newly performed review.
    observation = _artifact('native/observation.json', {
        'kind': 'OBSERVED', 'failure_type': manifest['failure_type'],
        'source_sha256': source_hash, 'pts_s': interval,
        'provenance': 'DERIVED_FROM_NATIVE_QA_RECORD_NO_NEW_VISUAL_VERDICT',
        'native_qa_id': native_id, 'native_qa_sha256': evidence['qa']['sha256'],
        'original_result': gate['result'], 'original_reason': gate['reason'],
        'frames': frame_proofs})
    source = _artifact('native/source', raw['source'])
    pts_artifact = _artifact('native/pts.json', {'source_sha256': source_hash,
        'pts_s': [float(t) for t in pts], 'duration_s': float(duration),
        'native_extraction_sha256': evidence['timeline']['sha256'], 'live_probe': probe})
    row = {'qa_id': native_id, 'ref': observation.ref, 'observed_status': gate['result'],
           'source_sha256': source_hash, 'pts_s': interval,
           'historical_prompt_sha256': evidence['source_prompt']['sha256'],
           'candidate_prompt_sha256': evidence['source_prompt']['sha256'],
           'constraint_status': 'PRESENT_BUT_OUTPUT_FAILED' if gate['result'] == 'FAIL' else 'PRESENT',
           'constraint_present_in_source': True, 'change_scope': 'TEXT_ONLY',
           'expected_mechanism': clause, 'failure_type': manifest['failure_type'],
           'source_ref': source.ref, 'pts_ref': pts_artifact.ref, 'pts_sha256': pts_artifact.sha256}
    report = _artifact('native/adapter_qa.json', {'schema_version': 1,
        'input_sha256': json_sha256(baseline), 'records': [row]})
    state['native_export']['adapter_envelopes'] = {
        'qa': _json(report.content), 'observation': _json(observation.content),
        'pts': _json(pts_artifact.content),
        'sha256': {a.ref: a.sha256 for a in (report, observation, pts_artifact)}}
    proposal = propose_revision(baseline=baseline, compiled=compiled, qa_report=report,
        artifacts={a.ref: a for a in (source, observation, pts_artifact)}, qa_id=native_id,
        required_clauses=[clause], enabled=True)
    state['adapter_result'] = proposal
    _require(proposal['status'] != 'BLOCKED', 'ADAPTER_BINDING_REJECTED')
    _require(proposal['status'] == 'NO_PROMPT_CHANGE_JUSTIFIED' and proposal['field_diffs'] == [],
             'NATIVE_BRIDGE_DOES_NOT_AUTHORIZE_REWRITE')
    validate_candidate_input(proposal, expected_baseline_input_sha256=json_sha256(baseline),
                             expected_proposal_sha256=json_sha256(proposal))
    _require(proposal['candidate_prompt_sha256'] == evidence['source_prompt']['sha256'],
             'NO_CHANGE_PROMPT_HASH_MISMATCH')
    state['field_diffs'] = []
    state['unchanged_hashes'] = {'input_sha256': json_sha256(baseline),
        'source_prompt_sha256': evidence['source_prompt']['sha256'],
        'effective_prompt_sha256': evidence['effective_prompt']['sha256']}
    state['decision_basis'] = ('LITERAL_RULE_PRESENT_MAPPING_HUMAN_REVIEW' if gate['result'] == 'FAIL' and
        proposal['reason'] == 'EXISTING_RULE_VIDEO_FAILURE_IS_NOT_A_TEXT_GAP' and
        proposal['evidence_integrity'] == 'VERIFIED_BYTES' and
        proposal['pts_verification'] == 'SOURCE_MANIFEST_BOUND' else 'INSUFFICIENT_EVIDENCE')
    state['status'] = 'HUMAN_REVIEW'
    # Re-read every input. No original QA, frame, Prompt, video or tool is written.
    for name, ref in files.items():
        _require(sha256_bytes(_read(ref)) == evidence[name]['sha256'], 'INPUT_CHANGED_DURING_EXPORT')
    for ref in frame_refs.values():
        _read(ref)
    state['files_unchanged'] = True
    state['checked_file_count'] = len(files) + len(frame_refs)


def export_native_qa(manifest, *, enabled=DEFAULT_ADAPTER_ENABLED):
    """Return a private export and the unchanged adapter's decision.

Only the existing frame-based native profile is supported. This bridge verifies
local provenance, not the truth of a historical visual judgement or its author's
identity. An absent literal clause is insufficient evidence, never an automatic
MISSING rule. The manifest selects inputs; it grants no approval or generation.
"""
    state = {'status': 'DISABLED', 'decision_basis': 'NOT_EVALUATED',
             'native_integrity': 'UNVERIFIED', 'adapter_result': None,
             'review_status': 'HUMAN_REVIEW', 'prompt_eligible': False,
             'production_admitted': False, 'generation_authorization': 'NONE',
             'provider_calls': 0, 'paid_usage': 0, 'authorization_consumptions': 0,
             'new_generations': 0, 'new_compilations': 0, 'files_unchanged': None}
    if type(enabled) is not bool:
        return dict(state, status='BLOCKED_INTEGRITY_MISMATCH', reason='ENABLED_MUST_BE_BOOLEAN')
    if not enabled:
        return dict(state, reason='DEFAULT_ADAPTER_ENABLED_FALSE')
    try:
        _export(deepcopy(manifest), state)
    except (MissingEvidence, FileNotFoundError, KeyError) as exc:
        state.update(status='INSUFFICIENT_EVIDENCE', decision_basis='INSUFFICIENT_EVIDENCE',
                     reason=str(exc))
    except (ValueError, TypeError, AttributeError, IndexError, OSError, OverflowError,
            InvalidOperation, subprocess.SubprocessError) as exc:
        state.update(status='BLOCKED_INTEGRITY_MISMATCH', decision_basis='INTEGRITY_REJECTED',
                     native_integrity='UNVERIFIED', reason=str(exc))
    return state

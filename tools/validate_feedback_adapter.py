"""Explicitly enabled, synthetic-only verification against a pinned local compiler.

No files are written. JSON goes to stdout for the caller's private report. The
Python audit hook is a cooperative guard, not an OS sandbox; the one allowed
Node subprocess is the inspected existing local schema validator. No provider,
production-state, media or authorization entrypoint is imported or invoked.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def json_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def file_record(path):
    return {'path': str(path), 'sha256': digest_bytes(path.read_bytes())}


def install_guard(node, validator, expected, reads, calls):
    """Deny writes/network and allow only the exact local validator command."""
    denied = {'os.remove', 'os.rename', 'os.rmdir', 'os.mkdir', 'os.link',
              'os.symlink', 'os.truncate', 'os.chmod', 'os.chown', 'os.utime',
              'os.system', 'os.startfile', 'os.exec', 'os.posix_spawn',
              'os.fork', 'os.forkpty', 'os.spawn'}
    write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

    def audit(event, args):
        if event.startswith('socket.') or event in denied:
            raise RuntimeError('OFFLINE_GUARD_DENIED:' + event)
        if event == 'open':
            name, mode, flags = args
            # Existing pipe descriptors and the null device are standard I/O.
            if isinstance(name, int) or str(name).casefold() == os.devnull.casefold():
                return
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')
                    or isinstance(flags, int) and flags & write_flags):
                raise RuntimeError('OFFLINE_GUARD_FILE_WRITE_DENIED')
            if isinstance(name, (str, bytes, os.PathLike)):
                reads.add(os.fsdecode(name))
        if event == 'subprocess.Popen':
            executable, arguments, cwd, environment = args
            command = [str(node), str(validator)]
            # Windows emits the already encoded command line and executable=None.
            exact_command = ((str(executable) == str(node) and arguments == command)
                             or (os.name == 'nt' and executable is None
                                 and arguments == subprocess.list2cmdline(command)))
            if (not exact_command
                    or environment is None
                    or set(environment) - {'SystemRoot', 'WINDIR', 'TEMP', 'TMP'}):
                raise RuntimeError('OFFLINE_GUARD_SUBPROCESS_DENIED')
            for path, sha in expected.items():
                if digest_bytes(path.read_bytes()) != sha:
                    raise RuntimeError('SCHEMA_SUBPROCESS_DEPENDENCY_CHANGED')
            calls.append({'executable': str(node), 'arguments': command,
                          'purpose': 'LOCAL_JSON_SCHEMA_VALIDATION'})

    sys.addaudithook(audit)


def fixture_artifacts(adapter, baseline, compiled, *, clause, failure, already_present=False):
    """Hash actual synthetic bytes; no claim these are video-decoded observations."""
    def artifact(ref, value):
        content = value if isinstance(value, bytes) else json_bytes(value)
        return adapter.Artifact(ref, content, digest_bytes(content))

    source = artifact('synthetic:source', b'SYNTHETIC_SOURCE_NOT_A_VIDEO\n')
    pts = artifact('synthetic:pts', {
        'source_sha256': source.sha256, 'duration_s': 4,
        'pts_s': [0, 1, 2, 4], 'origin': 'SYNTHETIC_TEST_MANIFEST',
    })
    observation = artifact('synthetic:observation', {
        'kind': 'OBSERVED', 'failure_type': failure,
        'source_sha256': source.sha256, 'pts_s': [1, 2],
        'scope': 'SYNTHETIC_TEST_RECORD_NOT_VISUAL_QA',
    })
    prompt_hash = digest_bytes(compiled['prompt'].encode('utf-8'))
    row = {
        'qa_id': 'SYNTHETIC_EXPRESSION_CHECK', 'ref': observation.ref,
        'failure_type': failure, 'expected_mechanism': clause,
        'observed_status': 'FAIL', 'change_scope': 'TEXT_ONLY',
        'constraint_status': 'PRESENT_BUT_OUTPUT_FAILED' if already_present else 'MISSING',
        'constraint_present_in_source': already_present, 'constraint_index': 0,
        'historical_prompt_sha256': prompt_hash, 'candidate_prompt_sha256': prompt_hash,
        'source_ref': source.ref, 'source_sha256': source.sha256,
        'pts_ref': pts.ref, 'pts_sha256': pts.sha256, 'pts_s': [1, 2],
        'prompt_eligible': False, 'director_approved': False,
    }
    report = artifact('synthetic:qa', {
        'schema_version': 1, 'input_sha256': adapter.json_sha256(baseline),
        'records': [row], 'scope': 'SYNTHETIC_TEST_RECORDS_ONLY',
    })
    return report, {a.ref: a for a in (source, pts, observation)}, row['qa_id']


def exercise(adapter, compiler, baseline, *, clause='No cuts', already_present=False):
    before = json_bytes(baseline)
    trusted_baseline_sha256 = adapter.json_sha256(baseline)
    compiled = compiler.compile_video(**deepcopy(baseline))
    failure = 'CAMERA_CONTINUITY' if clause == 'No cuts' else 'AUDIO_CONSTRAINT'
    category = 'CAMERA' if clause == 'No cuts' else 'AUDIO'
    target_field = 'camera_note' if clause == 'No cuts' else 'sound_note'
    report, artifacts, qa_id = fixture_artifacts(
        adapter, baseline, compiled, clause=clause, failure=failure,
        already_present=already_present)
    artifact_before = {a.ref: digest_bytes(a.content)
                       for a in [report, *artifacts.values()]}
    required = tuple(row['text'] for row in compiled['sentence_audit']['sentences']
                     if row['category'] != category)
    proposal = adapter.propose_revision(
        baseline=baseline, compiled=compiled, qa_report=report, artifacts=artifacts,
        qa_id=qa_id, required_clauses=required, enabled=True)
    expected = 'NO_PROMPT_CHANGE_JUSTIFIED' if already_present else 'REVISION_PROPOSED'
    if proposal['status'] != expected:
        raise ValueError('UNEXPECTED_PROPOSAL:' + json.dumps(proposal, ensure_ascii=True))
    trusted_proposal_sha256 = adapter.json_sha256(proposal)
    adapter.validate_candidate_input(
        proposal, expected_baseline_input_sha256=trusted_baseline_sha256,
        expected_proposal_sha256=trusted_proposal_sha256)
    candidate = compiler.compile_video(**deepcopy(proposal['candidate_input']))
    review = adapter.review_compilation(
        proposal=proposal, baseline_compiled=compiled, candidate_compiled=candidate,
        effective_prompt=candidate['prompt'].encode('utf-8'),
        expected_baseline_input_sha256=trusted_baseline_sha256,
        expected_proposal_sha256=trusted_proposal_sha256)
    unchanged = before == json_bytes(baseline)
    evidence_unchanged = artifact_before == {
        a.ref: digest_bytes(a.content) for a in [report, *artifacts.values()]}
    changed_keys = [row['sources'] for row in candidate['sentence_audit']['sentences']
                    if row['category'] == category]
    checks = {
        'expected_proposal': proposal['status'] == expected,
        'human_review_preserved': review['status'] == 'HUMAN_REVIEW',
        'input_unchanged': unchanged, 'original_qa_and_evidence_unchanged': evidence_unchanged,
        'candidate_clause_expressed': clause.casefold() in candidate['prompt'].casefold(),
        'production_admission_false': review.get('production_admitted') is False,
        'required_clauses_preserved': review.get('required_clause_coverage', {}).get('status') == 'PASS',
    }
    if already_present:
        checks['no_change_prompt_hash_unchanged'] = compiled['prompt'] == candidate['prompt']
        checks['no_change_structured_fields'] = proposal['field_diffs'] == []
    else:
        checks['baseline_clause_missing'] = clause.casefold() not in compiled['prompt'].casefold()
        checks['one_field_only'] = [r['path'] for r in proposal['field_diffs']] == ['intent.' + target_field]
        checks['actual_prompt_changed'] = compiled['prompt'] != candidate['prompt']
    return {
        'case': 'PRESENT_BUT_OUTPUT_FAILED' if already_present else 'MISSING_EXPRESSION',
        'projection_clause': clause,
        'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
        'synthetic_artifacts': [{'ref': a.ref, 'sha256': a.sha256,
                                'content_utf8': a.content.decode('utf-8')}
                               for a in [report, *artifacts.values()]],
        'proposal': proposal, 'baseline_compiled': compiled,
        'candidate_compiled': candidate, 'review': review,
        'changed_sentence_sources': changed_keys,
    }


def run(args):
    if not args.enable_adapter:
        return {'status': 'DISABLED', 'reason': 'DEFAULT_ADAPTER_ENABLED_FALSE',
                'compiler_invoked': False, 'production_admitted': False}, 0
    if not args.engine_root or not re.fullmatch(r'[0-9a-fA-F]{64}', args.compiler_sha256 or ''):
        raise ValueError('EXPLICIT_ENGINE_ROOT_AND_COMPILER_SHA256_REQUIRED')
    project = Path(args.engine_root).resolve(strict=True)
    engine = project / '01_engine'
    compiler_path = engine / 'production_kernel_1_5_1_compiler.py'
    compiler_bytes = compiler_path.read_bytes()
    actual_compiler = {'path': str(compiler_path), 'sha256': digest_bytes(compiler_bytes)}
    if actual_compiler['sha256'] != args.compiler_sha256.lower():
        raise ValueError('COMPILER_SHA256_MISMATCH')
    schema_dir = engine / 'browser_transport/libtv_domshell/json_schemas'
    validator = schema_dir / '_validate.cjs'
    provenance_path = schema_dir / 'ENGINE_PROVENANCE.json'
    provenance = json.loads(provenance_path.read_bytes())
    node = Path(provenance['node_path']).resolve(strict=True)
    subprocess_pins = {p: digest_bytes(p.read_bytes()) for p in (node, validator, provenance_path)}
    if subprocess_pins[node].lower() != provenance['node_sha256'].lower():
        raise ValueError('NODE_SHA256_DIFFERS_FROM_EXISTING_ENGINE_PROVENANCE')
    for item in provenance['pinned_files']:
        path = Path(item['path']).resolve(strict=True)
        observed = digest_bytes(path.read_bytes())
        if observed != item['sha256'].lower():
            raise ValueError('EXISTING_AJV_DEPENDENCY_HASH_MISMATCH')
        subprocess_pins[path] = observed
    # The existing validator preloads each of these schemas, so pin them too.
    for path in schema_dir.glob('*.schema.json'):
        subprocess_pins[path] = digest_bytes(path.read_bytes())
    reads, calls = set(), []
    install_guard(node, validator, subprocess_pins, reads, calls)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    sys.path.insert(0, str(engine))
    # Execute the exact pinned source bytes, never an unverified cached .pyc.
    spec = importlib.util.spec_from_file_location('production_kernel_1_5_1_compiler', compiler_path)
    compiler = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = compiler
    exec(compile(compiler_bytes, str(compiler_path), 'exec'), compiler.__dict__)
    fixture = importlib.import_module('test_production_kernel_1_5_1_compiler')
    adapter = importlib.import_module('novel_drama_candidate.feedback_adapter')
    if Path(compiler.__file__).resolve() != compiler_path or compiler.VERSION != '1.5.1':
        raise ValueError('LOADED_COMPILER_IDENTITY_MISMATCH')
    baseline = {'intent': fixture.synthetic_intent(), 'bindings': [],
                'preflight': {'overall': 'UNVERIFIED', 'bindings_sha256': adapter.json_sha256([]),
                              'chosen_mode': 'text2video'}}
    positive = exercise(adapter, compiler, baseline)
    negative = exercise(adapter, compiler, deepcopy(positive['proposal']['candidate_input']),
                        already_present=True)
    cases = [positive, negative]
    for clause in ('No dialogue', 'No music'):
        audio_baseline = deepcopy(baseline)
        audio_baseline['intent']['negative_constraints'][0] = clause
        cases.append(exercise(adapter, compiler, audio_baseline, clause=clause))
    dependencies = set(subprocess_pins) | {compiler_path}
    checkout = Path(__file__).resolve().parents[1]
    for name in tuple(reads):
        path = Path(name).resolve()
        if path.is_file() and (path.is_relative_to(project) or path.is_relative_to(checkout)):
            dependencies.add(path)
    dependency_records = [file_record(p) for p in sorted(dependencies, key=str)]
    if digest_bytes(compiler_path.read_bytes()) != actual_compiler['sha256']:
        raise ValueError('COMPILER_CHANGED_DURING_RUN')
    good = all(case['status'] == 'PASS' for case in cases)
    return {
        'schema_version': 1, 'checked_at': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS' if good else 'FAIL', 'scope': 'SYNTHETIC_OFFLINE_COMPILER_INTEGRATION',
        'compiler': actual_compiler, 'dependencies': dependency_records,
        'node': file_record(node), 'subprocess_calls': calls,
        'guard_scope': 'COOPERATIVE_PYTHON_AUDIT_NOT_OS_SANDBOX; EXISTING_PINNED_NODE_VALIDATOR_ONLY',
        'cases': cases, 'review_status': 'HUMAN_REVIEW',
        'production_admitted': False, 'provider_calls': 0, 'paid_usage': 0,
        'authorization_consumptions': 0, 'files_written_by_runner': 0,
        'new_generations': 0, 'visual_quality_improvement': 'NOT_TESTED',
        'source_evidence_scope': 'SYNTHETIC_BYTES_AND_DECLARED_PTS; NOT_REAL_VIDEO_QA',
        'provider_effective_status': 'UNVERIFIED_NOT_INVOKED',
    }, 0 if good else 1


def main():
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-adapter', action='store_true')
    parser.add_argument('--engine-root', help='Private project root containing 01_engine; read only')
    parser.add_argument('--compiler-sha256', help='Expected SHA256 of existing Compiler 1.5.1 bytes')
    args = parser.parse_args()
    try:
        result, code = run(args)
    except Exception as error:
        result, code = {'status': 'BLOCKED', 'error_type': type(error).__name__,
                        'reason': str(error), 'review_status': 'HUMAN_REVIEW',
                        'production_admitted': False, 'provider_calls': 0,
                        'paid_usage': 0, 'authorization_consumptions': 0}, 1
    # ASCII JSON is portable across Windows code pages; values retain Unicode.
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())

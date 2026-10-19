"""Default-off, offline QA -> structured text proposal, never an approval gate.

Only project an existing explicit constraint into a compiler-visible text field.
Hash/PTS checks establish integrity of supplied records, not visual truth or the
authority of their author. Production admission remains false in every result.
"""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import re

from .qa_feedback import qa_feedback_map
from .prompt_candidate import exact_clause_coverage, verify_prompt_fidelity

DEFAULT_ADAPTER_ENABLED = False

ROUTES = {
    'CAMERA_CONTINUITY': ('Cinematic Video Director', ('camera_note',)),
    'AUDIO_CONSTRAINT': ('Cinematic Video Director', ('sound_note',)),
    'CONTACT_VS_LOAD': ('Character Performance Director', ('motion_causality.contacts',)),
    'GRIP_VS_FORCE': ('Character Performance Director', ('motion_causality.force_sources',)),
    'PROP_SCREEN_CONTINUITY': ('Asset Spatial Director', ('motion_causality',)),
    'MOTION_TIMING': ('Cinematic Video Director', ('motion_causality.timing_milestones',)),
}
_PROJECTIONS = {
    ('CAMERA_CONTINUITY', 'no cuts'): 'camera_note',
    ('AUDIO_CONSTRAINT', 'no dialogue'): 'sound_note',
    ('AUDIO_CONSTRAINT', 'no music'): 'sound_note',
}


@dataclass(frozen=True)
class Artifact:
    ref: str
    content: bytes
    sha256: str


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def json_sha256(value):
    return sha256_bytes(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                  separators=(',', ':'), allow_nan=False).encode('utf-8'))


def _verified(artifact, ref=None):
    if (not isinstance(artifact, Artifact) or not isinstance(artifact.ref, str)
            or not artifact.ref.strip() or not isinstance(artifact.content, bytes)
            or not isinstance(artifact.sha256, str)
            or not re.fullmatch(r'[a-fA-F0-9]{64}', artifact.sha256)
            or sha256_bytes(artifact.content) != artifact.sha256.lower()
            or ref is not None and artifact.ref != ref):
        raise ValueError('ARTIFACT_HASH_OR_REFERENCE_MISMATCH')
    return artifact.content


def _json(content):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('NONFINITE_JSON_NUMBER')
    return json.loads(content, object_pairs_hook=unique, parse_constant=constant)


def _plain(value):
    return re.sub(r'\s+', ' ', value).strip().rstrip('.;').casefold()


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _contains(text, clause):
    # Literal clause boundaries only. This is not a general semantic entailment test.
    return re.search(r'(?<!\w)' + re.escape(_plain(clause)) + r'(?!\w)', _plain(text)) is not None


def _compiled_prompt(compiled, baseline):
    trace, lint, hep = compiled['trace'], compiled['lint'], compiled['hep']
    prompt = compiled['prompt'].encode('utf-8')
    if (trace.get('prompt_compiler_version') != '1.5.1'
            or trace.get('generation_authorization') != 'NONE'
            or type(trace.get('provider_calls')) is not int or trace['provider_calls'] != 0
            or trace.get('intent_sha256', '').lower() != json_sha256(baseline['intent'])
            or trace.get('bindings_sha256', '').lower() != json_sha256(baseline['bindings'])
            or trace.get('hep_sha256', '').lower() != json_sha256(
                {k: v for k, v in hep.items() if k != 'semantic_reviews'})
            or trace.get('prompt_sha256', '').lower() != sha256_bytes(prompt)
            or lint.get('prompt_sha256', '').lower() != sha256_bytes(prompt)
            or lint.get('schema_status') != 'PASS' or lint.get('runtime_errors') != []
            or lint.get('overall') not in ('PASS', 'UNVERIFIED', 'HUMAN_REVIEW')):
        raise ValueError('COMPILER_OUTPUT_BINDING_OR_OFFLINE_CONTRACT_INVALID')
    return prompt


def _base(status, reason, **details):
    return dict(status=status, reason=reason, review_status='HUMAN_REVIEW',
                rewrite_status='HUMAN_REVIEW', prompt_eligible=False,
                director_approved=False, production_admitted=False,
                generation_authorization='NONE', provider_calls=0,
                paid_usage=0, authorization_consumptions=0, **details)


def propose_revision(*, baseline, compiled, qa_report, artifacts, qa_id,
                     required_clauses, enabled=DEFAULT_ADAPTER_ENABLED):
    """Assess one raw QA row; never trust a historical feedback-result approval.

Artifacts are caller-selected immutable bytes, not URLs or paths to open. PTS
must match the supplied source-bound timestamp manifest; no frames are decoded.
Only camera/audio wording projections are implemented. Other domains are routed
for review with NO_PROMPT_CHANGE_JUSTIFIED, not a fabricated text repair.
    """
    if type(enabled) is not bool:
        return _base('BLOCKED', 'ENABLED_MUST_BE_BOOLEAN')
    if not enabled:
        return _base('DISABLED', 'DEFAULT_ADAPTER_ENABLED_FALSE')
    try:
        if not isinstance(baseline, Mapping) or set(baseline) != {'intent', 'bindings', 'preflight'}:
            raise ValueError('EXACT_COMPILER_INPUT_ENVELOPE_REQUIRED')
        original = deepcopy(baseline)
        prompt = _compiled_prompt(compiled, baseline)
        coverage = exact_clause_coverage(prompt.decode('utf-8'), required_clauses)
        if coverage['status'] != 'PASS':
            raise ValueError('BASELINE_REQUIRED_CLAUSES_NOT_ESTABLISHED')
        report = _json(_verified(qa_report))
        if (not isinstance(report, dict) or report.get('schema_version') != 1
                or 'result' in report or report.get('input_sha256') != json_sha256(baseline)
                or not isinstance(report.get('records'), list)):
            raise ValueError('RAW_QA_AND_EXACT_INPUT_BINDING_REQUIRED')
        records = report['records']
        if not all(isinstance(row, dict) for row in records):
            raise ValueError('QA_ROWS_REQUIRED')
        ids = [r.get('qa_id') for r in records]
        if len(set(ids)) != len(ids) or ids.count(qa_id) != 1:
            raise ValueError('UNIQUE_QA_ID_REQUIRED')
        row = next(r for r in records if r['qa_id'] == qa_id)
        if any(row.get(k) not in (None, False) for k in
               ('prompt_eligible', 'director_approved', 'approved', 'production_admitted')):
            raise ValueError('STALE_ELIGIBILITY_OR_CALLER_APPROVAL_NOT_AUTHORITY')
        if any(row.get(k, '').lower() != sha256_bytes(prompt) for k in
               ('historical_prompt_sha256', 'candidate_prompt_sha256')):
            raise ValueError('QA_PROMPT_HASH_MISMATCH')
        mapped = qa_feedback_map([deepcopy(row)])
        if not mapped.get('records'):
            raise ValueError('QA_FEEDBACK_BINDING_INVALID')
        feedback = mapped['records'][0]
        failure = row.get('failure_type')
        owner, fields = ROUTES.get(failure, ('Prompt Optimizer', ()))
        details = dict(qa_id=qa_id, failure_type=failure,
                       route={'director': owner, 'optimizer': 'Prompt Optimizer',
                              'structured_fields': list(fields)},
                       feedback=feedback, field_diffs=[], baseline_input=original,
                       candidate_input=deepcopy(original),
                       baseline_input_sha256=json_sha256(original),
                       candidate_input_sha256=json_sha256(original),
                       baseline_prompt_sha256=sha256_bytes(prompt),
                       required_clauses=list(required_clauses),
                       qa_report_sha256=sha256_bytes(qa_report.content),
                       evidence_integrity='UNVERIFIED', pts_verification='UNVERIFIED')
        def no_change(reason):
            return _base('NO_PROMPT_CHANGE_JUSTIFIED', reason,
                         candidate_prompt_sha256=sha256_bytes(prompt), **details)
        if feedback['binding_status'] != 'PASS' or not feedback['text_review_in_scope']:
            return no_change('INSUFFICIENT_OR_NON_TEXT_EVIDENCE')
        if row['observed_status'] != 'FAIL':
            return no_change('NO_OBSERVED_FAILURE')
        # Authenticate every linked artifact before deriving a text proposal.
        source = artifacts[row['source_ref']]
        source_bytes = _verified(source, row['source_ref'])
        observation = _json(_verified(artifacts[row['ref']], row['ref']))
        pts_artifact = artifacts[row['pts_ref']]
        pts_manifest = _json(_verified(pts_artifact, row['pts_ref']))
        source_hash = sha256_bytes(source_bytes)
        if (row['source_sha256'].lower() != source_hash
                or observation.get('source_sha256', '').lower() != source_hash
                or pts_manifest.get('source_sha256', '').lower() != source_hash
                or row['pts_sha256'].lower() != sha256_bytes(pts_artifact.content)
                or observation.get('kind') != 'OBSERVED'
                or observation.get('failure_type') != failure
                or observation.get('pts_s') != row['pts_s']):
            raise ValueError('OBSERVATION_SOURCE_OR_PTS_BINDING_MISMATCH')
        pts, duration = pts_manifest.get('pts_s'), pts_manifest.get('duration_s')
        interval = row['pts_s']
        if (not isinstance(pts, list) or not pts or not all(_number(t) for t in pts)
                or not _number(duration) or duration <= 0
                or any(a >= b for a, b in zip(pts, pts[1:]))
                or pts[-1] > duration or interval[1] > duration
                or not all(t in pts for t in interval)):
            raise ValueError('PTS_NOT_IN_SOURCE_MANIFEST')
        details.update(evidence_integrity='VERIFIED_BYTES', pts_verification='SOURCE_MANIFEST_BOUND',
                       evidence_sources=[{'ref': a.ref, 'sha256': sha256_bytes(a.content)}
                                         for a in (qa_report, source, artifacts[row['ref']], pts_artifact)])
        if row['constraint_status'] in ('PRESENT', 'PRESENT_BUT_OUTPUT_FAILED'):
            return no_change('EXISTING_RULE_VIDEO_FAILURE_IS_NOT_A_TEXT_GAP')
        if row['constraint_status'] != 'MISSING' or row.get('constraint_present_in_source') is not False:
            return no_change('TEXT_GAP_NOT_ESTABLISHED')
        index = row.get('constraint_index')
        constraints = original['intent'].get('negative_constraints', [])
        if type(index) is not int or not 0 <= index < len(constraints):
            return no_change('EXISTING_STRUCTURED_CONSTRAINT_REQUIRED')
        clause = constraints[index]
        if not isinstance(clause, str) or row['expected_mechanism'] != clause:
            raise ValueError('CONSTRAINT_PROVENANCE_MISMATCH')
        if _contains(prompt.decode('utf-8'), clause):
            return no_change('RULE_ALREADY_EXPLICIT_IN_SOURCE_PROMPT')
        target = _PROJECTIONS.get((failure, _plain(clause)))
        if target is None:
            return no_change('NO_REVIEWED_TEXT_PROJECTION_FOR_DOMAIN')
        before = original['intent'].get(target)
        if not isinstance(before, str) or not before.strip():
            return no_change('EXISTING_COMPILER_TEXT_FIELD_REQUIRED')
        if _contains(before, clause):
            return no_change('FIELD_ALREADY_HAS_RULE_COMPILER_MAPPING_REVIEW_REQUIRED')
        # A semicolon retains one SentenceIR sentence without adding a new fact.
        after = before.rstrip().rstrip('.;') + '; ' + _plain(clause)
        details['candidate_input']['intent'][target] = after
        details['candidate_input_sha256'] = json_sha256(details['candidate_input'])
        details['field_diffs'] = [{'path': 'intent.' + target, 'before': before,
                                  'after': after, 'constraint_index': index}]
        details['projection_clause'] = clause
        details['justification'] = 'Project the existing structured constraint into its reviewed compiler text field; no new action or approved fact.'
        return _base('REVISION_PROPOSED', 'EXISTING_CONSTRAINT_MISSING_FROM_COMPILED_EXPRESSION', **details)
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, OverflowError) as exc:
        return _base('BLOCKED', str(exc) if isinstance(exc, ValueError) else type(exc).__name__)


def validate_candidate_input(proposal, *, expected_baseline_input_sha256,
                             expected_proposal_sha256):
    """Reconstruct the sole permitted change; reject every hidden field mutation."""
    if json_sha256(proposal) != expected_proposal_sha256:
        raise ValueError('PROPOSAL_EVIDENCE_OR_DIFF_CHANGED')
    original, candidate = proposal['baseline_input'], proposal['candidate_input']
    if (proposal['baseline_input_sha256'] != expected_baseline_input_sha256
            or proposal['baseline_input_sha256'] != json_sha256(original)
            or proposal['candidate_input_sha256'] != json_sha256(candidate)):
        raise ValueError('INPUT_HASH_MISMATCH')
    expected = deepcopy(original)
    diffs = proposal['field_diffs']
    if proposal['status'] == 'NO_PROMPT_CHANGE_JUSTIFIED':
        if diffs or candidate != original:
            raise ValueError('NO_CHANGE_INPUT_MUTATED')
    elif proposal['status'] == 'REVISION_PROPOSED':
        if len(diffs) != 1:
            raise ValueError('EXACTLY_ONE_FIELD_CHANGE_REQUIRED')
        change = diffs[0]
        index = change['constraint_index']
        if type(index) is not int or index < 0:
            raise ValueError('CONSTRAINT_INDEX_INVALID')
        clause = original['intent']['negative_constraints'][index]
        if proposal.get('projection_clause') != clause:
            raise ValueError('PROJECTION_CLAUSE_CHANGED')
        field = _PROJECTIONS.get((proposal['failure_type'], _plain(clause)))
        if field is None or change['path'] != 'intent.' + field:
            raise ValueError('PROTECTED_OR_UNSUPPORTED_FIELD_CHANGE')
        before = original['intent'][field]
        after = before.rstrip().rstrip('.;') + '; ' + _plain(clause)
        if change['before'] != before or change['after'] != after:
            raise ValueError('UNAPPROVED_TEXT_CHANGE')
        expected['intent'][field] = after
    else:
        raise ValueError('PROPOSAL_NOT_COMPILABLE')
    if candidate != expected:
        raise ValueError('UNAPPROVED_STRUCTURED_CHANGE')
    return True


def review_compilation(*, proposal, baseline_compiled, candidate_compiled, effective_prompt,
                       expected_baseline_input_sha256, expected_proposal_sha256):
    """Check actual compiler results and an explicit offline delivery byte string.

The caller invokes the pinned local compiler. This pure function cannot prove
the execution identity of an arbitrary supplied dict. The isolated runner logs
that invocation separately. No provider Effective Prompt is asserted here.
    """
    try:
        validate_candidate_input(proposal,
                                 expected_baseline_input_sha256=expected_baseline_input_sha256,
                                 expected_proposal_sha256=expected_proposal_sha256)
        old = _compiled_prompt(baseline_compiled, proposal['baseline_input'])
        source = _compiled_prompt(candidate_compiled, proposal['candidate_input'])
        if sha256_bytes(old) != proposal['baseline_prompt_sha256']:
            raise ValueError('BASELINE_PROMPT_CHANGED')
        required = tuple(proposal['required_clauses'])
        if exact_clause_coverage(old.decode('utf-8'), required)['status'] != 'PASS':
            raise ValueError('BASELINE_REQUIRED_CLAUSES_LOST')
        if not isinstance(effective_prompt, bytes):
            raise ValueError('ACTUAL_OFFLINE_EFFECTIVE_BYTES_REQUIRED')
        fidelity = verify_prompt_fidelity(source, effective_prompt,
            expected_source_sha256=sha256_bytes(source),
            expected_effective_sha256=sha256_bytes(effective_prompt), required=required)
        if fidelity['status'] != 'PASS':
            raise ValueError('OFFLINE_HANDOFF_FIDELITY_FAILED')
        if proposal['status'] == 'NO_PROMPT_CHANGE_JUSTIFIED' and source != old:
            raise ValueError('NO_CHANGE_PROMPT_HASH_CHANGED')
        if proposal['status'] == 'REVISION_PROPOSED':
            clause = proposal['projection_clause']
            if source == old or _contains(old.decode('utf-8'), clause) or not _contains(source.decode('utf-8'), clause):
                raise ValueError('PROJECTED_CONSTRAINT_NOT_NEWLY_EXPRESSED')
        return _base('HUMAN_REVIEW', 'OFFLINE_EXPRESSION_AND_FIDELITY_CHECKED',
                     baseline_prompt_sha256=sha256_bytes(old), candidate_prompt=source.decode('utf-8'),
                     candidate_prompt_sha256=sha256_bytes(source), source_sha256=sha256_bytes(source),
                     effective_sha256=sha256_bytes(effective_prompt),
                     hash_scope='OFFLINE_IDENTITY_HANDOFF', provider_effective_sha256=None,
                     provider_effective_status='UNVERIFIED_NOT_INVOKED',
                     required_clause_coverage=fidelity['source_coverage'], fidelity=fidelity,
                     compiler_lint_overall=candidate_compiled['lint']['overall'],
                     visual_quality_improvement='NOT_TESTED', approval_authority='NOT_ESTABLISHED')
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, UnicodeError) as exc:
        return _base('BLOCKED', str(exc) if isinstance(exc, ValueError) else type(exc).__name__)

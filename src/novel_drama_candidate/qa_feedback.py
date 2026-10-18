"""Private offline evidence sidecars; no generation, approval, or physical truth oracle.

PASS means only consistency of caller-supplied, hash-bound records in their stated
PTS interval. Callers authenticate sources. Unknown world state remains unknown.
"""
from collections.abc import Mapping
from dataclasses import asdict
import math
import re

from .motion_contract import Finding, Observation, check_object_lifecycle
from .prompt_candidate import verify_prompt_fidelity

_EVENTS = {'FOOT_CONTACT', 'FOOT_OFF_LID', 'FIRST_VISIBLE', 'PALM_CONTACT',
           'FOREARM_LOAD', 'GRIP', 'ACTIVE_ASSISTANCE', 'FORCE_SOURCE', 'CONTACT',
           'BODY_RESPONSE', 'SUPPORT_BEFORE', 'SUPPORT_AFTER', 'SUPPORT_TRANSFER',
           'EXITED', 'OCCLUDED'}
_RANK = ('BLOCKED', 'FAIL', 'HUMAN_REVIEW', 'UNVERIFIED', 'WARN', 'PASS')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-fA-F]{64}', value) is not None


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _pts(value):
    return (isinstance(value, (list, tuple)) and len(value) == 2 and
            all(_number(x) for x in value) and value[0] <= value[1])


def _rows(value):
    return isinstance(value, (list, tuple)) and all(isinstance(x, Mapping) for x in value)


def _finding(rule, status, explanation):
    return asdict(Finding(rule, status, explanation))


def _result(findings, **data):
    status = next((x for x in _RANK if any(f['status'] == x for f in findings)), 'UNVERIFIED')
    return dict(status=status, findings=findings, production_admitted=False,
                scope='Supplied evidence records only; not real-video or physical certification', **data)


def _stop(rule, status='BLOCKED'):
    return _result([_finding(rule, status, 'Required evidence is absent, malformed, or out of scope')])


def check_evidence_claim(claim, evidence):
    """Do not promote a weaker observable into a stronger causal assertion."""
    if not _text(claim):
        return _stop('CLAIM_REQUIRED')
    if evidence is None:
        return _stop('EVIDENCE_REQUIRED', 'UNVERIFIED')
    if not isinstance(evidence, Mapping):
        return _stop('EVIDENCE_RECORD_REQUIRED')
    kind = evidence.get('kind')
    if kind not in ('OBSERVED', 'INFERRED', 'DESIGN_ASSUMPTION', 'UNKNOWN'):
        return _stop('EVIDENCE_KIND_REQUIRED')
    if kind != 'OBSERVED':
        return _stop('OBSERVATION_NOT_ESTABLISHED', 'UNVERIFIED')
    if not (_hash(evidence.get('source_sha256')) and _text(evidence.get('ref')) and
            _pts(evidence.get('pts_s')) and _text(evidence.get('event'))):
        return _stop('HASH_BOUND_ACTUAL_PTS_REQUIRED')
    if claim not in _EVENTS or evidence['event'] != claim:
        return _stop('OBSERVATION_DOES_NOT_ESTABLISH_CLAIM', 'UNVERIFIED')
    return _result([_finding('DIRECT_OBSERVATION_RECORD', 'PASS',
                   'Matching observable recorded; no stronger force, load or world claim')], evidence=dict(evidence))


def motion_load(events, duration_ms, warn_above=3):
    """Count declared unique events, not repeated descriptions of held support."""
    if (not _rows(events) or type(duration_ms) is not int or not _number(duration_ms) or duration_ms <= 0 or
            type(warn_above) is not int or warn_above < 1):
        return _stop('LOAD_INPUT_INVALID')
    if not events:
        return _stop('LOAD_EVENTS_REQUIRED', 'UNVERIFIED')
    seen = set()
    for e in events:
        if (not all(_text(e.get(k)) for k in ('id', 'actor', 'description')) or
                e.get('kind') not in ('ACTIVE_EVENT', 'MAINTAINED_SUPPORT') or
                not _number(e.get('begin_s')) or not _number(e.get('end_s')) or
                not 0 <= e['begin_s'] <= e['end_s'] <= duration_ms / 1000 or e['id'] in seen):
            return _stop('LOAD_EVENT_INVALID_OR_DUPLICATE')
        seen.add(e['id'])
    active = sum(e['kind'] == 'ACTIVE_EVENT' for e in events)
    return _result([_finding('DECLARED_LOAD_ONLY', 'WARN' if active > warn_above else 'PASS',
                   'Threshold is an uncalibrated attention warning, not a provider hard limit')],
                   active_event_count=active, maintained_support_count=len(events)-active,
                   point_event_count=sum(e['begin_s'] == e['end_s'] for e in events),
                   warn_above=warn_above, events=[dict(e) for e in events])


def _force_bindings(chain, parts):
    """Check upstream-supplied identity links; never fill missing observations."""
    findings = []
    def valid(value, location):
        if value is None or isinstance(value, str) and value.strip().upper() in ('UNKNOWN', 'UNVERIFIED'):
            findings.append(_finding('FORCE_BINDING_REQUIRED', 'UNVERIFIED', location))
            return False
        if not _text(value):
            findings.append(_finding('FORCE_BINDING_INVALID', 'BLOCKED', location))
            return False
        return True
    declared = {field: valid(chain.get(field), f"{chain['id']}.{field}")
                for field in ('actor', 'recipient', 'interaction_id', 'contact_id',
                              'support_before_id', 'support_after_id')}
    roles = {
        'force_source': {'actor':'actor', 'recipient':'recipient', 'contact_id':'contact_id'},
        'contact': {'actor':'actor', 'recipient':'recipient', 'contact_id':'contact_id'},
        'body_response': {'actor':'recipient', 'contact_id':'contact_id'},
        'support_before': {'actor':'recipient', 'support_id':'support_before_id'},
        'support_after': {'actor':'recipient', 'support_id':'support_after_id'},
        'transfer': {'actor':'recipient', 'from_support_id':'support_before_id', 'to_support_id':'support_after_id'},
    }
    for key, fields in roles.items():
        if parts[key]['status'] != 'PASS':
            continue
        for field, target in dict(fields, interaction_id='interaction_id').items():
            value = chain[key].get(field)
            location = f"{chain['id']}.{key}.{field} -> {target}"
            if valid(value, location) and declared[target] and value != chain[target]:
                findings.append(_finding('FORCE_BINDING_MISMATCH', 'FAIL', location))
    return findings


def force_causal_chain(chains):
    """actor initiates force; recipient responds. PASS is record consistency only."""
    if not _rows(chains):
        return _stop('FORCE_RECORDS_INVALID')
    if not chains:
        return _stop('FORCE_RECORDS_REQUIRED', 'UNVERIFIED')
    findings, records, seen = [], [], set()
    for chain in chains:
        if not _text(chain.get('id')) or not _text(chain.get('actor')):
            return _stop('FORCE_CHAIN_IDENTITY_REQUIRED')
        if chain['id'] in seen:
            return _stop('FORCE_CHAIN_DUPLICATE')
        seen.add(chain['id'])
        parts = {}
        for key, event in (('force_source','FORCE_SOURCE'), ('contact','CONTACT'),
                           ('body_response','BODY_RESPONSE'), ('support_before','SUPPORT_BEFORE'),
                           ('support_after','SUPPORT_AFTER'), ('transfer','SUPPORT_TRANSFER')):
            parts[key] = check_evidence_claim(event, chain.get(key))
            findings.extend(_finding(f"{chain['id']}.{key}.{f['rule']}", f['status'], f['explanation'])
                            for f in parts[key]['findings'])
        observed = [chain[k] for k, v in parts.items() if v['status'] == 'PASS']
        if len({e['source_sha256'].upper() for e in observed}) > 1:
            findings.append(_finding('FORCE_MIXED_SOURCE', 'BLOCKED', 'One causal chain must refer to one source'))
        findings.extend(_force_bindings(chain, parts))
        if parts['body_response']['status'] == 'PASS':
            for key in ('force_source', 'contact'):
                if parts[key]['status'] != 'PASS':
                    continue
                cause, response = chain[key]['pts_s'], chain['body_response']['pts_s']
                if cause[0] > response[1]:
                    findings.append(_finding('RESPONSE_PRECEDES_CAUSE', 'FAIL', key))
                elif cause[1] >= response[0]:
                    findings.append(_finding('CAUSE_RESPONSE_ORDER_UNCERTAIN', 'UNVERIFIED',
                                            f'{key}: overlapping or touching windows do not establish precedence'))
        if all(parts[k]['status'] == 'PASS' for k in ('support_before', 'transfer', 'support_after')):
            before, transfer, after = (chain[k]['pts_s'] for k in ('support_before', 'transfer', 'support_after'))
            if before[0] > transfer[1] or transfer[0] > after[1] or before[0] > after[1]:
                findings.append(_finding('SUPPORT_TRANSFER_ORDER', 'FAIL', 'Support evidence proves reversed handover order'))
            elif before[1] > transfer[0] or transfer[1] > after[0]:
                findings.append(_finding('SUPPORT_TRANSFER_ORDER_UNCERTAIN', 'UNVERIFIED',
                                        'Overlapping observation windows do not establish exact transfer order'))
        records.append(dict(id=chain['id'], actor=chain['actor'], parts=parts))
    return _result(findings, records=records)


def prop_lifecycle(records, critical_pairs):
    """Reuse object validator without upgrading screen records to world state.

    source_sha256 identifies the original video, identical across its frames.
    A caller may separately retain frame_sha256 and a per-frame evidence ref.
    """
    if not _rows(records) or not _rows(critical_pairs):
        return _stop('PROP_RECORDS_INVALID')
    if not records:
        return _stop('PROP_RECORDS_REQUIRED', 'UNVERIFIED')
    observations, index, source_ids = [], {}, {}
    for r in records:
        if (not _text(r.get('object_id')) or type(r.get('frame')) is not int or r['frame'] < 0 or
                not _number(r.get('pts_s')) or not _hash(r.get('source_sha256')) or
                not _text(r.get('ref')) or r.get('screen_state') not in ('VISIBLE','UNSEEN','OCCLUDED','EXITED')):
            return _stop('PROP_RECORD_INVALID')
        at_ms = r['pts_s'] * 1000
        if not _number(at_ms):
            return _stop('PROP_PTS_CANNOT_CONVERT_TO_MILLISECONDS')
        oid, frame = r['object_id'], r['frame']
        if (oid, frame) in index or (oid in source_ids and source_ids[oid] != r['source_sha256']):
            return _stop('PROP_IDENTITY_OR_FRAME_AMBIGUOUS')
        index[oid, frame] = r
        source_ids[oid] = r['source_sha256']
        explained = check_evidence_claim(r['screen_state'], r.get('cause_evidence'))['status'] == 'PASS'
        if explained:
            e = r['cause_evidence']
            explained = (e['source_sha256'].upper() == r['source_sha256'].upper() and
                         e['pts_s'][0] <= r['pts_s'] <= e['pts_s'][1])
        state = 'ACTIVE' if r['screen_state'] == 'VISIBLE' else r['screen_state']
        observations.append(Observation(round(at_ms), oid, state,
                            r['cause_evidence']['ref'] if explained else '', explained))
    findings = [asdict(f) for f in check_object_lifecycle(observations)]
    for oid in source_ids:
        ordered = sorted((r for r in records if r['object_id'] == oid), key=lambda r: r['frame'])
        if any(a['pts_s'] >= b['pts_s'] for a,b in zip(ordered, ordered[1:])):
            findings.append(_finding('FRAME_PTS_ORDER', 'FAIL', oid))
    for pair in critical_pairs:
        oid, before, after = pair.get('object_id'), pair.get('before_frame'), pair.get('after_frame')
        if not _text(oid) or type(before) is not int or type(after) is not int or before < 0 or after != before + 1:
            return _stop('CRITICAL_PAIR_MUST_BE_ADJACENT')
        if (oid,before) not in index or (oid,after) not in index:
            findings.append(_finding('CRITICAL_PAIR_MISSING','UNVERIFIED',f'{oid}: {before}->{after} was not sampled'))
    screen = _result(findings)['status']
    findings.append(_finding('WORLD_STATE_NOT_MEASURED', 'UNVERIFIED',
                            'Screen visibility does not establish world birth, removal or persistence'))
    return _result(findings, screen_status=screen, world_status='UNVERIFIED', records=[dict(r) for r in records])


def qa_feedback_map(records):
    """Bind QA metadata, not a justified rewrite. prompt_eligible stays false.

    text_review_in_scope only selects consistent TEXT_ONLY records for review;
    neither caller mechanism text nor a review label approves an actual edit.
    """
    if not _rows(records):
        return _stop('FEEDBACK_RECORDS_INVALID')
    if not records:
        return _stop('FEEDBACK_REQUIRED', 'UNVERIFIED')
    findings, output = [], []
    for r in records:
        if (not all(_text(r.get(k)) for k in ('qa_id','ref','expected_mechanism')) or
                not all(_hash(r.get(k)) for k in ('historical_prompt_sha256','candidate_prompt_sha256','source_sha256')) or
                r.get('observed_status') not in ('FAIL','INCONCLUSIVE','PASS','UNVERIFIED') or
                r.get('constraint_status') not in ('PRESENT_BUT_OUTPUT_FAILED','PRESENT','MISSING','AMBIGUOUS','UNVERIFIED') or
                r.get('change_scope') not in ('TEXT_ONLY','CONTRACT_CHANGE','REFERENCE_CHANGE','PROVIDER_MODE_CHANGE') or
                r.get('constraint_present_in_source') is not None and type(r['constraint_present_in_source']) is not bool):
            return _stop('FEEDBACK_BINDING_INVALID')
        if r.get('pts_s') is not None and not _pts(r['pts_s']):
            return _stop('FEEDBACK_PTS_INVALID')
        status = 'PASS'
        if r.get('constraint_present_in_source') is True and r['constraint_status'] == 'MISSING':
            status = 'FAIL'
        elif r.get('constraint_present_in_source') is False and r['constraint_status'] in ('PRESENT','PRESENT_BUT_OUTPUT_FAILED'):
            status = 'FAIL'
        elif (r['constraint_status'] == 'PRESENT_BUT_OUTPUT_FAILED' and
              (r.get('constraint_present_in_source') is not True or r['observed_status'] != 'FAIL')):
            status = 'FAIL'
        elif r.get('pts_s') is None or r.get('constraint_present_in_source') is None:
            status = 'UNVERIFIED'
        elif r['observed_status'] in ('INCONCLUSIVE', 'UNVERIFIED'):
            status = 'UNVERIFIED'
        elif r['constraint_status'] in ('AMBIGUOUS', 'UNVERIFIED'):
            status = 'UNVERIFIED'
        if r['change_scope'] != 'TEXT_ONLY':
            findings.append(_finding('NON_TEXT_CHANGE_REQUIRES_DIRECTOR', 'HUMAN_REVIEW', r['qa_id']))
        findings.append(_finding('FEEDBACK_BINDING_ONLY', status, 'QA result preserved; proposal is not a measured improvement'))
        output.append(dict(r, binding_status=status,
                           text_review_in_scope=r['change_scope']=='TEXT_ONLY' and status=='PASS',
                           prompt_eligible=False, rewrite_status='HUMAN_REVIEW', director_approved=False))
    return _result(findings, records=output)


def review_prompt_edit(source=None, effective=None, *, expected_source_sha256=None,
                       expected_effective_sha256=None, required_clauses=(), aspect='9:16',
                       continuous_end=True, provenance=(), allow_newline_only=False):
    """Detect imported conflicts; always require human semantic/authority review.

    Fidelity PASS is a component result only. Provenance labels are never trusted
    as approval records by this helper; existing project validators own that gate.
    """
    if (not isinstance(source, bytes) or not isinstance(effective, bytes) or
            not _hash(expected_source_sha256) or not _hash(expected_effective_sha256) or
            not isinstance(required_clauses, (list,tuple)) or
            not all(_text(x) for x in required_clauses) or not _rows(provenance) or
            not _text(aspect) or type(continuous_end) is not bool):
        return _stop('PROMPT_REVIEW_INPUT_INVALID')
    try:
        old, new = source.decode('utf-8'), effective.decode('utf-8')
    except UnicodeDecodeError:
        return _stop('PROMPT_UTF8_REQUIRED')
    findings = []
    def contains(pattern):
        return bool(re.search(pattern,new,re.I))
    if continuous_end and contains(r'(?<!not )(?<!no )freeze (?:the )?(?:final|last)\s*1\s*second|(?:末|最后)\s*1\s*秒[^。\n]{0,60}(?:完全静止|画面定格)'):
        findings.append(_finding('UNAUTHORIZED_END_FREEZE','FAIL','Imported final freeze conflicts with continuous ending'))
    if aspect == '9:16' and contains(r'(?<!no )(?<!not )\blandscape\b|横屏'):
        findings.append(_finding('PORTRAIT_LANDSCAPE_CONFLICT','FAIL','Portrait contract gains landscape instruction'))
    for p in provenance:
        if p.get('kind') != 'APPROVED_FACT':
            findings.append(_finding('UNAPPROVED_FACT_CANNOT_BE_COMPILED','HUMAN_REVIEW','Design assumption or unknown fact authority'))
    fidelity = verify_prompt_fidelity(source,effective,
        expected_source_sha256=expected_source_sha256, expected_effective_sha256=expected_effective_sha256,
        required=tuple(required_clauses), allow_newline_only=allow_newline_only)
    findings.append(_finding('EXISTING_FIDELITY_CHECK',fidelity['status'],fidelity['reason']))
    findings.append(_finding('SEMANTIC_AND_AUTHORITY_REVIEW_REQUIRED', 'HUMAN_REVIEW',
                            'Byte identity or caller labels do not establish approved facts or semantic equivalence'))
    return _result(findings, fidelity=fidelity)

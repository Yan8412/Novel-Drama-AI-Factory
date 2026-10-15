"""Offline and conservative chronological prompt compiler candidate.

This generates *candidate text only* from pre-approved facts, never invents
an action, an object exit, new contact or a physics explanation.
"""
from dataclasses import dataclass
import hashlib
import re
from typing import Tuple


@dataclass(frozen=True)
class TimedBeat:
    start_ms: int
    end_ms: int
    explicit_action: str
    physical_evidence: str


@dataclass(frozen=True)
class FactProvenance:
    """References checked upstream, not self-authenticating approval evidence.

Design assumptions remain explicitly distinguishable in the sidecar plan.
The value digest prevents a cited fact from silently changing at this boundary.
"""
    field_path: str
    source_record_id: str
    source_sha256: str
    approval_record_id: str
    value_sha256: str
    kind: str = "APPROVED_FACT"  # or DESIGN_ASSUMPTION


@dataclass(frozen=True)
class TemporalPromptPlan:
    duration_ms: int
    initial_facts: str
    beats: Tuple[TimedBeat, ...]
    end_facts: str
    camera_constraints: str
    prop_continuity_rule: str
    provenance: Tuple[FactProvenance, ...] = ()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def plan_values(plan: TemporalPromptPlan):
    """Fields that require a bound source/decision before candidate compilation."""
    values = {name: getattr(plan, name) for name in
              ("initial_facts", "end_facts", "camera_constraints", "prop_continuity_rule")}
    values["duration_ms"] = str(plan.duration_ms)
    for index, beat in enumerate(plan.beats):
        for name in ("start_ms", "end_ms", "explicit_action", "physical_evidence"):
            values[f"beats[{index}].{name}"] = str(getattr(beat, name))
    return values


def _check_provenance(plan):
    values = plan_values(plan)
    records = {p.field_path: p for p in plan.provenance}
    if len(records) != len(plan.provenance) or set(records) != set(values):
        raise ValueError("EXACT_FIELD_PROVENANCE_REQUIRED")
    for name, value in values.items():
        record = records[name]
        if (not isinstance(record.source_record_id, str) or not record.source_record_id.strip() or
                not isinstance(record.approval_record_id, str) or not record.approval_record_id.strip() or
                not isinstance(record.source_sha256, str) or
                not re.fullmatch(r"[0-9a-fA-F]{64}", record.source_sha256) or
                not isinstance(record.value_sha256, str) or
                record.value_sha256.upper() != text_sha256(value) or
                record.kind not in ("APPROVED_FACT", "DESIGN_ASSUMPTION")):
            raise ValueError(f"INVALID_OR_UNBOUND_PROVENANCE_{name}")
        if name in ("initial_facts", "end_facts") and record.kind != "APPROVED_FACT":
            raise ValueError("FROZEN_ENDPOINT_FACTS_CANNOT_BE_ASSUMPTIONS")


def compile_candidate(plan: TemporalPromptPlan) -> str:
    """Fails before writing if timing or required physical facts are absent.

    Callers must verify each fact against real Canon before using this candidate.
    """
    if not plan.initial_facts.strip() or not plan.end_facts.strip():
        raise ValueError("START_END_FACTS_REQUIRED")
    if not plan.camera_constraints.strip() or not plan.prop_continuity_rule.strip():
        raise ValueError("CAMERA_AND_PROP_CONTRACT_REQUIRED")
    if type(plan.duration_ms) is not int or plan.duration_ms <= 0 or not plan.beats:
        raise ValueError("POSITIVE_DURATION_AND_PHASES_REQUIRED")
    expected_start = 0
    clauses = [f"Start (frozen reference facts): {plan.initial_facts.strip()}"]
    for index, beat in enumerate(plan.beats):
        if (type(beat.start_ms) is not int or type(beat.end_ms) is not int or
                beat.start_ms != expected_start or beat.end_ms <= beat.start_ms):
            raise ValueError(f"NONCONTIGUOUS_OR_INVALID_BEAT_{index}")
        if not beat.explicit_action.strip() or not beat.physical_evidence.strip():
            raise ValueError(f"ACTION_AND_OBSERVABLE_CAUSAL_EVIDENCE_REQUIRED_{index}")
        clauses.append(f"{beat.start_ms/1000:.3f}-{beat.end_ms/1000:.3f}s: "
                       f"{beat.explicit_action.strip()}; visible physical evidence: "
                       f"{beat.physical_evidence.strip()}.")
        expected_start = beat.end_ms
    if expected_start != plan.duration_ms:
        raise ValueError("TIMELINE_DOES_NOT_REACH_TARGET_DURATION")
    _check_provenance(plan)
    clauses.extend([
        f"Camera and world geometry: {plan.camera_constraints.strip()}",
        f"Object lifecycle: {plan.prop_continuity_rule.strip()}",
        f"End (frozen reference facts): {plan.end_facts.strip()}",
    ])
    return "\n".join(clauses)


def exact_clause_coverage(text: str, required: Tuple[str, ...]):
    """Simple offline test hook; literal checks are NOT semantic or video QA."""
    if (not required or any(not isinstance(x, str) or not x.strip() for x in required)
            or len(set(required)) != len(required)):
        return {"status": "BLOCKED", "found": (), "missing": (), "pass": False,
                "reason": "NONEMPTY_UNIQUE_REQUIRED_CLAUSES_NEEDED"}
    found = tuple(x for x in required if x in text)
    missing = tuple(x for x in required if x not in text)
    return {"status": "FAIL" if missing else "PASS", "found": found,
            "missing": missing, "pass": not missing}


def verify_prompt_fidelity(source: bytes, effective: bytes, *,
                           expected_source_sha256: str, expected_effective_sha256: str,
                           required: Tuple[str, ...], allow_newline_only=False):
    """Read-only boundary check for existing compiler and provider adapter outputs.

No text is rewritten. A PASS is byte/literal preservation only, never semantic
equivalence, Canon verification, provider obedience, or visual QA acceptance.
"""
    source_sha = hashlib.sha256(source).hexdigest().upper()
    effective_sha = hashlib.sha256(effective).hexdigest().upper()
    result = {"source_sha256": source_sha, "effective_sha256": effective_sha,
              "production_admitted": False}
    if type(allow_newline_only) is not bool:
        return dict(result, status="BLOCKED", reason="NEWLINE_POLICY_MUST_BE_EXPLICIT_BOOLEAN")
    if (not isinstance(expected_source_sha256, str) or
            not isinstance(expected_effective_sha256, str)):
        return dict(result, status="BLOCKED", reason="EXPECTED_HASHES_REQUIRED")
    if (source_sha != expected_source_sha256.upper() or
            effective_sha != expected_effective_sha256.upper()):
        return dict(result, status="FAIL", reason="INPUT_HASH_MISMATCH")
    try:
        source_text, effective_text = source.decode("utf-8"), effective.decode("utf-8")
    except UnicodeDecodeError:
        return dict(result, status="BLOCKED", reason="UTF8_REQUIRED")
    source_coverage = exact_clause_coverage(source_text, required)
    effective_coverage = exact_clause_coverage(effective_text, required)
    result.update(source_coverage=source_coverage, effective_coverage=effective_coverage)
    if source_coverage["status"] == "BLOCKED" or effective_coverage["status"] == "BLOCKED":
        return dict(result, status="BLOCKED", reason="REQUIRED_CLAUSES_UNVERIFIED")
    if not source_coverage["pass"] or not effective_coverage["pass"]:
        return dict(result, status="FAIL", reason="REQUIRED_CLAUSE_MISSING")
    if source == effective:
        return dict(result, status="PASS", reason="EXACT_BYTES_AND_LITERAL_CLAUSES_PRESERVED")
    normalize = lambda value: value.replace("\r\n", "\n").rstrip("\n")
    if allow_newline_only and normalize(source_text) == normalize(effective_text):
        return dict(result, status="PASS", reason="EXPLICITLY_ALLOWED_NEWLINE_ONLY_DIFFERENCE")
    return dict(result, status="HUMAN_REVIEW", reason="TEXT_CHANGE_REQUIRES_SEMANTIC_REVIEW")

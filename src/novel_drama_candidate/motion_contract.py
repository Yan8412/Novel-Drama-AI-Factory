"""Textual *pre-generation* motion checks; never upgrades observed video QA.

A state transition may be physically plausible and still fail visual comprehension;
this validator only exposes missing causal evidence in structured plans.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple


@dataclass(frozen=True)
class Finding:
    rule: str
    status: str  # FAIL / BLOCKED / UNVERIFIED / PASS
    explanation: str


@dataclass(frozen=True)
class Observation:
    at_ms: int
    object_id: str
    state: str  # EMERGING / ACTIVE / OCCLUDED / EXITED / UNSEEN
    cause: str = ""
    verified_evidence: bool = False


@dataclass(frozen=True)
class MotionPhase:
    begin_ms: int
    end_ms: int
    actor: str
    action: str
    assistance_required: Optional[bool] = None
    helper_contact_explicit: Optional[bool] = None
    helper_force_explicit: Optional[bool] = None
    support_before: str = ""
    support_after: str = ""
    support_transition_evidenced: Optional[bool] = None


@dataclass(frozen=True)
class PhaseCoverage:
    """Declared review interval, not an inferred video or whole-shot duration.

    Each expected actor must cover [begin_ms, end_ms) independently. For a
    whole-shot check the caller must supply 0 and the actual contract endpoint.
    """
    begin_ms: int
    end_ms: int
    expected_actors: Tuple[str, ...]


def _records(values):
    if isinstance(values, (str, bytes, Mapping)):
        return None
    try:
        return tuple(values)
    except Exception:
        # An incomplete iterator is not usable evidence; expose no exception data.
        return None


def check_object_lifecycle(observations: Iterable[Observation]) -> Tuple[Finding, ...]:
    observations = _records(observations)
    if observations is None:
        return (Finding("OBJECT_OBSERVATIONS_ITERABLE_REQUIRED", "BLOCKED",
                        "Invalid or incomplete observation iterable"),)
    by_object = {}
    for obs in observations:
        if not isinstance(obs, Observation):
            return (Finding("OBJECT_OBSERVATION_RECORD_REQUIRED", "BLOCKED",
                            "Invalid observation record"),)
        if not isinstance(obs.cause, str) or type(obs.verified_evidence) is not bool:
            return (Finding("OBJECT_EVIDENCE_FIELDS_VALID", "BLOCKED",
                            "Cause must be text and evidence must be an explicit boolean"),)
        if (type(obs.at_ms) is not int or obs.at_ms < 0 or
                not isinstance(obs.object_id, str) or not obs.object_id.strip() or
                not isinstance(obs.state, str) or
                obs.state not in {"EMERGING", "ACTIVE", "OCCLUDED", "EXITED", "UNSEEN"}):
            return (Finding("OBJECT_STATE_VALID", "FAIL", "Invalid object identity, time or state"),)
        by_object.setdefault(obs.object_id, []).append(obs)
    if not by_object:
        return (Finding("OBJECT_OBSERVATIONS_REQUIRED", "UNVERIFIED",
                        "No object observations were supplied"),)
    findings = []
    for oid, sequence in sorted(by_object.items()):
        sequence.sort(key=lambda x: x.at_ms)
        if len(sequence) < 2:
            findings.append(Finding("OBJECT_CONTINUITY_OBSERVATIONS_REQUIRED", "UNVERIFIED",
                                    f"{oid}: one observation cannot establish continuity"))
            continue
        if not any(obs.state in {"EMERGING", "ACTIVE"} for obs in sequence):
            findings.append(Finding("OBJECT_VISIBLE_OBSERVATION_REQUIRED", "UNVERIFIED",
                                    f"{oid}: no visible object state was supplied"))
        for previous, current in zip(sequence, sequence[1:]):
            if previous.at_ms == current.at_ms:
                findings.append(Finding("OBJECT_TIME_UNIQUE", "FAIL", f"{oid}: repeated time"))
            if previous.state in {"EMERGING", "ACTIVE"} and current.state in {"OCCLUDED", "EXITED", "UNSEEN"}:
                if current.state == "UNSEEN":
                    findings.append(Finding("OBJECT_UNEXPLAINED_VANISH", "FAIL",
                                            f"{oid}: {previous.at_ms}->{current.at_ms}ms without verified exit/occlusion"))
                elif (current.verified_evidence is not True or
                      not isinstance(current.cause, str) or not current.cause.strip()):
                    findings.append(Finding("OBJECT_EXIT_NEEDS_EVIDENCE", "UNVERIFIED",
                                            f"{oid}: {current.state} lacks verified cause"))
                else:
                    findings.append(Finding("OBJECT_EXIT_EXPLAINED", "PASS",
                                            f"{oid}: human-verified evidence recorded"))
            if (previous.state in {"EXITED", "OCCLUDED", "UNSEEN"} and
                    current.state in {"ACTIVE", "EMERGING"}):
                if (current.verified_evidence is not True or
                        not isinstance(current.cause, str) or not current.cause.strip()):
                    findings.append(Finding("OBJECT_RETURN_NEEDS_EVIDENCE", "UNVERIFIED",
                                            f"{oid}: re-entry/reveal lacks verified cause"))
                else:
                    findings.append(Finding("OBJECT_RETURN_EXPLAINED", "PASS",
                                            f"{oid}: verified re-entry/reveal recorded"))
    if not findings:
        findings.append(Finding("NO_UNEXPLAINED_TRANSITION_IN_OBSERVATIONS", "PASS",
                                "No known discontinuity; does not prove all objects were observed"))
    findings.append(Finding("OBJECT_SAMPLE_COVERAGE_UNVERIFIED", "UNVERIFIED",
                            "Discrete observations do not establish continuity between samples or full-shot coverage"))
    return tuple(findings)


def check_contact_phases(phases: Iterable[MotionPhase], *,
                         coverage: Optional[PhaseCoverage] = None) -> Tuple[Finding, ...]:
    phases = _records(phases)
    if phases is None:
        return (Finding("MOTION_PHASES_ITERABLE_REQUIRED", "BLOCKED",
                        "Invalid or incomplete phase iterable"),)
    if not phases:
        return (Finding("MOTION_PHASES_REQUIRED", "UNVERIFIED",
                        "No motion phases were supplied"),)
    findings = []
    by_actor = {}
    for phase in phases:
        if not isinstance(phase, MotionPhase):
            findings.append(Finding("MOTION_PHASE_RECORD_REQUIRED", "BLOCKED", "Invalid phase record"))
            continue
        label = phase.action if isinstance(phase.action, str) else "Unspecified action"
        if type(phase.begin_ms) is not int or type(phase.end_ms) is not int:
            findings.append(Finding("PHASE_TIME_TYPE_VALID", "BLOCKED", label))
        elif phase.begin_ms < 0 or phase.end_ms <= phase.begin_ms:
            findings.append(Finding("PHASE_INTERVAL_VALID", "FAIL", label))
        for name in ("actor", "action"):
            value = getattr(phase, name)
            if value is None or isinstance(value, str) and not value.strip():
                findings.append(Finding("PHASE_ACTOR_ACTION_REQUIRED", "UNVERIFIED", name))
            elif not isinstance(value, str):
                findings.append(Finding("PHASE_ACTOR_ACTION_TYPE_VALID", "BLOCKED", name))
        if phase.support_before is None or phase.support_after is None:
            findings.append(Finding("SUPPORT_STATES_REQUIRED", "UNVERIFIED", label))
        elif not isinstance(phase.support_before, str) or not isinstance(phase.support_after, str):
            findings.append(Finding("SUPPORT_STATE_TYPES_VALID", "BLOCKED", label))
        elif not phase.support_before.strip() or not phase.support_after.strip():
            findings.append(Finding("SUPPORT_STATES_REQUIRED", "UNVERIFIED", label))
        elif phase.support_before != phase.support_after:
            if phase.support_transition_evidenced is False:
                findings.append(Finding("LOAD_TRANSFER_CAUSALITY", "FAIL", label))
        for name in ("assistance_required", "helper_contact_explicit", "helper_force_explicit",
                     "support_transition_evidenced"):
            value = getattr(phase, name)
            if type(value) is not bool:
                status = "UNVERIFIED" if value is None else "BLOCKED"
                findings.append(Finding("PHASE_FLAGS_MUST_BE_EXPLICIT_BOOLEANS", status, name))
        if phase.assistance_required is True and (phase.helper_contact_explicit is False or
                                                 phase.helper_force_explicit is False):
            findings.append(Finding("HELPER_FORCE_CAUSALITY", "FAIL", label))
        if (type(phase.begin_ms) is int and type(phase.end_ms) is int and
                0 <= phase.begin_ms < phase.end_ms and
                isinstance(phase.actor, str) and phase.actor.strip()):
            by_actor.setdefault(phase.actor, []).append(phase)

    for actor, sequence in by_actor.items():
        # Preserve the supplied per-actor order. Sorting would hide bad plans.
        for previous, current in zip(sequence, sequence[1:]):
            if current.begin_ms < previous.begin_ms:
                findings.append(Finding("PHASE_INPUT_ORDER", "FAIL", actor))
            if current.begin_ms < previous.end_ms:
                findings.append(Finding("PHASE_OVERLAP", "FAIL", actor))
            elif current.begin_ms > previous.end_ms:
                findings.append(Finding("PHASE_GAP", "FAIL", actor))
            elif (isinstance(previous.support_after, str) and previous.support_after.strip() and
                  isinstance(current.support_before, str) and current.support_before.strip() and
                  previous.support_after != current.support_before):
                findings.append(Finding("PHASE_SUPPORT_BOUNDARY", "FAIL", actor))

    if coverage is None:
        findings.append(Finding("PHASE_COVERAGE_REQUIRED", "UNVERIFIED",
                                "Review interval and expected actors were not declared"))
    elif (not isinstance(coverage, PhaseCoverage) or
          type(coverage.begin_ms) is not int or type(coverage.end_ms) is not int or
          not 0 <= coverage.begin_ms < coverage.end_ms or
          not isinstance(coverage.expected_actors, tuple) or not coverage.expected_actors or
          any(not isinstance(actor, str) or not actor.strip() for actor in coverage.expected_actors) or
          len(set(coverage.expected_actors)) != len(coverage.expected_actors)):
        findings.append(Finding("PHASE_COVERAGE_VALID", "BLOCKED", "Invalid coverage declaration"))
    else:
        if coverage.begin_ms != 0:
            findings.append(Finding("PHASE_PARTIAL_SHOT_COVERAGE", "UNVERIFIED",
                                    f"Declared interval [{coverage.begin_ms}, {coverage.end_ms}) "
                                    "does not cover the shot from its beginning"))
        expected = set(coverage.expected_actors)
        for actor in sorted(expected - by_actor.keys()):
            findings.append(Finding("PHASE_EXPECTED_ACTOR_REQUIRED", "UNVERIFIED", actor))
        for actor in sorted(by_actor.keys() - expected):
            findings.append(Finding("PHASE_UNDECLARED_ACTOR", "FAIL", actor))
        for actor, sequence in by_actor.items():
            if (sequence[0].begin_ms != coverage.begin_ms or
                    sequence[-1].end_ms != coverage.end_ms or
                    any(phase.begin_ms < coverage.begin_ms or phase.end_ms > coverage.end_ms
                        for phase in sequence)):
                findings.append(Finding("PHASE_INTERVAL_COVERAGE", "FAIL", actor))
    if not findings:
        findings.append(Finding("MOTION_PHASE_STATIC_RULES", "PASS",
                                f"Static plan covers declared interval [{coverage.begin_ms}, {coverage.end_ms}) "
                                "for each expected actor; no real-video or wider interval claim"))
    return tuple(findings)

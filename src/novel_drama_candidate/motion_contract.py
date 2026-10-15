"""Textual *pre-generation* motion checks; never upgrades observed video QA.

A state transition may be physically plausible and still fail visual comprehension;
this validator only exposes missing causal evidence in structured plans.
"""
from dataclasses import dataclass
from typing import Iterable, Tuple


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
    assistance_required: bool = False
    helper_contact_explicit: bool = False
    helper_force_explicit: bool = False
    support_before: str = ""
    support_after: str = ""
    support_transition_evidenced: bool = False


def check_object_lifecycle(observations: Iterable[Observation]) -> Tuple[Finding, ...]:
    by_object = {}
    for obs in observations:
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
    return tuple(findings)


def check_contact_phases(phases: Iterable[MotionPhase]) -> Tuple[Finding, ...]:
    findings = []
    phase_count = 0
    for phase in phases:
        phase_count += 1
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
        flags_valid = True
        for name in ("assistance_required", "helper_contact_explicit", "helper_force_explicit",
                     "support_transition_evidenced"):
            value = getattr(phase, name)
            if type(value) is not bool:
                flags_valid = False
                status = "UNVERIFIED" if value is None else "BLOCKED"
                findings.append(Finding("PHASE_FLAGS_MUST_BE_EXPLICIT_BOOLEANS", status, name))
        if not flags_valid:
            continue
        if phase.assistance_required and not (phase.helper_contact_explicit and phase.helper_force_explicit):
            findings.append(Finding("HELPER_FORCE_CAUSALITY", "FAIL", label))
        if phase.support_before is None or phase.support_after is None:
            findings.append(Finding("SUPPORT_STATES_REQUIRED", "UNVERIFIED", label))
        elif not isinstance(phase.support_before, str) or not isinstance(phase.support_after, str):
            findings.append(Finding("SUPPORT_STATE_TYPES_VALID", "BLOCKED", label))
        elif not phase.support_before.strip() or not phase.support_after.strip():
            findings.append(Finding("SUPPORT_STATES_REQUIRED", "UNVERIFIED", label))
        elif phase.support_before != phase.support_after:
            if not phase.support_transition_evidenced:
                findings.append(Finding("LOAD_TRANSFER_CAUSALITY", "FAIL", label))
    if not phase_count:
        return (Finding("MOTION_PHASES_REQUIRED", "UNVERIFIED",
                        "No motion phases were supplied"),)
    if not findings:
        findings.append(Finding("MOTION_PHASE_STATIC_RULES", "PASS",
                                "No missing declared causal facts; real-world motion not guaranteed"))
    return tuple(findings)

"""Offline mode proposals; this module has no network or spending authority.

Evidence references must be supplied by the project's existing capability/cost
validators. A reference or a digest is NOT authentication: this module checks
consistency and freshness only. Synthetic inputs cannot prove provider support.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re
from typing import Optional, Tuple


class Mode(str, Enum):
    T2V = "text2video"
    I2V = "image2video"
    F2F = "frames2video"
    MULTI = "multi_keyframe"
    MOTION = "motion_reference"


def _aware(value):
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9A-Fa-f]{64}", value) is not None


def _amount(value):
    return isinstance(value, Decimal) and value.is_finite() and value >= 0


def _text(value):
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True)
class ModeEvidence:
    """Explicit fields copied from a validated provider/model capability result."""
    mode: Mode
    supports_start: bool = False
    supports_end: bool = False
    supports_intermediate: bool = False
    supports_motion_reference: bool = False


@dataclass(frozen=True)
class CostEvidence:
    mode: Mode
    quote: Decimal
    unit: str
    captured_at: datetime
    expires_at: datetime
    evidence_id: str
    shot_contract_sha256: str
    # Optional proven bound, not the quote and not a new spending authorization.
    cost_upper_bound: Optional[Decimal] = None


@dataclass(frozen=True)
class ProviderEvidence:
    provider: str
    model: str
    evidence_id: str
    captured_at: datetime
    expires_at: datetime
    modes: Tuple[ModeEvidence, ...]
    validation_record_id: str = ""
    validated_contract_sha256: str = ""
    costs: Tuple[CostEvidence, ...] = ()
    # Mapping copied from the same upstream-validated provider/model profile.
    # Required only by the read-only adapter bridge, not invented by the router.
    transport_provider: str = ""

    def __post_init__(self):
        if not all(_text(value) for value in (self.provider, self.model, self.evidence_id)):
            raise ValueError("Provenance identifier/provider/model required")
        if not _aware(self.captured_at) or not _aware(self.expires_at):
            raise ValueError("UTC-offset-aware evidence times required")
        if self.expires_at <= self.captured_at:
            raise ValueError("Invalid evidence TTL")
        if any(not isinstance(m, ModeEvidence) or not isinstance(m.mode, Mode) for m in self.modes):
            raise ValueError("Unknown mode evidence")
        if any(type(getattr(m, name)) is not bool for m in self.modes for name in
               ("supports_start", "supports_end", "supports_intermediate", "supports_motion_reference")):
            raise ValueError("Capability flags must be explicit booleans")
        if len({m.mode for m in self.modes}) != len(self.modes):
            raise ValueError("Duplicate mode evidence")
        if any(not isinstance(c, CostEvidence) or not isinstance(c.mode, Mode) for c in self.costs):
            raise ValueError("Unknown mode cost evidence")
        if len({c.mode for c in self.costs}) != len(self.costs):
            raise ValueError("Duplicate mode cost evidence")


@dataclass(frozen=True)
class ShotContract:
    shot_id: str
    provider: str
    model: str
    requires_start: bool = False
    requires_end: bool = False
    identity_lock: bool = False
    multi_actor_contact: bool = False
    load_transfer: bool = False
    critical_prop_lifecycle: bool = False
    intermediate_keyframes_verified: bool = False
    motion_reference_verified: bool = False
    frozen: bool = False
    already_submitted: bool = False
    character_count: Optional[int] = None
    canonical_input_id: str = ""
    canonical_input_sha256: str = ""
    approval_record_id: str = ""
    allowed_modes: Tuple[Mode, ...] = ()
    preferred_mode: Optional[Mode] = None
    max_cost: Optional[Decimal] = None
    billing_unit: str = ""
    duration_ms: Optional[int] = None
    resolution: str = ""
    aspect: str = ""
    native_audio: Optional[bool] = None
    output_count: Optional[int] = None
    intermediate_evidence_id: str = ""
    motion_evidence_id: str = ""
    start_reference_uri: str = ""
    start_reference_sha256: str = ""
    end_reference_uri: str = ""
    end_reference_sha256: str = ""


def shot_contract_digest(shot: ShotContract) -> str:
    """Stable candidate identity, NOT an Exact Request or execution fingerprint."""
    data = asdict(shot)
    if data["max_cost"] is not None:
        data["max_cost"] = str(data["max_cost"])
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()


@dataclass(frozen=True)
class RoutingDecision:
    status: str
    proposed_mode: Optional[Mode]
    reasons: Tuple[str, ...]

    @property
    def production_admitted(self):
        return False


def route_candidate(shot: ShotContract, evidence: Optional[ProviderEvidence],
                    now: Optional[datetime] = None) -> RoutingDecision:
    """Check supplied evidence; never dispatch, authenticate it, or approve spend."""
    def blocked(reason):
        return RoutingDecision("BLOCKED", None, (reason,))

    if not isinstance(shot, ShotContract):
        return blocked("SHOT_CONTRACT_REQUIRED")
    if any(type(getattr(shot, name)) is not bool for name in (
            "requires_start", "requires_end", "identity_lock", "multi_actor_contact", "load_transfer",
            "critical_prop_lifecycle", "intermediate_keyframes_verified", "motion_reference_verified",
            "frozen", "already_submitted")):
        return blocked("SHOT_FLAGS_MUST_BE_EXPLICIT_BOOLEANS")
    if shot.frozen or shot.already_submitted:
        return blocked("FROZEN_OR_SUBMITTED_DO_NOT_REROUTE")
    if not all(_text(value) for value in (shot.shot_id, shot.provider, shot.model)):
        return blocked("INVALID_SHOT_METADATA")
    if (not _text(shot.canonical_input_id) or not _sha(shot.canonical_input_sha256)
            or not _text(shot.approval_record_id)):
        return blocked("CANONICAL_PROVENANCE_REQUIRED")
    if type(shot.character_count) is not int or shot.character_count < 0:
        return blocked("CHARACTER_COUNT_UNVERIFIED")
    if (type(shot.duration_ms) is not int or shot.duration_ms <= 0 or
            type(shot.output_count) is not int or shot.output_count <= 0 or
            type(shot.native_audio) is not bool or not _text(shot.resolution) or not _text(shot.aspect)):
        return blocked("GENERATION_CONFIGURATION_INCOMPLETE")
    if (not shot.allowed_modes or any(not isinstance(m, Mode) for m in shot.allowed_modes)
            or len(set(shot.allowed_modes)) != len(shot.allowed_modes)
            or (shot.preferred_mode is not None and shot.preferred_mode not in shot.allowed_modes)):
        return blocked("ALLOWED_OR_PREFERRED_MODE_INVALID")
    if not _amount(shot.max_cost) or not _text(shot.billing_unit):
        return blocked("COST_LIMIT_OR_UNIT_UNVERIFIED")
    if shot.requires_end and not shot.requires_start:
        return blocked("END_REQUIRES_EXPLICIT_START_POLICY")
    for required, uri, reference_sha in (
            (shot.requires_start, shot.start_reference_uri, shot.start_reference_sha256),
            (shot.requires_end, shot.end_reference_uri, shot.end_reference_sha256)):
        if required and (not _text(uri) or not _sha(reference_sha)):
            return blocked("ENDPOINT_REFERENCE_IDENTITY_UNVERIFIED")
        if not required and (uri or reference_sha):
            return blocked("UNDECLARED_ENDPOINT_REFERENCE")
    if not isinstance(evidence, ProviderEvidence):
        return blocked("NO_PROVIDER_CAPABILITY_EVIDENCE")
    now = datetime.now(timezone.utc) if now is None else now
    if not _aware(now):
        raise ValueError("now must have a UTC offset")
    if (shot.provider != evidence.provider or shot.model != evidence.model or
            now < evidence.captured_at or now >= evidence.expires_at):
        return blocked("CAPABILITY_UNMATCHED_OR_EXPIRED")
    digest = shot_contract_digest(shot)
    if (not _text(evidence.validation_record_id) or not _sha(evidence.validated_contract_sha256) or
            evidence.validated_contract_sha256.upper() != digest):
        return blocked("UPSTREAM_VALIDATION_RECORD_OR_CONTRACT_BINDING_REQUIRED")
    known = {m.mode: m for m in evidence.modes}
    complex_motion = shot.multi_actor_contact or shot.load_transfer or shot.critical_prop_lifecycle

    def supported(mode):
        spec = known.get(mode)
        if spec is None or mode not in shot.allowed_modes:
            return False
        if shot.requires_start and spec.supports_start is not True:
            return False
        if shot.requires_end and spec.supports_end is not True:
            return False
        if mode == Mode.T2V:
            return not shot.requires_start and not shot.requires_end
        if mode == Mode.I2V:
            return shot.requires_start and not shot.requires_end and spec.supports_start is True
        if mode == Mode.F2F:
            return (shot.requires_start and shot.requires_end and
                    spec.supports_start is True and spec.supports_end is True)
        if mode == Mode.MULTI:
            return (spec.supports_intermediate is True and
                    shot.intermediate_keyframes_verified is True and _text(shot.intermediate_evidence_id))
        if mode == Mode.MOTION:
            return (spec.supports_motion_reference is True and
                    shot.motion_reference_verified is True and _text(shot.motion_evidence_id))
        return False

    if shot.preferred_mode is not None:
        order = (shot.preferred_mode,)
    elif complex_motion:
        order = (Mode.MULTI, Mode.MOTION, Mode.F2F, Mode.I2V, Mode.T2V)
    else:
        order = (Mode.F2F, Mode.I2V, Mode.T2V, Mode.MULTI, Mode.MOTION)
    selected = next((mode for mode in order if supported(mode)), None)
    if selected is None:
        return blocked("NO_ALLOWED_CAPABILITY_AND_ENDPOINT_MATCH_NO_FALLBACK")
    cost = next((item for item in evidence.costs if item.mode == selected), None)
    if (cost is None or not _text(cost.evidence_id) or not _aware(cost.captured_at) or
            not _aware(cost.expires_at) or cost.expires_at <= cost.captured_at or
            now < cost.captured_at or now >= cost.expires_at or
            not _sha(cost.shot_contract_sha256) or cost.shot_contract_sha256.upper() != digest or cost.unit != shot.billing_unit or
            not _amount(cost.quote)):
        return blocked("MODE_COST_MISSING_EXPIRED_OR_UNMATCHED")
    if cost.quote > shot.max_cost:
        return blocked("QUOTE_EXCEEDS_COST_LIMIT")
    if cost.cost_upper_bound is not None:
        if not _amount(cost.cost_upper_bound) or cost.cost_upper_bound < cost.quote:
            return blocked("INVALID_COST_UPPER_BOUND")
        if cost.cost_upper_bound > shot.max_cost:
            return blocked("COST_UPPER_BOUND_EXCEEDS_LIMIT")
    reasons = []
    if cost.cost_upper_bound is None:
        reasons.append("QUOTE_IS_NOT_SETTLEMENT_OR_PROVEN_COST_BOUND")
    if complex_motion:
        reasons.append("CONTROL_CAPABILITY_DOES_NOT_PROVE_CONTACT_OR_PROP_CAUSALITY")
    if shot.character_count > 1:
        reasons.append("MULTI_CHARACTER_CARDINALITY_AND_IDENTITY_REQUIRE_REVIEW")
    if shot.identity_lock and not shot.requires_start:
        reasons.append("UNANCHORED_IDENTITY_REQUIRES_REVIEW")
    if reasons:
        return RoutingDecision("HUMAN_REVIEW", selected, tuple(reasons))
    return RoutingDecision("CANDIDATE_ONLY", selected,
                           ("SUPPLIED_CAPABILITY_AND_COST_RECORDS_CONSISTENT_NOT_ADMISSION",))

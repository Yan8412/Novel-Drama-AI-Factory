"""Opt-in, read-only bridge for existing compiler and official adapter OUTPUTS.

Consumes the 1.5.1 compiler's prompt/trace/HEP/lint and the reviewed adapter's
outbound params shape. It never imports the production compiler/runtime, reads
credentials, creates requests, or changes a Recipe. Callers keep private inputs
local. Evidence authentication stays with the existing project validators.
"""
from collections.abc import Mapping
from datetime import datetime
from typing import Optional, Tuple

from .mode_router import Mode, ProviderEvidence, ShotContract, route_candidate
from .prompt_candidate import verify_prompt_fidelity


def review_compiled_candidate(*, compiled: Mapping, source: bytes, effective: bytes,
                              outbound: Mapping, shot: ShotContract,
                              capability: Optional[ProviderEvidence],
                              expected_source_sha256: str, expected_effective_sha256: str,
                              ordered_reference_uris: Tuple[str, ...],
                              required_clauses: Tuple[str, ...], now: datetime,
                              expected_transport_provider: Optional[str] = None,
                              allow_newline_only: bool = False):
    """Return preservation and route findings; no whole-request SHA is invented.

The adapter projection here supports its reviewed frames2video fields only.
Other router modes need a separately reviewed adapter mapping before this bridge
can assess their requests. Missing inputs are UNVERIFIED, not silently defaulted.
    """
    base = {"production_admitted": False, "exact_request_sha256": "NOT_COMPUTED",
            "execution_semantic_core": "NOT_COMPUTED", "generation_submissions": 0}

    def stop(status, reason, **details):
        return dict(base, status=status, reason=reason, **details)

    if not isinstance(compiled, Mapping) or not isinstance(outbound, Mapping):
        return stop("UNVERIFIED", "COMPILER_AND_OUTBOUND_RECORDS_REQUIRED")
    if not isinstance(expected_transport_provider, str) or not expected_transport_provider.strip():
        return stop("UNVERIFIED", "EXPLICIT_TRANSPORT_PROVIDER_MAPPING_REQUIRED")
    if not isinstance(capability, ProviderEvidence):
        return stop("BLOCKED", "UPSTREAM_VALIDATED_PROVIDER_PROFILE_REQUIRED")
    if (capability.provider != shot.provider or capability.model != shot.model or
            capability.transport_provider != expected_transport_provider):
        return stop("BLOCKED", "TRANSPORT_PROVIDER_MAPPING_NOT_BOUND_TO_CAPABILITY_PROFILE")
    if outbound.get("provider") != expected_transport_provider:
        return stop("FAIL", "OUTBOUND_TRANSPORT_PROVIDER_CHANGED")
    try:
        trace, hep, lint = compiled["trace"], compiled["hep"], compiled["lint"]
        prompt, params = compiled["prompt"], outbound["params"]
        duration = hep["video"]["duration_s"]
        version = trace["prompt_compiler_version"]
        compiler_prompt_sha = trace["prompt_sha256"]
    except (KeyError, TypeError):
        return stop("UNVERIFIED", "REQUIRED_COMPILER_OR_ADAPTER_FIELDS_MISSING")
    if version != "1.5.1":
        return stop("UNVERIFIED", "COMPILER_VERSION_NOT_REVIEWED")
    if not all(isinstance(value, Mapping) for value in (trace, hep, lint, params)):
        return stop("UNVERIFIED", "MALFORMED_COMPILER_OR_ADAPTER_RECORD")
    if (trace.get("generation_authorization") != "NONE" or trace.get("provider_calls") != 0
            or type(trace.get("provider_calls")) is not int
            or shot.frozen or shot.already_submitted):
        return stop("BLOCKED", "FROZEN_SUBMITTED_OR_NON_OFFLINE_INPUT")
    if lint.get("schema_status") != "PASS" or lint.get("runtime_errors") or lint.get("overall") == "FAIL":
        return stop("BLOCKED", "EXISTING_COMPILER_LINT_NOT_ACCEPTABLE")
    if (not isinstance(prompt, str) or not isinstance(compiler_prompt_sha, str) or
            prompt.encode("utf-8") != source or
            compiler_prompt_sha.upper() != expected_source_sha256.upper()):
        return stop("FAIL", "COMPILER_SOURCE_PROMPT_BINDING_CHANGED")
    if type(duration) not in (int, float) or duration * 1000 != shot.duration_ms:
        return stop("FAIL", "COMPILED_DURATION_DIFFERS_FROM_SHOT")
    if (not isinstance(params.get("prompt"), str) or
            params["prompt"].encode("utf-8") != effective):
        return stop("FAIL", "OUTBOUND_EFFECTIVE_PROMPT_BINDING_CHANGED")
    if params.get("modeType") != Mode.F2F.value:
        return stop("UNVERIFIED", "ADAPTER_MODE_MAPPING_NOT_REVIEWED")
    if shot.requires_start is not True or shot.requires_end is not True:
        return stop("FAIL", "FRAMES2VIDEO_ENDPOINT_CONTRACT_REQUIRED")
    if (len(ordered_reference_uris) != 2 or
            any(not isinstance(uri, str) or not uri for uri in ordered_reference_uris)):
        return stop("UNVERIFIED", "EXPLICIT_ORDERED_ENDPOINT_BINDINGS_REQUIRED")
    if ordered_reference_uris != (shot.start_reference_uri, shot.end_reference_uri):
        return stop("FAIL", "SIDECAR_ENDPOINT_IDENTITIES_DIFFER_FROM_REQUEST_EXPECTATIONS")
    expected = {"model": shot.model, "duration": duration, "resolution": shot.resolution,
                "ratio": shot.aspect, "enableSound": shot.native_audio, "count": shot.output_count,
                "imageList": list(ordered_reference_uris)}
    if not set(expected).issubset(params):
        return stop("UNVERIFIED", "REQUIRED_ADAPTER_PARAMETERS_MISSING")
    if (outbound.get("model") != shot.model or outbound.get("taskType") != "video" or
            any(params[key] != value for key, value in expected.items()) or
            type(params["enableSound"]) is not bool or type(params["count"]) is not int):
        return stop("FAIL", "OUTBOUND_PARAMETERS_OR_REFERENCE_ORDER_CHANGED")
    # Never swallow extra media into an assumed two-frame request.
    for key in ("videoList", "audioList", "mixedList", "videoListV2", "audioListV2", "textList"):
        if params.get(key) not in (None, []):
            return stop("UNVERIFIED", "ADDITIONAL_ADAPTER_MEDIA_REQUIRES_REVIEW")
    fidelity = verify_prompt_fidelity(source, effective,
        expected_source_sha256=expected_source_sha256, expected_effective_sha256=expected_effective_sha256,
        required=required_clauses, allow_newline_only=allow_newline_only)
    if fidelity["status"] != "PASS":
        return stop(fidelity["status"], "PROMPT_FIDELITY_REQUIRES_RESOLUTION", fidelity=fidelity)
    decision = route_candidate(shot, capability, now)
    status, reasons = decision.status, decision.reasons
    known_params = set(expected) | {"prompt", "modeType", "videoList", "audioList", "mixedList",
                                   "videoListV2", "audioListV2", "textList"}
    if status != "BLOCKED" and set(params) - known_params:
        status, reasons = "HUMAN_REVIEW", reasons + ("ADDITIONAL_PARAMETERS_REQUIRE_EXISTING_ADAPTER_VALIDATION",)
    if status != "BLOCKED" and decision.proposed_mode != Mode.F2F:
        status, reasons = "HUMAN_REVIEW", reasons + ("ALTERNATIVE_MODE_NEEDS_NEW_REVIEWED_REQUEST",)
    if status != "BLOCKED" and lint.get("overall") != "PASS":
        status, reasons = "HUMAN_REVIEW", reasons + ("COMPILER_SEMANTIC_REVIEW_STILL_REQUIRED",)
    return dict(base, status=status, fidelity=fidelity,
                proposed_mode=decision.proposed_mode.value if decision.proposed_mode else None,
                reasons=reasons, adapter_projection="REVIEWED_FIELDS_ONLY_NOT_EXECUTION_ADMISSION")

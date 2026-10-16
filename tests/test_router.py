"""Synthetic contracts only; no test fixture attests real provider support."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from novel_drama_candidate.mode_router import (
    CostEvidence, Mode, ModeEvidence, ProviderEvidence, ShotContract,
    route_candidate, shot_contract_digest)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
START = NOW - timedelta(seconds=10)
END = NOW + timedelta(minutes=5)


def shot(**kwargs):
    values = dict(shot_id="synthetic-shot", provider="synthetic-provider", model="synthetic-model",
                  character_count=1, canonical_input_id="synthetic-input", canonical_input_sha256="A" * 64,
                  approval_record_id="synthetic-decision", allowed_modes=tuple(Mode),
                  max_cost=Decimal("10"), billing_unit="synthetic-unit", duration_ms=4000,
                  resolution="720p", aspect="9:16", native_audio=False, output_count=1,
                  requires_start=False, requires_end=False, identity_lock=False,
                  multi_actor_contact=False, load_transfer=False, critical_prop_lifecycle=False,
                  intermediate_keyframes_verified=False, motion_reference_verified=False,
                  frozen=False, already_submitted=False)
    values.update(kwargs)
    if values.get("requires_start") is True:
        values.setdefault("start_reference_uri", "synthetic://start")
        values.setdefault("start_reference_sha256", "B" * 64)
    if values.get("requires_end") is True:
        values.setdefault("end_reference_uri", "synthetic://end")
        values.setdefault("end_reference_sha256", "C" * 64)
    return ShotContract(**values)


def evidence(contract, *modes):
    digest = shot_contract_digest(contract)
    costs = tuple(CostEvidence(mode.mode, Decimal("2"), "synthetic-unit", START, END,
                               "synthetic-cost", digest, Decimal("3")) for mode in modes)
    return ProviderEvidence(contract.provider, contract.model, "synthetic-schema", START, END,
                            modes, "synthetic-validation", digest, costs)


F2F = ModeEvidence(Mode.F2F, supports_start=True, supports_end=True)
I2V = ModeEvidence(Mode.I2V, supports_start=True)
T2V = ModeEvidence(Mode.T2V)
MULTI = ModeEvidence(Mode.MULTI, supports_start=True, supports_end=True, supports_intermediate=True)
MOTION = ModeEvidence(Mode.MOTION, supports_start=True, supports_end=True, supports_motion_reference=True)


class RouterTest(unittest.TestCase):
    def assertBlocked(self, contract, supplied, reason=None):
        result = route_candidate(contract, supplied, NOW)
        self.assertEqual(result.status, "BLOCKED")
        self.assertFalse(result.production_admitted)
        if reason:
            self.assertIn(reason, result.reasons)

    def test_missing_capability_blocked(self):
        self.assertBlocked(shot(), None)

    def test_omitted_shot_classifications_do_not_inherit_false(self):
        for field in ("requires_start", "requires_end", "identity_lock", "multi_actor_contact", "load_transfer",
                      "critical_prop_lifecycle", "intermediate_keyframes_verified", "motion_reference_verified",
                      "frozen", "already_submitted"):
            with self.subTest(field=field):
                values = vars(shot()).copy()
                del values[field]
                contract = ShotContract(**values)
                self.assertBlocked(contract, evidence(contract, T2V), "SHOT_FLAGS_MUST_BE_EXPLICIT_BOOLEANS")

    def test_explicit_false_classifications_remain_valid(self):
        contract = shot()
        self.assertEqual(route_candidate(contract, evidence(contract, T2V), NOW).status, "CANDIDATE_ONLY")

    def test_expired_or_future_capability_blocked(self):
        contract = shot()
        current = evidence(contract, T2V)
        for times in ((NOW - timedelta(hours=1), NOW), (END, END + timedelta(minutes=5))):
            with self.subTest(times=times):
                self.assertBlocked(contract, replace(current, captured_at=times[0], expires_at=times[1]))

    def test_frozen_and_submitted_cannot_reroute(self):
        for values in (dict(frozen=True), dict(already_submitted=True)):
            contract = shot(**values)
            self.assertBlocked(contract, evidence(contract, T2V))

    def test_all_three_basic_modes_are_candidates_with_matching_evidence(self):
        for contract, mode in ((shot(), T2V), (shot(requires_start=True), I2V),
                               (shot(requires_start=True, requires_end=True), F2F)):
            with self.subTest(mode=mode.mode):
                result = route_candidate(contract, evidence(contract, mode), NOW)
                self.assertEqual((result.status, result.proposed_mode), ("CANDIDATE_ONLY", mode.mode))
                self.assertFalse(result.production_admitted)

    def test_complex_f2f_requires_review(self):
        contract = shot(requires_start=True, requires_end=True, load_transfer=True)
        result = route_candidate(contract, evidence(contract, F2F), NOW)
        self.assertEqual((result.status, result.proposed_mode), ("HUMAN_REVIEW", Mode.F2F))

    def test_multi_control_needs_assets_and_explicit_schema_fields(self):
        contract = shot(requires_start=True, requires_end=True, load_transfer=True,
                        intermediate_keyframes_verified=True, intermediate_evidence_id="synthetic-anchors")
        result = route_candidate(contract, evidence(contract, MULTI), NOW)
        self.assertEqual((result.status, result.proposed_mode), ("HUMAN_REVIEW", Mode.MULTI))
        for bad in (replace(contract, intermediate_evidence_id=""),
                    replace(contract, intermediate_keyframes_verified=False)):
            self.assertBlocked(bad, evidence(bad, MULTI))
        self.assertBlocked(contract, evidence(contract, replace(MULTI, supports_end=False)))

    def test_motion_control_needs_assets_and_explicit_schema_fields(self):
        contract = shot(requires_start=True, requires_end=True, load_transfer=True,
                        motion_reference_verified=True, motion_evidence_id="synthetic-motion")
        result = route_candidate(contract, evidence(contract, MOTION), NOW)
        self.assertEqual((result.status, result.proposed_mode), ("HUMAN_REVIEW", Mode.MOTION))
        self.assertBlocked(contract, evidence(contract, replace(MOTION, supports_motion_reference=False)))
        bad = replace(contract, motion_evidence_id="")
        self.assertBlocked(bad, evidence(bad, MOTION))

    def test_advanced_mode_never_inferred_from_video_support(self):
        contract = shot(requires_start=True, requires_end=True, preferred_mode=Mode.MULTI,
                        intermediate_keyframes_verified=True, intermediate_evidence_id="synthetic-anchors")
        self.assertBlocked(contract, evidence(contract, F2F))

    def test_preferred_mode_does_not_silently_fallback(self):
        contract = shot(requires_start=True, requires_end=True, preferred_mode=Mode.F2F)
        self.assertBlocked(contract, evidence(contract, I2V))

    def test_allowed_mode_policy_is_enforced(self):
        contract = shot(allowed_modes=(Mode.I2V,))
        self.assertBlocked(contract, evidence(contract, T2V))
        for bad in (shot(allowed_modes=()), shot(allowed_modes=(Mode.T2V,), preferred_mode=Mode.I2V)):
            self.assertBlocked(bad, evidence(bad, T2V))

    def test_provider_and_model_are_exact(self):
        contract = shot()
        for values in (dict(provider="different"), dict(model="different")):
            self.assertBlocked(contract, replace(evidence(contract, T2V), **values))

    def test_upstream_validation_reference_required(self):
        contract = shot()
        self.assertBlocked(contract, replace(evidence(contract, T2V), validation_record_id=""))

    def test_changed_configuration_requires_new_evidence(self):
        contract = shot()
        for values in (dict(duration_ms=5000), dict(native_audio=True), dict(resolution="1080p"),
                       dict(aspect="16:9"), dict(output_count=2), dict(character_count=2)):
            with self.subTest(values=values):
                self.assertBlocked(replace(contract, **values), evidence(contract, T2V))

    def test_missing_provenance_is_not_approval(self):
        for values in (dict(canonical_input_id=""), dict(approval_record_id=""),
                       dict(canonical_input_sha256="not-a-hash")):
            contract = shot(**values)
            self.assertBlocked(contract, evidence(contract, T2V))

    def test_unknown_character_count_is_not_one(self):
        for count in (None, -1, True, 1.5):
            contract = shot(character_count=count)
            self.assertBlocked(contract, evidence(contract, T2V))

    def test_multi_character_risk_cannot_be_candidate_only(self):
        contract = shot(character_count=2, requires_start=True)
        result = route_candidate(contract, evidence(contract, I2V), NOW)
        self.assertEqual(result.status, "HUMAN_REVIEW")

    def test_unanchored_identity_requires_review(self):
        contract = shot(identity_lock=True)
        self.assertEqual(route_candidate(contract, evidence(contract, T2V), NOW).status, "HUMAN_REVIEW")

    def test_end_only_policy_blocked(self):
        contract = shot(requires_end=True)
        self.assertBlocked(contract, evidence(contract, F2F))

    def test_missing_actual_configuration_blocked(self):
        for values in (dict(duration_ms=None), dict(native_audio=None), dict(resolution=""),
                       dict(aspect=""), dict(output_count=0)):
            contract = shot(**values)
            self.assertBlocked(contract, evidence(contract, T2V))

    def test_unknown_budget_or_nonfinite_budget_blocked(self):
        for amount in (None, Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), 10):
            contract = shot(max_cost=amount)
            self.assertBlocked(contract, evidence(contract, T2V))

    def test_missing_cost_is_blocked(self):
        contract = shot()
        self.assertBlocked(contract, replace(evidence(contract, T2V), costs=()))

    def test_expired_or_wrong_cost_is_blocked(self):
        contract = shot()
        supplied = evidence(contract, T2V)
        for values in (dict(expires_at=NOW), dict(unit="different-unit"), dict(evidence_id=""),
                       dict(shot_contract_sha256="B" * 64), dict(quote=Decimal("NaN")),
                       dict(captured_at=END), dict(quote=Decimal("-1"))):
            with self.subTest(values=values):
                self.assertBlocked(contract, replace(supplied, costs=(replace(supplied.costs[0], **values),)))

    def test_over_budget_quote_and_upper_bound_blocked(self):
        contract = shot()
        supplied = evidence(contract, T2V)
        for values in (dict(quote=Decimal("11")), dict(cost_upper_bound=Decimal("11")),
                       dict(cost_upper_bound=Decimal("1"))):
            self.assertBlocked(contract, replace(supplied, costs=(replace(supplied.costs[0], **values),)))

    def test_zero_quote_is_not_free_or_spend_permission(self):
        contract = shot()
        supplied = evidence(contract, T2V)
        cost = replace(supplied.costs[0], quote=Decimal("0"), cost_upper_bound=None)
        result = route_candidate(contract, replace(supplied, costs=(cost,)), NOW)
        self.assertEqual(result.status, "HUMAN_REVIEW")
        self.assertFalse(result.production_admitted)

    def test_duplicate_mode_or_cost_evidence_rejected(self):
        supplied = evidence(shot(), T2V)
        with self.assertRaisesRegex(ValueError, "Duplicate mode evidence"):
            replace(supplied, modes=(T2V, T2V))
        with self.assertRaisesRegex(ValueError, "Duplicate mode cost"):
            replace(supplied, costs=supplied.costs * 2)

    def test_naive_times_rejected(self):
        supplied = evidence(shot(), T2V)
        with self.assertRaises(ValueError):
            replace(supplied, captured_at=NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            route_candidate(shot(), supplied, NOW.replace(tzinfo=None))

    def test_candidate_digest_is_deterministic_and_parameter_sensitive(self):
        contract = shot()
        self.assertEqual(shot_contract_digest(contract), shot_contract_digest(replace(contract)))
        self.assertNotEqual(shot_contract_digest(contract), shot_contract_digest(replace(contract, duration_ms=5000)))

    def test_unknown_shot_flags_are_never_false_by_default(self):
        for field in ("requires_start", "requires_end", "identity_lock", "multi_actor_contact", "load_transfer",
                      "critical_prop_lifecycle", "intermediate_keyframes_verified", "motion_reference_verified",
                      "frozen", "already_submitted"):
            for value in (None, "False", 0):
                with self.subTest(field=field, value=value):
                    contract = shot(**{field: value})
                    self.assertBlocked(contract, evidence(contract, T2V))

    def test_capability_flags_are_explicit_booleans(self):
        for value in (None, "true", 1):
            with self.assertRaisesRegex(ValueError, "explicit booleans"):
                evidence(shot(), replace(T2V, supports_start=value))

    def test_blank_provenance_and_missing_hashes_fail_closed(self):
        contract = shot()
        supplied = evidence(contract, T2V)
        for value in (None, " ", 1):
            self.assertBlocked(contract, replace(supplied, validated_contract_sha256=value))
            self.assertBlocked(contract, replace(supplied, validation_record_id=value))
            self.assertBlocked(contract, replace(supplied, costs=(replace(supplied.costs[0], shot_contract_sha256=value),)))
        for field in ("canonical_input_id", "approval_record_id"):
            bad = shot(**{field: " "})
            self.assertBlocked(bad, evidence(bad, T2V))

    def test_endpoint_identity_required_and_bound_into_digest(self):
        contract = shot(requires_start=True, requires_end=True)
        supplied = evidence(contract, F2F)
        self.assertBlocked(replace(contract, end_reference_sha256="D" * 64), supplied)
        for values in (dict(start_reference_uri=""), dict(end_reference_sha256=None)):
            bad = replace(contract, **values)
            self.assertBlocked(bad, evidence(bad, F2F))
        bad = shot(start_reference_uri="synthetic://undeclared", start_reference_sha256="B" * 64)
        self.assertBlocked(bad, evidence(bad, T2V))


if __name__ == "__main__":
    unittest.main()

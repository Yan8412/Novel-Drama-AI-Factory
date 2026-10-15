"""Existing compiler/adapter output SHAPES with entirely synthetic content."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import unittest

from novel_drama_candidate.integration import review_compiled_candidate
from novel_drama_candidate.mode_router import (
    CostEvidence, Mode, ModeEvidence, ProviderEvidence, ShotContract, shot_contract_digest)


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.source = b"A cone remains visible. Maintain hand contact.\n"
        self.effective = self.source[:-1]
        sha = lambda value: hashlib.sha256(value).hexdigest().upper()
        self.shot = ShotContract("synthetic-shot", "synthetic-provider", "synthetic-model",
            requires_start=True, requires_end=True, character_count=1,
            canonical_input_id="synthetic-canonical", canonical_input_sha256="A" * 64,
            approval_record_id="synthetic-approval", allowed_modes=(Mode.F2F,),
            preferred_mode=Mode.F2F, max_cost=Decimal("10"), billing_unit="synthetic-unit",
            duration_ms=4000, resolution="720p", aspect="9:16", native_audio=False, output_count=1,
            start_reference_uri="synthetic://start", start_reference_sha256="B" * 64,
            end_reference_uri="synthetic://destination", end_reference_sha256="C" * 64)
        digest = shot_contract_digest(self.shot)
        cost = CostEvidence(Mode.F2F, Decimal("1"), "synthetic-unit", self.now,
                            self.now + timedelta(minutes=5), "synthetic-cost", digest, Decimal("2"))
        capability = ProviderEvidence("synthetic-provider", "synthetic-model", "synthetic-capability",
            self.now, self.now + timedelta(minutes=5),
            (ModeEvidence(Mode.F2F, supports_start=True, supports_end=True),),
            "synthetic-upstream-validation", digest, (cost,), "synthetic-transport")
        self.compiled = {"prompt": self.source.decode(), "hep": {"video": {"duration_s": 4}},
            "lint": {"schema_status": "PASS", "runtime_errors": [], "overall": "PASS"},
            "trace": {"prompt_compiler_version": "1.5.1", "prompt_sha256": sha(self.source),
                      "generation_authorization": "NONE", "provider_calls": 0}}
        self.outbound = {"taskType": "video", "provider": "synthetic-transport", "model": "synthetic-model", "params": {
            "prompt": self.effective.decode(), "model": "synthetic-model", "modeType": "frames2video",
            "duration": 4, "resolution": "720p", "ratio": "9:16", "enableSound": False,
            "count": 1, "imageList": ["synthetic://start", "synthetic://destination"]}}
        self.kwargs = dict(compiled=self.compiled, source=self.source, effective=self.effective,
            outbound=self.outbound, shot=self.shot, capability=capability,
            expected_source_sha256=sha(self.source), expected_effective_sha256=sha(self.effective),
            ordered_reference_uris=("synthetic://start", "synthetic://destination"),
            required_clauses=("cone remains visible", "hand contact"), now=self.now,
            expected_transport_provider="synthetic-transport",
            allow_newline_only=True)

    def test_consumes_existing_outputs_without_rewriting_or_admitting(self):
        before = deepcopy((self.compiled, self.outbound))
        result = review_compiled_candidate(**self.kwargs)
        self.assertEqual(result["status"], "CANDIDATE_ONLY")
        self.assertEqual(result["fidelity"]["status"], "PASS")
        self.assertEqual(result["exact_request_sha256"], "NOT_COMPUTED")
        self.assertEqual(result["execution_semantic_core"], "NOT_COMPUTED")
        self.assertFalse(result["production_admitted"])
        self.assertEqual(before, (self.compiled, self.outbound))

    def test_missing_compiler_metadata_is_unverified(self):
        del self.compiled["trace"]["prompt_compiler_version"]
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "UNVERIFIED")

    def test_nonreviewed_compiler_version_not_inferred(self):
        self.compiled["trace"]["prompt_compiler_version"] = "unknown"
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "UNVERIFIED")

    def test_altered_source_or_adapter_prompt_fails(self):
        self.compiled["prompt"] += "different"
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "FAIL")
        self.compiled["prompt"] = self.source.decode()
        self.outbound["params"]["prompt"] += "different"
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "FAIL")

    def test_expired_capability_blocks(self):
        self.kwargs["now"] += timedelta(minutes=5)
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "BLOCKED")

    def test_incomplete_parameters_are_unverified(self):
        del self.outbound["params"]["enableSound"]
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "UNVERIFIED")

    def test_parameter_drift_fails(self):
        self.outbound["params"]["enableSound"] = True
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "FAIL")

    def test_reference_order_drift_fails(self):
        self.outbound["params"]["imageList"].reverse()
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "FAIL")

    def test_extra_media_not_discarded(self):
        self.outbound["params"]["videoList"] = ["synthetic://motion"]
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "UNVERIFIED")

    def test_new_router_mode_does_not_imply_adapter_mapping(self):
        self.outbound["params"]["modeType"] = "multi_keyframe"
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "UNVERIFIED")

    def test_historical_submission_cannot_be_rerouted(self):
        self.kwargs["shot"] = replace(self.shot, already_submitted=True)
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "BLOCKED")

    def test_missing_cost_does_not_inherit_compiler_pass(self):
        self.kwargs["capability"] = replace(self.kwargs["capability"], costs=())
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "BLOCKED")

    def test_compiler_semantic_unknown_is_not_promoted(self):
        self.compiled["lint"]["overall"] = "UNVERIFIED"
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "HUMAN_REVIEW")

    def test_failed_compiler_lint_blocks(self):
        self.compiled["lint"]["overall"] = "FAIL"
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "BLOCKED")

    def test_additional_request_fields_require_review(self):
        self.outbound["params"]["unknown_execution_setting"] = True
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "HUMAN_REVIEW")

    def test_sidecar_reference_change_does_not_inherit_old_evidence(self):
        self.kwargs["shot"] = replace(self.shot, end_reference_uri="synthetic://changed")
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "FAIL")

    def test_missing_provider_mapping_is_unverified(self):
        del self.kwargs["expected_transport_provider"]
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "UNVERIFIED")

    def test_provider_drift_fails(self):
        self.outbound["provider"] = "different-transport"
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "FAIL")

    def test_arbitrary_transport_mapping_cannot_replace_provider_profile(self):
        self.kwargs["expected_transport_provider"] = "different-transport"
        self.outbound["provider"] = "different-transport"
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "BLOCKED")
        self.kwargs["expected_transport_provider"] = "synthetic-transport"
        self.kwargs["capability"] = replace(self.kwargs["capability"], provider="different-provider")
        self.assertEqual(review_compiled_candidate(**self.kwargs)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()

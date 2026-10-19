"""Offline adapter contracts; synthetic bytes are not real video/Compiler proof.

The compiler-shaped receipts below exercise input validation only. Integration
with the installed Compiler must be evidenced separately by its actual output.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import socket
import subprocess
import unittest
from unittest.mock import patch
import urllib.request

from novel_drama_candidate.feedback_adapter import (
    Artifact, DEFAULT_ADAPTER_ENABLED, json_sha256, propose_revision,
    review_compilation, validate_candidate_input)


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def artifact(ref, content):
    if not isinstance(content, bytes):
        content = json_bytes(content)
    return Artifact(ref=ref, content=content, sha256=digest(content))


class FeedbackAdapterTest(unittest.TestCase):
    def setUp(self):
        self.baseline = {
            "intent": {
                "camera_note": "Locked camera.",
                "sound_note": "Ambient wind.",
                "negative_constraints": ["No cuts", "No dialogue", "No music"],
                "action_description": "One person remains beside a fixed marker.",
                "duration_s": 4,
                "asset_ids": ["synthetic-marker"],
            },
            "bindings": [],
            "preflight": {"generation_authorization": "NONE"},
        }
        self.baseline_sha256 = json_sha256(self.baseline)
        self.prompt = ("One person remains beside a fixed marker. "
                       "Locked camera. Ambient wind.")
        self.compiled = {
            "prompt": self.prompt,
            "hep": {"video": {"duration_s": 4}},
            "trace": {
                "prompt_compiler_version": "1.5.1",
                "intent_sha256": json_sha256(self.baseline["intent"]),
                "bindings_sha256": json_sha256(self.baseline["bindings"]),
                "hep_sha256": json_sha256({"video": {"duration_s": 4}}),
                "prompt_sha256": digest(self.prompt.encode()),
                "generation_authorization": "NONE",
                "provider_calls": 0,
            },
            "lint": {"schema_status": "PASS", "runtime_errors": [],
                     "overall": "UNVERIFIED",
                     "prompt_sha256": digest(self.prompt.encode())},
        }
        source = artifact("synthetic/source.bin", b"synthetic-source-not-a-video")
        self.observation = {"kind": "OBSERVED", "failure_type": "CAMERA_CONTINUITY",
                            "source_sha256": source.sha256, "pts_s": [1.0, 1.5]}
        self.pts = {"source_sha256": source.sha256, "duration_s": 4,
                    "pts_s": [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0]}
        observation = artifact("synthetic/observation.json", self.observation)
        pts = artifact("synthetic/pts.json", self.pts)
        self.artifacts = {a.ref: a for a in (source, observation, pts)}
        self.row = {
            "qa_id": "synthetic-camera",
            "historical_prompt_sha256": digest(self.prompt.encode()),
            "candidate_prompt_sha256": digest(self.prompt.encode()),
            "source_sha256": source.sha256,
            "pts_s": [1.0, 1.5],
            "ref": observation.ref,
            "observed_status": "FAIL",
            "constraint_status": "MISSING",
            "constraint_present_in_source": False,
            "change_scope": "TEXT_ONLY",
            "expected_mechanism": "No cuts",
            "failure_type": "CAMERA_CONTINUITY",
            "constraint_index": 0,
            "source_ref": source.ref,
            "pts_ref": pts.ref,
            "pts_sha256": pts.sha256,
        }
        self.report = {"schema_version": 1, "input_sha256": json_sha256(self.baseline),
                       "records": [self.row]}
        self.required = ("One person remains beside a fixed marker.",)

    def call(self, **overrides):
        kwargs = dict(baseline=self.baseline, compiled=self.compiled,
                      qa_report=artifact("synthetic/qa.json", self.report),
                      artifacts=self.artifacts, qa_id=self.row["qa_id"],
                      required_clauses=self.required, enabled=True)
        kwargs.update(overrides)
        result = propose_revision(**kwargs)
        # Caller retains this independent anchor before the proposal is mutable.
        self.proposal_sha256 = json_sha256(result)
        return result

    def replace_observation(self):
        self.artifacts[self.row["ref"]] = artifact(self.row["ref"], self.observation)

    def replace_pts(self):
        a = artifact(self.row["pts_ref"], self.pts)
        self.artifacts[a.ref] = a
        self.row["pts_sha256"] = a.sha256

    def assert_not_admitted(self, result):
        self.assertFalse(result["prompt_eligible"])
        self.assertFalse(result["production_admitted"])
        self.assertEqual(result["review_status"], "HUMAN_REVIEW")
        self.assertEqual(result["rewrite_status"], "HUMAN_REVIEW")
        self.assertEqual(result["generation_authorization"], "NONE")
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["paid_usage"], 0)
        self.assertEqual(result["authorization_consumptions"], 0)

    def assert_no_revision(self, result):
        self.assert_not_admitted(result)
        self.assertFalse(result.get("field_diffs", []))
        if result.get("candidate_input") is not None:
            self.assertEqual(result["candidate_input"], self.baseline)

    def test_disabled_by_default_requires_explicit_boolean_opt_in(self):
        self.assertIs(DEFAULT_ADAPTER_ENABLED, False)
        kwargs = dict(baseline=self.baseline, compiled=self.compiled,
                      qa_report=artifact("synthetic/qa.json", self.report),
                      artifacts=self.artifacts, qa_id=self.row["qa_id"],
                      required_clauses=self.required)
        self.assertEqual(propose_revision(**kwargs)["status"], "DISABLED")
        for value in (False, None, "true", 1):
            with self.subTest(enabled=value):
                self.assert_no_revision(self.call(enabled=value))

    def test_json_digest_is_canonical_utf8_sha256(self):
        value = {"b": [2, 1], "a": "synthetic-\u03bb"}
        self.assertEqual(json_sha256(value), digest(json_bytes(value)))
        self.assertEqual(json_sha256(value), json_sha256({"a": value["a"], "b": value["b"]}))

    def test_camera_proposal_changes_one_owned_text_field_only(self):
        result = self.call()
        self.assertEqual(result["status"], "REVISION_PROPOSED")
        self.assert_not_admitted(result)
        self.assertEqual(len(result["field_diffs"]), 1)
        diff = result["field_diffs"][0]
        self.assertEqual(diff["path"], "intent.camera_note")
        self.assertEqual(diff["before"], self.baseline["intent"]["camera_note"])
        self.assertEqual(diff["constraint_index"], 0)
        self.assertIn("no cuts", diff["after"])
        candidate = deepcopy(result["candidate_input"])
        self.assertEqual(candidate["intent"]["camera_note"], diff["after"])
        candidate["intent"]["camera_note"] = diff["before"]
        self.assertEqual(candidate, self.baseline)

    def test_audio_routes_to_sound_without_action_or_time_changes(self):
        for index, constraint in ((1, "No dialogue"), (2, "No music")):
            with self.subTest(constraint=constraint):
                self.row.update(failure_type="AUDIO_CONSTRAINT", constraint_index=index,
                                expected_mechanism=constraint)
                self.observation["failure_type"] = "AUDIO_CONSTRAINT"
                self.replace_observation()
                result = self.call()
                self.assert_not_admitted(result)
                self.assertEqual(len(result["field_diffs"]), 1)
                diff = result["field_diffs"][0]
                self.assertEqual(diff["path"], "intent.sound_note")
                self.assertIn(constraint.lower(), diff["after"])
                candidate = deepcopy(result["candidate_input"])
                candidate["intent"]["sound_note"] = self.baseline["intent"]["sound_note"]
                self.assertEqual(candidate, self.baseline)

    def test_inputs_and_original_qa_are_not_mutated(self):
        before = deepcopy((self.baseline, self.compiled, self.report, self.artifacts))
        self.call()
        self.assertEqual((self.baseline, self.compiled, self.report, self.artifacts), before)

    def test_existing_prompt_constraint_failed_video_does_not_duplicate_rule(self):
        self.compiled["prompt"] += " No cuts."
        sha = digest(self.compiled["prompt"].encode())
        self.compiled["trace"]["prompt_sha256"] = sha
        self.compiled["lint"]["prompt_sha256"] = sha
        self.row.update(historical_prompt_sha256=sha, candidate_prompt_sha256=sha,
                        constraint_present_in_source=True,
                        constraint_status="PRESENT_BUT_OUTPUT_FAILED")
        result = self.call()
        self.assertEqual(result["status"], "NO_PROMPT_CHANGE_JUSTIFIED")
        self.assert_no_revision(result)
        self.assertEqual(result["candidate_input_sha256"], result["baseline_input_sha256"])
        self.assertEqual(result["candidate_prompt_sha256"], sha)

    def test_stronger_physical_or_world_claims_never_become_text_edits(self):
        for failure in ("CONTACT_VS_LOAD", "GRIP_VS_FORCE", "PROP_SCREEN_CONTINUITY", "MOTION_TIMING"):
            with self.subTest(failure=failure):
                self.row["failure_type"] = failure
                self.observation["failure_type"] = failure
                self.replace_observation()
                result = self.call()
                self.assertEqual(result["status"], "NO_PROMPT_CHANGE_JUSTIFIED")
                self.assert_no_revision(result)

    def test_missing_or_nonobservational_evidence_never_creates_revision(self):
        for kind in ("INFERRED", "DESIGN_ASSUMPTION", "UNKNOWN"):
            with self.subTest(kind=kind):
                self.observation["kind"] = kind
                self.replace_observation()
                self.assert_no_revision(self.call())
        self.artifacts.pop(self.row["ref"])
        self.assert_no_revision(self.call())

    def test_inconclusive_pass_or_unverified_qa_does_not_justify_revision(self):
        for status in ("INCONCLUSIVE", "UNVERIFIED", "PASS"):
            with self.subTest(status=status):
                self.row["observed_status"] = status
                self.assert_no_revision(self.call())

    def test_nontext_changes_do_not_enter_proposal(self):
        for scope in ("CONTRACT_CHANGE", "REFERENCE_CHANGE", "PROVIDER_MODE_CHANGE"):
            with self.subTest(scope=scope):
                self.row["change_scope"] = scope
                self.assert_no_revision(self.call())

    def test_qa_byte_tampering_is_detected(self):
        a = artifact("synthetic/qa.json", self.report)
        self.assert_no_revision(self.call(qa_report=replace(a, content=a.content + b" ")))

    def test_each_evidence_artifact_byte_tampering_is_detected(self):
        for ref in tuple(self.artifacts):
            with self.subTest(ref=ref):
                changed = dict(self.artifacts)
                changed[ref] = replace(changed[ref], content=changed[ref].content + b" ")
                self.assert_no_revision(self.call(artifacts=changed))

    def test_source_identity_cannot_be_stitched_from_other_bytes(self):
        other = artifact(self.row["source_ref"], b"different synthetic source")
        changed = dict(self.artifacts)
        changed[other.ref] = other
        self.assert_no_revision(self.call(artifacts=changed))

    def test_observation_cannot_be_stitched_from_other_source_or_failure(self):
        for field, value in (("source_sha256", digest(b"other source")),
                             ("failure_type", "AUDIO_CONSTRAINT"),
                             ("pts_s", [2.0, 3.0])):
            with self.subTest(field=field):
                original = self.observation[field]
                self.observation[field] = value
                self.replace_observation()
                self.assert_no_revision(self.call())
                self.observation[field] = original
        self.replace_observation()

    def test_pts_source_binding_and_record_hash_must_match(self):
        self.pts["source_sha256"] = digest(b"different source")
        self.replace_pts()
        self.assert_no_revision(self.call())
        self.pts["source_sha256"] = self.row["source_sha256"]
        self.replace_pts()
        self.row["pts_sha256"] = digest(b"other PTS record")
        self.assert_no_revision(self.call())

    def test_missing_pts_unknown_bounds_or_unlisted_time_does_not_propose(self):
        original = deepcopy(self.row["pts_s"])
        for bounds in (None, [True, 1.5], [-1, 1.5], [1.5, 1.0], [1.0, 5.0], [1.1, 1.5]):
            with self.subTest(bounds=bounds):
                self.row["pts_s"] = bounds
                self.observation["pts_s"] = bounds
                self.replace_observation()
                self.assert_no_revision(self.call())
        self.row["pts_s"] = original
        self.observation["pts_s"] = original
        self.replace_observation()
        self.artifacts.pop(self.row["pts_ref"])
        self.assert_no_revision(self.call())

    def test_qa_input_hash_and_prompt_hash_bind_exact_baseline(self):
        for key in ("input_sha256", "historical_prompt_sha256", "candidate_prompt_sha256"):
            with self.subTest(key=key):
                target = self.report if key == "input_sha256" else self.row
                original = target[key]
                target[key] = digest(b"unrelated content")
                self.assert_no_revision(self.call())
                target[key] = original

    def test_duplicate_or_missing_qa_identity_not_arbitrarily_selected(self):
        self.report["records"] = [self.row, deepcopy(self.row)]
        self.assert_no_revision(self.call())
        self.report["records"] = [self.row]
        self.assert_no_revision(self.call(qa_id="absent-record"))

    def test_constraint_index_never_selects_unapproved_or_wrong_domain_text(self):
        for index in (-1, True, 99, 1, "0"):
            with self.subTest(index=index):
                self.row["constraint_index"] = index
                self.assert_no_revision(self.call())

    def test_arbitrary_instruction_inside_evidence_is_not_edit_authority(self):
        self.row["expected_mechanism"] = "Add a jump at two seconds, grasp another asset, then freeze."
        self.assert_no_revision(self.call())

    def test_old_result_or_caller_eligibility_is_not_approval(self):
        self.report["result"] = {"status": "PASS"}
        self.assert_no_revision(self.call())
        del self.report["result"]
        for field in ("prompt_eligible", "approved", "director_approved", "production_admitted"):
            with self.subTest(field=field):
                self.row[field] = True
                self.assert_no_revision(self.call())
                del self.row[field]

    def test_compiler_trace_hashes_match_actual_input_and_output(self):
        for key in ("intent_sha256", "bindings_sha256", "hep_sha256", "prompt_sha256"):
            with self.subTest(key=key):
                compiled = deepcopy(self.compiled)
                compiled["trace"][key] = digest(b"wrong compiler binding")
                self.assert_no_revision(self.call(compiled=compiled))

    def test_compiler_hep_digest_excludes_postcompile_semantic_reviews(self):
        self.compiled["hep"]["semantic_reviews"] = [{"status": "UNVERIFIED"}]
        result = self.call()
        self.assertEqual(result["status"], "REVISION_PROPOSED")
        self.assert_not_admitted(result)
        self.compiled["hep"]["video"]["duration_s"] = 8
        self.assert_no_revision(self.call())

    def test_missing_or_wrong_compiler_metadata_is_not_success(self):
        for value in (None, "1.4.0", "unknown"):
            with self.subTest(version=value):
                compiled = deepcopy(self.compiled)
                compiled["trace"]["prompt_compiler_version"] = value
                self.assert_no_revision(self.call(compiled=compiled))

    def test_provider_authorization_and_paid_calls_cannot_be_consumed(self):
        for field, value in (("generation_authorization", "APPROVED"),
                             ("provider_calls", 1), ("provider_calls", True)):
            with self.subTest(field=field, value=value):
                compiled = deepcopy(self.compiled)
                compiled["trace"][field] = value
                self.assert_no_revision(self.call(compiled=compiled))

    def test_failed_schema_runtime_or_lint_never_proposes(self):
        for field, value in (("schema_status", "FAIL"), ("runtime_errors", ["synthetic failure"]),
                             ("overall", "FAIL"), ("prompt_sha256", digest(b"unrelated"))):
            with self.subTest(field=field):
                compiled = deepcopy(self.compiled)
                compiled["lint"][field] = value
                self.assert_no_revision(self.call(compiled=compiled))

    def test_missing_required_fact_does_not_propose(self):
        self.assert_no_revision(self.call(required_clauses=("An absent approved fact.",)))

    def test_adapter_does_not_access_network_or_spawn_a_provider(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), \
                patch.object(urllib.request, "urlopen", side_effect=AssertionError("network forbidden")), \
                patch.object(subprocess, "Popen", side_effect=AssertionError("process forbidden")):
            self.assert_not_admitted(self.call())

    def synthetic_candidate_receipt(self, proposal):
        """Only a test double; this does not invoke or certify Compiler 1.5.1."""
        receipt = deepcopy(self.compiled)
        candidate = proposal["candidate_input"]
        receipt["prompt"] = (candidate["intent"]["action_description"] + " " +
                             candidate["intent"]["camera_note"] + " " +
                             candidate["intent"]["sound_note"])
        receipt["trace"]["intent_sha256"] = json_sha256(candidate["intent"])
        sha = digest(receipt["prompt"].encode())
        receipt["trace"]["prompt_sha256"] = sha
        receipt["lint"]["prompt_sha256"] = sha
        return receipt

    def review(self, proposal, candidate, effective=None):
        return review_compilation(proposal=proposal, baseline_compiled=self.compiled,
                                  candidate_compiled=candidate,
                                  expected_baseline_input_sha256=self.baseline_sha256,
                                  expected_proposal_sha256=self.proposal_sha256,
                                  effective_prompt=candidate["prompt"].encode() if effective is None else effective)

    def validate(self, proposal, *, expected_proposal_sha256=None):
        return validate_candidate_input(proposal,
            expected_baseline_input_sha256=self.baseline_sha256,
            expected_proposal_sha256=(self.proposal_sha256 if expected_proposal_sha256 is None
                                      else expected_proposal_sha256))

    def test_legitimate_text_revision_preserves_clauses_and_real_byte_hashes(self):
        proposal = self.call()
        self.assertTrue(self.validate(proposal))
        candidate = self.synthetic_candidate_receipt(proposal)
        result = self.review(proposal, candidate)
        self.assertEqual(result["status"], "HUMAN_REVIEW")
        self.assert_not_admitted(result)
        self.assertEqual(result["candidate_prompt"], candidate["prompt"])
        self.assertEqual(result["source_sha256"], digest(candidate["prompt"].encode()))
        self.assertEqual(result["effective_sha256"], digest(candidate["prompt"].encode()))
        self.assertIn(self.required[0], result["candidate_prompt"])
        self.assertIsNone(result["provider_effective_sha256"])
        self.assertEqual(result["visual_quality_improvement"], "NOT_TESTED")

    def test_hidden_action_time_asset_binding_or_preflight_changes_are_rejected(self):
        proposal = self.call()
        mutations = (
            ("intent", "action_description", "A person jumps."),
            ("intent", "duration_s", 8),
            ("intent", "asset_ids", ["different-asset"]),
            ("intent", "contact", "New grasp"),
            ("preflight", "generation_authorization", "APPROVED"),
        )
        for section, field, value in mutations:
            with self.subTest(section=section, field=field):
                changed = deepcopy(proposal)
                changed["candidate_input"][section][field] = value
                changed["candidate_input_sha256"] = json_sha256(changed["candidate_input"])
                with self.assertRaises(ValueError):
                    self.validate(changed, expected_proposal_sha256=json_sha256(changed))
        changed = deepcopy(proposal)
        changed["candidate_input"]["bindings"] = [{"asset_id": "new-asset"}]
        changed["candidate_input_sha256"] = json_sha256(changed["candidate_input"])
        with self.assertRaises(ValueError):
            self.validate(changed, expected_proposal_sha256=json_sha256(changed))

    def test_allowed_field_cannot_smuggle_additional_actions(self):
        proposal = self.call()
        proposal["candidate_input"]["intent"]["camera_note"] += "; the person jumps"
        proposal["field_diffs"][0]["after"] = proposal["candidate_input"]["intent"]["camera_note"]
        proposal["candidate_input_sha256"] = json_sha256(proposal["candidate_input"])
        with self.assertRaises(ValueError):
            self.validate(proposal, expected_proposal_sha256=json_sha256(proposal))

    def test_projection_label_cannot_smuggle_an_unapproved_action(self):
        proposal = self.call()
        proposal["projection_clause"] = "The person jumps"
        with self.assertRaisesRegex(ValueError, "PROJECTION_CLAUSE_CHANGED"):
            self.validate(proposal, expected_proposal_sha256=json_sha256(proposal))
        candidate = self.synthetic_candidate_receipt(proposal)
        candidate["prompt"] = candidate["prompt"].replace("no cuts", "The person jumps")
        sha = digest(candidate["prompt"].encode())
        candidate["trace"]["prompt_sha256"] = sha
        candidate["lint"]["prompt_sha256"] = sha
        self.assertEqual(self.review(proposal, candidate)["status"], "BLOCKED")

    def test_mutating_both_proposal_inputs_cannot_replace_external_baseline_anchor(self):
        proposal = self.call()
        for input_key, digest_key in (("baseline_input", "baseline_input_sha256"),
                                      ("candidate_input", "candidate_input_sha256")):
            proposal[input_key]["intent"]["action_description"] = "The person jumps."
            proposal[digest_key] = json_sha256(proposal[input_key])
        with self.assertRaises(ValueError):
            self.validate(proposal)
        # Even internally re-anchored proposals must obey the independent input.
        with self.assertRaises(ValueError):
            self.validate(proposal, expected_proposal_sha256=json_sha256(proposal))
        candidate = self.synthetic_candidate_receipt(proposal)
        self.assertEqual(self.review(proposal, candidate)["status"], "BLOCKED")

    def test_same_baseline_cannot_rebind_camera_evidence_to_audio(self):
        proposal = self.call()
        proposal["failure_type"] = "AUDIO_CONSTRAINT"
        proposal["projection_clause"] = "No dialogue"
        proposal["candidate_input"] = deepcopy(self.baseline)
        before = self.baseline["intent"]["sound_note"]
        after = "Ambient wind; no dialogue"
        proposal["candidate_input"]["intent"]["sound_note"] = after
        proposal["candidate_input_sha256"] = json_sha256(proposal["candidate_input"])
        proposal["field_diffs"] = [{"path": "intent.sound_note", "before": before,
                                    "after": after, "constraint_index": 1}]
        with self.assertRaisesRegex(ValueError, "PROPOSAL_EVIDENCE_OR_DIFF_CHANGED"):
            self.validate(proposal)
        candidate = self.synthetic_candidate_receipt(proposal)
        self.assertEqual(self.review(proposal, candidate)["status"], "BLOCKED")

    def test_required_clause_contract_cannot_be_removed_after_proposal(self):
        proposal = self.call()
        proposal["required_clauses"] = []
        with self.assertRaisesRegex(ValueError, "PROPOSAL_EVIDENCE_OR_DIFF_CHANGED"):
            self.validate(proposal)
        candidate = self.synthetic_candidate_receipt(proposal)
        self.assertEqual(self.review(proposal, candidate)["status"], "BLOCKED")

    def test_effective_prompt_mutation_or_required_fact_loss_blocks_handoff(self):
        proposal = self.call()
        candidate = self.synthetic_candidate_receipt(proposal)
        self.assertEqual(self.review(proposal, candidate, b"An unrelated delivery prompt.")["status"], "BLOCKED")
        candidate["prompt"] = candidate["prompt"].replace(self.required[0], "")
        sha = digest(candidate["prompt"].encode())
        candidate["trace"]["prompt_sha256"] = sha
        candidate["lint"]["prompt_sha256"] = sha
        self.assertEqual(self.review(proposal, candidate)["status"], "BLOCKED")

    def test_input_change_without_new_expression_is_not_success(self):
        proposal = self.call()
        candidate = deepcopy(self.compiled)
        candidate["trace"]["intent_sha256"] = json_sha256(proposal["candidate_input"]["intent"])
        self.assertEqual(self.review(proposal, candidate)["status"], "BLOCKED")

    def test_unsupported_s1_failure_keeps_prompt_and_input_hashes(self):
        self.row["failure_type"] = "PROP_SCREEN_CONTINUITY"
        self.observation["failure_type"] = self.row["failure_type"]
        self.replace_observation()
        proposal = self.call()
        self.assertEqual(proposal["status"], "NO_PROMPT_CHANGE_JUSTIFIED")
        self.assertTrue(self.validate(proposal))
        result = self.review(proposal, self.compiled)
        self.assertEqual(result["status"], "HUMAN_REVIEW")
        self.assertEqual(result["baseline_prompt_sha256"], result["candidate_prompt_sha256"])
        self.assertEqual(proposal["baseline_input_sha256"], proposal["candidate_input_sha256"])
        self.assert_not_admitted(result)


if __name__ == "__main__":
    unittest.main()

"""Synthetic native-QA files test trust boundaries, not real video quality.

The compiler-shaped receipt is a fixture, not a claim of invoking Compiler.
Only ffprobe is mocked: actual fixture bytes, paths, hashes, and the existing
feedback adapter are exercised. Private production records are never embedded.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

from novel_drama_candidate.feedback_adapter import json_sha256
from novel_drama_candidate.native_qa_bridge import export_native_qa


def digest(content):
    return hashlib.sha256(content).hexdigest()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


class NativeQABridgeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="native-qa-synthetic-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.paths = {role: self.root / (role + ".bin") for role in (
            "qa", "timeline", "source", "source_prompt", "effective_prompt",
            "delivery", "canonical", "compiled", "ffprobe")}
        self.source = b"SYNTHETIC_SOURCE_NOT_A_VIDEO"
        self.prompt = "One person stays beside a marker. Locked camera; no cuts.\n"
        self.rule = "no cuts"
        self.baseline = {
            "intent": {"camera_note": "Locked camera; no cuts.",
                       "sound_note": "Ambient wind.", "duration_s": 4,
                       "negative_constraints": ["No cuts"],
                       "action_description": "One person stays beside a marker."},
            "bindings": [], "preflight": {"generation_authorization": "NONE"},
        }
        self.canonical = {
            "shot_intent": {"data": deepcopy(self.baseline["intent"])},
            "reference_bindings": [],
        }
        hep = {"video": {"duration_s": 4}}
        self.compiled = {
            "prompt": self.prompt, "hep": hep,
            "preflight": deepcopy(self.baseline["preflight"]),
            "trace": {"prompt_compiler_version": "1.5.1",
                      "intent_sha256": json_sha256(self.baseline["intent"]),
                      "bindings_sha256": json_sha256(self.baseline["bindings"]),
                      "hep_sha256": json_sha256(hep),
                      "canonical_task_sha256": json_sha256(self.canonical),
                      "prompt_sha256": digest(self.prompt.encode()),
                      "generation_authorization": "NONE", "provider_calls": 0},
            "lint": {"schema_status": "PASS", "runtime_errors": [],
                     "overall": "UNVERIFIED",
                     "prompt_sha256": digest(self.prompt.encode())},
        }
        self.frames = []
        self.timestamps = [0.0, 1.0, 2.0, 4.0]
        native_frames = []
        for index, pts in enumerate(self.timestamps):
            path = self.root / ("frame-%02d.png" % index)
            content = ("SYNTHETIC_FRAME_BYTES_%d" % index).encode()
            path.write_bytes(content)
            self.frames.append({"frame": index, "path": str(path),
                                "sha256": digest(content)})
            native_frames.append({
                "zero_based_frame_index": index,
                "best_effort_timestamp_time": str(pts), "pts_time": str(pts),
                "extracted_file": str(path), "extracted_sha256": digest(content),
            })
        self.qa = {
            "schema_version": "S1FinalFrameBasedQAResultV1",
            "source": {"path": str(self.paths["source"]),
                       "sha256": digest(self.source)},
            "gates": [{"gate_id": "SYNTHETIC_CAMERA_GATE", "result": "FAIL",
                       "reason": "The synthetic observation records a visible cut.",
                       "unchanged_criterion": "No cuts",
                       "evidence": [
                           {"frame_index": i, "actual_pts_seconds": self.timestamps[i],
                            "file": self.frames[i]["path"]} for i in (1, 2)]}],
            "counts": {"FAIL": 1},
            "reviewer": "SYNTHETIC_REVIEWER_NOT_HUMAN_APPROVAL",
            "production_approval": "NOT_GRANTED_BY_THIS_REVIEW",
        }
        self.timeline = {
            "source_sha256": digest(self.source),
            "ffprobe_sha256": digest(b"SYNTHETIC_FFPROBE_NEVER_EXECUTED"),
            "source_probe": {"frames": native_frames, "format": {"duration": "4.0"}},
        }
        self.delivery = {
            "fingerprints": {"source_prompt_sha256": digest(self.prompt.encode()),
                             "effective_prompt_sha256": digest(self.prompt.encode())},
            "output": {"path": str(self.paths["source"]), "sha256": digest(self.source)},
            "qa_report": str(self.paths["qa"]),
        }
        self.manifest = {"files": {}, "frames": deepcopy(self.frames[1:3]),
                         "gate_id": "SYNTHETIC_CAMERA_GATE",
                         "failure_type": "CAMERA_CONTINUITY", "rule_clause": self.rule}
        for role, value in (
            ("source", self.source), ("source_prompt", self.prompt.encode()),
            ("effective_prompt", self.prompt.encode()),
            ("ffprobe", b"SYNTHETIC_FFPROBE_NEVER_EXECUTED"),
            ("qa", self.qa), ("timeline", self.timeline),
            ("delivery", self.delivery), ("canonical", self.canonical),
            ("compiled", self.compiled),
        ):
            self.write(role, value)
        self.probe_output = {
            "frames": [{"best_effort_timestamp_time": str(p)} for p in self.timestamps],
            "format": {"duration": "4.0"},
        }

    def write(self, role, value, *, pin=True):
        content = value if isinstance(value, bytes) else json_bytes(value)
        self.paths[role].write_bytes(content)
        if pin:
            self.manifest["files"][role] = {
                "path": str(self.paths[role]), "sha256": digest(content)}

    def call(self, **kwargs):
        result = subprocess.CompletedProcess(
            [str(self.paths["ffprobe"])], 0, stdout=json_bytes(self.probe_output), stderr=b"")
        with patch("novel_drama_candidate.native_qa_bridge.subprocess.run",
                   return_value=result) as run:
            outcome = export_native_qa(self.manifest, enabled=True, **kwargs)
        self.probe_calls = run.call_args_list
        return outcome

    def assert_safe(self, result):
        self.assertNotEqual(result.get("status"), "REVISION_PROPOSED")
        self.assertFalse(result.get("production_admitted", False))
        self.assertFalse(result.get("prompt_eligible", False))
        adapter = result.get("adapter_result") or {}
        self.assertFalse(adapter.get("production_admitted", False))
        self.assertFalse(adapter.get("prompt_eligible", False))
        self.assertFalse(adapter.get("field_diffs", []))
        self.assertEqual(adapter.get("provider_calls", 0), 0)
        self.assertEqual(adapter.get("authorization_consumptions", 0), 0)

    def assert_insufficient(self, result):
        self.assert_safe(result)
        self.assertEqual(result["decision_basis"], "INSUFFICIENT_EVIDENCE", result)

    def assert_integrity_blocked(self, result):
        self.assert_safe(result)
        self.assertEqual(result["status"], "BLOCKED_INTEGRITY_MISMATCH", result)

    def test_default_disabled_opens_no_files_or_processes(self):
        with patch("pathlib.Path.read_bytes", side_effect=AssertionError("unexpected read")), \
                patch("subprocess.run", side_effect=AssertionError("unexpected subprocess")):
            result = export_native_qa(self.manifest)
        self.assertEqual(result["status"], "DISABLED")
        self.assert_safe(result)

    def test_verified_native_failure_reaches_real_adapter_without_change(self):
        result = self.call()
        self.assertEqual(result["status"], "HUMAN_REVIEW", result)
        self.assertEqual(result["decision_basis"], "LITERAL_RULE_PRESENT_MAPPING_HUMAN_REVIEW")
        self.assertEqual(result["native_integrity"], "VERIFIED_BYTES_AND_REFERENCES")
        self.assert_safe(result)
        native = result["native_export"]["native_qa"]
        self.assertEqual(native["gate"], self.qa["gates"][0])
        self.assertEqual(native["counts"], self.qa["counts"])
        self.assertEqual(native["reviewer"], self.qa["reviewer"])
        self.assertEqual(native["approval"], self.qa["production_approval"])
        self.assertEqual(native["id"], digest(self.paths["qa"].read_bytes()) +
                         "#SYNTHETIC_CAMERA_GATE")
        self.assertEqual(result["native_export"]["video_sha256"], digest(self.source))
        for proof in result["native_export"]["frames"]:
            index = proof["frame"]
            self.assertEqual(proof["pts_s"], self.timestamps[index])
            self.assertEqual(proof["sha256"], self.frames[index]["sha256"])
        self.assertTrue(all(value == "UNVERIFIED" for value in
                            result["native_export"]["uncertainties"].values()))
        adapter = result["adapter_result"]
        self.assertEqual(adapter["status"], "NO_PROMPT_CHANGE_JUSTIFIED")
        self.assertEqual(adapter["baseline_input"], self.baseline)
        self.assertEqual(adapter["candidate_input"], self.baseline)
        self.assertEqual(adapter["baseline_input_sha256"], adapter["candidate_input_sha256"])
        self.assertEqual(adapter["baseline_prompt_sha256"], digest(self.prompt.encode()))
        self.assertEqual(adapter["candidate_prompt_sha256"], digest(self.prompt.encode()))

    def test_all_fixture_bytes_and_manifest_remain_unchanged(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        manifest = deepcopy(self.manifest)
        self.call()
        self.assertEqual(self.manifest, manifest)
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)

    def test_stale_manifest_pin_detects_changed_qa_bytes(self):
        self.write("qa", json_bytes(self.qa) + b" ", pin=False)
        self.assert_integrity_blocked(self.call())

    def test_input_changed_during_probe_cannot_return_verified_success(self):
        def mutate_during_probe(*args, **kwargs):
            self.paths["qa"].write_bytes(json_bytes(self.qa) + b" ")
            return subprocess.CompletedProcess(
                args[0], 0, stdout=json_bytes(self.probe_output), stderr=b"")

        with patch("novel_drama_candidate.native_qa_bridge.subprocess.run",
                   side_effect=mutate_during_probe):
            result = export_native_qa(self.manifest, enabled=True)
        self.assert_integrity_blocked(result)

    def test_cross_video_substitution_rejected_even_with_updated_manifest_pin(self):
        self.write("source", b"A_DIFFERENT_SYNTHETIC_SOURCE")
        self.assert_integrity_blocked(self.call())

    def test_source_reference_mismatch_not_fixed_by_same_hash(self):
        self.qa["source"]["path"] = str(self.root / "another-source.bin")
        self.write("qa", self.qa)
        self.assert_integrity_blocked(self.call())

    def test_frame_bytes_replacement_with_updated_manifest_pin_is_detected(self):
        changed = b"CHANGED_SYNTHETIC_FRAME"
        Path(self.manifest["frames"][1]["path"]).write_bytes(changed)
        self.manifest["frames"][1]["sha256"] = digest(changed)
        self.assert_integrity_blocked(self.call())

    def test_qa_frame_index_and_pts_must_describe_same_frame(self):
        self.qa["gates"][0]["evidence"][0]["actual_pts_seconds"] = 2.0
        self.write("qa", self.qa)
        self.assert_integrity_blocked(self.call())

    def test_probe_actual_pts_must_match_timeline_manifest(self):
        self.probe_output["frames"][1]["best_effort_timestamp_time"] = "1.125"
        self.assert_integrity_blocked(self.call())

    def test_duplicate_frame_indices_are_rejected(self):
        self.manifest["frames"].append(deepcopy(self.manifest["frames"][1]))
        self.assert_integrity_blocked(self.call())

    def test_duplicate_native_gate_ids_are_rejected(self):
        self.qa["gates"].append(deepcopy(self.qa["gates"][0]))
        self.qa["counts"]["FAIL"] = 2
        self.write("qa", self.qa)
        self.assert_integrity_blocked(self.call())

    def test_duplicate_json_key_rejected_even_with_current_file_pin(self):
        content = json_bytes(self.qa)
        content = b'{"schema_version":"ObservationRecordV1",' + content[1:]
        self.write("qa", content)
        self.assert_integrity_blocked(self.call())

    def test_count_totals_cannot_hide_a_changed_native_conclusion(self):
        self.qa["counts"] = {"PASS": 1, "FAIL": 0, "INCONCLUSIVE": 0}
        self.write("qa", self.qa)
        self.assert_integrity_blocked(self.call())

    def test_inconclusive_or_pass_qa_is_not_promoted_to_failure(self):
        for result in ("INCONCLUSIVE", "PASS", "UNVERIFIED"):
            with self.subTest(result=result):
                self.qa["gates"][0]["result"] = result
                self.qa["counts"] = {result: 1}
                self.write("qa", self.qa)
                outcome = self.call()
                self.assert_safe(outcome)
                self.assertNotEqual(outcome["decision_basis"], "LITERAL_RULE_PRESENT_MAPPING_HUMAN_REVIEW")
                self.assertEqual(json.loads(self.paths["qa"].read_bytes())["gates"][0]["result"], result)

    def test_observation_record_is_not_upgraded_to_formal_qa(self):
        self.qa["schema_version"] = "ObservationRecordV1"
        self.qa["kind"] = "OBSERVATION"
        self.write("qa", self.qa)
        self.assert_insufficient(self.call())

    def test_missing_evidence_is_distinct_from_verified_existing_rule(self):
        self.qa["gates"][0]["evidence"] = []
        self.write("qa", self.qa)
        self.assert_insufficient(self.call())

    def test_missing_file_is_insufficient_evidence(self):
        self.paths["qa"].unlink()
        self.assert_insufficient(self.call())

    def test_missing_required_source_field_is_insufficient(self):
        del self.qa["source"]["sha256"]
        self.write("qa", self.qa)
        self.assert_insufficient(self.call())

    def test_rule_absence_does_not_create_a_missing_constraint_repair(self):
        self.manifest["rule_clause"] = "No music"
        self.assert_insufficient(self.call())

    def test_unrelated_existing_sentence_never_proves_semantic_mapping_or_approval(self):
        self.manifest["rule_clause"] = "One person stays beside a marker."
        result = self.call()
        self.assertEqual(result["decision_basis"], "LITERAL_RULE_PRESENT_MAPPING_HUMAN_REVIEW", result)
        mapping = result["native_export"]["rule_mapping"]
        self.assertEqual(mapping["native_gate_id"], self.qa["gates"][0]["gate_id"])
        self.assertEqual(mapping["native_criterion"], self.qa["gates"][0]["unchanged_criterion"])
        self.assertEqual(mapping["selected_clause"], self.manifest["rule_clause"])
        self.assertEqual(mapping["provenance"], "CALLER_SELECTED_LITERAL_RULE_REQUIRES_HUMAN_REVIEW")
        self.assertEqual(mapping["semantic_alignment"], "UNVERIFIED")
        self.assertEqual(mapping["approval"], "NOT_GRANTED")
        self.assert_safe(result)

    def test_prop_continuity_gate_cannot_be_routed_as_camera_failure(self):
        gate_id = "SYNTHETIC_PROP_THREAT_CONTINUITY"
        self.qa["gates"][0]["gate_id"] = gate_id
        self.manifest["gate_id"] = gate_id
        self.write("qa", self.qa)
        self.assertEqual(self.manifest["failure_type"], "CAMERA_CONTINUITY")
        self.assert_integrity_blocked(self.call())

    def test_prompt_source_effective_extra_text_is_rejected(self):
        effective = self.prompt.encode() + b"An unapproved action."
        self.write("effective_prompt", effective)
        self.delivery["fingerprints"]["effective_prompt_sha256"] = digest(effective)
        self.write("delivery", self.delivery)
        self.assert_integrity_blocked(self.call())

    def test_recorded_single_terminal_newline_difference_is_preserved(self):
        effective = self.prompt.encode()[:-1]
        self.write("effective_prompt", effective)
        self.delivery["fingerprints"]["effective_prompt_sha256"] = digest(effective)
        self.write("delivery", self.delivery)
        result = self.call()
        self.assertEqual(result["decision_basis"], "LITERAL_RULE_PRESENT_MAPPING_HUMAN_REVIEW", result)
        self.assertEqual(result["adapter_result"]["candidate_prompt_sha256"], digest(self.prompt.encode()))
        self.assertEqual(self.paths["effective_prompt"].read_bytes(), effective)

    def test_canonical_input_cannot_be_changed_by_refreshing_manifest_pin(self):
        self.canonical["shot_intent"]["data"]["action_description"] = "A different action."
        self.write("canonical", self.canonical)
        self.assert_integrity_blocked(self.call())

    def test_caller_approval_is_not_an_accepted_manifest_override(self):
        self.manifest["approved"] = True
        result = self.call()
        self.assert_safe(result)
        self.assertNotEqual(result["decision_basis"], "LITERAL_RULE_PRESENT_MAPPING_HUMAN_REVIEW")

    def test_no_network_or_paid_provider_path_and_only_one_probe_process(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network denied")), \
                patch.object(urllib.request, "urlopen", side_effect=AssertionError("network denied")):
            result = self.call()
        self.assertEqual(result["decision_basis"], "LITERAL_RULE_PRESENT_MAPPING_HUMAN_REVIEW", result)
        self.assert_safe(result)
        self.assertEqual(len(self.probe_calls), 1)
        arguments, options = self.probe_calls[0]
        command = arguments[0]
        self.assertEqual(str(command[0]), str(self.paths["ffprobe"]))
        self.assertIn(str(self.paths["source"]), command)
        self.assertIn("-show_entries", command)
        self.assertEqual(command[command.index("-protocol_whitelist") + 1], "file")
        self.assertEqual(command[command.index("-f") + 1], "mov")
        self.assertFalse(options.get("shell", False))


if __name__ == "__main__":
    unittest.main()

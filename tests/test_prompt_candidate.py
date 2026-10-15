from dataclasses import replace
import hashlib
import unittest
from novel_drama_candidate.prompt_candidate import (
    FactProvenance, TemporalPromptPlan, TimedBeat, compile_candidate, exact_clause_coverage,
    plan_values, text_sha256, verify_prompt_fidelity)


def synthetic_plan(**kwargs):
    base = dict(duration_ms=4000, initial_facts="synthetic initial image facts",
                beats=(TimedBeat(0, 1500, "subject reacts", "gaze turns toward hazard"),
                       TimedBeat(1500, 4000, "subject rises", "support and hand contact are shown")),
                end_facts="synthetic destination image facts",
                camera_constraints="preserve frame geometry",
                prop_continuity_rule="do not vanish without verified exit or occlusion")
    base.update(kwargs)
    plan = TemporalPromptPlan(**base)
    records = tuple(FactProvenance(name, "synthetic-canonical-source", "C" * 64,
                                  "synthetic-approval", text_sha256(value))
                    for name, value in plan_values(plan).items())
    return replace(plan, provenance=records)


class PromptCompilerTest(unittest.TestCase):
    def test_chronological_prompt_contains_phases(self):
        content = compile_candidate(synthetic_plan())
        self.assertLess(content.find("0.000-1.500s"), content.find("1.500-4.000s"))
        self.assertIn("verified exit or occlusion", content)

    def test_does_not_invent_an_exit(self):
        content = compile_candidate(synthetic_plan())
        self.assertNotIn("the spikes retract", content)

    def test_gap_rejected(self):
        with self.assertRaisesRegex(ValueError, "NONCONTIGUOUS"):
            compile_candidate(synthetic_plan(beats=(TimedBeat(0, 1000, "act", "proof"),
                                                  TimedBeat(1200, 4000, "act", "proof"))))

    def test_duration_gap_rejected(self):
        with self.assertRaisesRegex(ValueError, "TIMELINE_DOES_NOT_REACH"):
            compile_candidate(synthetic_plan(beats=(TimedBeat(0, 3800, "act", "proof"),)))

    def test_empty_physical_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError, "CAUSAL_EVIDENCE"):
            compile_candidate(synthetic_plan(beats=(TimedBeat(0, 4000, "assist", ""),)))

    def test_missing_end_frame_rejected(self):
        with self.assertRaisesRegex(ValueError, "START_END_FACTS"):
            compile_candidate(synthetic_plan(end_facts=""))

    def test_exact_clauses_as_differential_rule_only(self):
        result = exact_clause_coverage("keep actor and props", ("actor", "props", "force"))
        self.assertEqual(result["missing"], ("force",))
        self.assertFalse(result["pass"])

    def test_empty_required_clauses_never_pass(self):
        for required in ((), ("",), (" ",), ("actor", "actor")):
            with self.subTest(required=required):
                result = exact_clause_coverage("actor", required)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(result["pass"])

    def test_existing_clause_is_not_added_twice(self):
        plan = synthetic_plan(prop_continuity_rule="The cone stays on the floor.")
        content = compile_candidate(plan)
        self.assertEqual(content.count("The cone stays on the floor."), 1)

    def test_missing_provenance_rejected(self):
        with self.assertRaisesRegex(ValueError, "PROVENANCE_REQUIRED"):
            compile_candidate(replace(synthetic_plan(), provenance=()))

    def test_changed_fact_invalidates_approval_binding(self):
        with self.assertRaisesRegex(ValueError, "UNBOUND_PROVENANCE"):
            compile_candidate(replace(synthetic_plan(), initial_facts="different initial fact"))

    def test_incomplete_or_unknown_provenance_rejected(self):
        plan = synthetic_plan()
        for records in (plan.provenance[:-1], plan.provenance + (plan.provenance[0],),
                        (replace(plan.provenance[0], field_path="unknown"),) + plan.provenance[1:]):
            with self.assertRaisesRegex(ValueError, "PROVENANCE_REQUIRED"):
                compile_candidate(replace(plan, provenance=records))

    def test_missing_approval_record_rejected(self):
        plan = synthetic_plan()
        records = (replace(plan.provenance[0], approval_record_id=""),) + plan.provenance[1:]
        with self.assertRaisesRegex(ValueError, "INVALID_OR_UNBOUND"):
            compile_candidate(replace(plan, provenance=records))

    def test_blank_provenance_is_not_approval(self):
        plan = synthetic_plan()
        for field in ("source_record_id", "approval_record_id"):
            records = (replace(plan.provenance[0], **{field: " "}),) + plan.provenance[1:]
            with self.assertRaisesRegex(ValueError, "INVALID_OR_UNBOUND"):
                compile_candidate(replace(plan, provenance=records))

    def test_endpoint_assumption_not_promoted_to_frozen_fact(self):
        plan = synthetic_plan()
        records = tuple(replace(p, kind="DESIGN_ASSUMPTION") if p.field_path == "end_facts" else p
                        for p in plan.provenance)
        with self.assertRaisesRegex(ValueError, "ENDPOINT_FACTS"):
            compile_candidate(replace(plan, provenance=records))

    def test_design_assumption_retained_in_plan_not_authenticated_by_compiler(self):
        plan = synthetic_plan()
        records = tuple(replace(p, kind="DESIGN_ASSUMPTION") if p.field_path == "camera_constraints" else p
                        for p in plan.provenance)
        plan = replace(plan, provenance=records)
        self.assertIn("preserve frame geometry", compile_candidate(plan))
        self.assertEqual(next(p.kind for p in plan.provenance if p.field_path == "camera_constraints"),
                         "DESIGN_ASSUMPTION")

    def test_noninteger_timing_is_not_silently_rounded(self):
        for values in (dict(duration_ms=True),
                       dict(beats=(TimedBeat(0, 4000.0, "act", "visible contact"),))):
            with self.assertRaises(ValueError):
                compile_candidate(synthetic_plan(**values))


class PromptFidelityTest(unittest.TestCase):
    def check(self, source, effective, **kwargs):
        fields = dict(expected_source_sha256=hashlib.sha256(source).hexdigest(),
                      expected_effective_sha256=hashlib.sha256(effective).hexdigest(),
                      required=("cone remains", "hand contact"))
        fields.update(kwargs)
        return verify_prompt_fidelity(source, effective, **fields)

    def test_exact_bytes_pass_literal_check_only(self):
        content = b"cone remains; hand contact"
        result = self.check(content, content)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["production_admitted"])

    def test_lf_and_trailing_newline_difference_preserved_and_explicit(self):
        source, effective = b"cone remains\nhand contact\n", b"cone remains\r\nhand contact"
        original = (source, effective)
        self.assertEqual(self.check(source, effective)["status"], "HUMAN_REVIEW")
        result = self.check(source, effective, allow_newline_only=True)
        self.assertEqual(result["status"], "PASS")
        self.assertNotEqual(result["source_sha256"], result["effective_sha256"])
        self.assertEqual((source, effective), original)

    def test_internal_whitespace_change_is_not_newline_only(self):
        result = self.check(b"cone remains; hand contact", b"cone remains;  hand contact", allow_newline_only=True)
        self.assertEqual(result["status"], "HUMAN_REVIEW")

    def test_deleted_constraint_fails(self):
        result = self.check(b"cone remains; hand contact", b"cone remains")
        self.assertEqual((result["status"], result["reason"]), ("FAIL", "REQUIRED_CLAUSE_MISSING"))

    def test_wrong_bytes_fail_before_clause_check(self):
        result = self.check(b"cone remains; hand contact", b"cone remains; hand contact",
                            expected_effective_sha256="0" * 64)
        self.assertEqual(result["reason"], "INPUT_HASH_MISMATCH")

    def test_empty_coverage_blocks_fidelity(self):
        self.assertEqual(self.check(b"anything", b"anything", required=())["status"], "BLOCKED")

    def test_non_utf8_blocked(self):
        self.assertEqual(self.check(b"\xff", b"\xff")["status"], "BLOCKED")

    def test_unicode_bytes_have_platform_independent_hashes(self):
        content = "cone remains; hand contact; 人物".encode("utf-8")
        self.assertEqual(self.check(content, content)["status"], "PASS")

    def test_string_false_cannot_enable_newline_policy(self):
        result = self.check(b"cone remains; hand contact\n", b"cone remains; hand contact", allow_newline_only="False")
        self.assertEqual(result["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()

import unittest
from dataclasses import replace
from novel_drama_candidate.motion_contract import (
    Observation, MotionPhase, check_object_lifecycle, check_contact_phases)


class MotionContractTest(unittest.TestCase):
    def test_synthetic_unexplained_absence(self):
        observations = [Observation(1000, "prop-a", "ACTIVE"),
                        Observation(1200, "prop-a", "UNSEEN")]
        self.assertTrue(any(x.status == "FAIL" for x in check_object_lifecycle(observations)))

    def test_unseen_state_not_laundered_by_evidence_flag(self):
        observations = [Observation(1000, "prop-a", "ACTIVE"),
                        Observation(1200, "prop-a", "UNSEEN", cause="claimed exit",
                                    verified_evidence=True)]
        self.assertTrue(any(x.status == "FAIL" for x in check_object_lifecycle(observations)))

    def test_hypothetical_occlusion_without_evidence_must_review(self):
        observations = [Observation(1000, "prop-a", "ACTIVE"),
                        Observation(1200, "prop-a", "OCCLUDED", cause="maybe camera" )]
        self.assertTrue(any(x.status == "UNVERIFIED" for x in check_object_lifecycle(observations)))

    def test_empty_observations_are_unverified(self):
        for observations in ([], iter(())):
            with self.subTest(observations=type(observations).__name__):
                findings = check_object_lifecycle(observations)
                self.assertEqual([(f.rule, f.status) for f in findings],
                                 [("OBJECT_OBSERVATIONS_REQUIRED", "UNVERIFIED")])

    def test_single_observation_cannot_prove_continuity(self):
        for state in ("ACTIVE", "UNSEEN", "EXITED"):
            with self.subTest(state=state):
                findings = check_object_lifecycle([Observation(1000, "prop-a", state)])
                self.assertEqual(findings[0].status, "UNVERIFIED")

    def test_absent_only_observations_are_unverified(self):
        for state in ("UNSEEN", "EXITED", "OCCLUDED"):
            with self.subTest(state=state):
                findings = check_object_lifecycle([Observation(1000, "prop-a", state),
                                                   Observation(1200, "prop-a", state)])
                self.assertEqual(findings[0].status, "UNVERIFIED")

    def test_reentry_or_reveal_needs_evidence(self):
        for state in ("EXITED", "OCCLUDED", "UNSEEN"):
            with self.subTest(state=state):
                findings = check_object_lifecycle([Observation(1000, "prop-a", state),
                                                   Observation(1200, "prop-a", "ACTIVE")])
                self.assertEqual(findings[0].status, "UNVERIFIED")

    def test_verified_reentry_is_a_static_explanation_only(self):
        findings = check_object_lifecycle([Observation(1000, "prop-a", "EXITED"),
            Observation(1200, "prop-a", "ACTIVE", "verified movement into the frame", True)])
        self.assertEqual([(f.rule, f.status) for f in findings],
                         [("OBJECT_RETURN_EXPLAINED", "PASS")])

    def test_invalid_object_time_fails_without_sorting_error(self):
        for at_ms in (-1, "1000", None, float("nan"), float("inf"), True):
            with self.subTest(at_ms=at_ms):
                findings = check_object_lifecycle([Observation(at_ms, "prop-a", "ACTIVE")])
                self.assertEqual(findings[0].status, "FAIL")

    def test_blank_object_id_fails(self):
        for oid in ("", " ", None):
            with self.subTest(oid=oid):
                findings = check_object_lifecycle([Observation(1000, oid, "ACTIVE")])
                self.assertEqual(findings[0].status, "FAIL")

    def test_empty_phases_are_unverified(self):
        for phases in ([], iter(())):
            with self.subTest(phases=type(phases).__name__):
                self.assertEqual(check_contact_phases(phases)[0].status, "UNVERIFIED")

    def test_missing_support_states_are_unverified(self):
        for before, after in (("", "wall"), ("wall", ""), ("", ""), (" ", "wall")):
            with self.subTest(before=before, after=after):
                findings = check_contact_phases([MotionPhase(0, 500, "A", "rise",
                    support_before=before, support_after=after)])
                self.assertEqual([(f.rule, f.status) for f in findings],
                                 [("SUPPORT_STATES_REQUIRED", "UNVERIFIED")])

    def test_unchanged_explicit_support_statically_passes(self):
        findings = check_contact_phases([MotionPhase(0, 500, "A", "hold",
            support_before="wall", support_after="wall")])
        self.assertEqual(findings[0].status, "PASS")

    def test_missing_support_does_not_hide_true_interval_failure(self):
        findings = check_contact_phases([MotionPhase(500, 100, "A", "rise")])
        self.assertIn("FAIL", [f.status for f in findings])
        self.assertIn("UNVERIFIED", [f.status for f in findings])

    def test_unknown_motion_flags_never_pass(self):
        base = MotionPhase(0, 1000, "actor", "move", support_before="ground", support_after="ground")
        for name in ("assistance_required", "helper_contact_explicit", "helper_force_explicit",
                     "support_transition_evidenced"):
            with self.subTest(flag=name):
                findings = check_contact_phases([replace(base, **{name: None})])
                self.assertIn("UNVERIFIED", [f.status for f in findings])
                self.assertNotIn("PASS", [f.status for f in findings])

    def test_truthy_strings_and_numeric_flags_are_blocked(self):
        base = MotionPhase(0, 1000, "actor", "move", support_before="ground", support_after="wall")
        for name in ("assistance_required", "helper_contact_explicit", "helper_force_explicit",
                     "support_transition_evidenced"):
            for value in ("False", "True", 0, 1):
                with self.subTest(flag=name, value=value):
                    findings = check_contact_phases([replace(base, **{name: value})])
                    self.assertIn("BLOCKED", [f.status for f in findings])
                    self.assertNotIn("PASS", [f.status for f in findings])

    def test_missing_support_values_are_unverified_without_exception(self):
        base = MotionPhase(0, 1000, "actor", "move", support_before="ground", support_after="ground")
        for name in ("support_before", "support_after"):
            findings = check_contact_phases([replace(base, **{name: None})])
            self.assertEqual(findings[0].status, "UNVERIFIED")

    def test_malformed_support_values_are_blocked(self):
        base = MotionPhase(0, 1000, "actor", "move", support_before="ground", support_after="ground")
        for name in ("support_before", "support_after"):
            for value in (1, [], False):
                with self.subTest(field=name, value=value):
                    findings = check_contact_phases([replace(base, **{name: value})])
                    self.assertEqual(findings[0].status, "BLOCKED")

    def test_invalid_phase_time_types_are_blocked_without_exception(self):
        base = MotionPhase(0, 1000, "actor", "move", support_before="ground", support_after="ground")
        for name in ("begin_ms", "end_ms"):
            for value in (None, "1000", True, float("nan"), 1000.0):
                with self.subTest(field=name, value=value):
                    findings = check_contact_phases([replace(base, **{name: value})])
                    self.assertIn("BLOCKED", [f.status for f in findings])

    def test_missing_actor_or_action_is_unverified(self):
        base = MotionPhase(0, 1000, "actor", "move", support_before="ground", support_after="ground")
        for name in ("actor", "action"):
            for value in (None, "", " "):
                with self.subTest(field=name, value=value):
                    findings = check_contact_phases([replace(base, **{name: value})])
                    self.assertIn("UNVERIFIED", [f.status for f in findings])

    def test_malformed_actor_or_action_is_blocked(self):
        base = MotionPhase(0, 1000, "actor", "move", support_before="ground", support_after="ground")
        for name in ("actor", "action"):
            for value in (1, False, []):
                with self.subTest(field=name, value=value):
                    findings = check_contact_phases([replace(base, **{name: value})])
                    self.assertIn("BLOCKED", [f.status for f in findings])

    def test_malformed_phase_record_is_blocked(self):
        for record in (None, {}, "phase"):
            with self.subTest(record=record):
                self.assertEqual(check_contact_phases([record])[0].status, "BLOCKED")

    def test_evidenced_exit_accepted_in_static_validator(self):
        observations = [Observation(1000, "prop-a", "ACTIVE"),
                        Observation(1200, "prop-a", "EXITED", cause="verified moves beyond right edge",
                                    verified_evidence=True)]
        self.assertTrue(any(x.status == "PASS" for x in check_object_lifecycle(observations)))

    def test_cannot_replace_lost_visual_qa(self):
        observations = [Observation(100, "prop", "ACTIVE"), Observation(200, "prop", "ACTIVE")]
        self.assertEqual(check_object_lifecycle(observations)[0].rule,
                         "NO_UNEXPLAINED_TRANSITION_IN_OBSERVATIONS")

    def test_assistance_without_visible_force_fails(self):
        findings = check_contact_phases([MotionPhase(0, 500, "A", "assisted ascent",
                                                     assistance_required=True, helper_contact_explicit=True)])
        self.assertTrue(any(x.rule == "HELPER_FORCE_CAUSALITY" for x in findings))

    def test_unproved_load_transfer_fails(self):
        findings = check_contact_phases([MotionPhase(0, 500, "A", "leave support",
                                                     support_before="basket", support_after="grip")])
        self.assertTrue(any(x.rule == "LOAD_TRANSFER_CAUSALITY" for x in findings))

    def test_causal_phase_statically_passes(self):
        findings = check_contact_phases([MotionPhase(0, 500, "A", "assisted lift",
                                                     assistance_required=True, helper_contact_explicit=True,
                                                     helper_force_explicit=True, support_before="basket",
                                                     support_after="grip", support_transition_evidenced=True)])
        self.assertEqual(findings[0].status, "PASS")

    def test_bad_time_fails(self):
        findings = check_contact_phases([MotionPhase(100, 100, "A", "invalid")])
        self.assertEqual(findings[0].status, "FAIL")


if __name__ == "__main__":
    unittest.main()

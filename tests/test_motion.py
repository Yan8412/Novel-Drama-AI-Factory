import unittest
from dataclasses import replace
import novel_drama_candidate.motion_contract as motion
from novel_drama_candidate.motion_contract import (
    Observation, MotionPhase, PhaseCoverage, check_object_lifecycle, check_contact_phases)


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
                         [("OBJECT_RETURN_EXPLAINED", "PASS"),
                          ("OBJECT_SAMPLE_COVERAGE_UNVERIFIED", "UNVERIFIED")])

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
                self.assertIn(("SUPPORT_STATES_REQUIRED", "UNVERIFIED"),
                              [(f.rule, f.status) for f in findings])

    def test_unchanged_explicit_support_statically_passes(self):
        findings = check_contact_phases([MotionPhase(0, 500, "A", "hold",
            assistance_required=False, helper_contact_explicit=False, helper_force_explicit=False,
            support_before="wall", support_after="wall", support_transition_evidenced=False)],
            coverage=PhaseCoverage(0, 500, ("A",)))
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
                                                     assistance_required=True, helper_contact_explicit=True,
                                                     helper_force_explicit=False)])
        self.assertTrue(any(x.rule == "HELPER_FORCE_CAUSALITY" for x in findings))

    def test_unproved_load_transfer_fails(self):
        findings = check_contact_phases([MotionPhase(0, 500, "A", "leave support",
                                                     support_before="basket", support_after="grip",
                                                     support_transition_evidenced=False)])
        self.assertTrue(any(x.rule == "LOAD_TRANSFER_CAUSALITY" for x in findings))

    def test_causal_phase_statically_passes(self):
        findings = check_contact_phases([MotionPhase(0, 500, "A", "assisted lift",
                                                     assistance_required=True, helper_contact_explicit=True,
                                                     helper_force_explicit=True, support_before="basket",
                                                     support_after="grip", support_transition_evidenced=True)],
                                        coverage=PhaseCoverage(0, 500, ("A",)))
        self.assertEqual(findings[0].status, "PASS")

    def test_bad_time_fails(self):
        findings = check_contact_phases([MotionPhase(100, 100, "A", "invalid")])
        self.assertEqual(findings[0].status, "FAIL")


class MotionReviewRegressionTest(unittest.TestCase):
    @staticmethod
    def phase(begin=0, end=1000, actor="actor-a", **changes):
        values = dict(assistance_required=False, helper_contact_explicit=False,
                      helper_force_explicit=False, support_before="ground",
                      support_after="ground", support_transition_evidenced=False)
        values.update(changes)
        return MotionPhase(begin, end, actor, "hold", **values)

    def coverage(self, begin=0, end=1000, actors=("actor-a",)):
        coverage_type = getattr(motion, "PhaseCoverage", None)
        self.assertIsNotNone(coverage_type, "Explicit coverage API is required")
        return coverage_type(begin, end, actors)

    def test_omitted_risk_and_evidence_flags_are_unknown(self):
        phase = MotionPhase(0, 1000, "actor-a", "hold", support_before="ground", support_after="ground")
        for field in ("assistance_required", "helper_contact_explicit", "helper_force_explicit",
                      "support_transition_evidenced"):
            self.assertIsNone(getattr(phase, field), field)
        self.assertIn("UNVERIFIED", [f.status for f in check_contact_phases([phase])])

    def test_explicit_phase_without_coverage_is_not_full_continuity_pass(self):
        findings = check_contact_phases([self.phase()])
        self.assertIn("UNVERIFIED", [f.status for f in findings])
        self.assertFalse(all(f.status == "PASS" for f in findings))

    def test_same_actor_out_of_order_is_not_silently_sorted(self):
        findings = check_contact_phases([self.phase(500, 1000), self.phase(0, 500)])
        self.assertIn("FAIL", [f.status for f in findings])

    def test_same_actor_gap_blocks(self):
        findings = check_contact_phases([self.phase(0, 400), self.phase(600, 1000)])
        self.assertIn("FAIL", [f.status for f in findings])

    def test_same_actor_overlap_blocks(self):
        findings = check_contact_phases([self.phase(0, 700), self.phase(500, 1000)])
        self.assertIn("FAIL", [f.status for f in findings])

    def test_adjacent_support_state_cannot_change_without_phase_transfer(self):
        findings = check_contact_phases([self.phase(0, 500), self.phase(500, 1000,
            support_before="platform", support_after="platform")])
        self.assertIn("FAIL", [f.status for f in findings])

    def test_declared_complete_single_actor_coverage_passes_static_rules(self):
        phases = [self.phase(0, 500), self.phase(500, 1000)]
        findings = check_contact_phases(phases, coverage=self.coverage())
        self.assertTrue(all(f.status == "PASS" for f in findings), findings)

    def test_different_actors_can_have_parallel_tracks(self):
        phases = [self.phase(0, 500), self.phase(0, 1000, "actor-b"), self.phase(500, 1000)]
        findings = check_contact_phases(phases, coverage=self.coverage(actors=("actor-a", "actor-b")))
        self.assertTrue(all(f.status == "PASS" for f in findings), findings)

    def test_other_actor_cannot_fill_a_tracks_gap(self):
        phases = [self.phase(0, 400), self.phase(0, 1000, "actor-b"), self.phase(600, 1000)]
        findings = check_contact_phases(phases, coverage=self.coverage(actors=("actor-a", "actor-b")))
        self.assertIn("FAIL", [f.status for f in findings])

    def test_declared_partial_interval_is_scoped_not_whole_shot(self):
        findings = check_contact_phases([self.phase(500, 1000)], coverage=self.coverage(500, 1000))
        self.assertIn("UNVERIFIED", [f.status for f in findings])
        self.assertFalse(all(f.status == "PASS" for f in findings))
        self.assertIn("[500, 1000)", findings[0].explanation)

    def test_missing_expected_actor_is_unverified(self):
        findings = check_contact_phases([self.phase()], coverage=self.coverage(actors=("actor-a", "actor-b")))
        self.assertIn("UNVERIFIED", [f.status for f in findings])

    def test_undeclared_actor_blocks(self):
        findings = check_contact_phases([self.phase(actor="actor-b")], coverage=self.coverage())
        self.assertIn("FAIL", [f.status for f in findings])

    def test_uncovered_prefix_or_suffix_fails(self):
        for phase in (self.phase(100, 1000), self.phase(0, 900)):
            with self.subTest(phase=phase):
                findings = check_contact_phases([phase], coverage=self.coverage())
                self.assertIn("FAIL", [f.status for f in findings])

    def test_phase_outside_declared_interval_fails(self):
        findings = check_contact_phases([self.phase(0, 1200)], coverage=self.coverage())
        self.assertIn("FAIL", [f.status for f in findings])

    def test_invalid_coverage_is_controlled(self):
        for coverage in ({}, object(), "coverage"):
            with self.subTest(coverage=coverage):
                findings = check_contact_phases([self.phase()], coverage=coverage)
                self.assertIn("BLOCKED", [f.status for f in findings])

    def test_invalid_coverage_fields_are_controlled(self):
        for values in ((False, 1000, ("actor-a",)), (0, 0, ("actor-a",)),
                       (0, 1000, ()), (0, 1000, ("actor-a", "actor-a")),
                       (0, 1000, (None,)), (0, 1000, "actor-a")):
            with self.subTest(values=values):
                findings = check_contact_phases([self.phase()], coverage=self.coverage(*values))
                self.assertIn("BLOCKED", [f.status for f in findings])

    def test_invalid_observation_records_are_controlled(self):
        for record in (None, {}, object(), "observation"):
            with self.subTest(record=type(record).__name__):
                findings = check_object_lifecycle([record])
                self.assertEqual(findings[0].status, "BLOCKED")

    def test_invalid_observation_container_is_controlled(self):
        for observations in (None, 42, "observations", {}):
            with self.subTest(container=type(observations).__name__):
                findings = check_object_lifecycle(observations)
                self.assertEqual(findings[0].status, "BLOCKED")

    def test_observation_iterator_failure_is_controlled(self):
        def broken():
            yield Observation(0, "prop-a", "ACTIVE")
            raise RuntimeError("synthetic iterator failure")
        self.assertEqual(check_object_lifecycle(broken())[0].status, "BLOCKED")

    def test_malformed_observation_evidence_fields_are_controlled(self):
        base = Observation(0, "prop-a", "ACTIVE")
        for field, value in (("cause", None), ("cause", {}),
                             ("verified_evidence", "False"), ("verified_evidence", 1)):
            with self.subTest(field=field, value=value):
                findings = check_object_lifecycle([replace(base, **{field: value})])
                self.assertEqual(findings[0].status, "BLOCKED")

    def test_invalid_phase_container_is_controlled(self):
        for phases in (None, 42, "phases", {}):
            with self.subTest(container=type(phases).__name__):
                self.assertEqual(check_contact_phases(phases)[0].status, "BLOCKED")

    def test_phase_iterator_failure_is_controlled(self):
        def broken():
            yield self.phase()
            raise RuntimeError("synthetic iterator failure")
        self.assertEqual(check_contact_phases(broken())[0].status, "BLOCKED")

    def test_active_samples_do_not_prove_the_interval_between_them(self):
        findings = check_object_lifecycle([Observation(0, "prop-a", "ACTIVE"),
                                           Observation(1000, "prop-a", "ACTIVE")])
        self.assertIn("UNVERIFIED", [f.status for f in findings])
        self.assertFalse(all(f.status == "PASS" for f in findings))

    def test_explained_exit_still_does_not_prove_whole_interval_coverage(self):
        findings = check_object_lifecycle([Observation(0, "prop-a", "ACTIVE"),
            Observation(1000, "prop-a", "EXITED", "verified exit path", True)])
        self.assertIn("PASS", [f.status for f in findings])
        self.assertIn("UNVERIFIED", [f.status for f in findings])


if __name__ == "__main__":
    unittest.main()

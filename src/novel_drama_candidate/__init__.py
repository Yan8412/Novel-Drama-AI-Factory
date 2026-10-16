"""Offline-only reference components for Novel-to-Drama AI Factory.

This package does not call LibTV, invoke HSA/JIT, or authorize generation.
"""
from .mode_router import (Mode, ModeEvidence, CostEvidence, ProviderEvidence, ShotContract,
                          RoutingDecision, route_candidate, shot_contract_digest)
from .motion_contract import (Observation, MotionPhase, PhaseCoverage, Finding, check_object_lifecycle,
                              check_contact_phases)

__all__ = ["Mode", "ModeEvidence", "CostEvidence", "ProviderEvidence", "ShotContract", "RoutingDecision",
           "shot_contract_digest",
           "route_candidate", "Observation", "MotionPhase", "PhaseCoverage", "Finding",
           "check_object_lifecycle", "check_contact_phases"]

---
name: novel-drama-prompt-optimizer-candidate
description: Audit or prepare offline prompt and mode candidates for an explicitly requested Novel-to-Drama experiment, preserving the accepted compiler and domain-intent ownership.
metadata:
  version: "0.2.0-candidate"
---

# Prompt Optimizer Candidate

This is an isolated review overlay, not a replacement for an installed production Skill. It is not installed by this repository and cannot activate a runtime, change a frozen prompt, or grant execution permission.

Use the existing optimizer's authority order and current task scope. A historical failed output remains evidence; it is not permission to retry or redefine the story. Keep approved facts, design hypotheses, and observed output separate.

For the requested revision:

1. Compare the actual source/effective prompt and relevant approved inputs before proposing new wording. Classify each issue as `PRESENT`, `MISSING`, `CONTRADICTORY`, `AMBIGUOUS`, `PRESENT_BUT_OUTPUT_FAILED`, or `UNVERIFIED`. Do not label an explicit instruction missing merely because an output failed to show it.
2. Delegate only the needed domain intent: cinematic for timing/camera, performance for acting/reaction, spatial for reference roles and geometry. Preserve the installed `DIRECTOR_INTENT`, `PERFORMANCE_INTENT`, and `SPATIAL_INTENT` schemas; candidate annotations belong in a separate review record.
3. Change the smallest implicated part. If a rule is already explicit, investigate conflicting inputs, observation limits, or unsupported controls rather than duplicating it. An ambiguous instruction warrants a proposed clarification, not an invented contradiction.
4. Hand the proposal through the accepted `HUMANIZED_EXECUTION_PLAN -> GenerationRecipe + ProviderProfile -> Compiler 1.5.1` boundary where that installation is available. This package does not implement or replace that integration.

For a mode comparison or candidate compile, read [offline handoff](references/offline-handoff.md). Ordinary text review does not require routing all modes or loading every director.

Return the minimal proposed delta, its evidence category, deterministic check results, and remaining uncertainty. Keep hashes, QA IDs, provenance and authorization outside creative provider prose. A candidate compile or lint PASS does not establish video quality, physical feasibility, provider support, or permission to generate.

For a review using actual output failures, read [feedback and cleanup](references/feedback-cleanup.md). Keep evidence binding and candidate deltas separate from production admission.

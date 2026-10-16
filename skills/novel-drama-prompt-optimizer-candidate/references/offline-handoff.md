# Offline handoff

The executable interfaces are in [mode_router.py](../../../src/novel_drama_candidate/mode_router.py), [motion_contract.py](../../../src/novel_drama_candidate/motion_contract.py), and [prompt_candidate.py](../../../src/novel_drama_candidate/prompt_candidate.py). Read the current dataclasses before building inputs; do not invent fields or use a stale example.

## Mode comparison

Use `route_candidate(ShotContract, ProviderEvidence, now)` with the exact provider/model, allowed modes, reference requirements, and current verified upstream evidence. Evidence references identify an external validation result; a boolean or source string in this package cannot authenticate a provider claim.

Check each proposed mode's required reference roles and its own cost evidence. Generic video support is not evidence for intermediate keyframes or motion references. A price for one mode does not price another. Unknown, expired, mismatched, or over-budget evidence must retain the router's blocking/review outcome; do not fill gaps from remembered prices.

`CANDIDATE_ONLY`, `HUMAN_REVIEW`, and `BLOCKED` are planning results. Complex contact, support transfer, and critical prop continuity still require review when a richer mode is supported. Never treat `production_admitted` as true or transform a route suggestion into dispatch.

## Candidate text and fidelity

Map approved timing to `TimedBeat` / `TemporalPromptPlan`. Supply the required field-level provenance for initial facts, actions, physical evidence, ending facts, camera and prop continuity. Provenance records must point to the actual accepted source and approval; the compiler checks supplied structure, not whether those external assertions are true.

Keep a proposed physical mechanism distinct from observed evidence. If the installed compiler cannot represent it, retain a proposal and report that mapping gap; do not bypass the accepted compiler with this emitter's text.

Use `compile_candidate` for offline comparison, `verify_prompt_fidelity` for source/effective byte and clause checks, and `exact_clause_coverage` only for literal coverage. An empty coverage set is not a passing contract. Preserve each original byte stream; a reviewed newline-only difference is not permission to normalize or replace a frozen file. Literal retention does not prove semantic equivalence.

## Existing compiler boundary

Compiler 1.5.1 already compiles typed contact facts over the accepted 1.5 structured model. Permissions are not proof that optional contacts occur. Static reference inheritance does not establish motion or support. Reuse these distinctions; candidate motion checks are supplementary completeness checks, not a second physics authority.

When the installation, approved inputs, or existing schema is unavailable, stop at an offline candidate handoff and name the missing integration input. Do not claim a production compiler run occurred.

For a read-only comparison with an already compiled result, use `integration.review_compiled_candidate` with its explicit source/effective bytes, prospective request, expected hashes and review evidence. It consumes existing data only; do not import production modules, rerun a frozen compilation, or claim its route decision is a production gate.

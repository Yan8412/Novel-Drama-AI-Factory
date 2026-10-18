# Offline feedback candidate

This isolated extension of the existing candidate adds `qa_feedback.py`. It is
not an installed production Skill, provider adapter, compiler replacement or QA
authority. The original router, motion checks, prompt compiler candidate and
production-output bridge remain byte-identical to the reviewed baseline.

The new pure functions accept already-reviewed evidence with hashes, reference
locators and actual presentation timestamps. A supplied evidence declaration is
not self-authenticating: callers must check the source and observation upstream.
They provide supplementary findings without changing an original QA verdict.

| Output | Existing owner | Narrow increment |
|---|---|---|
| Motion load matrix | Cinematic Director / storyboard | Count active events separately from maintained support; uncalibrated thresholds only WARN |
| Force causal chain | Character Performance / structured contact contract | Keep force, contact, response and load transfer as distinct evidence requirements |
| Screen/world prop ledger | Asset Spatial / asset ledger | Bind each instance and screen transition; screen absence does not prove world disappearance |
| Cross-frame assertions | Existing shot QA | Require actual critical adjacent pairs; sparse samples cannot close a known boundary gap |
| QA feedback map | Prompt Optimizer / compiler handoff | Preserve present-but-failed requirements and route non-text changes to review |

Missing evidence remains UNVERIFIED; malformed input is BLOCKED. A negative
continuity finding records an unexplained supplied transition, not a unique
three-dimensional or model-internal cause. No function measures forces, observes
new frames, makes an HTTP request, generates a Prompt autonomously or grants
production permission.

The four Skill overlays remain separate from formal discovery roots. They link
to focused references for these sidecars. Proposed metadata stays outside the
accepted DIRECTOR_INTENT / PERFORMANCE_INTENT / SPATIAL_INTENT schemas. Stable
facial texture and identity details are preserved.

Run local standard-library regression tests with `PYTHONPATH=src` and
`python -B -m unittest discover -s tests -v`, then
`python -B tools/guard_staging.py .`. The guard's only extension is eight exact
file allowlist entries; link, replacement, containment and secret checks remain.
No dependency installation, hosted Actions or external model is needed.

## Causal evidence contract (PR #2 review 5564556151)

A chain declares `actor` (force initiator), `recipient` (responding actor),
`interaction_id`, `contact_id`, `support_before_id` and `support_after_id`.
IDs must come from the upstream-reviewed observations, not be filled into missing
records merely to make this check pass. Each observed part must bind the same
`interaction_id` and source-video hash. Required per-part fields are:

| Part | Bindings to the chain |
|---|---|
| force_source / contact | actor = actor; recipient = recipient; contact_id = contact_id |
| body_response | actor = recipient; contact_id = contact_id |
| support_before | actor = recipient; support_id = support_before_id |
| support_after | actor = recipient; support_id = support_after_id |
| transfer | actor = recipient; from_support_id = support_before_id; to_support_id = support_after_id |

Missing, null, UNKNOWN or UNVERIFIED identity links remain UNVERIFIED; malformed
IDs are BLOCKED; explicit role/contact/support contradictions FAIL. Distinct
interactions may run concurrently. Self-assistance and a change of support object
are not rejected merely for those properties. No field is a self-authenticating
attestation: callers still verify identities, source integrity and observations.

For each force/contact interval compared to the response, a cause wholly after
the response FAILS. Overlapping, containing, identical or touching windows remain
UNVERIFIED, including simultaneous point events. Only strictly separated
cause-before-response windows establish interval precedence here. This does not
require force before contact; an established grip may precede effort. Existing
support-transfer checks remain in place. A scoped PASS proves consistency of the
supplied records, not actual causation, transferred weight or whole-shot quality.

## Feedback field meanings

`binding_status` records metadata consistency. `text_review_in_scope` means only
that a consistent TEXT_ONLY feedback record can enter further text review. It
does not establish that a rewrite exists, is useful or is approved. The legacy
`prompt_eligible` field is retained as a conservative compatibility field and is
always false: this function does not assess an actual edit. `rewrite_status`
remains HUMAN_REVIEW and `director_approved` remains false. Caller-supplied
mechanism text, gap labels or review flags cannot change these results.

A PRESENT_BUT_OUTPUT_FAILED record may therefore have binding_status PASS and
text_review_in_scope true while prompt_eligible is false. Its original QA stays
unchanged. A proposed rewrite still needs separate source/effective fidelity,
semantic and authority review; no new execution path is provided here.

## Validation scope

The isolated candidate was tested on Windows 11 build 26200, AMD64:

| Interpreter | Total | PASS | SKIP | FAIL / ERROR |
|---|---:|---:|---:|---:|
| Python 3.13.15 | 206 | 204 | 2 | 0 / 0 |
| Python 3.14.7 | 206 | 204 | 2 | 0 / 0 |

Both skips were real file/directory symlink creation denied by the host; the
Windows junction check passed. These are prior private-candidate results, not
new-commit CI results. The publication migration preserves implementation behavior (Git-enforced LF
normalization only), generalizes private-shot documentation and replaces measurement-like
fixture values with unrelated synthetic values. Only the 49 affected feedback
tests and publication checks are rerun; the full suite is not rerun.

Python 3.10 syntax checks are not runtime tests. Python 3.10 and macOS runtime
remain UNVERIFIED for this extension. Historical hosted CI covers only its named
earlier commit. No workflow is dispatched by this publication.

Only generic code, synthetic tests and reviewed technical guidance are published.
Real media, production prompts, raw logs, billing and execution evidence remain
outside this tree. Public review does not install Skills or approve production.

### Review-fix validation

Review baseline: `f35e8988e232bc92dbc26a8bce03501fe35a7229`. Added 26 focused tests
before changing implementation. Against that baseline, 21 new test methods fail
(56 assertions including subtests); 54 methods pass, with zero ERROR/SKIP. The
original 49 methods and assertions remain. Their one full-chain positive fixture
now supplies genuinely ordered, explicitly bound observations rather than three
identical observation windows; its PASS assertion is unchanged.

After the fix: 75/75 targeted tests PASS on Windows Python 3.13.15 and 3.14.7,
zero FAIL/ERROR/SKIP. Full-suite historical results above remain historical; this
review repair does not rerun CI or claim new Python 3.10/macOS runtime acceptance.

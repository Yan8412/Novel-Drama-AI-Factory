# Default-off QA feedback adapter

`feedback_adapter.py` adds an offline proposal boundary to the existing QA
candidate. `DEFAULT_ADAPTER_ENABLED = False`. No production installation,
generation, paid call, authorization consumption, or automatic rewrite follows
from a proposal. Every outcome keeps `prompt_eligible=False`,
`director_approved=False`, `production_admitted=False`, and `HUMAN_REVIEW`.

## Implemented path and limits

1. Select one **raw** QA row, not a historical feedback result or approval flag.
2. Verify actual bytes for the QA report, source, observation and PTS manifest;
   bind the QA ID, source hash, historical Prompt hash, structured input hash,
   failure type and observed interval. PTS endpoints must exist in the monotonic
   source-bound manifest and stay within its duration.
3. Reuse `qa_feedback_map()` to distinguish metadata consistency, text review
   scope, and insufficient or non-text evidence. That function stays unchanged.
4. Route the failure to its existing owner. If a supported constraint already
   exists in structured input but is missing from the compiled expression,
   propose exactly one text-field change. There is no arbitrary replacement API.
5. In an explicitly enabled local validation process, invoke the existing pinned
   Compiler 1.5.1 twice, verify the returned input/HEP/Prompt hashes and lint, and
   compare required clauses and actual output bytes. Keep human review pending.

Hash agreement proves integrity of the supplied bytes. It does **not** establish
who approved them, authenticate a visual observation, independently decode video
PTS, prove physical causality, or establish that a video will improve. The caller
must source the records through its existing private QA process. The timestamp
manifest is checked, not promoted into an independent decoding result.

## Responsibility and field mapping

Production interface inspection found Prompt Optimizer 1.4.0 and the Cinematic,
Character Performance and Asset Spatial Directors 1.2.0. These Skills contain
Markdown guidance and schema contracts, not Python/LLM execution functions.
Routing below means ownership metadata, not that four models were called.

| Failure domain | Existing owner | Existing structured interface | Adapter behavior |
|---|---|---|---|
| Camera continuity | Cinematic Director + Optimizer | `DIRECTOR_INTENT.camera_reason` / `ShotIntent.camera_note` | Project existing `No cuts` into `camera_note` only when absent from source Prompt |
| Audio constraints | Cinematic Director + Optimizer | `audio_constraints` / `ShotIntent.sound_note` | Project existing `No dialogue` or `No music` into `sound_note` |
| Contact versus load | Character Performance Director | `motion_causality.contacts`, `contact_model` | Route for review; no change |
| Grip versus active force | Character Performance Director | `motion_causality.force_sources`, actions | Route for review; no change |
| Screen versus world continuity | Asset Spatial Director | Actor/region/reference/state/asset contracts | Route for review; no invented exit or disappearance |
| Action timing | Cinematic Director | `timing_milestones`, `motion_milestones` | Route for review; no time change |
| Other expression concerns | Prompt Optimizer | Existing explicit source constraints | No unsupported free-form rewrite |

`performance_notes` enters HEP but is not directly rendered as a complete prose
section by Compiler 1.5.1. Changes there cannot be claimed to improve Prompt
output. The adapter does not rebuild Director schemas or the Compiler.

## Minimal expression change

The synthetic positive case has an existing `negative_constraints = ["No cuts"]`.
Compiler 1.5.1 preserves that list in HEP but does not render this broad negative
in its final Prompt. The only proposed difference is:

```diff
- camera_note: A steady camera follows the action
+ camera_note: A steady camera follows the action; no cuts
```

The semicolon preserves a single SentenceIR sentence. The constraint is copied
from the existing input, never invented from a failure description. All motion,
time, contact, asset, reference, bindings and preflight fields remain identical.
This demonstrates a specific missing-expression repair. It is not a general
semantic-equivalence engine, a stronger safety rule, or evidence of visual gain.

If the rule is already explicit, especially `PRESENT_BUT_OUTPUT_FAILED`, return
`NO_PROMPT_CHANGE_JUSTIFIED`. Do not keep adding prohibitions because a generated
video failed. Unsupported physical/asset changes also return no justified text
change. Malformed or mismatched evidence returns `BLOCKED`. Insufficient evidence
never generates a revision. A no-change result retains original input and Prompt
hashes and must not normalize the original bytes.

## Input contract

`Artifact(ref, content, sha256)` contains caller-selected bytes. The adapter opens
no path or URL. Its SHA must be the actual SHA256 of `content`, not a placeholder.
The structured baseline has exactly `intent`, `bindings`, and `preflight`.

The raw QA report JSON has `schema_version=1`, `input_sha256` (the deterministic
JSON hash of that baseline), and unique `records[].qa_id`. Each record uses the
existing `qa_feedback_map` fields plus:

| Field | Meaning |
|---|---|
| `failure_type` | One declared failure domain in the routing table |
| `constraint_index` | Index of an existing `intent.negative_constraints` entry; not new text |
| `source_ref` | Key of the actual source artifact in the explicit registry |
| `ref` | Key of the observation artifact |
| `pts_ref`, `pts_sha256` | Key and actual hash of the source timestamp manifest |
| `expected_mechanism` | Must equal that existing constraint for an expression proposal |

An observation JSON binds `kind=OBSERVED`, `failure_type`, `source_sha256`, and
`pts_s=[start,end]`. The timestamp manifest binds `source_sha256`, `duration_s`,
and strictly increasing `pts_s`. Missing actual samples, contradictory bindings,
non-finite times, duplicate QA IDs/JSON keys and stale eligibility claims fail
closed. All synthetic source bytes in tests are clearly non-video fixtures.

Production `FailureEvidence` remains unchanged: `OBSERVATION` records cannot be
converted into `QA_CHECK` verdicts. The native domain checks reference syntax,
not file integrity. This adapter's envelope provides an explicit integrity
boundary; no automatic exporter from the canonical production store is installed.
An upstream exporter still needs an approved mapping of observation/QA IDs and
verified PTS. Caller labels such as `approved=True` are not authority.

## Compiler and hash boundary

The executable interface is existing
`production_kernel_1_5_1_compiler.compile_video(intent, bindings, preflight)`.
It returns `hep`, `prompt`, `trace`, `lint`, and `sentence_audit`. The canonical
alternative, `compile_canonical_task`, requires all six groups: ShotIntent,
StateSnapshots, ReferenceBindings, FailureEvidence, GenerationRecipe and model.
This adapter does not mutate or construct a production GenerationRecipe.

`validate_candidate_input()` requires an **independently retained**
`expected_baseline_input_sha256`, captured before creating the proposal. Do not
take this expected value back from a mutable proposal. It reconstructs the sole
allowed change and rejects hidden action/time/contact/asset changes. The selected
clause must still match the original indexed constraint.

Both validation functions additionally require `expected_proposal_sha256`, saved
independently immediately after `propose_revision()` returns. This binds the QA
identity, routing, selected constraint, required clauses and complete field diff;
re-hashing a subsequently modified proposal is not a valid approval. Neither
anchor is a cryptographic signature or independent evidence of human consent.

`review_compilation()` requires both independent anchors. It verifies actual
UTF-8 bytes including the final newline, compiler trace hashes, unchanged required
clauses, and new literal expression of the selected constraint. Compiler HEP
hashing excludes `semantic_reviews`, matching the existing lint contract.

An arbitrary self-consistent dictionary cannot prove that a real Compiler ran.
The local runner separately records its actual pinned import, invocation and
dependencies. The pure review function does not provide a semantic oracle that
detects every possible invented sentence in a forged compiler result.

There are four distinct hashes:

- `baseline_prompt_sha256`: actual pre-change Compiler output.
- `candidate_prompt_sha256`: actual post-change Compiler output.
- `source_sha256` / `effective_sha256`: candidate and explicit unchanged offline
  delivery bytes, under `OFFLINE_IDENTITY_HANDOFF` only.
- `provider_effective_sha256 = null`: actual provider outbound Prompt is
  `UNVERIFIED_NOT_INVOKED`. No provider transport or spend authorization runs.

## Reproducible validation

Standard-library tests need no production installation:

```sh
PYTHONPATH=src python -B -m unittest discover -s tests -v
python -B tools/guard_staging.py .
```

The optional real-Compiler probe is disabled by default. Run
`python -B tools/validate_feedback_adapter.py --help` for its explicit local path,
hash pin and enabling arguments. It emits JSON to stdout; keep detailed local
paths, production dependency hashes and private evidence outside the public tree.
It reads the existing engine and its synthetic fixture function, never the
fixture's historical acceptance test setup. No installation is performed.

The process uses read-only/network-denial audit checks and only permits the
existing local Node schema-validation subprocess. These are cooperative Python
guards, not an OS security sandbox or a guarantee against hostile native code.
Compiler schema validation uses existing local Ajv dependencies. It does not
connect to the browser/LibTV service despite the validator directory's name.

### Local validation recorded on 2026-10-20

| Check | Result |
|---|---|
| Windows Python 3.13 full suite | 270 total: 268 PASS, 0 FAIL/ERROR, 2 SKIP |
| Windows Python 3.14 full suite | 270 total: 268 PASS, 0 FAIL/ERROR, 2 SKIP |
| New adapter regression cases | 38 PASS, no skips |
| Existing test files | All six retained without modification |
| Actual local Compiler 1.5.1 cases | Four PASS: No cuts, No dialogue, No music, and present-but-output-failed/no-change |
| Default / missing pin / incorrect pin | DISABLED / BLOCKED / BLOCKED |
| Python 3.10 syntax | All 16 Python files parsed; no new 3.10 runtime claim |
| macOS and hosted CI for this change | Not run; no workflow dispatched |

The two skips in each full suite are real file/directory symlink creation denied
by the Windows host. The existing junction test passed. Earlier cross-platform
CI is evidence for its own commit, not this new adapter.

The actual synthetic camera-case candidate Prompt was:

```text
Mira's jump is the sole active driving force.

0–1s: Mira jumps across the marked space.

1–3s: Mira descends under gravity toward the floor; their feet reach the walkable floor and take their weight.

3–4s: Mira balances over her grounded feet.

A steady camera follows the action; no cuts.

A footstep accompanies ground contact.
```

Its actual UTF-8 output, including the final LF, has SHA256
`4cc96be00eae1b90aa4601b74e78f86abb4e80d649f11148369a40ca7e59907e`.
The baseline is
`8eae5125c636ab0e404a37ff44f005fdaf01466f0676d353491b880f609fe1bc`.
All non-camera required sentences survived. Both schema checks passed; both
compiler overall lints remained `UNVERIFIED`. No video was generated. The
no-change case reproduced its original Prompt bytes and hash exactly.

## Historical review and production entry conditions

Re-evaluate raw historical QA with the current `qa_feedback_map`; do not reuse
old derived `prompt_eligible=True` outputs as approval. Preserve original QA,
Prompt and media bytes. A prior candidate with explicit rules and an unresolved
visual failure stays `NO_PROMPT_CHANGE_JUSTIFIED` / `HUMAN_REVIEW`. Its old compile
receipt cannot stand in for this adapter's real synthetic compile verification.

Before production: review the field mapping and proposal, authenticate private
QA/PTS through the native workflow, approve any semantic/asset change separately,
verify actual provider-effective bytes through the existing authorized boundary,
and obtain distinct generation authorization. None is granted by this change.

## GitHub and licensing

New implementation uses the Python standard library and existing repository
functions. No production Compiler, external implementation, private story,
Prompt, media, QA or authorization record is copied here. The owner has not
selected a project LICENSE; this change does not change that status.

Read-only repository inspection on 2026-10-20 found main unprotected and no
rulesets. Recommended owner-approved setup: require pull requests and a review,
require resolved conversations, block force pushes and deletion, and restrict
bypass. Add required CI checks only after deciding how to authorize runs on each
new head: this repository currently uses a manual-only workflow. This change
does not edit branch protection or dispatch Actions. A Draft PR is not approval,
a merge, deployment, or a new cross-platform runtime certification.

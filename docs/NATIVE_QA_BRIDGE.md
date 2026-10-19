# Native QA evidence bridge (default off)

This bridge reads an existing native QA failure and passes its verified evidence
to the unchanged Feedback Adapter. It creates no new visual verdict, Prompt,
generation authorization or production artifact. An existing rule can justify
leaving the Prompt unchanged; an unverified record cannot justify that conclusion.

## Interface and scope

```python
from novel_drama_candidate.native_qa_bridge import export_native_qa

result = export_native_qa(private_manifest, enabled=True)
```

The default is `enabled=False`, inherited from `DEFAULT_ADAPTER_ENABLED=False`.
Disabled calls read no evidence and start no process. The result is JSON-compatible
and **private**: it includes native QA text, paths, structured inputs and hashes.
Do not commit it, its manifest, or its input files to this public repository.

The CLI prints to stdout and never writes a result file:

```text
python -B tools/export_native_qa.py
python -B tools/export_native_qa.py --enable --manifest <private-manifest.json>
```

Only the existing `S1FinalFrameBasedQAResultV1` profile is currently supported.
Other profiles return insufficient evidence instead of being coerced into it.
This is a provenance bridge for existing-rule review, not a generic QA importer
or a new text optimizer. An absent literal clause never becomes an automatic
`MISSING` constraint. The original adapter's separately reviewed projection
path is unchanged.

## Explicit private manifest

The manifest has exactly five keys:

| Key | Meaning |
|---|---|
| `files` | Named local file references described below |
| `frames` | Selected native evidence frames: `{frame, path, sha256}` |
| `gate_id` | The existing native gate ID; it must occur exactly once |
| `failure_type` | Existing adapter responsibility route, selected for review |
| `rule_clause` | Exact existing text selected for semantic review |

Each `files` entry is `{path: absolute_local_path, sha256: expected_digest}`.
The required roles are:

| Role | Native source and actual check |
|---|---|
| `qa` | Original QA, original verdict, reviewer, approval, counts and frame references |
| `timeline` | Original extraction receipt with source SHA, probe SHA, zero-based frame indices, actual PTS and PNG SHA |
| `source` | Actual source video bytes, bound by QA, extraction and delivery receipt |
| `source_prompt` | Actual Compiler Prompt bytes, equal to the stored Compiler output |
| `effective_prompt` | Historical delivered Prompt bytes, independently bound by delivery receipt |
| `delivery` | Existing receipt linking the QA path, output video and both Prompt hashes |
| `canonical` | Original six-part structured task, bound by Compiler canonical-task SHA |
| `compiled` | Existing Compiler 1.5.1 result, including trace, HEP, lint and preflight |
| `ffprobe` | Explicitly selected, trusted local probe executable, pinned to the original extraction receipt |

The manifest selects already reviewed local sources. It is not an approval, an
authenticated author signature, or evidence that a caller's semantic mapping is
correct. Updating a manifest pin alone cannot fix a mismatched native source:
cross-file hashes, frame identities, delivery references and actual bytes must
also agree.

## Native field mapping

| Original native field | Export / adapter treatment |
|---|---|
| QA file SHA + `gates[].gate_id` | Composite QA identity; the same gate in two videos remains distinct |
| `gates[].result` | Original observed status, never promoted from INCONCLUSIVE or observation-only input |
| `reason`, `unchanged_criterion` | Preserved in the private export, not re-authored as a new QA conclusion |
| `reviewer`, `production_approval` | Preserved; bridge production admission remains false regardless |
| `source.sha256` | Checked against actual video, timeline and delivery receipt |
| `evidence[].frame_index/actual_pts_seconds/file` | Checked against original extraction frame, live probe PTS and actual PNG bytes |
| `shot_intent.data` | Adapter baseline `intent` |
| `reference_bindings[].data.compiler_binding` | Adapter baseline `bindings` |
| Original Compiler result `preflight` | Adapter baseline `preflight`; not replaced with raw FailureEvidence |
| Original Compiler `prompt` | Exact actual Source Prompt bytes, including terminal LF |

The export's observation envelope uses the adapter's `OBSERVED` wire vocabulary
and explicitly records `DERIVED_FROM_NATIVE_QA_RECORD_NO_NEW_VISUAL_VERDICT`.
It is not a new canonical `QA_CHECK` and does not turn a plain `OBSERVATION` into
a formal verdict. FailureEvidence's original observation/check distinction is
unchanged. The bridge neither imports nor writes the production domain model.

## Evidence checks and what remains uncertain

1. Open explicitly selected regular local files read-only. Reject links/reparse
   points, remote paths, oversized files, duplicate JSON keys and changed bytes.
2. Bind original QA, extraction and delivery to the actual video. Bind canonical
   input, Compiler receipt and both historical Prompt files independently.
3. Run the pinned local `ffprobe` with `-protocol_whitelist file -f mov`. Compare
   every actual video-frame PTS with the original extraction timeline. No frames
   are generated or written. The input profile is local MP4/MOV only.
4. Verify the selected native PNG bytes, exact frame-number/PTS correspondence,
   original file references and every original SHA. Do not infer relocation from
   a similar filename or substitute a re-encoded PNG.
5. Invoke the original `propose_revision`, validate its no-change structured input
   and Prompt hash, then re-read all selected files to detect changes during export.

The decoder and manifest must come from a trusted local operator. This is not an
OS sandbox and does not safely execute arbitrary third-party manifests or binaries.
The file size limit is 256 MiB per file. The probe timeout is 60 seconds.
No provider, network client, model, LibTV interface or authorization-consumption
API is imported. The probe is the only external process.

Source and Effective Prompt remain separate. The accepted historical relations
are exact bytes, or Source having exactly one additional terminal LF. The two
original hashes are preserved in the latter case; this is not an identity handoff
and is not a new provider readback.

The hashes establish local integrity and reference consistency, not authenticated
authorship, correct visual judgement, physical causation or human approval.
World-space disappearance, active assistance and load transfer remain unverified.

### Rule mapping is a separate review

`rule_clause` is selected by the caller. The bridge checks literal presence in
both actual Prompt files and exports the native criterion beside the selected
clause. It cannot prove their semantic correspondence. The mapping therefore
retains `semantic_alignment=UNVERIFIED`, `approval=NOT_GRANTED`, and
`CALLER_SELECTED_LITERAL_RULE_REQUIRES_HUMAN_REVIEW` provenance.

The known native prop-threat-continuity gate can only route to
`PROP_SCREEN_CONTINUITY`; it cannot be relabelled as force or load evidence.
Other route selections still require semantic review. An irrelevant sentence
present in the Prompt cannot gain a verified-mapping or approval label.

## Decision distinctions

| Result | Meaning |
|---|---|
| `DISABLED` | No evidence accessed |
| `BLOCKED_INTEGRITY_MISMATCH` | Bytes, references, PTS or supported contracts conflict |
| `INSUFFICIENT_EVIDENCE` | A required source/profile/record or literal rule is unavailable; no failure or repair inferred |
| `HUMAN_REVIEW` + `LITERAL_RULE_PRESENT_MAPPING_HUMAN_REVIEW` | Source evidence verified, selected rule present, unchanged adapter returned no change; semantic relevance and approval remain pending |

For the last case the preserved adapter result must also show:

```text
status = NO_PROMPT_CHANGE_JUSTIFIED
reason = EXISTING_RULE_VIDEO_FAILURE_IS_NOT_A_TEXT_GAP
evidence_integrity = VERIFIED_BYTES
pts_verification = SOURCE_MANIFEST_BOUND
field_diffs = []
```

An INCONCLUSIVE or PASS QA is not promoted to FAIL; its decision basis cannot
become the verified-failure branch. Check both evidence fields and decision basis,
not merely the adapter's general no-change status.

## Offline validation and remaining integration

Synthetic tests exercise real file reads, hashes, cross-file bindings and the
unchanged adapter. Only probe stdout is mocked; these fixtures do not claim real
video or Compiler execution. Negative cases include refreshed pins on the wrong
video/frames, frame/PTS swaps, duplicated identity, altered counts, unsupported
observations, missing evidence, unauthorized Prompt changes and changes during
the probe.

A real private historical chain was separately verified through this exporter
using the original native QA, frames, live video PTS, canonical input and stored
Compiler 1.5.1 receipt. It produced no field change and preserved both original
Prompt hashes. This reused an existing Compiler result; no new compilation or
generation was needed. Identifying QA, Prompt, frame hashes and private paths
remain in local evidence outside this repository.

A second private experiment uses a manually supplied Prompt, with no matching
canonical input/Compiler receipt. Its actual evidence can be audited, but it must
not borrow the historical or later candidate's compilation. Supporting that native
profile and its true input provenance is separate work. No false receipt is created.

Before production, finish semantic mapping review, retain native source provenance,
obtain explicit production and generation approval, and validate the actual
provider boundary under that authority. No such approval is granted here.

`DEFAULT_ADAPTER_ENABLED=False` · `PR_MERGE=NO` · `PRODUCTION_DEPLOYMENT=NO` ·
`CI_DISPATCHES=0` · `NEW_GENERATIONS=0` · `NEXT_PAID_ACTION=NONE`

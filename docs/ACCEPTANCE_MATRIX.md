# Candidate acceptance matrix

This record concerns the generic public candidate only. Private prompt text,
production paths, execution identifiers, billing and raw media are deliberately
excluded. Detailed local audit records are kept outside the publication tree.

| Check | Result | Evidence / limitation |
|---|---|---|
| Repository visibility | PUBLIC, explicitly authorized | Existing target repository was read back before work |
| Branch | `feat/mode-router-candidate` | Separate candidate; no merge or deployment |
| Publication scope | Exact allowlist only | Full file content review plus staging guard and manifest |
| Motion and guard regressions | 75 PASS / 2 SKIP / 0 FAIL | Real Windows junction rejection passed; symlink creation unavailable on this host |
| Full Windows candidate suite | 157 tests per Python version: 155 PASS / 2 SKIP / 0 FAIL | Python 3.13.15 and 3.14.7; synthetic tests, not provider or video QA |
| Existing structured-contact/compiler regression | 117 PASS (initial candidate) | Historical result retained; unchanged production source, not rerun for review correction |
| Four candidate Skills | 4/4 quick_validate PASS | Structural validation only |
| Skill references | 6/6 resolved | Local relative paths, no production installation |
| Independent Skill scenario review | PASS within offline scope | Frozen-work rerouting, unsupported controls, removing stable facial detail and unauthorized regeneration rejected |
| Hosted Windows/macOS runtime | PASS at the tested code commit | Four real jobs; details and scope below |
| Actions | One observed manual run, attempt 1; SUCCESS | No dispatch or rerun during this archival task |
| Production changes | No production mutations performed; local baseline/readback audit retained separately | Candidate workspace is independent |
| External source licenses | Verified at pinned primary-source revisions | Methods only; no upstream runtime or model dependency |
| Candidate repository license | OWNER_DECISION_PENDING | No license was invented or inherited from references |

## Portability

Python 3.10+ standard library is the candidate runtime. Windows and macOS local
commands are documented separately; executable core has no drive letters or shell
commands. The isolated filesystem test uses a Windows-only junction fixture and
skips it elsewhere. Symlink creation depends on host privileges; genuine skips
must be disclosed. Case and Unicode normalization conflicts are rejected rather
than silently normalized. UTF-8 data and LF source files are used with explicit
Git attributes.

No Node.js, FFmpeg, CUDA, MPS, OS keychain, browser, or provider authentication is
needed to run this candidate. This does not make the original production toolchain
portable: credential stores, provider bridges, GPU paths and media QA require
separate platform integration. Building/installing with setuptools is optional;
the documented offline tests do not install packages or contact a package index.

Static review or Python syntax compatibility does not establish macOS runtime
success, minimum-version execution, provider capability, physical feasibility, or
production authorization. Future promotion, license selection and additional
hosted runs remain separate decisions.

Historical local Windows test times: Python 3.13.15 1.668 s; Python 3.14.7 0.777 s. At that earlier stage, Python 3.10 had syntax parsing only. The two local skips were file/directory symlink creation privileges, not failures suppressed by changing the guard. The subsequent hosted run below closes that minimum-version and macOS runtime gap for this candidate only.

## Completed cross-platform CI, archived 2026-10-17

Tested code commit: `be742ab0bdd75f0b569943f9b7b0fc5e049ff270`.
The archival commit changes documentation and its manifest entry only; it does
not claim that its new commit SHA was itself run in CI.

[Run 38949559315](https://github.com/Yan8412/Novel-Drama-AI-Factory/actions/runs/38949559315)
was read back with its full four-job metadata and logs. Event:
`workflow_dispatch`; branch: `feat/mode-router-candidate`; run number: 1;
attempt: 1; conclusion: `success`. The exact-head run listing contained one
run. No new dispatch or rerun was performed to archive these results. This
proves one observed run/attempt, not a separate server audit of all dispatch
requests. Run start: `2026-10-16T18:43:47Z`; last update:
`2026-10-16T18:44:34Z`.

| Job ID | Actual OS / architecture | Python | PASS | SKIP | FAIL / ERROR | Unit-test time | Job elapsed | Staging guard |
|---|---|---|---:|---:|---|---:|---:|---|
| [117137239789](https://github.com/Yan8412/Novel-Drama-AI-Factory/actions/runs/38949559315/job/117137239789) | Windows Server 2025 Datacenter, 10.0.26100 / x64 | 3.10.11 | 157 | 0 | 0 / 0 | 0.260 s | 15 s | PASS |
| [117137239791](https://github.com/Yan8412/Novel-Drama-AI-Factory/actions/runs/38949559315/job/117137239791) | Windows Server 2025 Datacenter, 10.0.26100 / x64 | 3.13.16 | 157 | 0 | 0 / 0 | 1.911 s | 25 s | PASS |
| [117137239798](https://github.com/Yan8412/Novel-Drama-AI-Factory/actions/runs/38949559315/job/117137239798) | macOS 26.6.2, build 25G83 / arm64 | 3.10.11 | 156 | 1 | 0 / 0 | 0.124 s | 33 s | PASS |
| [117137239679](https://github.com/Yan8412/Novel-Drama-AI-Factory/actions/runs/38949559315/job/117137239679) | macOS 26.6.2, build 25G83 / arm64 | 3.13.16 | 156 | 1 | 0 / 0 | 1.014 s | 11 s | PASS |

Each job ran 157 tests. Architecture and Python patch version come from the
runner image and selected interpreter path; job elapsed time is the API
completed-at minus started-at interval, distinct from test execution time.
Both real file and directory symlink rejection tests passed on all four jobs.
The real Windows junction test passed on Windows and was skipped only on the
two macOS jobs with reason `Real Windows junction test`. No failures or errors
were hidden. Each guard reported 33 exact reviewed starter files; that check
is not a security audit of the private production project.

The workflow bytes are unchanged: SHA256
`F45E6502EC95CE25FB14E0610CCACB69878FBA14D0FE6224B7136CF65D1908DB`.
It retains manual-only dispatch, contents-read permission, pinned actions,
standard runners and an eight-minute timeout. There are no artifact upload,
cache, paid-provider or production-secret steps. The macOS Python 3.10 setup
downloaded the interpreter and ran its bundled certificate setup; workflow
tests themselves install no dependencies. Hosted setup is not an air-gapped
process, even though the test suite is offline.

All four logs warn that the pinned checkout/setup-python actions target Node.js
20 and are being forced onto Node.js 24. They also report the `punycode`
deprecation warning. These warnings did not fail the jobs. Maintenance proposal:
review upstream Node.js 24 action releases and their full commit pins in a
separate change, then request a separately authorized validation run. Do not
silently update pins or rerun this accepted result. See the
[GitHub Node.js 20 deprecation notice](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/).

Cost evidence: public repository plus standard GitHub-hosted runners, with no
larger-runner, artifact-upload or cache usage configured. Under
[GitHub's published billing rules](https://docs.github.com/en/billing/concepts/product-billing/github-actions),
expected CI cost is USD 0; no extra billing path was found in this workflow.
No account invoice or settled billing receipt was obtained, so final settled
cost remains `UNVERIFIED`. No new cloud test was started during archival.

Acceptance scope: this generic candidate ran on these actual Windows/macOS
hosts and Python versions. This does not validate the full production factory
on macOS, new provider modes, motion quality, or replacement of human video QA.
The PR remains Draft; production admission remains false. License selection is
still `OWNER_DECISION_PENDING`; no LICENSE file is added.

## Review 5537067732 correction

Regression cases were run against the old implementation before correction.
The corrected full Windows suite includes 28 additional test methods.

- Shot/phase classification flags must be supplied explicitly; omission is unknown, not false.
- `PhaseCoverage(begin_ms, end_ms, expected_actors)` declares the scope. Each actor is checked independently for order, overlap, gaps and support handovers. Different actors may act concurrently. Full-shot checks require zero start and the actual contract endpoint; absent or partial coverage stays `UNVERIFIED`.
- `DESIGN_ASSUMPTION` may remain in the plan sidecar, but every emitted field must have `APPROVED_FACT` provenance before candidate text is returned. The caller still authenticates the upstream approval.
- Malformed observations return controlled findings. Discrete samples retain coverage `UNVERIFIED`, even when a specific transition has a local static explanation. Evaluate all findings; an individual `PASS` does not erase an unresolved finding.

Only candidate source, corresponding tests, this record and the hash manifest
changed. Skills, staging protection, the manual-only workflow and production code
remain unchanged. That correction used no hosted Actions or provider calls;
the later hosted CI run is archived separately above.

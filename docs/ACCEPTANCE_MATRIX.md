# Candidate acceptance matrix

This record concerns the generic public candidate only. Private prompt text,
production paths, execution identifiers, billing and raw media are deliberately
excluded. Detailed local audit records are kept outside the publication tree.

| Check | Result | Evidence / limitation |
|---|---|---|
| Repository visibility | PUBLIC, explicitly authorized | Existing target repository was read back before work |
| Branch | `feat/mode-router-candidate` | Separate candidate; no merge or deployment |
| Publication scope | Exact allowlist only | Full file content review plus staging guard and manifest |
| Motion and guard regressions | 51 PASS / 2 SKIP / 0 FAIL | Real Windows junction rejection passed; symlink creation unavailable on this host |
| Full Windows candidate suite | 129 tests per Python version: 127 PASS / 2 SKIP / 0 FAIL | Python 3.13.15 and 3.14.7; synthetic tests, not provider or video QA |
| Existing structured-contact/compiler regression | 117 PASS | Local read-only regression; production source unchanged |
| Four candidate Skills | 4/4 quick_validate PASS | Structural validation only |
| Skill references | 6/6 resolved | Local relative paths, no production installation |
| Independent Skill scenario review | PASS within offline scope | Frozen-work rerouting, unsupported controls, removing stable facial detail and unauthorized regeneration rejected |
| macOS runtime | MACOS_RUNTIME_UNVERIFIED | No Mac host or hosted workflow run used |
| Actions | Manual-only, not dispatched | Windows/macOS matrix; full commit pins; read-only contents permission |
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
production authorization. Future promotion, license selection and hosted runs
remain separate decisions.

Final Windows test times: Python 3.13.15 0.377 s; Python 3.14.7 0.370 s. Python 3.10 syntax parsing passed; its runtime was not executed. The two skips are real file/directory symlink creation privileges, not failures suppressed by changing the guard.

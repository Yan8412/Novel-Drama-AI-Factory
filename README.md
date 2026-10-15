# Novel-Drama-AI-Factory

Public development repository for **isolated, non-production** tooling experiments and cross-platform offline tests for a novel-to-video workflow.

## Publication and execution boundaries

- **Do not publish:** API keys, access tokens, credentials, `.env` files, unpublished manuscripts, proprietary prompts, original production videos or images, private provider requests/responses, billing records, HSA/JIT authorization evidence, or internal execution logs.
- **Do not upload or commit the local production project wholesale.** Only explicitly reviewed, redistributable, non-sensitive source files and synthetic test fixtures may be proposed here.
- **No production authorization:** code in this public repository is not an instruction to deploy, submit paid provider jobs, generate videos, or reset/consume existing production quotas.
- **Preserve frozen production assets:** past S1/S2 outputs, QA evidence, locked endpoints, and original hashes remain in controlled production storage. They are not part of this public repository.
- **Review before merge:** candidate Mode Router, motion-state validation, and prompt-compiler enhancements require isolated testing, license review, and independent approval before production integration.

## Development plan

1. Keep `main` stable.
2. Develop candidate features in review branches and open pull requests.
3. Test Python logic offline on Windows and macOS where supported, without invoking paid providers.
4. Use only synthetic examples and permitted source code.

See the pull request history for proposed changes. This repository intentionally starts without production source code.

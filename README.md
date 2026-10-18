# Novel-Drama AI Factory: offline mode-routing candidate

Feedback candidate extension: see [the adapter scope](docs/FEEDBACK_ADAPTER.md) and
[source/attribution boundaries](docs/FEEDBACK_PROVENANCE.md). This branch is for
Draft PR review, not installation or production deployment. The older acceptance
matrix applies only to its named baseline commit; it does not certify this extension.

This branch contains a reviewable extension to an existing Director -> structured
Compiler -> Provider architecture. It is not a production replacement. It never
creates a provider node, dispatches a generation, signs spend authorization, or
changes a production asset. All bundled test inputs are synthetic.

The five candidate families are text-to-video, image-to-video, explicit first/last
frames, multiple keyframes, and motion reference. A mode name is not evidence of
provider support. Routing consumes explicit, fresh, matching capability and cost
records and keeps complex or uncertain shots under human review.

## Local validation

Python 3.10+ is required; runtime and tests use the standard library only. No pip
install, Node.js, FFmpeg, GPU, cloud account, or provider key is required.

Windows PowerShell:

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m unittest discover -s tests -v
python -B tools/guard_staging.py .
```

macOS shell (instructions, not a claim of a completed macOS run):

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B tools/guard_staging.py .
```

Read [integration boundaries](docs/SKILL_INTEGRATION.md),
[architecture](docs/ARCHITECTURE_ADR_MULTI_MODE.md),
[acceptance](docs/ACCEPTANCE_MATRIX.md), and
[publication security](docs/GITHUB_MIGRATION_SECURITY.md).
The `skills/` entries are candidate overlays, not installed production Skills.

## Publication and licensing

Only explicitly reviewed generic code, synthetic tests, and sanitized documents
belong here. Production prompts, stories, media, credentials, billing, and private
execution evidence remain outside this repository. GitHub Actions is manual only;
this change does not dispatch it. See [source provenance](docs/EXTERNAL_SOURCE_PROVENANCE.md).
GitHub is the code version center: controlled branch -> isolated local changes ->
tests -> public-content review -> commit -> push -> Draft PR -> review -> human
merge/deployment decision. Validated publishable candidates must enter this flow.
Private media, prompts and ledgers stay in protected storage, associated with code
by private commit/hash references. A local test does not update GitHub.

The owner has not selected a license for this repository. Public visibility must
not be interpreted as an MIT/Apache/BSD license grant for this candidate.

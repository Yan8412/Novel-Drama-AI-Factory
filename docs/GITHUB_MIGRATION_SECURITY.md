# Public candidate publication boundary

The current human decision authorizes a public candidate repository and an
unmerged Draft PR. Earlier private-repository setup instructions are superseded.
No production deployment, provider action, billing change, or cloud workflow run
is authorized by publishing this branch.

## Exact allowlist

`tools/guard_staging.py` owns an explicit file allowlist. Review every addition to
that list. Reject unexpected files, links, reparse points, path/case conflicts,
invalid encodings, suspicious secrets, and unsafe or unstable reads before
publication. A scan is necessary, not proof that arbitrary content is public.

Human-readable diff review must also reject private narratives/prompts, asset and
job identifiers, spend credentials, billing records, media, raw provider
responses, production source collections, and private local evidence. Do not
publish first and delete later. Keep private review material outside this Git
working tree, not merely in an ignored directory inside it.

Use explicit paths when staging, inspect the staged content and hashes, and bind
publication to exactly the reviewed bytes. Reject any intervening change before
upload. Update only the intended candidate branch, using its observed parent and
an expected-head check. Do not force-push or merge. No credentials belong in
command arguments, saved logs, URLs, or source files.

## Limits

The guard is cooperative local validation, not an OS security boundary against
an adversarial same-user process. Race checks and before/after identity checks
reduce accidental replacement risk but do not create a universal sandbox.
The Git metadata directory is excluded from source scanning and is never uploaded
as a candidate file. Review the commit tree separately.

The manual-only workflow needs separate approval before any hosted execution.
Secrets are neither configured nor supplied. Production state and its mutation
lease mechanism remain unchanged; all candidate work occurs in an independent
workspace. No task may use this document as authority to reset historical quotas.

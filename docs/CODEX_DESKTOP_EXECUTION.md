# Candidate maintenance workflow

1. Read the current human task and protect production. Keep private evidence in a
   separate local directory. Do not load credential stores to populate examples.
2. Work only in the isolated candidate branch. Compare accepted interfaces before
   adding an abstraction; prefer a small overlay over a replacement compiler.
3. Run all local offline tests and the exact staging guard. Preserve real skips
   and failures. Do not mark a platform tested from syntax inspection alone.
4. Review every staged file and the complete manifest. Upload only the reviewed
   byte set to the authorized repository/branch, then verify the remote commit.
5. Create a Draft PR. Do not merge, deploy, run Actions, or generate videos.

A public review copy contains generic explanations and synthetic fixtures.
Detailed production hashes, private prompt comparisons, and execution evidence
belong only in the private local audit. Publication permissions do not grant
permission to rewrite accepted production records or replenish consumed quotas.

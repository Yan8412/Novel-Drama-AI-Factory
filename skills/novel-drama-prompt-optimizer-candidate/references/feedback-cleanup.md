# Evidence-bound feedback and cleanup

Use this only when a review has actual failed or inconclusive output evidence. The optimizer still owns diagnosis and the HEP/compiler handoff; it does not own media QA or new production authorization.

For each proposed change, bind the exact historical and candidate prompt hashes, original QA gate, observed status, source frame interval and actual PTS. Keep design deadlines in separate fields. Use the candidate `qa_feedback.py` sidecar checks together with the existing byte-fidelity review; neither replaces Compiler 1.5.1 or authenticates an approval record by itself.

Classify the change as `TEXT_ONLY`, `CONTRACT_CHANGE`, `REFERENCE_CHANGE` or `PROVIDER_MODE_CHANGE`. A shorter sentence that changes a deadline, force source, contact, camera path or endpoint is not `TEXT_ONLY`. In an expression-only task, the other classes remain proposals requiring their own authority. If a requirement is explicit but the video failed, retain `PRESENT_BUT_OUTPUT_FAILED`; adding the same rule again is not an evidenced repair mechanism.

For script-to-prompt cleanup, retain action owners, source-supported timing, continuing support and object identity. Never add a final-second freeze, a landing, new contact or a landscape instruction to a portrait contract. Preserve approved facial texture and stable identity details. Keep hashes, QA labels and unresolved inference metadata in the sidecar, not creative prose. An unresolved `DESIGN_ASSUMPTION` cannot be relabeled `APPROVED_FACT` to pass a compiler.

Return the smallest justified text delta. If the reviewed candidate already supplies it, return `NO_PROMPT_CHANGE_JUSTIFIED` and retain that candidate's hash and review status. Clearer wording does not prove improved video or a repaired prop. Keep each original formal QA result immutable; candidate static findings cannot replace the existing shot review or grant generation, retry, network or deployment permission.

---
name: novel-drama-cinematic-video-director-candidate
description: Review observable timing, camera and motion continuity for an offline Novel-to-Drama shot candidate, including contact-sensitive actions and persistent props.
metadata:
  version: "0.2.0-candidate"
---

# Cinematic Video Director Candidate

This isolated overlay proposes `DIRECTOR_INTENT`; it does not replace an installed Skill, alter approved endpoints, choose a provider, or execute generation.

Use the approved shot brief and existing intent schema. Keep the primary action actor-owned: action, target and visible body response. For a contact-sensitive shot, distinguish grip from force, passive contact from load-bearing support, and permission to touch from evidence that a touch occurs.

Read [temporal visibility](references/temporal-visibility.md) when reviewing a difficult transition, short readability window, or persistent prop. A simple shot does not need a new graph or expanded review checklist.

Keep proposed beat times separate from source-media observations. Cite original frame/PTS privately when actual media is available; do not convert a design interval into verified video behavior. Do not infer depth, force, occlusion, or a camera move from a single endpoint.

Write the result into existing `primary_motion_chain`, `timing_beats`, `physics_constraints`, `camera_reason`, `first_frame_state`, and `required_end_state` fields. Keep additional evidence in the review sidecar rather than extending the installed schema. Route through the optimizer-owned HEP and accepted compiler; no candidate state changes production QA.

For interacting simultaneous actions or frame-level failure feedback, read [load and frame review](references/load-and-frame-review.md). This adds a review sidecar, not a new storyboard authority.

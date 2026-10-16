# Temporal visibility review

For each implicated transition, identify the entry state, actor action, continuing contact/support, visible response, and resulting state. Use intervals when motion must remain continuous; separate a design duration from measured media time.

For a prop that should persist, track its known world location independently of screen visibility. An unseen object is not automatically absent. An offscreen or occluded explanation needs a compatible camera/occluder path and endpoint geometry; the words "offscreen" or "behind the actor" alone do not establish that path.

Check camera and subject movement together. If a claimed reframing removes a foreground object, ask which stable landmarks should move and whether the actual evidence supports that projection. Do not invent retraction, disappearance, restoration, or an unseen event to satisfy an endpoint.

Keep a short readable interval as a QA risk when no approved threshold proves it sufficient. Do not silently lengthen the shot, relax the ending pose, or add a cut that hides required movement. Offer the smallest reviewable design change if these constraints conflict.

Use the repository's `check_object_lifecycle` and `check_contact_phases` only as offline evidence-completeness checks. Supply the current dataclass fields and actual provenance as required. A declared transition can be internally consistent while visual legibility or physical feasibility remains unverified.

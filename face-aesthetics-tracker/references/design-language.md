# Design language and semantic decisions

## Visual hierarchy

The face remains the subject. Annotations should explain what the viewer already sees, not become the first thing they see. Use one primary relationship per shot and let secondary points support it.

Preferred hierarchy:

1. The changing facial feature or structural relationship.
2. A soft region, bone contour, or paired landmarks.
3. Optional pulse or reveal that directs attention.

Avoid combining dense landmarks, measuring grids, large labels, hard polygons, and strong fills in one shot.

## Region versus line

Use a region when the claim concerns area, support, volume, flatness, fullness, shadow, or texture. Use a line when the claim concerns an axis, boundary, proportion, angle, or structural contour. Use paired points only when they clarify symmetry or endpoints.

If a line would conceal the evidence—especially wrinkles, folds, shadows, or texture—replace it with external corner brackets or a feathered halo.

## Motion

- Smooth landmarks over time; a useful default is 70% prior position and 30% current detection.
- Fade in during the first 0.35–0.55 seconds.
- For X-ray or anatomical perspective, use a low-frequency 1.6–2.2 second breathing pulse. The minimum state should remain faintly legible rather than flashing off abruptly.
- Reduce overlay strength when the tracked face turns away from the view that supports the claim.
- If tracking disappears, fade rather than freeze or jump.

## Palette

- Warm ivory for structural contours.
- Champagne or bone rose for anatomical planes.
- Muted peach for selected soft-tissue regions.
- White only for tiny highlights; avoid pure red except when the user requests a diagnostic style.

Opacity should be judged at normal playback size. Increase region readability by refining shape and contrast before adding hard outlines.

## Established corrections

- Nasolabial folds: do not draw a curve over the fold when the intended effect is that it becomes lighter.
- Nasal base: use two separate alar-side curved regions; never place the selection in the central columella/subnasale area.
- Mid-face support: use a larger feathered field around the nasal-base regions, not angular cheek triangles.
- Bone perspective: make the eye treatment represent bony orbits rather than eyeliner; keep skull references elegant and translucent.

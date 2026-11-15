# Later

Ideas and tasks parked for later.

## AP exam redesign
- Move the AP runner (`apps/apclasses/templates/apclasses/attempt.html`) and the AP result page
  (`apclasses/result.html`) to the modern SAT runner style (`templates/test/shared/*`):
  same header, fonts, answer cards, question navigator, light/dark themes.
- Result page: drop the legacy "SAT MAKON" header, the red "Back to Event" button with a refresh icon
  and the raw green answer squares; reuse the SAT results layout (score cards, question map).
- Found during the V75 device audit (2026-11-15): it works on every device, it only looks dated.

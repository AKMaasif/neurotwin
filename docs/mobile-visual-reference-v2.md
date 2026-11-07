# Direct visual-reference implementation — 7 November 2026

This pass responds to the user's correction that the earlier UI still looked cheaper and different from the supplied three-phone reference. It replaces simplified artwork and refines composition rather than declaring the earlier style “close enough.” It works in the existing `/mobile/` app and preserves the separate `/dashboard/` app.

## Concrete changes

- Replaced flat clipboard/heart drawings and the simplified hero brain with three dedicated, transparent 3D-style illustration assets. They are stored locally as 512px WebP files under `web/mobile/assets/reference-v2/` (102,496 bytes combined). Generation prompts and provenance are in that folder's README.
- Bundled the actual Inter variable font locally, with the official license, rather than relying on a system-font approximation. Typography, weights, paragraph widths and compact metadata now use the same family consistently.
- Reworked `reference-match.css` as one authoritative visual module: compact Home branding/greeting, blue scenic hero, response-count ring, four coloured action tiles and purple active navigation; illustrated Plan/Support headers; compact white routine cards; and the lavender support-action panel.
- Reduced the Plan header/list gap and card density to follow the reference's first screen. Sharing/UUID detail is available in each existing details menu; timing, consent, pause and sharing operations remain connected. Routine filters continue to reflect real states, rather than inventing the reference's example completion count.
- Grouped Home’s greeting, hero, summary and shortcuts into a first-screen region with bottom-navigation clearance. The next activity stays available below it rather than peeking underneath the navigation. Resize remains CSS-driven and does not reset forms.
- Kept the adaptive rail/sidebar and used a deliberate desktop composition: hero left, activity summary and care-team information right, then actions and current work. Tablets retain simpler arrangements when insufficient space remains for those columns.

These are real app components, not an image of a UI used as a substitute for functionality. The reference's fictional profile portrait, sample counts and relative update timestamp were not fabricated. The profile uses the account initial; counts and reminders remain backed by the authorized workspace.

## Scope protection

Compared before/after SHA-256 snapshots of 52 files under `web/dashboard/` and `app/`: **zero changed in this pass**. No database schema, authorization, clinical decision, message/privacy or provider logic was altered. No primary data was modified by tests. Existing unrelated local changes remain preserved. No GitHub push or deployment was performed.

Changed application files: `web/mobile/reference-match.css`, `ui.js`, `routines.js`, `index.html`, plus the new local font/illustration assets. New visual verification: `scripts/visual_reference_browser_check.cjs`. Existing business workflow controllers remain in use.

## Current verification

- Five-browser matrix: 14 viewport sizes × eight pages × Chromium/Chrome/Edge/Firefox/WebKit, **560 checks passed**. This includes all requested phone widths (320, 360, 375, 390, 430, 480px), tablets, laptops and screens through 2560px, with current font/assets/layout.
- Reference-focused screenshot check: **18 screen/viewport checks passed** over Home, Plan and Support at 375/390/768/1024/1440/2560px. It verifies local images decode, the real local font loads, and all four Home shortcuts clear the bottom nav in the 375/390px portrait views.
- The established isolated browser batch passed all nine scripts: core 8; companion 10; reports 6; routines 9; messages 8; voice notes 10; multimedia 10; care pages 6; family reports 5 — **72 scenarios**.
- Enlarged text, entered routine values, orientation/resize, slow initial loading, simulated error/retry, and family/touch checks passed in the state/recovery script. Routine filtering/details and patient/family permissions also passed the separate premium screen check.
- Screenshots of the three primary phone screens and desktop/tablet variants were inspected. Formatting, JavaScript syntax, Ruff and diff checks pass. The primary local app serves the new illustration/font files successfully.

Artifacts are in ignored `test-results/visual-reference-v2/`: actual viewport PNGs, `report.json`, a three-screen HTML preview and `three-screens.png`. The preview frames contain screenshots of the connected application; they do not introduce fake OS status bars or nonfunctional product controls.

This remains synthetic/browser verification, not clinical or production certification. Actual Safari/iOS/Android/foldable devices, assistive technology and native toolbar zoom still require manual validation. Reflow-equivalent zoom and CSS text enlargement are automated checks. Field p75 performance and INP have not been certified. The Python suite was not repeated for this presentation/asset-only change; prior backend evidence remains separately dated.

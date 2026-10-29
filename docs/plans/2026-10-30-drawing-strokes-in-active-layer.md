# DEV-16: Keep brush strokes in the current drawing layer

## Problem and behavior

FullDrawingEditor treated each Fabric path as a top-level layer. Every pen or eraser gesture therefore created another Layers row.

New pen/eraser paths now belong to a persistent Fabric drawing-layer group. The first stroke creates one drawing layer; subsequent strokes append to the selected drawing layer. New layer explicitly creates another. Clearing Fabric's transform selection when changing tools retains the active layer. Locked or hidden drawing layers reject strokes. Existing standalone objects in version-1 documents are preserved, and groups serialize in the existing document format.

## Verification

- Browser plugin unavailable; used Playwright with isolated headless Edge against the real component, mocked drawing-project storage, and no user projects.
- URL: http://127.0.0.1:5179/react/.drawing-layers-qa.html; viewport: 1440x950. Temporary entry is deleted by the script.
- Command: `.venv\Scripts\python.exe scripts/qa_drawing_layers.py` (run Vite on the URL above first).
- Browser checks: correct title/URL, meaningful editor content, no Vite overlay, no console/page errors, interaction assertions, screenshot inspection: PASS.
- Interactions: three strokes share one layer; undo/redo removes/restores a stroke; explicit new layer; select prior layer then draw; save/reload groups and continue drawing; eraser appends within the layer; locked layer rejects stroke; legacy standalone paths remain preserved: PASS.
- `npm test`: 40 passed. `npm run lint`: exit 0. `npm run build`: exit 0; bundled frontend regenerated.
- Evidence: `test-results/drawing-qa-result.json`, `test-results/drawing-layers.png`, `drawing-qa.log`, `drawing-state-tests.log`, `drawing-lint.log`, `drawing-build.log` (local ignored artifacts).

## Limits

This verifies the editor component with simulated storage, not an installed Tauri build or a production backend save. Existing per-stroke layers are preserved rather than automatically merged. Other viewports and actual tablet pressure were not tested. The earlier whole-backend Blender/path environment limitation remains tracked separately.

Owner direction remains: do not publish. No push, release, installation or user drawing modification is part of this fix.

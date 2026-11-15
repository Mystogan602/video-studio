# QA checklist

Run `qa.py`, then open the images — numbers alone do not catch visual problems.

## Measured (`out/qa/report.md`)

- Duration within the brief (± 15 %); resolution = canvas.
- Loudness within ±2 LU of the target (−16 LUFS default), true peak below −1 dBTP.
- Every segment present in the expected order and length.

## By eye — `contact.png`, every `segment-NN.png`, zoomed frames

- The first frame of every clip: right screen, no leftover dialog, keyboard or loading state.
- Subtitles: one or two lines, never cut off, never covering the content that matters (band mode never covers it by design).
- Each claim in the narration is visibly true at that moment (filter applied, number shown, bug gone). Zoom in on those frames.
- No personal or sensitive data: notifications, chat heads, wallpapers, passwords, tokens, real customer data, other people's names.
- No system overlays: toasts, battery / screen-time reminders, dev-tool banners (`--watch-region` sheet for the top strip on phones).
- Cards: text centred, not wrapped awkwardly, diacritics correct.
- Fast-forwarded stretches look intentional (no 2.5× typing of something the narration talks about).
- `out/poster.jpg` is a clean, readable frame (title or the key screen); otherwise set `poster.atSeconds` and `merge` again.

## Audio

- Listen to the first and last 20 s and every line flagged by `tts.py`.
- No clipped words at clip boundaries; no overlap between lines.

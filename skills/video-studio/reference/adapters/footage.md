# Footage

Narration first, footage second: record only after the lines are voiced, so every action can be timed to its line.

## The narration-driven pattern (recordings)

Each recorded clip has a scenario module (`clip-scripts/clip<id>.mjs` in the project) that a recorder runs:

```js
export default async function scenario({ step, waitNarration, pause /* + device or page */ }) {
  await step(1); /* actions */ await waitNarration();
  await step(2); /* actions */ await waitNarration(1.5);   // extra seconds for a slow screen
}
```

The recorder starts the take (lead-in), runs the scenario, adds a tail and writes `clips/<id>/raw.mp4` + `timeline.txt`. `step(N)` logs when line N starts (it is placed there in the final video); `waitNarration()` waits until line N has been spoken + a settle time. Long silent stretches between lines (slow taps, loading) are fast-forwarded by `compose.py`, so do not rush the screen. Scenarios are plain JavaScript and run unchanged on Windows, macOS and Linux.

## Android (`scripts/record/android.mjs`)

```
node <skill>/scripts/record/android.mjs --project <dir> --clip 01 --scenario <dir>/clip-scripts/clip01.mjs [--serial <device>]
```

Node ≥ 18 and `adb` (on PATH or `ADB_PATH`); no `npm install` needed. Device: `--serial`, else `ANDROID_SERIAL`, else the only connected one. Template: `<skill>/templates/android-scenario.example.mjs`.

| In the scenario | Use |
|---|---|
| `export async function prepare({ device, pause })` | optional, runs **before** the take: `device.restartApp(package, waitSeconds)`, `device.openDeepLink(url, package)` — a clean start for every clip |
| `device.tap(x, y)`, `device.swipe(x1, y1, x2, y2, ms)`, `device.key('KEYCODE_BACK')`, `device.typeText('abc')` (ASCII only) | input |
| `device.tapText('Label', { x })`, `device.findText('Label')`, `device.hasText('…')` | uiautomator lookups — cost 2–5 s, prefer fixed coordinates from the dry run |
| `device.shell('…')`, `device.adb([...])` | anything else |

A still after the take (e.g. a web page screenshot): put it in a `slides` clip right after, with `"sectionCard": false`.

One take = one clip; `screenrecord` stops at 180 s, so split longer clips (the recorder warns near the limit). A failed scenario or Ctrl+C stops `screenrecord` and deletes the take on the device.

Device prep (undo in clean-up): do-not-disturb on; chat-head / overlay permissions off; `adb shell settings put system show_touches 1`; dismiss dev-tool toasts; log in off camera; prepare test data through the API and note ids for deletion. If the recorder was killed hard, `screenrecord` may still run → `adb shell pkill -INT screenrecord`. System toasts (screen-time reminders, battery) can appear mid-take → QA the top strip with `qa.py --watch-region`.

Phone status bar: crop it with `"recording": {"crop": {"top": <px>}}` (e.g. 80 on 1080 × 2400) and size the canvas to `device height − crop + bandHeight`.

## Web (`scripts/record/web.mjs`, Playwright)

```
node <skill>/scripts/record/web.mjs --project <dir> --clip 02 --scenario scenario.mjs [--scale 1] [--headed]
```

The scenario default-exports `async ({ page, step, waitNarration, pause }) => { … }` (template: `templates/web-scenario.example.mjs`). The video is the canvas picture area; `--scale 3` gives a phone-like layout (CSS width = video width / 3). Log in inside the scenario with credentials from environment variables, never literals, and before `step(1)` so it is fast-forwarded or trimmed.

## Desktop / anything else

Record with OBS (all three OSes) or `ffmpeg -f gdigrab` (Windows) / `avfoundation` (macOS; grant Screen Recording permission to the terminal) / `x11grab` (Linux X11; on Wayland use OBS) while reading the lines from `review/review.html`; then write `timeline.txt` by hand (`<step> <seconds>` where each line starts in `raw.mp4`). Prefer web or slides when the content allows.

## Slides

- Images: `"image": "images/x.png"` per step (any size; fitted and letterboxed).
- HTML: `"html": "slides/x.html"` per step, then `node <skill>/scripts/render_slides.mjs --project <dir>`; pages render at the canvas picture size, so design for that size (1920 × 1080 overlay mode; 1080 × (height − band) band mode). Template: `templates/slide.example.html`. Big type (≥ 48 px at 1080p), one message per slide, numbers first.
- A step without an image keeps the previous slide — use it to talk over one chart for several lines.

## Rendered (external renderer)

Contract: read `video.json` and the wav durations, render `clips/<id>/final.mp4` with the narration mixed in and any subtitles burned in, at the canvas size (other sizes are letterboxed at merge). `compose.py` only checks the file exists and merges it; its subtitles are not in `out/<name>.srt`.

**Remotion** (animated charts, motion graphics): let the official skills (`npx skills add remotion-dev/skills`) write and render the composition, with these overrides:
- The voice is this project's: give the clip `steps`, run `tts.py` first and use `clips/<id>/step<N>.wav` (never generate one there; they default to ElevenLabs). Scene lengths come from those wavs.
- Subtitle text comes from `video.json`.
- Licence: larger companies need a paid Remotion licence; check https://www.remotion.dev/docs/license first.

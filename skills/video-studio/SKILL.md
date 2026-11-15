---
name: video-studio
description: Make a narrated video end to end — brief, facts, script with an approval gate, TTS voice-over, footage (Android or web screen recording driven by the narration, HTML/image slides, externally rendered scenes, title cards), ffmpeg compose with subtitles, QA by eye, hand-over and a learnings loop. For product / sprint / feature demos, explainers and tutorials, vertical shorts, and progress reports. Use when the user says "/video-studio", "make a video", "demo video", "explainer video", "short", "report video", "làm video", "quay clip demo", "video báo cáo".
argument-hint: "<what the video is about> [demo|explainer|short|report] [landscape|vertical]"
---

# /video-studio

`<skill>` below = this skill's base directory (shown when the skill loads). Works on Windows, macOS and Linux. `python3` below means the Python ≥ 3.9 launcher of the OS: `py` on Windows, `python3` on macOS / Linux.

Before the first script on a machine, check what is missing (`ffmpeg -version`, `ffprobe -version`, `python3 --version`; `node --version` and `adb version` only when the video needs them). Give the user the install command for their OS (`reference/setup.md`) instead of guessing paths.

Every step below has a deeper reference in `<skill>/reference/` — read it when you reach that step, not before.

## 0. Load context

1. Find the workspace folder `.video-studio/` (current directory or the nearest parent). Read, if present:
   - `profile.md` — house rules for this workspace (audience, speaker voice, language, where facts come from, device / account preconditions, clean-up). **They override this file's defaults when they conflict.**
   - `learnings.md` — apply every rule under **Rules**; skim the last 3 run entries.
   - `defaults.json` — voice, canvas, brand (merged under each `video.json`).
2. No `.video-studio/`: for a one-off video just continue with built-in defaults; if the user will make more videos here, offer to create it from `<skill>/templates/` (profile, defaults, learnings) and ask only for voice adapter, language and brand.
3. Continuing an existing video: run `python3 <skill>/scripts/compose.py <project> status` first. It reads the files on disk (narration, footage, final clips: present / stale / missing) and prints the next command. Trust it over notes or memory.

## 1. Brief — ask only for what is missing

Needed: **type**, **audience**, **purpose** (what the viewer knows or does afterwards), **format** (landscape / vertical), **length**, **language + voice**, **where it will be shown**. Defaults per type: `reference/formats.md`.
Vague topic → offer 2–3 concrete angles (hook + payoff each) and recommend one. Pick a short English kebab-case slug.

## 2. Gather the facts

- Demo / report: list what was actually done from the source of truth (tracker, merged PRs, changelog). Drop anything not done, cancelled, deferred or only proposed. Only work visible on screen gets a clip; invisible work gets at most one sentence.
- Explainer: research; at least two independent sources per key claim, primary sources first; list them in the hand-over. Uncertain → say so or leave it out.
- Never invent numbers, quotes, features or results.

## 3. Outline and script → `video.json`

Project folder: `videos/<slug>/` in the workspace unless the profile says otherwise. Format, clip kinds and every setting: `reference/project-format.md` (start from `<skill>/templates/video.example.json`). Structure per type: `reference/formats.md`. Narration craft: `reference/script-writing.md`.

Run `python3 <skill>/scripts/compose.py <project> check` and fix errors (subtitle-length warnings: split the step or add a shorter `subtitle`). Then run the self-check in `reference/script-writing.md`.

**Gate 1 — script approval (mandatory).** Show the clip list and the full narration (spoken `text`, plus `subtitle` where it differs). Up to ~40 lines: in chat. Longer: give the path of `video.json` and a clip-by-clip summary. Record, render or call a paid TTS only after the user approves or edits it.

## 4. Voice

`python3 <skill>/scripts/tts.py <project>` (in the background when > ~20 lines). Default voice: VieNeu "Xuân Vĩnh" (Vietnamese, offline); **the first run on a machine installs it** (~1.3 GB, a few minutes) — tell the user first. Other voices: `reference/adapters/tts.md`. Unchanged lines are cached; `--clip <id>` limits a rerun.

Public videos, or when nobody can listen to every line: add `--transcribe` (speech recognition compares what was said with the script; first use installs it, ~800 MB). Read the `CHECK` lines it prints (speaking rate or voice similarity far from the median, words heard ≠ script): reword the sentence, give the step a new `seed`, or spell the word out, then rerun.

**Gate 2 — listening review** (mandatory for public videos, offered for internal ones): give the path of `review/review.html` (open it in a browser; an editor shows only its source), the total narration length and at most ~5 lines worth listening to. Do not paste the transcript again.

## 5. Footage — per clip kind (`reference/adapters/footage.md`)

| Kind | How |
|---|---|
| `card` | nothing to shoot (opening, closing, chapter) |
| `recording` | a scenario module per clip run by `node <skill>/scripts/record/android.mjs` (adb) or `node <skill>/scripts/record/web.mjs` (Playwright); desktop: manual recording + hand-written `timeline.txt` |
| `slides` | images, or HTML rendered with `node <skill>/scripts/render_slides.mjs --project <project>` |
| `rendered` | an external renderer (e.g. Remotion) writes `clips/<id>/final.mp4` with the narration inside |

Recording rules: dry run first (screenshots to find coordinates and timings); drive the screen one narration line at a time (`await step(N)` → actions → `await waitNarration()`); prepare the device (do-not-disturb, overlays off, test data ready, logged in off camera). What the narration says must be what the screen shows — when it is not, fix that line and re-voice only it.

## 6. Compose

`python3 <skill>/scripts/compose.py <project> all` (or `clip <id>` while iterating, then `merge`). Output: `out/<output>.mp4`, `out/<name>.srt` (subtitles as a separate file for YouTube / players), `out/poster.jpg` (thumbnail, frame at `poster.atSeconds`) and `out/segments.json`.

## 7. QA — look, do not assume

`python3 <skill>/scripts/qa.py <project> [--watch-region x:y:w:h]`, then **Read** `out/qa/contact.png`, every `segment-NN.png` and zoomed frames of the moments that prove each claim (`ffmpeg -ss <t> -i <mp4> -frames:v 1 <png>`). Checklist: `reference/qa.md`. Fix → recompose only the affected clip → `merge` → QA again. At most 3 rounds, then report what is left.

## 8. Clean up

Delete test data created for the video, restore device settings, stop processes you started (dev servers, Metro, a leftover `screenrecord`), remove scratch files outside the project.

## 9. Hand over

Start with one line naming the audience (`Written for: …`). Then: output path (+ `.srt` and `poster.jpg`), duration, one line per clip (title + length), open items (listening check, facts to verify, synthetic-voice disclosure, voice / music licences). Bugs noticed while recording: list them with the clip number and ask before filing anything. Nothing is uploaded or posted unless the user asks.

## 10. Improve — mandatory before finishing

Append a run entry to `.video-studio/learnings.md` (template inside). For each problem that could happen again pick the strongest fix:
1. Fix the cause in config (`defaults.json`, the project's `video.json`) or, when the user maintains this plugin, in its scripts.
2. Otherwise add a short imperative rule to **Rules** in `learnings.md`; house rules about audience / voice / sources go into `profile.md`.
3. A step of this file was wrong or missing → propose the edit to the user (the plugin may be shared; do not edit it silently).

## Always

- No fabricated facts, results or features; nothing cancelled or unfinished presented as done.
- Personal data stays off camera: passwords, notifications, chat heads, wallpapers, real customer records.
- Public videos say the voice is synthetic; check the voice model's and music's licence before monetised use.
- Long jobs (TTS batches, recordings, renders) run in the background; never block the conversation for minutes.
- Write every file as UTF-8 (on Windows never through PowerShell 5.1 `Set-Content` / `Out-File` defaults); use forward slashes in paths inside `video.json` and scenarios.

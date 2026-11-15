# video-studio

A Claude Code plugin that makes narrated videos end to end: brief → facts → script (approval gate) → TTS voice-over (listening gate) → footage → ffmpeg compose with subtitles → QA by eye → hand-over → learnings.

| Video type | Footage | Subtitles |
|---|---|---|
| Product / sprint / feature demo | Android screen recording (adb) or web recording (Playwright), driven line by line by the narration | band under the screen, or overlay |
| Explainer / tutorial | HTML slides, images, or scenes from your own renderer (Remotion…) | overlay |
| Vertical short | any of the above at 1080 × 1920 | overlay |
| Report / walkthrough | HTML slides (numbers, charts) + short recordings | overlay |

## Install

```
/plugin marketplace add Mystogan602/video-studio
/plugin install video-studio@video-studio
```

Then run `/video-studio <what the video is about>`. Updates: `/plugin marketplace update video-studio`.

Works on **Windows, macOS and Linux**. Requirements: `ffmpeg` + `ffprobe` on PATH, Python ≥ 3.9, internet for the one-time voice install. Optional: Node ≥ 18 (Android and web recording, HTML slides) + `npm install` in `skills/video-studio/scripts` (web recording, HTML slides; downloads Chromium); `adb` (Android recording); another TTS engine (see below). Install commands per OS: `skills/video-studio/reference/setup.md`.

## Voices

| Adapter | Good for |
|---|---|
| `vieneu` (default) | offline Vietnamese voices ("Xuân Vĩnh"); installs itself on the first run (~1.3 GB, private folder) |
| `command` | any CLI: Piper, Coqui, `edge-tts` (many languages, online), or a small wrapper around a cloud API |

Any voice can be checked with speech recognition (`tts.py --transcribe`, faster-whisper, installs itself on first use, ~800 MB): it flags lines whose words do not match the script.

Details: `skills/video-studio/reference/adapters/tts.md`.

## Make it yours

Create `.video-studio/` in your workspace (the skill offers to do this from `templates/`):

- `profile.md` — your house rules: audience, who speaks and how, where facts come from, device / account preconditions, clean-up. The skill follows it over its own defaults.
- `defaults.json` — voice, brand, card colours, any other setting.
- `learnings.md` — rules the skill learns from each run (it appends after every video).

## Layout

```
.claude-plugin/          plugin + marketplace manifests
skills/video-studio/
  SKILL.md               the process (core)
  reference/             setup per OS, formats, project format, script writing, QA, adapters/{tts,footage}
  scripts/               tts.py, compose.py, qa.py, setup_tools.py, render_slides.mjs, record/{android.mjs, web.mjs}, defaults.json
  fonts/                 Be Vietnam Pro Bold — default subtitle font (SIL OFL 1.1: licenses/BeVietnamPro-OFL.txt)
  templates/             profile, defaults, learnings, video.json, Android / web scenario and slide examples
```

## License

MIT (`LICENSE`). The bundled Be Vietnam Pro font is under the SIL Open Font License 1.1. Voice models (VieNeu, Whisper) are downloaded on first use under their own licences; check them before monetised use.

## Credits

- The "Cut these AI tells" list in `reference/script-writing.md` is adapted for spoken narration from [blader/humanizer](https://github.com/blader/humanizer) (MIT), which is based on Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing).

## Status

0.1.0 — smoke-tested on **Windows** (ffmpeg 8.1): compose (all four clip kinds, band and overlay subtitles), the `command` and `vieneu` TTS adapters (including the first-run VieNeu install), QA, HTML slides, web recording and Android recording on a real phone. On **Linux** (Ubuntu 24.04 container, ffmpeg 6.1): compose, `command` TTS, QA, HTML slides, web recording, bundled font, uv download. Not run yet: macOS (no machine), the full VieNeu install outside Windows.

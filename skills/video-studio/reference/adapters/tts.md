# TTS adapters

`tts.py` writes one wav per step (`clips/<id>/step<N>.wav`), caches by text + voice + seed, and builds `review/review.html`. Choose the adapter in `video.json` → `voice` (or once in `.video-studio/defaults.json`).

## `vieneu` — local VieNeu-TTS (Vietnamese, CPU, offline) — **the default**

Works with no configuration: the built-in default voice is `{"adapter": "vieneu", "name": "Xuân Vĩnh"}`. On the first narration run `tts.py` calls `scripts/setup_tools.py vieneu`, which:

1. uses `uv` from PATH, or downloads the pinned standalone uv binary from GitHub;
2. creates a private Python 3.11 environment and installs the pinned `vieneu` (+ `truststore`) — ~650 MB, a few minutes;
3. the voice model (~600 MB) downloads from Hugging Face on the first synthesis.

Location: `$VIDEO_STUDIO_HOME`, else `%LOCALAPPDATA%\video-studio` (Windows), `~/Library/Application Support/video-studio` (macOS), `${XDG_DATA_HOME:-~/.local/share}/video-studio` (Linux). Nothing is installed into the system Python. Tell the user before the first run and run it in the background. Reinstall: `python3 <skill>/scripts/setup_tools.py vieneu --force`. Runs on Windows, macOS (Apple Silicon; Intel on macOS 13+) and Linux x64 / arm64, CPU only.

Optional keys: `mode` (`v3turbo`), `temperature` (0.7), `python` (reuse an existing VieNeu environment: `…/Scripts/python.exe` on Windows, `…/bin/python` elsewhere).

- The model loads once per batch (~1 min + ~5 s per line on CPU). An unknown voice name fails with the list of available presets.
- The same sentence always gives the same take; set a step's `seed` to try another.
- A line whose voice similarity to the preset is far below the median is flagged as a likely glitch.
- Preset voices may have unclear training-data provenance: get the author's OK before monetised use.

## `command` — any TTS CLI

```json
"voice": {
  "adapter": "command",
  "name": "piper-vi",
  "command": ["piper", "--model", "D:/voices/vi_VN-vais1000-medium.onnx", "--output_file", "{output}"],
  "textOnStdin": true,
  "outputExtension": "wav"
}
```

Placeholders in `command`: `{text}` (the sentence), `{text_file}` (UTF-8 file holding it), `{output}` (file the command must write, with `outputExtension`). `textOnStdin: true` pipes the sentence to stdin. The result is converted to the project sample rate. Use this for Piper, Coqui, a cloud API wrapped in a small script (OpenAI, ElevenLabs, Google), Microsoft Edge online voices, or a test tone.

Edge voices (many languages, free, internet; `pip install edge-tts`, list with `edge-tts --list-voices`). Unofficial use of a Microsoft service: fine for drafts and internal videos, check terms before public / commercial use.

```json
"command": ["edge-tts", "--voice", "vi-VN-HoaiMyNeural", "--file", "{text_file}", "--write-media", "{output}"],
"outputExtension": "mp3"
```

Test tone:

```json
"command": ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "{output}"]
```

API keys come from the environment; never write them into `video.json`.

## Adding an adapter

Add a `synthesize_<name>(items, voice, project)` function to `tts.py` that writes every `item.output_path`, register it in `ADAPTERS`, and document its config here.

## Transcript check (`--transcribe`, any adapter)

`tts.py <project> --transcribe` runs speech recognition (faster-whisper, CPU) on every line and compares the words it heard with `text` (ignoring punctuation and tone marks). A line gets a `CHECK … heard "…"` flag when a script word is missing, an extra word was heard, or the overall match is below `tts.transcribe.minimumMatch` (0.6, i.e. garbled); the review page gets a "Heard" column. Words the recogniser replaced (digits for spoken numbers, a misheard name) are not flagged on their own. It catches skipped, added or misread words that the speaking-rate and similarity flags miss. Use it before Gate 2 for public videos, and whenever nobody can listen to every line.

- First use installs a private environment (`setup_tools.py whisper`, ~300 MB, same location as VieNeu). The model downloads from Hugging Face on the first run: `small` is ~500 MB.
- Settings: `tts.transcribe.model` (`small`; `base` is faster but weak in Vietnamese, `medium` is more accurate but slower), `language` (`vi`; set `en` etc. for other voices), `minimumMatch`.
- Results are cached per take in `clips/<id>/transcripts.json`; only new takes are recognised again.
- A flag is a hint, not a verdict: the recogniser can write digits for spoken numbers or mishear a brand name. Listen to a flagged line before rewording it.

## Fixing a bad line

| Symptom | Fix |
|---|---|
| Word mispronounced | spell it the way it sounds in `text` (keep the real word in `subtitle`) |
| Number / symbol misread | write it in words in `text` |
| Odd pause or rushed ending | commas, shorter sentences, split the step |
| Glitch (flagged slow / low similarity) | reword slightly or change `seed`, rerun |
| Whole voice too fast / slow | adapter rate setting (`rate`, model parameter) — never speed up the audio afterwards |

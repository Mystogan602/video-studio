# Project format

## Folders

```
<workspace>/
  .video-studio/
    profile.md         house rules (optional)
    defaults.json      settings shared by every video here (optional)
    learnings.md       rules + run log (step 10)
  videos/<slug>/
    video.json         the video: settings + clips + narration
    clips/<id>/
      step<N>.wav      narration (tts.py), tts-manifest.json, transcripts.json (--transcribe)
      raw.mp4          recording clips: the screen recording
      timeline.txt     recording clips: "<step> <seconds from video start>" per line
      step<N>.png      slides clips: rendered slides (render_slides.mjs)
      final.mp4        the composed clip (rendered clips: produced by the external renderer)
    review/review.html listening review page (tts.py)
    out/<output>.mp4   the video, <name>.srt, poster.jpg, segments.json, qa/ (qa.py)
```

Settings merge, later wins: `<skill>/scripts/defaults.json` → nearest `.video-studio/defaults.json` → `video.json`. Objects merge key by key; arrays (like `clips`) are replaced.

## `video.json`

Example: `<skill>/templates/video.example.json`. Top level: `title` (review page, default card title), `output` (default `<folder name>.mp4`), `brand.name` (default title of opening / closing cards), `voice` (`adapters/tts.md`), `clips`, plus any setting below.

### Clip fields

| Field | Kinds | Meaning |
|---|---|---|
| `id` | all | folder name under `clips/`; order in the video = order in the array |
| `kind` | all | `card`, `recording`, `slides`, `rendered` |
| `title` | all | section card text; card subtitle by default |
| `card` | card | `{ "title", "subtitle" }` overrides |
| `sectionCard` | non-card | `false` skips the section card before this clip |
| `crop` | recording | per-clip override of `recording.crop` |
| `steps` | all but rendered | narration lines, in order |

### Step fields

| Field | Meaning |
|---|---|
| `text` | what the voice reads (numbers in words, no symbols the voice misreads) |
| `subtitle` | what the viewer reads, when different (digits, units, quoted UI labels) |
| `seed` | integer; change it to get a different take of the same sentence (VieNeu) |
| `image` | slides: image path relative to the project |
| `html` / `url` | slides: page rendered to `clips/<id>/step<N>.png` by `render_slides.mjs` |
| `pauseAfter` | slides: extra seconds on this slide after the line |

A slides step without an image keeps the previous slide on screen.

## Settings (defaults in `<skill>/scripts/defaults.json`)

| Key | Default | Notes |
|---|---|---|
| `canvas.width/height/frameRate` | 1080 / 1920 / 30 | final video size |
| `subtitles.mode` | `band` | `band` = own strip under the picture; `overlay` = box over the picture |
| `subtitles.bandHeight` | 380 | band mode only; picture height = canvas height − band |
| `subtitles.fontName/fontSize` | Be Vietnam Pro / 64 | the default ships in `<skill>/fonts` (OFL; only font files may live there). Another font must be installed on the composing machine, or libass silently substitutes one — check the QA frames |
| `subtitles.maxCharactersPerLine` × `maxLines` | 30 × 2 | `check` warns above it |
| `subtitles.bottomMargin` | 96 | overlay mode distance from the bottom |
| `cards.*` | dark card | colours, font sizes, timings; `sectionCards` (a 2 s silent card before each non-card clip) on/off |
| `recording.fastForward` | 2.5× gaps ≥ 2 s | silent stretches between narration lines |
| `slides.leadInSeconds/gapSeconds` | 0.3 / 0.5 | timing around each slide's line |
| `audio.loudnessTarget/truePeak` | −16 LUFS / −1.5 dBTP | applied once at merge |
| `tts.slowSpeechRatio/fastSpeechRatio` | 0.6 / 1.6 | outlier flags vs the median speaking rate |
| `tts.transcribe.model/language/minimumMatch` | small / vi / 0.6 | `tts.py --transcribe` (`adapters/tts.md`) |
| `poster.atSeconds` | 1.0 | frame of the final video saved as `out/poster.jpg` |

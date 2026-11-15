"""Synthesize the narration of a video-studio project: one wav per step -> clips/<id>/step<N>.wav.

  tts.py <project> [--clip <id>] [--force] [--transcribe]

Uses video.json "voice" (see reference/adapters/tts.md). A step is re-synthesized only when its text, voice
or seed changed (hash kept in clips/<id>/tts-manifest.json) or with --force. Give a step a new "seed" to get
a different take of the same sentence (VieNeu). Writes review/review.html (an audio player per line) and
prints the lines whose speaking rate is far from the median (likely misread, truncated or glitched).
--transcribe also runs speech recognition (faster-whisper, installed on first use) on every line and flags
the lines whose words do not match the script (skipped, added or misread words); results are cached per take
in clips/<id>/transcripts.json.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import json
import os
import statistics
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from setup_tools import ensure_tool
from video_project import SCRIPTS_DIRECTORY, VideoProject, media_duration, read_json, run_ffmpeg, word_count, write_json

MANIFEST_FILE_NAME = "tts-manifest.json"
TRANSCRIPTS_FILE_NAME = "transcripts.json"
VIENEU_BATCH_SCRIPT = SCRIPTS_DIRECTORY / "tts" / "vieneu_batch.py"
TRANSCRIBE_BATCH_SCRIPT = SCRIPTS_DIRECTORY / "tts" / "transcribe_batch.py"
SEED_MODULO = 2 ** 31


class NarrationItem:
    def __init__(self, clip_id: str, step_number: int, step: dict, output_path: Path, voice: dict):
        self.clip_id = clip_id
        self.step_number = step_number
        self.text = step["text"]
        self.subtitle = step.get("subtitle", step["text"])
        self.output_path = output_path
        self.seed = int(step.get("seed", stable_seed(self.text)))
        voice_identity = json.dumps({key: voice.get(key) for key in ("adapter", "name", "rate", "temperature", "mode", "command")}, sort_keys=True)
        self.content_hash = hashlib.sha1(f"{voice_identity}|{self.seed}|{self.text}".encode("utf-8")).hexdigest()
        self.similarity = None
        self.duration = 0.0
        self.heard = None
        self.transcript_comparison = None

    @property
    def manifest_key(self) -> str:
        return f"step{self.step_number}"


def stable_seed(text: str) -> int:
    """Same sentence -> same seed -> same take; rewording a sentence gives a new take."""
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16) % SEED_MODULO


def convert_to_wav(source_path: Path, output_path: Path, sample_rate: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-i", str(source_path), "-ar", str(sample_rate), "-ac", "1", str(output_path)], output_path.parent)


def synthesize_vieneu(items: list, voice: dict, project: VideoProject) -> None:
    """Local VieNeu-TTS batch: the model loads once for every line. Installs VieNeu on first use."""
    python = voice.get("python") or str(ensure_tool("vieneu"))
    with tempfile.TemporaryDirectory() as temporary_directory:
        request_path, response_path = Path(temporary_directory) / "request.json", Path(temporary_directory) / "response.json"
        write_json(request_path, {
            "mode": voice["mode"], "voice": voice["name"], "temperature": voice["temperature"],
            "items": [{"text": item.text, "outputPath": item.output_path.as_posix(), "seed": item.seed} for item in items],
        })
        result = subprocess.run([python, str(VIENEU_BATCH_SCRIPT), str(request_path), str(response_path)])
        if result.returncode != 0:
            raise SystemExit("VieNeu batch failed (see its output above)")
        response = read_json(response_path)
    if not response["voiceAvailable"]:
        raise SystemExit(f"VieNeu has no voice {voice['name']!r}; available: {', '.join(response['availableVoices'])}")
    similarity_by_path = {Path(entry["outputPath"]).resolve(): entry["similarity"] for entry in response["results"]}
    for item in items:
        item.similarity = similarity_by_path.get(item.output_path.resolve())


def synthesize_command(items: list, voice: dict, project: VideoProject) -> None:
    """Any TTS CLI: voice.command is an argument list with {text}, {text_file} and {output} placeholders."""
    if not voice.get("command"):
        raise SystemExit("voice.command is required for the command adapter (see reference/adapters/tts.md)")
    sample_rate = int(project.settings["audio"]["sampleRate"])
    output_extension = voice.get("outputExtension", "wav")
    with tempfile.TemporaryDirectory() as temporary_directory:
        for item in items:
            text_path = Path(temporary_directory) / "line.txt"
            media_path = Path(temporary_directory) / f"line.{output_extension}"
            text_path.write_text(item.text, encoding="utf-8")
            placeholders = {"text": item.text, "text_file": str(text_path), "output": str(media_path)}
            command = [argument.format(**placeholders) for argument in voice["command"]]
            standard_input = item.text if voice.get("textOnStdin") else None
            result = subprocess.run(command, input=standard_input, text=True, encoding="utf-8")
            if result.returncode != 0 or not media_path.exists():
                raise SystemExit(f"TTS command failed on clip {item.clip_id} step {item.step_number}: {' '.join(command)}")
            convert_to_wav(media_path, item.output_path, sample_rate)
            print(f"  {item.clip_id}/step{item.step_number}", flush=True)


ADAPTERS = {"vieneu": synthesize_vieneu, "command": synthesize_command}


def collect_items(project: VideoProject, voice: dict, clip_filter) -> list:
    items = []
    for clip in project.clips:
        if clip_filter and clip["id"] != clip_filter:
            continue
        for step_number, step in enumerate(clip.get("steps", []), start=1):
            items.append(NarrationItem(clip["id"], step_number, step, project.step_audio_path(clip["id"], step_number), voice))
    return items


def load_manifest(project: VideoProject, clip_id: str) -> dict:
    manifest_path = project.clip_directory(clip_id) / MANIFEST_FILE_NAME
    return read_json(manifest_path) if manifest_path.exists() else {}


def is_up_to_date(project: VideoProject, item: NarrationItem) -> bool:
    return item.output_path.exists() and load_manifest(project, item.clip_id).get(item.manifest_key) == item.content_hash


def save_manifests(project: VideoProject, items: list) -> None:
    for clip_id in sorted({item.clip_id for item in items}):
        manifest = load_manifest(project, clip_id)
        for item in items:
            if item.clip_id == clip_id:
                manifest[item.manifest_key] = item.content_hash
        write_json(project.clip_directory(clip_id) / MANIFEST_FILE_NAME, manifest)


def spoken_words(text: str) -> list:
    """Lowercase words without punctuation, as written (diacritics kept)."""
    text = unicodedata.normalize("NFC", text.lower())
    return "".join(character if character.isalnum() else " " for character in text).split()


def without_diacritics(word: str) -> str:
    decomposed = unicodedata.normalize("NFD", word.replace("đ", "d"))
    return "".join(character for character in decomposed if unicodedata.category(character) != "Mn")


class TranscriptComparison:
    """Script vs heard words, compared without diacritics (recognisers often get tone marks wrong).

    missing / extra = script words with no counterpart in what was heard, and the reverse: the voice skipped or
    added them. Replaced words are not counted there, because they are mostly recognition errors (digits written
    for spoken numbers, a misheard brand name); a line where too much was replaced falls below minimumMatch.
    """

    def __init__(self, script_text: str, heard_text: str):
        script_words, heard_words = spoken_words(script_text), spoken_words(heard_text)
        matcher = difflib.SequenceMatcher(
            None, [without_diacritics(word) for word in script_words], [without_diacritics(word) for word in heard_words], autojunk=False)
        self.match = matcher.ratio()
        self.missing_words, self.extra_words = [], []
        for operation, script_start, script_end, heard_start, heard_end in matcher.get_opcodes():
            if operation == "delete":
                self.missing_words += script_words[script_start:script_end]
            if operation == "insert":
                self.extra_words += heard_words[heard_start:heard_end]

    def problems(self, minimum_match: float) -> list:
        problems = []
        if self.missing_words:
            problems.append(f"missing \"{' '.join(self.missing_words)}\"")
        if self.extra_words:
            problems.append(f"extra \"{' '.join(self.extra_words)}\"")
        if self.match < minimum_match:
            problems.append(f"match {self.match:.2f}")
        return problems


def transcribe(project: VideoProject, items: list) -> None:
    """Fill item.heard / item.transcript_match; only takes without a cached transcript are recognised."""
    settings = project.settings["tts"]["transcribe"]
    caches = {clip_id: load_transcripts(project, clip_id) for clip_id in {item.clip_id for item in items}}
    pending_items = [item for item in items if caches[item.clip_id].get(item.manifest_key, {}).get("hash") != item.content_hash]
    if pending_items:
        print(f"transcribing {len(pending_items)} lines with faster-whisper ({settings['model']}, {settings['language']})", flush=True)
        python = str(ensure_tool("whisper"))
        with tempfile.TemporaryDirectory() as temporary_directory:
            request_path, response_path = Path(temporary_directory) / "request.json", Path(temporary_directory) / "response.json"
            write_json(request_path, {
                "model": settings["model"], "language": settings["language"],
                "items": [{"audioPath": item.output_path.as_posix()} for item in pending_items],
            })
            if subprocess.run([python, str(TRANSCRIBE_BATCH_SCRIPT), str(request_path), str(response_path)]).returncode != 0:
                raise SystemExit("transcription failed (see its output above)")
            heard_by_path = {Path(entry["audioPath"]).resolve(): entry["heard"] for entry in read_json(response_path)["results"]}
        for item in pending_items:
            caches[item.clip_id][item.manifest_key] = {"hash": item.content_hash, "heard": heard_by_path[item.output_path.resolve()]}
        for clip_id, cache in caches.items():
            write_json(project.clip_directory(clip_id) / TRANSCRIPTS_FILE_NAME, cache)
    for item in items:
        item.heard = caches[item.clip_id][item.manifest_key]["heard"]
        item.transcript_comparison = TranscriptComparison(item.text, item.heard)


def load_transcripts(project: VideoProject, clip_id: str) -> dict:
    transcripts_path = project.clip_directory(clip_id) / TRANSCRIPTS_FILE_NAME
    return read_json(transcripts_path) if transcripts_path.exists() else {}


def flag_outliers(items: list, tts_settings: dict) -> dict:
    """{item: [reasons]} for lines whose words/second or voice similarity is far from the median."""
    rates = {item: word_count(item.text) / max(item.duration, 0.01) for item in items}
    median_rate = statistics.median(rates.values()) if rates else 0
    similarities = [item.similarity for item in items if item.similarity is not None]
    median_similarity = statistics.median(similarities) if similarities else None
    flags = {}
    for item in items:
        reasons = []
        if median_rate and rates[item] < median_rate * float(tts_settings["slowSpeechRatio"]):
            reasons.append(f"slow ({rates[item]:.1f} words/s vs median {median_rate:.1f}) — likely misread or long silence")
        if median_rate and rates[item] > median_rate * float(tts_settings["fastSpeechRatio"]):
            reasons.append(f"fast ({rates[item]:.1f} words/s vs median {median_rate:.1f}) — likely truncated")
        drop = float(tts_settings["similarityDropBelowMedian"])
        if median_similarity is not None and item.similarity is not None and item.similarity < median_similarity - drop:
            reasons.append(f"voice similarity {item.similarity:.2f} vs median {median_similarity:.2f} — likely glitch")
        if item.transcript_comparison is not None:
            problems = item.transcript_comparison.problems(float(tts_settings["transcribe"]["minimumMatch"]))
            if problems:
                reasons.append(f"heard \"{item.heard}\" ({', '.join(problems)}) — listen: skipped, added or garbled words?")
        if reasons:
            flags[item] = reasons
    return flags


def write_review_page(project: VideoProject, items: list, flags: dict) -> Path:
    review_path = project.directory / "review" / "review.html"
    is_transcribed = any(item.heard is not None for item in items)
    rows = []
    for item in items:
        audio_source = os.path.relpath(item.output_path, review_path.parent).replace(os.sep, "/")
        subtitle_cell = "" if item.subtitle == item.text else html.escape(item.subtitle)
        heard_cell = f"<td>{html.escape(item.heard or '')}</td>" if is_transcribed else ""
        flag_cell = "<br>".join(html.escape(reason) for reason in flags.get(item, []))
        rows.append(
            f"<tr class=\"{'flagged' if item in flags else ''}\"><td>{item.clip_id}/{item.step_number}</td>"
            f"<td>{html.escape(item.text)}</td><td>{subtitle_cell}</td>{heard_cell}<td>{item.duration:.1f}s</td>"
            f"<td><audio controls preload=\"none\" src=\"{audio_source}\"></audio></td><td>{flag_cell}</td></tr>"
        )
    heard_header = "<th>Heard (speech recognition)</th>" if is_transcribed else ""
    total_seconds = sum(item.duration for item in items)
    page = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Narration review</title><style>"
        "body{font-family:system-ui,sans-serif;margin:24px;background:#fff;color:#111}"
        "table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:8px;vertical-align:top;text-align:left}"
        ".flagged{background:#fff4e5}audio{width:260px}</style></head><body>"
        f"<h1>Narration review — {html.escape(project.settings.get('title', project.directory.name))}</h1>"
        f"<p>{len(items)} lines, {total_seconds:.0f}s of narration. Orange rows were flagged automatically.</p>"
        f"<table><tr><th>Clip/step</th><th>Spoken text</th><th>Subtitle (if different)</th>{heard_header}<th>Length</th><th>Listen</th><th>Flags</th></tr>"
        + "".join(rows) + "</table></body></html>"
    )
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(page, encoding="utf-8")
    return review_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("--clip", help="only this clip id")
    parser.add_argument("--force", action="store_true", help="re-synthesize even unchanged lines")
    parser.add_argument("--transcribe", action="store_true", help="check every line with speech recognition")
    arguments = parser.parse_args()

    project = VideoProject(arguments.project)
    voice = project.settings.get("voice")
    if not voice or voice.get("adapter") not in ADAPTERS:
        raise SystemExit(f"video.json (or .video-studio/defaults.json) needs \"voice\" with adapter one of: {', '.join(ADAPTERS)}")
    items = collect_items(project, voice, arguments.clip)
    pending_items = [item for item in items if arguments.force or not is_up_to_date(project, item)]
    print(f"{len(items)} lines, {len(pending_items)} to synthesize with {voice['adapter']} ({voice.get('name', 'custom command')})")
    if pending_items:
        ADAPTERS[voice["adapter"]](pending_items, voice, project)
        save_manifests(project, pending_items)

    for item in items:
        item.duration = media_duration(item.output_path)
    if arguments.transcribe:
        transcribe(project, items)
    flags = flag_outliers(items, project.settings["tts"])
    review_path = write_review_page(project, items, flags)
    print(f"narration total: {sum(item.duration for item in items):.1f}s — review page: {review_path}")
    for item, reasons in flags.items():
        print(f"  CHECK {item.clip_id}/step{item.step_number}: {'; '.join(reasons)}")


if __name__ == "__main__":
    main()

"""Shared helpers for the video-studio scripts: project loading, config merge, ffmpeg / ffprobe.

A video project is a folder holding video.json. Its settings are merged in this order (later wins):
  scripts/defaults.json  ->  <nearest parent>/.video-studio/defaults.json  ->  <project>/video.json
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
BUILT_IN_DEFAULTS_PATH = SCRIPTS_DIRECTORY / "defaults.json"
# Bundled subtitle font (Be Vietnam Pro, OFL): the same look on every OS, full Vietnamese glyphs.
BUNDLED_FONTS_DIRECTORY = SCRIPTS_DIRECTORY.parent / "fonts"
WORKSPACE_DEFAULTS_RELATIVE_PATH = Path(".video-studio") / "defaults.json"
PROJECT_FILE_NAME = "video.json"
CLIP_KINDS = ("card", "recording", "slides", "rendered")


def deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_workspace_defaults(project_directory: Path):
    for directory in [project_directory, *project_directory.parents]:
        candidate = directory / WORKSPACE_DEFAULTS_RELATIVE_PATH
        if candidate.exists():
            return candidate
    return None


class VideoProject:
    def __init__(self, project_directory: str):
        self.directory = Path(project_directory).resolve()
        project_file = self.directory / PROJECT_FILE_NAME
        if not project_file.exists():
            raise SystemExit(f"missing {project_file}")
        settings = read_json(BUILT_IN_DEFAULTS_PATH)
        workspace_defaults = find_workspace_defaults(self.directory)
        if workspace_defaults is not None:
            settings = deep_merge(settings, read_json(workspace_defaults))
        self.settings = deep_merge(settings, read_json(project_file))
        self.clips_directory = self.directory / "clips"
        self.output_directory = self.directory / "out"

    @property
    def clips(self) -> list:
        return self.settings.get("clips", [])

    def clip(self, clip_id: str) -> dict:
        for clip in self.clips:
            if clip["id"] == clip_id:
                return clip
        raise SystemExit(f"no clip with id {clip_id!r} in {self.directory / PROJECT_FILE_NAME}")

    def clip_directory(self, clip_id: str) -> Path:
        return self.clips_directory / clip_id

    def step_audio_path(self, clip_id: str, step_number: int) -> Path:
        return self.clip_directory(clip_id) / f"step{step_number}.wav"

    @property
    def output_name(self) -> str:
        return self.settings.get("output") or f"{self.directory.name}.mp4"

    @property
    def canvas_width(self) -> int:
        return int(self.settings["canvas"]["width"])

    @property
    def canvas_height(self) -> int:
        return int(self.settings["canvas"]["height"])

    @property
    def uses_subtitle_band(self) -> bool:
        return self.settings["subtitles"]["mode"] == "band"

    @property
    def content_height(self) -> int:
        """Height of the picture area (the canvas minus the subtitle band in band mode)."""
        if self.uses_subtitle_band:
            return self.canvas_height - int(self.settings["subtitles"]["bandHeight"])
        return self.canvas_height


def run_ffmpeg(arguments: list, working_directory: Path) -> None:
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *arguments]
    result = subprocess.run(command, cwd=working_directory)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg failed in {working_directory}:\n{' '.join(map(str, command))}")


def media_duration(path: Path) -> float:
    output = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(output.stdout.strip())


def has_audio_stream(path: Path) -> bool:
    output = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return output.stdout.strip() != ""


def ffmpeg_color(hex_color: str) -> str:
    """'#RRGGBB' -> '0xRRGGBB' (safe inside a filtergraph)."""
    return "0x" + hex_color.lstrip("#")


def filtergraph_path(path: Path) -> str:
    """Absolute path as a quoted filter option value: forward slashes, ':' escaped (Windows drive letters)."""
    escaped = path.resolve().as_posix().replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
    return f"'{escaped}'"


def subtitles_filter(subtitle_file_name: str) -> str:
    """libass subtitles filter that also loads the bundled fonts (system fonts stay available)."""
    return f"subtitles={subtitle_file_name}:fontsdir={filtergraph_path(BUNDLED_FONTS_DIRECTORY)}"


def ass_color(hex_color: str, alpha: int = 0) -> str:
    """'#RRGGBB' -> ASS '&HAABBGGRR' (alpha 0 = opaque, 255 = transparent)."""
    value = hex_color.lstrip("#")
    red, green, blue = value[0:2], value[2:4], value[4:6]
    return f"&H{alpha:02X}{blue}{green}{red}".upper()


def word_count(text: str) -> int:
    return len(text.split())

"""Compose a narrated video from a video-studio project (see reference/project-format.md).

  compose.py <project> check        validate video.json + inputs (no rendering)
  compose.py <project> status       per clip: narration, footage and final clip present / stale / missing + next step
  compose.py <project> clip <id>    build clips/<id>/final.mp4
  compose.py <project> merge        section cards + every clips/<id>/final.mp4 -> out/<output>, out/<name>.srt,
                                    out/poster.jpg, out/segments.json
  compose.py <project> all          every clip + merge

Clip kinds:
  card       narrated title card (opening, closing, chapter); lines play one after another
  recording  clips/<id>/raw.mp4 + timeline.txt ("<step> <seconds from video start>" per line);
             silent stretches between narration lines are fast-forwarded
  slides     one image per step (step "image", else clips/<id>/step<N>.png, else the previous image)
  rendered   clips/<id>/final.mp4 made by an external renderer (narration already inside); only merged here
"""
from __future__ import annotations

import sys
from pathlib import Path

from tts import collect_items, is_up_to_date
from video_project import (
    CLIP_KINDS, PROJECT_FILE_NAME, VideoProject, ass_color, ffmpeg_color, has_audio_stream, media_duration, run_ffmpeg,
    subtitles_filter, write_json,
)

SUBTITLE_FILE_NAME = "subtitles.ass"
SUBTITLE_STYLE_NAME = "Default"
CARD_TEXT_FILE_NAME = "card.ass"
SECTION_CARD_FILE_NAME = "section-card.mp4"
FINAL_CLIP_FILE_NAME = "final.mp4"
POSTER_FILE_NAME = "poster.jpg"
POSTER_JPEG_QUALITY = "2"  # ffmpeg -q:v scale: 2 = near-lossless, 31 = worst
SUBTITLE_END_GAP_SECONDS = 0.05
OVERLAY_BOX_ALPHA = 0x60
BOX_PADDING = 14
VIDEO_ENCODING = ["-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p"]
AUDIO_BITRATE = "160k"


class Composer:
    def __init__(self, project: VideoProject):
        self.project = project
        self.settings = project.settings
        self.frame_rate = int(self.settings["canvas"]["frameRate"])
        self.sample_rate = int(self.settings["audio"]["sampleRate"])

    # ---------- shared pieces ----------

    def video_encoding(self) -> list:
        return [*VIDEO_ENCODING, "-r", str(self.frame_rate)]

    def audio_encoding(self) -> list:
        return ["-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", str(self.sample_rate), "-ac", "2"]

    def fit_filter(self, width: int, height: int) -> str:
        """Scale into width x height keeping the aspect ratio, pad with the canvas background."""
        background = ffmpeg_color(self.settings["canvas"]["backgroundColor"])
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={background},setsar=1"
        )

    def step_durations(self, clip: dict) -> list:
        return [
            media_duration(self.project.step_audio_path(clip["id"], step_number))
            for step_number in range(1, len(clip["steps"]) + 1)
        ]

    def write_subtitles(self, clip: dict, step_starts: list, step_durations: list) -> None:
        subtitles = self.settings["subtitles"]
        tail_seconds = float(subtitles["tailSeconds"])
        events = []
        for index, step in enumerate(clip["steps"]):
            narration_end = step_starts[index] + step_durations[index] + tail_seconds
            is_last_step = index + 1 == len(step_starts)
            next_start = narration_end if is_last_step else step_starts[index + 1]
            end = min(narration_end, next_start - SUBTITLE_END_GAP_SECONDS)
            events.append((step_starts[index], end, step.get("subtitle", step["text"])))

        if self.project.uses_subtitle_band:
            play_height, alignment, vertical_margin, border_style, back_color = (
                int(subtitles["bandHeight"]), 5, 0, 1, ass_color("#000000"))
        else:
            play_height, alignment, vertical_margin, border_style, back_color = (
                self.project.canvas_height, 2, int(subtitles["bottomMargin"]), 3, ass_color("#000000", OVERLAY_BOX_ALPHA))
        style = AssStyle(
            name=SUBTITLE_STYLE_NAME, font_name=subtitles["fontName"], font_size=int(subtitles["fontSize"]),
            text_color=ass_color(subtitles["textColor"]), back_color=back_color, bold=True,
            border_style=border_style, alignment=alignment, side_margin=int(subtitles["sideMargin"]),
            vertical_margin=vertical_margin,
        )
        dialogues = [f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},{SUBTITLE_STYLE_NAME},{ass_text(text)}" for start, end, text in events]
        write_ass(self.project.clip_directory(clip["id"]) / SUBTITLE_FILE_NAME, self.project.canvas_width, play_height, [style], dialogues)

    def finish_with_subtitles(self, content_label: str) -> str:
        """Filter that turns [content_label] (picture area) into [video] with the clip's subtitles."""
        if self.project.uses_subtitle_band:
            subtitles = self.settings["subtitles"]
            band = f"color=c={ffmpeg_color(subtitles['bandColor'])}:s={self.project.canvas_width}x{subtitles['bandHeight']}:r={self.frame_rate}"
            return f"{band},{subtitles_filter(SUBTITLE_FILE_NAME)}[band];[{content_label}][band]vstack=shortest=1[video]"
        return f"[{content_label}]{subtitles_filter(SUBTITLE_FILE_NAME)}[video]"

    def narration_mix_filter(self, step_starts: list, first_input_index: int) -> str:
        delayed = []
        for offset, start in enumerate(step_starts):
            delay_milliseconds = round(start * 1000)
            delayed.append(
                f"[{first_input_index + offset}:a]adelay={delay_milliseconds}|{delay_milliseconds},"
                f"aresample={self.sample_rate}[narration{offset}]"
            )
        labels = "".join(f"[narration{offset}]" for offset in range(len(step_starts)))
        return ";".join(delayed) + f";{labels}amix=inputs={len(step_starts)}:normalize=0,apad[audio]"

    def narration_inputs(self, clip: dict) -> list:
        return [argument for step_number in range(1, len(clip["steps"]) + 1) for argument in ("-i", f"step{step_number}.wav")]

    def write_card_text(self, card_text_path: Path, play_height: int, title: str, subtitle: str) -> None:
        cards = self.settings["cards"]
        width = self.project.canvas_width
        title_size, subtitle_size = int(cards["titleFontSize"]), int(cards["subtitleFontSize"])
        text_color = ass_color(cards["textColor"])
        common = dict(font_name=self.settings["subtitles"]["fontName"], text_color=text_color, back_color=ass_color("#000000"),
                      bold=True, border_style=1, alignment=5, side_margin=int(self.settings["subtitles"]["sideMargin"]), vertical_margin=0)
        styles = [AssStyle(name="Title", font_size=title_size, **common), AssStyle(name="Subtitle", font_size=subtitle_size, **common)]
        center_x, center_y = width // 2, play_height // 2
        dialogues = []
        if title:
            dialogues.append(f"Dialogue: 0,0:00:00.00,9:59:59.00,Title,{{\\an5\\pos({center_x},{center_y - round(title_size * 0.6)})}}{ass_text(title)}")
        if subtitle:
            dialogues.append(f"Dialogue: 0,0:00:00.00,9:59:59.00,Subtitle,{{\\an5\\pos({center_x},{center_y + round(subtitle_size * 0.9)})}}{ass_text(subtitle)}")
        write_ass(card_text_path, width, play_height, styles, dialogues)

    # ---------- clip kinds ----------

    def compose_clip(self, clip_id: str) -> None:
        clip = self.project.clip(clip_id)
        builders = {
            "card": self.compose_card,
            "recording": self.compose_recording,
            "slides": self.compose_slides,
            "rendered": self.check_rendered,
        }
        builders[clip["kind"]](clip)
        final_path = self.project.clip_directory(clip_id) / FINAL_CLIP_FILE_NAME
        print(f"clip {clip_id} ({clip['kind']}): {media_duration(final_path):.1f}s")

    def compose_card(self, clip: dict) -> None:
        cards = self.settings["cards"]
        clip_directory = self.project.clip_directory(clip["id"])
        step_durations = self.step_durations(clip)
        step_starts, cursor = [], float(cards["leadInSeconds"])
        for duration in step_durations:
            step_starts.append(cursor)
            cursor += duration + float(cards["lineGapSeconds"])
        total_duration = cursor + float(cards["paddingSeconds"])
        self.write_subtitles(clip, step_starts, step_durations)
        card = clip.get("card", {})
        title = card.get("title", self.settings["brand"].get("name") or self.settings.get("title", ""))
        self.write_card_text(clip_directory / CARD_TEXT_FILE_NAME, self.project.content_height, title, card.get("subtitle", clip.get("title", "")))

        background = (
            f"color=c={ffmpeg_color(cards['backgroundColor'])}:s={self.project.canvas_width}x{self.project.content_height}"
            f":r={self.frame_rate}:d={total_duration:.3f},{subtitles_filter(CARD_TEXT_FILE_NAME)}[content]"
        )
        video_filter = f"{background};{self.finish_with_subtitles('content')}"
        run_ffmpeg([
            *self.narration_inputs(clip),
            "-filter_complex", f"{video_filter};{self.narration_mix_filter(step_starts, 0)}",
            "-map", "[video]", "-map", "[audio]", "-t", f"{total_duration:.3f}",
            *self.video_encoding(), *self.audio_encoding(), FINAL_CLIP_FILE_NAME,
        ], clip_directory)

    def compose_recording(self, clip: dict) -> None:
        clip_directory = self.project.clip_directory(clip["id"])
        raw_step_starts = read_timeline(clip_directory / "timeline.txt", len(clip["steps"]))
        step_durations = self.step_durations(clip)
        raw_duration = media_duration(clip_directory / "raw.mp4")
        segments = self.playback_segments(raw_step_starts, step_durations, raw_duration)
        step_starts = [remap_time(start, segments) for start in raw_step_starts]
        output_duration = remap_time(raw_duration, segments)
        self.write_subtitles(clip, step_starts, step_durations)

        crop = {**self.settings["recording"]["crop"], **clip.get("crop", {})}
        crop_filter = (
            f"crop=iw-{crop['left']}-{crop['right']}:ih-{crop['top']}-{crop['bottom']}:{crop['left']}:{crop['top']}"
        )
        part_filters = ";".join(
            f"[raw{index}]trim=start={start:.3f}:end={end:.3f},setpts=(PTS-STARTPTS)/{speed},fps={self.frame_rate}[part{index}]"
            for index, (start, end, speed) in enumerate(segments)
        )
        raw_labels = "".join(f"[raw{index}]" for index in range(len(segments)))
        part_labels = "".join(f"[part{index}]" for index in range(len(segments)))
        video_filter = (
            f"[0:v]fps={self.frame_rate},{crop_filter},split={len(segments)}{raw_labels};{part_filters};"
            f"{part_labels}concat=n={len(segments)}:v=1:a=0,"
            f"{self.fit_filter(self.project.canvas_width, self.project.content_height)}[content];"
            f"{self.finish_with_subtitles('content')}"
        )
        run_ffmpeg([
            "-i", "raw.mp4", *self.narration_inputs(clip),
            "-filter_complex", f"{video_filter};{self.narration_mix_filter(step_starts, 1)}",
            # Explicit length instead of -shortest: ffmpeg 6.x fails "-shortest" + "apad" with ENOSPC.
            "-map", "[video]", "-map", "[audio]", "-t", f"{output_duration:.3f}",
            *self.video_encoding(), *self.audio_encoding(), FINAL_CLIP_FILE_NAME,
        ], clip_directory)

    def playback_segments(self, step_starts: list, step_durations: list, video_duration: float) -> list:
        """[(start, end, speed)] covering the raw video; silent gaps between narration lines play faster."""
        fast_forward = self.settings["recording"]["fastForward"]
        gap_starts = [0.0] + [start + duration + float(fast_forward["marginAfterNarration"]) for start, duration in zip(step_starts, step_durations)]
        gap_ends = [start - float(fast_forward["marginBeforeStep"]) for start in step_starts]
        fast_ranges = [
            (start, end) for start, end in zip(gap_starts, gap_ends) if end - start >= float(fast_forward["minimumSeconds"])
        ]
        segments, cursor = [], 0.0
        for fast_start, fast_end in fast_ranges:
            if fast_start > cursor:
                segments.append((cursor, fast_start, 1.0))
            segments.append((fast_start, fast_end, float(fast_forward["speed"])))
            cursor = fast_end
        segments.append((cursor, video_duration, 1.0))
        return segments

    def compose_slides(self, clip: dict) -> None:
        slides = self.settings["slides"]
        clip_directory = self.project.clip_directory(clip["id"])
        step_durations = self.step_durations(clip)
        image_paths = self.slide_images(clip)
        step_starts, slide_durations, cursor = [], [], 0.0
        for index, (step, narration_duration) in enumerate(zip(clip["steps"], step_durations)):
            lead_in = float(slides["leadInSeconds"]) if index == 0 else 0.0
            step_starts.append(cursor + lead_in)
            slide_duration = lead_in + narration_duration + float(slides["gapSeconds"]) + float(step.get("pauseAfter", 0))
            slide_durations.append(slide_duration)
            cursor += slide_duration
        self.write_subtitles(clip, step_starts, step_durations)

        image_inputs = []
        for image_path, slide_duration in zip(image_paths, slide_durations):
            image_inputs += ["-loop", "1", "-t", f"{slide_duration:.3f}", "-i", str(image_path)]
        fit = self.fit_filter(self.project.canvas_width, self.project.content_height)
        slide_filters = ";".join(f"[{index}:v]fps={self.frame_rate},{fit},format=yuv420p[slide{index}]" for index in range(len(image_paths)))
        slide_labels = "".join(f"[slide{index}]" for index in range(len(image_paths)))
        video_filter = (
            f"{slide_filters};{slide_labels}concat=n={len(image_paths)}:v=1:a=0[content];"
            f"{self.finish_with_subtitles('content')}"
        )
        run_ffmpeg([
            *image_inputs, *self.narration_inputs(clip),
            "-filter_complex", f"{video_filter};{self.narration_mix_filter(step_starts, len(image_paths))}",
            "-map", "[video]", "-map", "[audio]", "-t", f"{cursor:.3f}",
            *self.video_encoding(), *self.audio_encoding(), FINAL_CLIP_FILE_NAME,
        ], clip_directory)

    def slide_images(self, clip: dict) -> list:
        image_paths, previous_image = [], None
        for step_number, step in enumerate(clip["steps"], start=1):
            image_path = self.slide_image(clip, step_number, step) or previous_image
            if image_path is None:
                raise SystemExit(f"clip {clip['id']} step {step_number}: no image (set \"image\" or render clips/{clip['id']}/step{step_number}.png)")
            image_paths.append(image_path)
            previous_image = image_path
        return image_paths

    def slide_image(self, clip: dict, step_number: int, step: dict):
        if "image" in step:
            return (self.project.directory / step["image"]).resolve()
        rendered_path = self.project.clip_directory(clip["id"]) / f"step{step_number}.png"
        return rendered_path if rendered_path.exists() else None

    def check_rendered(self, clip: dict) -> None:
        final_path = self.project.clip_directory(clip["id"]) / FINAL_CLIP_FILE_NAME
        if not final_path.exists():
            raise SystemExit(f"clip {clip['id']} (rendered): {final_path} is missing — run the renderer first")

    # ---------- merge ----------

    def compose_section_card(self, clip: dict, section_number: int) -> Path:
        cards = self.settings["cards"]
        clip_directory = self.project.clip_directory(clip["id"])
        self.write_card_text(clip_directory / CARD_TEXT_FILE_NAME, self.project.canvas_height, f"{section_number:02}", clip.get("title", ""))
        duration = float(cards["sectionCardSeconds"])
        video_source = (
            f"color=c={ffmpeg_color(cards['backgroundColor'])}:s={self.project.canvas_width}x{self.project.canvas_height}"
            f":r={self.frame_rate}:d={duration},{subtitles_filter(CARD_TEXT_FILE_NAME)}"
        )
        run_ffmpeg([
            "-f", "lavfi", "-i", video_source, "-f", "lavfi", "-i", f"anullsrc=r={self.sample_rate}:cl=stereo",
            "-map", "0:v", "-map", "1:a", "-t", str(duration), *self.video_encoding(), *self.audio_encoding(), SECTION_CARD_FILE_NAME,
        ], clip_directory)
        return clip_directory / SECTION_CARD_FILE_NAME

    def merge(self) -> None:
        use_section_cards = bool(self.settings["cards"]["sectionCards"])
        segments, section_number = [], 0
        for clip in self.project.clips:
            final_path = self.project.clip_directory(clip["id"]) / FINAL_CLIP_FILE_NAME
            if not final_path.exists():
                raise SystemExit(f"missing {final_path} (run: compose.py <project> clip {clip['id']})")
            if clip["kind"] != "card" and use_section_cards and clip.get("sectionCard", True):
                section_number += 1
                segments.append({"clip": clip["id"], "kind": "section-card", "path": self.compose_section_card(clip, section_number)})
            segments.append({"clip": clip["id"], "kind": clip["kind"], "path": final_path})

        inputs, video_filters, audio_filters = [], [], []
        fit = self.fit_filter(self.project.canvas_width, self.project.canvas_height)
        next_input_index = 0
        for segment_index, segment in enumerate(segments):
            segment["duration"] = media_duration(segment["path"])
            inputs += ["-i", str(segment["path"])]
            video_input_index = next_input_index
            next_input_index += 1
            if has_audio_stream(segment["path"]):
                audio_source = f"[{video_input_index}:a]"
            else:
                inputs += ["-f", "lavfi", "-t", f"{segment['duration']:.3f}", "-i", f"anullsrc=r={self.sample_rate}:cl=stereo"]
                audio_source = f"[{next_input_index}:a]"
                next_input_index += 1
            video_filters.append(f"[{video_input_index}:v]{fit},fps={self.frame_rate},format=yuv420p[video{segment_index}]")
            audio_filters.append(f"{audio_source}aresample={self.sample_rate},aformat=channel_layouts=stereo[audio{segment_index}]")

        audio = self.settings["audio"]
        streams = "".join(f"[video{index}][audio{index}]" for index in range(len(segments)))
        filter_graph = ";".join([
            *video_filters, *audio_filters,
            f"{streams}concat=n={len(segments)}:v=1:a=1[video][joined]",
            f"[joined]loudnorm=I={audio['loudnessTarget']}:TP={audio['truePeak']}:LRA=11,aresample={self.sample_rate}[audio]",
        ])
        self.project.output_directory.mkdir(parents=True, exist_ok=True)
        output_name = self.project.output_name
        run_ffmpeg([
            *inputs, "-filter_complex", filter_graph, "-map", "[video]", "-map", "[audio]",
            *self.video_encoding(), *self.audio_encoding(), "-movflags", "+faststart", output_name,
        ], self.project.output_directory)

        cursor = 0.0
        for segment in segments:
            segment["start"] = round(cursor, 3)
            cursor += segment["duration"]
        subtitle_path = self.write_srt(segments)
        output_duration = media_duration(self.project.output_directory / output_name)
        poster_path = self.write_poster(output_name, output_duration)
        for segment in segments:
            segment["path"] = str(segment["path"])
        write_json(self.project.output_directory / "segments.json", {"output": output_name, "segments": segments})
        print(f"{len(segments)} segments -> out/{output_name} ({output_duration:.1f}s), out/{subtitle_path.name}, out/{poster_path.name}")

    def write_srt(self, segments: list) -> Path:
        """Every clip's subtitles shifted to its place in the final video (rendered clips carry their own)."""
        kinds = {clip["id"]: clip["kind"] for clip in self.project.clips}
        cues = []
        for segment in segments:
            if segment["kind"] == "section-card" or kinds[segment["clip"]] == "rendered":
                continue
            subtitle_path = self.project.clip_directory(segment["clip"]) / SUBTITLE_FILE_NAME
            for start, end, text in read_ass_dialogues(subtitle_path, SUBTITLE_STYLE_NAME):
                cues.append((segment["start"] + start, segment["start"] + end, text))
        blocks = [f"{number}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{text}\n" for number, (start, end, text) in enumerate(cues, start=1)]
        subtitle_path = self.project.output_directory / (Path(self.project.output_name).stem + ".srt")
        subtitle_path.write_text("\n".join(blocks), encoding="utf-8")
        return subtitle_path

    def write_poster(self, output_name: str, output_duration: float) -> Path:
        """One frame of the final video as a thumbnail (poster.atSeconds, clamped into the video)."""
        at_seconds = min(float(self.settings["poster"]["atSeconds"]), max(output_duration - 0.1, 0.0))
        run_ffmpeg(["-ss", f"{at_seconds:.3f}", "-i", output_name, "-frames:v", "1", "-q:v", POSTER_JPEG_QUALITY, POSTER_FILE_NAME],
                   self.project.output_directory)
        return self.project.output_directory / POSTER_FILE_NAME


# ---------- validation ----------

def check_project(project: VideoProject, inputs_required: bool = False) -> bool:
    """Validate video.json. With inputs_required (before composing), missing narration / recordings are errors."""
    errors, warnings = [], []
    missing_inputs = errors if inputs_required else warnings
    seen_ids = set()
    subtitles = project.settings["subtitles"]
    maximum_characters = int(subtitles["maxCharactersPerLine"]) * int(subtitles["maxLines"])
    for clip in project.clips:
        clip_id = clip.get("id")
        label = f"clip {clip_id}"
        if not clip_id or clip_id in seen_ids:
            errors.append(f"{label}: missing or duplicate id")
        seen_ids.add(clip_id)
        if clip.get("kind") not in CLIP_KINDS:
            errors.append(f"{label}: kind must be one of {', '.join(CLIP_KINDS)}")
            continue
        steps = clip.get("steps", [])
        if not steps and clip["kind"] != "rendered":
            errors.append(f"{label}: no steps")
        for step_number, step in enumerate(steps, start=1):
            if not step.get("text"):
                errors.append(f"{label} step {step_number}: empty text")
                continue
            shown = step.get("subtitle", step["text"])
            if len(shown) > maximum_characters:
                warnings.append(f"{label} step {step_number}: subtitle {len(shown)} chars > {maximum_characters} (more than {subtitles['maxLines']} lines) — split the step or add a shorter \"subtitle\"")
            if clip["kind"] != "rendered" and not project.step_audio_path(clip_id, step_number).exists():
                missing_inputs.append(f"{label} step {step_number}: no narration yet (run tts.py)")
        clip_directory = project.clip_directory(clip_id)
        if clip["kind"] == "recording":
            for required_file in ("raw.mp4", "timeline.txt"):
                if not (clip_directory / required_file).exists():
                    missing_inputs.append(f"{label}: {required_file} not recorded yet")
        if clip["kind"] == "slides":
            for step_number, step in enumerate(steps, start=1):
                if "image" in step and not (project.directory / step["image"]).exists():
                    errors.append(f"{label} step {step_number}: image {step['image']} not found")
        if clip["kind"] == "rendered" and not (clip_directory / FINAL_CLIP_FILE_NAME).exists():
            missing_inputs.append(f"{label}: rendered final.mp4 not produced yet")
    for message in errors:
        print(f"ERROR   {message}")
    for message in warnings:
        print(f"warning {message}")
    print(f"{len(project.clips)} clips, {len(errors)} errors, {len(warnings)} warnings")
    return not errors


# ---------- status ----------

def newest_modification_time(paths: list) -> float:
    return max((path.stat().st_mtime for path in paths if path.exists()), default=0.0)


def footage_state(project: VideoProject, clip: dict) -> tuple:
    """(label, is_ready, input files) of a clip's picture source."""
    clip_directory = project.clip_directory(clip["id"])
    if clip["kind"] == "recording":
        files = [clip_directory / "raw.mp4", clip_directory / "timeline.txt"]
        is_ready = all(path.exists() for path in files)
        return ("recorded" if is_ready else "NOT RECORDED"), is_ready, files
    if clip["kind"] == "slides":
        files = [
            project.directory / step["image"] if "image" in step else clip_directory / f"step{step_number}.png"
            for step_number, step in enumerate(clip.get("steps", []), start=1)
            if "image" in step or "html" in step or "url" in step
        ]
        present = sum(path.exists() for path in files)
        return f"{present}/{len(files)} slides", present == len(files), files
    return "-", True, []


def final_clip_state(clip: dict, final_path: Path, input_time: float) -> tuple:
    """(label, is_ready); a final clip older than any of its inputs is stale (rendered clips: existence only)."""
    if not final_path.exists():
        return "MISSING", False
    if clip["kind"] != "rendered" and final_path.stat().st_mtime < input_time:
        return "STALE (inputs changed)", False
    return f"{media_duration(final_path):.1f}s", True


def print_status(project: VideoProject) -> None:
    """Files on disk are the truth: what exists, what is stale, and the next command to run."""
    project_file_time = (project.directory / PROJECT_FILE_NAME).stat().st_mtime
    voice = project.settings.get("voice", {})
    next_steps, final_times, are_all_clips_ready = [], [], True
    print(f"{'clip':<10} {'kind':<10} {'narration':<16} {'footage':<14} final")
    for clip in project.clips:
        items = collect_items(project, voice, clip["id"])
        ready_lines = sum(is_up_to_date(project, item) for item in items)
        narration = f"{ready_lines}/{len(items)} lines" if items else "-"
        if ready_lines < len(items):
            next_steps.append(f"tts.py <project> --clip {clip['id']}")
        footage, is_footage_ready, footage_files = footage_state(project, clip)
        if not is_footage_ready:
            next_steps.append(f"footage for clip {clip['id']} (reference/adapters/footage.md)")
        final_path = project.clip_directory(clip["id"]) / FINAL_CLIP_FILE_NAME
        input_time = max(newest_modification_time([item.output_path for item in items] + footage_files), project_file_time)
        final, is_final_ready = final_clip_state(clip, final_path, input_time)
        if is_final_ready:
            final_times.append(final_path.stat().st_mtime)
        else:
            are_all_clips_ready = False
            next_steps.append(f"compose.py <project> clip {clip['id']}" if clip["kind"] != "rendered" else f"render clip {clip['id']}")
        print(f"{clip['id']:<10} {clip['kind']:<10} {narration:<16} {footage:<14} {final}")

    output_path = project.output_directory / project.output_name
    is_output_ready = (
        are_all_clips_ready and output_path.exists() and output_path.stat().st_mtime >= max(final_times + [project_file_time])
    )
    if is_output_ready:
        output_state = f"{media_duration(output_path):.1f}s"
    else:
        output_state = "STALE (a clip changed)" if output_path.exists() else "MISSING"
    print(f"output out/{project.output_name}: {output_state}")
    if next_steps:
        print(f"next: {next_steps[0]}" + (f" (+{len(next_steps) - 1} more)" if len(next_steps) > 1 else ""))
    elif not is_output_ready:
        print("next: compose.py <project> merge")
    else:
        print("next: qa.py <project> (everything is up to date)")


# ---------- ASS helpers ----------

class AssStyle:
    def __init__(self, name: str, font_name: str, font_size: int, text_color: str, back_color: str, bold: bool,
                 border_style: int, alignment: int, side_margin: int, vertical_margin: int):
        # libass draws the BorderStyle 3 (opaque box) background with OutlineColour, so the box colour goes there.
        is_box = border_style == 3
        outline_color = back_color if is_box else "&H00000000"
        outline_size = BOX_PADDING if is_box else 0
        self.line = (
            f"Style: {name},{font_name},{font_size},{text_color},{outline_color},{back_color},{-1 if bold else 0},0,"
            f"{border_style},{outline_size},0,{alignment},{side_margin},{side_margin},{vertical_margin}"
        )


def write_ass(path: Path, play_width: int, play_height: int, styles: list, dialogues: list) -> None:
    header = (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {play_width}\nPlayResY: {play_height}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV\n"
        + "\n".join(style.line for style in styles)
        + "\n\n[Events]\nFormat: Layer, Start, End, Style, Text\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n".join(dialogues) + "\n", encoding="utf-8")


def ass_text(text: str) -> str:
    """Plain text -> ASS: braces would start override tags, a newline becomes a hard line break."""
    return text.replace("{", "(").replace("}", ")").replace("\n", "\\N")


def read_ass_dialogues(path: Path, style_name: str) -> list:
    """[(start, end, text)] of the Dialogue lines in one style, as written by write_ass."""
    if not path.exists():
        return []
    dialogues = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("Dialogue: "):
            continue
        _, start, end, style, text = line[len("Dialogue: "):].split(",", 4)
        if style == style_name:
            dialogues.append((parse_ass_time(start), parse_ass_time(end), text.replace("\\N", "\n")))
    return dialogues


def parse_ass_time(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def format_srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}"


def format_ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, centiseconds = divmod(centiseconds, 360_000)
    minutes, centiseconds = divmod(centiseconds, 6_000)
    whole_seconds, centiseconds = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02}:{whole_seconds:02}.{centiseconds:02}"


# ---------- timeline helpers ----------

def read_timeline(timeline_path: Path, expected_steps: int) -> list:
    if not timeline_path.exists():
        raise SystemExit(f"missing {timeline_path} (record the clip first)")
    starts = {}
    for line in timeline_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            step_number, seconds = line.split()
            starts[int(step_number)] = float(seconds)
    missing_steps = [step for step in range(1, expected_steps + 1) if step not in starts]
    if missing_steps:
        raise SystemExit(f"{timeline_path}: no start time for steps {missing_steps} ({expected_steps} narration lines)")
    return [starts[step] for step in range(1, expected_steps + 1)]


def remap_time(raw_time: float, segments: list) -> float:
    """Raw video time -> output time after fast-forwarding."""
    output_time = 0.0
    for start, end, speed in segments:
        if raw_time <= start:
            break
        output_time += (min(raw_time, end) - start) / speed
    return output_time


def main(arguments: list) -> None:
    if len(arguments) < 2:
        raise SystemExit(__doc__)
    project = VideoProject(arguments[0])
    command = arguments[1]
    composer = Composer(project)
    if command == "check":
        sys.exit(0 if check_project(project) else 1)
    if command == "status":
        print_status(project)
        return
    if command == "clip" and len(arguments) == 3:
        composer.compose_clip(arguments[2])
        return
    if command == "all":
        if not check_project(project, inputs_required=True):
            sys.exit(1)
        for clip in project.clips:
            composer.compose_clip(clip["id"])
    if command in ("merge", "all"):
        composer.merge()
        return
    raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

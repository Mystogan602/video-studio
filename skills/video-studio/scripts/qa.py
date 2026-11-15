"""Measure and sample the composed video so it can be judged by eye (run after compose.py merge).

  qa.py <project> [--watch-region x:y:width:height]

Writes out/qa/: contact.png (one frame every few seconds), segment-NN.png (a frame just after each segment
starts), region.png (the watched region at 1 fps, e.g. where a system toast could cover the app) and report.md
(duration, resolution, loudness, true peak, per-segment lengths).
"""
from __future__ import annotations

import argparse
import math
import re
import subprocess
from pathlib import Path

from video_project import VideoProject, media_duration, read_json, run_ffmpeg

CONTACT_SHEET_COLUMNS = 8
CONTACT_SHEET_TARGET_FRAMES = 48
CONTACT_SHEET_MINIMUM_INTERVAL_SECONDS = 2.0
CONTACT_THUMBNAIL_WIDTH = 270
SEGMENT_FRAME_OFFSET_SECONDS = 0.5
REGION_SHEET_COLUMNS = 20
REGION_THUMBNAIL_WIDTH = 216
LOUDNESS_TOLERANCE_LU = 2.0


def video_resolution(path: Path) -> str:
    output = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
        capture_output=True, text=True, check=True,
    )
    return output.stdout.strip()


def measure_loudness(path: Path) -> dict:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    summary = result.stderr[result.stderr.rfind("Summary:"):]
    integrated = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    true_peak = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    return {
        "integrated": float(integrated.group(1)) if integrated else None,
        "truePeak": float(true_peak.group(1)) if true_peak else None,
    }


def write_contact_sheet(video_path: Path, qa_directory: Path, duration: float) -> float:
    interval = max(CONTACT_SHEET_MINIMUM_INTERVAL_SECONDS, duration / CONTACT_SHEET_TARGET_FRAMES)
    rows = max(1, math.ceil(duration / interval / CONTACT_SHEET_COLUMNS))
    run_ffmpeg([
        "-i", str(video_path), "-vf", f"fps=1/{interval:.3f},scale={CONTACT_THUMBNAIL_WIDTH}:-1,tile={CONTACT_SHEET_COLUMNS}x{rows}",
        "-frames:v", "1", "contact.png",
    ], qa_directory)
    return interval


def write_segment_frames(video_path: Path, qa_directory: Path, segments: list) -> None:
    for index, segment in enumerate(segments, start=1):
        run_ffmpeg([
            "-ss", f"{segment['start'] + SEGMENT_FRAME_OFFSET_SECONDS:.3f}", "-i", str(video_path),
            "-frames:v", "1", f"segment-{index:02}.png",
        ], qa_directory)


def write_region_sheet(video_path: Path, qa_directory: Path, region: str, duration: float) -> None:
    x, y, width, height = region.split(":")
    rows = max(1, math.ceil(duration / REGION_SHEET_COLUMNS))
    run_ffmpeg([
        "-i", str(video_path),
        "-vf", f"fps=1,crop={width}:{height}:{x}:{y},scale={REGION_THUMBNAIL_WIDTH}:-1,tile={REGION_SHEET_COLUMNS}x{rows}",
        "-frames:v", "1", "region.png",
    ], qa_directory)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("--watch-region", help="x:y:width:height to sample at 1 fps (overlays, toasts, notifications)")
    arguments = parser.parse_args()

    project = VideoProject(arguments.project)
    video_path = project.output_directory / project.output_name
    if not video_path.exists():
        raise SystemExit(f"missing {video_path} (run compose.py <project> merge)")
    qa_directory = project.output_directory / "qa"
    qa_directory.mkdir(parents=True, exist_ok=True)

    duration = media_duration(video_path)
    segments_path = project.output_directory / "segments.json"
    segments = read_json(segments_path)["segments"] if segments_path.exists() else []
    loudness = measure_loudness(video_path)
    interval = write_contact_sheet(video_path, qa_directory, duration)
    write_segment_frames(video_path, qa_directory, segments)
    if arguments.watch_region:
        write_region_sheet(video_path, qa_directory, arguments.watch_region, duration)

    target = float(project.settings["audio"]["loudnessTarget"])
    lines = [
        f"# QA — {video_path.name}", "",
        f"- Duration: {duration:.1f}s ({duration / 60:.1f} min)",
        f"- Resolution: {video_resolution(video_path)} (expected {project.canvas_width}x{project.canvas_height})",
        f"- Loudness: {loudness['integrated']} LUFS (target {target}) · true peak {loudness['truePeak']} dBFS",
        f"- Contact sheet: contact.png (one frame every {interval:.1f}s)",
    ]
    if loudness["integrated"] is not None and abs(loudness["integrated"] - target) > LOUDNESS_TOLERANCE_LU:
        lines.append(f"- **Loudness off target by more than {LOUDNESS_TOLERANCE_LU} LU**")
    if arguments.watch_region:
        lines.append(f"- Watched region {arguments.watch_region}: region.png (1 fps)")
    lines += ["", "| # | Clip | Kind | Starts | Length | Frame |", "|---|---|---|---|---|---|"]
    for index, segment in enumerate(segments, start=1):
        lines.append(f"| {index} | {segment['clip']} | {segment['kind']} | {segment['start']:.1f}s | {segment['duration']:.1f}s | segment-{index:02}.png |")
    report_path = qa_directory / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n-> {report_path}")


if __name__ == "__main__":
    main()

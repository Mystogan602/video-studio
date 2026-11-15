"""One-time install of the private Python environments the scripts need (tts.py calls it automatically).

  setup_tools.py vieneu [--force]     VieNeu-TTS, the default voice ("vieneu" adapter)
  setup_tools.py whisper [--force]    faster-whisper, for tts.py --transcribe

Prints the environment's python path. Each tool goes into <tools home>/<tool>-env, where <tools home> is
$VIDEO_STUDIO_HOME, else %LOCALAPPDATA%\\video-studio (Windows), ~/Library/Application Support/video-studio (macOS)
or ${XDG_DATA_HOME:-~/.local/share}/video-studio (Linux). Nothing goes into the system Python: uv (from PATH, or a
standalone binary downloaded into <tools home>/uv) creates a Python 3.11 environment and installs the pinned packages.
Models download from Hugging Face on first use.
"""
from __future__ import annotations

import os
import platform
import shutil
import ssl
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

PYTHON_VERSION = "3.11"
UV_VERSION = "0.13.1"
READY_MARKER_FILE_NAME = ".video-studio-ready"
IS_WINDOWS = os.name == "nt"
IS_MACOS = sys.platform == "darwin"
TOOLS_FOLDER_NAME = "video-studio"

# Tool -> pinned packages and the size to announce before the first install.
TOOLS = {
    "vieneu": {
        "packages": ["vieneu==3.8.3", "truststore"],
        "announce": "~650 MB, a few minutes; the voice model (~600 MB) downloads on first use",
    },
    "whisper": {
        "packages": ["faster-whisper==1.2.1", "truststore"],
        "announce": "~300 MB, a minute or two; the speech model (~500 MB for 'small') downloads on first use",
    },
}


def tools_home() -> Path:
    if os.environ.get("VIDEO_STUDIO_HOME"):
        return Path(os.environ["VIDEO_STUDIO_HOME"])
    if IS_WINDOWS and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / TOOLS_FOLDER_NAME
    if IS_MACOS:
        return Path.home() / "Library" / "Application Support" / TOOLS_FOLDER_NAME
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / TOOLS_FOLDER_NAME


def environment_directory(tool: str) -> Path:
    return tools_home() / f"{tool}-env"


def environment_python(tool: str) -> Path:
    return environment_directory(tool) / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def ready_marker_text(tool: str) -> str:
    """The marker holds the pinned package list, so changing a pin triggers a reinstall."""
    return " ".join(TOOLS[tool]["packages"])


def is_ready(tool: str) -> bool:
    marker = environment_directory(tool) / READY_MARKER_FILE_NAME
    return marker.exists() and marker.read_text(encoding="utf-8").strip() == ready_marker_text(tool)


def install_environment() -> dict:
    """Use the operating system's certificate store (works behind TLS-inspecting proxies)."""
    return {**os.environ, "UV_SYSTEM_CERTS": "1"}


def run_step(description: str, command: list) -> None:
    print(f"[video-studio] {description}", flush=True)
    result = subprocess.run([str(part) for part in command], env=install_environment())
    if result.returncode != 0:
        raise SystemExit(f"[video-studio] failed: {' '.join(str(part) for part in command)}")


def uv_release_asset() -> str:
    machine = platform.machine().lower()
    architecture = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
    if IS_WINDOWS:
        return f"uv-{architecture}-pc-windows-msvc.zip"
    if IS_MACOS:
        return f"uv-{architecture}-apple-darwin.tar.gz"
    return f"uv-{architecture}-unknown-linux-gnu.tar.gz"


def extract_uv_binary(archive_path: Path, target_path: Path) -> None:
    binary_name = target_path.name
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            member = next(name for name in archive.namelist() if Path(name).name == binary_name)
            target_path.write_bytes(archive.read(member))
    else:
        with tarfile.open(archive_path) as archive:
            member = next(item for item in archive.getmembers() if Path(item.name).name == binary_name)
            target_path.write_bytes(archive.extractfile(member).read())
    target_path.chmod(0o755)


def download_file(url: str, target_path: Path) -> None:
    """urllib first (OS certificate store on Windows); curl as fallback, e.g. python.org Python on macOS without
    its certificates installed. curl ships with Windows 10+, macOS and most Linux distributions."""
    try:
        with urllib.request.urlopen(url, context=ssl.create_default_context()) as response:
            target_path.write_bytes(response.read())
        return
    except OSError as urllib_error:
        curl = shutil.which("curl")
        if curl is None:
            raise SystemExit(f"[video-studio] could not download {url}: {urllib_error}\n"
                             "Install uv yourself (https://docs.astral.sh/uv/) and rerun.")
        print(f"[video-studio] Python could not download ({urllib_error}); retrying with curl", flush=True)
    if subprocess.run([curl, "--fail", "--location", "--silent", "--show-error", "--output", str(target_path), url]).returncode != 0:
        raise SystemExit(f"[video-studio] could not download {url}\nInstall uv yourself (https://docs.astral.sh/uv/) and rerun.")


def download_uv() -> Path:
    """Standalone uv binary from GitHub."""
    uv_directory = tools_home() / "uv"
    uv_binary = uv_directory / ("uv.exe" if IS_WINDOWS else "uv")
    if uv_binary.exists():
        return uv_binary
    uv_directory.mkdir(parents=True, exist_ok=True)
    asset = uv_release_asset()
    url = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/{asset}"
    print(f"[video-studio] downloading uv {UV_VERSION} ({asset})", flush=True)
    archive_path = uv_directory / asset
    download_file(url, archive_path)
    extract_uv_binary(archive_path, uv_binary)
    archive_path.unlink()
    return uv_binary


def find_uv() -> list:
    uv_on_path = shutil.which("uv")
    if uv_on_path:
        return [uv_on_path]
    return [download_uv()]


def ensure_tool(tool: str, force: bool = False) -> Path:
    """Install the tool's environment when missing (or with force) and return its python."""
    if tool not in TOOLS:
        raise SystemExit(f"unknown tool {tool!r}; one of: {', '.join(TOOLS)}")
    if is_ready(tool) and not force:
        return environment_python(tool)
    directory = environment_directory(tool)
    print(f"[video-studio] one-time {tool} install into {directory} ({TOOLS[tool]['announce']})", flush=True)
    tools_home().mkdir(parents=True, exist_ok=True)
    uv = find_uv()
    if directory.exists():
        shutil.rmtree(directory)
    run_step(f"creating a Python {PYTHON_VERSION} environment", [*uv, "venv", "--python", PYTHON_VERSION, directory])
    packages = TOOLS[tool]["packages"]
    run_step(f"installing {' '.join(packages)}", [*uv, "pip", "install", "--python", environment_python(tool), *packages])
    (directory / READY_MARKER_FILE_NAME).write_text(ready_marker_text(tool), encoding="utf-8")
    print(f"[video-studio] {tool} ready", flush=True)
    return environment_python(tool)


if __name__ == "__main__":
    positional = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
    if len(positional) != 1:
        raise SystemExit(__doc__)
    print(ensure_tool(positional[0], force="--force" in sys.argv[1:]))

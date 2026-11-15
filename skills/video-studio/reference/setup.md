# Setup per operating system

Everything runs on Windows 10+, macOS 13+ and Linux (x64 / arm64). Install only what the video needs.

| Tool | Needed for | Windows | macOS (Homebrew) | Debian / Ubuntu |
|---|---|---|---|---|
| ffmpeg + ffprobe (with libass) | always | `winget install Gyan.FFmpeg` | `brew install ffmpeg` | `sudo apt install ffmpeg` |
| Python ≥ 3.9 | always | `winget install Python.Python.3.12` (run as `py`) | preinstalled `python3`, or `brew install python` | preinstalled `python3` |
| Node ≥ 18 | web recording, HTML slides, Android recording | `winget install OpenJS.NodeJS.LTS` | `brew install node` | `sudo apt install nodejs npm` (or nvm) |
| adb | Android recording | `winget install Google.PlatformTools` | `brew install --cask android-platform-tools` | `sudo apt install adb` |

Fedora: `sudo dnf install ffmpeg python3 nodejs android-tools` (ffmpeg from RPM Fusion). Arch: `sudo pacman -S ffmpeg python nodejs npm android-tools`.

After installing, open a new terminal so PATH is refreshed. On Windows `python3` may be the Microsoft Store stub: use `py`.

## One-time steps

- **Playwright** (web recording, HTML slides): `npm install` in `<skill>/scripts` — it also downloads Chromium. On Linux, add Chromium's system libraries once: `sudo npx playwright install-deps chromium` (in the same folder).
- **VieNeu voice**: nothing to do; the first `tts.py` run installs it (~1.3 GB, internet; details in `adapters/tts.md`).
- **Transcript check** (optional): nothing to do; the first `tts.py --transcribe` run installs faster-whisper (~800 MB with the model, internet).
- **Android device**: enable USB debugging, connect, accept the prompt, check with `adb devices`.

## Common problems

| Symptom | Cause / fix |
|---|---|
| `ffmpeg failed … No such filter: 'subtitles'` | ffmpeg built without libass — install the packages above (not a minimal / static build without libass) |
| `CERTIFICATE_VERIFY_FAILED` on macOS during the VieNeu / whisper install | python.org Python without certificates: the installer retries with `curl`; or run `/Applications/Python 3.x/Install Certificates.command` |
| Downloads fail behind a company proxy | set `HTTPS_PROXY`; uv, VieNeu and whisper use the OS certificate store |
| `cannot run adb` | install platform-tools or set `ADB_PATH` to the adb binary |
| Playwright: `Executable doesn't exist` | rerun `npm install` (or `npx playwright install chromium`) in `<skill>/scripts` |

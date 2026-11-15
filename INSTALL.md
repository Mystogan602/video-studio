# Installing video-studio

Step-by-step setup on Windows, macOS and Linux. About 10 minutes plus downloads.

## What you need

| Part | Needed for | Size |
|---|---|---|
| [Claude Code](https://claude.com/claude-code) | always | — |
| ffmpeg + ffprobe (with libass) | always | ~100 MB |
| Python ≥ 3.9 | always | ~100 MB |
| VieNeu voice (installed automatically on the first voice-over) | default Vietnamese voice | ~1.3 GB |
| Node.js ≥ 18 | screen recording, HTML slides | ~100 MB |
| Playwright + Chromium | web recording, HTML slides | ~300 MB |
| adb (Android platform-tools) | recording an Android phone | ~20 MB |
| faster-whisper (installed automatically on first `--transcribe`) | optional speech-recognition check | ~800 MB |

Only the first three are required. Install the rest when a video needs them.

## 1. Install the tools

### Windows 10 / 11

Open **PowerShell** or **Terminal**:

```powershell
winget install Gyan.FFmpeg
winget install Python.Python.3.12
# Optional
winget install OpenJS.NodeJS.LTS        # screen recording, HTML slides
winget install Google.PlatformTools     # Android recording
```

Close and reopen the terminal so the new PATH is used. On Windows run Python as `py` (`python3` may open the Microsoft Store).

### macOS 13+

Install [Homebrew](https://brew.sh) first if you do not have it, then in **Terminal**:

```bash
brew install ffmpeg python
# Optional
brew install node                              # screen recording, HTML slides
brew install --cask android-platform-tools     # Android recording
```

Web or desktop recording on macOS: allow your terminal in **System Settings → Privacy & Security → Screen Recording**.

### Linux

Debian / Ubuntu:

```bash
sudo apt update
sudo apt install ffmpeg python3
# Optional
sudo apt install nodejs npm    # screen recording, HTML slides (or use nvm for a newer Node)
sudo apt install adb           # Android recording
```

Fedora (ffmpeg comes from [RPM Fusion](https://rpmfusion.org/Configuration)): `sudo dnf install ffmpeg python3 nodejs android-tools`

Arch: `sudo pacman -S ffmpeg python nodejs npm android-tools`

## 2. Check the tools

```bash
ffmpeg -version
ffprobe -version
python3 --version      # Windows: py --version
node --version         # only if installed
adb version            # only if installed
```

ffmpeg must have the subtitles filter (libass). The packages above include it. To check:

- Windows: `ffmpeg -hide_banner -filters | findstr subtitles`
- macOS / Linux: `ffmpeg -hide_banner -filters | grep subtitles`

No output means your ffmpeg build lacks libass. Install the package above instead of a minimal or static build.

## 3. Install the plugin in Claude Code

Start Claude Code (`claude`) and run:

```
/plugin marketplace add Mystogan602/video-studio
/plugin install video-studio@video-studio
```

Restart Claude Code if `/video-studio` does not show up in the command list.

## 4. Make your first video

```
/video-studio <what the video is about>
```

Example prompts:

```
/video-studio explainer: how HTTP caching works, for new developers, 3 minutes, landscape
/video-studio demo the web app https://example.com — search and filters, for customers, 2 minutes
/video-studio vertical short: 3 tips for writing commit messages, 45 seconds
/video-studio monthly progress report from CHANGELOG.md, for management, 2 minutes
```

A good prompt says **what** the video is about, the **type** (demo, explainer, short, report), **who** watches it, the **length** and the **format** (landscape or vertical). Claude asks for anything missing.

What happens next:

1. **Script approval:** Claude shows the script and waits. Approve it or ask for changes.
2. **Voice:** the first voice-over installs the VieNeu voice (~1.3 GB, a few minutes, once per machine).
3. **Listening check:** open `review/review.html` in a browser and listen to the lines Claude flags.
4. **Output:** `out/<name>.mp4`, plus `out/<name>.srt` (subtitles) and `out/poster.jpg` (thumbnail).

Making more videos in the same folder? Accept Claude's offer to create `.video-studio/` (house rules, default voice, brand colours) so later prompts can be shorter.

## Optional set-up

**Web recording and HTML slides (Playwright).** The first time a video needs it, Claude gives you the command or runs it with your OK: `npm install` in the plugin's `skills/video-studio/scripts` folder (it also downloads Chromium). On Linux, also run `sudo npx playwright install-deps chromium` in that folder once.

**Android phone.** Turn on **Developer options → USB debugging**, connect the phone, accept the prompt on the phone, then check with `adb devices`. If adb is not on PATH, set `ADB_PATH` to the adb binary.

**Other voices.** The default voice is VieNeu "Xuân Vĩnh" (Vietnamese, offline). VieNeu has 25 Vietnamese preset voices, already downloaded with the model, so switching costs no extra download. Other languages: any TTS command line (Piper, `edge-tts`, a cloud API script) through the `command` adapter. See `skills/video-studio/reference/adapters/tts.md`.

## Update and uninstall

Update:

```
/plugin marketplace update video-studio
```

Uninstall:

```
/plugin uninstall video-studio@video-studio
/plugin marketplace remove video-studio
```

Then delete the voice environments if you want the disk space back:

| OS | Folder |
|---|---|
| Windows | `%LOCALAPPDATA%\video-studio` |
| macOS | `~/Library/Application Support/video-studio` |
| Linux | `~/.local/share/video-studio` (or `$XDG_DATA_HOME/video-studio`) |

The voice models live in the Hugging Face cache (`~/.cache/huggingface/hub`, on Windows `%USERPROFILE%\.cache\huggingface\hub`). Delete only the `models--pnnbao-ump--VieNeu-TTS-*`, `models--OpenMOSS-Team--MOSS-Audio-Tokenizer-*` and `models--Systran--faster-whisper-*` folders; other apps may use the rest.

## Using it with other AI agents

The plugin commands above work in Claude Code only. The skill itself (`skills/video-studio/`, a `SKILL.md` with plain Python / Node scripts) follows the open Agent Skills format, so agents that read `SKILL.md` skills can use it: copy that folder into the agent's skills folder (see the agent's documentation). Agents without skill support can be told: "read `<path>/skills/video-studio/SKILL.md` and follow it".

The agent must be able to run shell commands and read images (for the QA screenshots). Other agents have not been tested yet.

## Problems

| Symptom | Fix |
|---|---|
| `ffmpeg failed … No such filter: 'subtitles'` | ffmpeg without libass: install the package from step 1 |
| `python3` opens the Microsoft Store (Windows) | use `py` |
| `CERTIFICATE_VERIFY_FAILED` during the voice install (macOS) | run `/Applications/Python 3.x/Install Certificates.command`, or let the installer retry with `curl` |
| Downloads fail behind a company proxy | set `HTTPS_PROXY` |
| `cannot run adb` | install platform-tools or set `ADB_PATH` |
| Playwright: `Executable doesn't exist` | run `npm install` (or `npx playwright install chromium`) in `skills/video-studio/scripts` |

More details: `skills/video-studio/reference/setup.md`.

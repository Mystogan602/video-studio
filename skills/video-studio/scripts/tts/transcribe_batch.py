"""
faster-whisper batch transcriber used by tts.py --transcribe; runs inside the environment that
`setup_tools.py whisper` creates. Loads the model ONCE and transcribes every narration wav.

Usage:  <whisper-env python> transcribe_batch.py <request.json> <response.json>

request.json:
  { "model": "small", "language": "vi", "items": [ { "audioPath": "C:/.../step1.wav" } ] }
response.json:
  { "results": [ { "audioPath": "...", "heard": "..." } ] }
"""
import json
import os
import sys
from pathlib import Path

# Windows without Developer Mode cannot symlink in the Hugging Face cache; the copy fallback works, the warning is noise.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

try:
    import truststore

    # Trust the operating system's certificate store (machines behind a TLS-inspecting proxy need it to
    # download the model from Hugging Face). Harmless elsewhere.
    truststore.inject_into_ssl()
except ImportError:
    pass

from faster_whisper import WhisperModel  # noqa: E402

# int8 on CPU: the fastest setting that runs on every machine; accuracy is enough to spot skipped or wrong words.
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
# Greedy decoding: a single pass per line; the check compares against the known script, not a perfect transcript.
BEAM_SIZE = 1


def main(request_path: Path, response_path: Path) -> None:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    model = WhisperModel(request["model"], device=DEVICE, compute_type=COMPUTE_TYPE)
    results = []
    for item in request["items"]:
        segments, _ = model.transcribe(item["audioPath"], language=request["language"], beam_size=BEAM_SIZE,
                                       condition_on_previous_text=False)
        heard = " ".join(segment.text.strip() for segment in segments).strip()
        results.append({"audioPath": item["audioPath"], "heard": heard})
        print(f"  heard {len(results)}/{len(request['items'])}", flush=True)
    response_path.write_text(json.dumps({"results": results}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))

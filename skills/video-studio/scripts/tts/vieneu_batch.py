"""
VieNeu-TTS batch synthesizer used by tts.py (adapter "vieneu"); runs inside the VieNeu environment that
`setup_tools.py vieneu` creates. Adapted from an earlier private pipeline.

Loads the model ONCE, synthesizes every utterance of a video, and for each output measures the
speaker-embedding cosine similarity to the chosen preset voice (an objective voice-consistency check).

Usage:  <vieneu-env python> vieneu_batch.py <request.json> <response.json>

request.json:
  { "mode": "v3turbo", "voice": "Xuân Vĩnh", "temperature": 0.7,
    "items": [ { "text": "...", "outputPath": "C:/.../abc.wav", "seed": 123 } ] }
response.json:
  { "voiceAvailable": true, "availableVoices": ["..."], "results": [ { "outputPath": "...", "similarity": 0.87 } ] }
"""
import json
import sys
from pathlib import Path

import numpy as np

try:
    import truststore

    # Trust the operating system's certificate store (machines behind a TLS-inspecting proxy need it to
    # download the model from Hugging Face). Harmless elsewhere.
    truststore.inject_into_ssl()
except ImportError:
    pass

from vieneu import Vieneu  # noqa: E402


def cosine_similarity(first: np.ndarray, second: np.ndarray) -> float:
    first, second = np.asarray(first).reshape(-1), np.asarray(second).reshape(-1)
    return float(np.dot(first, second) / (np.linalg.norm(first) * np.linalg.norm(second)))


def main(request_path: Path, response_path: Path) -> None:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    tts = Vieneu(mode=request["mode"])
    available_voices = [voice_id for _, voice_id in tts.list_preset_voices()]
    voice = request["voice"]
    response = {
        "voiceAvailable": voice in available_voices,
        "availableVoices": available_voices,
        "results": [],
    }
    if not response["voiceAvailable"]:
        response_path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
        return

    preset_embedding = tts._preset_voices[voice]["speaker_emb"]
    for item in request["items"]:
        # VieNeu samples with NumPy's global RNG: a fixed seed per utterance makes re-renders reproducible.
        np.random.seed(item["seed"])
        audio = tts.infer(item["text"], voice=voice, temperature=request["temperature"], apply_watermark=True)
        Path(item["outputPath"]).parent.mkdir(parents=True, exist_ok=True)
        tts.save(audio, item["outputPath"])
        output_embedding, _ = tts.encode_reference(item["outputPath"], denoise=False)
        response["results"].append({"outputPath": item["outputPath"], "similarity": round(cosine_similarity(preset_embedding, output_embedding), 3)})
        print(f"  {len(response['results'])}/{len(request['items'])}", flush=True)

    response_path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))

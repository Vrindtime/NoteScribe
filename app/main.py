import io
import wave
import json
import os
import base64
import boto3

from piper.voice import PiperVoice, SynthesisConfig
from helper import (
    expand_hyphens,
    make_chunks,
    crossfade_end,
    fadein_start,
    insert_silence,
)

# ----------------------------------------------------------------------
# S3 / model handling
# ----------------------------------------------------------------------
MODEL_PATH = "/tmp/en_US-lessac-medium.onnx"
MODEL_JSON_PATH = "/tmp/en_US-lessac-medium.onnx.json"   # <-- also in /tmp
S3_BUCKET = "note-scribe"
S3_MODEL_KEY = "en_US-lessac-medium.onnx"
S3_JSON_KEY = "en_US-lessac-medium.onnx.json"

s3_client = boto3.client("s3")
voice: PiperVoice | None = None   # global, survives warm invocations


def ensure_model_loaded() -> PiperVoice:
    global voice

    if voice is not None:
        return voice

    # ---------- local dev mode ----------
    local_model = "../models/en_US-lessac-medium.onnx"
    local_json = "../models/en_US-lessac-medium.onnx.json"
    if os.path.exists(local_model) and os.path.exists(local_json):
        print("LOCAL MODE: loading from ../models")
        model_path = local_model
        json_path = local_json
    else:
        # ---------- Lambda / S3 ----------
        os.makedirs("/tmp", exist_ok=True)

        # download ONNX
        if not os.path.exists(MODEL_PATH):
            print(f"Downloading ONNX from s3://{S3_BUCKET}/{S3_MODEL_KEY}")
            s3_client.download_file(S3_BUCKET, S3_MODEL_KEY, MODEL_PATH)

        # download JSON config
        if not os.path.exists(MODEL_JSON_PATH):
            print(f"Downloading JSON from s3://{S3_BUCKET}/{S3_JSON_KEY}")
            s3_client.download_file(S3_BUCKET, S3_JSON_KEY, MODEL_JSON_PATH)

        model_path = MODEL_PATH
        json_path = MODEL_JSON_PATH

    # ---------- load Piper ----------
    voice = PiperVoice.load(model_path, config_path=json_path)
    print("PiperVoice ready")
    return voice


# ----------------------------------------------------------------------
# Lambda entry point
# ----------------------------------------------------------------------
def handler(event, context):

    # === 2. PING MODE (WARM-UP) ===
    if payload.get("text") == "vrindtime-ping-uptime-warm":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "pinged successful", "warm": True})
        }
    
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "POST, OPTIONS"
            },
            "body": ""
        }

    # ---- 1. Load model (once per container) ----
    piper_voice = ensure_model_loaded()

    # === PARSE FROM API GATEWAY PROXY ===
    try:
        body = event.get("body")
        if body is None:
            raise ValueError("Empty request body")
        if isinstance(body, str):
            payload = json.loads(body)
        else:
            payload = body
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in request body")
    except Exception as e:
        raise ValueError(f"Failed to parse body: {e}")

    text = payload.get("text")
    if not text or not isinstance(text, str):
        raise ValueError("Missing or invalid 'text' field (must be a non-empty string)")

    speed_raw = payload.get("speed", 0.8)
    try:
        speed = float(speed_raw)
    except (ValueError, TypeError):
        raise ValueError(f"'speed' must be a number, got {speed_raw!r}")

    pace = payload.get("pace", "writing")

    # ---- 3. Text → words → chunks ----
    words = expand_hyphens(text)
    if not words:
        raise ValueError("No words after hyphen expansion")

    chunks = make_chunks(words)
    base_pause = 1.8 if pace == "typing" else 3.0
    cfg = SynthesisConfig(length_scale=speed)

    # ---- 4. First chunk → WAV header ----
    first_io = io.BytesIO()
    with wave.open(first_io, "wb") as w:
        piper_voice.synthesize_wav(" ".join(chunks[0]), w, syn_config=cfg)
    first_io.seek(0)
    with wave.open(first_io, "rb") as src:
        wav_params = src.getparams()
        first_data = src.readframes(src.getnframes())

    # ---- 5. Master WAV ----
    master_io = io.BytesIO()
    with wave.open(master_io, "wb") as master:
        master.setparams(wav_params)
        master.writeframes(first_data)                # first chunk, no fade

        for chunk in chunks[1:]:
            txt = " ".join(chunk)
            chunk_io = io.BytesIO()
            with wave.open(chunk_io, "wb") as w:
                piper_voice.synthesize_wav(txt, w, syn_config=cfg)

            # optional cross-fade of the *previous* chunk's end
            # crossfade_end(chunk_io, master)

            # pause (silence) between chunks
            pause = base_pause
            if len(chunk) == 2 and all(len(w) > 5 for w in chunk):
                pause += 1.0
            insert_silence(master, pause)

            # fade-in the new chunk
            fadein_start(chunk_io, master)

        # ---- optional final period ----
        if not any(words[-1].endswith(p) for p in ".!?"):
            period_io = io.BytesIO()
            with wave.open(period_io, "wb") as w:
                piper_voice.synthesize_wav(".", w, syn_config=cfg)
            period_io.seek(0)
            crossfade_end(period_io, master)

    # ---- 6. Return base64-encoded WAV (Lambda proxy integration) ----
    master_io.seek(0)
    audio_bytes = master_io.read()

    return {
        "statusCode": 200,
        "headers": {
        "Content-Type": "audio/wav",
        "Content-Disposition": 'attachment; filename="speech.wav"',
    },
        "body": base64.b64encode(audio_bytes).decode("utf-8"),
        "isBase64Encoded": True,
    }

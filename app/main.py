from mangum import Mangum
from fastapi import FastAPI
# , HTTPException, Request
# from fastapi.middleware.cors import CORSMiddleware

# import wave
# import onnxruntime as ort
# from pathlib import Path

# import os
# import boto3
# from schema import TextForm
# from helper import (
#     expand_hyphens,
#     make_chunks,
#     crossfade_end,
#     fadein_start,
#     insert_silence,
# )

# import io
# from fastapi.responses import StreamingResponse
# from piper.voice import PiperVoice, SynthesisConfig

# # ----------- TESTING -------------
# import sys
# print("Python path:", sys.path)
# print("ONNX files:", os.listdir("onnxruntime/capi")[:5])


# MODEL_PATH = "/tmp/en_US-lessac-medium.onnx"
# MODEL_JSON_PATH = "en_US-lessac-medium.onnx.json"

# S3_BUCKET = "note-scribe"
# S3_MODEL_KEY = "en_US-lessac-medium.onnx"

# # === Global state (persists across warm invocations) ===
# model: ort.InferenceSession = None
# voice: PiperVoice = None
# s3_client = boto3.client('s3')

app = FastAPI(title="Note Scribe")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # === Lazy-load model on first request ===
# def ensure_model_loaded() -> PiperVoice:
#     global model, voice
#     if voice is not None:
#         return voice

#     # === LOCAL MODE: local folder ===
#     local_model = "../models/en_US-lessac-medium.onnx"
#     local_json  = "en_US-lessac-medium.onnx.json"

#     if os.path.exists(local_model) and os.path.exists(local_json):
#         print("LOCAL MODE: Loading model from local file system")
#         MODEL_PATH = local_model
#         MODEL_JSON_PATH = local_json
#     else:
#         # === Lambda / real S3 path ===
#         if not os.path.exists(MODEL_PATH):
#             try:
#                 print(f"Downloading from s3://{S3_BUCKET}/{S3_MODEL_KEY}")
#                 s3_client.download_file(S3_BUCKET, S3_MODEL_KEY, MODEL_PATH)
#             except Exception as e:
#                 if "Unable to locate credentials" in str(e):
#                     raise RuntimeError(
#                         "No AWS credentials found. "
#                         "Either:\n"
#                         "  1. Run on Lambda, or\n"
#                         "  2. Place the two files in ./models/ folder, or\n"
#                         "  3. Run: aws configure"
#                     ) from e
#                 raise

#         if not os.path.exists(MODEL_JSON_PATH):
#             s3_client.download_file(S3_BUCKET, MODEL_JSON_PATH, MODEL_JSON_PATH)

#     # Load ONNX + Piper (same for local & Lambda)
#     # model = ort.InferenceSession(MODEL_PATH)
#     voice = PiperVoice.load(MODEL_PATH, config_path=MODEL_JSON_PATH)
#     print("PiperVoice ready")
#     return voice

# # ----------------------------------------------------------------------
# #  Endpoint
# # ----------------------------------------------------------------------
# @app.post("/text-to-speech")
# async def tts(payload: TextForm):
    
#     piper_voice = ensure_model_loaded()

#     words = expand_hyphens(payload.text)
#     if not words:
#         raise HTTPException(400, "No text")

#     chunks = make_chunks(words)

#     base = 1.8 if payload.pace == "typing" else 3.0
#     cfg = SynthesisConfig(length_scale=payload.speed)

#     # ---- first chunk → header ------------------------------------------------
#     first_io = io.BytesIO()
#     with wave.open(first_io, "wb") as w:
#         piper_voice.synthesize_wav(" ".join(chunks[0]), w, syn_config=cfg)
#     first_io.seek(0)

#     with wave.open(first_io, "rb") as src:
#         params = src.getparams()
#         first_data = src.readframes(src.getnframes())

#     # ---- master WAV ---------------------------------------------------------
#     master_io = io.BytesIO()
#     with wave.open(master_io, "wb") as master:
#         master.setparams(params)
#         master.writeframes(first_data)               # first chunk (no fade needed)

#         for chunk in chunks[1:]:
#             txt = " ".join(chunk)
#             chunk_io = io.BytesIO()
#             with wave.open(chunk_io, "wb") as w:
#                 piper_voice.synthesize_wav(txt, w, syn_config=cfg)

#             # ---- cross-fade the *end* of this chunk -----------------------
#             # crossfade_end(chunk_io, master)

#             # ---- pause (silence with fades) -------------------------------
#             pause = base
#             if len(chunk) == 2 and all(len(w) > 5 for w in chunk):
#                 pause += 1.0
#             insert_silence(master, pause)

#             fadein_start(chunk_io, master)

#         # ---- optional final period (separate buffer) --------------------
#         if not any(words[-1].endswith(p) for p in ".!?"):
#             period_io = io.BytesIO()
#             with wave.open(period_io, "wb") as w:
#                 piper_voice.synthesize_wav(".", w, syn_config=cfg)
#             period_io.seek(0)
#             crossfade_end(period_io, master)   # fade the period too

#     master_io.seek(0)
#     response = StreamingResponse(master_io, media_type="audio/wav")
#     del master_io
#     return response

@app.get('/ping')
def ping():
    return {"message":'Pinged Successfully'}

handler = Mangum(app)
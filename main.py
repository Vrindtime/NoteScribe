from schema import TextForm
from helper import *
from workers import WorkerEntrypoint

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from piper.voice import PiperVoice, SynthesisConfig
from fastapi.middleware.cors import CORSMiddleware

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        import asgi

        return await asgi.fetch(app, request, self.env)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
#  Model loading
# ----------------------------------------------------------------------
@app.on_event("startup")
def load_piper():
    app.state.voice = PiperVoice.load(
        "en_US-lessac-medium.onnx",
        config_path="en_US-lessac-medium.onnx.json"
    )
    print("Model loaded.")

# ----------------------------------------------------------------------
#  Endpoint
# ----------------------------------------------------------------------
@app.post("/text-to-speech")
async def tts(payload: TextForm):
    words = expand_hyphens(payload.text)
    if not words:
        raise HTTPException(400, "No text")

    chunks = make_chunks(words)

    base = 1.8 if payload.pace == "typing" else 3.0
    cfg = SynthesisConfig(length_scale=payload.speed)

    # ---- first chunk → header ------------------------------------------------
    first_io = io.BytesIO()
    with wave.open(first_io, "wb") as w:
        app.state.voice.synthesize_wav(" ".join(chunks[0]), w, syn_config=cfg)
    first_io.seek(0)

    with wave.open(first_io, "rb") as src:
        params = src.getparams()
        first_data = src.readframes(src.getnframes())

    # ---- master WAV ---------------------------------------------------------
    master_io = io.BytesIO()
    with wave.open(master_io, "wb") as master:
        master.setparams(params)
        master.writeframes(first_data)               # first chunk (no fade needed)

        for chunk in chunks[1:]:
            txt = " ".join(chunk)
            chunk_io = io.BytesIO()
            with wave.open(chunk_io, "wb") as w:
                app.state.voice.synthesize_wav(txt, w, syn_config=cfg)

            # ---- cross-fade the *end* of this chunk -----------------------
            # crossfade_end(chunk_io, master)

            # ---- pause (silence with fades) -------------------------------
            pause = base
            if len(chunk) == 2 and all(len(w) > 5 for w in chunk):
                pause += 1.0
            insert_silence(master, pause)

            fadein_start(chunk_io, master)

        # ---- optional final period (separate buffer) --------------------
        if not any(words[-1].endswith(p) for p in ".!?"):
            period_io = io.BytesIO()
            with wave.open(period_io, "wb") as w:
                app.state.voice.synthesize_wav(".", w, syn_config=cfg)
            period_io.seek(0)
            crossfade_end(period_io, master)   # fade the period too

    master_io.seek(0)
    return StreamingResponse(master_io, media_type="audio/wav")
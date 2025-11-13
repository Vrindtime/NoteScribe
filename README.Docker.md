### Building and running your application

When you're ready, start your application by running:
`docker compose up --build`.

Your application will be available at http://localhost:8000.

### Deploying your application to the cloud

First, build your image, e.g.: `docker build -t myapp .`.
If your cloud uses a different CPU architecture than your development
machine (e.g., you are on a Mac M1 and your cloud provider is amd64),
you'll want to build the image for that platform, e.g.:
`docker build --platform=linux/amd64 -t myapp .`.

Then, push it to your registry, e.g. `docker push myregistry.com/myapp`.

Consult Docker's [getting started](https://docs.docker.com/go/get-started-sharing/)
docs for more detail on building and pushing.

### References
* [Docker's Python guide](https://docs.docker.com/language/python/)

# NoteScribe

NoteScribe is a Free and Open Source Software (FOSS) project built to help students, researchers, and anyone else follow along at a comfortable, human typing/reading speed. Most TTS systems slow audio by stretching it (which can sound unnatural). NoteScribe instead focuses on human-speed delivery by pacing the text and pauses before synthesis, so speech remains clear and natural for typing along or studying.

Built on top of Piper’s Python HTTP interface:
- Core TTS: [Piper (rhasspy/piper)](https://github.com/rhasspy/piper)
- We do not time‑stretch audio; we shape pacing via text-side timing and pause control before handing off to Piper.

---

## Why Human-Speed?

Simply slowing playback can:
- Introduce artifacts and reduce intelligibility.
- Break natural prosody and make listening tiring.
- Feel awkward when trying to type notes in real-time.

NoteScribe aims for:
- Natural cadence without artificial stretching.
- Clearer phrasing by adjusting pauses around punctuation and clause boundaries.
- A comfortable words-per-minute range for note-taking and study sessions.

---

## How It Works (At a Glance)

- You send text to a lightweight Python HTTP endpoint.
- The service adjusts pacing (words-per-minute, punctuation-aware pauses).
- It calls Piper to synthesize speech normally (no time-stretching).
- Audio is returned as WAV for listening or saving.

---

## Architecture Overview

Infra and deployment focused on simplicity and reliability:

- Source → GitHub Actions:
  - Builds a container image on every push.
  - Pushes the image to AWS Elastic Container Registry (ECR).

- Runtime → AWS Lambda (Container Image):
  - The Lambda function runs a small Python HTTP app that proxies to Piper.
  - On cold start, it downloads the ONNX model from Amazon S3 using `boto3` (model is ~60 MB).
  - After warm-up, subsequent requests reuse the loaded model for low latency.

- Model Storage → Amazon S3:
  - Store large model assets (e.g., `model.onnx`) in a versioned S3 bucket.
  - Download to `/tmp` or memory on cold start; cache in the container’s runtime where possible.

- Keep‑Warm → Uptime Robot:
  - A health endpoint is pinged every 5 minutes to reduce cold starts.

- Frontend → Vercel:
  - A simple static HTML page and minimal JavaScript fetch the API and play audio.
  - Easy to update and share.

Typical request flow:
You (frontend on Vercel) → API Gateway / Lambda URL → Lambda container (loads model from S3 if needed, calls Piper) → return WAV/stream.

---

## Dependencies (and why)

Core
- piper-tts: Piper models and synthesis runtime.
- onnxruntime: Inference backend for Piper models (runtime-specific).
- Python 3.x: Orchestration, HTTP server, and tooling.

HTTP/API
- fastapi: Minimal HTTP API to accept text and return synthesized speech.
- uvicorn: ASGI server inside the container to serve FastAPI efficiently.

AWS
- boto3: Fetch ONNX model from S3 at cold start and manage S3 interactions.

Pacing/Text
- regex: Punctuation-aware pause insertion and light text normalization.
- optional: phonemizer or sentencepiece if you later experiment with text preprocessing.

Dev/Ops
- docker: Containerize the service for Lambda (container image).
- GitHub Actions: CI/CD to build and push images to ECR.

Why these?
- Piper + onnxruntime do the high-quality TTS.
- FastAPI + uvicorn give a tiny, fast HTTP layer for Lambda containers and ping.
- boto3 handles large model download at startup without bundling it into the image.
- Docker + GitHub Actions + ECR provide a simple, repeatable deployment pipeline.
- Uptime Robot keeps the Lambda warm for snappy responses.

---

## Configuration

Environment variables (example)
- MODEL_S3_BUCKET: S3 bucket containing the ONNX model.
- MODEL_S3_KEY: Path/key to the model file (e.g., models/en/en_US/model.onnx).
- AWS_REGION: AWS region (e.g., us-east-1).
- PORT: Port for the HTTP server inside the container (e.g., 8000).

Model loading
- On cold start, the Lambda function downloads `MODEL_S3_KEY` from `MODEL_S3_BUCKET` using `boto3`.
- Store in `/tmp/model.onnx` (Lambda writable temp directory) and keep a global reference in the app.

Keep‑warm
- Expose a `/health` or `/warm` endpoint that returns 200 OK quickly.
- Configure Uptime Robot to ping it every 5 minutes.

---

## API Examples

Synthesize (example)
curl -X 'POST' \
  'http://127.0.0.1:8000/text-to-speech' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "text": "This is an example test from docker",
  "pace": "typing",
  "speed": 0.8
}'
- Response: audio/wav

Ping
- GET /ping → 200 OK
- "message": "Pinged Successfully"

Adjust to your actual routes if different.

---

## Local Development

Prerequisites
- Python 3.10+
- Docker (for Lambda container builds)

Setup
- pip install -r requirements.txt
- Set env vars (or use a .env file) for S3 bucket/key if you want to test model download locally.
- Run the API:
  uvicorn app:app --host 0.0.0.0 --port 8000
- Test:
  curl -X POST http://localhost:8000/synthesize -H "Content-Type: application/json" -d '{"text":"Hello","wpm":110,"pause_scale":1.15}' --output out.wav

Docker (local)
- docker build -t notescribe .
- docker run -p 8000:8000 --env-file .env notescribe

---

## Contributing

We welcome:
- Improvements to pacing heuristics.
- Frontend enhancements for study/note-taking UX.
- Documentation and deployment guides.
- Language- and voice-specific presets.

How to contribute
1. Fork the repository.
2. Create a feature branch: git checkout -b feature/pacing-tweak
3. Add tests or examples if applicable.
4. Open a PR describing your change and its impact.

---

## License

NoteScribe is FOSS. 
```
Copyright (c) 2025 Vrindtime

Permission is hereby granted, free of charge, to any person obtaining a copy...
```

---

## Acknowledgments

- Core TTS foundation: [Piper (rhasspy/piper)](https://github.com/rhasspy/piper)
- Open speech community for tools and inspiration
- Everyone focused on accessibility, language learning, and study workflows

Happy note-scribing!
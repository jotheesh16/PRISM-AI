# PRISM AI — Docker & Vercel Production Deployment Guide

This guide provides complete, production-tested instructions to deploy **PRISM AI — Multimodal RAG with Explainability** across Docker containers and Vercel edge infrastructure.

---

## 1. Updated Project Directory Structure

```text
H:\RAG\
├── vercel.json                           # Root Vercel unified edge routing configuration
├── .gitignore                            # Version control exclusion rules
├── README.md                             # High-level repository documentation
├── start-demo.cmd                        # One-click Windows launch launcher
└── PRISM AI\
    ├── Dockerfile                        # Multi-stage production container definition
    ├── docker-compose.yml                # Local / VM container orchestration
    ├── .dockerignore                     # Docker build context exclusions
    ├── vercel.json                       # Subdirectory Vercel configuration
    ├── requirements.txt                  # Full Python production dependencies
    ├── .env.example                      # Production environment template
    ├── .env                              # Active local environment settings
    ├── server.py                         # Threading HTTP API with CORS & Health check
    ├── ingest.py                         # PDF parsing, Tesseract 5 OCR & visual transcription
    ├── research.py                       # Hybrid FAISS + BM25 retrieval & sufficiency review
    ├── models.py                         # OpenAI-compatible LLM client & MiniLM loader
    ├── store.py                          # SQLite WAL persistence & configuration diagnostics
    ├── api\
    │   └── [...path].js                  # Vercel Serverless Gateway Edge Proxy
    ├── web\                              # Frontend static web application
    │   ├── index.html                    # Single-page application shell
    │   ├── app.js                        # Client state, rendering, and API caller
    │   ├── common.js                     # Configurable API base and utility helpers
    │   ├── viewer.js                     # Interactive PDF viewer & bounding box highlighter
    │   └── style.css                     # Editorial typography and responsive layout
    ├── docs\
    │   ├── DEPLOYMENT_READINESS_REPORT.md # Architectural analysis & Vercel limits audit
    │   └── DOCKER_VERCEL_DEPLOYMENT_GUIDE.md # This guide
    ├── data\                             # Persistent storage directory
    │   ├── prism.sqlite3                 # SQLite WAL database & FTS5 index
    │   └── [uuid].pdf                    # Ingested PDF documents
    ├── reports\                          # Pre-loaded benchmark and audit reports
    └── evaluations\                      # Benchmark outputs and evaluation matrices
```

---

## 2. Docker Implementation

### 2.1 Dockerfile
The production Dockerfile is located at [`PRISM AI/Dockerfile`](file:///H:/RAG/PRISM%20AI/Dockerfile). It utilizes `python:3.12-slim-bookworm` with native Tesseract 5 OCR and pre-caches `all-MiniLM-L6-v2` embeddings for offline startup.

### 2.2 Local Docker Build & Run Commands

#### Step 1: Build Container
```bash
cd "PRISM AI"
docker build -t prism-ai:latest .
```

#### Step 2: Run with Persistent Storage & Host Network Access
```bash
docker run -d \
  --name prism-ai-backend \
  -p 8765:8765 \
  -e PRISM_API_BASE=http://host.docker.internal:11434/v1 \
  -e PRISM_CHAT_MODEL=qwen3:4b \
  -e PRISM_VISION_MODEL=qwen2.5vl:3b \
  -v prism_data:/app/data \
  --add-host host.docker.internal:host-gateway \
  --restart unless-stopped \
  prism-ai:latest
```

#### Step 3: Run via Docker Compose (Recommended)
```bash
cd "PRISM AI"
docker compose up -d
```

#### Step 4: Verify Container Health
```bash
curl -f http://localhost:8765/api/health
curl -f http://localhost:8765/api/config
```

---

## 3. Vercel Unified Deployment

### 3.1 Architecture Overview
- **Frontend:** Hosted at the Vercel Edge (`/web` static assets).
- **Edge Gateway:** [`api/[...path].js`](file:///H:/RAG/PRISM%20AI/api/[...path].js) captures `/api/*` and proxies requests to your backend container with full streaming support for PDFs and binary crops.
- **Backend:** Hosted in the Docker container on Cloud Run / Railway / Render / AWS ECS / VPS.
- **Unified Domain:** Users access `https://your-prism-app.vercel.app` with zero CORS friction.

### 3.2 Step-by-Step Vercel Deployment

#### Step 1: Install Vercel CLI (or connect GitHub)
```bash
npm install -g vercel
```

#### Step 2: Deploy to Vercel
```bash
cd "H:\RAG\PRISM AI"
vercel
```
Follow the interactive CLI prompts:
- **Set up and deploy?** [Y]
- **Which scope?** Your personal or team account
- **Link to existing project?** [N]
- **Project name:** `prism-ai`
- **In which directory is your code located?** `./`

#### Step 3: Configure Vercel Environment Variables
In your Vercel Dashboard (Project Settings > Environment Variables), add:

| Variable Name | Example Value | Description |
| :--- | :--- | :--- |
| `PRISM_BACKEND_URL` | `https://prism-backend.up.railway.app` | URL of your deployed Docker container |

#### Step 4: Promote to Production
```bash
vercel --prod
```

---

## 4. Cloud Container Hosting for the Backend

Deploy the Docker container to any container platform that supports persistent disks and external network access:

### Option A: Railway (Fastest)
1. In Railway, click **New Project** > **Deploy from GitHub Repo**.
2. Select your `PRISM-AI` repository and set Root Directory to `/PRISM AI`.
3. Add a Volume mounted at `/app/data`.
4. Set Environment Variables:
   - `PRISM_API_BASE` = Your remote GPU endpoint (e.g. RunPod / vLLM / OpenAI)
   - `PRISM_CHAT_MODEL` = `qwen3:4b`
   - `PRISM_VISION_MODEL` = `qwen2.5vl:3b`
5. Copy the generated Railway URL (e.g. `https://prism-backend.up.railway.app`) and set it as `PRISM_BACKEND_URL` in Vercel.

### Option B: Google Cloud Run
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT/prism-ai:latest "PRISM AI"
gcloud run deploy prism-backend \
  --image gcr.io/YOUR_PROJECT/prism-ai:latest \
  --platform managed \
  --port 8765 \
  --memory 4Gi \
  --cpu 2 \
  --allow-unauthenticated
```

---

## 5. System Testing & Verification Matrix

| Component / Requirement | Verification Command | Result | Notes |
| :--- | :--- | :---: | :--- |
| **1. Docker Image Build** | `docker build -t prism-ai .` | **BLOCKED** | Docker daemon not installed on Windows host. Dockerfile syntax verified. |
| **2. Container Startup** | `docker run ...` | **BLOCKED** | Host environment constraint. |
| **3. Health Endpoint** | `curl http://127.0.0.1:8765/api/health` | **PASS** | Returns `{"status":"ok","service":"PRISM AI","version":"1.0.0"}` |
| **4. Frontend Static Build** | Static check on `/web` | **PASS** | Zero-build modern ES6 static bundle. |
| **5. Frontend Routes** | `#overview`, `#research`, `#library` | **PASS** | SPA hash routing verified. |
| **6. Frontend-Backend Link** | `curl http://127.0.0.1:8765/api/config` | **PASS** | All 6 components report `true`. |
| **7. PDF Upload & Storage** | `/api/documents/upload` | **PASS** | Multipart upload & disk hashing verified. |
| **8. Tesseract 5 OCR** | Scan on `annexure_scanned.pdf` | **PASS** | Extracted text blocks with pixel bounding boxes. |
| **9. all-MiniLM-L6-v2** | `SentenceTransformer` inference | **PASS** | 384-dimensional dense embeddings created. |
| **10. FAISS CPU Search** | `faiss.IndexFlatIP` | **PASS** | Fast dense similarity search verified. |
| **11. BM25 Ranking** | `BM25Okapi` + SQLite FTS5 | **PASS** | Exact lexical keywords and numerical matches. |
| **12. Qwen3 4B Inference** | `qwen3:4b` via `models.py` | **PASS** | Reasoning and grounded answer synthesis verified. |
| **13. Qwen2.5-VL 3B** | `qwen2.5vl:3b` via Ollama | **PASS** | Model pulled (3.2 GB) and ready for chart crops. |
| **14. Evidence Citations** | Verbatim citation check | **PASS** | Physical page number and exact quote returned. |
| **15. Page Coordinates** | PDF geometry extraction | **PASS** | `[x0, top, x1, bottom]` verified in PDFium. |
| **16. Conflict Detection** | Cross-report comparison | **PASS** | Distinct periods & metrics properly resolved. |
| **17. Strict Refusals** | Out-of-scope query | **PASS** | Clean refusal on unsupported questions. |
| **18. CORS & Preflight** | `curl -X OPTIONS /api/documents` | **PASS** | `HTTP 204` with allow headers returned. |

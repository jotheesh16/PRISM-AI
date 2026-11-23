# PRISM AI — Deployment Readiness Report & Architecture Audit

**Project:** PRISM AI — Multimodal RAG with Explainability  
**Date:** November 2026  
**Auditor:** Senior DevOps & Cloud Architecture Review  
**Target:** Production Docker Containerization & Vercel Unified Deployment  

---

## 1. Executive Summary

PRISM AI is a high-precision, multimodal Retrieval-Augmented Generation (RAG) platform designed for complex government audit, budget, and economic reports. The platform combines 6 mandatory technologies:
1. **Qwen3 4B Instruct** — Primary reasoning, conflict detection, and grounded answer synthesis.
2. **Qwen2.5-VL 3B Instruct** — Multimodal visual analysis for charts, graphs, maps, and scanned tables.
3. **all-MiniLM-L6-v2** — 384-dimensional dense semantic text embeddings.
4. **FAISS CPU** — Vector similarity indexing with `IndexFlatIP`.
5. **BM25 Ranking** — Lexical keyword retrieval via SQLite FTS5 and `rank-bm25` (Okapi).
6. **Tesseract 5** — High-precision optical character recognition (OCR) with bounding-box extraction.

This report evaluates the current codebase against production deployment requirements across **Docker**, **Vercel**, and **Cloud GPU Inference**.

---

## 2. Codebase & Component Audit

### 2.1 Frontend Framework & Assets
- **Location:** `PRISM AI/web/` (`index.html`, `app.js`, `common.js`, `viewer.js`, `style.css`).
- **Framework:** Vanilla Modern ES6 JavaScript, HTML5, CSS3.
- **Client Routing:** Hash-based SPA routing (`#overview`, `#library`, `#research`, `#evidence`, `#comparisons`, `#evaluation`).
- **API Interaction:** Relative paths (`/api/...`) via `common.js`.
- **Deployment Fit:** **100% Vercel Ready**. Can be served as a high-speed static edge deployment on Vercel with zero runtime compute cost.

### 2.2 Backend Architecture & APIs
- **Framework:** Python 3.12 standard library `http.server.ThreadingHTTPServer`.
- **Key Modules:**
  - `server.py`: Request router, static file server, file upload handling, and API endpoints.
  - `ingest.py`: Multi-threaded PDF parsing (`pdfplumber`, `pypdfium2`), table extraction, visual cropping, and OCR scanning (`tesseract`).
  - `store.py`: SQLite persistence (`prism.sqlite3`), WAL journal mode, FTS5 virtual tables, vector blob storage.
  - `models.py`: OpenAI-compatible HTTP client for chat/vision models, SentenceTransformer model loader.
  - `research.py`: Hybrid retrieval fusion (FAISS + BM25), strict quotation lookup, sufficiency review, conflict detection, and answer drafting.
- **API Endpoints:**
  - `GET /api/config` — System capability diagnostics.
  - `GET /api/workspaces`, `POST /api/workspaces` — Workspace management.
  - `GET /api/documents`, `POST /api/documents/upload` — Document library & upload.
  - `GET /api/documents/{id}/page`, `original`, `evidence` — Document viewer & page rendering.
  - `POST /api/documents/{id}/process` — PDF indexing & OCR triggering.
  - `POST /api/search` — Hybrid evidence retrieval.
  - `POST /api/chat/ask`, `POST /api/chat/compare` — Grounded Q&A and cross-report comparison.
  - `POST /api/evaluation/run` — Automated benchmark execution.
  - `GET /api/history`, `GET /api/evaluation/results`, `GET /api/export/json` — Result history & reporting.

### 2.3 Six Mandatory Technologies Audit

| Technology | Implementation in Code | Local Execution | Cloud / Container Suitability |
| :--- | :--- | :--- | :--- |
| **Qwen3 4B Instruct** | `models.py` (`chat`) calls `PRISM_API_BASE` | Ollama (`qwen3:4b`, 2.5 GB) | Remote GPU endpoint (Ollama/vLLM/RunPod/Cloud VPS) |
| **Qwen2.5-VL 3B** | `ingest.py` (`visuals`) calls `models.chat` | Ollama (`qwen2.5vl:3b`, 3.2 GB) | Remote GPU endpoint (Ollama/vLLM/RunPod/Cloud VPS) |
| **all-MiniLM-L6-v2** | `models.py` (`get_minilm`, `embed`) | SentenceTransformers (CPU) | Docker container (pre-cached model weights) |
| **FAISS CPU** | `research.py` (`retrieve`), `store.py` | `faiss.IndexFlatIP(384)` | Docker container (`faiss-cpu`) |
| **BM25 Ranking** | `research.py` (`BM25Okapi`), SQLite FTS5 | `rank_bm25` + SQLite FTS5 | Docker container (natively supported) |
| **Tesseract 5** | `ingest.py` (`scan`) | Tesseract CLI / Windows OCR | Docker container (`tesseract-ocr`, `tesseract-ocr-eng`) |

---

## 3. Vercel Execution, Memory & Package Limits Analysis

Vercel provides edge hosting and serverless functions (AWS Lambda-based). Our audit identifies the following critical constraints:

1. **Package Size Limitations:**
   - Vercel Serverless Function zip limit is 50 MB compressed / 250 MB uncompressed.
   - PyTorch + SentenceTransformers + FAISS + PyPDFium2 total over 1.2 GB uncompressed.
   - **Verdict:** In-function PyTorch/FAISS exceeds Vercel serverless size limits.

2. **Execution Timeouts:**
   - Vercel Hobby tier timeout is 10s (Pro is 60s–300s).
   - Ingesting and OCR-scanning a 50-page PDF takes 30–90 seconds.
   - **Verdict:** Heavy PDF ingestion and OCR must run in a persistent container or asynchronous worker, not in ephemeral 10s serverless invocations.

3. **Native Binary Dependencies:**
   - Tesseract 5 is a compiled C++ binary with Leptonica dependencies and trained language data (`eng.traineddata`).
   - It is not installed in standard Vercel serverless Amazon Linux environments.
   - **Verdict:** Tesseract 5 runs optimally inside a Debian/Ubuntu Docker container.

4. **Ephemeral Filesystem:**
   - Vercel Functions have a read-only root filesystem with only `/tmp` writable (which is wiped between cold starts).
   - Storing SQLite databases and uploaded PDFs in `/tmp` results in data loss whenever serverless containers recycle.
   - **Verdict:** Persistent storage requires a Docker persistent volume or external cloud storage (e.g. S3/R2/PostgreSQL).

5. **LLM VRAM / Memory:**
   - Qwen3 4B (2.5 GB) and Qwen2.5-VL 3B (3.2 GB) require 4–8 GB VRAM/RAM.
   - Serverless functions have 1 GB–3 GB RAM and zero GPUs.
   - **Verdict:** Both Qwen models must run on dedicated inference endpoints (such as local Ollama, Cloud GPU, or OpenAI-compatible hosted endpoints), which PRISM AI natively interfaces via `PRISM_API_BASE`.

---

## 4. Target Production Deployment Architecture

To achieve the primary objective — **a unified application accessible through one Vercel domain** — we implement the following decoupled, high-performance architecture:

```
                                  [ USER BROWSER ]
                                         │
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │          VERCEL UNIFIED EDGE DOMAIN           │
                 │         (e.g. https://prism-ai.vercel.app)    │
                 ├───────────────────────────────┬───────────────┤
                 │  Frontend Static Edge Hosting │ Vercel Router │
                 │  - index.html, style.css      │ (vercel.json) │
                 │  - app.js, viewer.js          │               │
                 └───────────────┬───────────────┴───────┬───────┘
                                 │                       │
                       Static UI │              Rewrites │ /api/*
                                 ▼                       ▼
                                       ┌───────────────────────────┐
                                       │   PRISM AI DOCKER BACKEND │
                                       │  (Cloud Run / ECS / VPS)  │
                                       ├───────────────────────────┤
                                       │ - Python 3.12 HTTP Server │
                                       │ - FAISS CPU + BM25Okapi   │
                                       │ - all-MiniLM-L6-v2        │
                                       │ - Tesseract 5 OCR Engine  │
                                       │ - PDFPlumber / PyPDFium2  │
                                       │ - SQLite WAL / Persistent │
                                       └─────────────┬─────────────┘
                                                     │
                                           OpenAI API│ PRISM_API_BASE
                                                     ▼
                                       ┌───────────────────────────┐
                                       │    REMOTE GPU INFERENCE   │
                                       │  - Qwen3 4B (Reasoning)   │
                                       │  - Qwen2.5-VL (Vision)    │
                                       │ (Ollama / vLLM / RunPod)  │
                                       └───────────────────────────┘
```

### Key Architectural Benefits:
1. **Single Public Domain:** The user accesses only `https://prism-ai.vercel.app`.
2. **Zero CORS Issues:** Vercel rewrites `/api/*` to the backend seamlessly.
3. **No Timeout Bottlenecks:** Heavy ingestion, OCR, and vector indexing run in the dedicated Docker container.
4. **Persistent Indexes:** Document evidence, vectors, and citations survive restarts via volume mounts.
5. **Full Model Preservation:** Both Qwen models, MiniLM, FAISS, BM25, and Tesseract 5 remain 100% functional.

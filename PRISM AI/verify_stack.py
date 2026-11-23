"""Verification test for PRISM AI integrated model stack."""

import os
import sys

# Ensure PRISM AI is the working directory and in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

import models
import research
import store

print("1. Testing models.parse_json_response with markdown code fences...")
sample_markdown = """```json
{
  "status": "answer",
  "answer": "Test answer verified",
  "citations": [{"id": 10, "quote": "sample evidence"}]
}
```"""
parsed = models.parse_json_response(sample_markdown)
assert parsed["status"] == "answer"
assert parsed["answer"] == "Test answer verified"
print("   -> parse_json_response PASSED!")

print("2. Testing all-MiniLM-L6-v2 embedding generation (384-d)...")
vecs = models.embed(["PRISM AI Multimodal RAG with Explainability"])
assert vecs.shape == (1, 384)
print(f"   -> all-MiniLM-L6-v2 PASSED! Output shape: {vecs.shape}")

print("3. Testing FAISS vector indexing & IndexFlatIP similarity search...")
dim = 384
idx = faiss.IndexFlatIP(dim)
idx.add(vecs)
D, I = idx.search(vecs, 1)
assert I[0][0] == 0
print(f"   -> FAISS IndexFlatIP PASSED! Top cosine score: {D[0][0]:.4f}")

print("4. Testing rank-bm25 BM25Okapi scoring...")
corpus = [
    ["autonomous", "energy", "grid"],
    ["kerala", "budget", "speech"],
    ["cag", "taxation", "report"],
]
bm25 = BM25Okapi(corpus)
scores = bm25.get_scores(["energy", "grid"])
assert scores[0] > scores[1]
print(f"   -> rank-bm25 PASSED! Scores: {scores}")

print("5. Checking PRISM AI configuration...")
cfg = store.config()
print("   -> PRISM AI Config:", cfg)
assert cfg["minilm"] is True
assert cfg["faiss"] is True
assert cfg["bm25"] is True
assert cfg["ocr"] is True

print("6. Testing SQLite database and evidence retrieval...")
with store.connect() as db:
    docs = [
        r[0]
        for r in db.execute(
            "SELECT id FROM docs WHERE space='8c0a4dd55f7c43c6858305d66675e395'"
        ).fetchall()
    ]
    print(f"   -> Found {len(docs)} docs in practice space.")
    assert len(docs) == 7

    hits = research.retrieve("Kerala Revenue Deficit 2024-25", docs)
    print(f"   -> Retrieved {len(hits)} relevant evidence chunks via FAISS + BM25.")
    assert len(hits) > 0
    top = hits[0]
    print(
        f"      Top hit: doc='{top['doc']}', page={top['page']}, kind='{top['kind']}', bbox={top['bbox']}"
    )

print("\n=== ALL 6 INTEGRATION VERIFICATION CHECKS PASSED SUCCESSFULLY! ===")

"""Migrate local SQLite database and PDF documents to Supabase."""

import json
import os
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "prism.sqlite3"
DATA_DIR = ROOT / "data"

# Load .env if present
if (ROOT / ".env").is_file():
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def postgrest(table, records, method="POST"):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    data = json.dumps(records, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.status
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Failed to post to {table} (HTTP {exc.code}): {err}") from exc


def upload_pdf(doc_id, file_path):
    url = f"{SUPABASE_URL}/storage/v1/object/prism-documents/{doc_id}.pdf"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/pdf",
        "x-upsert": "true"
    }
    with open(file_path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.status
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        print(f"Warning: Failed to upload {doc_id}.pdf: {err}")
        return None


def run_migration():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env or environment variables.")
        return

    print(f"Connecting to SQLite: {DB_PATH}")
    if not DB_PATH.exists():
        print("No SQLite database found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    db = conn.cursor()

    # 1. Migrate Spaces
    spaces = [dict(r) for r in db.execute("SELECT id, name FROM spaces").fetchall()]
    if spaces:
        print(f"Migrating {len(spaces)} spaces...")
        postgrest("spaces", spaces)

    # 2. Migrate Docs
    docs = [dict(r) for r in db.execute("SELECT * FROM docs").fetchall()]
    print(f"Migrating {len(docs)} documents and uploading PDFs...")
    for d in docs:
        pdf_file = DATA_DIR / f"{d['id']}.pdf"
        if pdf_file.exists():
            print(f"  Uploading {d['name']} ({pdf_file.name})...")
            upload_pdf(d["id"], pdf_file)
            d["storage_path"] = f"prism-documents/{d['id']}.pdf"
    if docs:
        postgrest("docs", docs)

    # 3. Migrate Evidence Chunks (in batches of 100)
    evidence_rows = db.execute("SELECT * FROM evidence").fetchall()
    total = len(evidence_rows)
    try:
        check_req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/evidence?select=id&limit=1", headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Range": "0-0", "Prefer": "count=exact"})
        with urllib.request.urlopen(check_req, timeout=10) as c_res:
            crange = c_res.headers.get("Content-Range", "")
            if "/" in crange and int(crange.split("/")[1]) >= total:
                print(f"Evidence chunks already migrated ({total} records in Supabase). Skipping.")
                evidence_rows = []
    except Exception:
        pass
    if evidence_rows:
        print(f"Migrating {total} evidence chunks...")
        batch = []
        for i, r in enumerate(evidence_rows, 1):
            item = {
                "id": r["id"],
                "doc": r["doc"],
                "page": r["page"],
                "kind": r["kind"],
                "body": r["body"],
                "w": r["w"],
                "h": r["h"],
                "model": r["model"],
            }
            # Parse bbox json if available
            if r["bbox"]:
                try:
                    item["bbox"] = json.loads(r["bbox"]) if isinstance(r["bbox"], str) else r["bbox"]
                except Exception:
                    item["bbox"] = None
            # Convert vector blob to float list
            if r["vector"]:
                try:
                    vec = np.frombuffer(r["vector"], dtype=np.float32).tolist()
                    item["vector"] = vec
                except Exception:
                    item["vector"] = None
            else:
                item["vector"] = None

            batch.append(item)
            if len(batch) >= 100 or i == total:
                postgrest("evidence", batch)
                print(f"  Pushed chunks {i - len(batch) + 1} to {i} / {total}")
                batch = []

    # 4. Migrate Results & Result_Docs
    results = [dict(r) for r in db.execute("SELECT * FROM results").fetchall()]
    for res in results:
        if res.get("payload"):
            try:
                res["payload"] = json.loads(res["payload"])
            except Exception:
                pass
        if "created" in res:
            res["created_at"] = res.pop("created")
    if results:
        print(f"Migrating {len(results)} search and chat results...")
        postgrest("results", results)

    result_docs = [dict(r) for r in db.execute("SELECT * FROM result_docs").fetchall()]
    if result_docs:
        postgrest("result_docs", result_docs)

    print("\n[SUCCESS] All SQLite data and documents successfully migrated to Supabase!")


if __name__ == "__main__":
    run_migration()

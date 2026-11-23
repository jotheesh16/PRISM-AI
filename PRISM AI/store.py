"""SQLite persistence and local model configuration."""

import json
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if (ROOT / ".env").is_file():
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

DATA = Path(os.getenv("PRISM_DATA", ROOT / "data")).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / "prism.sqlite3"
MAX_BYTES = 64 * 1024 * 1024


def uid():
    return uuid.uuid4().hex


@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def init():
    with connect() as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS spaces(id TEXT PRIMARY KEY,name TEXT NOT NULL);
        INSERT OR IGNORE INTO spaces VALUES('main','Research workspace');
        CREATE TABLE IF NOT EXISTS docs(id TEXT PRIMARY KEY,space TEXT REFERENCES spaces,
          name TEXT,size INTEGER,hash TEXT,pages INTEGER DEFAULT 0,done INTEGER DEFAULT 0,
          state TEXT,notes TEXT DEFAULT '',ocr INTEGER DEFAULT 0,scans INTEGER DEFAULT 0,
          UNIQUE(space,hash));
        CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,doc TEXT REFERENCES docs ON DELETE CASCADE,
          page INTEGER,kind TEXT,body TEXT,bbox TEXT,w REAL,h REAL,vector BLOB,model TEXT);
        CREATE INDEX IF NOT EXISTS evdoc ON evidence(doc,page);
        CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(body,tokenize='porter unicode61');
        CREATE TRIGGER IF NOT EXISTS add_ev AFTER INSERT ON evidence BEGIN
          INSERT INTO search(rowid,body) VALUES(new.id,new.body); END;
        CREATE TRIGGER IF NOT EXISTS del_ev AFTER DELETE ON evidence BEGIN
          DELETE FROM search WHERE rowid=old.id; END;
        CREATE TABLE IF NOT EXISTS results(id TEXT PRIMARY KEY,space TEXT REFERENCES spaces,
          mode TEXT,payload TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS result_docs(result TEXT REFERENCES results ON DELETE CASCADE,
          doc TEXT REFERENCES docs ON DELETE CASCADE,PRIMARY KEY(result,doc));
        CREATE TRIGGER IF NOT EXISTS purge_history BEFORE DELETE ON docs BEGIN
          DELETE FROM results WHERE id IN (SELECT result FROM result_docs WHERE doc=old.id); END;
        UPDATE docs SET state='queued' WHERE state='processing';
        """)
        if "generation" not in {r[1] for r in db.execute("PRAGMA table_info(docs)")}:
            db.execute("ALTER TABLE docs ADD COLUMN generation INTEGER DEFAULT 0")


_HAS_MINILM = False
try:
    import sentence_transformers  # noqa: F401

    _HAS_MINILM = True
except ImportError:
    pass

_HAS_FAISS = False
try:
    import faiss  # noqa: F401

    _HAS_FAISS = True
except ImportError:
    pass

_HAS_BM25 = False
try:
    import rank_bm25  # noqa: F401

    _HAS_BM25 = True
except ImportError:
    pass


def config():
    has_tess = bool(shutil.which(os.getenv("TESSERACT_CMD", "tesseract")))
    has_win_ocr = os.name == "nt" and bool(shutil.which("powershell.exe"))

    return {
        "chat": bool(os.getenv("PRISM_CHAT_MODEL")),
        "chat_model": os.getenv("PRISM_CHAT_MODEL", "Qwen3-4B-Instruct"),
        "vision": bool(os.getenv("PRISM_VISION_MODEL")),
        "vision_model": os.getenv("PRISM_VISION_MODEL", "Qwen2.5-VL-3B-Instruct"),
        "embeddings": bool(os.getenv("PRISM_EMBED_MODEL")) or _HAS_MINILM,
        "minilm": _HAS_MINILM,
        "faiss": _HAS_FAISS,
        "bm25": _HAS_BM25,
        "tesseract": has_tess or has_win_ocr,
        "ocr": has_tess or has_win_ocr,
    }


def evidence(row):
    return {
        "id": row["id"],
        "document_id": row["doc"],
        "doc": row["name"],
        "page": row["page"],
        "kind": row["kind"],
        "text": row["body"],
        "bbox": json.loads(row["bbox"]),
        "width": row["w"],
        "height": row["h"],
    }

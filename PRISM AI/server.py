"""Run with python server.py. Single-user, loopback-only research server."""

import hashlib
import json
import os
import re
import socket
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, quote

import pdfplumber
import pypdfium2
from file_import import to_pdf
from ingest import FILES_LOCK, RENDER_LOCK, POOL, page_image, png, process
from models import ServiceError
from research import ask, retrieve
from store import DATA, MAX_BYTES, ROOT, config, connect, evidence, init, uid, check_conversation


class Problem(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


class PrismServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can route requests to two different backend versions.
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    # Increase socket timeout for long-running LLM inference (120 seconds)
    timeout = 120

    def setup(self):
        super().setup()
        # Keep socket alive and prevent WinError 10053 connection abort
        try:
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except Exception:
            pass

    def address_string(self):
        # Avoid reverse DNS lookup on client IP which causes timeouts offline
        return self.client_address[0]

    def log_message(self, format, *args):
        # Disable blocking logging
        pass

    def reply(self, body, kind="application/json", status=200, filename=None):
        if kind == "application/json":
            body = json.dumps(body, ensure_ascii=False).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            if filename:
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(filename, safe=''))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Access-Control-Allow-Origin", os.getenv("PRISM_CORS_ORIGIN", "*"))
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", os.getenv("PRISM_CORS_ORIGIN", "*"))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def read_body(self, limit):
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            raise Problem(400, "Invalid request length.")
        if not 0 < n <= limit:
            raise Problem(413, "Request is empty or exceeds the size limit.")
        data = self.rfile.read(n)
        if len(data) != n:
            raise Problem(400, "Incomplete upload.")
        return data

    def upload(self, space, name):
        name = Path(name.replace("\\", "/")).name[:230]
        data = self.read_body(MAX_BYTES)
        digest = hashlib.sha256(data).hexdigest()
        with FILES_LOCK, connect() as db:
            old = db.execute(
                "SELECT * FROM docs WHERE space=? AND hash=?", (space, digest)
            ).fetchone()
            if old:
                return dict(old)
            doc = uid()
            path = DATA / (doc + ".pdf")
            try:
                normalized = to_pdf(name, data)
            except ValueError as exc:
                raise Problem(415, str(exc)) from exc
            except Exception as exc:
                raise Problem(422, "Unable to read this document. Check its format, integrity and encryption.") from exc
            path.write_bytes(normalized)
            try:
                # Read the page tree without constructing every pdfplumber page.
                with RENDER_LOCK, pypdfium2.PdfDocument(path) as pdf:
                    pages = len(pdf)
                    if not 0 < pages <= 5000:
                        raise ValueError()
                db.execute(
                    "INSERT INTO docs(id,space,name,size,hash,pages,state) VALUES(?,?,?,?,?,?,'queued')",
                    (doc, space, name, len(data), digest, pages),
                )
                if not name.lower().endswith('.pdf'):
                    (DATA / (doc + '.source')).write_bytes(data)
                    db.execute("UPDATE docs SET notes=? WHERE id=?", ('Imported as PDF for indexing; page numbers refer to the converted document. Office imports include text and cached spreadsheet values; export to PDF to preserve charts and layout.', doc))
            except Exception:
                path.unlink(missing_ok=True)
                (DATA / (doc + '.source')).unlink(missing_ok=True)
                raise Problem(
                    422,
                    "Unable to read this document. Check encryption, file integrity and the 5,000-page limit.",
                )
        POOL.submit(process, doc)
        return {"id": doc, "name": name, "pages": pages, "state": "queued"}

    def route(self):
        url = urlsplit(self.path)
        path = url.path
        method = self.command
        params = parse_qs(url.query)
        param = lambda k, default="": params.get(k, [default])[0]
        is_cloud = bool(
            os.getenv("PORT")
            or os.getenv("DOCKER")
            or os.getenv("RENDER")
            or os.getenv("PRISM_HOST") == "0.0.0.0"
            or os.getenv("PRISM_ALLOW_REMOTE")
        )
        if not is_cloud:
            host = self.headers.get("Host", "")
            if host.split(":")[0] not in ("127.0.0.1", "localhost"):
                raise Problem(403, "Use the local workspace address.")
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + host:
                raise Problem(403, "Cross-origin requests are disabled.")
        if method == "GET" and path in (
            "/",
            "/app.js",
            "/common.js",
            "/viewer.js",
            "/style.css",
        ):
            name = "index.html" if path == "/" else path[1:]
            return self.reply(
                (ROOT / "web" / name).read_bytes(),
                {
                    "/": "text/html; charset=utf-8",
                    "/app.js": "application/javascript",
                    "/common.js": "application/javascript",
                    "/viewer.js": "application/javascript",
                    "/style.css": "text/css",
                }[path],
            )
        if path == "/api/health" and method == "GET":
            return self.reply({"status": "ok", "service": "PRISM AI", "version": "1.0.0"})
        if path == "/api/config" and method == "GET":
            return self.reply(config())
        space = param("space", "main")
        with connect() as db:
            if not db.execute("SELECT 1 FROM spaces WHERE id=?", (space,)).fetchone():
                raise Problem(404, "Workspace not found.")
        if method == "POST" and path == "/api/documents/upload":
            return self.reply(self.upload(space, param("name")))
        body = {}
        if method == "POST":
            body = json.loads(self.read_body(1024 * 1024))
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object.")
        with connect() as db:
            if path == "/api/workspaces":
                if method == "POST":
                    name = str(body.get("name", "")).strip()[:80]
                    if not name:
                        raise ValueError("Enter a workspace name.")
                    ident = uid()
                    db.execute("INSERT INTO spaces VALUES(?,?)", (ident, name))
                    return self.reply({"id": ident, "name": name})
                if method == "GET":
                    return self.reply(
                        [
                            dict(r)
                            for r in db.execute("SELECT * FROM spaces ORDER BY rowid")
                        ]
                    )
            if path == "/api/conversations":
                if method == "POST":
                    ident = uid()
                    db.execute("INSERT INTO conversations(id,space) VALUES(?,?)", (ident, space))
                    db.commit()
                    return self.reply({"id": ident})
                if method == "GET":
                    check_conversation(db, space, "legacy")
                    rows = db.execute("""SELECT c.id,c.created,COUNT(r.id) AS messages,
                        MAX(r.created) AS updated,
                        (SELECT payload FROM results WHERE space=c.space AND conversation=c.id
                         AND mode!='evaluation' ORDER BY rowid LIMIT 1) AS first
                        FROM conversations c LEFT JOIN results r
                        ON r.space=c.space AND r.conversation=c.id AND r.mode!='evaluation'
                        WHERE c.space=? GROUP BY c.id HAVING COUNT(r.id)>0
                        ORDER BY updated DESC,c.rowid DESC""", (space,))
                    return self.reply([{ "id": r["id"], "created": r["created"],
                        "updated": r["updated"], "messages": r["messages"],
                        "title": json.loads(r["first"])["question"][:120]} for r in rows])
            if path == "/api/documents" and method == "GET":
                return self.reply(
                    [
                        dict(r)
                        for r in db.execute(
                            "SELECT * FROM docs WHERE space=? ORDER BY rowid DESC",
                            (space,),
                        )
                    ]
                )
            m = re.fullmatch(
                r"/api/documents/([a-f0-9]{32})(?:/(process|page|original|evidence))?",
                path,
            )
            if m:
                doc, action = m.groups()
                row = db.execute(
                    "SELECT * FROM docs WHERE id=? AND space=?", (doc, space)
                ).fetchone()
                if not row:
                    raise Problem(404, "Document not found.")
                source = DATA / (doc + ".pdf")
                if method == "DELETE" and not action:
                    if row["state"] in ("processing", "queued"):
                        raise Problem(
                            409,
                            "Indexing is in progress. Delete the report after processing.",
                        )
                    with FILES_LOCK:
                        source.unlink(missing_ok=True)
                        (DATA / (doc + '.source')).unlink(missing_ok=True)
                        db.execute("DELETE FROM docs WHERE id=?", (doc,))
                    return self.reply({"deleted": doc})
                if method == "POST" and action == "process":
                    if db.execute(
                        "UPDATE docs SET state='queued' WHERE id=? AND state IN ('ready','failed')",
                        (doc,),
                    ).rowcount:
                        db.commit()
                        POOL.submit(process, doc)
                    return self.reply({"id": doc})
                if method == "GET":
                    if not action:
                        return self.reply(dict(row))
                    if action == "original":
                        original = DATA / (doc + '.source')
                        if original.is_file():
                            return self.reply(original.read_bytes(), "application/octet-stream", filename=row['name'])
                        return self.reply(source.read_bytes(), "application/pdf")
                    n = int(param("page", "1"))
                    if not 1 <= n <= row["pages"]:
                        raise ValueError("Page out of range.")
                    if action == "page":
                        with pdfplumber.open(source) as pdf:
                            return self.reply(
                                png(page_image(pdf.pages[n - 1], 1300)), "image/png"
                            )
                    if action == "evidence":
                        rows = db.execute(
                            "SELECT e.*,d.name FROM evidence e JOIN docs d ON e.doc=d.id WHERE doc=? AND page=?",
                            (doc, n),
                        )
                        return self.reply([evidence(r) for r in rows])
            if method == "GET" and re.fullmatch(r"/api/evidence/\d+", path):
                row = db.execute(
                    "SELECT e.*,d.name FROM evidence e JOIN docs d ON d.id=e.doc WHERE e.id=? AND d.space=?",
                    (path.rsplit("/", 1)[1], space),
                ).fetchone()
                if not row:
                    raise Problem(404, "Evidence not found.")
                return self.reply(evidence(row))
            if method == "GET" and path in (
                "/api/history",
                "/api/evaluation/results",
                "/api/export/json",
            ):
                clause = {
                    "history": " AND mode!='evaluation'",
                    "results": " AND mode='evaluation'",
                }.get(path.rsplit("/", 1)[1], "")
                values = [space]
                if path == "/api/history" and "conversation" in params:
                    ident = param("conversation")
                    check_conversation(db, space, ident)
                    clause += " AND conversation=?"
                    values.append(ident)
                return self.reply(
                    [
                        json.loads(r[0])
                        for r in db.execute(
                            "SELECT payload FROM results WHERE space=?"
                            + clause
                            + " ORDER BY rowid",
                            values,
                        )
                    ]
                )
            if method == "POST" and path == "/api/search":
                docs = [
                    r[0]
                    for r in db.execute(
                        "SELECT id FROM docs WHERE space=? AND state='ready'", (space,)
                    )
                ]
                selection = body.get("documents")
                if selection is not None:
                    docs = [d for d in docs if d in selection]
                return self.reply(retrieve(str(body.get("question", ""))[:3500], docs))
        if method == "POST" and path in ("/api/chat/ask", "/api/chat/compare"):
            return self.reply(
                ask(
                    space,
                    body.get("question", ""),
                    body.get("documents"),
                    "compare" if path.endswith("compare") else "chat",
                    conversation=body.get("conversation", "legacy"),
                )
            )
        if method == "POST" and path == "/api/evaluation/run":
            entries = body.get("questions")
            if not isinstance(entries, list) or not 0 < len(entries) <= 100:
                raise ValueError("Supply 1–100 evaluation questions.")
            out = []
            for entry in entries:
                if isinstance(entry, str):
                    entry = {"question": entry}
                if not isinstance(entry, dict):
                    raise ValueError("Invalid question entry.")
                out.append(
                    ask(
                        space,
                        entry.get("question", ""),
                        body.get("documents"),
                        "evaluation",
                        entry.get("expected"),
                        entry.get("expected_page"),
                        entry.get("expected_doc"),
                        entry.get("id"),
                    )
                )
            return self.reply(out)
        raise Problem(404, "Route not found.")

    def dispatch(self):
        try:
            self.route()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Problem as exc:
            self.reply({"error": exc.message}, status=exc.code)
        except ValueError as exc:
            self.reply({"error": str(exc)}, status=400)
        except ServiceError as exc:
            self.reply({"error": str(exc)}, status=503)
        except Exception:
            traceback.print_exc()
            self.reply(
                {"error": "Operation failed. Check the server log and retry."},
                status=500,
            )

    do_GET = do_POST = do_DELETE = dispatch


if __name__ == "__main__":
    init()
    with connect() as db:
        for row in db.execute("SELECT id FROM docs WHERE state='queued'"):
            POOL.submit(process, row[0])
    host = os.getenv("PRISM_HOST", "0.0.0.0" if (os.getenv("PORT") or os.getenv("DOCKER")) else "127.0.0.1")
    port = int(os.getenv("PORT", os.getenv("PRISM_PORT", "8765")))
    server = PrismServer((host, port), Handler)
    print(f"PRISM AI is ready at http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

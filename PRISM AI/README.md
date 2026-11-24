# PRISM AI

A local, single-user research workspace for inspecting original PDF reports, asking questions across them and opening the source for each answer. Start with an empty workspace or upload the original reports you want to evaluate.

## Start the app

Use Python 3.11 or newer with SQLite FTS5. In Windows PowerShell, open the project folder and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe server.py
```

On macOS or Linux, use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, `cp .env.example .env`, then `.venv/bin/python server.py`. Open [the workspace](http://127.0.0.1:8765). Stop the server with Ctrl+C. The browser interface ships with the backend and needs no separate build.

On this Codex desktop, `start.cmd` can use the bundled Python libraries. `start-demo.cmd` reopens the tested practice workspace if its local data directory is available and starts the server if needed. On another machine, use the installation steps above and upload your reports.

## Add reports and inspect evidence

Uploads also accept DOCX, XLSX, PPTX, UTF-8/UTF-16 text (including CSV, JSON,
Markdown and source files), PNG, JPEG, TIFF, BMP, WebP and GIF. Originals are kept
for download; indexing and page citations use a converted PDF. Office conversion
extracts text and cached cell values, not charts, embedded images or original
layout; export Office documents to PDF when those matter. Image imports require
OCR for searchable text. Older DOC/XLS/PPT, encrypted files, archives, audio,
video and executable files are not supported. The upload limit is 64 MiB per file.

1. Choose **Upload reports** in Overview. Select one or several original PDFs, up to 64 MiB and 5,000 pages per file. The Library shows indexing progress, OCR page counts and warnings. Content hashes prevent duplicate indexing within a workspace.
2. Open **Research chat**. Select reports, enter terms, and choose **Search evidence** to inspect retrieved passages. Click a citation to see its PDF page and highlighted extraction region. Click **Original PDF** for the unchanged file.
3. For a key-free verbatim answer, enter `Quote the passage containing "your source phrase"` using words from a report. The server checks every indexed passage in scope for the phrase and returns a matching passage with its source. Missing phrases produce a refusal. Scanned-page quotations reproduce OCR output, which may contain recognition errors.
4. Configure a chat model for general questions, comparisons, calculations and follow-ups. **Comparisons** uses every ready report in the workspace. **Evaluation** accepts one question per line, a JSON array, an object containing a questions array, or JSONL. Each item can contain `id`, `question`, `expected`, `expected_doc` and `expected_page`. Expected values are displayed for review and excluded from model prompts.

## Configure the processing services

### Clear and reopen conversations

In **Research chat**, choose **Clear conversation** to start a fresh conversation.
This clears the displayed messages, question input, search results and follow-up
context. Earlier messages remain saved in **History**. Choose **Open conversation**
to review or continue a saved chat. The current conversation survives a browser
reload, and history is isolated by workspace. Existing messages appear together
as the original conversation. Deleting or reprocessing reports still invalidates
results that depended on their previous evidence. Restart the backend after this
update to apply the database migration.

Functional regression checks: `python -m unittest test_regressions -v` (requires
ReportLab for test PDF generation). Browser checks: `python test_browser.py`, with
`PRISM_NODE` pointing to Node.js and `PRISM_PLAYWRIGHT` to the installed Playwright
package; these use Chrome and temporary test data.

Passing functional tests does not establish model answer accuracy. The requested
95–99% accuracy target remains unverified until representative questions and
correct answers are supplied and evaluated against the configured live model.
Review answer correctness, citations, refusals and coverage separately; expected
answers must stay out of model prompts.

Set the following in `.env`, then restart. Model names must be IDs supported by your own provider.

| Setting | Purpose |
| --- | --- |
| PRISM_API_BASE | OpenAI-compatible endpoint for chat completions and embeddings. Local endpoints are supported. |
| PRISM_API_KEY | Authorization for the selected endpoint. Leave blank only for a local service that accepts unauthenticated requests. |
| PRISM_CHAT_MODEL | Model supporting chat completions with JSON-object output. Drafts an answer and checks it in a separate verification request. |
| PRISM_VISION_MODEL | Image-capable chat model supporting inline PNGs and JSON output. Transcribes labeled charts, plots, maps and diagrams during indexing. |
| PRISM_EMBED_MODEL | Embeddings model used for both document chunks and questions. |
| TESSERACT_CMD / PRISM_OCR_LANG | Path to the Tesseract executable and installed recognition language(s). On Windows, installed Windows OCR languages provide a fallback. |
| PRISM_DATA / PRISM_PORT | Persistent data folder and local HTTP port. Defaults are the project's data folder and port 8765. |

Enabling a remote provider sends relevant passages and questions for answering, chunks for embedding, and selected page images for visual transcription to that provider. Configuration indicators show which services are enabled. An actual call checks availability. Reprocess documents after changing OCR, embedding or vision settings. Reprocessing invalidates saved results that depended on the previous index. Export results first if you need to keep them.

## Retrieval and verification

The Python server uses pdfplumber and PDFium to extract and render pages, SQLite for durable metadata and a BM25 full-text index, and NumPy cosine similarity for optional dense vectors. The browser uses native JavaScript modules. The MVP runs in one process with a background indexing worker. A crashed or interrupted index job is picked up on restart.

Text blocks, ruled-table rows, OCR regions and optional visual transcriptions retain physical PDF page numbers. Table rows retain cell order, including empty cells. Retrieval includes the first row of the same table for context. The PDF viewer highlights the associated extraction region in PDF points measured from the top-left of the displayed media box. The original printed page number may differ. Full-page vision evidence carries a null bounding box. Borderless tables can be recovered as text or interpreted visually, and unlabeled chart values can remain unresolved.

Hybrid retrieval fuses lexical and optional semantic rankings, limits source concentration and retrieves surrounding page evidence for named figures. The answer model receives only candidate evidence as factual sources. The server validates citation IDs and exact quoted substrings. A separate model review evaluates sufficiency, units, comparisons and conflicts. Conflict status requires citations from at least two documents. Model verification can miss errors, and relevant evidence outside the retrieved set can be missed. A refusal means the requested claim could not be verified.

## API

Workspace-scoped endpoints accept `?space=<id>`; the default is `main`. Use GET or POST `/api/workspaces` to list or create workspaces. Supply the workspace name as a JSON object when creating one.

| Method | Path | Input or output |
| --- | --- | --- |
| POST | /api/documents/upload?name=filename.pdf | Raw PDF bytes. Multi-file selection calls this once per file. |
| GET | /api/documents | Metadata, progress and warnings |
| GET / DELETE | /api/documents/{id} | Metadata or deletion of a finished document and associated data |
| POST | /api/documents/{id}/process | Empty JSON object to reindex |
| GET | /api/documents/{id}/original | Original bytes |
| GET | /api/documents/{id}/page?page=N | Rendered PDF page |
| GET | /api/documents/{id}/evidence?page=N | Page evidence with coordinates |
| POST | /api/search, /api/chat/ask, /api/chat/compare | JSON question and optional documents array of selected IDs |
| GET | /api/evidence/{id} | Source, physical page, content and bounding box |
| POST | /api/evaluation/run | JSON questions array and optional documents selection |
| GET | /api/evaluation/results, /api/history, /api/export/json | Stored evaluation results, conversation, or all results |

Every completed question result includes id, answer, doc, page, bbox, status and an evidence array. Status is answer, conflict, or refuse. A refusal has null source fields. Missing configured services return a configuration error. Generated results persist in SQLite. Use Configuration to export the whole workspace or Evaluation to export evaluation runs only.

## Demonstration and verification

See the accompanying acceptance report for the real PDF uploads, browser citation check, and model-dependent tests that still require a provider. The application source contains no evaluation documents, predefined answers or fitted practice-question rules.

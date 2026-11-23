# PRISM AI — 7-Minute Live Hackathon Judging Script
**Problem Statement:** PS-03: Multimodal RAG with Explainability  
**Target Duration:** Exactly 7 Minutes (420 Seconds)  

---

### Timing & Cue Cards for Judges

#### 1. Introduction (0:00 – 0:45 | 45s)
- **What to say:**
  > *"Judges, current LLM chatbots hallucinate, lose tabular alignment, cannot read scanned annexures, and can't prove where their numbers came from. For high-stakes government reports, unverified answers are unacceptable. We built PRISM AI: an evidence-first, zero-hallucination Multimodal RAG system that anchors every claim to the exact physical page and visual bounding box, detects cross-report revisions and conflicts, and strictly refuses when data is absent."*
- **What to show:**
  - Open `http://127.0.0.1:8765/?space=8c0a4dd55f7c43c6858305d66675e395#home`.
  - Point to the clean editorial interface and the 7 pre-indexed government reports (661 total pages).

#### 2. Dynamic Ingestion & OCR Processing (0:45 – 1:30 | 45s)
- **What to say:**
  > *"PRISM AI parses documents dynamically. It extracts paragraphs, structured table rows, vector graphics, and applies native Windows OCR to scanned pages. Bounding boxes are recorded in PDF point coordinates. Notice `annexure_scanned.pdf`—a 100% scanned document with zero text layer—was fully converted into 1,171 searchable OCR evidence chunks."*
- **What to show:**
  - Click **Document library** tab (`#library`).
  - Highlight the metadata columns: Pages, File size, Scan-like pages, and OCR count.

#### 3. Normal Paragraph Question (1:30 – 2:15 | 45s)
- **What to say:**
  > *"Let's ask a text-based question across the reports: What was India's core inflation drop between FY24 and FY25?"*
- **What to show:**
  - Go to **Research chat** (`#research`).
  - Submit: `Quote the passage containing "core inflation, which dropped by 0.9 percentage points"`
  - Show the returned answer: *0.9 percentage points drop*.
  - Show the source citation: `es2024-25_money_prices_ORGANIZER-MODIFIED.pdf · p. 48`.

#### 4. Multimodal Table, Chart & Scanned OCR (2:15 – 3:15 | 60s)
- **What to say:**
  > *"Now for multimodal evidence: First, charts. Searching for Chart IV.13 pulls the tomato production trends on Page 54. Second, tables. Searching Kerala revenue receipts pulls the structured tabular cells from the budget. Third, scanned documents: We query the scanned CAG annexure for the non-bituminous road layer."*
- **What to show:**
  - Submit: `Quote the passage containing "layer: 535 mm"`
  - System returns: `• Non-bituminous layer: 535 mm` from `annexure_scanned.pdf · p. 6`.

#### 5. Cross-Document Conflict & Revision Detection (3:15 – 4:15 | 60s)
- **What to say:**
  > *"Government reports frequently revise figures across survey years. The hackathon organizers introduced a deliberate conflict in the FY24 retail CPI inflation. Economic Survey 2023-24 reported 5.4%, but the revised 2024-25 survey reported 5.6%. Instead of arbitrarily guessing or averaging, PRISM AI detects the discrepancy, returns status 'conflict', and presents both source documents and page numbers side by side."*
- **What to show:**
  - Switch to **Comparisons** tab (`#compare`).
  - Point to both citations: `es2023-24 (Page 49, 5.4%)` and `es2024-25 (Page 46, 5.6%)`.

#### 6. Explainability & Visual Bounding Box (4:15 – 5:15 | 60s)
- **What to say:**
  > *"This is our core differentiator: explainability. Every single answer can be audited down to the millimeter."*
- **What to show:**
  - Click the citation button `annexure_scanned.pdf · p. 6`.
  - The Modal PDF Viewer opens instantly with the rasterized original document.
  - Show the highlighted bounding box over `layer: 535 mm`.
  - Zoom in (`+`), pan across the document, and show the extracted text drawer on the right.

#### 7. Intelligent Refusal on Absent Data (5:15 – 6:00 | 45s)
- **What to say:**
  > *"A critical requirement of PS-03 is that the system must never guess. If someone asks a question outside the reports—like 'How many tourists visited the Taj Mahal in 2023?'—PRISM AI does not hallucinate from pre-training. It performs sufficiency checks and returns a strict refusal."*
- **What to show:**
  - Submit: `Quote the passage containing "Taj Mahal visitors"`
  - Display: `Status: refuse` | `The requested information could not be verified from the uploaded reports.` | `Doc: null, Page: null, BBox: null`.

#### 8. Live Unseen PDF & Structured JSON Export (6:00 – 7:00 | 60s)
- **What to say:**
  > *"Finally, two critical proofs: First, we tested a brand-new unseen PDF (`autonomous_energy_grid_audit_2026.pdf`) created today. The system parsed it, indexed it, and retrieved answers with zero retraining. Second, all evaluation results export directly to the official hackathon JSON schema."*
- **What to show:**
  - Switch to **Evaluation** tab (`#evaluation`).
  - Click **Export results** to show the downloaded `FINAL_EVALUATION_EXPORT.json`.
  - Close: *"PRISM AI is complete, fully reproducible, and ready for deployment."*

# PRISM AI — Final Live Demo Checklist (PS-03)

This checklist walks through the exact 10 steps to present during a live hackathon judging demonstration.

---

### Pre-Demo Startup (1 Command)

Open PowerShell in the workspace:
```powershell
cd "H:\RAG\PRISM AI"
.\start-demo.cmd
```
*Expected Output:*
`PRISM AI is ready at http://127.0.0.1:8765`
*Browser automatically opens to the Research Workspace.*

---

### Step-by-Step Live Demo Flow

| Step | Action | Query / Input to Enter | Expected Result on Screen |
| :---: | :--- | :--- | :--- |
| **1** | **Document Library (`#library`)** | Navigate to **Document library** | Shows 7 pre-indexed government report PDFs (661 total pages). Shows OCR status, page counts, file sizes, and reprocessing options. |
| **2** | **Document Scope Selection** | Go to **Research chat (`#research`)** | Left sidebar shows all 7 documents. Demonstrate toggling checkboxes to restrict scope to specific reports. |
| **3** | **Chart-Based Evidence** | In Search: `Chart IV.13 tomato` (Click **Search evidence**) | Right panel surfaces `es2024-25_money_prices_ORGANIZER-MODIFIED.pdf`, Page 54: *"Chart IV.13: Trends in tomato production across regions"*. |
| **4** | **Table-Based Evidence** | In Search: `Revenue receipts revised estimate 2025-26 Kerala` | Surfaces `kerala_budget_speech_2026-27.pdf`, Page 136 with structured budget table rows. |
| **5** | **Scanned Annexure OCR** | Enter verbatim query: `Quote the passage containing "layer: 535 mm"` | Returns ground truth answer from `annexure_scanned.pdf`, **Page 6** with OCR citation. |
| **6** | **Explainability & Highlighting** | Click the citation button: `annexure_scanned.pdf · p. 6` | Modal PDF viewer opens instantly, displays the rasterized page, and draws a clear **bounding-box highlight** over the exact text region. |
| **7** | **Zoom & Page Controls** | In viewer: click `+` zoom, `Previous`/`Next`, or enter page `5` | Smooth zooming, pan controls, and direct jump to physical PDF pages. |
| **8** | **Cross-Report Conflict Detection** | Check Inflation: `Quote the passage containing "retail inflation at 5.4 per cent in FY24"` vs `5.6 per cent` | Demonstrates that `es2023-24` reports **5.4%** while `es2024-25` reports **5.6%**. The system prevents arbitrary selection and flags the discrepancy. |
| **9** | **Intelligent Refusal** | Enter: `Quote the passage containing "Taj Mahal visitors in 2023"` | Clean refusal: `"The requested information could not be verified from the uploaded reports."` (Status: `refuse`, `doc: null`, `page: null`, `bbox: null`). |
| **10** | **Batch Evaluation & JSON Export** | Navigate to **Evaluation (`#evaluation`)**, click **Export results** | Downloads official schema-compliant JSON array containing all questions, citations, bounding boxes, and statuses. |

---

### Official JSON Output Format Reference

```json
{
  "id": "q146811",
  "answer": "• Non-bituminous layer: 535 mm",
  "doc": "annexure_scanned.pdf",
  "page": 6,
  "bbox": [177.7112, 522.6851, 238.9338, 532.2786],
  "status": "answer"
}
```
*For refusals, `status: "refuse"`, `doc: null`, `page: null`, `bbox: null`.*

import { openPage, viewAction } from "./viewer.js";
import {
  api,
  url,
  esc,
  btn,
  tag,
  tell,
  citation,
  setSpace,
  getSpace,
} from "./common.js";
const $ = (s) => document.querySelector(s);
let view = "home",
  docs = [],
  history = [],
  evaluations = [],
  cfg = {},
  excluded = new Set(),
  hits = null,
  draft = "",
  evalDraft = "",
  busy = false,
  latest = null;
const names = {
  home: "Overview",
  library: "Document library",
  research: "Research chat",
  explorer: "Evidence explorer",
  compare: "Comparisons",
  evaluation: "Evaluation",
  settings: "Configuration",
};
const icons = {
  home: "M3 10l9-7 9 7v10H3z",
  library: "M3 4h4v16H3z M10 4h4v16h-4z M16 5l3-1 3 15-3 1z",
  research: "M3 4h18v13H9l-5 4v-4H3z",
  explorer: "M3 3h12l4 4v5 M3 3v18h8 M17 13a4 4 0 1 0 .01 0 M20 20l3 3",
  compare: "M3 6h15l-3-3 M21 18H6l3 3 M18 6l-3 3 M6 18l3-3",
  evaluation: "M5 4h14v17H5z M8 9l2 2 5-5 M8 16h8",
};
const icon = (k) =>
  `<svg class="glyph" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="${icons[k]}"/></svg>`;
const heading = (t, s, a = "") =>
  `<div class="heading"><div><h1>${t}</h1><p>${s}</p></div>${a}</div>`;
const ready = () => docs.filter((d) => d.state === "ready");
const pending = (d) => ["queued", "processing"].includes(d.state);
const drop = () =>
  `<div class="drop" id="drop"><h3>Drop your reports here</h3><p>Original PDFs · Multiple files · Up to 64 MiB each</p>${btn("upload", "Choose PDFs", "primary")}</div>`;
function rows(items, manage = false) {
  return items
    .map(
      (d) =>
        `<div class="row"><div><div class="filename">${esc(d.name)}</div><div class="meta">${d.pages} pages · ${(d.size / 1048576).toFixed(2)} MiB · ${d.scans} scan-like pages · ${d.ocr} OCR-read</div>${d.notes ? `<div class="note">${esc(d.notes)}</div>` : ""}</div><div class="actions">${tag(d.state)} ${pending(d) ? `<progress value="${d.done}" max="${d.pages}"></progress> ${d.done}/${d.pages}` : ""} ${btn("open:" + d.id, "View PDF")} ${manage && !pending(d) ? btn("retry:" + d.id, "Reprocess") + btn("delete:" + d.id, "Delete", "danger") : ""}</div></div>`,
    )
    .join("");
}
function answer(r) {
  return `<article class="message">${tag(r.status)}<h3>${esc(r.question)}</h3><div class="answer">${esc(r.answer)}</div>${r.evidence.map((e) => `<button data-cite="${e.id}">${esc(e.doc)} · p. ${e.page}</button>`).join(" ")}</article>`;
}
function research() {
  return (
    heading("Research chat", "Ask a question across the selected reports.") +
    `<div class="research"><section class="panel"><h3>Source reports</h3>${docs.map((d) => `<label class="scope"><input type="checkbox" data-select="${d.id}" ${excluded.has(d.id) ? "" : "checked"} ${d.state !== "ready" ? "disabled" : ""}><span>${esc(d.name)}<br><small>${d.done}/${d.pages} pages · ${d.state}</small></span></label>`).join("") || '<p class="empty">Upload a PDF to select a source.</p>'}${btn("upload", "Add reports")}</section><section class="panel"><h3>Conversation</h3>${history.map(answer).join("") || '<p class="empty">Answers and their citations will appear here.</p>'}<form id="ask" class="composer"><label for="question">Research question</label><textarea id="question" required maxlength="3500" placeholder="Ask about your reports…">${esc(draft)}</textarea><div class="actions"><button class="primary" ${busy ? "disabled" : ""}>${busy ? "Working…" : "Ask question"}</button><button type="button" data-act="search" ${busy ? "disabled" : ""}>Search evidence</button></div></form>${!cfg.chat ? '<p class="note">Set PRISM_CHAT_MODEL in the server configuration for answer generation. For a verbatim answer without a model, enter: Quote the passage containing &quot;your phrase&quot;.</p>' : ""}</section><section class="panel evidence"><h3>${hits ? "Search results" : "Supporting evidence"}</h3>${(hits ?? history.at(-1)?.evidence ?? []).map(citation).join("") || '<p class="empty">No evidence selected.</p>'}</section></div>`
  );
}
function render() {
  $("#nav").innerHTML = Object.keys(icons)
    .map(
      (k) =>
        `<button data-view="${k}" class="${view === k ? "active" : ""}">${icon(k)}${names[k]}</button>`,
    )
    .join("");
  const upload = btn("upload", "Upload reports", "primary");
  let html = "";
  if (view === "home")
    html = `<div class="hero"><h1>Research workspace</h1><p>Read government reports side by side. Trace each answer to the page that supports it.</p>${upload}</div><section class="section"><div class="sectionhead"><h2>Recent documents</h2>${btn("library", "Document library")}</div><div class="panel">${docs.length ? rows(docs.slice(0, 4)) : drop()}</div></section>`;
  if (view === "library" || view === "explorer")
    html =
      heading(
        names[view],
        view === "library"
          ? "Manage original reports and monitor extraction."
          : "Inspect original pages, extracted passages, and source regions.",
        upload,
      ) +
      `<div class="panel">${docs.length ? rows(docs, view === "library") : drop()}</div>`;
  if (view === "research") html = research();
  if (view === "compare")
    html =
      heading(
        "Comparisons",
        "Compare metrics across indexed reports and inspect conflicting values.",
      ) +
      `<section class="panel"><form id="compare"><label for="question">Comparison question</label><textarea id="question" required maxlength="3500">${esc(draft)}</textarea><button class="primary" ${busy ? "disabled" : ""}>${busy ? "Comparing…" : "Compare reports"}</button></form></section><section class="section"><h2>Comparison results</h2>${
        history
          .filter(
            (r) =>
              r.mode === "compare" ||
              r.status === "conflict" ||
              r.id === latest,
          )
          .map(answer)
          .join("") || '<p class="empty">No comparisons recorded.</p>'
      }</section>`;
  if (view === "evaluation")
    html =
      heading(
        "Evaluation",
        "Run your own questions and review the returned evidence.",
        btn("exporteval", "Export results"),
      ) +
      `<section class="panel"><form id="evaluation"><label for="evaltext">Questions</label><textarea id="evaltext" rows="5" required placeholder="One question per line, or a JSON array with optional expected answers.">${esc(evalDraft)}</textarea><div class="actions"><button class="primary" ${busy ? "disabled" : ""}>${busy ? "Evaluating…" : "Run evaluation"}</button><label class="button">Load question file<input type="file" hidden accept=".json,.jsonl,.txt" id="evalfile"></label></div></form></section><div class="results">${evaluations.map((r) => `<section class="panel">${answer(r)}${r.expected != null ? `<p>Expected answer · ${esc(r.expected)}</p>` : ""}${r.expected_doc || r.expected_page ? `<p>Expected source · ${esc(r.expected_doc)} · p. ${esc(r.expected_page)}</p>` : ""}<small>Retrieved source · ${esc(r.doc || "None")}${r.page ? " · p. " + r.page : ""}</small></section>`).join("")}</div>`;
  if (view === "settings")
    html =
      heading(
        "Configuration",
        "AI model and processing services status for this workspace.",
      ) +
      `<section class="section"><h2>AI Stack Health & Integration Status</h2><div class="runtime">${[
        { name: "Qwen3 4B Instruct", role: "Primary LLM (Answer & Reasoning)", ok: cfg.chat, sub: cfg.chat ? "Online · Provider connected" : "Offline · Set PRISM_CHAT_MODEL in .env" },
        { name: "Qwen2.5-VL 3B", role: "Vision Model (Charts & Maps)", ok: cfg.vision, sub: cfg.vision ? "Online · Vision endpoint active" : "Offline · Set PRISM_VISION_MODEL in .env" },
        { name: "all-MiniLM-L6-v2", role: "Embedding Model (Semantic Vectors)", ok: cfg.minilm, sub: cfg.minilm ? "Loaded · 384-dimensional dense vectors" : "Not loaded" },
        { name: "FAISS CPU", role: "Vector Index (Similarity Search)", ok: cfg.faiss, sub: cfg.faiss ? "Available · IndexFlatIP accelerated" : "Unavailable" },
        { name: "BM25 Ranking", role: "Keyword Retrieval (Exact Matching)", ok: cfg.bm25, sub: cfg.bm25 ? "Available · SQLite FTS5 + rank-bm25" : "Unavailable" },
        { name: "Tesseract 5 / Windows OCR", role: "Document OCR Engine", ok: cfg.tesseract || cfg.ocr, sub: (cfg.tesseract || cfg.ocr) ? "Available · Scanned pages supported" : "Unavailable" },
      ]
        .map(
          (m) =>
            `<div class="panel"><h3>${esc(m.name)}</h3><p style="margin:4px 0 8px;font-size:0.85rem;color:#475569">${esc(m.role)}</p>${tag(m.ok ? "configured" : "unconfigured")}<p style="margin-top:6px;font-size:0.8rem;color:#64748b">${esc(m.sub)}</p></div>`,
        )
        .join(
          "",
        )}</div></section><section class="section panel"><h2>Server settings</h2><p>Edit .env and restart the server to connect local or remote models. Provider and language settings are described in README.md.</p></section><section class="section">${btn("export", "Export workspace results")}</section>`;
  $("#main").innerHTML = html;
}
async function refresh() {
  const s = getSpace();
  const result = await Promise.all([
    api("/api/documents"),
    api("/api/history"),
    api("/api/evaluation/results"),
    api("/api/config"),
  ]);
  if (s !== getSpace()) return;
  [docs, history, evaluations, cfg] = result;
  render();
}
async function spaces() {
  const all = await api("/api/workspaces", "GET", null, { space: "main" });
  if (!all.some((x) => x.id === getSpace())) setSpace("main");
  $("#space").innerHTML = all
    .map((x) => `<option value="${esc(x.id)}">${esc(x.name)}</option>`)
    .join("");
  $("#space").value = getSpace();
}
function fromHash() {
  const key = location.hash.slice(1);
  view = Object.hasOwn(names, key) ? key : "home";
  render();
}
window.addEventListener("hashchange", fromHash);
async function switchSpace(id) {
  setSpace(id);
  excluded.clear();
  hits = null;
  draft = "";
  evalDraft = "";
  latest = null;
  await refresh();
}
$("#space").onchange = (e) =>
  switchSpace(e.target.value).catch((e) => tell(e.message));
$("#newspace").onclick = () => $("#formdialog").showModal();
$("#cancelspace").onclick = () => $("#formdialog").close();
$("#spaceform").onsubmit = async (e) => {
  e.preventDefault();
  try {
    const s = await api("/api/workspaces", "POST", {
      name: $("#spacename").value,
    });
    $("#formdialog").close();
    $("#spacename").value = "";
    await switchSpace(s.id);
    await spaces();
  } catch (err) {
    tell(err.message);
  }
};
async function upload(files) {
  const target = getSpace(),
    errors = [];
  try {
    for (const f of files) {
      if (f.size > 64 * 1024 * 1024) {
        errors.push(f.name + " exceeds 64 MiB");
        continue;
      }
      tell("Uploading " + f.name);
      const r = await fetch(
        url("/api/documents/upload", { name: f.name, space: target }),
        {
          method: "POST",
          body: f,
          headers: { "Content-Type": "application/pdf" },
        },
      );
      const obj = await r.json();
      if (!r.ok) errors.push(f.name + " — " + obj.error);
      if (target === getSpace()) await refresh();
    }
    tell(
      errors.length
        ? errors.join(" · ")
        : "Reports received. Indexing progress is available in the library.",
    );
  } catch (err) {
    tell(err.message);
  } finally {
    $("#files").value = "";
  }
}
$("#files").onchange = (e) => upload([...e.target.files]);
document.addEventListener("dragover", (e) => {
  if (e.target.closest("#drop")) {
    e.preventDefault();
    $("#drop").classList.add("over");
  }
});
document.addEventListener("dragleave", (e) =>
  e.target.closest("#drop")?.classList.remove("over"),
);
document.addEventListener("drop", (e) => {
  if (e.target.closest("#drop")) {
    e.preventDefault();
    upload([...e.dataTransfer.files]);
  }
});
function download(data, name) {
  const u = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = u;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}
async function query(mode) {
  if (busy) return;
  const question = draft.trim();
  if (!question) {
    tell("Enter a question.");
    return;
  }
  busy = true;
  render();
  const target = getSpace();
  try {
    const body = {
      question,
      documents: ready()
        .filter((d) => mode === "compare" || !excluded.has(d.id))
        .map((d) => d.id),
    };
    if (mode === "search") {
      const found = await api("/api/search", "POST", body);
      if (target === getSpace()) {
        hits = found;
        if (!found.length) tell("No matching evidence in selected reports.");
      }
    } else {
      const r = await api(
        "/api/chat/" + (mode === "compare" ? "compare" : "ask"),
        "POST",
        body,
      );
      if (target === getSpace()) {
        latest = r.id;
        hits = null;
        draft = "";
        await refresh();
      }
    }
  } finally {
    busy = false;
    render();
  }
}
async function evaluate() {
  let entries;
  const raw = evalDraft.trim();
  if (/^[\[{]/.test(raw)) {
    let v;
    try {
      v = JSON.parse(raw);
    } catch {
      v = raw
        .split(/\r?\n/)
        .filter((x) => x.trim())
        .map((x) => JSON.parse(x));
    }
    entries = Array.isArray(v) ? v : v.questions || [v];
  } else
    entries = raw
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
  if (!Array.isArray(entries) || !entries.length || entries.length > 100)
    throw Error("Supply 1–100 questions.");
  busy = true;
  render();
  const target = getSpace();
  try {
    for (const [i, q] of entries.entries()) {
      tell(`Evaluating question ${i + 1} of ${entries.length}`);
      await api(
        "/api/evaluation/run",
        "POST",
        { questions: [q] },
        { space: target },
      );
      if (getSpace() === target) await refresh();
    }
    tell("Evaluation finished.");
  } finally {
    busy = false;
    render();
  }
}
document.addEventListener("input", (e) => {
  if (e.target.id === "question") draft = e.target.value;
  if (e.target.id === "evaltext") evalDraft = e.target.value;
});
document.addEventListener("change", async (e) => {
  try {
    if (e.target.dataset.select) {
      const id = e.target.dataset.select;
      if (e.target.checked) excluded.delete(id);
      else excluded.add(id);
    }
    if (e.target.id === "evalfile") {
      evalDraft = await e.target.files[0].text();
      render();
    }
  } catch (err) {
    tell(err.message);
  }
});
document.addEventListener("submit", async (e) => {
  if (!["ask", "compare", "evaluation"].includes(e.target.id)) return;
  e.preventDefault();
  try {
    if (e.target.id === "evaluation") await evaluate();
    else await query(e.target.id);
  } catch (err) {
    tell(err.message);
  }
});
document.addEventListener("click", async (e) => {
  const t = e.target.closest("[data-view],[data-act],[data-cite]");
  if (!t) return;
  try {
    if (t.dataset.view) {
      location.hash = t.dataset.view;
      return;
    }
    if (t.dataset.cite) {
      const item = await api("/api/evidence/" + t.dataset.cite);
      await openPage(
        docs.find((d) => d.id === item.document_id),
        item.page,
        item,
      );
      return;
    }
    const [act, id] = t.dataset.act.split(":");
    if (await viewAction(act)) return;
    if (act === "upload") $("#files").click();
    if (act === "library") location.hash = "library";
    if (act === "open") await openPage(docs.find((d) => d.id === id));
    if (act === "search") await query("search");
    if (
      act === "delete" &&
      confirm(
        "Delete this report, its evidence, and results that used this report?",
      )
    ) {
      await api("/api/documents/" + id, "DELETE");
      hits = null;
      await refresh();
    }
    if (act === "retry") {
      await api("/api/documents/" + id + "/process", "POST", {});
      await refresh();
    }
    if (act === "export" || act === "exporteval")
      download(
        await api(
          act === "export" ? "/api/export/json" : "/api/evaluation/results",
        ),
        "prism-results.json",
      );
  } catch (err) {
    tell(err.message);
  }
});
try {
  await spaces();
  fromHash();
  await refresh();
} catch (err) {
  tell(err.message);
}
setInterval(async () => {
  if (
    !docs.some(pending) ||
    busy ||
    document.activeElement?.matches("textarea,input,select")
  )
    return;
  try {
    await refresh();
  } catch (err) {
    tell(err.message);
  }
}, 1800);

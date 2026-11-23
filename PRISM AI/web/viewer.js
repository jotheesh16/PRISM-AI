import { api, url, esc, btn, citation, tell } from "./common.js";
let doc,
  page,
  item,
  zoom = 1,
  seq = 0;
const dialog = document.querySelector("#viewer");
export async function openPage(d, n = 1, e = null, keep = false) {
  if (!d) return;
  const request = ++seq;
  doc = d;
  page = n;
  item = e;
  if (!keep) zoom = 1;
  const records = await api(
    "/api/documents/" + doc.id + "/evidence",
    "GET",
    null,
    { page },
  );
  if (seq !== request) return;
  const b = item?.bbox;
  const rect = b
    ? `<div class="highlight" style="left:${(100 * b[0]) / item.width}%;top:${(100 * b[1]) / item.height}%;width:${(100 * (b[2] - b[0])) / item.width}%;height:${(100 * (b[3] - b[1])) / item.height}%"></div>`
    : "";
  document.querySelector("#viewerbody").innerHTML =
    `<div class="bar"><h2>${esc(d.name)}</h2>${btn("close", "Close")}</div><div class="bar"><div class="actions"><button data-act="prev" ${page <= 1 ? "disabled" : ""}>Previous</button><label>Page <input id="pagenum" type="number" min="1" max="${doc.pages}" value="${page}" style="width:5rem"></label> of ${doc.pages}<button data-act="next" ${page >= doc.pages ? "disabled" : ""}>Next</button></div><div class="actions"><button data-act="smaller" aria-label="Zoom out">−</button>${Math.round(zoom * 100)}%<button data-act="larger" aria-label="Zoom in">＋</button><a class="button" target="_blank" rel="noopener" href="${url("/api/documents/" + doc.id + "/original")}#page=${page}">Original PDF</a></div></div><div class="vgrid"><div class="paperwell"><div class="paper" style="width:${zoom * 100}%"><img alt="Original PDF page ${page}" src="${url("/api/documents/" + doc.id + "/page", { page })}">${rect}</div></div><div class="vside">${item ? `<h3>Selected evidence</h3><div class="quote">${esc(item.quote || item.text)}</div><small>${b ? "Highlighted extraction region" : "Page citation only · region-level highlighting unavailable"}</small>` : ""}<h3>Page evidence</h3>${records.map(citation).join("") || '<p class="empty">No extracted evidence on this page.</p>'}</div></div>`;
  const image = dialog.querySelector("img");
  image.onerror = () => {
    image.alt =
      "Page rendering failed. Open the original PDF to inspect this page.";
  };
  image.onload = () =>
    dialog
      .querySelector(".highlight")
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  if (!dialog.open) dialog.showModal();
}
dialog.addEventListener("change", (e) => {
  if (e.target.id === "pagenum") {
    const n = Number(e.target.value);
    if (Number.isInteger(n) && n >= 1 && n <= doc.pages)
      openPage(doc, n).catch((err) => tell(err.message));
  }
});
export async function viewAction(act) {
  if (!["close", "prev", "next", "larger", "smaller"].includes(act))
    return false;
  if (act === "close") {
    seq++;
    dialog.close();
  } else if (act === "prev" || act === "next")
    await openPage(doc, page + (act === "prev" ? -1 : 1));
  else {
    zoom = Math.min(3, Math.max(0.5, zoom + (act === "larger" ? 0.25 : -0.25)));
    await openPage(doc, page, item, true);
  }
  return true;
}

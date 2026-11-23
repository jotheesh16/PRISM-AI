let space =
  new URLSearchParams(location.search).get("space") ||
  localStorage.getItem("prism-space") ||
  "main";
let apiBase =
  (typeof window !== "undefined" && window.__PRISM_API_BASE__) ||
  localStorage.getItem("prism-api-base") ||
  "";
export const getSpace = () => space;
export function setSpace(id) {
  space = id;
  localStorage.setItem("prism-space", id);
}
export const getApiBase = () => apiBase;
export function setApiBase(base) {
  apiBase = (base || "").trim().replace(/\/+$/, "");
  localStorage.setItem("prism-api-base", apiBase);
}
export const url = (path, params = {}) =>
  (apiBase || "") + path + "?" + new URLSearchParams({ space, ...params });
export async function api(path, method = "GET", body, params) {
  const res = await fetch(url(path, params), {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw Error(data.error || "Request failed");
  return data;
}
export const esc = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export const btn = (act, label, cls = "") =>
  `<button class="${cls}" data-act="${act}">${label}</button>`;
const labels = {
  answer: "Verified",
  refuse: "Insufficient evidence",
  conflict: "Conflict",
};
export const tag = (s) =>
  `<span class="tag ${esc(s)}">${esc(labels[s] || s)}</span>`;
export const citation = (e) =>
  `<button class="cite" data-cite="${e.id}">${esc(e.doc)} · p. ${e.page}<small>${esc(e.kind)} · ${esc((e.quote || e.text).slice(0, 150))}</small></button>`;
let timer;
export function tell(msg) {
  const t = document.querySelector("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(timer);
  timer = setTimeout(() => (t.hidden = true), 7000);
}

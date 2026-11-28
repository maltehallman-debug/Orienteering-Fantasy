/* Small helpers for building the dashboard's interface. Text always goes in as text, never as HTML. */
export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v; else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "html") throw new Error("no html"); else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}
export const clear = el => { while (el.firstChild) el.removeChild(el.firstChild); return el; };
export const when = iso => { if (!iso) return "–"; const d = new Date(iso); return d.toLocaleDateString("sv-SE", { day: "numeric", month: "short" }) + " " + d.toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" }); };
export const ago = iso => { if (!iso) return "aldrig"; const s = (Date.now() - new Date(iso)) / 1000; if (s < 60) return "nyss"; if (s < 3600) return Math.round(s / 60) + " min sedan"; if (s < 86400) return Math.round(s / 3600) + " tim sedan"; return Math.round(s / 86400) + " dagar sedan"; };

let toastT;
export function toast(msg, tone = "") {
  let t = document.getElementById("toast"); if (!t) { t = h("div", { id: "toast", role: "status", "aria-live": "polite" }); document.body.appendChild(t); }
  t.className = "toast show " + tone; t.textContent = msg; clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), 3200);
}
/* a confirmation step inside the page (no browser dialogs) */
export function ask(title, text, okLabel = "Fortsätt", danger = false, withNote = false) {
  return new Promise(res => {
    const note = withNote ? h("input", { class: "input", placeholder: "Kort beskrivning (valfritt)", maxlength: "300" }) : null;
    const close = v => { m.remove(); res(v); };
    const m = h("div", { class: "modal-bg", onclick: e => { if (e.target === m) close(null); } },
      h("div", { class: "modal", role: "dialog", "aria-modal": "true" }, h("h3", {}, title), h("p", { class: "muted" }, text), note,
        h("div", { class: "row end" }, h("button", { class: "btn ghost", onclick: () => close(null) }, "Avbryt"),
          h("button", { class: "btn " + (danger ? "danger" : "primary"), onclick: () => close(withNote ? (note.value || "") : true) }, okLabel))));
    document.body.appendChild(m); (note || m.querySelector(".btn.primary,.btn.danger")).focus();
  });
}
export const field = (label, input, hint) => h("label", { class: "field" }, h("span", { class: "lbl" }, label), input, hint ? h("span", { class: "hint" }, hint) : null);
export const card = (title, ...kids) => h("section", { class: "card" }, title ? h("h3", { class: "card-t" }, title) : null, ...kids);
export const pill = (text, tone = "") => h("span", { class: "pill " + tone }, text);
export const icon = name => { const s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", "ic"); s.setAttribute("aria-hidden", "true");
  const p = { dash: "M3 13h8V3H3zm10 8h8V11h-8zM3 21h8v-6H3zm10-18v6h8V3z", edit: "M4 20h4L19 9l-4-4L4 16zM14 6l4 4", eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zm10 3a3 3 0 100-6 3 3 0 000 6z",
    term: "M4 5h16v14H4zM7 9l3 3-3 3m5 0h5", test: "M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3", flag: "M5 21V4h11l-1 4 1 4H5", hist: "M3 12a9 9 0 103-6.7M3 4v4h4M12 7v5l3 3",
    theme: "M12 3a9 9 0 100 18c1.5 0 2-1 2-2s-1-2 0-3 3 0 4-1 2-3 2-4a9 9 0 00-8-8zM7.5 12a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm4-4a1.5 1.5 0 110-3 1.5 1.5 0 010 3z",
    out: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h11", moon: "M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z", undo: "M9 14L4 9l5-5M4 9h10a6 6 0 010 12h-3", redo: "M15 14l5-5-5-5M20 9H10a6 6 0 000 12h3",
    cursor: "M5 3l14 7-6 2-2 6z", plus: "M12 5v14M5 12h14", menu: "M4 7h16M4 12h16M4 17h16" }[name] || "";
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path"); path.setAttribute("d", p); s.appendChild(path); return s; };

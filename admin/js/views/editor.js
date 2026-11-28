/* The visual editor: the site in a frame on the left, click an element, edit it in the panel on the right. Every edit
   goes into the draft and is shown in the frame at once; the real site changes only when you publish. */
import { h, clear, field, toast, icon } from "../ui.js";
import { S, change, on, undo, redo } from "../store.js";
import { makeFrame } from "../frame.js";
import { TABS, ROLES, DEVICES, FONTS } from "../config.js";

const PX = v => (v === "" || v == null ? "" : /^-?\d+(\.\d+)?$/.test(String(v).trim()) ? String(v).trim() + "px" : String(v).trim());
const rgb2hex = c => { const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?/.exec(c || ""); if (!m) return /^#/.test(c) ? c : "#000000"; if (m[4] === "0") return ""; return "#" + [m[1], m[2], m[3]].map(x => (+x).toString(16).padStart(2, "0")).join(""); };

export function editorView(root, state) {
  let sel = null;   // info about the selected element, from the frame
  const top = h("div", { class: "toolbar" });
  const canvas = h("div", { class: "canvas" });
  const panel = h("aside", { class: "inspector" });
  root.append(h("div", { class: "editor" }, h("div", { class: "editor-main" }, top, canvas), panel));

  const f = makeFrame(canvas, { tab: state.tab || "home", role: state.role || "guest", device: state.device || "mobile", cfg: () => S.draft });
  const tabSel = h("select", { class: "input sm", "aria-label": "Sida", onchange: e => { f.setTab(e.target.value); state.tab = e.target.value; sel = null; drawPanel(); } }, TABS.map(([k, l]) => h("option", { value: k }, l)));
  const roleSel = h("select", { class: "input sm", "aria-label": "Vy", onchange: e => { f.setRole(e.target.value); state.role = e.target.value; } }, ROLES.map(([k, l]) => h("option", { value: k }, l)));
  tabSel.value = f.tab; roleSel.value = f.role;
  const devs = h("div", { class: "seg" }, DEVICES.map(([k, l]) => h("button", { class: f.device === k ? "on" : "", "data-dev": k, onclick: e => { f.setDevice(k); state.device = k; devs.querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.dev === k)); } }, l)));
  let picking = true;
  const pickBtn = h("button", { class: "btn sm on", title: "Klicka på ett element i sidan för att redigera det", onclick: () => { picking = !picking; pickBtn.classList.toggle("on", picking); f.send({ t: "pick", on: picking }); } }, icon("cursor"), "Välj element");
  top.append(h("div", { class: "row wrap" }, tabSel, roleSel, devs, pickBtn,
    h("button", { class: "btn sm ghost", title: "Ångra (Ctrl+Z)", onclick: () => undo() || toast("Inget att ångra") }, icon("undo")),
    h("button", { class: "btn sm ghost", title: "Gör om", onclick: () => redo() || toast("Inget att göra om") }, icon("redo")),
    h("button", { class: "btn sm ghost", onclick: () => f.load() }, "Ladda om")));

  f.on("ready", () => f.send({ t: "pick", on: picking }));
  f.on("tab", m => { tabSel.value = m.tab; state.tab = m.tab; });
  f.on("select", m => { sel = m.info; drawPanel(); });
  const off = on(w => { if (w === "draft" || w === "published" || w === "start") { f.push(S.draft); drawPanel(); } });

  /* ---------- the panel ---------- */
  function setStyle(prop, val) { const s = sel.sel; change(d => { d.styles[s] = d.styles[s] || {}; if (val === "" || val == null) delete d.styles[s][prop]; else d.styles[s][prop] = val; if (!Object.keys(d.styles[s]).length) delete d.styles[s]; }, `Stil ${prop} på ${short(s)}`); }
  const short = s => s.length > 48 ? "…" + s.slice(-46) : s;
  const cur = prop => (S.draft.styles[sel.sel] || {})[prop] ?? "";
  const num = (prop, label) => { const i = h("input", { class: "input sm", value: cur(prop), placeholder: sel.styles[prop] || "", onchange: e => setStyle(prop, PX(e.target.value)) }); return field(label, i); };
  const color = (prop, label) => {
    const v = cur(prop) || rgb2hex(sel.styles[prop]); const c = h("input", { type: "color", value: /^#[0-9a-f]{6}$/i.test(v) ? v : "#ffffff", oninput: e => setStyle(prop, e.target.value) });
    return field(label, h("div", { class: "row" }, c, h("input", { class: "input sm", value: cur(prop), placeholder: sel.styles[prop], onchange: e => setStyle(prop, e.target.value.trim()) }),
      h("button", { class: "btn xs ghost", title: "Som sajten", onclick: () => setStyle(prop, "") }, "×")));
  };

  function drawPanel() {
    clear(panel);
    if (!sel) {
      panel.append(h("h3", { class: "card-t" }, "Redigera"), h("p", { class: "muted" }, "Klicka på ett element i sidan till vänster: en rubrik, en text, en knapp, en bild eller ett kort. Här visas då allt du kan ändra."));
      const edited = [...new Set([...Object.keys(S.draft.styles), ...Object.keys(S.draft.texts), ...Object.keys(S.draft.attrs), ...S.draft.hidden])];
      if (edited.length) panel.append(h("h4", { class: "sub-t" }, `Ändrade element (${edited.length})`), h("div", { class: "list" }, edited.map(s => h("button", { class: "list-i", onclick: () => f.send({ t: "highlight", sel: s }) }, h("code", {}, short(s))))));
      panel.append(blockForm(null));
      return;
    }
    const s = sel.sel, hidden = S.draft.hidden.includes(s);
    panel.append(
      h("div", { class: "insp-head" }, h("span", { class: "pill" }, sel.tag), h("code", { class: "sel", title: s }, short(s)),
        h("div", { class: "row" }, h("button", { class: "btn xs ghost", onclick: () => f.send({ t: "highlight", sel: s }) }, "Visa"),
          h("button", { class: "btn xs ghost", onclick: () => { navigator.clipboard?.writeText(s).then(() => toast("Väljaren kopierad"), () => toast(s)); } }, "Kopiera"),
          h("button", { class: "btn xs danger", onclick: () => { change(d => { delete d.styles[s]; delete d.texts[s]; delete d.attrs[s]; d.hidden = d.hidden.filter(x => x !== s); d.moves = d.moves.filter(m => m.sel !== s && m.before !== s); }, "Återställt " + short(s)); toast("Elementet är som på sajten igen"); } }, "Återställ"))));
    /* text */
    if (sel.textEditable) panel.append(sec("Text", field("Text", h("textarea", { class: "input", rows: "3", oninput: e => change(d => { if (e.target.value === sel.text && !(s in d.texts)) return; d.texts[s] = e.target.value; }, "Text på " + short(s)) }, S.draft.texts[s] ?? sel.text),
      h("button", { class: "btn xs ghost", onclick: () => change(d => { delete d.texts[s]; }, "Text återställd") }, "Originaltext"))));
    else panel.append(sec("Text", h("p", { class: "muted sm" }, "Elementet innehåller andra element. Välj texten inuti för att ändra den.")));
    /* typography */
    panel.append(sec("Typografi", h("div", { class: "grid2" }, num("font-size", "Storlek"),
      field("Vikt", h("select", { class: "input sm", onchange: e => setStyle("font-weight", e.target.value) }, [["", "Som sajten (" + sel.styles["font-weight"] + ")"], ["400", "Normal"], ["600", "Halvfet"], ["700", "Fet"], ["800", "Extra fet"], ["900", "Svart"]].map(([v, l]) => h("option", { value: v, selected: cur("font-weight") === v }, l)))),
      field("Typsnitt", h("select", { class: "input sm", onchange: e => setStyle("font-family", e.target.value) }, FONTS.map(([v, l]) => h("option", { value: v, selected: cur("font-family") === v }, l)))),
      field("Justering", h("select", { class: "input sm", onchange: e => setStyle("text-align", e.target.value) }, [["", "Som sajten"], ["left", "Vänster"], ["center", "Centrerad"], ["right", "Höger"]].map(([v, l]) => h("option", { value: v, selected: cur("text-align") === v }, l))))),
      color("color", "Textfärg"), color("background-color", "Bakgrund")));
    /* spacing and size */
    const four = (base, label) => h("div", {}, h("span", { class: "lbl" }, label), h("div", { class: "grid4" }, ["top", "right", "bottom", "left"].map((side, k) => {
      const p = base + "-" + side; return h("input", { class: "input sm", title: label + " " + ["upp", "höger", "ner", "vänster"][k], value: cur(p), placeholder: sel.styles[p], onchange: e => setStyle(p, PX(e.target.value)) }); })));
    panel.append(sec("Avstånd och storlek", four("margin", "Marginal (upp, höger, ner, vänster)"), four("padding", "Padding (upp, höger, ner, vänster)"),
      h("div", { class: "grid3" }, num("width", "Bredd"), num("height", "Höjd"), num("border-radius", "Hörn"))));
    /* visibility and order */
    const stable = !/:nth-child/.test(s.split(">").pop());
    panel.append(sec("Synlighet och ordning",
      h("label", { class: "switch" }, h("input", { type: "checkbox", checked: !hidden, onchange: e => change(d => { d.hidden = d.hidden.filter(x => x !== s); if (!e.target.checked) d.hidden.push(s); }, (e.target.checked ? "Visar " : "Döljer ") + short(s)) }), h("span", {}, "Visas på sajten")),
      stable ? h("p", { class: "muted sm" }, "Flytta elementet genom att välja det element det ska ligga före:") : h("p", { class: "muted sm" }, "Det här elementet saknar ett stabilt namn (det pekas ut med sin plats), så det kan inte flyttas säkert."),
      stable ? h("div", { class: "row" }, h("button", { class: "btn xs", onclick: () => { toast("Klicka på elementet det ska ligga före"); const once = m => { f.handlers.select = f.handlers.select.filter(x => x !== once); change(d => { d.moves = d.moves.filter(x => x.sel !== s); d.moves.push({ sel: s, before: m.info.sel }); }, "Flyttat " + short(s)); }; f.on("select", once); } }, "Flytta före …"),
        h("button", { class: "btn xs ghost", onclick: () => change(d => { d.moves = d.moves.filter(x => x.sel !== s); }, "Flytt ångrad") }, "Ursprunglig plats")) : null));
    /* links, buttons, images */
    const at = S.draft.attrs[s] || {};
    const setAttr = (k, v) => change(d => { d.attrs[s] = Object.assign({}, d.attrs[s]); if (v === "") delete d.attrs[s][k]; else d.attrs[s][k] = v; if (!Object.keys(d.attrs[s]).length) delete d.attrs[s]; }, `${k} på ${short(s)}`);
    if (sel.tag === "a") panel.append(sec("Länk", field("Adress", h("input", { class: "input sm", value: at.href ?? sel.href ?? "", placeholder: "https://…", onchange: e => setAttr("href", e.target.value.trim()) }), "Bara https-adresser.")));
    if (sel.isButton) panel.append(sec("Knappens funktion", field("Öppnar sidan", h("select", { class: "input sm", onchange: e => setAttr("tab", e.target.value) }, [["", sel.dataTab ? "Som nu (" + sel.dataTab + ")" : "Som nu"], ...TABS].map(([v, l]) => h("option", { value: v, selected: at.tab === v }, l)))),
      h("p", { class: "muted sm" }, "Knappar som gör något annat (spara, köpa, logga in) behåller sin funktion. Här kan du styra vilken sida en navigeringsknapp öppnar.")));
    if (sel.tag === "img") panel.append(sec("Bild", field("Bildadress", h("input", { class: "input sm", value: at.src ?? sel.src ?? "", placeholder: "https://… eller img/…", onchange: e => setAttr("src", e.target.value.trim()) }))));
    panel.append(blockForm(s));
  }
  const sec = (title, ...kids) => h("details", { class: "sec", open: true }, h("summary", {}, title), h("div", { class: "sec-b" }, ...kids));

  /* a new section after the selected element (or after the page's last card) */
  function blockForm(after) {
    const hd = h("input", { class: "input sm", placeholder: "Rubrik" }), bd = h("textarea", { class: "input sm", rows: "2", placeholder: "Text" }),
      im = h("input", { class: "input sm", placeholder: "Bild (https://… eller img/…), valfritt" }), lb = h("input", { class: "input sm", placeholder: "Knapptext, valfritt" }),
      hr = h("input", { class: "input sm", placeholder: "Knappens mål: https://… eller #team, #leagues …" });
    const blocks = S.draft.blocks.filter(b => !b.tab || b.tab === "all" || b.tab === f.tab);
    return sec("Egna sektioner",
      blocks.length ? h("div", { class: "list" }, blocks.map(b => h("div", { class: "list-i" }, h("b", {}, b.heading || "(utan rubrik)"), h("span", { class: "muted sm" }, " efter " + short(b.after)),
        h("button", { class: "btn xs danger", onclick: () => change(d => { d.blocks = d.blocks.filter(x => x.id !== b.id); }, "Sektion borttagen") }, "Ta bort")))) : null,
      h("p", { class: "muted sm" }, after ? "Läggs direkt efter det valda elementet, på den här sidan." : "Välj först ett element: sektionen läggs efter det."),
      hd, bd, im, h("div", { class: "grid2" }, lb, hr),
      h("button", { class: "btn sm primary", disabled: !after, onclick: () => {
        if (!hd.value.trim() && !bd.value.trim()) return toast("Skriv en rubrik eller en text");
        change(d => { d.blocks.push({ id: "b" + Date.now().toString(36), tab: f.tab, after, heading: hd.value.trim(), body: bd.value.trim(), img: im.value.trim(), label: lb.value.trim(), href: hr.value.trim() }); }, "Ny sektion"); toast("Sektionen är tillagd i utkastet"); } }, icon("plus"), "Lägg till sektion"));
  }
  const key = e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) { e.preventDefault(); e.shiftKey ? redo() : undo(); } };
  addEventListener("keydown", key);
  drawPanel();
  return () => { off(); f.destroy(); removeEventListener("keydown", key); };
}

/* Förhandsgranska: the same page as a phone, a tablet and a computer at once, for any role, with the draft or with
   what is published. Runs in the sandbox, so trying things here touches no real account. */
import { h, card } from "../ui.js";
import { S, on } from "../store.js";
import { makeFrame } from "../frame.js";
import { TABS, ROLES, DEVICES } from "../config.js";

export function previewView(root, state) {
  let which = "draft";
  const grid = h("div", { class: "device-grid" });
  const cfg = () => which === "draft" ? S.draft : S.published;
  const frames = [];
  const tabSel = h("select", { class: "input sm", onchange: e => frames.forEach(f => f.setTab(e.target.value)) }, TABS.map(([k, l]) => h("option", { value: k }, l)));
  const roleSel = h("select", { class: "input sm", onchange: e => frames.forEach(f => f.setRole(e.target.value)) }, ROLES.map(([k, l]) => h("option", { value: k }, l)));
  roleSel.value = state.role || "guest"; tabSel.value = state.tab || "home";
  const seg = h("div", { class: "seg" }, [["draft", "Utkast"], ["published", "Publicerat"]].map(([k, l]) => h("button", { class: k === which ? "on" : "", "data-k": k, onclick: () => { which = k; seg.querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.k === k)); frames.forEach(f => f.push(cfg())); } }, l)));
  root.append(h("div", { class: "page-head" }, h("h2", {}, "Förhandsgranska"), h("p", { class: "muted" }, "Byt sida, vy och version. Allt körs i ett testläge: inget sparas och inga riktiga konton påverkas.")),
    h("div", { class: "toolbar" }, h("div", { class: "row wrap" }, tabSel, roleSel, seg, h("button", { class: "btn sm ghost", onclick: () => frames.forEach(f => f.load()) }, "Ladda om"))), grid);
  DEVICES.forEach(([k, l]) => { const col = h("div", { class: "device-col" }, h("span", { class: "lbl" }, l)); grid.appendChild(col);
    frames.push(makeFrame(col, { device: k, tab: tabSel.value, role: roleSel.value, cfg, fitHeight: true, fixedHeight: 640 })); });
  const off = on(w => { if (w === "draft" && which === "draft") frames.forEach(f => f.push(S.draft)); if (w === "published") frames.forEach(f => f.push(cfg())); });
  return () => { off(); frames.forEach(f => f.destroy()); };
}

/* Funktioner och tema: switch sections on and off, the banner across the top, and the design tokens (colours, corners,
   text sizes). Everything goes into the draft. */
import { h, card, field, toast } from "../ui.js";
import { S, change, on } from "../store.js";
import { FLAGS, TOKENS } from "../config.js";

export function featuresView(root) {
  const body = h("div", {});
  root.append(h("div", { class: "page-head" }, h("h2", {}, "Funktioner och tema"), h("p", { class: "muted" }, "Slå av och på delar av sajten, visa ett meddelande överst och justera färger, hörn och textstorlekar. Allt hamnar i utkastet.")), body);
  const draw = () => {
    const d = S.draft;
    const flags = card("Funktioner", h("div", { class: "list" }, FLAGS.map(([k, l]) => h("label", { class: "list-i switch" },
      h("input", { type: "checkbox", checked: d.flags[k] !== false, onchange: e => change(x => { if (e.target.checked) delete x.flags[k]; else x.flags[k] = false; }, "Funktion " + l + (e.target.checked ? " på" : " av")) }),
      h("span", {}, l), h("code", { class: "muted sm" }, k)))));
    const bt = h("input", { class: "input", maxlength: "200", value: d.banner.text || "", placeholder: "T.ex. Lanseringen är 1 mars!" });
    const tone = h("select", { class: "input sm" }, [["info", "Marinblå"], ["warn", "Gul"]].map(([v, l]) => h("option", { value: v, selected: (d.banner.tone || "info") === v }, l)));
    const banner = card("Meddelande överst", field("Text", bt), field("Färg", tone),
      h("div", { class: "row" }, h("button", { class: "btn sm primary", onclick: () => { if (!bt.value.trim()) return toast("Skriv en text"); change(x => { x.banner = { on: true, text: bt.value.trim(), tone: tone.value }; }, "Banner på"); toast("Bannern är på i utkastet"); } }, d.banner.on ? "Uppdatera" : "Visa meddelandet"),
        d.banner.on ? h("button", { class: "btn sm ghost", onclick: () => change(x => { x.banner = {}; }, "Banner av") }, "Ta bort") : null));
    const theme = card("Tema", h("div", { class: "grid2" }, TOKENS.map(([k, l, type, def]) => {
      const v = d.tokens[k] || "";
      const set = val => change(x => { if (!val || val === def) delete x.tokens[k]; else x.tokens[k] = val; }, "Tema " + l);
      return field(l, type === "color" ? h("div", { class: "row" }, h("input", { type: "color", value: v || def, oninput: e => set(e.target.value) }), h("code", { class: "muted sm" }, v || def + " (som sajten)"), v ? h("button", { class: "btn xs ghost", onclick: () => set("") }, "×") : null)
        : h("div", { class: "row" }, h("input", { class: "input sm", value: v, placeholder: def, onchange: e => set(/^\d+(\.\d+)?$/.test(e.target.value.trim()) ? e.target.value.trim() + "px" : e.target.value.trim()) }), v ? h("button", { class: "btn xs ghost", onclick: () => set("") }, "×") : null));
    })), h("button", { class: "btn sm ghost", onclick: () => change(x => { x.tokens = {}; }, "Tema återställt") }, "Återställ temat"));
    body.replaceChildren(h("div", { class: "cols" }, flags, h("div", {}, banner, theme)));
  };
  const off = on(w => { if (w !== "saved") draw(); }); draw();
  return off;
}

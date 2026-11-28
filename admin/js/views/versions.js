/* Utkast och versioner: what is saved, what is published, what differs, the log of changes, earlier versions to look at
   or restore, and export/import as a file. */
import { h, card, pill, when, ago, toast, ask } from "../ui.js";
import { S, on, diff, dirty, unpublished, save, publish, restore, discardToPublished, replaceDraft, undo, redo } from "../store.js";

export function versionsView(root) {
  const body = h("div", {});
  root.append(h("div", { class: "page-head" }, h("h2", {}, "Utkast och versioner"), h("p", { class: "muted" }, "Spara som utkast, se skillnaden mot det publicerade, publicera när du är nöjd eller gå tillbaka till en tidigare version.")), body);
  const table = rows => rows.length ? h("table", { class: "tbl" }, h("thead", {}, h("tr", {}, h("th", {}, "Typ"), h("th", {}, "Vad"), h("th", {}, "Publicerat"), h("th", {}, "Utkast"))),
    h("tbody", {}, rows.map(([g, k, a, b]) => h("tr", {}, h("td", {}, g), h("td", {}, h("code", {}, k)), h("td", { class: "muted" }, a == null || a === "" ? "–" : String(a)), h("td", {}, b == null || b === "" ? "–" : String(b)))))) : h("p", { class: "muted" }, "Utkastet är samma som det publicerade.");
  const draw = () => {
    const d = diff(S.published, S.draft);
    const state = card("Läge",
      h("div", { class: "stat-grid" },
        h("div", { class: "stat " + (dirty() ? "warn" : "ok") }, h("span", { class: "lbl" }, "Utkast"), h("b", {}, dirty() ? "Osparat" : "Sparat"), h("span", { class: "muted sm" }, S.savedAt ? when(S.savedAt) : "–")),
        h("div", { class: "stat " + (unpublished() ? "warn" : "ok") }, h("span", { class: "lbl" }, "Publicerat"), h("b", {}, unpublished() ? d.length + " ändringar kvar" : "Aktuellt"), h("span", { class: "muted sm" }, S.publishedAt ? when(S.publishedAt) : "–"))),
      h("div", { class: "quick" },
        h("button", { class: "btn", disabled: !dirty(), onclick: async () => { try { await save(); toast("Utkastet är sparat", "ok"); } catch (e) { toast(e.message, "bad"); } } }, "Spara utkast"),
        h("button", { class: "btn primary", disabled: !unpublished() || S.mode !== "live", onclick: async () => { const note = await ask("Publicera?", "Utkastet går ut på den riktiga sajten för alla besökare. Beskriv gärna vad som ändrats.", "Publicera", false, true); if (note === null) return; try { await publish(note); toast("Publicerat", "ok"); } catch (e) { toast(e.message, "bad"); } } }, "Publicera"),
        h("button", { class: "btn ghost", onclick: () => undo() || toast("Inget att ångra") }, "Ångra"),
        h("button", { class: "btn ghost", onclick: () => redo() || toast("Inget att göra om") }, "Gör om"),
        h("button", { class: "btn ghost", disabled: !unpublished(), onclick: async () => { if (await ask("Släng utkastet?", "Utkastet blir samma som det publicerade.", "Släng", true)) discardToPublished(); } }, "Släng utkast")),
      S.mode !== "live" ? h("p", { class: "muted sm" }, "Demoläge: publicering och versioner kräver inloggning som administratör.") : null);
    const changes = card("Skillnad mot det publicerade", table(d));
    const vers = card("Tidigare versioner", S.mode !== "live" ? h("p", { class: "muted" }, "Logga in som administratör för att se versionerna.") :
      S.history.length ? h("div", { class: "list" }, S.history.map(x => h("div", { class: "list-i" },
        h("b", {}, "#" + x.id), pill(x.action === "publish" ? "Publicerat" : "Återställt", x.action === "publish" ? "ok" : "warn"), h("span", { class: "muted sm" }, when(x.created_at) + (x.note ? " · " + x.note : "")),
        h("div", { class: "row end grow" },
          h("button", { class: "btn xs ghost", onclick: () => { const dd = diff(x.config, S.draft); toast(dd.length ? dd.length + " skillnader mot utkastet" : "Samma som utkastet"); detail.replaceChildren(h("h4", { class: "sub-t" }, "Version #" + x.id + " jämfört med utkastet"), table(diff(x.config, S.draft))); } }, "Jämför"),
          h("button", { class: "btn xs ghost", onclick: () => replaceDraft(x.config, "Version #" + x.id + " som utkast") }, "Till utkast"),
          h("button", { class: "btn xs", onclick: async () => { if (await ask("Återställ version #" + x.id + "?", "Versionen blir både utkast och publicerad på sajten.", "Återställ", true)) { try { await restore(x.id); toast("Återställd", "ok"); } catch (e) { toast(e.message, "bad"); } } } }, "Återställ"))))) : h("p", { class: "muted" }, "Inga versioner än. Den första skapas när du publicerar."));
    const detail = h("div", {});
    const fileIn = h("input", { type: "file", accept: "application/json", style: { display: "none" }, onchange: async e => { const fl = e.target.files[0]; if (!fl) return; try { const j = JSON.parse(await fl.text()); replaceDraft(j, "Importerad fil"); toast("Filen är inläst som utkast", "ok"); } catch (er) { toast("Filen kunde inte läsas", "bad"); } } });
    const io = card("Export och import", h("p", { class: "muted sm" }, "Spara utkastet som en fil, som säkerhetskopia eller för att flytta det."),
      h("div", { class: "row" }, h("button", { class: "btn sm", onclick: () => { const b = new Blob([JSON.stringify(S.draft, null, 2)], { type: "application/json" }); const a = h("a", { href: URL.createObjectURL(b), download: "fantasy-orientering-utkast-" + new Date().toISOString().slice(0, 10) + ".json" }); document.body.appendChild(a); a.click(); a.remove(); } }, "Exportera utkast"),
        h("button", { class: "btn sm ghost", onclick: () => fileIn.click() }, "Importera fil"), fileIn));
    const log = card("Ändringslogg", S.log.length ? h("div", { class: "list" }, S.log.slice(0, 50).map(x => h("div", { class: "list-i" }, h("span", {}, x.label), h("span", { class: "muted sm" }, when(x.at))))) : h("p", { class: "muted" }, "Inget loggat än."));
    body.replaceChildren(state, h("div", { class: "cols" }, h("div", {}, changes, detail), h("div", {}, vers, io, log)));
  };
  const off = on(draw); draw();
  return off;
}

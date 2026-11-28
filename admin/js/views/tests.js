/* Testläge: run the site's checks in every role, see JavaScript errors, reset the test environment. Everything runs in
   the sandbox with the draft applied, so changes are tested before they are published. */
import { h, card, when, toast } from "../ui.js";
import { S, on } from "../store.js";
import { makeFrame } from "../frame.js";
import { ROLES, TABS, DEVICES } from "../config.js";

export function testsView(root, state) {
  const results = h("div", { class: "results" }), errs = h("div", { class: "list" }), side = h("div", { class: "cmd-frame" });
  const f = makeFrame(side, { device: state.device || "mobile", tab: "home", role: state.role || "guest", cfg: () => S.draft, fitHeight: true, fixedHeight: 620 });
  const off = on(w => { if (w === "draft") f.push(S.draft); });
  let queue = [], all = [];
  const drawErrs = () => errs.replaceChildren(...(S.errors.length ? S.errors.slice(0, 40).map(e => h("div", { class: "list-i bad" }, h("code", {}, e.msg), h("span", { class: "muted sm" }, " " + (e.where || "") + " · " + e.role + "/" + e.tab + " · " + when(e.at)))) : [h("p", { class: "muted" }, "Inga JavaScript-fel rapporterade.")]));
  const runRole = role => new Promise(res => { f.setRole(role); setTimeout(() => { const once = m => { f.handlers.test = f.handlers.test.filter(x => x !== once); res(m.results); }; f.on("test", once); f.send({ t: "test" }); }, 500); });
  async function runAll(roles) {
    results.replaceChildren(h("p", { class: "muted" }, "Kör …")); all = [];
    for (const r of roles) { const res = await runRole(r); all.push([r, res]);
      results.replaceChildren(...all.map(([role, rs]) => h("div", { class: "res-block" }, h("h4", { class: "sub-t" }, ROLES.find(x => x[0] === role)[1] + " · " + rs.filter(x => x.ok).length + "/" + rs.length),
        h("table", { class: "tbl" }, h("tbody", {}, rs.map(x => h("tr", { class: x.ok ? "ok" : "bad" }, h("td", {}, x.ok ? "✓" : "✗"), h("td", {}, x.name), h("td", { class: "muted" }, x.detail || ""))))))));
    }
    drawErrs(); const bad = all.flatMap(([, rs]) => rs).filter(x => !x.ok).length; toast(bad ? bad + " tester misslyckades" : "Alla tester gick igenom", bad ? "bad" : "ok");
  }
  root.append(h("div", { class: "page-head" }, h("h2", {}, "Testläge"), h("p", { class: "muted" }, "Testerna körs på sajten med ditt utkast, i ett testläge utan inloggning och utan sparande. Riktiga konton och den riktiga sajten påverkas inte.")),
    h("div", { class: "cmd" }, h("div", { class: "cmd-main" },
      h("div", { class: "quick" },
        h("button", { class: "btn primary", onclick: () => runAll(["guest", "user", "admin"]) }, "Kör alla tester i alla vyer"),
        ...ROLES.map(([k, l]) => h("button", { class: "btn sm", onclick: () => runAll([k]) }, l)),
        h("button", { class: "btn sm ghost", onclick: () => { f.load(); S.errors = []; drawErrs(); results.replaceChildren(); toast("Testmiljön är återställd"); } }, "Återställ testmiljön")),
      card("Resultat", results, h("p", { class: "muted sm" }, "Testerna ritar varje sida, kollar att knappar har text och länkar har mål, öppnar menyn och kontaktformuläret, fyller laget automatiskt, söker i löparlistan och öppnar ett löparkort.")),
      card("Inloggning och utloggning", h("p", { class: "muted" }, "Vyerna ovan simulerar en besökare, en inloggad spelare och en administratör utan att logga in någon på riktigt. Själva inloggningen med e-post och lösenord testas säkrast med ett eget testkonto på sajten:"),
        h("a", { class: "btn sm", href: f.ifr.src.split("?")[0], target: "_blank", rel: "noopener" }, "Öppna sajten i ny flik ↗")),
      card("JavaScript-fel", errs)), side));
  results.append(h("p", { class: "muted" }, "Inga tester körda än."));
  drawErrs();
  return () => { off(); f.destroy(); };
}

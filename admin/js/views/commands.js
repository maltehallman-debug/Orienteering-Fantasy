/* Kommandocenter: buttons for common admin actions and a command line. Commands that change the site change the draft;
   'publicera' and 'bygg' are the only ones that reach the real site, and they ask first. */
import { h, toast, ask, when } from "../ui.js";
import { S, change, undo, redo, save, publish, discardToPublished, clearLocal, diff, on } from "../store.js";
import { makeFrame } from "../frame.js";
import * as api from "../api.js";
import { FLAGS, TABS, ROLES, SITE } from "../config.js";

export function commandsView(root, state) {
  const out = h("div", { class: "console", role: "log", "aria-live": "polite" });
  const input = h("input", { class: "input mono", placeholder: "Skriv ett kommando, t.ex. hjälp, status, flagga hem.nyheter av …", autocomplete: "off", spellcheck: "false" });
  const side = h("div", { class: "cmd-frame" });
  const line = (text, tone = "") => { out.appendChild(h("div", { class: "ln " + tone }, text)); out.scrollTop = out.scrollHeight; };
  const f = makeFrame(side, { device: "mobile", tab: state.tab || "home", role: state.role || "guest", cfg: () => S.draft, fitHeight: true, fixedHeight: 600 });
  f.on("info", m => Object.entries(m.data).forEach(([k, v]) => line("  " + k + ": " + v)));
  f.on("test", m => { m.results.forEach(r => line((r.ok ? "✓ " : "✗ ") + r.name + (r.detail ? " · " + r.detail : ""), r.ok ? "ok" : "bad")); line(m.results.filter(r => r.ok).length + " av " + m.results.length + " tester gick igenom."); });
  const off = on(w => { if (w === "draft") f.push(S.draft); });
  const hist = []; let hi = 0;

  const C = {
    "hjälp": ["Visa alla kommandon", () => Object.entries(C).forEach(([k, [d]]) => line(k.padEnd(14) + d))],
    "status": ["Kolla sajten, databasen, utlägg och datauppdatering", async () => {
      const r = await api.siteReachable(); line("Sajten: " + (r.ok ? "uppe (" + r.ms + " ms)" : "nås inte"), r.ok ? "ok" : "bad");
      try { await api.publishedPublic(); line("Databasen: svarar", "ok"); } catch (e) { line("Databasen: " + e.message, "bad"); }
      try { const d = await api.deployStatus(); line("Senaste utlägg (" + d.sha + "): " + d.state + " · " + d.text, d.state === "success" ? "ok" : "warn"); } catch (e) { line("Utlägg: " + e.message, "warn"); }
      try { const x = (await api.refreshRuns())[0]; line("Datauppdatering: " + (x ? x.status + " " + (x.conclusion || "") + " · " + when(x.at) : "–")); } catch (e) { line("Datauppdatering: " + e.message, "warn"); } }],
    "siffror": ["Konton, lag, ligor (kräver inloggning)", async () => { const s = await api.stats(); Object.entries(s).forEach(([k, v]) => line("  " + k + ": " + v)); }],
    "info": ["Teknisk information om förhandsvisningen", () => f.send({ t: "info" })],
    "roll": ["roll gate|guest|user|admin · byt vy i förhandsvisningen", a => { const r = a[0]; if (!ROLES.some(x => x[0] === r)) return line("Roller: " + ROLES.map(x => x[0] + " (" + x[1] + ")").join(", "), "warn"); f.setRole(r); line("Vy: " + ROLES.find(x => x[0] === r)[1], "ok"); }],
    "sida": ["sida home|team|rounds|leagues|rules|profile", a => { if (!TABS.some(x => x[0] === a[0])) return line("Sidor: " + TABS.map(x => x[0]).join(", "), "warn"); f.setTab(a[0]); line("Sida: " + a[0], "ok"); }],
    "flaggor": ["Lista funktioner och om de är på", () => FLAGS.forEach(([k, l]) => line("  " + (S.draft.flags[k] === false ? "av " : "på ") + k.padEnd(20) + l))],
    "flagga": ["flagga <namn> på|av · slå på eller av en funktion", a => { const k = a[0], v = a[1]; if (!FLAGS.some(x => x[0] === k) || !/^(på|av|on|off)$/.test(v || "")) return line("Exempel: flagga hem.nyheter av", "warn");
      const onv = /^(på|on)$/.test(v); change(d => { if (onv) delete d.flags[k]; else d.flags[k] = false; }, "Funktion " + k + " " + (onv ? "på" : "av")); line(k + " är " + (onv ? "på" : "av") + " i utkastet", "ok"); }],
    "dölj": ["dölj <css-väljare> · dölj ett element", a => { const s = a.join(" "); if (!s) return line("Exempel: dölj .hm-news", "warn"); change(d => { if (!d.hidden.includes(s)) d.hidden.push(s); }, "Döljer " + s); line("Dolt: " + s, "ok"); }],
    "visa": ["visa <css-väljare> · visa ett dolt element", a => { const s = a.join(" "); change(d => { d.hidden = d.hidden.filter(x => x !== s); }, "Visar " + s); line("Visas: " + s, "ok"); }],
    "banner": ["banner <text> | banner av · meddelande överst", a => { if (!a.length || a[0] === "av") { change(d => { d.banner = {}; }, "Banner av"); return line("Bannern är av", "ok"); } const t = a.join(" ").slice(0, 200); change(d => { d.banner = { on: true, text: t, tone: "info" }; }, "Banner: " + t); line("Banner: " + t, "ok"); }],
    "tema": ["tema <--variabel> <värde> · ändra en designvariabel", a => { if (!/^--[a-z0-9-]+$/.test(a[0] || "") || !a[1]) return line("Exempel: tema --ds-navy #002a4a", "warn"); change(d => { d.tokens[a[0]] = a.slice(1).join(" "); }, "Tema " + a[0]); line(a[0] + " = " + a.slice(1).join(" "), "ok"); }],
    "ändringar": ["Vad skiljer utkastet från det publicerade", () => { const d = diff(S.published, S.draft); if (!d.length) return line("Inga ändringar."); d.forEach(([g, k, a, b]) => line("  " + g + " · " + k + ": " + (a ?? "–") + " → " + (b ?? "–"))); }],
    "ångra": ["Ångra senaste ändringen", () => line(undo() ? "Ångrat" : "Inget att ångra")],
    "gör-om": ["Gör om", () => line(redo() ? "Gjort om" : "Inget att göra om")],
    "spara": ["Spara utkastet", async () => { await save(); line("Utkast sparat", "ok"); }],
    "publicera": ["publicera [beskrivning] · lägg ut utkastet på sajten", async a => { if (!(await ask("Publicera?", "Utkastet går ut på den riktiga sajten för alla besökare.", "Publicera"))) return line("Avbrutet"); await publish(a.join(" ")); line("Publicerat", "ok"); }],
    "återställ": ["Släng utkastet och börja från det publicerade", async () => { if (!(await ask("Släng utkastet?", "Alla ändringar som inte är publicerade försvinner.", "Släng", true))) return; discardToPublished(); line("Utkastet är som det publicerade", "ok"); }],
    "rensa-test": ["Rensa testdata: ladda om förhandsvisningen", () => { f.load(); S.errors = []; line("Testmiljön är återställd", "ok"); }],
    "rensa-lokalt": ["Rensa lokala utkast och loggen i den här webbläsaren", async () => { if (!(await ask("Rensa lokalt?", "Lokala utkast och loggen tas bort från den här webbläsaren.", "Rensa", true))) return; clearLocal(); line("Rensat", "ok"); }],
    "test": ["Kör testerna i förhandsvisningen", () => { line("Kör tester …"); f.send({ t: "test" }); }],
    "fel": ["Visa JavaScript-fel från förhandsvisningarna", () => { if (!S.errors.length) return line("Inga fel.", "ok"); S.errors.slice(0, 30).forEach(e => line(when(e.at) + " · " + e.msg + (e.where ? " (" + e.where + ")" : "") + " · " + e.role + "/" + e.tab, "bad")); }],
    "bygg": ["Bygg om sajten nu (data + utlägg, kräver inloggning)", async () => { if (!(await ask("Bygga om sajten?", "Startar datauppdateringen och ett nytt utlägg. Vercel tillåter ett begränsat antal utlägg per dygn.", "Bygg om"))) return; line(await api.rebuildSite(), "ok"); }],
    "rensa": ["Töm konsolen", () => out.replaceChildren()],
  };
  async function run(raw) {
    const txt = raw.trim(); if (!txt) return; hist.unshift(txt); hi = -1; line("› " + txt, "cmd");
    const [cmd, ...args] = txt.split(/\s+/); const c = C[cmd.toLowerCase()];
    if (!c) return line("Okänt kommando. Skriv hjälp.", "warn");
    try { await c[1](args); } catch (e) { line("Fel: " + (e.message || e), "bad"); }
  }
  input.addEventListener("keydown", e => {
    if (e.key === "Enter") { run(input.value); input.value = ""; }
    else if (e.key === "ArrowUp") { hi = Math.min(hist.length - 1, hi + 1); if (hist[hi]) input.value = hist[hi]; e.preventDefault(); }
    else if (e.key === "ArrowDown") { hi = Math.max(-1, hi - 1); input.value = hi >= 0 ? hist[hi] : ""; e.preventDefault(); }
    else if (e.key === "Tab") { const m = Object.keys(C).find(k => k.startsWith(input.value)); if (m) { input.value = m + " "; e.preventDefault(); } }
  });
  const btn = (l, cmd) => h("button", { class: "btn sm", onclick: () => run(cmd) }, l);
  root.append(h("div", { class: "page-head" }, h("h2", {}, "Kommandocenter"), h("p", { class: "muted" }, "Snabbknappar och en kommandorad. Ändringar hamnar i utkastet och syns i förhandsvisningen. Bara 'publicera' och 'bygg' påverkar den riktiga sajten, och de frågar först.")),
    h("div", { class: "cmd" }, h("div", { class: "cmd-main" },
      h("div", { class: "quick" }, btn("Status", "status"), btn("Siffror", "siffror"), btn("Kör tester", "test"), btn("Visa fel", "fel"), btn("Teknisk info", "info"), btn("Ändringar", "ändringar"),
        btn("Som besökare", "roll guest"), btn("Som spelare", "roll user"), btn("Som admin", "roll admin"), btn("Rensa testdata", "rensa-test"), btn("Släng utkast", "återställ"), btn("Bygg om sajten", "bygg")),
      out, input), side));
  line("Fantasy Orientering · kommandocenter. Skriv hjälp för alla kommandon. ↑ för förra kommandot, Tab fyller i.");
  setTimeout(() => input.focus(), 50);
  return () => { off(); f.destroy(); };
}

/* Översikt: the site's status, the numbers, what is switched on, the latest changes and messages, quick actions. */
import { h, card, pill, ago, when, toast } from "../ui.js";
import { S, diff, unpublished } from "../store.js";
import * as api from "../api.js";
import { FLAGS, SITE, PUBLIC_SITE, REPO } from "../config.js";

export function dashboardView(root, state, go) {
  const status = h("div", { class: "stat-grid" }), numbers = h("div", { class: "stat-grid" }), msgs = h("div", { class: "list" });
  const stat = (label, value, tone = "", sub = "") => h("div", { class: "stat " + tone }, h("span", { class: "lbl" }, label), h("b", {}, value), sub ? h("span", { class: "muted sm" }, sub) : null);
  const changes = diff(S.published, S.draft);
  root.append(
    h("div", { class: "page-head" }, h("h2", {}, "Översikt"), h("p", { class: "muted" }, S.mode === "live" ? "Inloggad som " + (S.user?.email || "admin") + "." : "Demoläge: utkast sparas bara i den här webbläsaren och inget publiceras.")),
    h("div", { class: "quick" },
      h("button", { class: "btn primary", onclick: () => go("editor") }, "Redigera sidan"),
      h("button", { class: "btn", onclick: () => go("preview") }, "Förhandsgranska vyer"),
      h("button", { class: "btn", onclick: () => go("tests") }, "Kör tester"),
      h("button", { class: "btn", onclick: () => go("versions") }, unpublished() ? `Publicera (${changes.length})` : "Versioner"),
      h("a", { class: "btn ghost", href: PUBLIC_SITE, target: "_blank", rel: "noopener" }, "Öppna sajten ↗")),
    card("Webbplatsens status", status),
    card("Spelare och innehåll", numbers),
    h("div", { class: "cols" },
      card("Aktiva funktioner", h("div", { class: "list" }, FLAGS.map(([k, l]) => { const onp = S.published.flags[k] !== false, ond = S.draft.flags[k] !== false;
        return h("div", { class: "list-i" }, h("span", {}, l), pill(onp ? "På" : "Av", onp ? "ok" : "off"), onp !== ond ? pill("utkast: " + (ond ? "på" : "av"), "warn") : null); })),
        h("button", { class: "btn sm", onclick: () => go("features") }, "Ändra funktioner")),
      card("Senaste ändringar",
        S.history.length ? h("div", { class: "list" }, S.history.slice(0, 5).map(x => h("div", { class: "list-i" }, h("b", {}, x.action === "publish" ? "Publicerat" : "Återställt"), h("span", { class: "muted sm" }, " " + when(x.created_at) + (x.note ? " · " + x.note : ""))))) : null,
        h("div", { class: "list" }, S.log.slice(0, 6).map(x => h("div", { class: "list-i" }, h("span", {}, x.label), h("span", { class: "muted sm" }, ago(x.at))))),
        !S.history.length && !S.log.length ? h("p", { class: "muted" }, "Inga ändringar än.") : null),
      card("Systemmeddelanden", msgs)));

  /* status: the site, the database, the last deploy, the last data refresh */
  status.append(stat("Sajten", "Kollar …"), stat("Databasen", "Kollar …"), stat("Senaste utlägg", "Kollar …"), stat("Datauppdatering", "Kollar …"));
  const set = (i, v, tone, sub) => status.replaceChild(stat(status.children[i].querySelector(".lbl").textContent, v, tone, sub), status.children[i]);
  api.siteReachable().then(r => set(0, r.ok ? "Uppe" : "Nås inte", r.ok ? "ok" : "bad", r.ok ? r.ms + " ms · " + new URL(SITE).host : ""));
  api.publishedPublic().then(() => set(1, "Svarar", "ok", "Supabase"), e => set(1, "Fel", "bad", e.message));
  api.deployStatus().then(d => set(2, d.state === "success" ? "Klart" : d.state === "pending" ? "Pågår" : d.state === "failure" ? "Misslyckades" : d.state || "–", d.state === "success" ? "ok" : d.state === "failure" ? "bad" : "warn", (d.text || "") + (d.at ? " · " + ago(d.at) : "")), e => set(2, "Okänt", "warn", e.message));
  api.refreshRuns().then(r => { const x = r[0]; set(3, !x ? "–" : x.status !== "completed" ? "Pågår" : x.conclusion === "success" ? "Lyckades" : "Misslyckades", !x ? "" : x.conclusion === "success" ? "ok" : x.status !== "completed" ? "warn" : "bad", x ? ago(x.at) : ""); }, e => set(3, "Okänt", "warn", e.message));

  /* numbers: only for a signed-in admin (the database answers only admins) */
  if (S.mode === "live") {
    numbers.append(stat("Laddar …", "…"));
    api.stats().then(s => {
      numbers.replaceChildren(stat("Konton", s.users, "", "+" + s.users_7d + " senaste veckan"), stat("Spelare med lag", s.squads), stat("Ligor", s.leagues), stat("Nyheter", s.news),
        stat("Besökare", "Vercel", "muted", "Finns i Vercel Analytics, kräver nyckel"), stat("Sluten beta", s.closed_beta ? "På" : "Av", s.closed_beta ? "warn" : "ok"));
      const m = [];
      if (s.removal_open) m.push(["warn", s.removal_open + " vill tas bort ur spelet", "Hanteras under Profil → Admin på sajten"]);
      if (s.feedback_open) m.push(["", s.feedback_open + " tips från spelare", "Under Profil → Admin på sajten"]);
      if (s.photos_pending) m.push(["warn", s.photos_pending + " foton väntar på granskning", ""]);
      if (unpublished()) m.push(["warn", changes.length + " ändringar i utkastet är inte publicerade", ""]);
      msgs.replaceChildren(...(m.length ? m.map(([t, a, b]) => h("div", { class: "list-i" }, pill(t === "warn" ? "Att göra" : "Info", t || "info"), h("span", {}, a), b ? h("span", { class: "muted sm" }, " · " + b) : null)) : [h("p", { class: "muted" }, "Inget som väntar.")]));
    }, e => numbers.replaceChildren(h("p", { class: "muted" }, "Kunde inte läsa siffrorna: " + e.message)));
  } else {
    numbers.append(h("p", { class: "muted" }, "Siffrorna kommer från databasen och visas bara för en inloggad administratör."));
    msgs.append(unpublished() ? h("div", { class: "list-i" }, pill("Utkast", "warn"), h("span", {}, changes.length + " lokala ändringar")) : h("p", { class: "muted" }, "Inget som väntar."));
  }
  return () => {};
}

/* The dashboard shell: sign-in, the side menu, the top bar with the draft's state, and switching between views. */
import { h, clear, toast, ask, icon, ago } from "./ui.js";
import { S, start, on, dirty, unpublished, save, publish, undo, redo, diff, replaceDraft } from "./store.js";
import * as api from "./api.js";
import { PUBLIC_SITE } from "./config.js";
import { dashboardView } from "./views/dashboard.js";
import { editorView } from "./views/editor.js";
import { previewView } from "./views/preview.js";
import { commandsView } from "./views/commands.js";
import { testsView } from "./views/tests.js";
import { featuresView } from "./views/features.js";
import { versionsView } from "./views/versions.js";

const VIEWS = [
  ["dashboard", "Översikt", "dash", dashboardView], ["editor", "Redigera", "edit", editorView], ["preview", "Förhandsgranska", "eye", previewView],
  ["features", "Funktioner och tema", "flag", featuresView], ["commands", "Kommandon", "term", commandsView], ["tests", "Testläge", "test", testsView],
  ["versions", "Utkast och versioner", "hist", versionsView]];
const app = document.getElementById("app");
const shared = { tab: "home", role: "guest", device: "mobile" };
let cleanup = null, current = null;

/* light or dark, remembered in this browser */
const theme = localStorage.getItem("of-admin-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
document.documentElement.dataset.theme = theme;
const toggleTheme = () => { const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = t; localStorage.setItem("of-admin-theme", t); };

function loginScreen(msg = "") {
  clear(app);
  const email = h("input", { class: "input", type: "email", autocomplete: "email", placeholder: "E-post", required: true });
  const pw = h("input", { class: "input", type: "password", autocomplete: "current-password", placeholder: "Lösenord", required: true });
  const note = h("p", { class: "muted sm", role: "status" }, msg);
  const go = h("button", { class: "btn primary block", type: "submit" }, "Logga in");
  const form = h("form", { class: "login-form", onsubmit: async e => { e.preventDefault(); go.disabled = true; note.textContent = "Loggar in …";
    try { const u = await api.signIn(email.value.trim(), pw.value); if (!(await api.isAdmin())) { await api.signOut(); return loginScreen("Kontot är inte administratör. Be en administratör lägga till det."); } await boot("live", u); }
    catch (er) { note.textContent = /Invalid login/i.test(er.message) ? "Fel e-post eller lösenord." : er.message; go.disabled = false; } } }, email, pw, go);
  app.append(h("div", { class: "login" }, h("div", { class: "login-card" },
    h("div", { class: "brand" }, h("span", { class: "brand-mark" }, "FO"), h("div", {}, h("b", {}, "Fantasy Orientering"), h("span", { class: "muted sm" }, "Adminpanel"))),
    h("h1", {}, "Logga in"), h("p", { class: "muted" }, "Med ditt vanliga konto. Bara administratörer kommer in, och databasen tillåter ändringar bara från dem."),
    form, note)));
  setTimeout(() => email.focus(), 50);
}

async function boot(mode, user) {
  if (mode !== "live" || !user) return loginScreen();
  clear(app); app.append(h("div", { class: "loading" }, "Laddar …"));
  try { await start(mode, user); } catch (e) { return loginScreen("Kunde inte läsa inställningarna: " + e.message); }
  shell();
  if (S.recover) { const r = S.recover; delete S.recover;
    if (await ask("Osparade ändringar hittades", "Det finns ändringar från " + ago(r.at) + " i den här webbläsaren som inte sparades. Vill du ta tillbaka dem?", "Ta tillbaka")) replaceDraft(r.draft, "Osparade ändringar tillbaka"); }
}

function shell() {
  clear(app);
  const nav = h("nav", { class: "side", "aria-label": "Adminmeny" },
    h("div", { class: "brand" }, h("span", { class: "brand-mark" }, "FO"), h("div", {}, h("b", {}, "Fantasy Orientering"), h("span", { class: "muted sm" }, "Admin"))),
    h("div", { class: "nav-list" }, VIEWS.map(([k, l, ic]) => h("button", { class: "nav-i", "data-v": k, onclick: () => { go(k); app.classList.remove("nav-open"); } }, icon(ic), h("span", {}, l)))),
    h("div", { class: "nav-foot" },
      h("a", { class: "nav-i", href: PUBLIC_SITE, target: "_blank", rel: "noopener" }, icon("eye"), h("span", {}, "Öppna sajten ↗")),
      h("button", { class: "nav-i", onclick: toggleTheme }, icon("moon"), h("span", {}, "Ljust / mörkt")),
      h("button", { class: "nav-i", onclick: async () => { if (dirty() && !(await ask("Osparade ändringar", "Du har ändringar som inte är sparade. Logga ut ändå? En kopia finns kvar i webbläsaren.", "Logga ut", true))) return; await api.signOut(); location.hash = ""; loginScreen(); } }, icon("out"), h("span", {}, "Logga ut"))));
  const status = h("div", { class: "draft-state" });
  const saveBtn = h("button", { class: "btn sm", onclick: async () => { try { await save(); toast("Utkastet är sparat", "ok"); } catch (e) { toast(e.message, "bad"); } } }, "Spara utkast");
  const pubBtn = h("button", { class: "btn sm primary", onclick: async () => {
    if (S.mode !== "live") return toast("Publicering kräver inloggning som administratör.", "bad");
    const n = diff(S.published, S.draft).length; const note = await ask("Publicera " + n + " ändringar?", "Utkastet går ut på den riktiga sajten för alla besökare. Beskriv gärna vad som ändrats.", "Publicera", false, true);
    if (note === null) return; try { await publish(note); toast("Publicerat. Sajten visar ändringarna vid nästa sidladdning.", "ok"); } catch (e) { toast(e.message, "bad"); } } }, "Publicera");
  const topbar = h("header", { class: "topbar" },
    h("button", { class: "btn sm ghost menu-btn", "aria-label": "Meny", onclick: () => app.classList.toggle("nav-open") }, icon("menu")),
    h("h1", { class: "top-t" }, ""), status,
    h("div", { class: "row" }, h("button", { class: "btn sm ghost", title: "Ångra", onclick: () => undo() || toast("Inget att ångra") }, icon("undo")),
      h("button", { class: "btn sm ghost", title: "Gör om", onclick: () => redo() || toast("Inget att göra om") }, icon("redo")), saveBtn, pubBtn));
  const main = h("main", { class: "main", id: "main" });
  app.append(nav, h("div", { class: "content" }, topbar, main));
  const drawState = () => {
    const d = dirty(), u = unpublished(), n = diff(S.published, S.draft).length;
    status.replaceChildren(h("span", { class: "dot " + (d ? "warn" : u ? "info" : "ok") }), h("span", {}, d ? "Osparade ändringar" : u ? "Sparat utkast · " + n + " ändringar ej publicerade" : "Allt publicerat"),
      h("span", { class: "muted sm" }, S.publishedAt ? " · publicerat " + ago(S.publishedAt) : ""));
    saveBtn.disabled = !d; pubBtn.disabled = !u || S.mode !== "live";
  };
  on(w => drawState()); drawState();
  addEventListener("beforeunload", e => { if (dirty()) { e.preventDefault(); e.returnValue = ""; } });
  addEventListener("hashchange", () => { const v = location.hash.slice(1); if (v && v !== current) go(v); });
  go(location.hash.slice(1) || "dashboard");
}

function go(view) {
  const v = VIEWS.find(x => x[0] === view) || VIEWS[0]; current = v[0];
  if (location.hash.slice(1) !== v[0]) history.replaceState(null, "", "#" + v[0]);
  if (cleanup) { try { cleanup(); } catch (e) {} cleanup = null; }
  document.querySelectorAll(".nav-i[data-v]").forEach(b => b.classList.toggle("on", b.dataset.v === v[0]));
  document.querySelector(".top-t").textContent = v[1];
  const main = clear(document.getElementById("main")); main.dataset.view = v[0];
  cleanup = v[3](main, shared, go) || null;
}

(async () => {
  const u = await api.currentUser();
  if (u) { if (await api.isAdmin()) return boot("live", u); await api.signOut(); return loginScreen("Kontot är inte administratör."); }
  loginScreen();
})();

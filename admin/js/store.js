/* The dashboard's state: who is signed in, the draft being edited, what is saved and what is published, and the undo
   history. Every change to the draft goes through change(), which keeps undo, autosaves a local copy and tells the
   rest of the dashboard (and the preview frames) about it. */
import * as api from "./api.js";

const LOCAL = "of-admin-draft", LOG = "of-admin-log";
const clone = o => JSON.parse(JSON.stringify(o || {}));
export const empty = () => ({ tokens: {}, styles: {}, texts: {}, attrs: {}, hidden: [], moves: [], blocks: [], flags: {}, banner: {} });
export const norm = c => Object.assign(empty(), clone(c));

export const S = {
  mode: null,            // "live" (signed-in admin) or "demo" (this browser only)
  user: null,
  draft: empty(),
  savedJson: "{}",       // the draft as last saved (server or local)
  published: empty(),
  savedAt: null, publishedAt: null,
  undo: [], redo: [],
  log: (() => { try { return JSON.parse(localStorage.getItem(LOG) || "[]"); } catch (e) { return []; } })(),
  errors: [],            // JavaScript errors reported by the preview frames
  history: [],
};
const subs = new Set();
export const on = fn => { subs.add(fn); return () => subs.delete(fn); };
export const emit = what => subs.forEach(fn => { try { fn(what); } catch (e) { console.error(e); } });

export const dirty = () => JSON.stringify(S.draft) !== S.savedJson;
export const unpublished = () => JSON.stringify(S.draft) !== JSON.stringify(S.published);

function logIt(label) {
  S.log.unshift({ at: new Date().toISOString(), label }); S.log = S.log.slice(0, 200);
  try { localStorage.setItem(LOG, JSON.stringify(S.log)); } catch (e) {}
}
/* change the draft: fn edits a copy; label says what changed (shown in the log) */
export function change(fn, label) {
  const before = JSON.stringify(S.draft); const next = norm(S.draft); fn(next);
  const after = JSON.stringify(next); if (after === before) return;
  S.undo.push(before); if (S.undo.length > 200) S.undo.shift(); S.redo = [];
  S.draft = next; autosave(); logIt(label || "Ändring"); emit("draft");
}
export function undo() { if (!S.undo.length) return false; S.redo.push(JSON.stringify(S.draft)); S.draft = norm(JSON.parse(S.undo.pop())); autosave(); logIt("Ångra"); emit("draft"); return true; }
export function redo() { if (!S.redo.length) return false; S.undo.push(JSON.stringify(S.draft)); S.draft = norm(JSON.parse(S.redo.pop())); autosave(); logIt("Gör om"); emit("draft"); return true; }
export function replaceDraft(c, label) { change(d => { Object.keys(d).forEach(k => delete d[k]); Object.assign(d, norm(c)); }, label); }

function autosave() { try { localStorage.setItem(LOCAL, JSON.stringify({ mode: S.mode, at: new Date().toISOString(), draft: S.draft })); } catch (e) {} }
function localCopy() { try { return JSON.parse(localStorage.getItem(LOCAL) || "null"); } catch (e) { return null; } }

export async function start(mode, user) {
  S.mode = mode; S.user = user || null;
  if (mode === "live") {
    const row = await api.loadConfigRow();
    S.published = norm(row.published); S.draft = norm(row.draft); S.savedJson = JSON.stringify(S.draft);
    S.savedAt = row.draft_updated_at; S.publishedAt = row.published_at;
    /* a local copy newer than the saved draft (a tab closed before saving) is offered back */
    const l = localCopy(); if (l && l.mode === "live" && l.at > (row.draft_updated_at || "") && JSON.stringify(norm(l.draft)) !== S.savedJson) { S.recover = l; }
    try { S.history = await api.historyRemote(); } catch (e) { S.history = []; }
  } else {
    try { S.published = norm(await api.publishedPublic()); } catch (e) { S.published = empty(); }
    const l = localCopy(); S.draft = l && l.mode === "demo" ? norm(l.draft) : norm(S.published);
    S.savedJson = JSON.stringify(S.draft); S.savedAt = l ? l.at : null; S.history = [];
  }
  emit("start");
}
export async function save() {
  if (S.mode === "live") { S.savedAt = await api.saveDraftRemote(S.draft); }
  else { autosave(); S.savedAt = new Date().toISOString(); }
  S.savedJson = JSON.stringify(S.draft); logIt("Utkast sparat"); emit("saved");
}
export async function publish(note) {
  if (S.mode !== "live") throw new Error("Publicering kräver inloggning som administratör.");
  if (dirty()) await save();
  const c = await api.publishRemote(note); S.published = norm(c); S.publishedAt = new Date().toISOString();
  S.history = await api.historyRemote(); logIt("Publicerat" + (note ? ": " + note : "")); emit("published");
}
export async function restore(id) {
  if (S.mode !== "live") throw new Error("Återställning kräver inloggning som administratör.");
  const c = await api.restoreRemote(id); S.draft = norm(c); S.published = norm(c); S.savedJson = JSON.stringify(S.draft);
  S.savedAt = S.publishedAt = new Date().toISOString(); S.history = await api.historyRemote(); logIt("Återställd version " + id); emit("published");
}
export function discardToPublished() { replaceDraft(S.published, "Utkastet återställt till publicerat"); }
export function clearLocal() { try { localStorage.removeItem(LOCAL); localStorage.removeItem(LOG); } catch (e) {} S.log = []; emit("draft"); }

/* what differs between two configurations, in words */
export function diff(a, b) {
  a = norm(a); b = norm(b); const out = [];
  const keys = (x, y) => [...new Set([...Object.keys(x || {}), ...Object.keys(y || {})])];
  for (const k of keys(a.tokens, b.tokens)) if (a.tokens[k] !== b.tokens[k]) out.push(["Tema", k, a.tokens[k], b.tokens[k]]);
  for (const s of keys(a.styles, b.styles)) { const x = a.styles[s] || {}, y = b.styles[s] || {}; for (const p of keys(x, y)) if (x[p] !== y[p]) out.push(["Stil", s + " · " + p, x[p], y[p]]); }
  for (const s of keys(a.texts, b.texts)) if (a.texts[s] !== b.texts[s]) out.push(["Text", s, a.texts[s], b.texts[s]]);
  for (const s of keys(a.attrs, b.attrs)) if (JSON.stringify(a.attrs[s]) !== JSON.stringify(b.attrs[s])) out.push(["Länk/bild", s, JSON.stringify(a.attrs[s] || ""), JSON.stringify(b.attrs[s] || "")]);
  for (const s of new Set([...a.hidden, ...b.hidden])) if (a.hidden.includes(s) !== b.hidden.includes(s)) out.push(["Dold", s, a.hidden.includes(s) ? "dold" : "", b.hidden.includes(s) ? "dold" : ""]);
  if (JSON.stringify(a.moves) !== JSON.stringify(b.moves)) out.push(["Ordning", "flyttade element", a.moves.length + " st", b.moves.length + " st"]);
  if (JSON.stringify(a.blocks) !== JSON.stringify(b.blocks)) out.push(["Sektioner", "egna sektioner", a.blocks.length + " st", b.blocks.length + " st"]);
  for (const k of keys(a.flags, b.flags)) if (a.flags[k] !== b.flags[k]) out.push(["Funktion", k, String(a.flags[k] ?? "på"), String(b.flags[k] ?? "på")]);
  if (JSON.stringify(a.banner) !== JSON.stringify(b.banner)) out.push(["Banner", "meddelande", a.banner.on ? a.banner.text : "av", b.banner.on ? b.banner.text : "av"]);
  return out;
}

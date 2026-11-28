/* Talking to the backend. Real sign-in with Supabase Auth; whether you are an admin is decided by the database
   (is_admin), and the database refuses every write from anyone else. In demo mode nothing is sent: the draft lives in
   this browser only and publishing is off. */
import { SB_URL, SB_KEY, REPO, SITE } from "./config.js";

export const sb = window.supabase.createClient(SB_URL, SB_KEY, { auth: { persistSession: true, autoRefreshToken: true, storageKey: "of-admin-auth" } });

export async function currentUser() { const { data } = await sb.auth.getSession(); return data.session ? data.session.user : null; }
export async function signIn(email, password) { const r = await sb.auth.signInWithPassword({ email, password }); if (r.error) throw r.error; return r.data.user; }
export async function signOut() { await sb.auth.signOut(); }
export async function isAdmin() { const r = await sb.rpc("is_admin"); return r.data === true; }

export async function loadConfigRow() {
  const r = await sb.from("site_config").select("draft,published,draft_updated_at,published_at").eq("id", 1).single();
  if (r.error) throw r.error; return r.data;
}
export async function saveDraftRemote(draft) {
  const { data } = await sb.auth.getSession();
  const r = await sb.from("site_config").update({ draft, draft_updated_at: new Date().toISOString(), draft_updated_by: data.session?.user.id || null }).eq("id", 1).select("draft_updated_at").single();
  if (r.error) throw r.error; return r.data.draft_updated_at;
}
export async function publishRemote(note) { const r = await sb.rpc("publish_site_config", { p_note: note || null }); if (r.error) throw r.error; return r.data; }
export async function restoreRemote(id) { const r = await sb.rpc("restore_site_config", { p_id: id }); if (r.error) throw r.error; return r.data; }
export async function historyRemote(limit = 40) {
  const r = await sb.from("site_config_history").select("id,created_at,action,note,config").order("id", { ascending: false }).limit(limit);
  if (r.error) throw r.error; return r.data || [];
}
export async function stats() { const r = await sb.rpc("admin_stats"); if (r.error) throw r.error; return r.data; }
export async function publishedPublic() { const r = await sb.rpc("get_site_config"); if (r.error) throw r.error; return r.data || {}; }
/* the site rebuild (data refresh + deploy) through the existing server function, which checks that you are an admin */
export async function rebuildSite() {
  const r = await sb.functions.invoke("apply-now", { method: "POST" });
  if (r.error) { let msg = r.error.message; try { const j = await r.error.context.json(); if (j && j.msg) msg = j.msg; } catch (e) {} throw new Error(msg); }
  return (r.data && r.data.msg) || "Uppdateringen är startad.";
}

/* public status, no keys: is the site up, how did the last deploy and the last data refresh go (GitHub's open API) */
export async function siteReachable() {
  const t = performance.now();
  try { await fetch(SITE + "manifest.webmanifest?nc=" + Date.now(), { mode: "no-cors", cache: "no-store" }); return { ok: true, ms: Math.round(performance.now() - t) }; }
  catch (e) { return { ok: false, ms: 0 }; }
}
export async function deployStatus() {
  const r = await fetch(`https://api.github.com/repos/${REPO}/commits/main/status`); if (!r.ok) throw new Error("GitHub svarar inte (" + r.status + ")");
  const j = await r.json(); const v = (j.statuses || []).find(s => /vercel/i.test(s.context)) || {};
  return { state: v.state || j.state, text: v.description || "", sha: (j.sha || "").slice(0, 7), at: v.updated_at || null };
}
export async function refreshRuns() {
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/refresh.yml/runs?per_page=5`); if (!r.ok) throw new Error("GitHub svarar inte (" + r.status + ")");
  const j = await r.json(); return (j.workflow_runs || []).map(x => ({ id: x.id, status: x.status, conclusion: x.conclusion, at: x.created_at, url: x.html_url, event: x.event }));
}

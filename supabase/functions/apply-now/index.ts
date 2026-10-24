// Admins press "Apply now" on the site: this starts the GitHub data refresh at once instead of waiting for the night.
// It checks the caller is a signed-in admin (the same is_admin() the database uses), refuses while a refresh is
// already queued or running, and calls GitHub with a token kept as the Supabase secret GH_DISPATCH_TOKEN
// or in Supabase Vault as gh_dispatch_token (a fine-grained token for this one repository with "Actions: read and
// write"). The token never reaches a browser.
import { createClient } from "jsr:@supabase/supabase-js@2";

const REPO = "maltehallman-debug/Orienteering-Fantasy";
const WORKFLOW = "refresh.yml";
const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};
const json = (o: unknown, status = 200) => new Response(JSON.stringify(o), { status, headers: { ...cors, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  const auth = req.headers.get("Authorization") || "";
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: auth } } });
  const { data: isAdmin, error } = await sb.rpc("is_admin");
  if (error || isAdmin !== true) return json({ ok: false, msg: "Only admins can do this." }, 403);
  // the token: a function secret if one is set, otherwise the encrypted Vault entry (readable by the service role only)
  let token = Deno.env.get("GH_DISPATCH_TOKEN");
  if (!token) {
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const t = await admin.rpc("gh_dispatch_token");
    token = typeof t.data === "string" ? t.data : undefined;
  }
  if (!token) return json({ ok: false, msg: "The refresh button is not set up yet (missing GitHub token)." }, 503);
  const gh = (path: string, init: RequestInit = {}) => fetch(`https://api.github.com/repos/${REPO}${path}`, {
    ...init, headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", ...(init.headers || {}) },
  });
  // the latest refresh, so the page can say whether one is running
  const runs = await gh(`/actions/workflows/${WORKFLOW}/runs?per_page=1`);
  const last = runs.ok ? (await runs.json()).workflow_runs?.[0] : null;
  const busy = last && (last.status === "queued" || last.status === "in_progress");
  const state = last ? { status: last.status, conclusion: last.conclusion, started: last.run_started_at || last.created_at, updated: last.updated_at } : null;
  if (req.method === "GET") return json({ ok: true, busy: !!busy, last: state });
  if (busy) return json({ ok: true, busy: true, already: true, last: state, msg: "A refresh is already running. Your changes are included if you saved them before it started; otherwise press again when it is done." });
  const r = await gh(`/actions/workflows/${WORKFLOW}/dispatches`, { method: "POST", body: JSON.stringify({ ref: "main" }) });
  if (r.status !== 204) return json({ ok: false, msg: `GitHub refused (${r.status}).` }, 502);
  return json({ ok: true, busy: true, started: true, msg: "Refresh started. The site updates in about 5 to 8 minutes." });
});

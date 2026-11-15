// Deadline reminders by web push. A cron job in the database calls this every half hour with the key it keeps in
// Vault (push_cron_key). For a round that locks within a day it reminds everyone who turned reminders on and has no
// squad for that round yet: once about a day before, once in the last three hours. Each reminder is sent once
// (push_log). Skipped weeks (season_rounds.skip) get none.
// A signed-in player can also call it with { test: true } to get a test notification on their own devices.
// The VAPID key pair is made here on the first run and kept in Vault; the private key never leaves the server.
import { createClient } from "jsr:@supabase/supabase-js@2";
import webpush from "npm:web-push@3.6.7";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-cron-key",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (o: unknown, status = 200) => new Response(JSON.stringify(o), { status, headers: { ...cors, "Content-Type": "application/json" } });
const b64u = (b: Uint8Array) => btoa(String.fromCharCode(...b)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const fromB64u = (s: string) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));

const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
const secret = async (n: string) => { const r = await admin.rpc("push_secret", { n }); return typeof r.data === "string" ? r.data : null; };

async function keys() {
  let pub = await secret("vapid_public"), priv = await secret("vapid_private");
  if (!pub || !priv) {
    const kp = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
    const jwk = await crypto.subtle.exportKey("jwk", kp.privateKey);
    const raw = new Uint8Array(65); raw[0] = 4; raw.set(fromB64u(jwk.x!), 1); raw.set(fromB64u(jwk.y!), 33);
    await admin.rpc("push_store_keys", { pub: b64u(raw), priv: jwk.d! });
    pub = await secret("vapid_public"); priv = await secret("vapid_private");
  }
  webpush.setVapidDetails("https://fantasyorientering.se", pub!, priv!);
  return pub!;
}

type Sub = { endpoint: string; user_id: string; p256dh: string; auth: string };
async function send(subs: Sub[], payload: Record<string, unknown>) {
  let ok = 0;
  for (const s of subs) {
    try {
      await webpush.sendNotification({ endpoint: s.endpoint, keys: { p256dh: s.p256dh, auth: s.auth } }, JSON.stringify(payload), { TTL: 6 * 3600 });
      ok++;
    } catch (e) {
      const code = (e as { statusCode?: number }).statusCode;
      if (code === 404 || code === 410) await admin.from("push_subs").delete().eq("endpoint", s.endpoint);   // the browser dropped it
    }
  }
  return ok;
}
const DAYS = ["söndag", "måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag"];
function when(t: Date) {
  const f = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Stockholm", weekday: "long", hour: "2-digit", minute: "2-digit" }).formatToParts(t);
  const g = (k: string) => f.find((p) => p.type === k)?.value || "";
  return `${g("weekday") || DAYS[t.getDay()]} kl ${g("hour")}.${g("minute")}`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  const body = await req.json().catch(() => ({}));
  /* a player's own test notification */
  if (body && body.test) {
    const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: req.headers.get("Authorization") || "" } } });
    const { data: u } = await sb.auth.getUser();
    if (!u?.user) return json({ ok: false, msg: "Logga in först." }, 401);
    await keys();
    const { data: subs } = await admin.from("push_subs").select("*").eq("user_id", u.user.id);
    const n = await send((subs || []) as Sub[], { title: "Påminnelser är på", body: "Du får en påminnelse innan laget låses om du inte har valt det.", url: "/" });
    return json({ ok: n > 0, sent: n });
  }
  /* the cron job */
  const want = await secret("push_cron_key");
  if (!want || req.headers.get("x-cron-key") !== want) return json({ ok: false }, 403);
  await keys();
  const now = Date.now();
  const { data: rounds } = await admin.from("season_rounds").select("round,locks_at,skip").gt("locks_at", new Date(now).toISOString()).lte("locks_at", new Date(now + 25 * 3600e3).toISOString());
  let sent = 0;
  for (const r of rounds || []) {
    if (r.skip) continue;
    const lockAt = new Date(r.locks_at), hours = (lockAt.getTime() - now) / 3600e3;
    const kind = hours <= 3 ? "h2" : "d1";
    const { data: subs } = await admin.from("push_subs").select("*");
    if (!subs?.length) continue;
    const users = [...new Set(subs.map((s) => s.user_id))];
    const [{ data: have }, { data: done }, { data: before }] = await Promise.all([
      admin.from("squads").select("user_id").eq("round", r.round).in("user_id", users),
      admin.from("push_log").select("user_id").eq("round", r.round).eq("kind", kind).in("user_id", users),
      admin.from("squads").select("user_id").lt("round", r.round).in("user_id", users),
    ]);
    const skip = new Set([...(have || []), ...(done || [])].map((x) => x.user_id));
    /* someone with a squad from an earlier round keeps it (it carries over): one gentle reminder, a day before */
    const carried = new Set((before || []).map((x) => x.user_id));
    for (const uid of users.filter((u) => !skip.has(u) && !(kind === "h2" && carried.has(u)))) {
      const mine = subs.filter((s) => s.user_id === uid) as Sub[];
      const n = await send(mine, carried.has(uid)
        ? { title: "Kolla ditt lag", body: `Nästa omgång låses ${when(lockAt)}. Ändrar du inget spelar ditt lag från förra omgången.`, url: "/" }
        : kind === "h2"
        ? { title: "Snart låst", body: `Du har inget lag i nästa omgång. Det låses ${when(lockAt)}.`, url: "/" }
        : { title: "Välj ditt lag", body: `Nästa omgång låses ${when(lockAt)}. Du har inte valt något lag än.`, url: "/" });
      await admin.from("push_log").insert({ user_id: uid, round: r.round, kind });
      sent += n;
    }
  }
  return json({ ok: true, sent });
});

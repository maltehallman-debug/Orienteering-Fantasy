// "Delete my account" on the profile page. Only the signed-in user can delete their own account: the user is read
// from their own login token, never from the request body. Their uploaded pictures are removed from storage, then the
// login itself; every table row of theirs (profile, squads, saves, leagues they own, memberships, scores, photo
// submissions) goes with it, as all of them cascade from auth.users.
import { createClient } from "jsr:@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (o: unknown, status = 200) => new Response(JSON.stringify(o), { status, headers: { ...cors, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ ok: false, msg: "Use POST." }, 405);
  const auth = req.headers.get("Authorization") || "";
  const user = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: auth } } });
  const { data: u, error } = await user.auth.getUser();
  if (error || !u?.user) return json({ ok: false, msg: "Sign in first." }, 401);
  const uid = u.user.id;
  const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  // pictures they uploaded: their avatar and any runner photos (both stored under a folder named by their id)
  for (const bucket of ["avatars", "runner-photos"]) {
    const { data: files } = await admin.storage.from(bucket).list(uid, { limit: 1000 });
    if (files && files.length) await admin.storage.from(bucket).remove(files.map((f) => `${uid}/${f.name}`));
  }
  const del = await admin.auth.admin.deleteUser(uid);
  if (del.error) return json({ ok: false, msg: "Could not delete the account. Try again." }, 500);
  return json({ ok: true });
});

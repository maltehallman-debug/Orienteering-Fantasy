/* A preview frame: the real site, running in its sandbox (?sandbox=1: in-memory storage, no login, nothing saved)
   with the editing bridge on (?edit=1). Messages go both ways with postMessage, checked by origin. */
import { frameUrl, SITE_ORIGIN, DEVICES } from "./config.js";
import { S } from "./store.js";

export function makeFrame(host, opts = {}) {
  const wrap = document.createElement("div"); wrap.className = "frame-wrap";
  const stage = document.createElement("div"); stage.className = "frame-stage";
  const ifr = document.createElement("iframe"); ifr.title = "Förhandsvisning av sajten"; ifr.loading = "eager";
  ifr.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms allow-popups");
  stage.appendChild(ifr); wrap.appendChild(stage); host.appendChild(wrap);
  const f = { ifr, wrap, ready: false, tab: opts.tab || "home", role: opts.role || "guest", device: opts.device || "mobile", cfg: opts.cfg || null, handlers: {}, queue: [] };
  f.on = (t, fn) => { (f.handlers[t] = f.handlers[t] || []).push(fn); return f; };
  f.send = m => { const msg = Object.assign({ src: "of-admin" }, m); if (f.ready || m.t === "hello") ifr.contentWindow && ifr.contentWindow.postMessage(msg, SITE_ORIGIN); else f.queue.push(msg); };
  const onMsg = e => {
    if (e.source !== ifr.contentWindow || e.origin !== SITE_ORIGIN) return; const m = e.data || {}; if (m.src !== "of-site") return;
    if (m.t === "ready" && !f.ready) { f.ready = true; f.info = m; f.send({ t: "role", role: f.role }); f.send({ t: "tab", tab: f.tab }); if (f.cfg) f.send({ t: "cfg", cfg: f.cfg() });
      f.queue.splice(0).forEach(x => ifr.contentWindow.postMessage(x, SITE_ORIGIN)); }
    if (m.t === "error") { S.errors.unshift({ at: new Date().toISOString(), msg: m.msg, where: m.where || "", tab: f.tab, role: f.role }); S.errors = S.errors.slice(0, 200); }
    if (m.t === "tab") f.tab = m.tab;
    (f.handlers[m.t] || []).forEach(fn => fn(m));
  };
  addEventListener("message", onMsg);
  /* keep saying hello until the page answers (it may still be loading) */
  const hello = () => { if (f.ready) return; f.send({ t: "hello" }); setTimeout(hello, 400); };
  ifr.addEventListener("load", () => { f.ready = false; hello(); });
  f.load = () => { f.ready = false; ifr.src = frameUrl() + "&r=" + Date.now(); };
  f.setDevice = d => { f.device = d; fit(); };
  f.setRole = r => { f.role = r; f.send({ t: "role", role: r }); };
  f.setTab = t => { f.tab = t; f.send({ t: "tab", tab: t }); };
  f.push = cfg => f.send({ t: "cfg", cfg });
  /* the device's width at scale, so a phone or a desktop fits the space there is */
  const fit = () => {
    const d = DEVICES.find(x => x[0] === f.device) || DEVICES[0], w = d[2], h = d[3];
    const avail = wrap.clientWidth || host.clientWidth || w, availH = opts.fixedHeight || Math.max(420, (window.innerHeight - (wrap.getBoundingClientRect().top || 120) - 24));
    const sc = Math.min(1, avail / w, opts.fitHeight ? availH / h : 1);
    Object.assign(ifr.style, { width: w + "px", height: (opts.fitHeight ? h : Math.max(h, availH / sc)) + "px", transform: `scale(${sc})` });
    Object.assign(stage.style, { width: w * sc + "px", height: (opts.fitHeight ? h : Math.max(h, availH / sc)) * sc + "px" });
  };
  f.fit = fit; const ro = new ResizeObserver(fit); ro.observe(host);
  f.destroy = () => { removeEventListener("message", onMsg); ro.disconnect(); wrap.remove(); };
  f.load(); requestAnimationFrame(fit);
  return f;
}

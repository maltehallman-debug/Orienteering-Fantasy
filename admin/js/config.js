/* Settings for the dashboard. Nothing secret lives here: the Supabase URL and the publishable key are the same ones the
   public site already ships, and every write is checked by row level security in the database (public.is_admin()). */
export const SB_URL = "https://hjpfmubvpvftxyyemltn.supabase.co";
export const SB_KEY = "sb_publishable_Ent2RuVrh-iKyjT1or8gOw_UFdZ74ch";
export const REPO = "maltehallman-debug/Orienteering-Fantasy";
export const PUBLIC_SITE = "https://www.fantasyorientering.se/";

/* On GitHub Pages the dashboard edits the live site in a frame; served next to the site (Vercel or a local server) it
   uses the site beside it. */
export const SITE = /\.github\.io$/.test(location.hostname) ? PUBLIC_SITE : new URL("../", location.href).href;
export const SITE_ORIGIN = new URL(SITE).origin;
export const frameUrl = () => SITE + "?sandbox=1&edit=1";

export const TABS = [
  ["home", "Hem"], ["team", "Lag"], ["rounds", "Poäng"], ["leagues", "Ligor"], ["rules", "Regler"], ["profile", "Profil"]];
export const ROLES = [
  ["gate", "Besökare, betaspärr"], ["guest", "Besökare utan konto"], ["user", "Inloggad spelare"], ["admin", "Administratör"]];
export const DEVICES = [["mobile", "Mobil", 390, 844], ["tablet", "Surfplatta", 820, 1180], ["desktop", "Dator", 1280, 860]];

/* sections that can be switched on and off as a whole (the site holds the matching selectors) */
export const FLAGS = [
  ["hem.nyheter", "Nyheter på startsidan"], ["hem.arets_manager", "Årets manager på startsidan"], ["hem.topplistor", "Topplistor på startsidan"],
  ["hem.live", "Livekortet"], ["hem.sammanfattning", "Veckans sammanfattning"], ["hem.rival", "Rivalkortet"],
  ["lag.autofyll", "Fyll laget automatiskt"], ["lag.lopp", "Veckans lopp på Lag"], ["lag.foton", "Egna foton på löparkort"],
  ["ligor.topplistor", "Topplistor på Ligor"], ["sidfot.knappar", "Knapparna längst ner"], ["topp.nedrakning", "Nedräkningen överst"]];

/* the site's design tokens that the theme editor offers */
export const TOKENS = [
  ["--ds-navy", "Marinblå (huvudfärg)", "color", "#003c68"], ["--ds-yellow", "Gul (accent)", "color", "#ffe74d"],
  ["--ds-ink", "Text", "color", "#0b0f14"], ["--ds-ink-2", "Sekundär text", "color", "#5b6773"],
  ["--ds-surface", "Kortens bakgrund", "color", "#ffffff"], ["--ds-line", "Kantlinjer", "color", "#e3e7ec"],
  ["--ds-good", "Grönt (upp)", "color", "#1a9e4b"], ["--ds-bad", "Rött (ner)", "color", "#d23b3b"],
  ["--ds-r-box", "Hörn på kort", "px", "20px"], ["--ds-r-ctl", "Hörn på fält", "px", "14px"],
  ["--ds-fs-h2", "Sidrubrik", "px", "28px"], ["--ds-fs-h3", "Kortrubrik", "px", "17px"], ["--ds-fs-body", "Brödtext", "px", "14px"]];

export const FONTS = [["", "Som sajten"], ["Montserrat, sans-serif", "Montserrat"], ["'Barlow Condensed', sans-serif", "Barlow Condensed"],
  ["-apple-system, Segoe UI, Roboto, sans-serif", "Systemtypsnitt"], ["Georgia, serif", "Georgia"]];

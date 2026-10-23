function makeEngine(D) {
  const R = D.rounds.length, N = D.runners.length;
  const pts = Array.from({ length: R }, () => new Int32Array(N));
  const starts = Array.from({ length: R }, () => new Int32Array(N));
  D.rounds.forEach((rd, r) => rd.ev.forEach(ei => D.res[ei].forEach(row => { pts[r][row[0]] += row[5]; starts[r][row[0]]++; })));
  const hist = Array.from({ length: N }, () => []);
  D.res.forEach((rows, ei) => rows.forEach(row => hist[row[0]].push({ ev: ei, kind: row[1], rank: row[2], t: row[3], gap: row[4], pts: row[5] })));
  const cutoff = r => (r >= R ? "9999-12-31" : D.rounds[r].start);
  const visible = (i, r) => hist[i].filter(h => D.events[h.ev].date < cutoff(r));
  function stats(i, r) {
    const h = visible(i, r);
    const total = h.reduce((a, x) => a + x.pts, 0);
    const last3 = h.slice(-3);
    const form = last3.length ? last3.reduce((a, x) => a + x.pts, 0) / last3.length : 0;
    return { starts: h.length, total, form, last: h.length ? h[h.length - 1].pts : 0 };
  }
  const price = (i, r) => D.prices[Math.min(r, R - 1)][i];
  const clubOf = i => D.runners[i].c;
  function errors(squad, r) {
    const e = [];
    if (squad.length !== D.squad) e.push(`Pick exactly ${D.squad} runners`);
    if (new Set(squad).size !== squad.length) e.push("Duplicate runner");
    const cc = {};
    squad.forEach(i => { cc[clubOf(i)] = (cc[clubOf(i)] || 0) + 1; if (!D.runners[i].p) e.push("Runner not in pool"); });
    Object.entries(cc).forEach(([c, n]) => { if (n > D.clubMax) e.push(`Max ${D.clubMax} runners from ${c}`); });
    return e;
  }
  // chips, one use each per season: wc wildcard (free transfers), tc 3x boost, ax A team double, bb B team plays like the A team, yo youth (16) double
  const CHIPS = ["wc", "tc", "ax", "bb", "yo"];
  const A = D.aSize || Math.ceil(D.squad / 2);
  const youth = i => /16$/.test(D.runners[i].k);
  // points multiplier for the runner at position k of an ordered squad (A team first), before the boost
  function teamMult(i, k, chip) {
    const a = k < A;
    return (a ? 2 : 1) * (chip === "ax" && a ? 2 : 1) * (chip === "bb" && !a ? 2 : 1) * (chip === "yo" && youth(i) ? 2 : 1);
  }
  function newState(start = 0) { return { start, round: start, squad: [], captain: null, vice: null, bank: D.budget, chips: { wc: false, tc: false, ax: false, bb: false, yo: false }, log: [], total: 0 }; }
  function transfersFor(state, squad) {
    if (!state.squad.length) return { n: 0, out: [], inn: squad.slice() };
    const out = state.squad.filter(i => !squad.includes(i)), inn = squad.filter(i => !state.squad.includes(i));
    return { n: inn.length, out, inn };
  }
  function bankAfter(state, squad) {
    const r = state.round, t = transfersFor(state, squad);
    let b = state.bank;
    t.out.forEach(i => b += price(i, r));
    t.inn.forEach(i => b -= price(i, r));
    return b;
  }
  // opts.budget === false skips the budget check: prices move after a squad is locked, so a squad that was
  // affordable when it was locked must still count when the round is scored
  function planErrors(state, plan, opts) {
    const r = state.round, e = errors(plan.squad, r);
    if (!plan.squad.includes(plan.captain)) e.push("Pick a runner to boost");
    if (plan.chip && !CHIPS.includes(plan.chip)) e.push("Unknown chip");
    if (plan.chip && state.chips[plan.chip]) e.push("Chip already used");
    if (plan.chip === "wc" && !state.squad.length) e.push("Wildcard cannot be used for the opening squad");
    // a bank that went negative only because prices moved never blocks keeping the same squad
    if (!(opts && opts.budget === false)) { const b = bankAfter(state, plan.squad); if (b < 0 && b < state.bank) e.push("Over budget"); }
    return e;
  }
  function play(state, plan, opts) {
    const e = planErrors(state, plan, opts);
    if (e.length) throw new Error(e.join("; "));
    const r = state.round, t = transfersFor(state, plan.squad);
    const penalty = plan.chip === "wc" ? 0 : Math.max(0, t.n - D.freeTransfers) * D.penalty;
    // "captain" is the boosted runner (field name kept so old saves still load); no fallback if they do not race
    const capLive = starts[r][plan.captain] > 0 ? plan.captain : null;
    const mult = plan.chip === "tc" ? 3 : 2;
    // plan.squad is ordered: the first A runners are the A team
    const rows = plan.squad.map((i, k) => { const tm = teamMult(i, k, plan.chip); return { i, pts: pts[r][i], starts: starts[r][i], cap: i === capLive, team: k < A ? "A" : "B", mult: tm * (i === capLive ? mult : 1) }; });
    const base = rows.reduce((a, x, k) => a + x.pts * teamMult(x.i, k, plan.chip), 0);
    const capExtra = capLive === null ? 0 : (mult - 1) * pts[r][capLive] * teamMult(capLive, plan.squad.indexOf(capLive), plan.chip);
    const total = base + capExtra - penalty;
    const ns = {
      start: state.start || 0, round: r + 1, squad: plan.squad.slice(), captain: plan.captain, vice: null, bank: bankAfter(state, plan.squad),
      chips: Object.fromEntries(CHIPS.map(c => [c, !!(state.chips[c] || plan.chip === c)])),
      total: state.total + total,
      log: state.log.concat([{ round: r, squad: plan.squad.slice(), captain: plan.captain, vice: null, capLive, chip: plan.chip || null, transfers: t.n, penalty, base, capExtra, total, in: t.inn, out: t.out }])
    };
    return { state: ns, result: { rows, base, capExtra, penalty, total, capLive, mult, transfers: t.n } };
  }
  // ----- live season: one locked squad per round, the last squad carries over when none is locked -----
  // picks: { roundIndex: { squad, captain, chip } } with runner indices. Rounds from start to upto (inclusive) are
  // scored with whatever results are in, so a round in progress gives provisional points. Every client runs this
  // same function on the same published squads, so every league table shows the same numbers.
  function season(picks, start, upto) {
    let st = newState(start), prev = null;
    const rounds = [];
    for (let r = start; r <= upto && r < R; r++) {
      st.round = r;
      let p = picks[r] ? { squad: picks[r].squad.slice(), captain: picks[r].captain, chip: picks[r].chip || null } : null, carried = false;
      if (p && p.chip && st.chips[p.chip]) p.chip = null;
      if (!p || planErrors(st, p, { budget: false }).length) {
        if (!prev) continue; // no squad yet: the manager joins later
        p = { squad: prev.squad.slice(), captain: prev.captain, chip: null }; carried = true;
      }
      let o;
      try { o = play(st, p, { budget: false }); } catch (e) { continue; }
      st = o.state; prev = p;
      rounds.push(Object.assign({ round: r, carried, rows: o.result.rows, mult: o.result.mult }, st.log[st.log.length - 1]));
    }
    st.round = Math.max(st.round, Math.min(upto + 1, R));
    return { state: st, rounds };
  }
  // ----- benchmarks -----
  function rating(i, r, m0) {
    const h = visible(i, r); if (!h.length) return null;
    let num = 0, den = 0;
    for (let a = 0; a < h.length; a++) { const w = Math.pow(0.9, a); num += w * h[h.length - 1 - a].pts; den += w; }
    return (num + 2 * m0) / (den + 2);
  }
  function leagueMean(r) {
    let s = 0, n = 0;
    D.res.forEach((rows, ei) => { if (D.events[ei].date < cutoff(r)) rows.forEach(x => { s += x[5]; n++; }); });
    return n ? s / n : 170;
  }
  // the cheapest price in the pool this round: what each still-empty place must at least cost
  const minP = r => { let m = Infinity; for (let i = 0; i < N; i++) if (D.runners[i].p) m = Math.min(m, price(i, r)); return m };
  function greedy(order, r) {
    const sq = [], cc = {}, mp = minP(r); let cost = 0;
    for (const i of order) {
      if (sq.length === D.squad) break;
      const p = price(i, r), left = D.squad - sq.length - 1;
      if (cost + p + left * mp > D.budget) continue;
      if ((cc[clubOf(i)] || 0) >= D.clubMax) continue;
      sq.push(i); cc[clubOf(i)] = (cc[clubOf(i)] || 0) + 1; cost += p;
    }
    return sq;
  }
  function bestCaptain(sq, r) { return sq.slice().sort((a, b) => pts[r][b] - pts[r][a]); }
  function bots() {
    const out = { formChaser: 0, setForget: 0, ceiling: 0 };
    let fixed = null;
    for (let r = 0; r < R; r++) {
      const m0 = leagueMean(r);
      const pool = []; for (let i = 0; i < N; i++) if (D.runners[i].p) pool.push(i);
      const rt = i => { const x = rating(i, r, m0); return x === null ? m0 * 0.8 : x; };
      const order = pool.slice().sort((a, b) => rt(b) - rt(a));
      const fc = greedy(order, r);
      const capF = fc.slice().sort((a, b) => rt(b) - rt(a));
      const sumF = fc.reduce((a, i) => a + pts[r][i], 0);
      const capLive = starts[r][capF[0]] > 0 ? capF[0] : undefined;
      out.formChaser += sumF + (capLive === undefined ? 0 : pts[r][capLive]);
      if (!fixed) fixed = fc.slice();
      const capS = fixed.slice().sort((a, b) => rt(b) - rt(a));
      const capSL = starts[r][capS[0]] > 0 ? capS[0] : undefined;
      out.setForget += fixed.reduce((a, i) => a + pts[r][i], 0) + (capSL === undefined ? 0 : pts[r][capSL]);
      const top = pool.slice().sort((a, b) => pts[r][b] - pts[r][a]);
      const cl = []; const cc = {};
      for (const i of top) { if (cl.length === D.squad) break; if ((cc[clubOf(i)] || 0) >= D.clubMax) continue; cl.push(i); cc[clubOf(i)] = (cc[clubOf(i)] || 0) + 1; }
      out.ceiling += cl.reduce((a, i) => a + pts[r][i], 0) + pts[r][cl[0]];
    }
    return out;
  }
  function roundBest(r, k = 5) {
    const a = []; for (let i = 0; i < N; i++) if (starts[r][i]) a.push([i, pts[r][i]]);
    return a.sort((x, y) => y[1] - x[1]).slice(0, k);
  }
  return { R, N, pts, starts, hist, visible, stats, price, errors, newState, transfersFor, bankAfter, planErrors, play, season, teamMult, CHIPS, A, youth, bots, roundBest, greedy, rating, leagueMean };
}
if (typeof module !== "undefined") module.exports = { makeEngine };
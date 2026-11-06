// The logic behind the size panel on the Analyst tab: what to do with what a person types, which levels to size, and which warnings apply.
// Pure functions, no network, no keys, nothing that can place an order. The arithmetic itself is size.mjs (the desk's own rules).
import { sizeCall, FEE } from "./size.mjs";

export const MIN_NOTIONAL = 5.0;                 // Bitget's smallest order value in USD (desk.MIN_NOTIONAL)
export const SCALP_STOP = 0.004;                 // a stop closer than this to the entry is "scalp-sized": where the desk's calls have lost

// What a person typed -> a positive finite number, or null. "20", " 20.5 ", "1,000", ".5" are fine; "", "abc", "-3", "0", "1e9x" are not.
export function parseNum(s) {
  const t = String(s ?? "").trim().replace(/,/g, "");
  if (!/^(\d+\.?\d*|\.\d+)$/.test(t)) return null;
  const v = Number(t);
  return Number.isFinite(v) && v > 0 ? v : null;
}

// The levels to size for an open desk call. mode "now": enter at the price now (the stop and target stay where the desk put them);
// "logged": enter at the price the desk logged. Falls back to the logged entry when there is no usable price now.
export function levelsFor(call, mode) {
  const useNow = mode === "now" && Number.isFinite(call.mark) && call.mark > 0;
  return { side: call.side, entry: useNow ? call.mark : call.entry, stop: call.stop, target: call.target };
}

// Size one trade and say what is wrong with it. Returns { ok: false, reason } or { ok: true, r, ...flags }.
//   r            sizeCall's result (position, margin, liquidation, loss at the stop, gain at the target, room, status, maxLev)
//   belowMin     the position would be under the exchange's minimum order; needRiskPct is the risk % that would just reach it
//   notAffordable  the margin is more than the balance; minLev is the lowest leverage that fits
//   capped       the desk's 3x rule cut the position, so the loss at the stop is smaller than the chosen risk
//   scalpStop    the stop is under 0.4% from the entry, the size where the desk's calls have lost
//   noTarget     no target was given (a trade typed by hand); targetGone: the price is already past it. Neither has a gain figure
//   rr           reward to risk from this entry (null without a usable target)
export function buildSizing({ side, entry, stop, target, bal, lev, riskPct }) {
  if (!(bal > 0)) return { ok: false, reason: "Enter your balance." };
  if (!(lev >= 1)) return { ok: false, reason: "Enter a leverage of 1 or more." };
  if (!(riskPct > 0) || riskPct > 100) return { ok: false, reason: "Enter a risk between 0 and 100 percent." };
  if (!(entry > 0) || !(stop > 0)) return { ok: false, reason: "Enter an entry and a stop." };
  const r = sizeCall({ side, entry, stop, target, bal, lev, riskPct: riskPct / 100 });
  if (!r) return { ok: false, reason: side === "long" ? "The stop has to be below the entry for a long." : "The stop has to be above the entry for a short." };
  const noTarget = !(target > 0);
  const targetGone = !noTarget && r.gainAtTarget === null;
  return {
    ok: true, r, noTarget, targetGone,
    belowMin: r.notional < MIN_NOTIONAL,
    needRiskPct: (MIN_NOTIONAL * (r.stopPct + FEE) / bal) * 100,
    notAffordable: !r.affordable,
    minLev: Math.max(1, Math.ceil(r.notional / bal - 1e-9)),
    capped: r.capped,
    scalpStop: r.stopPct < SCALP_STOP,
    rr: noTarget || targetGone ? null : r.targetPct / r.stopPct,
  };
}

// Coins to show: enough digits to see a small order, few enough to read.
export function fmtQty(q) {
  if (!Number.isFinite(q)) return "–";
  const a = Math.abs(q);
  return a >= 100 ? q.toFixed(0) : a >= 1 ? q.toFixed(2) : a >= 0.01 ? q.toFixed(4) : q.toFixed(6);
}

// Is an open call still worth entering from the price now? Not when the price has already reached the stop or the target, when the desk's own
// reward-to-risk floor no longer holds from here (`sw.valid`), or when the stop is already scalp-sized from here (the price ran most of the way to it).
export function liveFromHere(c) {
  if (c.sw && c.sw.valid === false) return false;
  const px = Number.isFinite(c.mark) && c.mark > 0 ? c.mark : c.entry;
  const dir = c.side === "short" ? -1 : 1;
  if (!(dir * (px - c.stop) > 0)) return false;                     // at or past the stop
  if (Number.isFinite(c.target) && dir * (c.target - px) <= 0) return false;   // at or past the target
  return Math.abs(px - c.stop) / px >= SCALP_STOP;
}

// The call the panel opens on, so nobody has to choose a method: the newest open sweet-spot call that is still worth entering from here and counts in
// the forward test; failing that the newest such call that does not count; failing that none. `scored(c)` says whether a call counts in the test.
// Middle and scalp-sized calls are never the pick.
export function todaysPick(calls, scored) {
  const sweet = calls.filter((c) => c.sw && c.sw.kind === "sweet" && liveFromHere(c));
  const newest = (xs) => xs.reduce((best, c) => (best === null || c.id > best.id ? c : best), null);
  return newest(sweet.filter((c) => scored(c))) || newest(sweet);
}

// What the desk's rule saw, in plain words, instead of its jargon.
const PLAIN = {
  SR: { long: "price bounced up off a level that has held several times before", short: "price was turned back down at a level that has held several times before" },
  FIB: { long: "price pulled back into a Fibonacci zone of the last upward move and turned up again", short: "price pulled back up into a Fibonacci zone of the last downward move and turned down again" },
  SMC: { long: "price dipped under the lowest low of the last 24 hours and snapped back above it (a liquidity sweep)", short: "price poked above the highest high of the last 24 hours and fell back below it (a liquidity sweep)" },
};
export function plainSetup(method, side) {
  return (PLAIN[method] && PLAIN[method][side === "short" ? "short" : "long"]) || "the desk's rule fired";
}

// The leverage to type on the exchange when the person has not chosen one. Leverage does NOT change what is lost at the stop (the position size and the
// stop do that); it only decides how much of the balance is locked as margin and how far away liquidation is. So: at least 3x, enough to keep the
// margin at or under half the balance, and never above the highest leverage that keeps liquidation twice as far as the stop (r.maxLev).
// `fits` is false when even that leverage cannot carry the position inside the balance.
export function recommendedLeverage(r, bal) {
  const comfortable = Math.max(3, Math.ceil((2 * r.notional) / bal - 1e-9));
  const lev = Math.min(comfortable, r.maxLev);
  return { lev, fits: r.notional / lev <= bal };
}

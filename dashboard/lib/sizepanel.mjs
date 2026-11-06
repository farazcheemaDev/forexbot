// The logic behind the size panel on the Analyst tab: what to do with what a person types, which levels to size, and which warnings apply.
// Pure functions, no network, no keys, nothing that can place an order. The arithmetic itself is size.mjs (the desk's own rules).
import { sizeCall, FEE } from "./size.mjs";

export const MIN_NOTIONAL = 5.0;                 // Bitget's smallest order value in USD (desk.MIN_NOTIONAL)

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
    rr: noTarget || targetGone ? null : r.targetPct / r.stopPct,
  };
}

// Coins to show: enough digits to see a small order, few enough to read.
export function fmtQty(q) {
  if (!Number.isFinite(q)) return "–";
  const a = Math.abs(q);
  return a >= 100 ? q.toFixed(0) : a >= 1 ? q.toFixed(2) : a >= 0.01 ? q.toFixed(4) : q.toFixed(6);
}

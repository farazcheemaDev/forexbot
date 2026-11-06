// Position sizing for ONE desk call, from a futures balance, a leverage and a risk share. Pure arithmetic: no network, no keys.
// The rules are the desk's own (analyst.py): risk a fixed share of the balance on the stop, fee 0.12% a round trip, open notional capped at 3x the
// balance, and the repo's liquidation approximation for isolated margin (analyst.leveraged_result): the price moving 1/leverage minus 0.5% against you.
export const FEE = 0.0012;
export const MAINT = 0.005;
export const GROSS_CAP = 3.0;

export function sizeCall({ side, entry, stop, target, bal, lev, riskPct }) {
  if (![entry, stop, bal, lev, riskPct].every((x) => Number.isFinite(x) && x > 0) || lev < 1) return null;
  const dir = side === "long" ? 1 : -1;
  if (dir * (entry - stop) <= 0) return null;                                  // the stop has to sit on the losing side of the entry
  const stopPct = Math.abs(entry - stop) / entry;
  const targetPct = Number.isFinite(target) ? (dir * (target - entry)) / entry : null;
  const wanted = (bal * riskPct) / (stopPct + FEE);                            // the loss AT THE STOP, fee included, equals the risk share
  const capped = wanted > bal * GROSS_CAP;
  const notional = capped ? bal * GROSS_CAP : wanted;
  const margin = notional / lev;
  const liqDist = 1 / lev - MAINT;
  const liqPrice = entry * (1 - dir * liqDist);
  const lossAtStop = notional * (stopPct + FEE);
  return {
    stopPct, targetPct, notional, qty: notional / entry, capped, margin, marginShare: margin / bal, affordable: margin <= bal,
    liqDist, liqPrice, lossAtStop, lossShare: lossAtStop / bal,
    gainAtTarget: targetPct !== null && targetPct > 0 ? notional * (targetPct - FEE) : null,
    room: liqDist - stopPct, roomX: liqDist / stopPct,
    status: liqDist <= stopPct ? "danger" : liqDist >= 2 * stopPct ? "ok" : "tight",       // ok = liquidation at least twice as far as the stop
    maxLev: Math.max(1, Math.floor(1 / (2 * stopPct + MAINT))),                            // the highest leverage that keeps that 2x gap
  };
}

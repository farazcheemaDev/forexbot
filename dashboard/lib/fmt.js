// Number and time formatting shared by the page's components (pure functions, safe on server and client).

export const BOOKS = {
  trend: { name: "Trend", desc: "Breakouts on 12 big coins, long or short" },
  mn: { name: "Market-neutral", desc: "Long the strongest coins, short the weakest" },
  carry: { name: "Funding carry", desc: "Collects funding: long where shorts pay, short where longs pay" },
  sleeve: { name: "Bear sleeve", desc: "Trades only in bear markets" },
  daily: { name: "Daily breakout", desc: "Daily Bollinger breakouts on the top 40 coins" },
  capit2: { name: "Crash buys", desc: "Buys a coin after a 10% crash" },
  news: { name: "News shorts", desc: "Shorts a coin after a bad Binance notice" },
  ndx: { name: "NASDAQ dip", desc: "Buys QQQ after a sharp NASDAQ drop" },
};
export const bookName = (b) => BOOKS[b]?.name || b;

const ok = (v) => v !== null && v !== undefined && Number.isFinite(+v);

export function usd(v, { sign = false, dp = 2 } = {}) {
  if (!ok(v)) return "–";
  const n = +v;
  const s = Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });
  if (sign) return `${n > 0 ? "+" : n < 0 ? "−" : ""}$${s}`;
  return `${n < 0 ? "−" : ""}$${s}`;
}

export function pct(v, { dp = 2, sign = true } = {}) {
  if (!ok(v)) return "–";
  const n = +v * 100;
  return `${sign && n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(dp)}%`;
}

export function priceFmt(v) {
  if (!ok(v)) return "–";
  const n = +v, a = Math.abs(n);
  if (a >= 1000) return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (a >= 1) return n.toFixed(4);
  const s = n.toPrecision(4);
  return s.includes("e") ? n.toFixed(10) : s;
}

export const tone = (v) => (ok(v) && +v > 0 ? "up" : ok(v) && +v < 0 ? "down" : "");

// The feed's times are UTC ("YYYY-MM-DD HH:MM:SS", a day "YYYY-MM-DD", or unix seconds). Before the page has mounted
// they print in UTC (what the server renders); after mounting, in the viewer's own time zone.
export function toDate(t) {
  if (t === null || t === undefined || t === "") return null;
  if (typeof t === "number") return new Date(t * 1000);
  const s = String(t);
  return new Date(s.length <= 10 ? `${s}T00:00:00Z` : s.replace(" ", "T") + "Z");
}

export function when(t, local) {
  const d = toDate(t);
  if (!d || Number.isNaN(d.getTime())) return "–";
  const o = { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false };
  return local ? d.toLocaleString("en-GB", o) : `${d.toLocaleString("en-GB", { ...o, timeZone: "UTC" })} UTC`;
}

export function dayLabel(t) {
  const d = toDate(t);
  return d ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }) : "";
}

export const ACCOUNT_NAMES = { main: "Main account", fresh: "Fresh $300" };

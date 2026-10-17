import { getEquitySeries, getSnapshot } from "../lib/data";
import Refresh from "./Refresh";

export const dynamic = "force-dynamic";

const BOOKS = [
  ["trend", "Trend (triple)"], ["mn", "Market-neutral"], ["sleeve", "Bear sleeve"], ["carry", "Funding carry"],
  ["daily", "Daily Bollinger"], ["capit2", "Capitulation (capit2)"], ["news", "News book"], ["ndx", "NASDAQ dip"],
  ["fees", "Fees"],
];

const usd = (v, d = 2) => (v === null || v === undefined || Number.isNaN(+v) ? "-" :
  `${+v < 0 ? "-" : ""}$${Math.abs(+v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}`);
const pct = (v, d = 1) => (v === null || v === undefined || Number.isNaN(+v) ? "-" : `${+v >= 0 ? "+" : ""}${(+v * 100).toFixed(d)}%`);
const tone = (v) => (+v > 0 ? "up" : +v < 0 ? "down" : "");
const num = (v, d = 4) => (v === null || v === undefined || Number.isNaN(+v) ? "-" : (+v).toPrecision(d));

function ago(utc) {
  if (!utc) return null;
  const t = Date.parse(utc.replace(" ", "T") + "Z");
  return Math.round((Date.now() - t) / 60000);
}

function Spark({ points }) {
  if (!points || points.length < 2) return <p className="sub">The equity line appears after the first pushes.</p>;
  const xs = points.map((p) => p[0]), ys = points.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const W = 1000, H = 120, pad = 6;
  const sx = (x) => pad + ((x - x0) / Math.max(x1 - x0, 1)) * (W - 2 * pad);
  const sy = (y) => H - pad - ((y - y0) / Math.max(y1 - y0, 1e-9)) * (H - 2 * pad);
  const d = points.map((p, i) => `${i ? "L" : "M"}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`).join(" ");
  const up = ys[ys.length - 1] >= ys[0];
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img"
      aria-label={`equity from ${ys[0].toFixed(2)} to ${ys[ys.length - 1].toFixed(2)}`}>
      <path d={d} fill="none" stroke={up ? "var(--up)" : "var(--down)"} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Table({ cols, rows, empty = "None." }) {
  if (!rows || !rows.length) return <p className="sub">{empty}</p>;
  return (
    <div className="scroll">
      <table>
        <thead><tr>{cols.map((c) => <th key={c[0]} className={c[2] ? "r" : ""}>{c[0]}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{cols.map((c) => { const v = c[1](r); return <td key={c[0]} className={c[2] ? "r" : ""}>{v}</td>; })}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function Page() {
  let snap = null, eq = [], err = null;
  try {
    [snap, eq] = await Promise.all([getSnapshot(), getEquitySeries()]);
  } catch (e) {
    err = String(e.message || e);
  }
  if (!snap) {
    return (
      <main><Refresh />
        <div className="panel"><h1>Forexbot Live</h1>
          <p className="down">No snapshot yet{err ? `: ${err}` : ""}.</p>
          <p className="sub">The VM pushes one a minute once dashboard_push.py runs there (docs/24, dashboard/README.md).</p>
        </div>
      </main>
    );
  }
  const f = snap.final, h = snap.health;
  const age = ago(snap.generated_utc);
  const marks = (f.marks || []).map((m) => [Date.parse(m.day + "T00:00:00Z") / 1000, +m.equity]).filter((p) => Number.isFinite(p[1]));
  const series = eq.length > 5 ? eq : marks;
  const books = BOOKS.map(([k, name]) => ({ k, name, v: f.cum?.[k] ?? 0 }));     // every book, $0 until it trades
  const levPct = f.cap ? Math.min(100, (f.leverage / f.cap) * 100) : 0;
  return (
    <main>
      <Refresh />
      <div className="top">
        <div>
          <h1>The final machine - paper</h1>
          <div className="sub">
            Updated {snap.generated_utc} UTC
            {age !== null ? <span className={age > 5 ? "warn" : ""}> ({age} min ago{age > 5 ? " - the VM push may be stuck" : ""})</span> : null}
            {" "}| started {f.started} | BTC {usd(snap.btc, 0)}
          </div>
        </div>
        <form method="post" action="/api/logout"><button className="btn" type="submit">Sign out</button></form>
      </div>

      <div className="grid">
        <section className="panel wide">
          <div className="kpis">
            <div className="kpi"><div className="l">Equity</div><div className="v">{usd(f.equity)}</div></div>
            <div className="kpi"><div className="l">Since start ({usd(f.start, 0)})</div>
              <div className={`v ${tone(f.equity - f.start)}`}>{pct(f.equity / f.start - 1)}</div></div>
            <div className="kpi"><div className="l">Below peak ({usd(f.peak)})</div><div className={`v ${f.fall > 0 ? "down" : ""}`}>{pct(-f.fall)}</div></div>
            <div className="kpi"><div className="l">Gross leverage / cap</div><div className="v">{f.leverage}x / {f.cap}x</div>
              <div className="bar"><i style={{ width: `${levPct}%` }} /></div></div>
            <div className="kpi"><div className="l">News signals waiting</div><div className="v">{f.pending?.news ?? 0}</div></div>
          </div>
          <div style={{ height: 12 }} />
          <Spark points={series} />
          <div className="sub">{eq.length > 5 ? "Equity, one point a minute (last 2 days)" : "Equity at each daily mark"}</div>
        </section>

        <section className="panel">
          <h2>Profit and loss by book</h2>
          <Table cols={[["Book", (b) => b.name], ["P&L", (b) => <span className={tone(b.k === "fees" ? -b.v : b.v)}>{usd(b.k === "fees" ? -b.v : b.v)}</span>, 1]]}
            rows={books} />
        </section>

        <section className="panel">
          <h2>News, as it arrives (Binance announcements)</h2>
          <div className="sub">read {f.news_stats?.seen ?? 0} | traded {f.news_stats?.taken ?? 0} | dropped {f.news_stats?.dropped ?? 0}</div>
          <Table cols={[["Time (UTC)", (r) => new Date(r.ts * 1000).toISOString().slice(5, 16).replace("T", " ")],
            ["Type", (r) => <span className={`tag ${r.traded ? "trade" : ""}`}>{r.etype}</span>],
            ["Coins", (r) => (r.coins || []).map((c) => c.replace("USDT", "")).join(" ")],
            ["Headline", (r) => <span title={r.headline}>{r.headline.slice(0, 70)}</span>]]}
            rows={f.news_recent} empty="No new announcements since the bot started watching." />
        </section>

        <section className="panel wide">
          <h2>Open positions by book</h2>
          <Table cols={[["Trend", (r) => r.key], ["Side", (r) => r.side], ["Entry", (r) => num(r.entry), 1], ["Stop", (r) => num(r.stop), 1],
            ["Units", (r) => r.units, 1], ["Notional", (r) => usd(r.notional), 1], ["Since", (r) => (r.since || "").slice(0, 16)]]}
            rows={f.trend_open} empty="No trend positions." />
          <div style={{ height: 10 }} />
          <Table cols={[["Book", (r) => r.book], ["Symbol", (r) => r.symbol.replace("USDT", "")], ["Entry", (r) => num(r.entry), 1],
            ["Now", (r) => num(r.now), 1], ["Move", (r) => <span className={tone(r.book === "news" ? -r.move : r.move)}>{pct(r.move)}</span>, 1],
            ["Note", (r) => r.note]]}
            rows={[
              ...(f.books?.daily || []).map((r) => ({ book: "daily", symbol: r.symbol, entry: r.entry, now: r.now, move: r.ret, note: "" })),
              ...(f.books?.capit2 || []).map((r) => ({ book: "capit2", symbol: r.symbol, entry: r.entry, now: r.now, move: r.ret, note: "" })),
              ...(f.books?.news || []).map((r) => ({ book: "news", symbol: r.symbol, entry: r.entry, now: r.now, move: r.coin_move,
                note: `short vs BTC (${r.etype})` })),
              ...(f.books?.ndx || []).map((r) => ({ book: "ndx", symbol: r.symbol, entry: r.entry, now: r.now, move: r.ret,
                note: `${r.days} closes held` })),
            ]} empty="No daily / capit2 / news / NASDAQ positions." />
        </section>

        <section className="panel">
          <h2>The account's positions (netted, live prices)</h2>
          <div className="sub">gross {usd(f.gross)} = {f.leverage}x equity</div>
          <Table cols={[["Coin", (r) => r.symbol], ["Qty", (r) => num(r.qty, 5), 1], ["Value", (r) => <span className={tone(r.value)}>{usd(r.value)}</span>, 1]]}
            rows={(f.positions || []).slice(0, 20)} />
        </section>

        <section className="panel">
          <h2>Last orders</h2>
          <Table cols={[["Time", (r) => r.ts?.slice(5, 16)], ["Coin", (r) => r.symbol?.split("/")[0]], ["Side", (r) => r.side],
            ["Why", (r) => r.why], ["Value", (r) => usd(r.notional), 1]]} rows={(f.orders || []).slice(0, 15)} />
        </section>

        <section className="panel">
          <h2>Closed trades</h2>
          <Table cols={[["Time", (r) => (r.ts || "").slice(5, 16)], ["Book", (r) => r.book], ["Symbol", (r) => (r.symbol || "").replace("USDT", "")],
            ["Why", (r) => r.why], ["P&L", (r) => <span className={tone(r.pnl)}>{r.pnl === "" ? "-" : usd(r.pnl)}</span>, 1]]}
            rows={(f.closed || []).slice(0, 15)} />
        </section>

        <section className="panel">
          <h2>The other paper books</h2>
          <Table cols={[["Book", (r) => r.name], ["Equity / cash", (r) => r.equity !== undefined ? usd(r.equity) :
            Object.entries(r.cash || {}).map(([k, v]) => `${k} ${usd(v)}`).join(", ")],
            ["vs start", (r) => (r.equity !== undefined && r.start ? <span className={tone(r.equity - r.start)}>{pct(r.equity / r.start - 1)}</span> : "-"), 1]]}
            rows={Object.values(snap.others || {})} />
        </section>

        <section className="panel">
          <h2>Health (VM)</h2>
          <Table cols={[["Service", (r) => r[0]], ["State", (r) => <span className={r[1].active === "active" ? "up" : "down"}>{r[1].active}</span>],
            ["Restarts", (r) => r[1].restarts ?? "-", 1]]} rows={Object.entries(h.services || {})} />
          <div className="sub" style={{ marginTop: 8 }}>
            memory free {h.memory_mb?.MemAvailable ?? "-"} of {h.memory_mb?.MemTotal ?? "-"} MB | disk {h.disk_used_pct}% used |
            final bot's last log {h.final_last_log}
          </div>
        </section>

        <section className="panel wide">
          <h2>The final bot's log</h2>
          <div className="log">{(f.log || []).join("\n")}</div>
        </section>
      </div>
      <p className="sub" style={{ marginTop: 14 }}>Paper only - no orders, no keys. Every figure is from the VM's own files (dashboard_push.py).</p>
    </main>
  );
}

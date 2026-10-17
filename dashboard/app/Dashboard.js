"use client";
import { useEffect, useMemo, useState } from "react";
import { DailyChart, EquityChart } from "./charts";
import Refresh from "./Refresh";
import { ACCOUNT_NAMES, BOOKS, bookName, dayLabel, pct, priceFmt, tone, usd, when } from "../lib/fmt";

function useMounted() {
  const [m, setM] = useState(false);
  useEffect(() => setM(true), []);
  return m;
}

function useNow(ms = 5000) {
  const [now, setNow] = useState(null);
  useEffect(() => {
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

function ago(sec) {
  if (sec < 60) return `${Math.max(0, Math.round(sec))}s ago`;
  if (sec < 3600) return `${Math.round(sec / 60)} min ago`;
  return `${Math.round(sec / 3600)} h ago`;
}

// ------------------------------------------------------------------ top bar

function TopBar({ meta, want }) {
  const now = useNow();
  const age = now && meta?.generated ? now / 1000 - meta.generated : null;
  const stale = age !== null && age > 300;
  return (
    <header className="bar">
      <div className="bar-in">
        <div className="brand"><i>F</i>Forexbot <span className="pill">PAPER</span></div>
        <nav className="seg" aria-label="Account">
          {(meta?.accounts || []).map((a) => (
            <a key={a.id} href={`/?acct=${a.id}`} className={a.id === want ? "on" : ""}>
              {ACCOUNT_NAMES[a.id] || a.id}
              <small className={tone(a.equity - a.start)}>{pct(a.equity / a.start - 1, { dp: 1 })}</small>
            </a>
          ))}
        </nav>
        <div className="spacer" />
        <div className="live">
          <span className={`dot ${stale ? "stale" : ""}`} />
          <span>{age === null ? "Live" : stale ? `No update for ${ago(age)}` : `Live · updated ${ago(age)}`}</span>
          <span className="btc">· BTC {usd(meta?.btc, { dp: 0 })}</span>
        </div>
        <form method="post" action="/api/logout"><button className="btn" type="submit">Sign out</button></form>
      </div>
    </header>
  );
}

// ------------------------------------------------------------------ headline numbers

function Kpis({ a }) {
  const total = a.equity - a.start;
  const prevClose = a.equity - (a.today || 0);
  const st = a.stats || {};
  return (
    <div className="kpis">
      <div className="kpi hero">
        <div className="l">Equity (live)</div>
        <div className="v">{usd(a.equity)}</div>
        <div className="s">booked {usd(a.booked)} · open <span className={tone(a.unrealized)}>{usd(a.unrealized, { sign: true })}</span></div>
      </div>
      <div className="kpi">
        <div className="l">Today (UTC day)</div>
        <div className={`v ${tone(a.today)}`}>{usd(a.today, { sign: true })}</div>
        <div className={`s ${tone(a.today)}`}>{pct(prevClose ? a.today / prevClose : null)}</div>
      </div>
      <div className="kpi">
        <div className="l">Total since start ({usd(a.start, { dp: 0 })})</div>
        <div className={`v ${tone(total)}`}>{usd(total, { sign: true })}</div>
        <div className={`s ${tone(total)}`}>{pct(total / a.start)}</div>
      </div>
      <div className="kpi">
        <div className="l">Open P&amp;L</div>
        <div className={`v ${tone(a.unrealized)}`}>{usd(a.unrealized, { sign: true })}</div>
        <div className="s">{(a.open || []).length} open positions</div>
      </div>
      <div className="kpi">
        <div className="l">Down from peak</div>
        <div className={`v ${a.fall > 0.0001 ? "down" : ""}`}>{a.fall > 0.0001 ? pct(-a.fall) : "0.00%"}</div>
        <div className="s">peak {usd(a.peak)}</div>
      </div>
      <div className="kpi">
        <div className="l">Win rate</div>
        <div className="v">{st.win_rate === null || st.win_rate === undefined ? "–" : pct(st.win_rate, { dp: 0, sign: false })}</div>
        <div className="s">{st.wins || 0} won of {st.n || 0} closed</div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ P&L by strategy

function BookBars({ a }) {
  const rows = Object.keys(BOOKS).map((k) => {
    const b = a.books?.[k] || { booked: 0, open: 0 };
    return { k, booked: b.booked, open: b.open, total: b.booked + b.open };
  }).sort((x, y) => y.total - x.total);
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.total)), Math.abs(a.fees || 0));
  const bar = (v) => {
    const w = Math.min(50, (Math.abs(v) / max) * 50);
    return <i style={{ left: v >= 0 ? "50%" : `${50 - w}%`, width: `${w}%`, background: v >= 0 ? "var(--up)" : "var(--down)" }} />;
  };
  return (
    <section className="card">
      <div className="card-h"><div><h2>Profit &amp; loss by strategy</h2><div className="sub">closed + open, since the start</div></div></div>
      <div className="books">
        {rows.map((r) => (
          <div className="book" key={r.k} title={BOOKS[r.k].desc}>
            <div className="top">
              <div><span className="name">{BOOKS[r.k].name}</span> <span className="desc">{BOOKS[r.k].desc}</span></div>
              <span className={`num ${tone(r.total)}`}>{usd(r.total, { sign: true })}</span>
            </div>
            <div className="track"><span className="mid" />{bar(r.total)}</div>
            {r.booked || r.open ? <div className="split">closed {usd(r.booked, { sign: true })} · open {usd(r.open, { sign: true })}</div> : null}
          </div>
        ))}
        <div className="book">
          <div className="top"><div><span className="name">Trading fees</span></div><span className="num down">{usd(-(a.fees || 0), { sign: true })}</span></div>
          <div className="track"><span className="mid" />{bar(-(a.fees || 0))}</div>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ exposure

function Exposure({ a }) {
  const e = a.exposure || {};
  const g = (e.long || 0) + (e.short || 0);
  const longs = (a.open || []).filter((r) => r.side === "long").length;
  return (
    <section className="card">
      <div className="card-h"><div><h2>Exposure</h2><div className="sub">what the account holds, netted per coin</div></div></div>
      <div className="kv"><span>Long</span><span className="num up">{usd(e.long)}</span></div>
      <div className="kv"><span>Short</span><span className="num down">{usd(e.short)}</span></div>
      <div className="stack">
        <i style={{ width: `${g ? (e.long / g) * 100 : 50}%`, background: "var(--up)" }} />
        <i style={{ width: `${g ? (e.short / g) * 100 : 50}%`, background: "var(--down)" }} />
      </div>
      <div className="kv"><span>Leverage</span><span className="num">{e.lev ?? "–"}x of {e.cap}x allowed</span></div>
      <div className="meter"><i style={{ width: `${Math.min(100, ((e.lev || 0) / (e.cap || 1)) * 100)}%` }} /></div>
      <div style={{ height: 6 }} />
      <div className="kv"><span>Positions</span><span className="num">{longs} long · {(a.open || []).length - longs} short</span></div>
      <div className="kv"><span>Signals waiting</span><span className="num">news {a.pending?.news ?? 0} · crash buys {a.pending?.capit2 ?? 0}</span></div>
      <div className="kv"><span>News read</span><span className="num">{a.news?.seen ?? 0} · traded {a.news?.taken ?? 0}</span></div>
    </section>
  );
}

// ------------------------------------------------------------------ positions / history / news

function Chips({ books, value, set }) {
  return (
    <div className="chips">
      {["all", ...books].map((b) => (
        <button key={b} className={b === value ? "on" : ""} onClick={() => set(b)}>{b === "all" ? "All" : bookName(b)}</button>
      ))}
    </div>
  );
}

function Positions({ a, local }) {
  const [book, setBook] = useState("all");
  const all = a.open || [];
  const books = [...new Set(all.map((r) => r.book))];
  const rows = book === "all" ? all : all.filter((r) => r.book === book);
  const sum = rows.reduce((s, r) => s + (r.upnl || 0), 0);
  if (!all.length) return <div className="empty">No open positions.</div>;
  return (
    <>
      <Chips books={books} value={book} set={setBook} />
      <div className="summary">
        <span>Open P&amp;L <b className={tone(sum)}>{usd(sum, { sign: true })}</b></span>
        <span>Size <b>{usd(rows.reduce((s, r) => s + (r.size || 0), 0), { dp: 0 })}</b></span>
        <span><b>{rows.length}</b> positions</span>
      </div>
      <div className="scroll">
        <table>
          <thead><tr>
            <th>Symbol</th><th>Side</th><th className="r">Size</th><th className="r">Entry price</th>
            <th className="r">Mark price</th><th className="r">P&amp;L (ROE %)</th><th>Opened</th>
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.book}-${r.sym}-${i}`}>
                <td><div className="sym">{r.sym.replace(/USDT$/, "")}<span className="faint">/USDT</span></div>
                  <span className="tag" title={r.note}>{bookName(r.book)}</span></td>
                <td><span className={`side ${r.side}`}>{r.side === "long" ? "Long" : "Short"}</span></td>
                <td className="r">{usd(r.size)}</td>
                <td className="r">{priceFmt(r.entry)}</td>
                <td className="r">{priceFmt(r.mark)}</td>
                <td className={`r ${tone(r.upnl)}`}><div>{usd(r.upnl, { sign: true })}</div><div className="note">{pct(r.pct)}</div></td>
                <td><div>{r.since ? when(r.since, local) : "–"}</div><div className="note">{r.note}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function History({ a, local }) {
  const [book, setBook] = useState("all");
  const all = a.closed || [];
  const books = [...new Set(all.map((r) => r.book))];
  const rows = book === "all" ? all : all.filter((r) => r.book === book);
  const pn = rows.filter((r) => r.pnl !== null && r.pnl !== undefined);
  const won = pn.filter((r) => r.pnl > 0).length;
  const tot = pn.reduce((s, r) => s + r.pnl, 0);
  if (!all.length) return <div className="empty">No closed trades yet.</div>;
  return (
    <>
      <Chips books={books} value={book} set={setBook} />
      <div className="summary">
        <span><b>{pn.length}</b> trades</span>
        <span>won <b>{won}</b> ({pn.length ? Math.round((won / pn.length) * 100) : 0}%)</span>
        <span>total <b className={tone(tot)}>{usd(tot, { sign: true })}</b></span>
      </div>
      <div className="scroll">
        <table>
          <thead><tr>
            <th>Closed</th><th>Symbol</th><th>Side</th><th className="r">Entry</th><th className="r">Exit</th>
            <th className="r">Result</th><th className="r">P&amp;L</th><th>Why it closed</th>
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.ts}-${r.sym}-${i}`}>
                <td>{when(r.ts, local)}</td>
                <td><div className="sym">{(r.sym || "").replace(/USDT$/, "")}</div><span className="tag">{bookName(r.book)}</span></td>
                <td><span className={`side ${r.side}`}>{r.side === "long" ? "Long" : "Short"}</span></td>
                <td className="r">{priceFmt(r.entry)}</td>
                <td className="r">{priceFmt(r.exit)}</td>
                <td className={`r ${tone(r.pct)}`}>{pct(r.pct)}</td>
                <td className={`r ${tone(r.pnl)}`} title={r.approx ? "estimated from the trade's R multiple" : undefined}>
                  {r.approx ? "≈ " : ""}{usd(r.pnl, { sign: true })}</td>
                <td className="muted">{r.why}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function News({ a, local }) {
  const rows = a.news?.recent || [];
  if (!rows.length) return <div className="empty">No new Binance announcements since the bot started reading. It trades only "adds products" and "monitoring tag" notices.</div>;
  return (
    <div className="scroll">
      <table>
        <thead><tr><th>Time</th><th>Type</th><th>Coins</th><th>Headline</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{when(r.ts, local)}</td>
              <td><span className={`etype ${r.traded ? "traded" : ""}`}>{r.traded ? "traded · " : ""}{r.etype}</span></td>
              <td>{(r.coins || []).map((c) => c.replace(/USDT$/, "")).join(" ")}</td>
              <td className="headline">{r.headline}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Panel({ a, local }) {
  const [tab, setTab] = useState("pos");
  const tabs = [["pos", `Positions (${(a.open || []).length})`], ["hist", `Trade history (${a.stats?.n ?? 0})`],
    ["news", `News feed (${(a.news?.recent || []).length})`]];
  return (
    <section className="card">
      <div className="ptabs">
        {tabs.map(([k, l]) => <button key={k} className={k === tab ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === "pos" ? <Positions a={a} local={local} /> : tab === "hist" ? <History a={a} local={local} /> : <News a={a} local={local} />}
    </section>
  );
}

// ------------------------------------------------------------------ the page

export default function Dashboard({ meta, acct, want }) {
  const local = useMounted();
  const down = useMemo(() => Object.entries(meta?.health?.services || {})
    .filter(([, s]) => s.active !== "active").map(([n]) => n), [meta]);
  return (
    <>
      <Refresh />
      <TopBar meta={meta} want={want} />
      <main>
        {down.length ? <div className="alert">Not running on the VM: {down.join(", ")}</div> : null}
        {!acct ? (
          <div className="alert info">
            {want === "fresh" ? "The fresh $300 account has not reported yet - it appears within a minute or two of starting." :
              "This account has not reported yet."}
          </div>
        ) : (
          <>
            <Kpis a={acct} />
            <div className="row">
              <EquityChart curve={acct.curve} start={acct.start} />
              <BookBars a={acct} />
            </div>
            <div className="row">
              <section className="card">
                <div className="card-h"><div><h2>Daily profit &amp; loss</h2>
                  <div className="sub">per UTC day{acct.started ? `, since ${dayLabel(acct.started)}` : ""}</div></div></div>
                <DailyChart daily={acct.curve?.daily} />
              </section>
              <Exposure a={acct} />
            </div>
            <Panel a={acct} local={local} />
          </>
        )}
        <div className="foot">
          <span>Other paper books:</span>
          {(meta?.others || []).map((o) => (
            <span className="chip" key={o.name}>{o.name} <b className={tone(o.equity - o.start)}>{usd(o.equity)}</b>
              {" "}<span className={tone(o.equity - o.start)}>{pct(o.equity / o.start - 1, { dp: 1 })}</span></span>
          ))}
          <span className="spacer" />
          <span>Paper only: no real money, no orders. VM memory free {meta?.health?.memory_mb?.MemAvailable ?? "–"} MB.</span>
        </div>
      </main>
    </>
  );
}

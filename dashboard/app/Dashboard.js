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
          {meta?.crowd ? (
            <a href="/?acct=crowd" className={want === "crowd" ? "on" : ""}>
              {ACCOUNT_NAMES.crowd}
              <small className={tone(meta.crowd.equity - meta.crowd.start)}>{pct(meta.crowd.equity / meta.crowd.start - 1, { dp: 1 })}</small>
            </a>
          ) : null}
          {meta?.analyst ? (
            <a href="/?acct=analyst" className={want === "analyst" ? "on" : ""}>
              {ACCOUNT_NAMES.analyst}
              <small className={tone(meta.analyst.equity - meta.analyst.start)}>{pct(meta.analyst.equity / meta.analyst.start - 1, { dp: 1 })}</small>
            </a>
          ) : null}
          {meta?.mood ? (
            <a href="/?acct=mood" className={want === "mood" ? "on" : ""}>
              {ACCOUNT_NAMES.mood}<small>F&amp;G {meta.mood.market?.fear_greed ?? "–"}</small>
            </a>
          ) : null}
        </nav>
        <div className="spacer" />
        <div className="live">
          <span className={`dot ${stale ? "stale" : ""}`} />
          <span>{age === null ? "Live" : stale ? `No update for ${ago(age)}` : `Live · updated ${ago(age)}`}</span>
          <span className="btc">· BTC {usd(meta?.btc, { dp: 0 })}</span>
          {meta?.mood?.market?.fuel ? (
            <a className="fuel" href="/?acct=mood"
               title="Trend-book fuel: how many of the top coins are already running. The trend book earns after months with many runners. Tap for detail.">
              · Fuel <b>{meta.mood.market.fuel.state ?? "–"}</b>
            </a>
          ) : null}
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
        <div className="l">Equity: what you would have if everything closed now</div>
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

// ------------------------------------------------------------------ scorecard: live vs the backtest's normal range

const STATUS = {
  worse: ["Worse than expected", "bad"], below: ["Below typical", "warn"], ok: ["On track", "good"],
  above: ["Better than typical", "good"], idle: ["No trades yet (normal)", "idle"],
};

function Dial({ p, status }) {
  return (
    <div className="dial" title={`${Math.round(p)}th percentile of the backtest`}>
      <span className="zone z90" /><span className="zone z50" /><span className="mark50" />
      <i className={`pin ${STATUS[status]?.[1] || ""}`} style={{ left: `${Math.min(100, Math.max(0, p))}%` }} />
    </div>
  );
}

function ordinal(n) {
  const r = Math.round(n), s = ["th", "st", "nd", "rd"], v = r % 100;
  return r + (s[(v - 20) % 10] || s[v] || s[0]);
}

function Scorecard({ a }) {
  const sc = a.score;
  if (!sc?.ready) {
    return (
      <section className="card score">
        <div className="card-h"><div><h2>Scorecard: live vs backtest</h2>
          <div className="sub">Starts once the account is {sc?.min_days || 7} days old
            {sc?.days !== undefined ? ` - now ${sc.days < 1 ? `${Math.round(sc.days * 24)} hours` : `${sc.days.toFixed(1)} days`}` : ""}.
            Some strategies settle weekly, so a shorter stretch can not be compared fairly.</div></div></div>
      </section>
    );
  }
  const t = sc.total;
  const days = sc.days < 2 ? `${sc.days.toFixed(1)} days` : `${Math.round(sc.days)} days`;
  return (
    <section className="card score">
      <div className="card-h">
        <div><h2>Scorecard: live vs backtest</h2>
          <div className="sub">Each result placed among every {Math.round(sc.days)}-day stretch of the backtest ({sc.span}). 50th = as good as the backtest.</div></div>
        {sc.days < 30 ? <span className="pill warn-pill">early read - {days} in</span> : null}
      </div>
      <div className="score-total">
        <div>
          <div className="muted" style={{ fontSize: 12 }}>Whole account after {days}</div>
          <div className="big"><span className={tone(t.usd)}>{usd(t.usd, { sign: true })}</span>
            <span className={`small ${tone(t.ret)}`}> {pct(t.ret)}</span></div>
          <div className="muted" style={{ fontSize: 12 }}>backtest typical {pct(t.p25)} to {pct(t.p75)} · median {pct(t.p50)}</div>
        </div>
        <div className="score-dial">
          <Dial p={t.pctile} status={t.status} />
          <div className="dial-lab"><span>worst</span><span>{ordinal(t.pctile)} percentile</span><span>best</span></div>
        </div>
        <span className={`badge ${STATUS[t.status][1]}`}>{STATUS[t.status][0]}</span>
      </div>
      <div className="scroll">
        <table>
          <thead><tr><th>Strategy</th><th className="r">Live</th><th className="r">Backtest typical</th>
            <th style={{ minWidth: 170 }}>Where it sits</th><th>Status</th></tr></thead>
          <tbody>
            {sc.books.map((r) => (
              <tr key={r.book}>
                <td><div className="sym">{bookName(r.book)}</div><div className="note">{BOOKS[r.book]?.desc}</div></td>
                <td className={`r ${tone(r.usd)}`}>{usd(r.usd, { sign: true })}</td>
                <td className="r muted">{usd(r.p25, { sign: true })} to {usd(r.p75, { sign: true })}</td>
                <td><Dial p={r.pctile} status={r.status} /><div className="note">{r.status === "idle"
                  ? `idle in ${Math.round(r.idle_share * 100)}% of ${Math.round(sc.days)}-day stretches` : `${ordinal(r.pctile)} percentile`}</div></td>
                <td><span className={`badge ${STATUS[r.status][1]}`}>{STATUS[r.status][0]}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note" style={{ marginTop: 10, whiteSpace: "normal" }}>
        Below the 5th percentile for weeks means a strategy is not doing what its backtest did. In the first month the
        percentiles swing a lot - read them as an early warning, not a verdict. The backtest itself is optimistic.
      </p>
    </section>
  );
}

// ------------------------------------------------------------------ P&L by strategy

function BookBars({ a }) {
  const rows = Object.keys(BOOKS).filter((k) => k !== "crowd" || a.books?.crowd).map((k) => {
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
        <span title="The value of the coins these positions control, most of it with leverage - not money in the account">
          Position size <b>{usd(rows.reduce((s, r) => s + (r.size || 0), 0), { dp: 0 })}</b> (with leverage, not cash)</span>
        <span><b>{rows.length}</b> positions</span>
        {book === "all" ? <span>If all closed now: <b>≈ {usd(a.equity - rows.reduce((s, r) => s + (r.size || 0), 0) * 0.0006)}</b></span> : null}
      </div>
      <div className="scroll">
        <table>
          <thead><tr>
            <th>Symbol</th><th>Side</th><th className="r" title="value of the position, with leverage">Size</th><th className="r">Entry price</th>
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

// ------------------------------------------------------------------ the crowd-squeeze paper book (news/crowd_paper.py)

const SLEEVE = { mon: "Monday", thu: "Thursday" };

function CrowdBook({ c }) {
  if (!c) return null;
  const total = c.equity - c.start;
  const sc = c.score || {};
  const legs = c.legs || [];
  const sum = legs.reduce((s, r) => s + (r.upnl || 0), 0);
  return (
    <>
      <section className="card score">
        <div className="card-h">
          <div><h2>Crowd-squeeze book · paper, its own {usd(c.start, { dp: 0 })}</h2>
            <div className="sub">Long the quarter of coins the crowd is most short, short the most-long quarter, held a week
              (half from Monday, half from Thursday). Backtest 2022-26: +37% to +48% a year, not proven. Not part of the
              bot's account.</div></div>
          {sc.ready ? <span className={`badge ${STATUS[sc.status][1]}`}>{STATUS[sc.status][0]}</span>
            : <span className="pill warn-pill">{legs.length || (c.weeks || []).length ? `scored from week ${sc.min_weeks || 4}`
              : `first trades ${dayLabel(c.first)} 00:00 UTC`}</span>}
        </div>
        <div className="score-total">
          <div>
            <div className="muted" style={{ fontSize: 12 }}>Equity now (open legs at live prices)</div>
            <div className="big">{usd(c.equity)} <span className={`small ${tone(total)}`}>{pct(total / c.start)}</span></div>
            <div className="muted" style={{ fontSize: 12 }}>{(c.sleeves || []).map((s) =>
              `${SLEEVE[s.id] || s.id} ${usd(s.equity)} · ${s.weeks} weeks closed · funding ${usd(s.funding, { sign: true })}`).join("  |  ")}</div>
          </div>
          {sc.ready ? (
            <div className="score-dial">
              <Dial p={sc.pctile} status={sc.status} />
              <div className="dial-lab"><span>worst</span><span>{ordinal(sc.pctile)} percentile of {Math.round(sc.weeks)}-week stretches</span><span>best</span></div>
            </div>
          ) : (
            <div className="muted" style={{ fontSize: 12, maxWidth: 420 }}>Checkpoint 25 Jan 2027: stopped if under −7.8%.
              Verdict 9 Apr 2027, with the bot's own: dead under −6.6%, held up at +16.8% or more (the backtest's 10th
              percentile and median). A month swings −6% to +11% in the backtest.</div>
          )}
        </div>
        {legs.length ? (
          <>
            <div className="summary">
              <span>Open P&amp;L <b className={tone(sum)}>{usd(sum, { sign: true })}</b></span>
              <span><b>{legs.filter((r) => r.side === "long").length}</b> long · <b>{legs.filter((r) => r.side === "short").length}</b> short</span>
            </div>
            <div className="scroll">
              <table>
                <thead><tr><th>Symbol</th><th>Side</th><th className="r">Size</th><th className="r">Entry</th>
                  <th className="r">Mark</th><th className="r">P&amp;L</th></tr></thead>
                <tbody>
                  {legs.map((r, i) => (
                    <tr key={`${r.sleeve}-${r.sym}-${i}`}>
                      <td><div className="sym">{r.sym.replace(/USDT$/, "")}<span className="faint">/USDT</span></div>
                        <span className="tag">{SLEEVE[r.sleeve] || r.sleeve}</span></td>
                      <td><span className={`side ${r.side}`}>{r.side === "long" ? "Long" : "Short"}</span></td>
                      <td className="r">{usd(r.size)}</td>
                      <td className="r">{priceFmt(r.entry)}</td>
                      <td className="r">{priceFmt(r.mark)}</td>
                      <td className={`r ${tone(r.upnl)}`}><div>{usd(r.upnl, { sign: true })}</div><div className="note">{pct(r.pct)}</div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : <div className="empty">No positions yet. The Monday half opens {dayLabel(c.first)} at 00:00 UTC, the Thursday half three days later.</div>}
      </section>
      <div className="row">
        <EquityChart curve={c.curve} start={c.start} title="Crowd book equity" sub="daily marks, and now at live prices" />
        <section className="card">
          <div className="card-h"><div><h2>Closed weeks</h2><div className="sub">each half's week, after funding and fees</div></div></div>
          {(c.weeks || []).length ? (
            <div className="scroll">
              <table>
                <thead><tr><th>Week</th><th>Half</th><th className="r">Result</th><th className="r">P&amp;L</th></tr></thead>
                <tbody>
                  {c.weeks.map((w, i) => (
                    <tr key={i}><td>{dayLabel(w.opened)} → {dayLabel(w.closed)}</td><td>{SLEEVE[w.sleeve] || w.sleeve}</td>
                      <td className={`r ${tone(w.net)}`}>{pct(w.net)}</td><td className={`r ${tone(w.usd)}`}>{usd(w.usd, { sign: true })}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <div className="empty">No week closed yet.</div>}
        </section>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ market mood (news/mood_now.py, hourly)

const FLAG = { "SQUEEZE WATCH": ["Squeeze watch", "warn"], "crowd long": ["Crowd long", "idle"] };

function Mood({ m }) {
  const [all, setAll] = useState(true);
  if (!m) return null;
  const k = m.market || {};
  const coins = m.coins || [];
  const rows = all ? coins : coins.filter((r) => r.flag);
  const num = (v, dp) => (v === null || v === undefined ? "–" : (+v).toFixed(dp));
  return (
    <section className="card">
      <div className="card-h">
        <div><h2>Market mood</h2>
          <div className="sub">Binance crowd positioning on the top {coins.length} coins · updated {m.t} · information, not a trade signal</div></div>
        <div className="tabs">
          <button className={!all ? "on" : ""} onClick={() => setAll(false)}>Flagged</button>
          <button className={all ? "on" : ""} onClick={() => setAll(true)}>All {coins.length}</button>
        </div>
      </div>
      <div className="summary">
        <span>Fear &amp; Greed <b>{k.fear_greed ?? "–"}</b> {k.fear_greed_txt}</span>
        <span>Median coin: <b>{pct(k.median_long_share, { dp: 0, sign: false })}</b> of accounts long</span>
        <span><b>{pct(k.share_neg_funding, { dp: 0, sign: false })}</b> of coins pay shorts</span>
        <span>BTC crowd long/short <b>{num(k.btc_crowd, 2)}</b></span>
        {k.fuel ? (
          <span title="The machine's profit comes in a few explosive alt months, and the trend book earns after months when many coins were already running. Information, not a signal.">
            Trend-book fuel <b>{k.fuel.state ?? "–"}</b>: {pct(k.fuel.runners, { dp: 0, sign: false })} of coins up over 20% in 30 days
            (percentile {num(k.fuel.runners_pct, 0)}), median coin {pct(k.fuel.med, { dp: 0 })}
          </span>
        ) : null}
      </div>
      <div className="scroll">
        <table>
          <thead><tr><th>Coin</th><th className="r">Accounts long</th><th className="r">Crowd rank</th>
            <th className="r">Funding a year</th><th className="r">Buy / sell flow</th><th className="r">Open interest 7d</th><th>Flag</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.sym}>
                <td><div className="sym">{r.sym.replace(/USDT$/, "")}</div></td>
                <td className="r">{pct(r.long_share, { dp: 0, sign: false })}</td>
                <td className="r">{r.crowd_pct === null || r.crowd_pct === undefined ? "–" : Math.round(r.crowd_pct * 100)}</td>
                <td className="r">{r.fund_yr === null || r.fund_yr === undefined ? "–" : `${num(r.fund_yr, 1).replace("-", "−")}%`}</td>
                <td className="r">{num(r.taker, 2)}</td>
                <td className={`r ${tone(r.oi7)}`}>{pct(r.oi7, { dp: 0 })}</td>
                <td>{FLAG[r.flag] ? <span className={`badge ${FLAG[r.flag][1]}`}>{FLAG[r.flag][0]}</span> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note" style={{ marginTop: 10, whiteSpace: "normal" }}>
        Crowd rank 0 = the coin the crowd is most short, 100 = most long. Squeeze watch is the most-short quarter - the long
        side of the crowd-squeeze book above. Funding: positive = longs pay shorts. Buy / sell flow over 1 = more aggressive
        buying in the last 24h. Tested on 2022-26: crowd positioning is a lead; buy / sell flow, open interest, top traders,
        Bluesky chatter and news tone predicted nothing.
      </p>
    </section>
  );
}

// ------------------------------------------------------------------ the analyst desk (analyst.py, hourly)

const METHOD = { SR: "Support / resistance", FIB: "Fibonacci", SMC: "Liquidity sweep" };
const AN_VERDICT = { "NOT ENOUGH CALLS": ["Too early to judge", "warn"], "NO EDGE PROVEN": ["No edge proven", "idle"], EDGE: ["Beats chance", "good"] };
const RESULT = { WIN: ["Target hit", "good"], LOSS: ["Stopped out", "bad"], EXPIRED: ["Timed out", "idle"] };
const sym0 = (s) => (s || "").replace(/USDT$/, "");

// every line a chart reader would draw for one symbol, highest price first, each with its distance from the live price
function ladderRows(s, calls) {
  const rows = [];
  (s.resistance || []).slice(0, 2).forEach((x) => rows.push({ k: "res", p: x.price, label: x.touches >= 3 ? "Resistance · strong" : "Resistance", note: `${x.touches} touches` }));
  (s.support || []).slice(0, 2).forEach((x) => rows.push({ k: "sup", p: x.price, label: x.touches >= 3 ? "Support · strong" : "Support", note: `${x.touches} touches` }));
  if (s.fib?.levels) {
    ["0.5", "0.618", "0.786"].forEach((r) => s.fib.levels[r] !== undefined &&
      rows.push({ k: "fib", p: s.fib.levels[r], label: `Fibonacci ${(+r * 100).toFixed(1).replace(".0", "")}%`, note: `${s.fib.trend} swing` }));
  }
  (s.gaps || []).slice(0, 1).forEach((g) => rows.push({ k: "gap", p: (g.lo + g.hi) / 2, label: g.side === "bull" ? "Unfilled gap · bullish" : "Unfilled gap · bearish", note: `${priceFmt(g.lo)} – ${priceFmt(g.hi)}` }));
  if (s.typical) {
    rows.push({ k: "typ", p: s.typical[1], label: "Typical day, high end", note: "1 sd of recent days" });
    rows.push({ k: "typ", p: s.typical[0], label: "Typical day, low end", note: "1 sd of recent days" });
  }
  (calls || []).forEach((c) => {
    rows.push({ k: "tgt", p: c.target, label: `Target · ${c.side} call #${c.id}`, note: METHOD[c.method] });
    rows.push({ k: "stp", p: c.stop, label: `Stop · ${c.side} call #${c.id}`, note: METHOD[c.method] });
  });
  rows.push({ k: "now", p: s.price, label: "Price now", note: "live" });
  return rows.sort((x, y) => y.p - x.p);
}

// the same calls, the whole account on each one at 10x / 20x / 30x: from the live record, and from the same rules replayed over history
function WhatIf({ w, n }) {
  const rep = w?.replay;
  const [src, setSrc] = useState(rep ? "replay" : "live");
  if (!w) return null;
  const cells = src === "replay" ? rep?.grid?.all : w.live;
  const at = (c, l) => (cells || []).find((x) => x.capital === c && x.lev === l);
  const caps = [20, 50, 100, 300], levs = [10, 20, 30];
  const live = src === "live";
  const any = (cells || []).some((x) => x.taken > 0);
  const mult = (v) => (v === null || v === undefined ? "–" : v < 0.005 ? "0×" : `${v.toFixed(2)}×`);
  return (
    <section className="card" style={{ marginBottom: 14 }}>
      <div className="card-h">
        <div><h2>What if the whole account went on every call?</h2>
          <div className="sub">$20 / $50 / $100 / $300 at 10× / 20× / 30×, one position at a time, stop and target as logged. Each trade costs 0.12% × leverage of the
            account in fees, and the exchange closes it if price moves about 1 ÷ leverage against you.</div></div>
        <div className="tabs">
          {rep ? <button className={src === "replay" ? "on" : ""} onClick={() => setSrc("replay")}>History replay</button> : null}
          <button className={src === "live" ? "on" : ""} onClick={() => setSrc("live")}>Live record</button>
        </div>
      </div>
      {live && !any ? <div className="empty">No call has resolved yet, so there is nothing to replay at leverage. {rep ? "The History replay tab shows the same rules over past years." : ""}</div> : (
        <div className="scroll">
          <table>
            <thead><tr><th>Start with</th>{levs.map((l) => <th key={l} className="r">{l}× leverage</th>)}</tr></thead>
            <tbody>
              {caps.map((c) => (
                <tr key={c}>
                  <td><div className="sym">{usd(c, { dp: 0 })}</div></td>
                  {levs.map((l) => {
                    const x = at(c, l);
                    if (!x) return <td key={l} className="r">–</td>;
                    return (
                      <td key={l} className={`r ${tone(x.ret)}`}>
                        <div>{x.ruined ? "wiped out" : usd(x.equity)}</div>
                        <div className="note">{x.ruined ? `ended ${usd(x.equity)}` : pct(x.ret, { dp: 0 })} · {x.taken} trades · {x.liquidated} liquidated</div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="note" style={{ marginTop: 10, whiteSpace: "normal" }}>
        {live ? `Live record: ${n || 0} resolved calls so far; calls made while an earlier one is still open are left out until it ends. ` :
          `History replay: the desk's three rules, unchanged, over ${rep.years} years of hourly candles (${rep.span?.[0]} to ${rep.span?.[1]}), ${rep.calls} calls, ${rep.taken} taken one at a time. A bar that touches both stop and target counts as a loss. Nothing was tuned; it is a replay, not a forecast. `}
        Capital only scales the dollars - $20 and $300 make the same percentage; the $5 minimum order is why a wiped-out account stops trading.
      </p>
      {!live && rep?.boot?.length ? (
        <>
          <div className="card-h" style={{ marginTop: 14 }}><div><h3 style={{ fontSize: 13, margin: 0 }}>A year of these calls, drawn 20,000 ways</h3>
            <div className="sub">the replay's calls resampled in random order, {rep.per_year} a year; start = 1×</div></div></div>
          <div className="scroll">
            <table>
              <thead><tr><th>Leverage</th><th className="r">Typical year</th><th className="r">Bad year (1 in 10)</th><th className="r">Good year (1 in 10)</th>
                <th className="r">Ends under start</th><th className="r">Loses 90% on the way</th></tr></thead>
              <tbody>
                {rep.boot.map((b) => (
                  <tr key={b.lev}>
                    <td><div className="sym">{b.lev}×</div></td>
                    <td className={`r ${tone(b.median - 1)}`}>{mult(b.median)}</td>
                    <td className="r">{mult(b.p10)}</td><td className="r">{mult(b.p90)}</td>
                    <td className="r">{pct(b.below_start, { dp: 0, sign: false })}</td>
                    <td className={`r ${b.ruin > 0.5 ? "down" : ""}`}>{pct(b.ruin, { dp: 0, sign: false })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rep.paper_book ? (
            <p className="note" style={{ marginTop: 10, whiteSpace: "normal" }}>
              The desk's own book (its 0.5%-risk sizing, not all-in) over the same calls: {usd(300, { dp: 0 })} would have ended at <b className={tone(rep.paper_book.final - 300)}>{usd(rep.paper_book.final)}</b>,
              with a deepest fall of {pct(rep.paper_book.maxdd, { dp: 0, sign: false })} and about {pct(rep.paper_book.weekly, { dp: 1 })} a week on average.
              {rep.paper_book.final < 300 ? " The live book above is measuring whether the same drift shows up forward." : ""}
            </p>
          ) : null}
          {rep.stats?.all?.hit !== undefined ? (
            <p className="note" style={{ marginTop: 10, whiteSpace: "normal" }}>
              In the replay the rules were right {pct(rep.stats.all.hit, { dp: 1, sign: false })} of the time (target first); a random entry with the same stop and target was
              right {pct(rep.stats.all.baseline, { dp: 1, sign: false })}; covering the fees needs {pct(rep.stats.all.breakeven, { dp: 1, sign: false })}.
              Average per call {rep.stats.all.avg_r > 0 ? "+" : "−"}{Math.abs(rep.stats.all.avg_r).toFixed(2)}R after fees. Leverage multiplies that average, it does not change its sign.
              {rep.check_1m?.s1m ? ` Scoring is not what makes them lose: the last ${rep.check_1m.days} days' ${rep.check_1m.calls} calls re-scored on 1-minute candles were right ${pct(rep.check_1m.s1m.hit, { dp: 1, sign: false })} of the time (${pct(rep.check_1m.s1h.hit, { dp: 1, sign: false })} on hourly bars).` : ""}
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function AnalystDesk({ a }) {
  const local = useMounted();
  const syms = Object.keys(a.symbols || {});
  const [pick, setPick] = useState(null);
  const sel = a.symbols?.[pick] ? pick : syms[0];
  const s = a.stats || {};
  const total = a.equity - a.start;
  const open = a.open || [];
  const selCalls = open.filter((c) => c.symbol === sel);
  const verdict = AN_VERDICT[s.verdict] || (s.resolved ? AN_VERDICT["NOT ENOUGH CALLS"] : ["No calls resolved yet", "warn"]);
  const cur = sel ? a.symbols[sel] : null;
  const nr = cur?.resistance?.[0], ns = cur?.support?.[0];
  return (
    <>
      <section className="card score">
        <div className="card-h">
          <div><h2>Analyst desk · paper, its own {usd(a.start, { dp: 0 })}</h2>
            <div className="sub">Three fixed chart rules (support / resistance bounce, Fibonacci pullback, liquidity sweep) read 7 markets every hour.
              Each call is written down BEFORE it plays out - entry, stop, target and the odds a random entry would have - then scored on
              1-minute candles. Not part of either account. The repo's own tests expect no edge after fees: this measures it.</div></div>
          <span className={`badge ${verdict[1]}`}>{verdict[0]}</span>
        </div>
        <div className="score-total">
          <div>
            <div className="muted" style={{ fontSize: 12 }}>Paper book now (open calls at live prices)</div>
            <div className="big">{usd(a.equity)} <span className={`small ${tone(total)}`}>{pct(total / a.start)}</span></div>
            <div className="muted" style={{ fontSize: 12 }}>booked {usd(a.booked)} · each call risks {a.cfg?.risk_pct}% of the book · fee 0.12% a round trip</div>
          </div>
          <div className="muted" style={{ fontSize: 12, maxWidth: 440 }}>
            {s.resolved ? `${s.resolved} of ${s.min_resolved} resolved calls needed for a verdict. ` : `No call has resolved yet; a verdict needs ${s.min_resolved}. `}
            Review at 100 resolved calls or 31 Jan 2027: retired if the average result after fees is not above zero or the hit rate is no better than chance.
          </div>
        </div>
        <div className="summary">
          <span>Calls <b>{s.calls ?? 0}</b> · open <b>{s.open ?? 0}</b> · resolved <b>{s.resolved ?? 0}</b> (<span className="up">{s.wins ?? 0} target</span> · <span className="down">{s.losses ?? 0} stopped</span> · {s.expired ?? 0} timed out)</span>
          {s.resolved ? (
            <>
              <span>Right (target first) <b>{pct(s.hit, { dp: 0, sign: false })}</b></span>
              <span title="The share of calls that would have hit target first if the same stop, target and hours had been entered at a random moment on the same chart.">Random entry <b>{pct(s.baseline, { dp: 0, sign: false })}</b></span>
              <span title="The hit rate needed to cover the fees at these stop / target sizes.">Break-even <b>{pct(s.breakeven, { dp: 0, sign: false })}</b></span>
              <span>Average per call <b className={tone(s.avg_r)}>{s.avg_r > 0 ? "+" : s.avg_r < 0 ? "−" : ""}{Math.abs(s.avg_r).toFixed(2)}R</b></span>
              <span>Booked P&amp;L <b className={tone(s.pnl)}>{usd(s.pnl, { sign: true })}</b></span>
            </>
          ) : null}
        </div>
      </section>

      <div className="row">
        <section className="card">
          <div className="card-h"><div><h2>Levels and expected movement</h2>
            <div className="sub">levels from closed candles · distance from the live price · updated {a.levels_t || "–"} UTC · tap a market</div></div></div>
          <div className="scroll">
            <table>
              <thead><tr><th>Market</th><th className="r">Price</th><th className="r">Next resistance</th><th className="r">Next support</th>
                <th className="r">Typical day</th><th>Prediction</th></tr></thead>
              <tbody>
                {syms.map((k) => {
                  const v = a.symbols[k], r = v.resistance?.[0], sp = v.support?.[0];
                  const mine = open.filter((c) => c.symbol === k);
                  return (
                    <tr key={k} className={k === sel ? "pick" : ""} onClick={() => setPick(k)} style={{ cursor: "pointer" }}>
                      <td><div className="sym">{sym0(k)}<span className="faint">/USDT</span></div></td>
                      <td className="r">{priceFmt(v.price)}</td>
                      <td className="r">{r ? <><div className="up">{pct(r.dist)}</div><div className="note">{priceFmt(r.price)} · {r.touches}×</div></> : "–"}</td>
                      <td className="r">{sp ? <><div className="down">{pct(sp.dist)}</div><div className="note">{priceFmt(sp.price)} · {sp.touches}×</div></> : "–"}</td>
                      <td className="r">±{pct(v.typical_move_pct, { dp: 1, sign: false })}</td>
                      <td>{mine.length ? mine.map((c) => <span key={c.id} className={`side ${c.side}`} style={{ marginRight: 4 }}>{c.side === "long" ? "Long" : "Short"} · {c.method}</span>)
                        : <span className="faint">waiting</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="note" style={{ marginTop: 10, whiteSpace: "normal" }}>
            Typical day = one standard deviation of the last 14 daily moves: the size of an ordinary day, not a forecast of its direction.
            "Waiting" means none of the three rules is triggered right now - which is most of the time.
          </p>
        </section>
        <section className="card">
          <div className="card-h"><div><h2>{cur ? `${sym0(sel)} ladder` : "Ladder"}</h2>
            <div className="sub">every line the desk draws, with its distance from the price</div></div></div>
          {cur ? (
            <>
              <div className="ladder">
                {ladderRows(cur, selCalls).map((r, i) => (
                  <div key={i} className={`lad lad-${r.k}`}>
                    <span className="lab">{r.label}<span className="note"> {r.note}</span></span>
                    <span className="px">{priceFmt(r.p)}</span>
                    <span className={`d ${r.k === "now" ? "" : tone(r.p - cur.price)}`}>{r.k === "now" ? "" : pct(r.p / cur.price - 1)}</span>
                  </div>
                ))}
              </div>
              <p className="note" style={{ marginTop: 10, whiteSpace: "normal" }}>
                {nr && ns ? `Room above: ${pct(nr.dist)} to the next resistance. Room below: ${pct(ns.dist)} to the next support. ` : ""}
                {cur.fib ? `Price has retraced ${pct(cur.fib.retraced, { dp: 0, sign: false })} of the ${cur.fib.trend} swing ${priceFmt(cur.fib.lo)} – ${priceFmt(cur.fib.hi)}. ` : ""}
                {selCalls.length ? "A rule has fired: its prediction is in the table below." : "No rule has fired on this market, so the desk makes no prediction."}
              </p>
            </>
          ) : <div className="empty">No levels yet - the desk runs hourly on the VM.</div>}
        </section>
      </div>

      <section className="card" style={{ marginBottom: 14 }}>
        <div className="card-h"><div><h2>Open predictions</h2>
          <div className="sub">written down before the outcome · marked at live prices · "random" = the odds the same trade has when entered at a random moment</div></div></div>
        {open.length ? (
          <div className="scroll">
            <table>
              <thead><tr><th>Market</th><th>Rule</th><th className="r">Entry</th><th className="r">Target</th><th className="r">Stop</th><th className="r">Now</th>
                <th className="r">Result so far</th><th className="r">Odds</th><th className="r">Time left</th></tr></thead>
              <tbody>
                {open.map((c) => (
                  <tr key={c.id}>
                    <td><div className="sym">{sym0(c.symbol)}<span className="faint">/USDT</span></div>
                      <span className={`side ${c.side}`}>{c.side === "long" ? "Long" : "Short"}</span> <span className="note">#{c.id} · {when(c.made, local)}</span></td>
                    <td><div>{METHOD[c.method] || c.method}</div><div className="note" style={{ whiteSpace: "normal" }}>{c.why}</div></td>
                    <td className="r">{priceFmt(c.entry)}</td>
                    <td className="r"><div>{priceFmt(c.target)}</div><div className="note">{pct(c.target / c.entry - 1)}</div></td>
                    <td className="r"><div>{priceFmt(c.stop)}</div><div className="note">{pct(c.stop / c.entry - 1)}</div></td>
                    <td className="r">{priceFmt(c.mark)}</td>
                    <td className={`r ${tone(c.r)}`}>{c.booked ? <div>{usd(c.upnl, { sign: true })}</div> : <div className="note">not booked</div>}
                      <div className="note">{c.r === null || c.r === undefined ? "–" : `${c.r > 0 ? "+" : c.r < 0 ? "−" : ""}${Math.abs(c.r).toFixed(2)}R`}</div></td>
                    <td className="r"><div>random {pct(c.base_p, { dp: 0, sign: false })}</div><div className="note">needs {pct(c.be_p, { dp: 0, sign: false })} · pays {c.rr?.toFixed(1)}R</div></td>
                    <td className="r">{c.left_h > 0 ? `${c.left_h.toFixed(0)} h` : "closing"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="empty">No open prediction. The rules are strict, so most hours nothing fires.</div>}
      </section>

      <WhatIf w={a.what_if} n={s.resolved} />

      <div className="row">
        <EquityChart curve={a.curve} start={a.start} title="Analyst book equity" sub="daily marks, and now at live prices" />
        <section className="card">
          <div className="card-h"><div><h2>Record by rule</h2><div className="sub">resolved calls, against random entries</div></div></div>
          {Object.keys(s.by_method || {}).length ? (
            <div className="scroll">
              <table>
                <thead><tr><th>Rule</th><th className="r">Calls</th><th className="r">Right</th><th className="r">Random</th><th className="r">Avg</th><th className="r">P&amp;L</th></tr></thead>
                <tbody>
                  {Object.entries(s.by_method).map(([m, g]) => (
                    <tr key={m}><td>{METHOD[m] || m}</td><td className="r">{g.n}</td>
                      <td className="r">{pct(g.wins / g.n, { dp: 0, sign: false })}</td><td className="r">{pct(g.baseline, { dp: 0, sign: false })}</td>
                      <td className={`r ${tone(g.avg_r)}`}>{g.avg_r > 0 ? "+" : g.avg_r < 0 ? "−" : ""}{Math.abs(g.avg_r).toFixed(2)}R</td>
                      <td className={`r ${tone(g.pnl)}`}>{usd(g.pnl, { sign: true })}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <div className="empty">No call has resolved yet.</div>}
        </section>
      </div>

      <section className="card" style={{ marginBottom: 14 }}>
        <div className="card-h"><div><h2>Recent calls</h2><div className="sub">scored on public 1-minute candles: a bar touching both stop and target counts as stopped</div></div></div>
        {(a.recent || []).length ? (
          <div className="scroll">
            <table>
              <thead><tr><th>Market</th><th>Rule</th><th>Result</th><th className="r">Entry → exit</th><th className="r">After fees</th><th className="r">Book P&amp;L</th><th className="r">Random</th></tr></thead>
              <tbody>
                {a.recent.map((c) => (
                  <tr key={c.id}>
                    <td><div className="sym">{sym0(c.symbol)}<span className="faint">/USDT</span></div>
                      <span className={`side ${c.side}`}>{c.side === "long" ? "Long" : "Short"}</span> <span className="note">#{c.id}</span></td>
                    <td>{METHOD[c.method] || c.method}</td>
                    <td><span className={`badge ${RESULT[c.status]?.[1] || "idle"}`}>{RESULT[c.status]?.[0] || c.status}</span>
                      <div className="note">{when(c.closed, local)}</div></td>
                    <td className="r">{priceFmt(c.entry)} → {priceFmt(c.exit)}</td>
                    <td className={`r ${tone(c.r)}`}>{c.r > 0 ? "+" : c.r < 0 ? "−" : ""}{Math.abs(c.r).toFixed(2)}R</td>
                    <td className={`r ${tone(c.usd)}`}>{c.booked ? usd(c.usd, { sign: true }) : <span className="note">not booked</span>}</td>
                    <td className="r">{pct(c.base_p, { dp: 0, sign: false })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="empty">No call has resolved yet.</div>}
      </section>
    </>
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
        {want === "crowd" ? (meta?.crowd ? <CrowdBook c={meta.crowd} />
          : <div className="alert info">The crowd-squeeze book has not reported yet - it runs hourly on the VM.</div>)
        : want === "analyst" ? (meta?.analyst ? <AnalystDesk a={meta.analyst} />
          : <div className="alert info">The analyst desk has not reported yet - it runs hourly on the VM.</div>)
        : want === "mood" ? (meta?.mood ? <Mood m={meta.mood} />
          : <div className="alert info">No market-mood snapshot yet - it is written hourly on the VM.</div>)
        : !acct ? (
          <div className="alert info">
            {want === "fresh" ? "The fresh $300 account has not reported yet - it appears within a minute or two of starting." :
              "This account has not reported yet."}
          </div>
        ) : (
          <>
            <Kpis a={acct} />
            <Scorecard a={acct} />
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

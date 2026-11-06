"use client";
import { useEffect, useMemo, useState } from "react";
import { DailyChart, EquityChart } from "./charts";
import Refresh from "./Refresh";
import { ACCOUNT_NAMES, BOOKS, bookName, dayLabel, pct, priceFmt, tone, usd, when } from "../lib/fmt";
import { buildSizing, fmtQty, levelsFor, parseNum, plainSetup, recommendedLeverage, todaysPick } from "../lib/sizepanel.mjs";

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
  // The same coin is often held in several books at once; its rows must be read together (on 2026-11-06 two micro-caps, AKE and AIN, were about three quarters of one account's day).
  const byCoin = {};
  all.forEach((r) => {
    const c = byCoin[r.sym] || (byCoin[r.sym] = { sym: r.sym, upnl: 0, books: [] });
    c.upnl += r.upnl || 0;
    if (!c.books.includes(r.book)) c.books.push(r.book);
  });
  const coins = Object.values(byCoin);
  const losers = coins.filter((c) => c.upnl < 0).sort((a, b) => a.upnl - b.upnl).slice(0, 3);
  const gainers = coins.filter((c) => c.upnl > 0).sort((a, b) => b.upnl - a.upnl).slice(0, 2);
  const multi = coins.filter((c) => c.books.length >= 3);
  const coinTxt = (c) => `${c.sym.replace(/USDT$/, "")} ${usd(c.upnl, { sign: true })} (${c.books.map(bookName).join(", ")})`;
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
      {book === "all" && (losers.length || gainers.length) ? (
        <p className="note" style={{ margin: "0 0 10px", whiteSpace: "normal" }}>
          Open P&amp;L by coin, all books added: <b className="down">{losers.map(coinTxt).join(" · ") || "no losers"}</b>
          {gainers.length ? <> · best <b className="up">{gainers.map(coinTxt).join(" · ")}</b></> : null}
          {multi.length ? <> · held in 3 or more books at once: <b>{multi.map((c) => `${c.sym.replace(/USDT$/, "")} (${c.books.length})`).join(", ")}</b></> : null}
        </p>
      ) : null}
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
                <td className="r"><div>{priceFmt(r.entry)}</div>{r.daily ? <div className="note" title="This book is booked daily: each day's P&L is that day's move from the day's mark.">day mark</div> : null}</td>
                <td className="r">{priceFmt(r.mark)}</td>
                <td className={`r ${tone(r.upnl)}`}><div>{usd(r.upnl, { sign: true })}</div><div className="note">{pct(r.pct)}{r.daily ? " today" : ""}</div></td>
                <td><div>{r.since ? when(r.since, local) : "–"}</div>
                  <div className="note">{r.daily && r.open_px
                    ? `opened at ${priceFmt(r.open_px)} · price now ${pct(r.chg_open)}`
                    : r.note}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {all.some((r) => r.daily) ? (
        <p className="note" style={{ marginTop: 10, whiteSpace: "normal" }}>
          Rows marked <b>day mark</b> (market-neutral, carry, bear basket) are booked once a day: the account takes each day's move on that day's exposure and
          starts the next day from the new mark. Their P&amp;L is therefore <b>today's</b>, and it is what adds up to the open P&amp;L above. The price in the last
          column is where the basket was opened, and the move since is the coin's price change, not this position's profit.
        </p>
      ) : null}
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

const SIZE_BADGE = { sweet: ["Sweet-spot size", "good"], maybe: ["Only if the wick runs long", "warn"], small: ["Small stop", "idle"], mid: ["Middle size", "idle"], scalp: ["Scalp-sized", "bad"] };
const rTxt = (x) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(2)}R`;

function oddsLine(h) {
  if (!h || !h.n) return "no resolved calls of this size yet";
  const p = (x) => pct(x, { dp: 0, sign: false });
  return `${p(h.hit)} hit (${h.wins} of ${h.n} calls, which are only ${h.bets} independent bets, so the likely range is ${p(h.lo)} to ${p(h.hi)}) · average ${rTxt(h.mean_r)} a call, ${rTxt(h.mean_r_bet)} a bet, after fees`;
}

const SIZE_KEY = "sizepanel.v2";
const SIZE_DEFAULTS = { bal: "20", risk: "1", lev: "", entry: "now", side: "long", e: "", s: "", t: "" };       // lev empty = the bot's suggestion
const SAFETY = { ok: ["Safe", "good"], tight: ["Close", "warn"], danger: ["Danger", "bad"] };

// How big a position would be, what a stop-out costs and how far liquidation is, for one open desk call or a trade typed by hand.
// The arithmetic is lib/size.mjs (the desk's rules); the warnings are lib/sizepanel.mjs; both are tested. Nothing here can place an order.
function SizePanel({ calls, scored, bets, needed, scalp }) {
  const [v, setV] = useState(SIZE_DEFAULTS);
  useEffect(() => {
    try {
      const s = JSON.parse(window.localStorage.getItem(SIZE_KEY) || "null");
      if (s && typeof s === "object") setV((x) => Object.fromEntries(Object.keys(SIZE_DEFAULTS).map((k) => [k, typeof s[k] === "string" ? s[k] : x[k]])));
    } catch { /* private window or blocked storage: the panel works without remembering */ }
  }, []);
  const set = (patch) => {
    const n = { ...v, ...patch };
    setV(n);
    try { window.localStorage.setItem(SIZE_KEY, JSON.stringify(n)); } catch { /* ignore */ }
  };
  const [pickId, setPickId] = useState("");      // a choice made on this visit only; it is not remembered, so the panel always opens on the bot's pick
  const [more, setMore] = useState(false);
  const local = useMounted();
  const byId = Object.fromEntries(calls.map((c) => [String(c.id), c]));
  const star = todaysPick(calls, scored);
  const pick = pickId === "manual" || byId[pickId] ? pickId : star ? String(star.id) : "none";
  const call = byId[pick] || null;
  const bal = parseNum(v.bal), typedLev = parseNum(v.lev), risk = parseNum(v.risk);
  const lv = call ? levelsFor(call, v.entry) : { side: v.side, entry: parseNum(v.e), stop: parseNum(v.s), target: parseNum(v.t) };
  const hasSweet = calls.some((c) => c.sw.kind === "sweet");
  const noPickWhy = hasSweet
    ? "The open sweet-spot calls are no longer worth entering from the price now: it has already run most of the way to their stops or targets, so the bot has no pick."
    : "No sweet-spot call is open right now, so the bot has no pick. The desk checks every hour at :07, and the pick appears here when it logs one.";
  // the position and the loss at the stop do not depend on leverage, so size once at 1x, then suggest a leverage unless the person typed one
  const base = pick === "none" ? null : buildSizing({ ...lv, bal, lev: 1, riskPct: risk });
  const rec = base && base.ok ? recommendedLeverage(base.r, bal) : null;
  const levAuto = !typedLev;
  const lev = typedLev || (rec ? rec.lev : 1);
  const out = pick === "none" ? { ok: false, reason: "There is nothing for the bot to pick right now." } : buildSizing({ ...lv, bal, lev, riskPct: risk });
  const sym = call ? call.symbol.replace(/USDT$/, "") : "coins";
  const r = out.ok ? out.r : null;
  const long = lv.side !== "short";
  const sf = r ? SAFETY[r.status] : null;
  return (
    <div className="sizer">
      <h3 style={{ margin: "16px 0 6px", fontSize: 14 }}>Size a trade</h3>
      <p className="note" style={{ margin: "0 0 10px", whiteSpace: "normal" }}>
        The bot picks the trade and suggests the leverage. Enter your balance and how much of it you accept losing if the stop-loss hits, and this turns the pick into an order you can copy onto the exchange.
        It is arithmetic on the desk's rules, not a promise, and nothing on this page can place an order.
      </p>
      <div className="pickbox">
        {call ? (
          <>
            <div><b>{star && call.id === star.id ? "The bot's pick" : "Your choice"}: {sym} {call.side === "long" ? "long (a bet that it goes up)" : "short (a bet that it goes down)"}</b>{" "}
              {scored(call) ? <span className="badge good">counts in the forward test</span> : <span className="badge idle">made before the test began, not scored</span>}</div>
            <div className="note" style={{ whiteSpace: "normal" }}>
              What the desk saw: {plainSetup(call.method, call.side)}. Logged {when(call.made, local)}.
            </div>
            <div className="note" style={{ whiteSpace: "normal" }}>
              {star && call.id === star.id
                ? (scored(call)
                  ? `Why this one: it is the newest open call with a stop of 0.8% or more made since the test began, the kind the test is checking, and the price has not run most of the way to its stop. That is not a promise it wins: the test stands at ${bets} of ${needed} bets.`
                  : "Why this one: it is the newest open call with a stop of 0.8% or more and the price has not run most of the way to its stop. It was made before the test began, so it does not count in it.")
                : "You picked this one yourself."}
            </div>
          </>
        ) : pick === "manual"
          ? <div><b>Your own trade</b> <span className="note">type the levels below</span></div>
          : <div className="note" style={{ whiteSpace: "normal" }}>{noPickWhy}</div>}
        <button className="btn" onClick={() => setMore(!more)}>{more ? "Hide the other choices" : "Size a different call or type my own trade"}</button>
      </div>
      {more ? (
        <div className="sizer-in">
          <label>Which trade
            <select value={pick} onChange={(e) => setPickId(e.target.value)}>
              {calls.map((c) => (
                <option key={c.id} value={String(c.id)}>
                  {c.symbol.replace(/USDT$/, "")} {c.side} · stop {pct(c.sw.stop_pct, { dp: 2, sign: false })} away · {(SIZE_BADGE[c.sw.kind] || ["–"])[0]}{scored(c) ? " · counts in the test" : ""}
                </option>
              ))}
              <option value="manual">My own trade: type the levels</option>
            </select>
          </label>
        </div>
      ) : null}
      <div className="sizer-in">
        <label>Your futures balance ($)<input inputMode="decimal" value={v.bal} onChange={(e) => set({ bal: e.target.value })} /></label>
        <label>Most you accept losing if the stop-loss hits (% of balance)<input inputMode="decimal" value={v.risk} onChange={(e) => set({ risk: e.target.value })} /></label>
        <label>Leverage (x): empty = the bot's suggestion<input inputMode="decimal" placeholder={rec ? `suggested ${rec.lev}` : ""} value={v.lev} onChange={(e) => set({ lev: e.target.value })} /></label>
      </div>
      <div className="chips">
        <span className="note" style={{ alignSelf: "center" }}>Balance</span>
        {[10, 20, 50, 100, 300].map((x) => <button key={x} className={bal === x ? "on" : ""} onClick={() => set({ bal: String(x) })}>${x}</button>)}
        <span className="note" style={{ alignSelf: "center", marginLeft: 8 }}>Risk</span>
        {[0.5, 1, 2].map((x) => <button key={x} className={risk === x ? "on" : ""} onClick={() => set({ risk: String(x) })}>{x}%</button>)}
        {call ? (
          <>
            <span className="note" style={{ alignSelf: "center", marginLeft: 8 }}>Enter</span>
            <button className={v.entry === "now" ? "on" : ""} onClick={() => set({ entry: "now" })}>at the price now</button>
            <button className={v.entry === "logged" ? "on" : ""} onClick={() => set({ entry: "logged" })}>at the desk's logged price</button>
          </>
        ) : null}
      </div>
      {pick === "manual" ? (
        <div className="sizer-in">
          <label>Side
            <select value={v.side} onChange={(e) => set({ side: e.target.value })}>
              <option value="long">Long</option>
              <option value="short">Short</option>
            </select>
          </label>
          <label>Entry price<input inputMode="decimal" value={v.e} onChange={(e) => set({ e: e.target.value })} /></label>
          <label>Stop price<input inputMode="decimal" value={v.s} onChange={(e) => set({ s: e.target.value })} /></label>
          <label>Target price (optional)<input inputMode="decimal" value={v.t} onChange={(e) => set({ t: e.target.value })} /></label>
        </div>
      ) : null}
      {!out.ok ? <div className="empty" style={{ padding: "8px 0" }}>{out.reason}</div> : (
        <>
          {out.belowMin ? <p className="note" style={{ whiteSpace: "normal" }}><span className="badge bad">Under the minimum order</span> {usd(r.notional)} is below the $5 minimum order value, so the exchange would refuse it. At this stop it takes at least {out.needRiskPct.toFixed(2)}% risk to place it.</p> : null}
          {out.scalpStop ? <p className="note" style={{ whiteSpace: "normal" }}><span className="badge warn">Scalp-sized stop</span> The stop is only {pct(r.stopPct, { dp: 2, sign: false })} from your entry. The desk's calls with a stop under 0.4% have won {scalp?.n ? `${scalp.wins} of ${scalp.n}` : "very few"}: this close, ordinary price movement is enough to stop you out.</p> : null}
          {levAuto && rec && !rec.fits ? <p className="note" style={{ whiteSpace: "normal" }}><span className="badge bad">Too big for your balance</span> Even at the highest safe leverage ({r.maxLev}x) this position needs more margin than you have. Lower the risk, or use a call with a wider stop.</p> : null}
          {!levAuto && out.notAffordable ? <p className="note" style={{ whiteSpace: "normal" }}><span className="badge bad">Not enough balance</span> The margin is more than your balance. Use at least {out.minLev}x leverage, or a smaller risk.</p> : null}
          {out.capped ? <p className="note" style={{ whiteSpace: "normal" }}><span className="badge warn">Cut to 3× the balance</span> The desk never holds more than 3 times the balance, so the position is cut to {usd(r.notional)}; a stop-out costs {usd(r.lossAtStop)}, less than the {risk}% you chose.</p> : null}
          <div className="ticket">
            <div className="t-h">If you take this trade, this is what to enter on the exchange</div>
            <div className="trow"><div className="tl">1. Direction</div>
              <div className="tv">{long ? "LONG (buy)" : "SHORT (sell)"} {call ? `${sym}/USDT` : "your coin"} <small>perpetual futures</small></div>
              <div className="tnote">{long ? "A bet that the price goes up." : "A bet that the price goes down."}</div></div>
            <div className="trow"><div className="tl">2. Entry price</div>
              <div className="tv">about {priceFmt(lv.entry)}</div>
              <div className="tnote">{call ? (v.entry === "now" ? `The price now (the desk logged ${priceFmt(call.entry)}).` : "The price the desk logged.") : "The entry you typed."} A market order is fine; every number below assumes you get about this price.</div></div>
            <div className="trow"><div className="tl">3. Leverage</div>
              <div className="tv">{lev}x</div>
              <div className="tnote">{levAuto ? "The bot's suggestion." : "Your setting."} Anything up to {r.maxLev}x is safe for this trade. Leverage does not change how much you lose at the stop-loss: it only decides how much of your money is locked as margin and how close liquidation is. Lower is safer.</div></div>
            <div className="trow"><div className="tl">4. Position size</div>
              <div className="tv">{usd(r.notional)} <small>({fmtQty(r.qty)} {sym})</small></div>
              <div className="tnote">This locks {usd(r.margin)} of your {usd(bal)} as margin ({pct(r.marginShare, { dp: 0, sign: false })}).</div></div>
            <div className="trow"><div className="tl">5. Stop-loss at</div>
              <div className="tv down">{priceFmt(lv.stop)}</div>
              <div className="tnote">{pct(r.stopPct, { dp: 2, sign: false })} {long ? "below" : "above"} your entry. If the price touches it the trade closes and you lose about {usd(r.lossAtStop)} ({pct(r.lossShare, { dp: 2, sign: false })} of your balance), fee included.</div></div>
            <div className="trow"><div className="tl">6. Take-profit at</div>
              {r.gainAtTarget !== null
                ? <><div className="tv up">{priceFmt(lv.target)}</div>
                  <div className="tnote">{pct(r.targetPct, { dp: 2, sign: false })} {long ? "above" : "below"} your entry. If it is hit you make about {usd(r.gainAtTarget)}, {out.rr.toFixed(1)} times what you risk, after the fee.</div></>
                : <><div className="tv">none</div><div className="tnote">{out.noTarget ? "No target was given." : "The price is already past the target."}</div></>}</div>
          </div>
          <div className="safety"><span className={`badge ${sf[1]}`}>{sf[0]}</span>
            <span>{r.status === "ok"
              ? `Liquidation (the exchange force-closing your trade) would be at ${priceFmt(r.liqPrice)}, ${pct(r.liqDist, { dp: 1, sign: false })} from your entry. Your stop-loss is only ${pct(r.stopPct, { dp: 2, sign: false })} away, so it triggers long before liquidation could.`
              : r.status === "tight"
                ? `Liquidation at ${priceFmt(r.liqPrice)} is only ${r.roomX.toFixed(1)}× as far as your stop-loss, so a fast move could jump past the stop. Use ${r.maxLev}x or less.`
                : `At ${lev}x the exchange would force-close the trade at ${priceFmt(r.liqPrice)}, BEFORE your stop-loss. Use ${r.maxLev}x or less.`}</span></div>
        </>
      )}
      <p className="note" style={{ marginTop: 8, whiteSpace: "normal" }}>
        These are estimates: a 0.12% round-trip fee, a 0.5% maintenance margin and isolated margin. Your exchange's own liquidation price differs by coin and tier, the size is not rounded to the coin's smallest
        order step, and funding is left out. The calls themselves are unproven: the sweet-spot test stands at {bets} of {needed} bets. If you trade one, you place the order yourself.
      </p>
    </div>
  );
}

function SweetSpot({ a }) {
  const sw = a.sweet;
  const now = useNow(15000);
  const local = useMounted();
  if (!sw) return null;
  const fw = sw.forward || {};
  const v = fw.verdict || "";
  const badge = v.startsWith("PASS") ? ["Registered bar met", "good"] : v.startsWith("NO PASS") ? ["Registered bar not met", "bad"] : [`Unproven · ${fw.bets ?? 0} of ${fw.needed ?? 30} bets`, "warn"];
  const hhmm = new Date(sw.next_run * 1000).toISOString().slice(11, 16);
  const mins = now ? Math.max(0, Math.round((sw.next_run * 1000 - now) / 60000)) : null;
  const byId = Object.fromEntries((sw.calls || []).map((x) => [x.id, x]));
  const open = (a.open || []).map((c) => ({ ...c, sw: byId[c.id] || {} }));
  const sweetOpen = open.filter((c) => c.sw.kind === "sweet");
  const otherOpen = open.filter((c) => c.sw.kind !== "sweet");
  const fresh = (c) => { const t = Date.parse(`${String(c.made).replace(" ", "T")}:00Z`); return !!(now && t && now - t < 90 * 60000); };
  const scored = (c) => Date.parse(`${String(c.made).replace(" ", "T")}:00Z`) >= (sw.registered_ms || 0);
  const h = sw.history || {};
  return (
    <section className="card">
      <div className="card-h">
        <div><h2>Sweet-spot watch</h2>
          <div className="sub">A sweet spot is a desk call whose stop is at least {pct(sw.def_stop, { dp: 1, sign: false })} from its entry. This idea was registered on {sw.registered}, after the
            desk's first 86 calls suggested it, and is scored only on calls made after that. It needs {fw.needed ?? 30} independent bets, at least +0.15R a bet after fees and a clear
            statistical margin. Today it is a hypothesis, not a result.</div></div>
        <span className={`badge ${badge[1]}`}>{badge[0]}</span>
      </div>
      <div className="summary">
        <span>Next desk run <b>{hhmm} UTC</b>{mins !== null ? <> (in <b>{mins} min</b>)</> : null} - new calls appear then</span>
        <span>Forward test <b>{fw.bets ?? 0}</b> of {fw.needed ?? 30} bets{fw.bets ? <> · mean <b className={tone(fw.mean_r_bet)}>{rTxt(fw.mean_r_bet)}</b> a bet</> : null}</span>
        <span title="The desk's own resolved calls with a stop under 0.4%">Scalp-sized calls so far <b className="down">{h.scalp?.n ? `${h.scalp.wins} of ${h.scalp.n} hit, ${rTxt(h.scalp.mean_r)} a call` : "none"}</b></span>
      </div>

      <h3 style={{ margin: "14px 0 6px", fontSize: 14 }}>Open sweet-spot calls</h3>
      {sweetOpen.length ? (
        <div className="scroll">
          <table>
            <thead><tr><th>Call</th><th className="r">Entry</th><th className="r">Stop</th><th className="r">Target</th><th className="r">Price now</th><th className="r">From here</th><th>The odds, from the desk's own record</th></tr></thead>
            <tbody>
              {sweetOpen.map((c) => (
                <tr key={c.id}>
                  <td><div className="sym">{c.symbol.replace(/USDT$/, "")}<span className="faint">/USDT</span> {fresh(c) ? <span className="badge good">new</span> : null}</div>
                    <span className={`side ${c.side}`}>{c.side === "long" ? "Long" : "Short"}</span> <span className="note">{METHOD[c.method]} · {when(c.made, local)}</span>
                    <div>{scored(c)
                      ? <span className="badge good" title="Made after the registration: this call counts toward the forward test.">counts in the forward test</span>
                      : <span className="badge idle" title="Made before the registration: it is the kind of call that suggested the idea, so it cannot test it.">before the registration, not scored</span>}</div></td>
                  <td className="r"><div>{priceFmt(c.entry)}</div><div className="note">logged by the desk</div></td>
                  <td className="r"><div>{priceFmt(c.stop)}</div><div className="note">{pct(c.sw.stop_pct, { dp: 2, sign: false })} away</div></td>
                  <td className="r"><div>{priceFmt(c.target)}</div><div className="note">{pct(Math.abs(c.target / c.entry - 1), { dp: 2, sign: false })} away</div></td>
                  <td className="r"><div>{priceFmt(c.mark)}</div><div className={`note ${tone(c.pct)}`}>{pct(c.pct)} since the call</div></td>
                  <td className="r"><div>{c.sw.rr_now !== null && c.sw.rr_now !== undefined ? `${c.sw.rr_now.toFixed(1)}R` : "–"}</div>
                    <div className="note">{c.sw.valid ? "above the desk's 1.5R floor" : "most of the move is gone"}</div></td>
                  <td style={{ whiteSpace: "normal", minWidth: 280 }}>
                    <div>A random entry with this stop and target would hit <b>{c.base_p < 0.01 ? "under 1%" : pct(c.base_p, { dp: 0, sign: false })}</b>; it must hit <b>{pct(c.be_p, { dp: 0, sign: false })}</b> to cover fees.</div>
                    <div className="note" style={{ whiteSpace: "normal" }}>Past {c.sw.odds_scope === "method" ? `${METHOD[c.method]} ` : ""}sweet-spot calls: {oddsLine(c.sw.odds)}.
                      The cut was chosen after looking at these results, so it flatters: read it as the best case.</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="empty" style={{ padding: "8px 0" }}>No sweet-spot call is open right now. The desk checks at {hhmm} UTC and then every hour.</div>}
      {otherOpen.length ? (
        <p className="note" style={{ margin: "10px 0 0", whiteSpace: "normal" }}>
          Other open calls: {otherOpen.map((c) => (
            <span key={c.id} style={{ marginRight: 12 }}>{c.symbol.replace(/USDT$/, "")} {c.side} <span className={`badge ${(SIZE_BADGE[c.sw.kind] || ["", "idle"])[1]}`}>{(SIZE_BADGE[c.sw.kind] || ["–"])[0]}</span>
              {c.sw.odds?.n ? ` past: ${c.sw.odds.wins} of ${c.sw.odds.n} hit, ${rTxt(c.sw.odds.mean_r)} a call` : ""}</span>
          ))}
        </p>
      ) : null}

      <SizePanel calls={[...sweetOpen, ...otherOpen]} scored={scored} bets={fw.bets ?? 0} needed={fw.needed ?? 30} scalp={h.scalp} />

      <h3 style={{ margin: "16px 0 6px", fontSize: 14 }}>Coming: where a rule could fire at the next run</h3>
      {sw.watch?.length ? (
        <div className="scroll">
          <table>
            <thead><tr><th>Market</th><th>Setup</th><th>What has to happen</th><th className="r">The call it would be</th><th>Size</th></tr></thead>
            <tbody>
              {sw.watch.map((w, i) => (
                <tr key={`${w.symbol}-${w.kind}-${i}`}>
                  <td><div className="sym">{w.symbol.replace(/USDT$/, "")}<span className="faint">/USDT</span></div>
                    <span className={`side ${w.side}`}>{w.side === "long" ? "Long" : "Short"}</span> <span className="note">{priceFmt(w.price)} now</span></td>
                  <td>{w.kind === "FIB" ? "Fibonacci pullback zone" : `${w.touches}-touch ${w.side === "long" ? "support" : "resistance"} ${priceFmt(w.level)}`}
                    <div className="note">{w.kind === "FIB" ? "price is inside the zone" : `${w.dist_atr} hourly ranges away`}</div></td>
                  <td style={{ whiteSpace: "normal", minWidth: 240 }}>{w.need}</td>
                  <td className="r">{w.kind === "FIB"
                    ? (w.fires ? <><div>stop {pct(w.stop_pct, { dp: 2, sign: false })} · {w.rr}R</div><div className="note">stop {priceFmt(w.stop)} · target {priceFmt(w.target)}</div></> : <span className="note">no call</span>)
                    : <><div>stop {pct(w.stop_pct_lo, { dp: 2, sign: false })} to {pct(w.stop_pct_hi, { dp: 2, sign: false })}</div><div className="note">{w.rr ? `${w.rr[0]} to ${w.rr[1]}R (the desk needs 1.5R)` : "no target level"}</div></>}</td>
                  <td><span className={`badge ${(SIZE_BADGE[w.kind_size] || ["", "idle"])[1]}`}>{(SIZE_BADGE[w.kind_size] || ["–"])[0]}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="empty" style={{ padding: "8px 0" }}>Nothing is close to a trigger: no price is inside a Fibonacci zone or near a strong level.</div>}

      <p className="note" style={{ marginTop: 12, whiteSpace: "normal" }}>
        How to read this. <b>The odds are the desk's own resolved calls of the same stop size</b>, after the 0.12% fee. The range counts independent bets (all same-direction calls of a day are one bet,
        because one market move settles them together), so it is wide. It is not a forecast. The random-entry figure is exact for this call's stop and target. The desk logs a call at about :07 past the hour,
        so your own entry will differ a little: check the "from here" ratio. The setups that need an hour's own wick, such as the liquidity sweeps that did best inside the sweet spot, cannot be
        previewed; they show up here only once logged. Scalp-sized calls (stop under 0.4%) are where the desk has lost.
      </p>
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
            {s.bets ? `The verdict counts calls made the same day in the same direction as one bet, since one market move settles them together: ${s.bets} bet${s.bets === 1 ? "" : "s"} so far. ` : null}
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

      <SweetSpot a={a} />

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

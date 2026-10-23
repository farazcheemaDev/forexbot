"use client";
// The two charts (TradingView's lightweight-charts): the equity curve and the daily P&L bars. Times on the axis are
// shifted to the viewer's own time zone (the library draws UTC).
import { useEffect, useRef, useState } from "react";

const UP = "#0ecb81", DOWN = "#f6465d", MUTED = "#848e9c", LINE = "#2b3139";

function baseOptions() {
  return {
    autoSize: true,
    layout: { background: { type: "solid", color: "transparent" }, textColor: MUTED, fontSize: 11,
      fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif" },
    grid: { vertLines: { color: "rgba(43,49,57,.45)" }, horzLines: { color: "rgba(43,49,57,.45)" } },
    rightPriceScale: { borderColor: LINE, scaleMargins: { top: 0.12, bottom: 0.08 } },
    timeScale: { borderColor: LINE, timeVisible: true, secondsVisible: false },
    crosshair: { mode: 0, vertLine: { color: "#5e6673", labelBackgroundColor: "#2b3139" },
      horzLine: { color: "#5e6673", labelBackgroundColor: "#2b3139" } },
    handleScroll: false,
    handleScale: false,
  };
}

function useChart(build) {
  const box = useRef(null);
  const api = useRef(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let chart, gone = false;
    import("lightweight-charts").then((lw) => {
      if (gone || !box.current) return;
      chart = lw.createChart(box.current, baseOptions());
      api.current = { chart, ...build(chart, lw) };
      setReady(true);
    });
    return () => { gone = true; if (chart) chart.remove(); api.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return [box, api, ready];
}

const RANGES = [["1D", 86400], ["1W", 7 * 86400], ["1M", 30 * 86400], ["All", Infinity]];

// lightweight-charts spaces POINTS evenly, not time: 8 daily marks next to a day of hourly points would squeeze the
// days into a sliver. Put the line on an even time grid (straight lines between the real points, as a time axis
// would draw them), keeping the last real point.
function uniform(pts, maxPoints = 400) {
  if (pts.length < 3) return pts;
  const t0 = pts[0][0], t1 = pts[pts.length - 1][0];
  const step = Math.max(300, Math.ceil((t1 - t0) / maxPoints / 300) * 300);
  const out = [];
  let j = 0;
  for (let t = t0; t < t1; t += step) {
    while (j < pts.length - 2 && pts[j + 1][0] <= t) j++;
    const [ta, va] = pts[j], [tb, vb] = pts[j + 1];
    out.push([t, tb > ta ? va + ((vb - va) * (t - ta)) / (tb - ta) : vb]);
  }
  out.push(pts[pts.length - 1]);
  return out;
}

export function EquityChart({ curve, start, title = "Equity", sub = "live: booked + open positions" }) {
  const [range, setRange] = useState("All");
  const [box, api, ready] = useChart((chart) => {
    const series = chart.addAreaSeries({ lineWidth: 2, priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      lastValueVisible: true, priceLineVisible: false });
    const startLine = series.createPriceLine({ price: start, color: "#5e6673", lineWidth: 1, lineStyle: 2,
      axisLabelVisible: true, title: "start" });
    return { series, startLine };
  });
  useEffect(() => {
    if (!ready || !api.current) return;
    const tz = -new Date().getTimezoneOffset() * 60;
    const secs = RANGES.find((r) => r[0] === range)[1];
    const src = range === "1D" ? curve?.d || [] : curve?.h || [];
    const last = src.length ? src[src.length - 1][0] : 0;
    const seen = new Set();
    const clean = [...src].sort((a, b) => a[0] - b[0])
      .filter((p) => (seen.has(p[0]) ? false : (seen.add(p[0]), true)));
    const cut = clean.filter((p) => p[0] >= last - secs);
    // a range that starts between two real points begins on the line between them, not at the next point
    const k = clean.findIndex((p) => p[0] >= last - secs);
    if (k > 0 && Number.isFinite(secs) && cut.length && cut[0][0] > last - secs) cut.unshift(clean[k - 1]);
    const pts = uniform(cut).map(([t, v]) => ({ time: Math.round(t) + tz, value: Math.round(v * 100) / 100 }));
    const up = pts.length ? pts[pts.length - 1].value >= start : true;
    const c = up ? UP : DOWN;
    api.current.series.applyOptions({ lineColor: c, topColor: up ? "rgba(14,203,129,.28)" : "rgba(246,70,93,.28)",
      bottomColor: "rgba(0,0,0,0)" });
    api.current.series.setData(pts);
    api.current.chart.timeScale().fitContent();
  }, [ready, curve, start, range, api]);
  return (
    <section className="card">
      <div className="card-h">
        <div><h2>{title}</h2><div className="sub">{sub}</div></div>
        <div className="tabs">
          {RANGES.map(([r]) => <button key={r} className={r === range ? "on" : ""} onClick={() => setRange(r)}>{r}</button>)}
        </div>
      </div>
      <div ref={box} className="chart" />
    </section>
  );
}

export function DailyChart({ daily }) {
  const [box, api, ready] = useChart((chart) => {
    chart.applyOptions({ timeScale: { timeVisible: false } });
    const series = chart.addHistogramSeries({ priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      priceLineVisible: false, lastValueVisible: false });
    return { series };
  });
  useEffect(() => {
    if (!ready || !api.current) return;
    api.current.series.setData((daily || []).map(([d, v]) => ({ time: d, value: v, color: v >= 0 ? UP : DOWN })));
    api.current.chart.timeScale().fitContent();
  }, [ready, daily, api]);
  return <div ref={box} className="chart small" />;
}

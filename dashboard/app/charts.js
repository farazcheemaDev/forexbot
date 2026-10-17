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

export function EquityChart({ curve, start }) {
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
    const pts = src.filter((p) => p[0] >= last - secs).map(([t, v]) => ({ time: t + tz, value: v }))
      .filter((p) => (seen.has(p.time) ? false : (seen.add(p.time), true))).sort((a, b) => a.time - b.time);
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
        <div><h2>Equity</h2><div className="sub">live: booked + open positions</div></div>
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

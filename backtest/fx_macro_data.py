"""WHAT DRIVES FOREX - the data, 1996-2026, from free official sources (2026-10-12)

The user (2026-10-12, /goal): "run these economic data and all other data that drives forex and correlation with them -
the last 30 years would be enough". Every forex test so far read PRICE patterns; this file collects the INFORMATION
forex is said to move on. FRED is blocked from this PC (connection closed), so each series comes from its publisher:

    fx      Federal Reserve H.10 noon buying rates, daily 1996-: AUD EUR NZD GBP CAD JPY CHF (+ NOK SEK MXN ZAR as extra)
            stored as USD per unit of the foreign currency (up = the foreign currency rose)
    ust     Federal Reserve H.15 Treasury yields, daily 1996-: 3m, 2y, 10y
    policy  BIS central bank policy rates (WS_CBPOL), daily: US XM JP GB AU NZ CA CH
    oecd    OECD monthly short (3-month) and long (10-year) rates, same 8 areas
    cot     CFTC Commitments of Traders, legacy futures-only, weekly (as of Tuesday, published Friday): non-commercial
            long / short / open interest for the 7 currency futures
    tff     CFTC Traders in Financial Futures, 2006-: net positions of leveraged funds, asset managers and dealers
    mkt     Yahoo (yfinance) daily closes: ^VIX ^GSPC CL=F (oil) GC=F (gold) HG=F (copper)
    ff      ForexFactory calendar with actual / forecast, month by month, 2007-01 .. 2026-09 (backtest/ff_calendar.py)
    gdelt   GDELT news TONE and VOLUME per economy, daily 2017- (build_gdelt; the DOC API reaches back to 2017 only)
    speech  BIS central bankers' speeches with full text, 1996-2026 (build_speeches)
    y2      2-YEAR government yields, daily, from each issuer (added 2026-10-12 after the user's "you did not have all the
            information"): US (H.15), Germany for EUR (Bundesbank, Svensson 2y, 1997-), Japan (Ministry of Finance JGB
            curve, 1974-), Canada (Bank of Canada benchmark 2y, 2001-), Switzerland (SNB Confederation 2y, 1988-, to
            2025-07). The UK (Bank of England: no connection from this PC), Australia and New Zealand (RBA / RBNZ: HTTP
            403) could not be reached - those three keep the OECD 3-month rate.

All cached under strategy_analysis/data/fx_macro/ (gitignored). Re-running fetches only what is missing.

    python -m backtest.fx_macro_data            # everything except the calendar
    python -m backtest.fx_macro_data --ff       # the calendar too (~240 pages, a polite 2 s apart)
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "strategy_analysis" / "data" / "fx_macro"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
START = "1996-01-01"
CCY = ["EUR", "JPY", "GBP", "AUD", "NZD", "CAD", "CHF"]
AREAS = {"USD": ("US", "USA"), "EUR": ("XM", "EA20"), "JPY": ("JP", "JPN"), "GBP": ("GB", "GBR"), "AUD": ("AU", "AUS"),
         "NZD": ("NZ", "NZL"), "CAD": ("CA", "CAN"), "CHF": ("CH", "CHE")}
COT_CODES = {"EUR": "099741", "JPY": "097741", "GBP": "096742", "AUD": "232741", "NZD": "112741", "CAD": "090741",
             "CHF": "092741"}


def get(url: str, timeout=120) -> bytes:
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:                      # noqa: BLE001
            if k == 3:
                raise
            time.sleep(2 + 3 * k)
    return b""


def fed_ddp(rel: str, series: str) -> pd.DataFrame:
    url = (f"https://www.federalreserve.gov/datadownload/Output.aspx?rel={rel}&series={series}&lastobs=&from=01/01/1996"
           f"&to=12/31/2026&filetype=csv&label=include&layout=seriescolumn")
    raw = get(url).decode("utf-8", "replace").splitlines()
    head = [r for r in raw[:8]]
    ids = next(l for l in head if l.startswith('"Unique Identifier')).split('","')
    start = next(i for i, l in enumerate(raw) if l.startswith('"Time Period"')) + 1
    df = pd.read_csv(io.StringIO("\n".join(raw[start:])), header=None, na_values=["ND", "NC", ""])
    names = [s.strip('"').split("/")[-1] for s in ids[1:]]
    df.columns = ["date"] + names
    df["date"] = pd.to_datetime(df.date)
    return df.set_index("date").astype(float)


def build_fx():
    f = OUT / "fx_h10.csv"
    if f.exists():
        return
    d = fed_ddp("H10", "60f32914ab61dfab590e0e470153e3ae")
    # H.10 quotes AUD, EUR, NZD, GBP in USD per unit; the others in units per USD -> invert those
    m = {"AUD": ("RXI$US_N.B.AL", False), "EUR": ("RXI$US_N.B.EU", False), "NZD": ("RXI$US_N.B.NZ", False),
         "GBP": ("RXI$US_N.B.UK", False), "CAD": ("RXI_N.B.CA", True), "JPY": ("RXI_N.B.JA", True),
         "CHF": ("RXI_N.B.SZ", True), "NOK": ("RXI_N.B.NO", True), "SEK": ("RXI_N.B.SD", True),
         "MXN": ("RXI_N.B.MX", True), "ZAR": ("RXI_N.B.SF", True)}
    out = pd.DataFrame({k: (1 / d[c] if inv else d[c]) for k, (c, inv) in m.items()})
    out.to_csv(f)


def build_ust():
    f = OUT / "ust_h15.csv"
    if f.exists():
        return
    d = fed_ddp("H15", "bf17364827e38702b42a58cf8eaa3f78")
    pick = {"3m": "RIFLGFCM03_N.B", "2y": "RIFLGFCY02_N.B", "10y": "RIFLGFCY10_N.B"}     # constant-maturity yields
    assert all(v in d.columns for v in pick.values()), list(d.columns)[:30]
    d[list(pick.values())].rename(columns={v: k for k, v in pick.items()}).to_csv(f)


def build_policy():
    f = OUT / "policy_bis.csv"
    if f.exists():
        return
    keys = "+".join(v[0] for v in AREAS.values())
    raw = get(f"https://stats.bis.org/api/v1/data/WS_CBPOL/D.{keys}/all?startPeriod={START}&format=csv").decode("utf-8", "replace")
    d = pd.read_csv(io.StringIO(raw), usecols=["REF_AREA", "TIME_PERIOD", "OBS_VALUE"])
    back = {v[0]: k for k, v in AREAS.items()}
    d["ccy"] = d.REF_AREA.map(back)
    p = d.pivot_table(index="TIME_PERIOD", columns="ccy", values="OBS_VALUE")
    p.index = pd.to_datetime(p.index)
    p.sort_index().to_csv(f)


def build_oecd():
    f = OUT / "oecd_rates.csv"
    if f.exists():
        return
    rows = []
    for meas in ("IR3TIB", "IRLT"):
        for ccy, (_, iso) in AREAS.items():
            for area in ([iso] if iso != "EA20" else ["EA20", "EA19", "EA"]):
                url = (f"https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/{area}.M.{meas}.PA....."
                       f"?startPeriod=1995-01&format=csvfilewithlabels")
                try:
                    raw = get(url).decode("utf-8", "replace")
                    d = pd.read_csv(io.StringIO(raw), usecols=["TIME_PERIOD", "OBS_VALUE"])
                except Exception:                    # noqa: BLE001
                    continue
                if len(d):
                    d["ccy"], d["meas"] = ccy, ("st" if meas == "IR3TIB" else "lt")
                    rows.append(d)
                    break
                time.sleep(0.5)
    d = pd.concat(rows)
    p = d.pivot_table(index="TIME_PERIOD", columns=["meas", "ccy"], values="OBS_VALUE")
    p.columns = [f"{a}_{b}" for a, b in p.columns]
    p.index = pd.PeriodIndex(p.index, freq="M").to_timestamp(how="end").normalize()
    p.sort_index().to_csv(f)


def build_cot():
    f = OUT / "cot.csv"
    if f.exists():
        return
    names = ["deacot1986_2016.zip"] + [f"deacot{y}.zip" for y in range(2017, 2027)]
    frames = []
    for nm in names:
        z = zipfile.ZipFile(io.BytesIO(get(f"https://www.cftc.gov/files/dea/history/{nm}")))
        for inner in z.namelist():
            d = pd.read_csv(z.open(inner), low_memory=False, encoding="latin-1")
            frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    code = d["CFTC Contract Market Code"].astype(str).str.strip().str.zfill(6)
    rows = []
    for ccy, c in COT_CODES.items():
        g = d[code == c]
        rows.append(pd.DataFrame({"date": pd.to_datetime(g["As of Date in Form YYYY-MM-DD"]), "ccy": ccy,
                                  "nc_long": g["Noncommercial Positions-Long (All)"].astype(float),
                                  "nc_short": g["Noncommercial Positions-Short (All)"].astype(float),
                                  "oi": g["Open Interest (All)"].astype(float)}))
    out = pd.concat(rows).drop_duplicates(["date", "ccy"]).sort_values(["ccy", "date"], kind="stable")
    out[out.date >= "1995-01-01"].to_csv(f, index=False)


def build_mkt():
    f = OUT / "markets_yahoo.csv"
    if f.exists():
        return
    import yfinance as yf
    cols = {}
    for tk in ("^VIX", "^GSPC", "CL=F", "GC=F", "HG=F"):
        d = yf.download(tk, start=START, progress=False, auto_adjust=False)
        d.columns = d.columns.get_level_values(0)
        cols[tk] = d["Close"]
    pd.DataFrame(cols).to_csv(f)


def build_ff():
    from backtest.ff_calendar import fetch_month
    cache = OUT / "ff"
    cache.mkdir(parents=True, exist_ok=True)
    months = pd.period_range("2007-01", "2026-09", freq="M")
    for p in months:
        tag = p.strftime("%b").lower() + f".{p.year}"
        fp = cache / f"{p.year}-{p.month:02d}.json"
        if fp.exists():
            continue
        try:
            rows = fetch_month(tag)
        except Exception as e:                       # noqa: BLE001
            print("ff fail", tag, e, flush=True)
            time.sleep(10)
            continue
        fp.write_text(json.dumps([{**r, "utc": str(r["utc"])} for r in rows]))
        print("ff", tag, len(rows), flush=True)
        time.sleep(2)
    allr = []
    for fp in sorted(cache.glob("*.json")):
        allr += json.loads(fp.read_text())
    pd.DataFrame(allr).to_csv(OUT / "ff_2007_2026.csv", index=False)


def build_tff():
    """CFTC Traders in Financial Futures (2006-): leveraged funds / asset managers / dealers, per currency future."""
    f = OUT / "tff.csv"
    if f.exists():
        return
    names = ["fin_fut_txt_2006_2016.zip"] + [f"fut_fin_txt_{y}.zip" for y in range(2017, 2027)]
    frames = []
    for nm in names:
        z = zipfile.ZipFile(io.BytesIO(get(f"https://www.cftc.gov/files/dea/history/{nm}")))
        for inner in z.namelist():
            frames.append(pd.read_csv(z.open(inner), low_memory=False, encoding="latin-1"))
    d = pd.concat(frames, ignore_index=True)
    d.columns = [c.strip() for c in d.columns]
    code = d["CFTC_Contract_Market_Code"].astype(str).str.strip().str.zfill(6)
    rows = []
    for ccy, c in COT_CODES.items():
        g = d[code == c]
        rows.append(pd.DataFrame({
            "date": pd.to_datetime(g["Report_Date_as_YYYY-MM-DD"]), "ccy": ccy, "oi": g["Open_Interest_All"].astype(float),
            "lev": g["Lev_Money_Positions_Long_All"].astype(float) - g["Lev_Money_Positions_Short_All"].astype(float),
            "am": g["Asset_Mgr_Positions_Long_All"].astype(float) - g["Asset_Mgr_Positions_Short_All"].astype(float),
            "dealer": g["Dealer_Positions_Long_All"].astype(float) - g["Dealer_Positions_Short_All"].astype(float)}))
    pd.concat(rows).drop_duplicates(["date", "ccy"]).sort_values(["ccy", "date"], kind="stable").to_csv(f, index=False)


GDELT_Q = {
    "USD": '("US economy" OR "American economy" OR "Federal Reserve")',
    "EUR": '("eurozone economy" OR "euro zone economy" OR "European Central Bank")',
    "GBP": '("UK economy" OR "British economy" OR "Bank of England")',
    "JPY": '("Japan economy" OR "Japanese economy" OR "Bank of Japan")',
    "AUD": '("Australian economy" OR "Reserve Bank of Australia")',
    "NZD": '("New Zealand economy" OR "Reserve Bank of New Zealand")',
    "CAD": '("Canadian economy" OR "Bank of Canada")',
    "CHF": '("Swiss economy" OR "Swiss National Bank")',
}


def build_gdelt():
    """GDELT DOC 2.0 API, daily 2017-01-01 .. : the average TONE of the world's online news matching each economy's query,
    and its article VOLUME (share of all coverage). One request every 6 s (GDELT's limit is one per 5 s). Each series is
    cached on arrival in fx_macro/gdelt/ (a first run lost 7 series to a timeout by saving only at the end)."""
    import urllib.parse
    gd = OUT / "gdelt"
    gd.mkdir(parents=True, exist_ok=True)
    for ccy, q in GDELT_Q.items():
        for mode, tag in (("timelinetone", "tone"), ("timelinevol", "vol")):
            fp = gd / f"{tag}_{ccy}.csv"
            if fp.exists():
                continue
            url = ("https://api.gdeltproject.org/api/v2/doc/doc?query=" + urllib.parse.quote(q) +
                   f"&mode={mode}&format=csv&STARTDATETIME=20170101000000&ENDDATETIME=20261010000000")
            d = None
            for k in range(4):
                time.sleep(6)
                try:
                    d = pd.read_csv(io.StringIO(get(url).decode("utf-8-sig", "replace")))
                    if "Value" in d.columns:
                        break
                except Exception:                        # noqa: BLE001
                    pass
                d = None
                time.sleep(20)
            if d is None:
                print("gdelt failed", ccy, tag, flush=True)
                continue
            d[["Date", "Value"]].to_csv(fp, index=False)
            print("gdelt", ccy, tag, len(d), flush=True)
    cols = {}
    for fp in sorted(gd.glob("*.csv")):
        d = pd.read_csv(fp, parse_dates=["Date"])
        cols[fp.stem] = pd.Series(d.Value.values, index=d.Date)
    pd.DataFrame(cols).sort_index().to_csv(OUT / "gdelt_tone.csv")


def build_speeches():
    """BIS central bankers' speeches, one zip per year 1996-2026 (url, title, description, date, text, author), kept as
    downloaded in fx_macro/speeches/ - backtest/fx_speeches.py reads them."""
    d = OUT / "speeches"
    d.mkdir(parents=True, exist_ok=True)
    for y in range(1996, 2027):
        f = d / f"speeches-{y}.zip"
        if f.exists():
            continue
        f.write_bytes(get(f"https://www.bis.org/pages/download-central-bankers-speeches/speeches-{y}.zip", timeout=300))
        print("speeches", y, f.stat().st_size, flush=True)
        time.sleep(2)


def build_y2():
    f = OUT / "yields_2y.csv"
    if f.exists():
        return
    cols = {}
    cols["USD"] = load("ust_h15.csv")["2y"]
    raw = get("https://api.statistiken.bundesbank.de/rest/data/BBSIS/D.I.ZST.ZI.EUR.S1311.B.A604.R02XX.R.A.A._Z._Z.A"
              "?format=csv&lang=en").decode("utf-8-sig", "replace").splitlines()
    rows = [l.split(",") for l in raw if l[:4].isdigit()]
    de = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in rows if r[1] not in (".", "")})
    cols["EUR"] = de
    jp = []
    for u in ("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",
              "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"):
        d = pd.read_csv(io.StringIO(get(u).decode("utf-8", "replace")), skiprows=1, na_values=["-"])
        dt = pd.to_datetime(d["Date"], format="%Y/%m/%d", errors="coerce")       # footnote rows -> NaT, dropped
        jp.append(pd.Series(pd.to_numeric(d["2Y"], errors="coerce").values, index=dt)[dt.notna().values])
    cols["JPY"] = pd.concat(jp)
    raw = get("https://www.bankofcanada.ca/valet/observations/BD.CDN.2YR.DQ.YLD/csv?start_date=1996-01-01").decode("utf-8-sig", "replace")
    i = raw.index('"date"')
    ca = pd.read_csv(io.StringIO(raw[i:]))
    cols["CAD"] = pd.Series(pd.to_numeric(ca.iloc[:, 1], errors="coerce").values, index=pd.to_datetime(ca.iloc[:, 0]))
    raw = get("https://data.snb.ch/api/cube/rendoblid/data/csv/en").decode("utf-8-sig", "replace")
    i = raw.index('"Date"')
    ch = pd.read_csv(io.StringIO(raw[i:]), sep=";")
    ch = ch[ch.D0 == "2J"].dropna(subset=["Value"])
    cols["CHF"] = pd.Series(ch.Value.astype(float).values, index=pd.to_datetime(ch.Date))
    out = pd.DataFrame({k: v[~v.index.duplicated(keep="last")] for k, v in cols.items()}).sort_index()
    out[out.index >= "1996-01-01"].to_csv(f)


def load(name: str) -> pd.DataFrame:
    f = OUT / name
    if name in ("cot.csv", "tff.csv"):
        return pd.read_csv(f, parse_dates=["date"])
    if name == "ff_2007_2026.csv":
        return pd.read_csv(f, parse_dates=["utc"])
    return pd.read_csv(f, index_col=0, parse_dates=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ff", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for fn in (build_fx, build_ust, build_policy, build_oecd, build_cot, build_mkt, build_y2, build_tff):
        t = time.time()
        try:
            fn()
            print(f"{fn.__name__} ok ({time.time() - t:.0f}s)", flush=True)
        except Exception as e:                       # noqa: BLE001
            print(f"{fn.__name__} FAILED: {e!r}".encode("ascii", "replace").decode(), flush=True)
    if a.ff:
        build_ff()

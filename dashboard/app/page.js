import { getData } from "../lib/data";
import Dashboard from "./Dashboard";
import Refresh from "./Refresh";

export const dynamic = "force-dynamic";

export default async function Page({ searchParams }) {
  const q = searchParams?.acct;
  const want = typeof q === "string" && /^[a-z0-9]{1,20}$/.test(q) ? q : "main";
  let meta = null, acct = null, err = null;
  try {
    ({ meta, acct } = await getData(want));
  } catch (e) {
    err = String(e?.message || e);
  }
  if (!meta) {
    return (
      <main className="login"><Refresh />
        <div className="card">
          <h1>Forexbot</h1>
          <p className="down">No data yet{err ? `: ${err}` : ""}.</p>
          <p className="muted">The VM pushes once a minute (dashboard_push.py). This page retries by itself.</p>
        </div>
      </main>
    );
  }
  return <Dashboard meta={meta} acct={acct} want={want} />;
}

// Reads what the VM pushes (dashboard_push.py): forexbot:meta + forexbot:acct:<id>, each "gz:" + base64(gzip(json)).
// On Vercel: Upstash REST with a READ-ONLY token, one MGET per page load. Locally: SNAPSHOT_FILE=path/to/print.json
// (the output of `python dashboard_push.py --print`) for a test run without any account.
import { readFile } from "fs/promises";
import { gunzipSync } from "zlib";

// Forgiving about how the values were pasted into Vercel: spaces and surrounding quotes are dropped.
const env = (k) => (process.env[k] || "").trim().replace(/^["']+|["']+$/g, "");

async function upstash(cmd) {
  const url = env("UPSTASH_REDIS_REST_URL");
  const tok = env("UPSTASH_REDIS_REST_TOKEN");
  if (!url || !tok) throw new Error("UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN are not set");
  const r = await fetch(`${url.replace(/\/$/, "")}/${cmd.map(encodeURIComponent).join("/")}`, {
    headers: { Authorization: `Bearer ${tok}` },
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`Upstash ${r.status}`);
  return (await r.json()).result;
}

function unpack(raw) {
  if (!raw) return null;
  if (raw.startsWith("gz:")) return JSON.parse(gunzipSync(Buffer.from(raw.slice(3), "base64")).toString("utf8"));
  return JSON.parse(raw);
}

export async function getData(acct) {
  if (process.env.SNAPSHOT_FILE) {
    const d = JSON.parse(await readFile(process.env.SNAPSHOT_FILE, "utf8"));
    return { meta: d.meta, acct: d.accounts?.[acct] || null };
  }
  const [m, a] = (await upstash(["mget", "forexbot:meta", `forexbot:acct:${acct}`])) || [];
  return { meta: unpack(m), acct: unpack(a) };
}

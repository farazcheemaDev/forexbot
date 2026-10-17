// Reads the snapshot the VM pushes (dashboard_push.py). On Vercel: Upstash REST with a READ-ONLY token. Locally:
// SNAPSHOT_FILE=path/to/snapshot.json for a test run without any account.
import { readFile } from "fs/promises";

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

export async function getSnapshot() {
  if (process.env.SNAPSHOT_FILE) return JSON.parse(await readFile(process.env.SNAPSHOT_FILE, "utf8"));
  const raw = await upstash(["get", "forexbot:snapshot"]);
  return raw ? JSON.parse(raw) : null;
}

export async function getEquitySeries() {
  if (process.env.SNAPSHOT_FILE) return [];
  const rows = (await upstash(["lrange", "forexbot:eq", "0", "2879"])) || [];
  return rows
    .map((s) => s.split(",").map(Number))
    .filter((p) => p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]))
    .reverse();
}

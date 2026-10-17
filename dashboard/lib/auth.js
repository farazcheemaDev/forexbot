// The login cookie is an HMAC of a fixed string under DASHBOARD_SECRET: no user table, nothing to steal from the code
// (the repo is public). Web Crypto, so it runs in the middleware (edge) and in route handlers alike.
export const COOKIE = "fx_auth";

export async function token() {
  const secret = process.env.DASHBOARD_SECRET || "";
  if (secret.length < 16) return null;              // refuse to issue or accept anything without a real secret
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" },
    false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode("forexbot-dashboard-v1"));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function same(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

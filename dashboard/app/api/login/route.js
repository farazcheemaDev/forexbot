import { NextResponse } from "next/server";
import { COOKIE, same, token } from "../../../lib/auth";

export async function POST(req) {
  const form = await req.formData();
  const pw = String(form.get("password") || "");
  const want = process.env.DASHBOARD_PASSWORD || "";
  const t = await token();
  const back = new URL(req.url);
  if (!want || want.length < 8 || !t || !same(pw, want)) {
    back.pathname = "/login";
    back.search = "?e=1";
    return NextResponse.redirect(back, 303);
  }
  back.pathname = "/";
  back.search = "";
  const res = NextResponse.redirect(back, 303);
  res.cookies.set(COOKIE, t, { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 30 });
  return res;
}

import { NextResponse } from "next/server";
import { COOKIE } from "../../../lib/auth";

export async function POST(req) {
  const back = new URL(req.url);
  back.pathname = "/login";
  back.search = "";
  const res = NextResponse.redirect(back, 303);
  res.cookies.set(COOKIE, "", { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 0 });
  return res;
}

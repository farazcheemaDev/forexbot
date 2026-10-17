import { NextResponse } from "next/server";
import { COOKIE, same, token } from "./lib/auth";

// Every page needs the login cookie except the login page and its handler.
export async function middleware(req) {
  const { pathname } = req.nextUrl;
  if (pathname.startsWith("/login") || pathname.startsWith("/api/login")) return NextResponse.next();
  const want = await token();
  const got = req.cookies.get(COOKIE)?.value;
  if (want && same(got, want)) return NextResponse.next();
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  return NextResponse.redirect(url);
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };

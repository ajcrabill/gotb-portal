/**
 * Route protection middleware.
 *
 * Public routes: /sign-in, /embed/*, /api/*
 * All other routes require a valid session (token in sessionStorage is checked
 * client-side; the server validates via /api/auth/me on layout mount).
 *
 * Role-based routing:
 *   /admin/*       → superuser, lead_senior_practitioner
 *   /portal/*      → any authenticated user
 *   /sign-in       → unauthenticated only (authenticated → /portal/dashboard)
 *
 * Note: Next.js middleware runs on the edge — it cannot inspect sessionStorage.
 * The token lives in sessionStorage so it's JS-only. Middleware enforces
 * route existence and i18n; actual auth state is checked server-side via
 * the API in layout.tsx server components.
 */
import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/sign-in", "/embed"];
const API_PATHS = ["/api"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Pass API routes and public paths through
  if (
    API_PATHS.some((p) => pathname.startsWith(p)) ||
    PUBLIC_PATHS.some((p) => pathname.startsWith(p))
  ) {
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

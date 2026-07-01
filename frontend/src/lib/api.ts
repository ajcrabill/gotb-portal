/**
 * ESB Portal API client.
 *
 * All requests are authenticated via Bearer token stored in
 * sessionStorage (not localStorage — clears on tab close).
 * The token is never placed in cookies to avoid CSRF surface.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("esb_token");
}

export function setToken(token: string): void {
  sessionStorage.setItem("esb_token", token);
}

export function clearToken(): void {
  sessionStorage.removeItem("esb_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    let code = "UNKNOWN";
    let message = res.statusText;
    try {
      const body = await res.json();
      code = body?.detail?.code ?? body?.code ?? "UNKNOWN";
      message = body?.detail?.message ?? body?.detail ?? body?.message ?? message;
    } catch {}
    throw new ApiError(res.status, code, message);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export type OTPResponse = { sent: boolean; dev_otp?: string };
export type SessionResponse = { token: string; person_id: string; roles: string[] };
export type MeResponse = { person_id: string; roles: string[]; is_step_up: boolean };

export const auth = {
  requestOtp: (email: string, name?: string) =>
    request<OTPResponse>("/api/auth/request-otp", {
      method: "POST",
      body: JSON.stringify({ email, name }),
    }),

  verifyOtp: (email: string, code: string) =>
    request<SessionResponse>("/api/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    }),

  stepUp: (code: string) =>
    request<{ token: string }>("/api/auth/step-up", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),

  logout: () =>
    request<void>("/api/auth/logout", { method: "POST" }).then(() => clearToken()),

  me: () => request<MeResponse>("/api/auth/me"),
};

import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";
const BACKEND_TIMEOUT_MS = 180_000;

export async function proxyBackend(path: string, init: RequestInit = {}): Promise<NextResponse> {
  const backendUrl = (process.env.RELEASE_CAPTAIN_API_URL ?? DEFAULT_BACKEND_URL).replace(/\/+$/, "");

  try {
    const response = await fetch(`${backendUrl}${path}`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
      headers: {
        Accept: "application/json",
        ...(init.body ? { "content-type": "application/json" } : {}),
        ...(init.headers ?? {}),
      },
    });
    const payload = await response.json().catch(() => ({ detail: `Backend returned HTTP ${response.status} without JSON.` }));
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    const message = error instanceof Error ? error.message : "The Release Captain backend could not be reached.";
    const detail = error instanceof Error && error.name === "TimeoutError"
      ? "The backend took too long to complete this request. Check the session again before retrying."
      : message;
    return NextResponse.json({ detail }, { status: 502 });
  }
}

export async function readJsonBody(request: Request): Promise<unknown | NextResponse> {
  try {
    return await request.json();
  } catch {
    return NextResponse.json({ detail: "Request body must be valid JSON." }, { status: 400 });
  }
}

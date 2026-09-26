import { NextResponse } from "next/server";
import { proxyBackend, readJsonBody } from "../../../../../lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function POST(request: Request, context: { params: Promise<{ sessionId: string }> }) {
  const body = await readJsonBody(request);
  if (body instanceof NextResponse) return body;
  const { sessionId } = await context.params;
  return proxyBackend(`/api/sessions/${encodeURIComponent(sessionId)}/approve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

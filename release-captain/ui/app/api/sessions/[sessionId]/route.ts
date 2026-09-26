import { proxyBackend } from "../../../../lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, context: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = await context.params;
  return proxyBackend(`/api/sessions/${encodeURIComponent(sessionId)}`);
}

import { NextResponse } from "next/server";
import { proxyBackend, readJsonBody } from "../../../lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = await readJsonBody(request);
  if (body instanceof NextResponse) return body;

  const input = body && typeof body === "object" && !Array.isArray(body) ? (body as Record<string, unknown>) : {};
  const repositoryUrl = typeof input.repositoryUrl === "string" ? input.repositoryUrl.trim() : "";
  const branch = typeof input.branch === "string" ? input.branch.trim() : "";
  const previousTag = typeof input.previousTag === "string" ? input.previousTag.trim() : "";
  const testCommand = typeof input.testCommand === "string" ? input.testCommand.trim() : "";

  if (!repositoryUrl || !branch) {
    return NextResponse.json({ detail: "Repository URL and branch are required." }, { status: 400 });
  }

  return proxyBackend("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      repository_url: repositoryUrl,
      branch,
      previous_tag: previousTag || null,
      test_command: testCommand,
    }),
  });
}

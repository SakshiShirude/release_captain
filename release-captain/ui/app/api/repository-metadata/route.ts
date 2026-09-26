import { NextRequest, NextResponse } from "next/server";
import { proxyBackend } from "../../../lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const repositoryUrl = request.nextUrl.searchParams.get("repositoryUrl")?.trim() ?? "";
  if (!repositoryUrl) return NextResponse.json({ detail: "Repository URL is required." }, { status: 400 });
  return proxyBackend(`/api/repository-metadata?repository_url=${encodeURIComponent(repositoryUrl)}`);
}

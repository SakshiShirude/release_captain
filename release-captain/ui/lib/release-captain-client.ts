export type RepositoryMetadata = {
  repository_key: string;
  default_branch: string;
  branches: string[];
  tags: string[];
  test_command: string;
  test_command_reason: string;
  source: string;
};

export type BackendHealth = {
  status: string;
  demo_mode: boolean;
  sandbox_enabled: boolean;
  execution_enabled: boolean;
  local_test_runner_enabled: boolean;
  analysis_only: boolean;
};

export type CommitChange = {
  sha: string;
  message: string;
  author: string;
  category: string;
  breaking: boolean;
};

export type PullRequestChange = {
  number: number;
  title: string;
  author: string;
  labels: string[];
  merged: boolean;
};

export type ObservedToolCall = {
  id: string;
  tool_name: string;
  method: string;
  path: string;
  status: "success" | "error" | "simulated" | string;
  status_code: number | null;
  duration_seconds: number;
  detail: string;
};

export type TestResult = {
  command: string;
  status: string;
  exit_code: number;
  duration_seconds: number;
  passed_count: number | null;
  failed_count: number | null;
  log_excerpt: string;
  sandbox_provider: string;
};

export type ReleaseRisk = {
  title: string;
  severity: string;
  evidence: string[];
};

export type ReleasePlan = {
  current_version: string;
  recommended_version: string;
  bump: string;
  summary: string;
  categories: Record<string, string[]>;
  breaking_changes: string[];
  risks: ReleaseRisk[];
  release_notes: string;
  proposed_actions: string[];
};

export type AuditEvent = {
  timestamp: string;
  action: string;
  status: string;
  detail: string;
};

export type BackendReleaseSession = {
  id: string;
  repository_url: string;
  branch: string;
  previous_tag: string | null;
  test_command: string;
  analysis_only: boolean;
  sandbox_enabled: boolean;
  status: string;
  created_at: string;
  commits: CommitChange[];
  pull_requests: PullRequestChange[];
  observed_tool_calls: ObservedToolCall[];
  test_result: TestResult | null;
  plan: ReleasePlan | null;
  audit: AuditEvent[];
  approval: {
    approved: boolean;
    plan_version: string;
    repository_url: string;
    actions: string[];
    comment: string | null;
  } | null;
  evidence: Record<string, unknown>;
};

export type ReleaseEvidence = {
  commits: CommitChange[];
  pull_requests: PullRequestChange[];
  test_result: TestResult | null;
  plan: ReleasePlan | null;
  evidence: Record<string, unknown>;
};

export type CreateReleaseInput = {
  repositoryUrl: string;
  branch: string;
  previousTag: string;
  testCommand: string;
};

export type ApprovalInput = {
  approved: true;
  plan_version: string;
  repository_url: string;
  actions: string[];
  comment?: string;
};

async function readJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.detail ?? payload?.error ?? payload?.message;
    const message = Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(" ")
      : typeof detail === "string"
        ? detail
        : `Request failed with status ${response.status}.`;
    throw new Error(message);
  }
  return payload as T;
}

export async function fetchBackendHealth(): Promise<BackendHealth> {
  return readJson<BackendHealth>(await fetch("/api/health", { cache: "no-store" }));
}

export async function fetchRepositoryMetadata(repositoryUrl: string): Promise<RepositoryMetadata> {
  const query = new URLSearchParams({ repositoryUrl });
  return readJson<RepositoryMetadata>(await fetch(`/api/repository-metadata?${query}`, { cache: "no-store" }));
}

export async function createReleaseSession(input: CreateReleaseInput): Promise<BackendReleaseSession> {
  return readJson<BackendReleaseSession>(
    await fetch("/api/sessions", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function fetchReleaseSession(sessionId: string): Promise<BackendReleaseSession> {
  return readJson<BackendReleaseSession>(await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, { cache: "no-store" }));
}

export async function fetchReleaseEvidence(sessionId: string): Promise<ReleaseEvidence> {
  return readJson<ReleaseEvidence>(await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/evidence`, { cache: "no-store" }));
}

export async function fetchReleaseAudit(sessionId: string): Promise<AuditEvent[]> {
  return readJson<AuditEvent[]>(await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/audit`, { cache: "no-store" }));
}

export async function approveReleaseSession(sessionId: string, approval: ApprovalInput): Promise<BackendReleaseSession> {
  return readJson<BackendReleaseSession>(
    await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/approve`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(approval),
    }),
  );
}

export async function requestReleaseChanges(sessionId: string, comment: string): Promise<BackendReleaseSession> {
  return readJson<BackendReleaseSession>(
    await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/request-changes`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ comment }),
    }),
  );
}

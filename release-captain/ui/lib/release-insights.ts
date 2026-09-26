import type { BackendReleaseSession, ReleaseEvidence } from "./release-captain-client";

export type EvidenceCounts = {
  commits: number;
  pullRequests: number;
  changedFiles: number;
  ciRuns: number;
};

export function getEvidenceCounts(session: BackendReleaseSession, evidence: ReleaseEvidence): EvidenceCounts {
  const changedFiles = evidence.evidence.changed_files;
  const ciRuns = evidence.evidence.ci_runs;
  return {
    commits: evidence.commits?.length ?? session.commits.length,
    pullRequests: evidence.pull_requests?.length ?? session.pull_requests.length,
    changedFiles: Array.isArray(changedFiles) ? changedFiles.length : 0,
    ciRuns: Array.isArray(ciRuns) ? ciRuns.length : 0,
  };
}

export function statusTone(status?: string | null): "done" | "waiting" | "failed" | "running" {
  const normalized = status?.toLowerCase() ?? "";
  if (["completed", "complete", "passed", "success", "approved"].includes(normalized)) return "done";
  if (["failed", "failure", "error"].includes(normalized)) return "failed";
  if (["ready_for_approval", "waiting", "unavailable", "rejected", "blocked", "simulated", "skipped"].includes(normalized)) return "waiting";
  return "running";
}

export function prettyLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

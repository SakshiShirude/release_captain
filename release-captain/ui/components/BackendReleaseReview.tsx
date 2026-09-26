"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  approveReleaseSession,
  fetchBackendHealth,
  fetchReleaseAudit,
  fetchReleaseEvidence,
  fetchReleaseSession,
  requestReleaseChanges,
  type AuditEvent,
  type BackendHealth,
  type BackendReleaseSession,
  type ReleaseEvidence,
} from "../lib/release-captain-client";
import { getEvidenceCounts, prettyLabel, statusTone } from "../lib/release-insights";
import { ReleaseHighlights } from "./ReleaseHighlights";

type BackendReleaseReviewProps = {
  sessionId: string;
};

type JsonRecord = Record<string, unknown>;

const EMPTY_EVIDENCE: ReleaseEvidence = {
  commits: [],
  pull_requests: [],
  test_result: null,
  plan: null,
  evidence: {},
};

function humanStatus(status?: string): string {
  const labels: Record<string, string> = {
    created: "Created",
    collecting: "Collecting evidence",
    analyzing: "Analyzing changes",
    testing: "Running tests",
    ready_for_approval: "Waiting for approval",
    approved: "Approved",
    executing: "Executing approved actions",
    completed: "Completed",
    rejected: "Changes requested",
    failed: "Failed",
  };
  return status ? labels[status] ?? prettyLabel(status) : "Unknown";
}

function timestampLabel(value?: string | null): string {
  if (!value) return "Time unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Time unavailable"
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function textValue(value: unknown, fallback = "Not recorded"): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function shortRepositoryLabel(repositoryUrl: string): string {
  return repositoryUrl.replace(/^https?:\/\//, "").replace(/^github\.com\//, "");
}

function records(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((item): item is JsonRecord => Boolean(item) && typeof item === "object" && !Array.isArray(item))
    : [];
}

function sourceLabel(source: unknown): string {
  if (source === "github") return "GitHub API";
  if (source === "demo") return "Deterministic demo data";
  return "Backend evidence";
}

function renderNotes(notes: string) {
  const sections: Array<{ title: string; lines: string[] }> = [];
  let current = { title: "Release notes", lines: [] as string[] };
  for (const line of notes.split("\n")) {
    if (line.startsWith("## ")) {
      if (current.lines.length) sections.push(current);
      current = { title: line.slice(3).trim(), lines: [] };
    } else if (line.trim()) {
      current.lines.push(line.trim());
    }
  }
  if (current.lines.length) sections.push(current);

  return sections.map((section, index) => {
    const bullets = section.lines.filter((line) => /^[-*]\s+/.test(line));
    const paragraphs = section.lines.filter((line) => !/^[-*]\s+/.test(line));
    return (
      <article className="notes-section" key={`${section.title}-${index}`}>
        <h3>{section.title}</h3>
        {paragraphs.map((line, lineIndex) => <p key={lineIndex}>{line.replace(/\*\*(.*?)\*\*/g, "$1").replace(/`/g, "")}</p>)}
        {bullets.length ? (
          <ul>{bullets.map((line, lineIndex) => <li key={lineIndex}>{line.replace(/^[-*]\s+/, "").replace(/\*\*(.*?)\*\*/g, "$1").replace(/`/g, "")}</li>)}</ul>
        ) : null}
      </article>
    );
  });
}

function ProgressSteps({ session, audit }: { session: BackendReleaseSession; audit: AuditEvent[] }) {
  const completed = new Set(audit.filter((item) => ["completed", "passed", "unavailable"].includes(item.status)).map((item) => item.action));
  const steps = [
    { label: "Repository evidence", action: "collect_repository", active: session.status === "collecting" },
    { label: "Release plan", action: "analyze_release", active: session.status === "analyzing" },
    { label: "Test result", action: "run_tests", active: session.status === "testing" },
    { label: "Human review", action: "approval_gate", active: session.status === "ready_for_approval" || session.status === "approved" || session.status === "executing" || session.status === "completed" },
  ];

  return (
    <ol className="review-steps" aria-label="Release review progress">
      {steps.map((step, index) => {
        const done = completed.has(step.action) || (step.action === "approval_gate" && ["approved", "executing", "completed"].includes(session.status));
        const state = done ? "done" : step.active ? "active" : session.status === "failed" ? "failed" : "pending";
        return (
          <li className={`review-step ${state}`} key={step.action}>
            <span className="review-step-index">{done ? "✓" : String(index + 1).padStart(2, "0")}</span>
            <span>{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

export function BackendReleaseReview({ sessionId }: BackendReleaseReviewProps) {
  const [session, setSession] = useState<BackendReleaseSession | null>(null);
  const [evidence, setEvidence] = useState<ReleaseEvidence>(EMPTY_EVIDENCE);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionBusy, setActionBusy] = useState<"approve" | "changes" | "">("");
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [approvedExactPlan, setApprovedExactPlan] = useState(false);
  const [approvalComment, setApprovalComment] = useState("");
  const [changeComment, setChangeComment] = useState("");

  const refresh = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    else setRefreshing(true);
    setError("");
    try {
      const [nextSession, nextEvidence, nextAudit] = await Promise.all([
        fetchReleaseSession(sessionId),
        fetchReleaseEvidence(sessionId),
        fetchReleaseAudit(sessionId),
      ]);
      setSession(nextSession);
      setEvidence(nextEvidence);
      setAudit(nextAudit);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not load the backend release session.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void refresh(true);
    fetchBackendHealth().then(setHealth).catch(() => setHealth(null));
  }, [refresh]);

  const plan = evidence.plan ?? session?.plan ?? null;
  const testResult = evidence.test_result ?? session?.test_result ?? null;
  const counts = useMemo(() => session ? getEvidenceCounts(session, evidence) : null, [session, evidence]);
  const changedFiles = records(evidence.evidence.changed_files);
  const ciRuns = records(evidence.evidence.ci_runs);
  const dataSource = sourceLabel(evidence.evidence.source);
  const waitingForApproval = session?.status === "ready_for_approval";
  const riskCount = plan?.risks.length ?? 0;
  const pendingActions = plan?.proposed_actions.length ?? 0;
  const reviewSummary = plan
    ? [
        {
          label: "Recommendation",
          value: plan.recommended_version,
          tone: plan.bump === "major" ? "waiting" : "done",
          meta: `${prettyLabel(plan.bump)} release`,
          detail: plan.summary,
        },
        {
          label: "Approval",
          value: humanStatus(session?.status),
          tone: statusTone(session?.status),
          meta: waitingForApproval ? `${pendingActions} action${pendingActions === 1 ? "" : "s"} waiting` : "Backend state",
          detail: waitingForApproval ? "Review and confirm the listed release actions." : "The current approval state is synced from the backend.",
        },
        {
          label: "Tests",
          value: prettyLabel(testResult?.status ?? "pending"),
          tone: statusTone(testResult?.status),
          meta: testResult?.command || session?.test_command || "No test command configured",
          detail: testResult?.status === "unavailable"
            ? testResult.log_excerpt
            : testResult
              ? `${testResult.duration_seconds.toFixed(2)}s in ${testResult.sandbox_provider}`
              : "No test result has been recorded yet.",
        },
        {
          label: "Evidence",
          value: `${counts?.commits ?? 0} commits`,
          tone: "running" as const,
          meta: `${counts?.pullRequests ?? 0} PRs · ${counts?.changedFiles ?? 0} files · ${session?.observed_tool_calls.length ?? 0} calls`,
          detail: riskCount ? `${riskCount} risk${riskCount === 1 ? "" : "s"} highlighted for review.` : "No release risks were reported by the backend.",
        },
      ]
    : [];

  function adoptSession(nextSession: BackendReleaseSession) {
    setSession(nextSession);
    setEvidence({
      commits: nextSession.commits,
      pull_requests: nextSession.pull_requests,
      test_result: nextSession.test_result,
      plan: nextSession.plan,
      evidence: nextSession.evidence,
    });
    setAudit(nextSession.audit);
    setApprovedExactPlan(false);
  }

  async function submitApproval() {
    if (!session || !plan || !approvedExactPlan) return;
    setActionBusy("approve");
    setActionError("");
    try {
      const updated = await approveReleaseSession(session.id, {
        approved: true,
        plan_version: plan.recommended_version,
        repository_url: session.repository_url,
        actions: plan.proposed_actions,
        comment: approvalComment.trim() || undefined,
      });
      adoptSession(updated);
    } catch (caughtError) {
      setActionError(caughtError instanceof Error ? caughtError.message : "Approval could not be recorded.");
      await refresh(false);
    } finally {
      setActionBusy("");
    }
  }

  async function submitChanges() {
    if (!session || changeComment.trim().length < 4) return;
    setActionBusy("changes");
    setActionError("");
    try {
      const updated = await requestReleaseChanges(session.id, changeComment.trim());
      adoptSession(updated);
    } catch (caughtError) {
      setActionError(caughtError instanceof Error ? caughtError.message : "The change request could not be recorded.");
      await refresh(false);
    } finally {
      setActionBusy("");
    }
  }

  if (loading) {
    return <main className="shell"><div className="detail-card loading-card" role="status">Loading release evidence from the backend…</div></main>;
  }

  if (error && !session) {
    return (
      <main className="shell">
        <div className="detail-card error-card">
          <p className="eyebrow">Session unavailable</p>
          <h1 className="panel-title">Could not load this release review</h1>
          <p className="copy">{error}</p>
          <div className="actions"><button className="button secondary" onClick={() => void refresh(true)}>Try again</button><Link className="button primary" href="/">Start a review</Link></div>
        </div>
      </main>
    );
  }

  if (!session) return null;

  return (
    <main className="shell review-shell">
      <header className="topbar review-topbar">
        <div className="workspace-copy review-repo-copy">
          <p className="eyebrow">Release review · {session.branch}</p>
          <h1 className="session-title review-repo-title">{shortRepositoryLabel(session.repository_url)}</h1>
          <p className="copy">Baseline {session.previous_tag || textValue(evidence.evidence.base_ref, "latest available release")} · Created {timestampLabel(session.created_at)}</p>
        </div>
        <div className="review-header-actions">
          <span className={`pill ${statusTone(session.status)}`}>{humanStatus(session.status)}</span>
          <button className="button secondary compact-button" onClick={() => void refresh(false)} disabled={refreshing || Boolean(actionBusy)}>
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
          <Link href="/" className="button secondary compact-button">New review</Link>
        </div>
      </header>

      {error ? <div className="inline-alert" role="status">Refresh failed: {error}</div> : null}

      {plan ? (
        <section className="detail-card review-summary-card" aria-label="Release review summary">
          <div className="panel-heading review-summary-heading">
            <div>
              <p className="eyebrow">Release review summary</p>
              <h2 className="panel-title">The decision-critical information is here first</h2>
            </div>
            <span className={`pill ${plan.bump === "major" ? "waiting" : "done"}`}>{prettyLabel(plan.bump)} bump</span>
          </div>

          <div className="review-summary-grid">
            {reviewSummary.map((item) => (
              <article className="review-summary-item" key={item.label}>
                <div className="review-summary-item-top">
                  <span className="review-summary-label">{item.label}</span>
                  <span className={`pill ${item.tone}`}>{item.meta}</span>
                </div>
                <strong className="review-summary-value">{item.value}</strong>
                <p className="review-summary-detail">{item.detail}</p>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section className="review-environment-row" aria-label="Backend mode">
        <span className={`status-chip ${health?.demo_mode ? "warning" : "live"}`}>{health?.demo_mode ? "Demo mode · simulated evidence" : dataSource}</span>
        <span className="status-chip">{session.sandbox_enabled ? "Sandbox tests enabled" : "Sandbox disabled"}</span>
        <span className={`status-chip ${health?.execution_enabled ? "warning" : ""}`}>
          {health ? (health.execution_enabled ? "Release execution enabled" : "Release execution disabled") : "Execution mode unknown"}
        </span>
      </section>

      {counts ? (
        <nav className="review-stat-strip" aria-label="Evidence counts">
          <a className="review-stat" href="#commits"><span>Commits</span><strong>{counts.commits}</strong></a>
          <a className="review-stat" href="#pull-requests"><span>Pull requests</span><strong>{counts.pullRequests}</strong></a>
          <a className="review-stat" href="#changed-files"><span>Changed files</span><strong>{counts.changedFiles}</strong></a>
          <a className="review-stat" href="#test-result"><span>Test result</span><strong>{testResult?.status ?? "Pending"}</strong></a>
          <a className="review-stat" href="#audit-timeline"><span>Audit events</span><strong>{audit.length}</strong></a>
        </nav>
      ) : null}

      <ProgressSteps session={session} audit={audit} />

      <section className="review-layout">
        <div className="review-main-column">
          <section className="detail-card plan-card" id="release-plan">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Release recommendation</p>
                <h2 className="panel-title">{plan?.summary ?? "No release plan was produced."}</h2>
              </div>
              {plan ? <span className={`pill ${plan.bump === "major" ? "waiting" : "done"}`}>{prettyLabel(plan.bump)} bump</span> : null}
            </div>

            {plan ? (
              <>
                <div className="version-comparison">
                  <div><span>Current version</span><strong>{plan.current_version}</strong></div>
                  <span className="version-arrow" aria-hidden="true">→</span>
                  <div className="recommended-version"><span>Recommended</span><strong>{plan.recommended_version}</strong></div>
                </div>

                {plan.risks.length ? (
                  <div className="risk-list" aria-label="Risks to review">
                    {plan.risks.map((risk, index) => (
                      <article className={`risk-row ${risk.severity.toLowerCase()}`} key={`${risk.title}-${index}`}>
                        <div className="risk-row-heading"><strong>{risk.title}</strong><span className={`pill ${risk.severity.toLowerCase() === "high" ? "failed" : "waiting"}`}>{risk.severity}</span></div>
                        {risk.evidence.length ? <ul>{risk.evidence.map((item) => <li key={item}>{item}</li>)}</ul> : null}
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="quiet-note">The backend did not report a release risk for this plan.</p>
                )}
              </>
            ) : null}
          </section>

          <section className="detail-card evidence-section" id="repository-evidence">
            <div className="panel-heading">
              <div><p className="eyebrow">Repository evidence</p><h2 className="panel-title">What the backend collected</h2></div>
              <span className="pill">{dataSource}</span>
            </div>

            <details className="evidence-disclosure" id="commits">
              <summary><span>Commits in scope</span><strong>{counts?.commits ?? 0}</strong></summary>
              {evidence.commits.length ? (
                <ul className="evidence-list">
                  {evidence.commits.map((commit) => (
                    <li key={`${commit.sha}-${commit.message}`}>
                      <div className="evidence-item-heading">
                        <strong>{commit.message}</strong>
                        {commit.breaking ? <span className="pill failed">Breaking</span> : null}
                      </div>
                      <span className="evidence-meta">{commit.category} · {commit.author} · <code>{commit.sha.slice(0, 8)}</code></span>
                    </li>
                  ))}
                </ul>
              ) : <p className="quiet-note">No commits were returned by the backend.</p>}
            </details>

            <details className="evidence-disclosure" id="pull-requests">
              <summary><span>Merged pull requests</span><strong>{counts?.pullRequests ?? 0}</strong></summary>
              {evidence.pull_requests.length ? (
                <ul className="evidence-list">
                  {evidence.pull_requests.map((pullRequest) => (
                    <li key={pullRequest.number}>
                      <div className="evidence-item-heading"><strong>#{pullRequest.number} · {pullRequest.title}</strong><span className="evidence-meta">{pullRequest.author}</span></div>
                      {pullRequest.labels.length ? <div className="label-row">{pullRequest.labels.map((label) => <span className="evidence-label" key={label}>{label}</span>)}</div> : null}
                    </li>
                  ))}
                </ul>
              ) : <p className="quiet-note">No merged pull requests were returned by the backend.</p>}
            </details>

            <details className="evidence-disclosure" id="changed-files">
              <summary><span>Changed files</span><strong>{counts?.changedFiles ?? 0}</strong></summary>
              {changedFiles.length ? (
                <ul className="file-evidence-list">
                  {changedFiles.map((file, index) => (
                    <li key={`${String(file.path)}-${index}`}>
                      <code>{textValue(file.path)}</code>
                      <span className="file-change-counts">{textValue(file.status, "modified")} · +{String(file.additions ?? 0)} / −{String(file.deletions ?? 0)}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="quiet-note">Changed-file details were not available for this comparison.</p>}
            </details>

            <details className="evidence-disclosure" id="ci-evidence">
              <summary><span>Recent CI runs</span><strong>{counts?.ciRuns ?? 0}</strong></summary>
              {ciRuns.length ? (
                <ul className="evidence-list">
                  {ciRuns.map((run, index) => (
                    <li key={`${String(run.name)}-${index}`}>
                      <div className="evidence-item-heading"><strong>{textValue(run.name, "Workflow")}</strong><span className={`pill ${statusTone(textValue(run.conclusion, textValue(run.status, "unknown")))}`}>{textValue(run.conclusion, textValue(run.status, "unknown"))}</span></div>
                      {typeof run.url === "string" && run.url.startsWith("https://") ? <a className="evidence-link" href={run.url} target="_blank" rel="noreferrer">Open workflow run</a> : null}
                    </li>
                  ))}
                </ul>
              ) : <p className="quiet-note">No CI run data was returned by the backend.</p>}
            </details>
          </section>

          <section className="detail-card tool-observation-section" id="observed-tools">
            <div className="panel-heading">
              <div><p className="eyebrow">Backend activity</p><h2 className="panel-title">Observed tool calls</h2><p className="copy panel-description">GitHub API requests made during collection. Demo entries are labeled as simulated.</p></div>
              <span className="pill">{session.observed_tool_calls.length}</span>
            </div>
            {session.observed_tool_calls.length ? (
              <div className="observed-call-list">
                {session.observed_tool_calls.map((call, index) => (
                  <article className="observed-call" key={call.id}>
                    <span className="observed-call-index">{String(index + 1).padStart(2, "0")}</span>
                    <div className="observed-call-content">
                      <div className="observed-call-heading"><strong>{call.method} <code>{call.path}</code></strong><span className={`pill ${statusTone(call.status)}`}>{call.status === "simulated" ? "Simulated" : call.status_code ? `HTTP ${call.status_code}` : prettyLabel(call.status)}</span></div>
                      <p>{call.detail}</p>
                    </div>
                    <span className="observed-call-duration">{call.duration_seconds.toFixed(2)}s</span>
                  </article>
                ))}
              </div>
            ) : <p className="quiet-note">No GitHub API calls were recorded for this session.</p>}
          </section>

          {plan?.release_notes ? (
            <section className="detail-card" id="release-notes">
              <div className="panel-heading"><div><p className="eyebrow">Draft</p><h2 className="panel-title">Release notes</h2></div></div>
              <div className="release-notes-content">{renderNotes(plan.release_notes)}</div>
            </section>
          ) : null}

          <section className="detail-card audit-section" id="audit-timeline">
            <div className="panel-heading"><div><p className="eyebrow">Persisted backend events</p><h2 className="panel-title">Audit timeline</h2></div><span className="pill">{audit.length} events</span></div>
            {audit.length ? (
              <ol className="audit-list">
                {[...audit].reverse().map((item, index) => (
                  <li className="audit-item" key={`${item.timestamp}-${item.action}-${index}`}>
                    <span className={`audit-marker ${statusTone(item.status)}`} aria-hidden="true" />
                    <div><div className="audit-item-heading"><strong>{prettyLabel(item.action)}</strong><span className={`pill ${statusTone(item.status)}`}>{prettyLabel(item.status)}</span></div><p>{item.detail}</p><time>{timestampLabel(item.timestamp)}</time></div>
                  </li>
                ))}
              </ol>
            ) : <p className="quiet-note">The backend has not recorded any audit events yet.</p>}
          </section>
        </div>

        <aside className="review-aside">
          <section className={`detail-card approval-card ${waitingForApproval ? "approval-card-active" : ""}`} id="approval-gate">
            <div className="panel-heading">
              <div><p className="eyebrow">Human checkpoint</p><h2 className="panel-title">Approval gate</h2></div>
              <span className={`pill ${statusTone(session.status)}`}>{humanStatus(session.status)}</span>
            </div>

            {waitingForApproval && plan ? (
              <>
                <p className="approval-summary">Approving submits the exact version, repository, and actions shown below to the backend.</p>
                <ul className="approval-action-list">{plan.proposed_actions.map((action) => <li key={action}>{action}</li>)}</ul>
                <label className="approval-check">
                  <input type="checkbox" checked={approvedExactPlan} onChange={(event) => setApprovedExactPlan(event.target.checked)} disabled={Boolean(actionBusy)} />
                  <span>I reviewed and approve these exact actions.</span>
                </label>
                <label className="field approval-comment-field" htmlFor="approval-comment">
                  <span>Approval note <small>Optional</small></span>
                  <textarea id="approval-comment" rows={2} value={approvalComment} onChange={(event) => setApprovalComment(event.target.value)} placeholder="Add release context for the audit log" disabled={Boolean(actionBusy)} />
                </label>
                <button className="button primary full-button" onClick={() => void submitApproval()} disabled={!approvedExactPlan || !health || Boolean(actionBusy)}>
                  {actionBusy === "approve" ? "Submitting approval…" : health?.demo_mode ? "Approve & simulate" : health?.execution_enabled ? "Approve & execute listed actions" : "Record approval"}
                </button>
                <div className="change-request-divider"><span>Or request changes</span></div>
                <label className="field" htmlFor="change-comment">
                  <span>What needs to change?</span>
                  <textarea id="change-comment" rows={3} value={changeComment} onChange={(event) => setChangeComment(event.target.value)} placeholder="Describe what should be reviewed again" disabled={Boolean(actionBusy)} />
                </label>
                <button className="button secondary full-button" onClick={() => void submitChanges()} disabled={changeComment.trim().length < 4 || Boolean(actionBusy)}>
                  {actionBusy === "changes" ? "Sending request…" : "Request changes"}
                </button>
                <p className="field-hint">The backend validates approval against this repository, version and action list.</p>
              </>
            ) : (
              <>
                <p className="approval-summary">
                  {session.approval?.approved
                    ? "An approval decision is recorded. See the audit timeline for action results."
                    : session.status === "rejected"
                      ? "Changes were requested. This session is closed for approval."
                      : session.status === "completed"
                        ? "The approved release actions are complete."
                        : "This session is not currently waiting for an approval decision."}
                </p>
                {session.approval?.comment ? <blockquote className="approval-note">{session.approval.comment}</blockquote> : null}
                {session.status === "failed" ? <button className="button secondary" onClick={() => void refresh(false)} disabled={refreshing}>Refresh session</button> : null}
              </>
            )}
            {actionError ? <p className="feedback error" role="alert">{actionError}</p> : null}
            {health?.demo_mode ? <p className="approval-mode-note">Demo mode: approvals simulate the listed actions and do not write to GitHub.</p> : health && !health.execution_enabled ? <p className="approval-mode-note">Backend execution is disabled; approval is recorded without running release writes.</p> : !health ? <p className="approval-mode-note">The backend mode could not be verified. Refresh before submitting an approval.</p> : null}
          </section>

          <section className="detail-card snapshot-card">
            <div className="panel-heading"><div><p className="eyebrow">Review snapshot</p><h2 className="panel-title">At a glance</h2></div></div>
            <ReleaseHighlights session={session} evidence={evidence} />
          </section>

          <section className="detail-card test-card" id="test-result">
            <div className="panel-heading">
              <div><p className="eyebrow">Verification</p><h2 className="panel-title">Test result</h2></div>
              <span className={`pill ${statusTone(testResult?.status)}`}>{prettyLabel(testResult?.status ?? "pending")}</span>
            </div>
            {testResult ? (
              <>
                <div className="test-result-heading"><strong>{testResult.command}</strong><span>{testResult.sandbox_provider}</span></div>
                <div className="test-metrics">
                  {testResult.passed_count !== null ? <div><span>Passed</span><strong>{testResult.passed_count}</strong></div> : null}
                  {testResult.failed_count !== null ? <div><span>Failed</span><strong>{testResult.failed_count}</strong></div> : null}
                  <div><span>Duration</span><strong>{testResult.duration_seconds.toFixed(2)}s</strong></div>
                  {testResult.status !== "unavailable" ? <div><span>Exit code</span><strong>{testResult.exit_code}</strong></div> : null}
                </div>
                {testResult.status === "unavailable" ? <p className="quiet-note">{testResult.log_excerpt}</p> : null}
                <details className="test-output-details">
                  <summary>{testResult.status === "unavailable" ? "Why tests were not run" : "Show captured test output"}</summary>
                  <pre className="test-output">{testResult.log_excerpt || "The test runner returned no output."}</pre>
                </details>
              </>
            ) : <p className="quiet-note">No test result was returned by the backend.</p>}
          </section>
        </aside>
      </section>
    </main>
  );
}

import type { BackendReleaseSession, ReleaseEvidence } from "../lib/release-captain-client";
import { getEvidenceCounts, statusTone } from "../lib/release-insights";

type ReleaseHighlightsProps = {
  session: BackendReleaseSession;
  evidence: ReleaseEvidence;
};

export function ReleaseHighlights({ session, evidence }: ReleaseHighlightsProps) {
  const counts = getEvidenceCounts(session, evidence);
  const plan = evidence.plan ?? session.plan;
  const testResult = evidence.test_result ?? session.test_result;
  const riskCount = plan?.risks.length ?? 0;
  const approvalLabel = session.status.replaceAll("_", " ");
  const testLabel = testResult?.status === "unavailable"
    ? "Tests unavailable"
    : testResult?.status
      ? `${testResult.passed_count ?? 0} passed`
      : "Pending";

  return (
    <section className="review-highlights">
      <article className="highlight-card">
        <div className="highlight-header">
          <p className="eyebrow">Recommendation</p>
          <span className={`pill ${plan ? (plan.bump === "major" ? "waiting" : "done") : "running"}`}>
            {plan?.bump ?? "Pending"}
          </span>
        </div>
        <strong className="highlight-value">{plan?.recommended_version ?? "Pending"}</strong>
        <p className="copy">{plan?.summary ?? "The backend has not produced a release plan yet."}</p>
      </article>

      <article className="highlight-card">
        <div className="highlight-header">
          <p className="eyebrow">Scope</p>
          <span className="pill">{counts.changedFiles} files</span>
        </div>
        <strong className="highlight-value">{counts.commits} commits · {counts.pullRequests} PRs</strong>
        <p className="copy">{counts.ciRuns} CI runs and backend evidence are attached to this review.</p>
      </article>

      <article className="highlight-card">
        <div className="highlight-header">
          <p className="eyebrow">Test result</p>
          <span className={`pill ${statusTone(testResult?.status)}`}>{testResult?.status ?? "Pending"}</span>
        </div>
        <strong className="highlight-value">{testLabel}</strong>
        <p className="copy">{(testResult?.command ?? session.test_command) || "No test command configured"}</p>
      </article>

      <article className="highlight-card">
        <div className="highlight-header">
          <p className="eyebrow">Approval checkpoint</p>
          <span className={`pill ${statusTone(session.status)}`}>{approvalLabel}</span>
        </div>
        <strong className="highlight-value">{riskCount ? `${riskCount} risk${riskCount === 1 ? "" : "s"} to review` : "No flagged risks"}</strong>
        <p className="copy">{session.status === "ready_for_approval" ? "The release is waiting for a human decision." : "Approval state is synced from the backend session."}</p>
      </article>
    </section>
  );
}

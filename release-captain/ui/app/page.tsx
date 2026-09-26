"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  createReleaseSession,
  fetchBackendHealth,
  fetchRepositoryMetadata,
  type BackendHealth,
  type RepositoryMetadata,
} from "../lib/release-captain-client";

const ALLOWED_TEST_COMMANDS = ["pytest", "python -m pytest", "npm test", "yarn test", "pnpm test"];

export default function HomePage() {
  const router = useRouter();
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [healthError, setHealthError] = useState("");
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [metadata, setMetadata] = useState<RepositoryMetadata | null>(null);
  const [branch, setBranch] = useState("");
  const [previousTag, setPreviousTag] = useState("");
  const [testCommand, setTestCommand] = useState("");
  const [inspecting, setInspecting] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    fetchBackendHealth()
      .then((result) => {
        if (mounted) {
          setHealth(result);
          setHealthError("");
        }
      })
      .catch((caughtError) => {
        if (mounted) setHealthError(caughtError instanceof Error ? caughtError.message : "Backend is unavailable.");
      });
    return () => {
      mounted = false;
    };
  }, []);

  async function inspectRepository() {
    if (!repositoryUrl.trim()) {
      setError("Enter a GitHub repository URL first.");
      return;
    }

    setInspecting(true);
    setError("");
    setMetadata(null);
    try {
      const result = await fetchRepositoryMetadata(repositoryUrl.trim());
      setMetadata(result);
      setBranch(result.default_branch);
      setPreviousTag("");
      setTestCommand(result.test_command);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not inspect this repository.");
    } finally {
      setInspecting(false);
    }
  }

  async function startReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!metadata) {
      setError("Inspect the repository before starting the release review.");
      return;
    }
    if (!ALLOWED_TEST_COMMANDS.includes(testCommand) && testCommand !== "") {
      setError("Choose an allowlisted test command or leave tests unconfigured.");
      return;
    }

    setStarting(true);
    setError("");
    try {
      const session = await createReleaseSession({ repositoryUrl: repositoryUrl.trim(), branch, previousTag, testCommand });
      router.push(`/session/${encodeURIComponent(session.id)}`);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not start the release review.");
    } finally {
      setStarting(false);
    }
  }

  return (
    <main className="shell home-shell">
      <header className="topbar session-topbar">
        <div className="workspace-copy">
          <p className="eyebrow">Release workspace</p>
          <strong className="session-title">Prepare a release review</strong>
          <p className="copy">Collect repository evidence, inspect the proposed version, then decide whether to approve the exact actions.</p>
        </div>
        <div className="status-chip-row home-status-row">
          <span className={`status-chip ${health ? "live" : healthError ? "warning" : ""}`}>
            {health ? "Backend connected" : healthError ? "Backend unavailable" : "Checking backend"}
          </span>
          {health ? <span className={`status-chip ${health.demo_mode ? "warning" : "live"}`}>{health.demo_mode ? "Demo data" : "GitHub evidence"}</span> : null}
        </div>
      </header>

      <section className="home-hero panel">
        <div>
          <p className="eyebrow">Release Captain</p>
          <h1 className="title">A release decision backed by evidence.</h1>
          <p className="subtitle">
            Review commits, pull requests, CI and test results in one place. Release actions stay paused until you approve the exact plan.
          </p>
        </div>
        <div className="home-hero-status">
          <span className="home-hero-status-label">Current environment</span>
          <strong>{health ? (health.demo_mode ? "Deterministic demo" : "Backend analysis") : "Connecting…"}</strong>
          <span>{health?.sandbox_enabled ? "Sandbox tests enabled" : "Test execution is disabled in this environment"}</span>
          {healthError ? <span className="feedback error" role="status">{healthError}</span> : null}
        </div>
      </section>

      <section className="home-grid">
        <form className="detail-card launch-form" onSubmit={startReview}>
          <div className="panel-heading">
            <div>
              <p className="eyebrow">01 / Repository</p>
              <h2 className="panel-title">Choose what to review</h2>
            </div>
            {metadata ? <span className={`pill ${metadata.source === "live" ? "done" : "waiting"}`}>{metadata.source === "live" ? "Live GitHub metadata" : "Demo metadata fallback"}</span> : null}
          </div>

          <div className="field">
            <label htmlFor="repository-url">GitHub repository URL</label>
            <div className="input-action-row">
              <input
                id="repository-url"
                name="repositoryUrl"
                type="url"
                placeholder="https://github.com/owner/repository"
                value={repositoryUrl}
                autoComplete="url"
                required
                onChange={(event) => {
                  setRepositoryUrl(event.target.value);
                  setMetadata(null);
                  setBranch("");
                  setPreviousTag("");
                  setTestCommand("");
                  setError("");
                }}
              />
              <button className="button secondary" type="button" onClick={inspectRepository} disabled={inspecting || starting || !health}>
                {inspecting ? "Inspecting…" : "Inspect repository"}
              </button>
            </div>
            <span className="field-hint">Branch, baseline tags, and the allowlisted test command are read from the repository by the backend when available.</span>
          </div>

          {metadata ? (
            <div className="form-option-grid">
              <div className="field field-wide">
                <span className="field-hint">
                  {metadata.source === "live"
                    ? `Loaded live repository metadata for ${metadata.repository_key}.`
                    : `Loaded demo fallback metadata for ${metadata.repository_key}. Check backend GitHub access if these branches or tags look generic.`}
                </span>
              </div>
              <div className="field">
                <label htmlFor="release-branch">Branch</label>
                <select id="release-branch" value={branch} onChange={(event) => setBranch(event.target.value)} required>
                  {metadata.branches.map((item) => <option value={item} key={item}>{item}{item === metadata.default_branch ? " · default" : ""}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor="release-baseline">Baseline</label>
                <select id="release-baseline" value={previousTag} onChange={(event) => setPreviousTag(event.target.value)}>
                  <option value="">
                    {branch !== metadata.default_branch
                      ? `Default branch (${metadata.default_branch})`
                      : metadata.tags[0]
                        ? `Latest tag (${metadata.tags[0]})`
                        : "Recent commits (no tag found)"}
                  </option>
                  {metadata.tags.map((tag) => <option value={tag} key={tag}>{tag}</option>)}
                </select>
              </div>
              <div className="field field-wide">
                <label htmlFor="test-command">Test command</label>
                <select id="test-command" value={testCommand} onChange={(event) => setTestCommand(event.target.value)}>
                  <option value="">No allowlisted command detected</option>
                  {ALLOWED_TEST_COMMANDS.map((command) => <option value={command} key={command}>{command}</option>)}
                </select>
                <span className="field-hint">{metadata.test_command_reason}</span>
              </div>
            </div>
          ) : null}

          {error ? <p className="feedback error" role="alert">{error}</p> : null}
          <div className="actions launch-actions">
            <button className="button primary" type="submit" disabled={!metadata || starting || inspecting || !health}>
              {starting ? "Analyzing release…" : "Start release review"}
            </button>
            <span className="field-hint">Analysis and test output will be stored in the backend session.</span>
          </div>
        </form>

        <aside className="detail-card workflow-card">
          <p className="eyebrow">What the backend collects</p>
          <h2 className="panel-title">A review you can verify</h2>
          <ol className="workflow-list">
            <li><span>01</span><div><strong>Repository changes</strong><p>Commits, merged pull requests, changed files, tags and recent CI.</p></div></li>
            <li><span>02</span><div><strong>Version recommendation</strong><p>Change categories, breaking-change risks and release notes.</p></div></li>
            <li><span>03</span><div><strong>Test evidence</strong><p>Allowlisted command, result, exit code, duration and captured output.</p></div></li>
            <li><span>04</span><div><strong>Human checkpoint</strong><p>Review the exact actions before anything can execute.</p></div></li>
          </ol>
          <div className="workflow-note">
            {health?.demo_mode
              ? "Demo mode uses deterministic evidence and never writes to GitHub."
              : health?.execution_enabled
                ? "Approved actions can run in this environment after an explicit confirmation."
                : "Real release actions are disabled in this backend environment."}
          </div>
        </aside>
      </section>
    </main>
  );
}

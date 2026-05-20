import { AlertOctagon, GitCompareArrows } from "lucide-react";

import type { FieldIssue, RunSample } from "../types";

function valueLabel(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "missing";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function issueReason(issue: FieldIssue): string {
  return issue.reason ?? issue.message ?? "field mismatch";
}

function expectedLabel(issue: FieldIssue): string {
  return issue.reason === "business rule mismatch" ? "Rule target" : "Expected";
}

interface CandidateDiffPaneProps {
  sample: RunSample | null;
}

export function CandidateDiffPane({ sample }: CandidateDiffPaneProps) {
  const blockingErrors = sample?.report?.blocking_errors ?? [];
  const qualityErrors = Array.isArray(sample?.report?.quality_errors) ? sample.report.quality_errors : [];
  const issues = blockingErrors.length > 0 ? blockingErrors : (qualityErrors as FieldIssue[]);

  return (
    <section className="pane diff-pane">
      <div className="pane-header">
        <div>
          <span className="pane-kicker">Review Check</span>
          <h2>{issues.length ? "Blocking Issues" : "Clean Sample"}</h2>
        </div>
        <GitCompareArrows size={18} />
      </div>

      {issues.length === 0 ? (
        <div className="empty-pane compact-empty-pane">No blocking differences for the selected sample.</div>
      ) : (
        <div className="diff-list">
          {issues.slice(0, 8).map((issue, index) => (
            <article className="diff-row" key={`${issue.field}-${index}`}>
              <div className="diff-title">
                <AlertOctagon size={15} />
                <strong>{issue.field || "unknown field"}</strong>
                <span>{issue.severity ?? "p0"}</span>
              </div>
              <p>{issueReason(issue)}</p>
              <div className="diff-values">
                <div>
                  <span>{expectedLabel(issue)}</span>
                  <code>{valueLabel(issue.expected)}</code>
                </div>
                <div>
                  <span>Actual</span>
                  <code>{valueLabel(issue.actual)}</code>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

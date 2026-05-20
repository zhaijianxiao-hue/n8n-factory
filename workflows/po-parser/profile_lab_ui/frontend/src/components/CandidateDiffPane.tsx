import { AlertOctagon, GitCompareArrows } from "lucide-react";

import { fieldMeta, issueReasonLabel, severityLabel } from "../labels";
import type { FieldIssue, RunSample } from "../types";

function valueLabel(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "缺失";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function issueReason(issue: FieldIssue): string {
  return issueReasonLabel(issue.reason ?? issue.message);
}

function expectedLabel(issue: FieldIssue): string {
  return issue.reason === "business rule mismatch" ? "规则目标" : "期望值";
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
          <span className="pane-kicker">复核检查</span>
          <h2>{issues.length ? "阻断问题" : "样本通过"}</h2>
        </div>
        <GitCompareArrows size={18} />
      </div>

      {issues.length === 0 ? (
        <div className="empty-pane compact-empty-pane">当前样本暂无阻断差异。</div>
      ) : (
        <div className="diff-list">
          {issues.slice(0, 8).map((issue, index) => {
            const meta = issue.field ? fieldMeta(issue.field) : null;
            return (
              <article className="diff-row" key={`${issue.field}-${index}`}>
                <div className="diff-title">
                  <AlertOctagon size={15} />
                  <strong>{meta ? `${meta.label}（${issue.field}）` : "未知字段"}</strong>
                  <span>{severityLabel(issue.severity)}</span>
                </div>
                <p>{issueReason(issue)}</p>
                <div className="diff-values">
                  <div>
                    <span>{expectedLabel(issue)}</span>
                    <code>{valueLabel(issue.expected)}</code>
                  </div>
                  <div>
                    <span>实际值</span>
                    <code>{valueLabel(issue.actual)}</code>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

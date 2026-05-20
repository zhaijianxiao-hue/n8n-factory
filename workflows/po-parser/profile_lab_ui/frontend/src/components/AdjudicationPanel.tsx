import { Bell, CheckCheck, ListChecks, ShieldX } from "lucide-react";

import type { ApprovalRecord, EvaluationSummary, RunSample } from "../types";

interface AdjudicationPanelProps {
  evaluation: EvaluationSummary | null;
  approval: ApprovalRecord | null;
  sample: RunSample | null;
}

export function AdjudicationPanel({ evaluation, approval, sample }: AdjudicationPanelProps) {
  const blockingErrors = sample?.report?.blocking_errors ?? [];
  const publishable = evaluation?.publishable === true;
  const notificationStatus = approval?.notification_status ?? "not sent";
  const recommendations =
    blockingErrors.length > 0
      ? blockingErrors.slice(0, 4).map((issue) => `Fix ${issue.field || "field"}: ${issue.reason ?? issue.message ?? "blocking mismatch"}`)
      : publishable
        ? ["P0 gate is clean for the selected evidence.", "Ready for admin approval once business submits."]
        : ["Review business rule score and sample coverage before approval."];

  return (
    <section className="pane adjudication-pane">
      <div className="pane-header">
        <div>
          <span className="pane-kicker">Run Guidance</span>
          <h2>Next Step</h2>
        </div>
        {publishable ? <CheckCheck size={18} /> : <ShieldX size={18} />}
      </div>

      <div className={`publishability ${publishable ? "publishable" : "not-publishable"}`}>
        <span>{publishable ? "Publishable" : "Needs review"}</span>
        <strong>{approval?.state ?? "draft"}</strong>
      </div>

      <div className="recommendation-list">
        {recommendations.map((recommendation, index) => (
          <div className="recommendation-row" key={`${recommendation}-${index}`}>
            <ListChecks size={15} />
            <span>{recommendation}</span>
          </div>
        ))}
      </div>

      <div className="notification-line">
        <Bell size={15} />
        <span>{notificationStatus}</span>
        {approval?.notification_error ? <code>{approval.notification_error}</code> : null}
      </div>
    </section>
  );
}

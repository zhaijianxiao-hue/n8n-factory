import { Bell, CheckCheck, ListChecks, ShieldX } from "lucide-react";

import { approvalStateLabel, fieldMeta, issueReasonLabel, notificationLabel } from "../labels";
import type { ApprovalRecord, EvaluationSummary, RunSample } from "../types";

interface AdjudicationPanelProps {
  evaluation: EvaluationSummary | null;
  approval: ApprovalRecord | null;
  sample: RunSample | null;
}

export function AdjudicationPanel({ evaluation, approval, sample }: AdjudicationPanelProps) {
  const blockingErrors = sample?.report?.blocking_errors ?? [];
  const publishable = evaluation?.publishable === true;
  const notificationStatus = notificationLabel(approval?.notification_status);
  const recommendations =
    blockingErrors.length > 0
      ? blockingErrors.slice(0, 4).map((issue) => {
          const meta = issue.field ? fieldMeta(issue.field) : null;
          return `请修正${meta?.label ?? "字段"}：${issueReasonLabel(issue.reason ?? issue.message)}`;
        })
      : publishable
        ? ["当前样本P0门禁已通过。", "业务提交后即可进入管理员审核。"]
        : ["上线前请复核业务规则分数和样本覆盖情况。"];

  return (
    <section className="pane adjudication-pane">
      <div className="pane-header">
        <div>
          <span className="pane-kicker">运行建议</span>
          <h2>下一步</h2>
        </div>
        {publishable ? <CheckCheck size={18} /> : <ShieldX size={18} />}
      </div>

      <div className={`publishability ${publishable ? "publishable" : "not-publishable"}`}>
        <span>{publishable ? "可上线" : "需复核"}</span>
        <strong>{approvalStateLabel(approval?.state)}</strong>
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

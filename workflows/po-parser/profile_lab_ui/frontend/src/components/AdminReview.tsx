import { Bell, ExternalLink, Inbox, Lock, ShieldAlert } from "lucide-react";

import { notificationLabel } from "../labels";
import type { CustomerSummary, RunSummary } from "../types";

interface AdminReviewProps {
  customers: CustomerSummary[];
  runs: RunSummary[];
  adminToken: string;
  onAdminTokenChange: (token: string) => void;
  onOpenRun: (customer: string, runId: string) => void;
}

function scorePercent(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return `${Math.round(value * 100)}%`;
}

function customerName(customers: CustomerSummary[], customerKey: string): string {
  return customers.find((customer) => customer.customer_key === customerKey)?.display_name || customerKey;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function AdminReview({ customers, runs, adminToken, onAdminTokenChange, onOpenRun }: AdminReviewProps) {
  const isUnlocked = adminToken.trim().length > 0;
  const submittedRuns = runs
    .filter((run) => run.approval?.state === "submitted")
    .sort((left, right) => (right.approval?.submitted_at ?? right.created_at ?? "").localeCompare(left.approval?.submitted_at ?? left.created_at ?? ""));

  return (
    <section className="admin-review-view" aria-label="管理员审核">
      <div className="console-panel review-queue-panel">
        <div className="panel-title">
          <span className="pane-kicker">管理员审核</span>
          <h2>等待批准的提交记录</h2>
        </div>

        {!isUnlocked ? (
          <div className="admin-lock-panel">
            <Lock size={18} />
            <div>
              <strong>需要管理员令牌</strong>
              <span>输入已配置的审核令牌后，才能执行批准和上线操作。</span>
            </div>
            <input
              aria-label="管理员令牌"
              autoComplete="off"
              placeholder="PO_PROFILE_LAB_ADMIN_TOKEN"
              type="password"
              value={adminToken}
              onChange={(event) => onAdminTokenChange(event.target.value)}
            />
          </div>
        ) : submittedRuns.length ? (
          <div className="admin-run-list">
            {submittedRuns.map((run) => (
              <article className="admin-run-card" key={`${run.customer}/${run.run_id}`}>
                <div className="admin-run-main">
                  <ShieldAlert size={17} />
                  <div>
                    <strong>{customerName(customers, run.customer)}</strong>
                    <code>{run.run_id}</code>
                  </div>
                </div>
                <dl className="admin-run-meta">
                  <div>
                    <dt>分数</dt>
                    <dd>{scorePercent(run.evaluation?.overall_score)}</dd>
                  </div>
                  <div>
                    <dt>样本</dt>
                    <dd>{run.sample_count}</dd>
                  </div>
                  <div>
                    <dt>通知</dt>
                    <dd>
                      <Bell size={13} />
                      {notificationLabel(run.approval?.notification_status)}
                    </dd>
                  </div>
                  <div>
                    <dt>提交时间</dt>
                    <dd>{formatDate(run.approval?.submitted_at ?? run.created_at)}</dd>
                  </div>
                </dl>
                <button type="button" className="open-run-button" onClick={() => onOpenRun(run.customer, run.run_id)}>
                  <ExternalLink size={15} />
                  <span>打开</span>
                </button>
              </article>
            ))}
          </div>
        ) : (
          <div className="compact-empty admin-empty">
            <Inbox size={18} />
            <span>暂无等待批准的提交记录。</span>
          </div>
        )}
      </div>
    </section>
  );
}

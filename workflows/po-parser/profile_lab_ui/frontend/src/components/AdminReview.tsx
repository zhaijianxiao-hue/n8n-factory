import { Bell, ExternalLink, Inbox, Lock, ShieldAlert } from "lucide-react";

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
    <section className="admin-review-view" aria-label="Admin Review">
      <div className="console-panel review-queue-panel">
        <div className="panel-title">
          <span className="pane-kicker">Admin Review</span>
          <h2>Submitted runs waiting for approval</h2>
        </div>

        {!isUnlocked ? (
          <div className="admin-lock-panel">
            <Lock size={18} />
            <div>
              <strong>Admin token required</strong>
              <span>Enter the configured review token to unlock approval and publish actions.</span>
            </div>
            <input
              aria-label="Admin token"
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
                    <dt>Score</dt>
                    <dd>{scorePercent(run.evaluation?.overall_score)}</dd>
                  </div>
                  <div>
                    <dt>Samples</dt>
                    <dd>{run.sample_count}</dd>
                  </div>
                  <div>
                    <dt>Notify</dt>
                    <dd>
                      <Bell size={13} />
                      {run.approval?.notification_status ?? "not sent"}
                    </dd>
                  </div>
                  <div>
                    <dt>Submitted</dt>
                    <dd>{formatDate(run.approval?.submitted_at ?? run.created_at)}</dd>
                  </div>
                </dl>
                <button type="button" className="open-run-button" onClick={() => onOpenRun(run.customer, run.run_id)}>
                  <ExternalLink size={15} />
                  <span>Open</span>
                </button>
              </article>
            ))}
          </div>
        ) : (
          <div className="compact-empty admin-empty">
            <Inbox size={18} />
            <span>No submitted runs are waiting for approval.</span>
          </div>
        )}
      </div>
    </section>
  );
}

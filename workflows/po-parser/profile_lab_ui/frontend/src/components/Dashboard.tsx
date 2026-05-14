import { AlertOctagon, Archive, CheckCircle2, Clock3, Database, Users } from "lucide-react";

import type { CustomerSummary, RunSummary } from "../types";

interface DashboardProps {
  customers: CustomerSummary[];
  runs: RunSummary[];
}

function scorePercent(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return `${Math.round(value * 100)}%`;
}

function runScore(run: RunSummary): number | null {
  return typeof run.evaluation?.overall_score === "number" ? run.evaluation.overall_score : null;
}

function hasP0Blockers(run: RunSummary): boolean {
  return (run.evaluation?.reports ?? []).some(
    (report) => report.p0_pass === false || (report.blocking_errors?.length ?? 0) > 0
  );
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

function customerName(customers: CustomerSummary[], customerKey: string): string {
  return customers.find((customer) => customer.customer_key === customerKey)?.display_name || customerKey;
}

export function Dashboard({ customers, runs }: DashboardProps) {
  const latestRuns = [...runs]
    .sort((left, right) => (right.created_at ?? "").localeCompare(left.created_at ?? ""))
    .slice(0, 8);
  const submittedCount = runs.filter((run) => run.approval?.state === "submitted").length;
  const publishedCount = runs.filter((run) => run.approval?.state === "published").length;
  const blockedCustomers = customers.filter((customer) =>
    runs.some((run) => run.customer === customer.customer_key && hasP0Blockers(run))
  );

  return (
    <section className="dashboard-view" aria-label="Dashboard">
      <div className="metric-grid">
        <div className="metric-card">
          <Users size={17} />
          <span>Customers</span>
          <strong>{customers.length}</strong>
        </div>
        <div className="metric-card">
          <Database size={17} />
          <span>Total Runs</span>
          <strong>{runs.length}</strong>
        </div>
        <div className="metric-card">
          <Clock3 size={17} />
          <span>Submitted</span>
          <strong>{submittedCount}</strong>
        </div>
        <div className="metric-card">
          <CheckCircle2 size={17} />
          <span>Published</span>
          <strong>{publishedCount}</strong>
        </div>
      </div>

      <div className="dashboard-grid">
        <section className="console-panel latest-runs-panel">
          <div className="panel-title">
            <span className="pane-kicker">Latest Runs</span>
            <h2>Recent profile lab output</h2>
          </div>
          <div className="run-table">
            {latestRuns.length ? (
              latestRuns.map((run) => (
                <div className="run-row" key={`${run.customer}/${run.run_id}`}>
                  <span>{customerName(customers, run.customer)}</span>
                  <code>{run.run_id}</code>
                  <strong>{scorePercent(runScore(run))}</strong>
                  <span>{run.sample_count} samples</span>
                  <span className={`state-pill state-${run.approval?.state ?? "draft"}`}>{run.approval?.state ?? "draft"}</span>
                  <time>{formatDate(run.created_at)}</time>
                </div>
              ))
            ) : (
              <div className="compact-empty">
                <Archive size={16} />
                <span>No runs loaded.</span>
              </div>
            )}
          </div>
        </section>

        <section className="console-panel blockers-panel">
          <div className="panel-title">
            <span className="pane-kicker">P0 Blockers</span>
            <h2>Customers requiring correction</h2>
          </div>
          <div className="blocker-list">
            {blockedCustomers.length ? (
              blockedCustomers.map((customer) => {
                const count = runs.filter((run) => run.customer === customer.customer_key && hasP0Blockers(run)).length;
                return (
                  <div className="blocker-row" key={customer.customer_key}>
                    <AlertOctagon size={16} />
                    <span>{customer.display_name || customer.customer_key}</span>
                    <strong>{count}</strong>
                  </div>
                );
              })
            ) : (
              <div className="compact-empty">
                <CheckCircle2 size={16} />
                <span>No blocking P0 issues.</span>
              </div>
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

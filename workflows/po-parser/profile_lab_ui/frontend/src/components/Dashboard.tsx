import { AlertOctagon, Archive, CheckCircle2, Clock3, Database, Users } from "lucide-react";

import { approvalStateLabel } from "../labels";
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
    <section className="dashboard-view" aria-label="看板">
      <div className="metric-grid">
        <div className="metric-card">
          <Users size={17} />
          <span>客户数</span>
          <strong>{customers.length}</strong>
        </div>
        <div className="metric-card">
          <Database size={17} />
          <span>运行总数</span>
          <strong>{runs.length}</strong>
        </div>
        <div className="metric-card">
          <Clock3 size={17} />
          <span>待审核</span>
          <strong>{submittedCount}</strong>
        </div>
        <div className="metric-card">
          <CheckCircle2 size={17} />
          <span>已上线</span>
          <strong>{publishedCount}</strong>
        </div>
      </div>

      <div className="dashboard-grid">
        <section className="console-panel latest-runs-panel">
          <div className="panel-title">
            <span className="pane-kicker">最新运行</span>
            <h2>最近的客户解析档案结果</h2>
          </div>
          <div className="run-table">
            {latestRuns.length ? (
              latestRuns.map((run) => (
                <div className="run-row" key={`${run.customer}/${run.run_id}`}>
                  <span>{customerName(customers, run.customer)}</span>
                  <code>{run.run_id}</code>
                  <strong>{scorePercent(runScore(run))}</strong>
                  <span>{run.sample_count} 个样本</span>
                  <span className={`state-pill state-${run.approval?.state ?? "draft"}`}>{approvalStateLabel(run.approval?.state)}</span>
                  <time>{formatDate(run.created_at)}</time>
                </div>
              ))
            ) : (
              <div className="compact-empty">
                <Archive size={16} />
                <span>暂无运行记录。</span>
              </div>
            )}
          </div>
        </section>

        <section className="console-panel blockers-panel">
          <div className="panel-title">
            <span className="pane-kicker">P0阻断</span>
            <h2>需要纠错的客户</h2>
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
                <span>暂无P0阻断问题。</span>
              </div>
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

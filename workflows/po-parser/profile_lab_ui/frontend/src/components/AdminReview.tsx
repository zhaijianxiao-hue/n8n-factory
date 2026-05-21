import { Bell, ExternalLink, Inbox, Lock, ShieldAlert, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { approvalStateLabel, notificationLabel } from "../labels";
import type { ApprovalState, CustomerSummary, RunSummary } from "../types";

interface AdminReviewProps {
  customers: CustomerSummary[];
  runs: RunSummary[];
  adminToken: string;
  onAdminTokenChange: (token: string) => void;
  onOpenRun: (customer: string, runId: string) => void;
  onDeleteRun: (customer: string, runId: string) => Promise<void>;
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

const FILTERS: Array<{ key: "all" | ApprovalState; label: string }> = [
  { key: "submitted", label: "待审核" },
  { key: "draft", label: "草稿" },
  { key: "generated", label: "已生成" },
  { key: "evaluated", label: "已评测" },
  { key: "changes_requested", label: "已驳回" },
  { key: "approved", label: "已批准" },
  { key: "published", label: "已上线" },
  { key: "all", label: "全部" }
];

export function AdminReview({ customers, runs, adminToken, onAdminTokenChange, onOpenRun, onDeleteRun }: AdminReviewProps) {
  const [statusFilter, setStatusFilter] = useState<"all" | ApprovalState>("submitted");
  const isUnlocked = adminToken.trim().length > 0;
  const runCounts = useMemo(
    () =>
      runs.reduce<Record<string, number>>(
        (counts, run) => {
          const state = run.approval?.state ?? "draft";
          counts[state] = (counts[state] ?? 0) + 1;
          counts.all += 1;
          return counts;
        },
        { all: 0 }
      ),
    [runs]
  );
  const visibleRuns = runs
    .filter((run) => statusFilter === "all" || run.approval?.state === statusFilter)
    .sort((left, right) => (right.approval?.submitted_at ?? right.created_at ?? "").localeCompare(left.approval?.submitted_at ?? left.created_at ?? ""));
  const activeFilterLabel = FILTERS.find((filter) => filter.key === statusFilter)?.label ?? "记录";

  return (
    <section className="admin-review-view" aria-label="管理员审核">
      <div className="console-panel review-queue-panel">
        <div className="panel-title">
          <span className="pane-kicker">管理员审核</span>
          <h2>{activeFilterLabel}记录</h2>
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
        ) : (
          <>
            <div className="admin-filter-bar" aria-label="审核状态筛选">
              {FILTERS.map((filter) => (
                <button
                  className={statusFilter === filter.key ? "active" : ""}
                  key={filter.key}
                  type="button"
                  onClick={() => setStatusFilter(filter.key)}
                >
                  <span>{filter.label}</span>
                  <strong>{runCounts[filter.key] ?? 0}</strong>
                </button>
              ))}
            </div>

            {visibleRuns.length ? (
              <div className="admin-run-list">
                {visibleRuns.map((run) => (
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
                        <dt>状态</dt>
                        <dd>
                          <span className={`state-pill state-${run.approval?.state ?? "draft"}`}>{approvalStateLabel(run.approval?.state)}</span>
                        </dd>
                      </div>
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
                    <div className="admin-run-actions">
                      <button type="button" className="open-run-button" onClick={() => onOpenRun(run.customer, run.run_id)}>
                        <ExternalLink size={15} />
                        <span>打开</span>
                      </button>
                      <button
                        type="button"
                        className="delete-run-button"
                        onClick={() => {
                          if (window.confirm(`确认删除运行批次 ${run.run_id}？`)) {
                            void onDeleteRun(run.customer, run.run_id);
                          }
                        }}
                      >
                        <Trash2 size={15} />
                        <span>删除</span>
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="compact-empty admin-empty">
                <Inbox size={18} />
                <span>当前筛选条件下暂无运行记录。</span>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

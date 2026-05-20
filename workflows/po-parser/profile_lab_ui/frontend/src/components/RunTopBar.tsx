import { Activity, GitBranch, ShieldCheck } from "lucide-react";

import { approvalStateLabel } from "../labels";
import type { ApprovalRecord, CustomerSummary, RunSummary } from "../types";

interface RunTopBarProps {
  customers: CustomerSummary[];
  runs: RunSummary[];
  selectedCustomer: string;
  selectedRunId: string;
  approval: ApprovalRecord | null;
  onCustomerChange: (customer: string) => void;
  onRunChange: (runId: string) => void;
}

export function RunTopBar({
  customers,
  runs,
  selectedCustomer,
  selectedRunId,
  approval,
  onCustomerChange,
  onRunChange
}: RunTopBarProps) {
  return (
    <header className="run-topbar">
      <div className="brand-lockup">
        <span className="eyebrow">先审核后上线</span>
        <h1>PO解析实验室</h1>
      </div>

      <div className="topbar-controls" aria-label="运行上下文">
        <label className="control-field">
          <span>客户</span>
          <select value={selectedCustomer} onChange={(event) => onCustomerChange(event.target.value)}>
            {customers.map((customer) => (
              <option key={customer.customer_key} value={customer.customer_key}>
                {customer.display_name || customer.customer_key}
              </option>
            ))}
          </select>
        </label>

        <label className="control-field">
          <span>运行批次</span>
          <select value={selectedRunId} onChange={(event) => onRunChange(event.target.value)}>
            {runs.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.run_id}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="topbar-state">
        <div className={`state-chip state-${approval?.state ?? "draft"}`}>
          <ShieldCheck size={16} />
          <span>{approvalStateLabel(approval?.state)}</span>
        </div>
        <div className="action-hints">
          <span>
            <Activity size={14} />
            审核
          </span>
          <span>
            <GitBranch size={14} />
            右侧门禁
          </span>
        </div>
      </div>
    </header>
  );
}

import { Activity, GitBranch, ShieldCheck } from "lucide-react";

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
        <span className="eyebrow">REVIEW FIRST</span>
        <h1>PO Profile Lab</h1>
      </div>

      <div className="topbar-controls" aria-label="Run context">
        <label className="control-field">
          <span>Customer</span>
          <select value={selectedCustomer} onChange={(event) => onCustomerChange(event.target.value)}>
            {customers.map((customer) => (
              <option key={customer.customer_key} value={customer.customer_key}>
                {customer.display_name || customer.customer_key}
              </option>
            ))}
          </select>
        </label>

        <label className="control-field">
          <span>Run</span>
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
          <span>{approval?.state ?? "draft"}</span>
        </div>
        <div className="action-hints">
          <span>
            <Activity size={14} />
            Review
          </span>
          <span>
            <GitBranch size={14} />
            Gate in panel
          </span>
        </div>
      </div>
    </header>
  );
}

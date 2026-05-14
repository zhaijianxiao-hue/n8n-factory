import { Check, Rocket, Send, X } from "lucide-react";
import { useState } from "react";

import { api } from "../api";
import type { ApprovalRecord } from "../types";

interface ApprovalGateProps {
  customer: string;
  runId: string;
  approval: ApprovalRecord | null;
  mode: "business" | "admin";
  adminToken: string;
  onReload: () => Promise<void>;
}

type ActionName = "submit" | "approve" | "reject" | "publish";

export function ApprovalGate({ customer, runId, approval, mode, adminToken, onReload }: ApprovalGateProps) {
  const [busyAction, setBusyAction] = useState<ActionName | null>(null);
  const [error, setError] = useState("");

  async function runAction(action: ActionName) {
    setBusyAction(action);
    setError("");
    try {
      if (action === "submit") {
        await api.submit(customer, runId, "business", "ready for admin review");
      } else if (action === "approve") {
        await api.approve(customer, runId, adminToken, "admin", "approved in review workbench");
      } else if (action === "reject") {
        await api.reject(customer, runId, adminToken, "admin", "changes requested in review workbench");
      } else {
        await api.publish(customer, runId, adminToken);
      }
      await onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusyAction(null);
    }
  }

  const isAdminMode = mode === "admin";
  const hasAdminToken = adminToken.trim().length > 0;
  const adminActionDisabled = !isAdminMode || !hasAdminToken || busyAction !== null;
  const publishDisabled = adminActionDisabled || approval?.state !== "approved";
  const actionDisabled = busyAction !== null;

  return (
    <section className="pane approval-gate">
      <div className="pane-header">
        <div>
          <span className="pane-kicker">{isAdminMode ? "Admin Gate" : "Business Gate"}</span>
          <h2>{approval?.state ?? "draft"}</h2>
        </div>
        <Rocket size={18} />
      </div>

      <div className="gate-actions">
        <button type="button" onClick={() => runAction("submit")} disabled={isAdminMode || actionDisabled} title="Submit">
          <Send size={16} />
          <span>{busyAction === "submit" ? "Submitting" : "Submit"}</span>
        </button>
        <button type="button" onClick={() => runAction("approve")} disabled={adminActionDisabled} title="Approve">
          <Check size={16} />
          <span>{busyAction === "approve" ? "Approving" : "Approve"}</span>
        </button>
        <button type="button" onClick={() => runAction("reject")} disabled={adminActionDisabled} title="Reject">
          <X size={16} />
          <span>{busyAction === "reject" ? "Rejecting" : "Reject"}</span>
        </button>
        <button type="button" className="publish-button" onClick={() => runAction("publish")} disabled={publishDisabled} title="Publish">
          <Rocket size={16} />
          <span>{busyAction === "publish" ? "Publishing" : "Publish"}</span>
        </button>
      </div>

      {error ? <div className="gate-error">{error}</div> : null}
      <div className="gate-meta">
        <span>{isAdminMode && hasAdminToken ? "admin token present" : "business submission mode"}</span>
        <span>{approval?.admin_decision ?? "no admin decision"}</span>
      </div>
    </section>
  );
}

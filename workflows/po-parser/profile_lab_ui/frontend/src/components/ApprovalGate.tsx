import { BadgeCheck, Check, Rocket, Send, X } from "lucide-react";
import { useState } from "react";

import { api } from "../api";
import { adminDecisionLabel, approvalStateLabel } from "../labels";
import type { ApprovalRecord } from "../types";

interface ApprovalGateProps {
  customer: string;
  runId: string;
  approval: ApprovalRecord | null;
  mode: "business" | "admin";
  adminToken: string;
  sampleKey: string;
  requiresExpectedConfirmation: boolean;
  onReload: () => Promise<void>;
}

type ActionName = "confirm" | "submit" | "approve" | "reject" | "publish";

export function ApprovalGate({
  customer,
  runId,
  approval,
  mode,
  adminToken,
  sampleKey,
  requiresExpectedConfirmation,
  onReload
}: ApprovalGateProps) {
  const [busyAction, setBusyAction] = useState<ActionName | null>(null);
  const [error, setError] = useState("");

  async function runAction(action: ActionName) {
    setBusyAction(action);
    setError("");
    try {
      if (action === "confirm") {
        await api.confirmExpected(customer, runId, sampleKey);
      } else if (action === "submit") {
        await api.submit(customer, runId, "business", "业务已确认，提交管理员审核");
      } else if (action === "approve") {
        await api.approve(customer, runId, adminToken, "admin", "管理员在审核工作台批准");
      } else if (action === "reject") {
        await api.reject(customer, runId, adminToken, "admin", "管理员要求继续修改");
      } else {
        await api.publish(customer, runId, adminToken);
      }
      await onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusyAction(null);
    }
  }

  const isAdminMode = mode === "admin";
  const hasAdminToken = adminToken.trim().length > 0;
  const adminActionDisabled = !isAdminMode || !hasAdminToken || busyAction !== null;
  const publishDisabled = adminActionDisabled || approval?.state !== "approved";
  const actionDisabled = busyAction !== null;
  const submitDisabled = isAdminMode || actionDisabled || requiresExpectedConfirmation;
  const confirmDisabled = isAdminMode || actionDisabled || !sampleKey;

  return (
    <section className="pane approval-gate">
      <div className="pane-header">
        <div>
          <span className="pane-kicker">{isAdminMode ? "管理员审核" : "审核门禁"}</span>
          <h2>{approvalStateLabel(approval?.state)}</h2>
        </div>
        <Rocket size={18} />
      </div>

      <button
        type="button"
        className="confirm-expected-button"
        onClick={() => runAction("confirm")}
        disabled={confirmDisabled}
        title="确认当前样本为标准答案"
      >
        <BadgeCheck size={16} />
        <span>{busyAction === "confirm" ? "确认中" : "确认标准答案"}</span>
      </button>

      <div className="gate-actions">
        <button type="button" onClick={() => runAction("submit")} disabled={submitDisabled} title="提交管理员审核">
          <Send size={16} />
          <span>{busyAction === "submit" ? "提交中" : "提交审核"}</span>
        </button>
        <button type="button" onClick={() => runAction("approve")} disabled={adminActionDisabled} title="管理员批准">
          <Check size={16} />
          <span>{busyAction === "approve" ? "批准中" : "批准"}</span>
        </button>
        <button type="button" onClick={() => runAction("reject")} disabled={adminActionDisabled} title="管理员驳回">
          <X size={16} />
          <span>{busyAction === "reject" ? "驳回中" : "驳回"}</span>
        </button>
        <button type="button" className="publish-button" onClick={() => runAction("publish")} disabled={publishDisabled} title="上线自动化使用">
          <Rocket size={16} />
          <span>{busyAction === "publish" ? "上线中" : "上线"}</span>
        </button>
      </div>

      {error ? <div className="gate-error">{error}</div> : null}
      <div className="gate-meta">
        <span>
          {requiresExpectedConfirmation
            ? "提交前需先确认标准答案"
            : isAdminMode && hasAdminToken
              ? "管理员令牌已输入"
              : "业务提交模式"}
        </span>
        <span>{adminDecisionLabel(approval?.admin_decision)}</span>
      </div>
    </section>
  );
}

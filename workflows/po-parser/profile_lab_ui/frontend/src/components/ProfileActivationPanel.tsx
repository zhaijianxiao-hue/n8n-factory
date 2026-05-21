import { AlertTriangle, BadgeCheck, CheckCircle2, Plus, Save, Tags, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import type { ApprovalRecord, ProfileStatus, RunSample } from "../types";

interface ProfileActivationPanelProps {
  customer: string;
  displayName: string;
  adminToken: string;
  approval: ApprovalRecord | null;
  profileStatus: ProfileStatus | null;
  sample: RunSample | null;
  onProfileChange: (profile: ProfileStatus) => void;
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeMarkers(markers: string[]): string[] {
  const seen = new Set<string>();
  return markers
    .map((marker) => marker.trim())
    .filter((marker) => {
      if (!marker || seen.has(marker)) {
        return false;
      }
      seen.add(marker);
      return true;
    });
}

function suggestedMarkers(customer: string, displayName: string, sample: RunSample | null): string[] {
  const draft = sample?.merged_draft ?? {};
  const header = typeof draft.header === "object" && draft.header !== null ? (draft.header as Record<string, unknown>) : {};
  const email = stringValue(header.customer_contact_email);
  const domain = email.includes("@") ? email.split("@").pop() ?? "" : "";
  return normalizeMarkers([
    displayName,
    customer,
    stringValue(header.customer_name),
    stringValue(header.supplier_name),
    domain,
    sample?.source_file?.replace(/\.pdf$/i, "") ?? ""
  ]);
}

export function ProfileActivationPanel({
  customer,
  displayName,
  adminToken,
  approval,
  profileStatus,
  sample,
  onProfileChange
}: ProfileActivationPanelProps) {
  const [markerText, setMarkerText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setMarkerText((profileStatus?.markers ?? []).join("\n"));
  }, [profileStatus?.markers]);

  const markers = useMemo(() => normalizeMarkers(markerText.split(/\r?\n/)), [markerText]);
  const suggestions = useMemo(
    () => suggestedMarkers(customer, displayName, sample).filter((marker) => !markers.includes(marker)),
    [customer, displayName, markers, sample]
  );
  const hasAdminToken = adminToken.trim().length > 0;
  const canSave = hasAdminToken && markers.length > 0 && !busy;
  const isPublished = approval?.state === "published" || profileStatus?.runtime_ready;
  const hasMarkers = markers.length > 0;
  const activationTitle = profileStatus?.runtime_ready ? "生产已接入" : hasMarkers ? "等待上线发布" : "待补齐识别标识";

  function addMarker(marker: string) {
    setMarkerText(normalizeMarkers([...markers, marker]).join("\n"));
  }

  async function saveMarkers() {
    if (!canSave) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const nextProfile = await api.updateProfileMarkers(customer, adminToken, markers);
      onProfileChange(nextProfile);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存识别标识失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="pane profile-activation-pane">
      <div className="pane-header">
        <div>
          <span className="pane-kicker">上线资源</span>
          <h2>{activationTitle}</h2>
        </div>
        {profileStatus?.runtime_ready ? <CheckCircle2 size={18} /> : <Tags size={18} />}
      </div>

      <div className={`activation-status ${profileStatus?.runtime_ready ? "ready" : "not-ready"}`}>
        <div>
          <span>{isPublished ? "上线状态" : "准备状态"}</span>
          <strong>{profileStatus?.production_exists ? "生产 Profile 已生成" : "尚未生成生产 Profile"}</strong>
        </div>
        {profileStatus?.runtime_ready ? <BadgeCheck size={18} /> : <AlertTriangle size={18} />}
      </div>

      <label className="marker-editor">
        <span>客户识别标识</span>
        <textarea
          value={markerText}
          onChange={(event) => setMarkerText(event.target.value)}
          placeholder="每行一个稳定出现在客户PO里的文字，例如客户全称、邮箱域名、固定抬头"
        />
      </label>

      <div className="marker-suggestions" aria-label="建议识别标识">
        {suggestions.slice(0, 5).map((marker) => (
          <button type="button" key={marker} onClick={() => addMarker(marker)}>
            <Plus size={14} />
            <span>{marker}</span>
          </button>
        ))}
      </div>

      <button type="button" className="save-markers-button" onClick={saveMarkers} disabled={!canSave}>
        <Save size={16} />
        <span>{busy ? "保存中" : "保存识别标识"}</span>
      </button>

      {error ? (
        <div className="gate-error">
          <X size={14} />
          <span>{error}</span>
        </div>
      ) : null}

      <div className="activation-footnote">
        <span>{hasAdminToken ? "管理员令牌已输入" : "保存识别标识需要管理员令牌"}</span>
        <span>
          {profileStatus?.runtime_ready
            ? "新PDF会按此客户 Profile 识别"
            : hasMarkers
              ? "识别标识已维护，发布后进入正式解析"
              : "上线前至少维护 1 个稳定标识"}
        </span>
      </div>
    </section>
  );
}

import { CheckCircle2, Circle, FileUp, Loader2, Play, Plus, UserPlus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../api";

interface RunComposerProps {
  selectedCustomer: string;
  mode?: "all" | "customer" | "sample" | "run";
  onCustomerCreated: (customer: string) => Promise<void>;
  onSampleUploaded: (filename: string) => Promise<void>;
  onRunCreated: (runId: string) => Promise<void>;
}

const DRAFT_STEPS = [
  "确认客户样本",
  "读取 PDF 页面",
  "生成文本候选 JSON",
  "生成视觉候选 JSON",
  "合并字段草稿",
  "执行评测门禁",
  "写入运行批次"
];
const DEFAULT_TEXT_MODEL = "DeepSeek-V4-Pro";
const DEFAULT_VISION_MODEL = "Qwen3.5-27B";

function defaultRunId(): string {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  const hh = String(now.getHours()).padStart(2, "0");
  const mi = String(now.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}-${hh}${mi}`;
}

export function RunComposer({ selectedCustomer, mode = "all", onCustomerCreated, onSampleUploaded, onRunCreated }: RunComposerProps) {
  const [customerKey, setCustomerKey] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [sampleFile, setSampleFile] = useState<File | null>(null);
  const [runId, setRunId] = useState(defaultRunId);
  const [textModel, setTextModel] = useState(DEFAULT_TEXT_MODEL);
  const [visionModel, setVisionModel] = useState(DEFAULT_VISION_MODEL);
  const [busy, setBusy] = useState<"customer" | "sample" | "run" | null>(null);
  const [draftStepIndex, setDraftStepIndex] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const canUpload = useMemo(() => Boolean(selectedCustomer && sampleFile && !busy), [busy, sampleFile, selectedCustomer]);
  const canCreateRun = useMemo(() => Boolean(selectedCustomer && runId.trim() && !busy), [busy, runId, selectedCustomer]);

  useEffect(() => {
    if (busy !== "run") {
      setDraftStepIndex(0);
      return;
    }
    setDraftStepIndex(0);
    const timer = window.setInterval(() => {
      setDraftStepIndex((current) => Math.min(current + 1, DRAFT_STEPS.length - 1));
    }, 1400);
    return () => window.clearInterval(timer);
  }, [busy]);

  async function createCustomer() {
    if (!customerKey.trim()) {
      return;
    }
    setBusy("customer");
    setMessage("");
    setError("");
    try {
      const customer = await api.createCustomer(customerKey.trim(), displayName.trim() || customerKey.trim());
      setCustomerKey("");
      setDisplayName("");
      setMessage(`已创建客户：${customer.display_name || customer.customer_key}`);
      await onCustomerCreated(customer.customer_key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建客户失败");
    } finally {
      setBusy(null);
    }
  }

  async function uploadSample() {
    if (!sampleFile || !selectedCustomer) {
      return;
    }
    setBusy("sample");
    setMessage("");
    setError("");
    try {
      const uploaded = await api.uploadSample(selectedCustomer, sampleFile);
      setSampleFile(null);
      setMessage(`已上传样本：${uploaded.filename}`);
      await onSampleUploaded(uploaded.filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传样本失败");
    } finally {
      setBusy(null);
    }
  }

  async function createRun() {
    if (!selectedCustomer || !runId.trim()) {
      return;
    }
    setBusy("run");
    setMessage("");
    setError("");
    try {
      const run = await api.createRun(selectedCustomer, runId.trim(), textModel.trim(), visionModel.trim());
      setRunId(defaultRunId());
      setMessage(`已生成运行批次：${run.manifest.run_id ?? runId.trim()}`);
      await onRunCreated(String(run.manifest.run_id ?? runId.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成运行失败");
    } finally {
      setBusy(null);
    }
  }

  const showCustomer = mode === "all" || mode === "customer";
  const showSample = mode === "all" || mode === "sample";
  const showRun = mode === "all" || mode === "run";

  return (
    <section className={`run-composer ${mode === "all" ? "" : "single"}`} aria-label="新建客户与运行">
      {showCustomer ? (
        <div className="composer-card">
          <div className="composer-title">
            <UserPlus size={17} />
            <span>新客户</span>
          </div>
          <input value={customerKey} onChange={(event) => setCustomerKey(event.target.value)} placeholder="客户代码，例如 wanji" />
          <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="显示名称，例如 武汉万集" />
          <button type="button" onClick={createCustomer} disabled={!customerKey.trim() || busy !== null}>
            <Plus size={15} />
            <span>{busy === "customer" ? "创建中" : "创建客户"}</span>
          </button>
        </div>
      ) : null}

      {showSample ? (
        <div className="composer-card">
          <div className="composer-title">
            <FileUp size={17} />
            <span>样本 PDF</span>
          </div>
          <input type="file" accept="application/pdf,.pdf" onChange={(event) => setSampleFile(event.target.files?.[0] ?? null)} />
          <button type="button" onClick={uploadSample} disabled={!canUpload}>
            <FileUp size={15} />
            <span>{busy === "sample" ? "上传中" : "上传样本"}</span>
          </button>
        </div>
      ) : null}

      {showRun ? (
        <div className="composer-card composer-run-card">
          <div className="composer-title">
            <Play size={17} />
            <span>生成运行</span>
          </div>
          <input value={runId} onChange={(event) => setRunId(event.target.value)} placeholder="运行批次" />
          <input value={textModel} onChange={(event) => setTextModel(event.target.value)} placeholder="文本模型" />
          <input value={visionModel} onChange={(event) => setVisionModel(event.target.value)} placeholder="视觉模型" />
          <button type="button" onClick={createRun} disabled={!canCreateRun}>
            <Play size={15} />
            <span>{busy === "run" ? "生成中" : "生成并评测"}</span>
          </button>
        </div>
      ) : null}

      {showRun ? (
        <div className={`draft-progress-card ${busy === "run" ? "running" : ""}`} aria-live="polite">
          <div className="draft-progress-head">
            <span>{busy === "run" ? "解析作业进行中" : "生成前检查清单"}</span>
            <strong>{busy === "run" ? `${draftStepIndex + 1}/${DRAFT_STEPS.length}` : "待开始"}</strong>
          </div>
          <ol className="draft-todo-list">
            {DRAFT_STEPS.map((step, index) => {
              const done = busy === "run" && index < draftStepIndex;
              const active = busy === "run" && index === draftStepIndex;
              return (
                <li className={done ? "done" : active ? "active" : ""} key={step}>
                  {done ? <CheckCircle2 size={16} /> : active ? <Loader2 size={16} className="spin" /> : <Circle size={16} />}
                  <span>{step}</span>
                </li>
              );
            })}
          </ol>
        </div>
      ) : null}

      {(message || error) && <div className={error ? "composer-message composer-error" : "composer-message"}>{error || message}</div>}
    </section>
  );
}

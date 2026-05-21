import { AlertTriangle, ArrowRight, BarChart3, ClipboardCheck, FileText, Loader2, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "./api";
import { AdjudicationPanel } from "./components/AdjudicationPanel";
import { AdminReview } from "./components/AdminReview";
import { ApprovalGate } from "./components/ApprovalGate";
import { CandidateDiffPane } from "./components/CandidateDiffPane";
import { Dashboard } from "./components/Dashboard";
import { JobProgress, type PipelineStage } from "./components/JobProgress";
import { PdfEvidencePane } from "./components/PdfEvidencePane";
import { ProfileActivationPanel } from "./components/ProfileActivationPanel";
import { RunComposer } from "./components/RunComposer";
import { RunTopBar } from "./components/RunTopBar";
import { ScoreStrip } from "./components/ScoreStrip";
import { StandardJsonPane } from "./components/StandardJsonPane";
import type { CustomerSummary, ProfileStatus, RunDetail, RunSample, RunSummary } from "./types";

type LoadState = "loading" | "ready" | "empty" | "error";
type AppView = "workbench" | "dashboard" | "admin";
type PipelineStageId = "setup" | "upload" | "draft" | "review" | "evaluate" | "submit" | "admin" | "publish";
const ADMIN_TOKEN_STORAGE_KEY = "po-profile-lab-admin-token";

function latestRunId(runs: RunSummary[]): string {
  return runs[0]?.run_id ?? "";
}

function approvalReached(state: string | undefined, targets: string[]): boolean {
  return targets.includes(state ?? "");
}

export default function App() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [allRuns, setAllRuns] = useState<RunSummary[]>([]);
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);
  const [profileStatus, setProfileStatus] = useState<ProfileStatus | null>(null);
  const [selectedCustomer, setSelectedCustomer] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedSampleKey, setSelectedSampleKey] = useState("");
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [uploadedSampleNames, setUploadedSampleNames] = useState<string[]>([]);
  const [activeView, setActiveView] = useState<AppView>("workbench");
  const [activeStageId, setActiveStageId] = useState<PipelineStageId>("setup");
  const [adminToken, setAdminToken] = useState(() => window.sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) ?? "");

  const selectedSample = useMemo<RunSample | null>(() => {
    if (!runDetail?.samples.length) {
      return null;
    }
    return runDetail.samples.find((sample) => sample.sample_key === selectedSampleKey) ?? runDetail.samples[0];
  }, [runDetail, selectedSampleKey]);

  const requiresExpectedConfirmation = useMemo(
    () => runDetail?.evaluation.reports?.some((report) => report.expected_missing) ?? false,
    [runDetail]
  );

  const selectedSampleHasBlockingErrors = (selectedSample?.report?.blocking_errors?.length ?? 0) > 0;
  const isPublishable = runDetail?.evaluation.publishable === true;
  const approvalState = runDetail?.approval.state;
  const hasRuntimeProfile = profileStatus?.runtime_ready === true;
  const selectedCustomerRecord = useMemo(
    () => customers.find((customer) => customer.customer_key === selectedCustomer),
    [customers, selectedCustomer]
  );
  const sampleCount = runDetail?.samples.length ?? 0;
  const stagedSampleCount = selectedCustomerRecord?.sample_count ?? 0;
  const availableSampleCount = Math.max(sampleCount, stagedSampleCount, uploadedSampleNames.length);

  const selectedCustomerDisplayName = useMemo(
    () => selectedCustomerRecord?.display_name || selectedCustomer,
    [selectedCustomer, selectedCustomerRecord]
  );

  const currentStageId = useMemo<PipelineStageId>(() => {
    if (!selectedCustomer) {
      return "setup";
    }
    if (!selectedRunId || !runDetail) {
      return "upload";
    }
    if (hasRuntimeProfile || approvalState === "published") {
      return "publish";
    }
    if (approvalState === "approved") {
      return "publish";
    }
    if (approvalState === "submitted") {
      return "admin";
    }
    if (approvalState === "changes_requested" || requiresExpectedConfirmation || selectedSampleHasBlockingErrors) {
      return "review";
    }
    if (isPublishable) {
      return "submit";
    }
    if (sampleCount > 0) {
      return "evaluate";
    }
    return "draft";
  }, [
    approvalState,
    hasRuntimeProfile,
    isPublishable,
    requiresExpectedConfirmation,
    runDetail,
    sampleCount,
    selectedCustomer,
    selectedRunId,
    selectedSampleHasBlockingErrors
  ]);

  const pipelineStages = useMemo<PipelineStage[]>(() => {
    const done = {
      setup: Boolean(selectedCustomer),
      upload: availableSampleCount > 0,
      draft: Boolean(runDetail),
      review: Boolean(runDetail) && !requiresExpectedConfirmation && !selectedSampleHasBlockingErrors,
      evaluate: isPublishable,
      submit: approvalReached(approvalState, ["submitted", "approved", "published"]),
      admin: approvalReached(approvalState, ["approved", "published"]),
      publish: hasRuntimeProfile || approvalState === "published"
    };
    const titles: Record<PipelineStageId, { title: string; hint: string }> = {
      setup: { title: "创建作业", hint: selectedCustomerDisplayName || "选择或新建客户" },
      upload: { title: "上传样本", hint: availableSampleCount ? `${availableSampleCount} 个 PDF 已就绪` : "放入客户 PO" },
      draft: { title: "生成初稿", hint: runDetail ? "解析草稿已生成" : "调用模型解析" },
      review: { title: "人工核对", hint: requiresExpectedConfirmation ? "确认标准答案" : selectedSampleHasBlockingErrors ? "存在阻塞项" : "字段可复核" },
      evaluate: { title: "评测达标", hint: isPublishable ? "门禁通过" : "等待达标" },
      submit: { title: "提交审核", hint: approvalReached(approvalState, ["submitted", "approved", "published"]) ? "已提交" : "业务确认后提交" },
      admin: { title: "管理员批准", hint: approvalReached(approvalState, ["approved", "published"]) ? "已批准" : "等待管理员" },
      publish: { title: "上线生效", hint: hasRuntimeProfile ? "生产已接入" : "发布 Profile" }
    };
    return (Object.keys(titles) as PipelineStageId[]).map((id) => ({
      id,
      title: titles[id].title,
      hint: titles[id].hint,
      state: done[id] ? "done" : id === currentStageId ? (id === "review" && selectedSampleHasBlockingErrors ? "blocked" : "current") : "todo"
    }));
  }, [
    approvalState,
    currentStageId,
    availableSampleCount,
    hasRuntimeProfile,
    isPublishable,
    requiresExpectedConfirmation,
    runDetail,
    selectedCustomer,
    selectedCustomerDisplayName,
    selectedSampleHasBlockingErrors
  ]);

  useEffect(() => {
    setActiveStageId(currentStageId);
  }, [currentStageId]);

  const loadRunDetail = useCallback(async (customer: string, runId: string) => {
    const detail = await api.run(customer, runId);
    setRunDetail(detail);
    setSelectedSampleKey(detail.samples[0]?.sample_key ?? "");
    setState("ready");
  }, []);

  const loadProfileStatus = useCallback(async (customer: string) => {
    if (!customer) {
      setProfileStatus(null);
      return;
    }
    try {
      const profile = await api.profile(customer);
      setProfileStatus(profile);
    } catch {
      setProfileStatus(null);
    }
  }, []);

  const mergeRunsForCustomer = useCallback((customer: string, nextRuns: RunSummary[]) => {
    setAllRuns((currentRuns) => [...currentRuns.filter((run) => run.customer !== customer), ...nextRuns]);
  }, []);

  const loadRunsForCustomer = useCallback(
    async (customer: string, preferredRunId = "") => {
      setState("loading");
      setError("");
      const nextRuns = await api.runs(customer);
      setRuns(nextRuns);
      mergeRunsForCustomer(customer, nextRuns);
      const runId = preferredRunId || latestRunId(nextRuns);
      setSelectedRunId(runId);
      await loadProfileStatus(customer);
      if (!runId) {
        setRunDetail(null);
        setSelectedSampleKey("");
        setState("empty");
        return;
      }
      await loadRunDetail(customer, runId);
    },
    [loadProfileStatus, loadRunDetail, mergeRunsForCustomer]
  );

  const reloadCurrentRun = useCallback(async () => {
    if (!selectedCustomer || !selectedRunId) {
      return;
    }
    const nextRuns = await api.runs(selectedCustomer);
    setRuns(nextRuns);
    mergeRunsForCustomer(selectedCustomer, nextRuns);
    await loadProfileStatus(selectedCustomer);
    await loadRunDetail(selectedCustomer, selectedRunId);
  }, [loadProfileStatus, loadRunDetail, mergeRunsForCustomer, selectedCustomer, selectedRunId]);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialWorkbench() {
      try {
        setState("loading");
        const customerRows = await api.customers();
        if (cancelled) {
          return;
        }
        setCustomers(customerRows);
        const runGroups = await Promise.all(
          customerRows.map(async (customer) => ({
            customer: customer.customer_key,
            runs: await api.runs(customer.customer_key)
          }))
        );
        if (cancelled) {
          return;
        }
        setAllRuns(runGroups.flatMap((group) => group.runs));
        const firstCustomer =
          customerRows.find((customer) => runGroups.some((group) => group.customer === customer.customer_key && group.runs.length > 0)) ??
          customerRows[0];
        if (!firstCustomer) {
          setState("empty");
          return;
        }
        setSelectedCustomer(firstCustomer.customer_key);
        await loadProfileStatus(firstCustomer.customer_key);
        const firstRuns = runGroups.find((group) => group.customer === firstCustomer.customer_key)?.runs ?? [];
        setRuns(firstRuns);
        const firstRunId = latestRunId(firstRuns);
        setSelectedRunId(firstRunId);
        if (!firstRunId) {
          setRunDetail(null);
          setSelectedSampleKey("");
          setState("empty");
          return;
        }
        await loadRunDetail(firstCustomer.customer_key, firstRunId);
      } catch (err) {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : "无法加载审核工作台");
        setState("error");
      }
    }

    loadInitialWorkbench();

    return () => {
      cancelled = true;
    };
  }, [loadProfileStatus, loadRunDetail]);

  async function handleCustomerChange(customer: string) {
    setSelectedCustomer(customer);
    try {
      await loadRunsForCustomer(customer);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载客户运行记录");
      setState("error");
    }
  }

  async function handleRunChange(runId: string) {
    setSelectedRunId(runId);
    try {
      setState("loading");
      await loadRunDetail(selectedCustomer, runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载运行详情");
      setState("error");
    }
  }

  async function handleCustomerCreated(customer: string) {
    const nextCustomers = await api.customers();
    setCustomers(nextCustomers);
    setUploadedSampleNames([]);
    setSelectedCustomer(customer);
    await loadRunsForCustomer(customer);
    setActiveStageId("upload");
  }

  async function handleSampleUploaded(filename: string) {
    const nextCustomers = await api.customers();
    setCustomers(nextCustomers);
    setUploadedSampleNames((current) => (current.includes(filename) ? current : [...current, filename]));
    if (selectedCustomer) {
      await loadProfileStatus(selectedCustomer);
    }
  }

  async function handleRunCreated(runId: string) {
    if (!selectedCustomer) {
      return;
    }
    const nextCustomers = await api.customers();
    setCustomers(nextCustomers);
    setUploadedSampleNames([]);
    await loadRunsForCustomer(selectedCustomer, runId);
  }

  async function handleOpenRun(customer: string, runId: string) {
    if (!adminToken.trim()) {
      setError("打开管理员审核记录前，需要先输入管理员令牌。");
      return;
    }
    setActiveView("workbench");
    setSelectedCustomer(customer);
    try {
      await loadRunsForCustomer(customer, runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载运行详情");
      setState("error");
    }
  }

  function handleAdminTokenChange(token: string) {
    setAdminToken(token);
    if (token.trim()) {
      window.sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
    } else {
      window.sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
    }
  }

  async function handleDeleteRun(customer: string, runId: string) {
    if (!adminToken.trim()) {
      setError("删除运行记录前，需要先输入管理员令牌。");
      return;
    }
    try {
      await api.deleteRun(customer, runId, adminToken);
      const nextCustomers = await api.customers();
      setCustomers(nextCustomers);
      const runGroups = await Promise.all(
        nextCustomers.map(async (customerRow) => ({
          customer: customerRow.customer_key,
          runs: await api.runs(customerRow.customer_key)
        }))
      );
      setAllRuns(runGroups.flatMap((group) => group.runs));
      if (customer === selectedCustomer) {
        await loadRunsForCustomer(customer, selectedRunId === runId ? "" : selectedRunId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除运行记录失败");
    }
  }

  function startNewCustomerImport() {
    setActiveView("workbench");
    setSelectedCustomer("");
    setSelectedRunId("");
    setSelectedSampleKey("");
    setRuns([]);
    setRunDetail(null);
    setProfileStatus(null);
    setUploadedSampleNames([]);
    setError("");
    setState("empty");
    setActiveStageId("setup");
  }

  function renderUploadReadyPanel() {
    if (!selectedCustomer || availableSampleCount === 0) {
      return null;
    }
    const names = uploadedSampleNames.length ? uploadedSampleNames : [`已准备 ${availableSampleCount} 个 PDF 样本`];
    return (
      <div className="upload-ready-panel">
        <div>
          <span className="pane-kicker">样本已就绪</span>
          <h3>{availableSampleCount} 个 PDF 可用于生成初稿</h3>
          <p>可以继续上传同一客户的其他 PO，也可以进入下一步开始调用模型。</p>
        </div>
        <ul>
          {names.slice(0, 4).map((name) => (
            <li key={name}>
              <FileText size={15} />
              <span>{name}</span>
            </li>
          ))}
        </ul>
        <button type="button" onClick={() => setActiveStageId("draft")}>
          <ArrowRight size={16} />
          <span>进入生成初稿</span>
        </button>
      </div>
    );
  }

  const hasWorkbench = state === "ready" && runDetail && selectedCustomer && selectedRunId;

  function renderSampleRail() {
    if (!runDetail?.samples.length) {
      return null;
    }
    return (
      <section className="sample-rail" aria-label="样本列表">
        {runDetail.samples.map((sample) => (
          <button
            className={sample.sample_key === selectedSample?.sample_key ? "sample-tab active" : "sample-tab"}
            key={sample.sample_key}
            type="button"
            onClick={() => setSelectedSampleKey(sample.sample_key)}
            title={sample.source_file}
          >
            <span>{sample.sample_key}</span>
            <strong>{sample.report?.publishable ? "通过" : "检查"}</strong>
          </button>
        ))}
      </section>
    );
  }

  function renderStageIntro(title: string, description: string) {
    return (
      <div className="stage-intro">
        <span className="pane-kicker">当前阶段</span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    );
  }

  function renderCurrentStage() {
    if (activeStageId === "setup") {
      return (
        <section className="stage-panel stage-setup">
          {renderStageIntro("创建或选择客户", "先建立客户档案。后续样本、评测、纠错、上线都会沉淀到这个客户 Profile 下。")}
          <RunComposer
            mode="customer"
            selectedCustomer={selectedCustomer}
            onCustomerCreated={handleCustomerCreated}
            onSampleUploaded={handleSampleUploaded}
            onRunCreated={handleRunCreated}
          />
        </section>
      );
    }

    if (activeStageId === "upload") {
      return (
        <section className="stage-panel stage-upload">
          {renderStageIntro("上传客户 PO 样本", "把当前客户的 PDF 样本放进来。一个作业可以承载多个样本，用来验证这个客户 Profile 是否稳定。")}
          <RunComposer
            mode="sample"
            selectedCustomer={selectedCustomer}
            onCustomerCreated={handleCustomerCreated}
            onSampleUploaded={handleSampleUploaded}
            onRunCreated={handleRunCreated}
          />
          {renderUploadReadyPanel()}
          {renderSampleRail()}
        </section>
      );
    }

    if (activeStageId === "draft") {
      return (
        <section className="stage-panel stage-draft">
          {renderStageIntro("生成解析初稿", "使用文本和视觉模型跑出字段草稿，并自动完成合并与首轮评测。等待时页面会保留作业上下文，不需要切换到命令行。")}
          <RunComposer
            mode="run"
            selectedCustomer={selectedCustomer}
            onCustomerCreated={handleCustomerCreated}
            onSampleUploaded={handleSampleUploaded}
            onRunCreated={handleRunCreated}
          />
          <div className="run-wait-visual" aria-label="生成等待提示">
            <strong>解析引擎待命</strong>
            <p>点击「生成并评测」后，会在上方清单中显示当前作业进展。当前版本是同步作业，真实完成以运行批次生成成功为准。</p>
          </div>
        </section>
      );
    }

    if (!hasWorkbench) {
      return (
        <section className={`workbench-state state-${state}`} aria-live="polite">
          {state === "loading" ? <Loader2 size={22} className="spin" /> : <AlertTriangle size={22} />}
          <span>
            {state === "loading"
              ? "正在加载审核运行..."
              : state === "empty"
                ? "暂无可用的客户运行记录。"
                : error || "工作台暂不可用。"}
          </span>
        </section>
      );
    }

    if (activeStageId === "review") {
      return (
        <section className="stage-panel">
          {renderStageIntro("人工核对与纠错", "左侧看原始 PDF，右侧点字段填写正确值。保存纠错后会更新标准答案并重新评测。")}
          {renderSampleRail()}
          <div className="stage-review-grid">
            <PdfEvidencePane sample={selectedSample} />
            <StandardJsonPane customer={selectedCustomer} runId={selectedRunId} sample={selectedSample} onReload={reloadCurrentRun} />
          </div>
        </section>
      );
    }

    if (activeStageId === "evaluate") {
      return (
        <section className="stage-panel">
          {renderStageIntro("评测结果与问题定位", "这里只看差异、分数和下一步建议。没有阻塞项并且评测达标后，就可以提交管理员审核。")}
          <ScoreStrip evaluation={runDetail.evaluation} samples={runDetail.samples} approval={runDetail.approval} />
          <div className="stage-evaluate-grid">
            <CandidateDiffPane sample={selectedSample} />
            <AdjudicationPanel evaluation={runDetail.evaluation} approval={runDetail.approval} sample={selectedSample} />
          </div>
        </section>
      );
    }

    if (activeStageId === "submit") {
      return (
        <section className="stage-panel stage-gate-panel">
          {renderStageIntro("业务确认并提交审核", "确认标准答案和评测分数后，业务侧只需要提交审核。管理员会在审核队列中看到这个作业。")}
          <div className="stage-gate-grid">
            <AdjudicationPanel evaluation={runDetail.evaluation} approval={runDetail.approval} sample={selectedSample} />
            <ApprovalGate
              customer={selectedCustomer}
              runId={selectedRunId}
              approval={runDetail.approval}
              mode="business"
              adminToken={adminToken}
              sampleKey={selectedSample?.sample_key ?? ""}
              requiresExpectedConfirmation={requiresExpectedConfirmation}
              profileStatus={profileStatus}
              onReload={reloadCurrentRun}
            />
          </div>
        </section>
      );
    }

    if (activeStageId === "admin") {
      return (
        <section className="stage-panel stage-gate-panel">
          {renderStageIntro("管理员批准", "管理员输入令牌后批准或驳回。驳回会回到人工核对阶段，批准后进入上线发布。")}
          <div className="stage-gate-grid">
            <ApprovalGate
              customer={selectedCustomer}
              runId={selectedRunId}
              approval={runDetail.approval}
              mode="admin"
              adminToken={adminToken}
              sampleKey={selectedSample?.sample_key ?? ""}
              requiresExpectedConfirmation={requiresExpectedConfirmation}
              profileStatus={profileStatus}
              onReload={reloadCurrentRun}
            />
            <AdjudicationPanel evaluation={runDetail.evaluation} approval={runDetail.approval} sample={selectedSample} />
          </div>
        </section>
      );
    }

    return (
      <section className="stage-panel stage-gate-panel">
        {renderStageIntro("上线生效", "确认客户识别标识后发布 Profile。发布成功后，新 PDF 会被正式解析服务识别并使用该客户配置。")}
        <div className="stage-gate-grid">
          <ProfileActivationPanel
            customer={selectedCustomer}
            displayName={selectedCustomerDisplayName}
            adminToken={adminToken}
            approval={runDetail.approval}
            profileStatus={profileStatus}
            sample={selectedSample}
            onProfileChange={setProfileStatus}
          />
          <ApprovalGate
            customer={selectedCustomer}
            runId={selectedRunId}
            approval={runDetail.approval}
            mode="admin"
            adminToken={adminToken}
            sampleKey={selectedSample?.sample_key ?? ""}
            requiresExpectedConfirmation={requiresExpectedConfirmation}
            profileStatus={profileStatus}
            onReload={reloadCurrentRun}
          />
        </div>
      </section>
    );
  }

  return (
    <main className="app-shell">
      <nav className="view-tabs" aria-label="PO解析工作台视图">
        <div className="app-identity">
          <span className="app-mark">PO</span>
          <div>
            <strong>PO解析实验室</strong>
            <span>审核与调优工作台</span>
          </div>
        </div>
        <button
          className={activeView === "workbench" ? "active" : ""}
          type="button"
          onClick={() => {
            setActiveView("workbench");
          }}
        >
          <ClipboardCheck size={16} />
          <span>工作台</span>
        </button>
        <button className={activeView === "dashboard" ? "active" : ""} type="button" onClick={() => setActiveView("dashboard")}>
          <BarChart3 size={16} />
          <span>看板</span>
        </button>
        <button className={activeView === "admin" ? "active" : ""} type="button" onClick={() => setActiveView("admin")}>
          <ShieldCheck size={16} />
          <span>管理员审核</span>
        </button>
        <div className="app-footnote">
          <strong>轻量审核流程</strong>
          <span>PDF证据、纠错队列、上线门禁。</span>
        </div>
      </nav>

      {activeView === "dashboard" ? <Dashboard customers={customers} runs={allRuns} /> : null}
      {activeView === "admin" ? (
        <AdminReview
          customers={customers}
          runs={allRuns}
          adminToken={adminToken}
          onAdminTokenChange={handleAdminTokenChange}
          onOpenRun={handleOpenRun}
          onDeleteRun={handleDeleteRun}
        />
      ) : null}

      <section className={activeView === "workbench" ? "workbench" : "workbench hidden-view"}>
        <RunTopBar
          customers={customers}
          runs={runs}
          selectedCustomer={selectedCustomer}
          selectedRunId={selectedRunId}
          approval={runDetail?.approval ?? null}
          onCustomerChange={handleCustomerChange}
          onRunChange={handleRunChange}
          onStartNewJob={startNewCustomerImport}
        />

        <JobProgress
          stages={pipelineStages}
          activeStageId={activeStageId}
          onStageChange={(stageId) => setActiveStageId(stageId as PipelineStageId)}
        />

        <section className="stage-workspace">{renderCurrentStage()}</section>
      </section>
    </main>
  );
}

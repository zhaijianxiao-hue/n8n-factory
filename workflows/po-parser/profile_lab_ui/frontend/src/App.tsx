import { AlertTriangle, BarChart3, ClipboardCheck, Loader2, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "./api";
import { AdjudicationPanel } from "./components/AdjudicationPanel";
import { AdminReview } from "./components/AdminReview";
import { ApprovalGate } from "./components/ApprovalGate";
import { CandidateDiffPane } from "./components/CandidateDiffPane";
import { Dashboard } from "./components/Dashboard";
import { PdfEvidencePane } from "./components/PdfEvidencePane";
import { RunTopBar } from "./components/RunTopBar";
import { ScoreStrip } from "./components/ScoreStrip";
import { StandardJsonPane } from "./components/StandardJsonPane";
import type { CustomerSummary, RunDetail, RunSample, RunSummary } from "./types";

type LoadState = "loading" | "ready" | "empty" | "error";
type AppView = "workbench" | "dashboard" | "admin";
type ApprovalMode = "business" | "admin";
const ADMIN_TOKEN_STORAGE_KEY = "po-profile-lab-admin-token";

function latestRunId(runs: RunSummary[]): string {
  return runs[0]?.run_id ?? "";
}

export default function App() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [allRuns, setAllRuns] = useState<RunSummary[]>([]);
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);
  const [selectedCustomer, setSelectedCustomer] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedSampleKey, setSelectedSampleKey] = useState("");
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [activeView, setActiveView] = useState<AppView>("workbench");
  const [approvalMode, setApprovalMode] = useState<ApprovalMode>("business");
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

  const loadRunDetail = useCallback(async (customer: string, runId: string) => {
    const detail = await api.run(customer, runId);
    setRunDetail(detail);
    setSelectedSampleKey(detail.samples[0]?.sample_key ?? "");
    setState("ready");
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
      if (!runId) {
        setRunDetail(null);
        setSelectedSampleKey("");
        setState("empty");
        return;
      }
      await loadRunDetail(customer, runId);
    },
    [loadRunDetail, mergeRunsForCustomer]
  );

  const reloadCurrentRun = useCallback(async () => {
    if (!selectedCustomer || !selectedRunId) {
      return;
    }
    const nextRuns = await api.runs(selectedCustomer);
    setRuns(nextRuns);
    mergeRunsForCustomer(selectedCustomer, nextRuns);
    await loadRunDetail(selectedCustomer, selectedRunId);
  }, [loadRunDetail, mergeRunsForCustomer, selectedCustomer, selectedRunId]);

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
        setError(err instanceof Error ? err.message : "无法加载 Review Workbench");
        setState("error");
      }
    }

    loadInitialWorkbench();

    return () => {
      cancelled = true;
    };
  }, [loadRunDetail]);

  async function handleCustomerChange(customer: string) {
    setSelectedCustomer(customer);
    setApprovalMode("business");
    try {
      await loadRunsForCustomer(customer);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载客户运行记录");
      setState("error");
    }
  }

  async function handleRunChange(runId: string) {
    setSelectedRunId(runId);
    setApprovalMode("business");
    try {
      setState("loading");
      await loadRunDetail(selectedCustomer, runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载运行详情");
      setState("error");
    }
  }

  async function handleOpenRun(customer: string, runId: string) {
    if (!adminToken.trim()) {
      setApprovalMode("business");
      setError("Admin token is required before opening an approval run.");
      return;
    }
    setActiveView("workbench");
    setApprovalMode("admin");
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
      setApprovalMode("business");
    }
  }

  const hasWorkbench = state === "ready" && runDetail && selectedCustomer && selectedRunId;

  return (
    <main className="app-shell">
      <nav className="view-tabs" aria-label="Profile Lab views">
        <div className="app-identity">
          <span className="app-mark">PO</span>
          <div>
            <strong>Profile Lab</strong>
            <span>Review workbench</span>
          </div>
        </div>
        <button
          className={activeView === "workbench" ? "active" : ""}
          type="button"
          onClick={() => {
            setActiveView("workbench");
            setApprovalMode("business");
          }}
        >
          <ClipboardCheck size={16} />
          <span>Workbench</span>
        </button>
        <button className={activeView === "dashboard" ? "active" : ""} type="button" onClick={() => setActiveView("dashboard")}>
          <BarChart3 size={16} />
          <span>Dashboard</span>
        </button>
        <button className={activeView === "admin" ? "active" : ""} type="button" onClick={() => setActiveView("admin")}>
          <ShieldCheck size={16} />
          <span>Admin Review</span>
        </button>
        <div className="app-footnote">
          <strong>Light operations UI</strong>
          <span>PDF evidence, correction queue, publish gate.</span>
        </div>
      </nav>

      {activeView === "dashboard" ? <Dashboard customers={customers} runs={allRuns} /> : null}
      {activeView === "admin" ? (
        <AdminReview customers={customers} runs={allRuns} adminToken={adminToken} onAdminTokenChange={handleAdminTokenChange} onOpenRun={handleOpenRun} />
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
        />

        {hasWorkbench ? (
          <>
            <ScoreStrip evaluation={runDetail.evaluation} samples={runDetail.samples} approval={runDetail.approval} />

            <section className="sample-rail" aria-label="Samples">
              {runDetail.samples.map((sample) => (
                <button
                  className={sample.sample_key === selectedSample?.sample_key ? "sample-tab active" : "sample-tab"}
                  key={sample.sample_key}
                  type="button"
                  onClick={() => setSelectedSampleKey(sample.sample_key)}
                  title={sample.source_file}
                >
                  <span>{sample.sample_key}</span>
                  <strong>{sample.report?.publishable ? "PASS" : "CHECK"}</strong>
                </button>
              ))}
            </section>

            <section className="review-grid">
              <PdfEvidencePane sample={selectedSample} />
              <CandidateDiffPane sample={selectedSample} />
              <StandardJsonPane customer={selectedCustomer} runId={selectedRunId} sample={selectedSample} onReload={reloadCurrentRun} />
              <AdjudicationPanel evaluation={runDetail.evaluation} approval={runDetail.approval} sample={selectedSample} />
              <ApprovalGate
                customer={selectedCustomer}
                runId={selectedRunId}
                approval={runDetail.approval}
                mode={approvalMode}
                adminToken={adminToken}
                sampleKey={selectedSample?.sample_key ?? ""}
                requiresExpectedConfirmation={requiresExpectedConfirmation}
                onReload={reloadCurrentRun}
              />
            </section>
          </>
        ) : (
          <section className={`workbench-state state-${state}`} aria-live="polite">
            {state === "loading" ? <Loader2 size={22} className="spin" /> : <AlertTriangle size={22} />}
            <span>
              {state === "loading"
                ? "Loading review run..."
                : state === "empty"
                  ? "No customer runs are available."
                  : error || "Workbench unavailable."}
            </span>
          </section>
        )}
      </section>
    </main>
  );
}

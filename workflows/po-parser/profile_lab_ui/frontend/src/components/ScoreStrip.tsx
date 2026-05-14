import { Ban, CheckCircle2, Gauge, Rows3, ShieldAlert } from "lucide-react";

import type { ApprovalRecord, EvaluationReport, EvaluationSummary, RunSample } from "../types";

function average(values: number[]): number | null {
  if (values.length === 0) {
    return null;
  }
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function scorePercent(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return `${Math.round(value * 100)}%`;
}

function reportOverallScore(report: EvaluationReport): number | undefined {
  return typeof report.overall_score === "number" ? report.overall_score : undefined;
}

function deriveOverallScore(evaluation: EvaluationSummary | null): number | null {
  if (!evaluation) {
    return null;
  }
  if (typeof evaluation.overall_score === "number") {
    return evaluation.overall_score;
  }
  return average((evaluation.reports ?? []).map(reportOverallScore).filter((score): score is number => typeof score === "number"));
}

function deriveBusinessRulesScore(evaluation: EvaluationSummary | null): number | null {
  return average(
    (evaluation?.reports ?? [])
      .map((report) => report.scores?.business_rules)
      .filter((score): score is number => typeof score === "number")
  );
}

interface ScoreStripProps {
  evaluation: EvaluationSummary | null;
  samples: RunSample[];
  approval: ApprovalRecord | null;
}

export function ScoreStrip({ evaluation, samples, approval }: ScoreStripProps) {
  const p0Pass =
    evaluation?.p0_pass ??
    (evaluation?.reports?.length ? evaluation.reports.every((report) => report.p0_pass !== false) : undefined);
  const sampleCount = evaluation?.sample_count ?? samples.length;

  return (
    <section className="score-strip" aria-label="Run scores">
      <div className="score-cell primary-score">
        <Gauge size={18} />
        <span>Overall</span>
        <strong>{scorePercent(deriveOverallScore(evaluation))}</strong>
      </div>
      <div className={`score-cell ${p0Pass ? "score-ok" : "score-danger"}`}>
        {p0Pass ? <CheckCircle2 size={18} /> : <Ban size={18} />}
        <span>P0</span>
        <strong>{p0Pass === undefined ? "--" : p0Pass ? "PASS" : "BLOCK"}</strong>
      </div>
      <div className="score-cell">
        <Rows3 size={18} />
        <span>Samples</span>
        <strong>{sampleCount}</strong>
      </div>
      <div className="score-cell">
        <ShieldAlert size={18} />
        <span>Business</span>
        <strong>{scorePercent(deriveBusinessRulesScore(evaluation))}</strong>
      </div>
      <div className="score-cell gate-cell">
        <CheckCircle2 size={18} />
        <span>Gate</span>
        <strong>{approval?.state ?? "draft"}</strong>
      </div>
    </section>
  );
}

import { AlertTriangle, Check, Circle, Loader2 } from "lucide-react";

export type PipelineStageState = "done" | "current" | "blocked" | "todo";

export interface PipelineStage {
  id: string;
  title: string;
  hint: string;
  state: PipelineStageState;
}

interface JobProgressProps {
  stages: PipelineStage[];
  activeStageId: string;
  onStageChange: (stageId: string) => void;
}

function StageIcon({ state }: { state: PipelineStageState }) {
  if (state === "done") {
    return <Check size={16} />;
  }
  if (state === "current") {
    return <Loader2 size={16} className="stage-spin" />;
  }
  if (state === "blocked") {
    return <AlertTriangle size={16} />;
  }
  return <Circle size={16} />;
}

export function JobProgress({ stages, activeStageId, onStageChange }: JobProgressProps) {
  const highlightedStage = stages.find((stage) => stage.id === activeStageId) ?? stages.find((stage) => stage.state === "current");

  return (
    <section className="job-progress" aria-label="作业进度">
      <div className="job-progress-header">
        <div>
          <span className="pane-kicker">作业流水线</span>
          <h2>按阶段推进客户 PO Profile 上线</h2>
        </div>
        <strong>{highlightedStage?.title ?? "准备中"}</strong>
      </div>

      <div className="pipeline-track" role="list">
        {stages.map((stage, index) => (
          <button
            className={`pipeline-step ${stage.state} ${activeStageId === stage.id ? "active" : ""}`}
            key={stage.id}
            type="button"
            onClick={() => onStageChange(stage.id)}
            role="listitem"
            style={{ animationDelay: `${index * 70}ms` }}
          >
            <span className="pipeline-node">
              <StageIcon state={stage.state} />
            </span>
            <span className="pipeline-copy">
              <strong>{stage.title}</strong>
              <small>{stage.hint}</small>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

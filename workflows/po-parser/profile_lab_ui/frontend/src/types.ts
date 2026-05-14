declare module "react" {
  export type ReactNode = unknown;
  export namespace JSX {
    interface IntrinsicElements {
      [elementName: string]: unknown;
    }
  }
  export interface EffectCallback {
    (): void | (() => void);
  }
  export interface Dispatch<T> {
    (value: T): void;
  }
  export function useEffect(effect: EffectCallback, deps?: unknown[]): void;
  export function useState<T>(initialValue: T): [T, Dispatch<T>];
  const React: {
    StrictMode: (props: { children?: ReactNode }) => ReactNode;
  };
  export default React;
}

declare module "react-dom/client" {
  export function createRoot(container: HTMLElement): {
    render(children: unknown): void;
  };
}

declare module "react/jsx-runtime" {
  export namespace JSX {
    interface IntrinsicElements {
      [elementName: string]: unknown;
    }
  }
  export const Fragment: unknown;
  export function jsx(type: unknown, props: unknown, key?: unknown): unknown;
  export function jsxs(type: unknown, props: unknown, key?: unknown): unknown;
}

namespace JSX {
  interface IntrinsicElements {
    [elementName: string]: unknown;
  }
}

type ApprovalState =
  | "draft"
  | "generated"
  | "evaluated"
  | "submitted"
  | "changes_requested"
  | "approved"
  | "published";

interface ApprovalRecord {
  state: ApprovalState;
  submitted_by: string | null;
  submitted_at: string | null;
  admin_decision: "approved" | "rejected" | null;
  admin_by: string | null;
  admin_at: string | null;
  note: string;
  notification_status: string | null;
  notification_error: string | null;
}

interface CustomerSummary {
  customer_key: string;
  display_name: string;
  run_count: number;
}

interface FieldIssue {
  field: string;
  severity: "p0" | "p1" | "warning" | string;
  message: string;
  expected?: unknown;
  actual?: unknown;
}

interface EvaluationReport {
  publishable?: boolean;
  schema_pass?: boolean;
  p0_pass?: boolean;
  blocking_errors?: string[];
  scores?: Record<string, number>;
  field_issues?: FieldIssue[];
  [key: string]: unknown;
}

interface EvaluationSummary {
  publishable?: boolean;
  sample_count?: number;
  overall_score?: number;
  reports?: EvaluationReport[];
  [key: string]: unknown;
}

interface RunSummary {
  run_id: string;
  customer: string;
  created_at: string | null;
  sample_count: number;
  evaluation: EvaluationSummary;
  approval: ApprovalRecord;
}

interface RunSample {
  sample_key: string;
  source_file: string;
  text_candidate: Record<string, unknown>;
  vision_candidate: Record<string, unknown>;
  merged_draft: Record<string, unknown>;
  report: EvaluationReport;
}

interface RunDetail {
  manifest: Record<string, unknown>;
  evaluation: EvaluationSummary;
  approval: ApprovalRecord;
  samples: RunSample[];
}

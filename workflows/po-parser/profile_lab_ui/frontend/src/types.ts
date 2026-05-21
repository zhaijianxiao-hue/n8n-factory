export type ApprovalState =
  | "draft"
  | "generated"
  | "evaluated"
  | "submitted"
  | "changes_requested"
  | "approved"
  | "published";

export interface ApprovalRecord {
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

export interface CustomerSummary {
  customer_key: string;
  display_name: string;
  run_count: number;
  sample_count: number;
}

export interface ProfileStatus {
  customer: string;
  profile_name: string;
  markers: string[];
  lab_status: string;
  production_status: string | null;
  runtime_ready: boolean;
  lab_profile_path: string;
  production_profile_path: string;
  production_exists: boolean;
  published_at: string | null;
  last_run_id: string | null;
}

export interface FieldIssue {
  field: string;
  severity: "p0" | "p1" | "warning" | string;
  message?: string;
  reason?: string;
  expected?: unknown;
  actual?: unknown;
}

export interface EvaluationReport {
  publishable?: boolean;
  schema_pass?: boolean;
  p0_pass?: boolean;
  expected_missing?: boolean;
  blocking_errors?: FieldIssue[];
  scores?: Record<string, number>;
  field_issues?: FieldIssue[];
  [key: string]: unknown;
}

export interface EvaluationSummary {
  publishable?: boolean;
  sample_count?: number;
  overall_score?: number;
  reports?: EvaluationReport[];
  [key: string]: unknown;
}

export interface CorrectionEntry {
  field: string;
  wrong_value?: unknown;
  correct_value: unknown;
  note?: string;
  actor?: string;
}

export interface CorrectionRecord {
  sample_key?: string;
  source_file?: string;
  actor?: string;
  corrections?: CorrectionEntry[];
}

export interface RunSummary {
  run_id: string;
  customer: string;
  created_at: string | null;
  sample_count: number;
  evaluation: EvaluationSummary;
  approval: ApprovalRecord;
}

export interface RunSample {
  sample_key: string;
  source_file: string;
  pdf_url?: string;
  page_image_url?: string;
  text_candidate: Record<string, unknown>;
  vision_candidate: Record<string, unknown>;
  merged_draft: Record<string, unknown>;
  report: EvaluationReport;
  corrections?: CorrectionRecord;
}

export interface RunDetail {
  manifest: Record<string, unknown>;
  evaluation: EvaluationSummary;
  approval: ApprovalRecord;
  samples: RunSample[];
}

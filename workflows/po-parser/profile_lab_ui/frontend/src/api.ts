import type {
  ApprovalRecord,
  CustomerSummary,
  ProfileStatus,
  RunDetail,
  RunSummary
} from "./types";

type RequestOptions = RequestInit & {
  json?: unknown;
};

function actionBody(actor: string, note?: string): RequestOptions {
  return {
    method: "POST",
    json: {
      actor,
      note: note ?? ""
    }
  };
}

function adminHeaders(adminToken: string): HeadersInit {
  return {
    "X-PO-Profile-Lab-Admin-Token": adminToken
  };
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  let body = options.body;
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.json);
  }

  const response = await fetch(path, {
    ...options,
    headers,
    body
  });

  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const detail = typeof data === "object" && data !== null && "detail" in data ? data.detail : data;
    throw new Error(typeof detail === "string" ? detail : `Request failed: ${response.status}`);
  }

  return data as T;
}

export const api = {
  customers: () => request<CustomerSummary[]>("/api/customers"),
  createCustomer: (customer: string, displayName: string) =>
    request<CustomerSummary>("/api/customers", {
      method: "POST",
      json: {
        customer,
        display_name: displayName
      }
    }),
  profile: (customer: string) => request<ProfileStatus>(`/api/customers/${encodeURIComponent(customer)}/profile`),
  updateProfileMarkers: (customer: string, adminToken: string, markers: string[]) =>
    request<ProfileStatus>(
      `/api/customers/${encodeURIComponent(customer)}/profile/markers`,
      {
        method: "PUT",
        headers: adminHeaders(adminToken),
        json: { markers }
      }
    ),
  runs: (customer: string) => request<RunSummary[]>(`/api/customers/${encodeURIComponent(customer)}/runs`),
  samples: (customer: string) =>
    request<Array<{ filename: string; size: number }>>(`/api/customers/${encodeURIComponent(customer)}/samples`),
  uploadSample: (customer: string, file: File) =>
    request<{ customer: string; filename: string; size: number }>(
      `/api/customers/${encodeURIComponent(customer)}/samples/${encodeURIComponent(file.name)}`,
      {
        method: "PUT",
        headers: { "Content-Type": file.type || "application/pdf" },
        body: file
      }
    ),
  createRun: (customer: string, runId: string, textModel?: string, visionModel?: string) =>
    request<RunDetail>(`/api/customers/${encodeURIComponent(customer)}/runs`, {
      method: "POST",
      json: {
        run_id: runId,
        text_model: textModel || null,
        vision_model: visionModel || null
      }
    }),
  run: (customer: string, runId: string) =>
    request<RunDetail>(`/api/customers/${encodeURIComponent(customer)}/runs/${encodeURIComponent(runId)}`),
  confirmExpected: (customer: string, runId: string, sampleKey: string) =>
    request<RunDetail>(
      `/api/customers/${encodeURIComponent(customer)}/runs/${encodeURIComponent(runId)}/samples/${encodeURIComponent(sampleKey)}/confirm-expected`,
      { method: "POST" }
    ),
  saveCorrections: (customer: string, runId: string, sampleKey: string, corrections: Array<{ field: string; correct_value: unknown; note?: string }>) =>
    request<RunDetail>(
      `/api/customers/${encodeURIComponent(customer)}/runs/${encodeURIComponent(runId)}/samples/${encodeURIComponent(sampleKey)}/corrections`,
      {
        method: "POST",
        json: {
          actor: "business",
          corrections
        }
      }
    ),
  submit: (customer: string, runId: string, actor = "business", note?: string) =>
    request<ApprovalRecord>(
      `/api/customers/${encodeURIComponent(customer)}/runs/${encodeURIComponent(runId)}/submit`,
      actionBody(actor, note)
    ),
  approve: (customer: string, runId: string, adminToken: string, actor = "admin", note?: string) =>
    request<ApprovalRecord>(
      `/api/customers/${encodeURIComponent(customer)}/runs/${encodeURIComponent(runId)}/approve`,
      { ...actionBody(actor, note), headers: adminHeaders(adminToken) }
    ),
  reject: (customer: string, runId: string, adminToken: string, actor = "admin", note?: string) =>
    request<ApprovalRecord>(
      `/api/customers/${encodeURIComponent(customer)}/runs/${encodeURIComponent(runId)}/reject`,
      { ...actionBody(actor, note), headers: adminHeaders(adminToken) }
    ),
  publish: (customer: string, runId: string, adminToken: string) =>
    request<ApprovalRecord & { profile_path?: string }>(
      `/api/customers/${encodeURIComponent(customer)}/runs/${encodeURIComponent(runId)}/publish`,
      { method: "POST", headers: adminHeaders(adminToken) }
    ),
  deleteRun: (customer: string, runId: string, adminToken: string) =>
    request<{ customer: string; run_id: string; deleted: boolean }>(
      `/api/customers/${encodeURIComponent(customer)}/runs/${encodeURIComponent(runId)}`,
      { method: "DELETE", headers: adminHeaders(adminToken) }
    )
};

import type {
  ApprovalRecord,
  CustomerSummary,
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
  runs: (customer: string) => request<RunSummary[]>(`/api/customers/${encodeURIComponent(customer)}/runs`),
  run: (customer: string, runId: string) =>
    request<RunDetail>(`/api/customers/${encodeURIComponent(customer)}/runs/${encodeURIComponent(runId)}`),
  confirmExpected: (customer: string, runId: string, sampleKey: string) =>
    request<RunDetail>(
      `/api/customers/${encodeURIComponent(customer)}/runs/${encodeURIComponent(runId)}/samples/${encodeURIComponent(sampleKey)}/confirm-expected`,
      { method: "POST" }
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
    )
};

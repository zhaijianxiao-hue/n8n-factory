import { Braces, CircleAlert, Pencil, Save } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { api } from "../api";
import type { FieldIssue, RunSample } from "../types";

function valueText(value: unknown): string {
  if (value === null) {
    return "null";
  }
  if (value === undefined) {
    return "undefined";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function tableValueText(value: unknown): string {
  return value === null || value === undefined || value === "" ? "-" : valueText(value);
}

function flattenJson(value: unknown, prefix = "", depth = 0): Array<{ path: string; value: unknown }> {
  if (!value || typeof value !== "object" || depth >= 3) {
    return prefix ? [{ path: prefix, value }] : [];
  }

  if (Array.isArray(value)) {
    return value.slice(0, 8).flatMap((entry, index) => flattenJson(entry, `${prefix}[${index}]`, depth + 1));
  }

  return Object.entries(value as Record<string, unknown>).flatMap(([key, entry]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (entry && typeof entry === "object" && !Array.isArray(entry)) {
      return flattenJson(entry, path, depth + 1);
    }
    return [{ path, value: entry }];
  });
}

function isHotPath(path: string): boolean {
  return path.startsWith("header.") || path.includes("status");
}

function hasIssue(path: string, issues: FieldIssue[]): boolean {
  return issues.some((issue) => issue.field && (path === issue.field || path.startsWith(`${issue.field}.`)));
}

interface StandardJsonPaneProps {
  customer: string;
  runId: string;
  sample: RunSample | null;
  onReload: () => Promise<void>;
}

const itemColumns = [
  { key: "line_no", label: "Line" },
  { key: "customer_material", label: "Material" },
  { key: "qty", label: "Qty" },
  { key: "delivery_date", label: "Delivery" },
  { key: "unit_price", label: "Unit Price" },
  { key: "amount", label: "Amount" }
];

function draftItems(draft: Record<string, unknown>): Array<Record<string, unknown>> {
  return Array.isArray(draft.items) ? draft.items.filter((item): item is Record<string, unknown> => item !== null && typeof item === "object") : [];
}

function itemHasIssue(index: number, issues: FieldIssue[]): boolean {
  return issues.some((issue) => issue.field?.startsWith(`items[${index}]`));
}

export function StandardJsonPane({ customer, runId, sample, onReload }: StandardJsonPaneProps) {
  const [fieldPath, setFieldPath] = useState("");
  const [correctValue, setCorrectValue] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const draft = sample?.merged_draft ?? {};
  const rows = flattenJson(draft).filter((row) => !row.path.startsWith("items"));
  const items = draftItems(draft);
  const blockingErrors = sample?.report?.blocking_errors ?? [];
  const correctionCount = sample?.corrections?.corrections?.length ?? 0;

  useEffect(() => {
    setError("");
  }, [sample?.sample_key]);

  function selectCorrection(path: string, value: unknown) {
    setFieldPath(path);
    setCorrectValue(value === null || value === undefined ? "" : valueText(value));
    setNote("");
    setError("");
  }

  async function saveCorrection(event: FormEvent) {
    event.preventDefault();
    if (!sample || !fieldPath.trim()) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.saveCorrections(customer, runId, sample.sample_key, [
        {
          field: fieldPath.trim(),
          correct_value: correctValue,
          note
        }
      ]);
      await onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Correction failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="pane json-pane">
      <div className="pane-header">
        <div>
          <span className="pane-kicker">Standard JSON</span>
          <h2>{correctionCount ? `Merged draft · ${correctionCount} corrections` : "Merged draft"}</h2>
        </div>
        <Braces size={18} />
      </div>

      <div className="json-list">
        {rows.length === 0 && items.length === 0 ? (
          <div className="empty-pane">No merged draft available.</div>
        ) : (
          <>
            {rows.slice(0, 42).map((row, index) => {
              const blocked = hasIssue(row.path, blockingErrors);
              return (
                <div className={`json-row ${isHotPath(row.path) ? "json-hot" : ""} ${blocked ? "json-blocked" : ""}`} key={`${row.path}-${index}`}>
                  <span className="json-path">
                    {blocked ? <CircleAlert size={13} /> : null}
                    {row.path}
                  </span>
                  <code>{valueText(row.value)}</code>
                  <button type="button" className="field-edit-button" onClick={() => selectCorrection(row.path, row.value)} title={`Correct ${row.path}`}>
                    <Pencil size={13} />
                  </button>
                </div>
              );
            })}

            {items.length ? (
              <div className="items-block">
                <div className="items-title">
                  <span>Items</span>
                  <strong>{items.length}</strong>
                </div>
                <div className="items-table" role="table" aria-label="PO items">
                  <div className="items-row items-head" role="row">
                    {itemColumns.map((column) => (
                      <span key={column.key} role="columnheader">
                        {column.label}
                      </span>
                    ))}
                  </div>
                  {items.map((item, index) => (
                    <div className={`items-row ${itemHasIssue(index, blockingErrors) ? "items-blocked" : ""}`} role="row" key={`${valueText(item.line_no)}-${index}`}>
                      {itemColumns.map((column) => (
                        <button
                          className="item-edit-cell"
                          key={column.key}
                          type="button"
                          role="cell"
                          onClick={() => selectCorrection(`items[${index}].${column.key}`, item[column.key])}
                          title={`Correct items[${index}].${column.key}`}
                        >
                          {tableValueText(item[column.key])}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <form className="correction-editor" onSubmit={saveCorrection}>
              <div className="correction-fields">
                <label>
                  <span>Field</span>
                  <input value={fieldPath} onChange={(event) => setFieldPath(event.target.value)} placeholder="header.payment_terms" />
                </label>
                <label>
                  <span>Correct Value</span>
                  <input value={correctValue} onChange={(event) => setCorrectValue(event.target.value)} />
                </label>
              </div>
              <label>
                <span>Agent Note</span>
                <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} />
              </label>
              <button className="save-correction-button" type="submit" disabled={!sample || !fieldPath.trim() || busy}>
                <Save size={15} />
                <span>{busy ? "Saving" : "Save Correction"}</span>
              </button>
              {error ? <div className="gate-error">{error}</div> : null}
            </form>
          </>
        )}
      </div>
    </section>
  );
}

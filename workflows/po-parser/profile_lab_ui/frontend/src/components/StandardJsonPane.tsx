import { Braces, CircleAlert, Pencil, Plus, Save, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { api } from "../api";
import { fieldMeta } from "../labels";
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

interface PendingCorrection {
  id: string;
  field: string;
  correct_value: string;
  note: string;
}

const itemDetailFields = ["qty", "unit", "delivery_date", "unit_price", "price_basis_qty", "amount", "currency"];

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
  const [pendingCorrections, setPendingCorrections] = useState<PendingCorrection[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const draft = sample?.merged_draft ?? {};
  const rows = flattenJson(draft).filter((row) => !row.path.startsWith("items"));
  const items = draftItems(draft);
  const blockingErrors = sample?.report?.blocking_errors ?? [];
  const correctionCount = sample?.corrections?.corrections?.length ?? 0;

  useEffect(() => {
    setError("");
    setFieldPath("");
    setCorrectValue("");
    setNote("");
    setPendingCorrections([]);
  }, [sample?.sample_key]);

  function selectCorrection(path: string, value: unknown) {
    setFieldPath(path);
    setCorrectValue(value === null || value === undefined ? "" : valueText(value));
    setNote("");
    setError("");
  }

  function addCorrectionToList() {
    const field = fieldPath.trim();
    if (!field) {
      return;
    }
    setPendingCorrections((current) => [
      ...current,
      {
        id: `${field}-${Date.now()}`,
        field,
        correct_value: correctValue,
        note
      }
    ]);
    setFieldPath("");
    setCorrectValue("");
    setNote("");
    setError("");
  }

  function removeCorrection(id: string) {
    setPendingCorrections((current) => current.filter((correction) => correction.id !== id));
  }

  async function saveCorrection(event: FormEvent) {
    event.preventDefault();
    const correctionsToSave = pendingCorrections.length
      ? pendingCorrections
      : fieldPath.trim()
        ? [{ id: "current", field: fieldPath.trim(), correct_value: correctValue, note }]
        : [];
    if (!sample || correctionsToSave.length === 0) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.saveCorrections(
        customer,
        runId,
        sample.sample_key,
        correctionsToSave.map((correction) => ({
          field: correction.field,
          correct_value: correction.correct_value,
          note: correction.note
        }))
      );
      setPendingCorrections([]);
      setFieldPath("");
      setCorrectValue("");
      setNote("");
      await onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存纠错失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="pane json-pane">
      <div className="pane-header">
        <div>
          <span className="pane-kicker">解析结果</span>
          <h2>{correctionCount ? `字段草稿 · 已保存 ${correctionCount} 条纠错` : "字段草稿"}</h2>
        </div>
        <Braces size={18} />
      </div>

      <div className="json-list">
        {rows.length === 0 && items.length === 0 ? (
          <div className="empty-pane">暂无合并后的解析草稿。</div>
        ) : (
          <>
            {items.length ? (
              <div className="items-block">
                <div className="items-title">
                  <span>采购明细</span>
                  <strong>{items.length} 行</strong>
                </div>
                <div className="items-table item-card-list" role="table" aria-label="采购明细">
                  {items.map((item, index) => (
                    <div
                      className={`item-card ${itemHasIssue(index, blockingErrors) ? "items-blocked" : ""}`}
                      role="row"
                      key={`${valueText(item.line_no)}-${index}`}
                    >
                      <div className="item-card-main">
                        <button
                          className="item-line-chip"
                          type="button"
                          role="cell"
                          onClick={() => selectCorrection(`items[${index}].line_no`, item.line_no)}
                          title="修改行号"
                        >
                          第 {tableValueText(item.line_no)} 行
                        </button>
                        <button
                          className="item-material"
                          type="button"
                          role="cell"
                          onClick={() => selectCorrection(`items[${index}].customer_material`, item.customer_material)}
                          title="修改客户物料号"
                        >
                          {tableValueText(item.customer_material)}
                        </button>
                      </div>
                      <button
                        className="item-description"
                        type="button"
                        role="cell"
                        onClick={() => selectCorrection(`items[${index}].material_description`, item.material_description)}
                        title="修改客户物料描述"
                      >
                        {tableValueText(item.material_description)}
                      </button>
                      <div className="item-card-fields">
                        {itemDetailFields.map((key) => {
                          const meta = fieldMeta(`items[${index}].${key}`);
                          return (
                            <button
                              className="item-mini-field"
                              key={key}
                              type="button"
                              role="cell"
                              onClick={() => selectCorrection(`items[${index}].${key}`, item[key])}
                              title={`修改${meta.label}`}
                            >
                              <span>{meta.label}</span>
                              <strong>{tableValueText(item[key])}</strong>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <form className="correction-editor" onSubmit={saveCorrection}>
              <div className="correction-title">
                <div>
                  <span>纠错队列</span>
                  <strong>{pendingCorrections.length ? `${pendingCorrections.length} 条待保存` : "点击字段后填写正确值，可一次保存多条"}</strong>
                </div>
                <Pencil size={16} />
              </div>
              <div className="correction-fields">
                <label>
                  <span>字段路径</span>
                  <input value={fieldPath} onChange={(event) => setFieldPath(event.target.value)} placeholder="例如 header.payment_terms" />
                </label>
                <label>
                  <span>正确值</span>
                  <input value={correctValue} onChange={(event) => setCorrectValue(event.target.value)} />
                </label>
              </div>
              <label>
                <span>给调优助手的说明</span>
                <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} />
              </label>
              <div className="correction-actions">
                <button className="queue-correction-button" type="button" onClick={addCorrectionToList} disabled={!fieldPath.trim() || busy}>
                  <Plus size={15} />
                  <span>加入列表</span>
                </button>
                <button className="save-correction-button" type="submit" disabled={!sample || busy || (!fieldPath.trim() && pendingCorrections.length === 0)}>
                  <Save size={15} />
                  <span>{busy ? "保存中" : pendingCorrections.length ? `保存 ${pendingCorrections.length} 条纠错` : "保存纠错"}</span>
                </button>
              </div>
              {pendingCorrections.length ? (
                <div className="pending-corrections" aria-label="待保存纠错">
                  {pendingCorrections.map((correction) => (
                    <div className="pending-correction-row" key={correction.id}>
                      <div>
                        <strong>{correction.field}</strong>
                        <span>{correction.correct_value || "空值"}</span>
                      </div>
                      <button type="button" onClick={() => removeCorrection(correction.id)} title={`移除 ${correction.field}`}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : null}
              {error ? <div className="gate-error">{error}</div> : null}
            </form>

            <div className="field-list-block">
              <div className="items-title">
                <span>抬头与元数据</span>
                <strong>{rows.length} 项</strong>
              </div>
              {rows.slice(0, 42).map((row, index) => {
                const blocked = hasIssue(row.path, blockingErrors);
                const meta = fieldMeta(row.path);
                return (
                  <div className={`json-row ${isHotPath(row.path) ? "json-hot" : ""} ${blocked ? "json-blocked" : ""}`} key={`${row.path}-${index}`}>
                    <div className="json-field-meta">
                      <span className="json-path">
                        {blocked ? <CircleAlert size={13} /> : null}
                        {row.path}
                      </span>
                      <strong>{meta.label}</strong>
                      <small>{meta.description}</small>
                    </div>
                    <code>{valueText(row.value)}</code>
                    <button type="button" className="field-edit-button" onClick={() => selectCorrection(row.path, row.value)} title={`修改${meta.label}`}>
                      <Pencil size={13} />
                    </button>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

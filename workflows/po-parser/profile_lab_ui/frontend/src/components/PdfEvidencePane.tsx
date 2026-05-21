import { ExternalLink, Maximize2, ScanLine, X } from "lucide-react";
import { useState } from "react";

import type { RunSample } from "../types";

interface PdfEvidencePaneProps {
  sample: RunSample | null;
}

export function PdfEvidencePane({ sample }: PdfEvidencePaneProps) {
  const [isOpen, setIsOpen] = useState(false);
  const pageImageUrl =
    sample?.page_image_url || (typeof sample?.report?.page_image_url === "string" ? sample.report.page_image_url : "");
  const pdfUrl = sample?.pdf_url ?? "";
  const pdfObjectUrl = pdfUrl ? `${pdfUrl}#toolbar=1&navpanes=0&scrollbar=1&view=FitH` : "";

  return (
    <section className="pane evidence-pane evidence-trigger-pane">
      <button className="pdf-evidence-trigger" type="button" onClick={() => setIsOpen(true)} disabled={!sample}>
        <div>
          <span className="pane-kicker">PDF证据</span>
          <h2>{sample?.source_file ?? "暂无样本"}</h2>
          <p>点击查看原始 PDF 页面</p>
        </div>
        <Maximize2 size={18} />
      </button>

      {isOpen ? (
        <div className="pdf-modal-backdrop" role="dialog" aria-modal="true" aria-label="PDF证据预览" onClick={() => setIsOpen(false)}>
          <section className="pdf-modal" onClick={(event) => event.stopPropagation()}>
            <header>
              <div>
                <span className="pane-kicker">PDF证据</span>
                <h2>{sample?.source_file ?? "暂无样本"}</h2>
              </div>
              <div className="pdf-modal-actions">
                {pdfUrl ? (
                  <a href={pdfUrl} target="_blank" rel="noreferrer" title="新窗口打开原始PDF">
                    <ExternalLink size={16} />
                    <span>打开原文件</span>
                  </a>
                ) : null}
                <button type="button" onClick={() => setIsOpen(false)} title="关闭预览">
                  <X size={18} />
                </button>
              </div>
            </header>

            <div className="pdf-modal-body">
              {pageImageUrl ? (
                <img className="evidence-image" src={pageImageUrl} alt={sample?.source_file ?? "PDF证据"} />
              ) : pdfObjectUrl ? (
                <iframe className="evidence-pdf" src={pdfObjectUrl} title={sample?.source_file ?? "PDF证据"}>
                  <a href={pdfUrl} target="_blank" rel="noreferrer">
                    {sample?.source_file ?? "打开PDF"}
                  </a>
                </iframe>
              ) : (
                <div className="pdf-placeholder" aria-label="PDF证据占位">
                  <div className="pdf-page">
                    <div className="pdf-band" />
                    <div className="pdf-line wide" />
                    <div className="pdf-line" />
                    <div className="pdf-table">
                      {Array.from({ length: 18 }).map((_, index) => (
                        <span key={index} />
                      ))}
                    </div>
                    <div className="scan-marker">
                      <ScanLine size={18} />
                      <span>{sample?.sample_key ?? "样本"}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}

import { FileText, ScanLine } from "lucide-react";

import type { RunSample } from "../types";

interface PdfEvidencePaneProps {
  sample: RunSample | null;
}

export function PdfEvidencePane({ sample }: PdfEvidencePaneProps) {
  const pageImageUrl = typeof sample?.report?.page_image_url === "string" ? sample.report.page_image_url : "";
  const pdfUrl = sample?.pdf_url ?? "";

  return (
    <section className="pane evidence-pane">
      <div className="pane-header">
        <div>
          <span className="pane-kicker">PDF Evidence</span>
          <h2>{sample?.source_file ?? "No sample"}</h2>
        </div>
        <FileText size={18} />
      </div>

      {pdfUrl ? (
        <object className="evidence-pdf" data={pdfUrl} type="application/pdf" aria-label={sample?.source_file ?? "PDF evidence"}>
          <a href={pdfUrl} target="_blank" rel="noreferrer">
            {sample?.source_file ?? "Open PDF"}
          </a>
        </object>
      ) : pageImageUrl ? (
        <img className="evidence-image" src={pageImageUrl} alt={sample?.source_file ?? "PDF evidence"} />
      ) : (
        <div className="pdf-placeholder" aria-label="PDF evidence placeholder">
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
              <span>{sample?.sample_key ?? "sample"}</span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

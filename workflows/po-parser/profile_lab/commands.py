import argparse
from pathlib import Path
from typing import Sequence

from .adjudicator import adjudicate_sample
from .customer_assets import create_run, init_customer
from .evaluator import evaluate_po_result
from .json_io import read_json, write_json
from .llm_client import create_json_client
from .paths import DEFAULT_LAB_ROOT, PRODUCTION_PROFILE_DIR
from .pdf_pages import render_pdf_pages, sample_key_from_pdf
from .publisher import PublishGateError, publish_profile
from .text_candidate import (
    extract_text_from_pdf,
    generate_text_candidate,
    generate_text_candidate_with_model,
)
from .vision_candidate import generate_vision_candidate, generate_vision_candidate_with_model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="profile-lab")
    parser.add_argument("--lab-root", default=str(DEFAULT_LAB_ROOT))
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_customer_parser = subparsers.add_parser("init-customer")
    init_customer_parser.add_argument("--customer", required=True)
    init_customer_parser.add_argument("--display-name", default=None)

    draft = subparsers.add_parser("draft")
    draft.add_argument("--customer", required=True)
    draft.add_argument("--run-id", required=True)
    draft.add_argument("--skip-render", action="store_true")
    draft.add_argument("--text-model", default=None)
    draft.add_argument("--vision-model", default=None)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--customer", required=True)
    evaluate.add_argument("--run-id", required=True)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--customer", required=True)
    publish.add_argument("--run-id", required=True)
    publish.add_argument("--production-dir", default=str(PRODUCTION_PROFILE_DIR))

    return parser


def run_draft(
    lab_root: Path,
    customer_key: str,
    run_id: str,
    skip_render: bool,
    text_model: str | None = None,
    vision_model: str | None = None,
) -> Path:
    run = create_run(root=lab_root, customer_key=customer_key, run_id=run_id)
    inputs_dir = run.run_dir / "inputs"
    customer_dir = lab_root / "customers" / customer_key
    prompt = (customer_dir / "prompt.md").read_text(encoding="utf-8")
    model_client = create_json_client() if text_model or vision_model else None

    for pdf_path in sorted(inputs_dir.glob("*.pdf")):
        sample_key = sample_key_from_pdf(pdf_path)
        page_paths: list[Path] = []
        if not skip_render:
            page_paths = render_pdf_pages(pdf_path, run.run_dir / "pages" / sample_key)

        text_path = run.run_dir / "candidates" / "text" / f"{sample_key}.json"
        vision_path = run.run_dir / "candidates" / "vision" / f"{sample_key}.json"
        if text_model and model_client:
            extracted_text = extract_text_from_pdf(pdf_path)
            text_candidate = generate_text_candidate_with_model(
                pdf_path=pdf_path,
                extracted_text=extracted_text,
                prompt=prompt,
                model=text_model,
                client=model_client,
            )
        else:
            text_candidate = generate_text_candidate(pdf_path)

        if vision_model and model_client:
            vision_candidate = generate_vision_candidate_with_model(
                pdf_path=pdf_path,
                page_paths=page_paths,
                prompt=prompt,
                model=vision_model,
                client=model_client,
            )
        else:
            vision_candidate = generate_vision_candidate(pdf_path, page_paths)

        write_json(text_path, text_candidate)
        write_json(vision_path, vision_candidate)
        adjudicate_sample(
            sample_key,
            text_candidate,
            vision_candidate,
            run.run_dir / "adjudication",
        )

    return run.run_dir


def build_missing_actual_report(sample_key: str, actual_path: Path) -> dict:
    return {
        "overall_score": 0.0,
        "publishable": False,
        "schema_pass": False,
        "p0_pass": False,
        "item_row_count_match": False,
        "scores": {"header": 0.0, "items": 0.0, "p1": 0.0, "business_rules": 0.0},
        "blocking_errors": [
            {
                "field": "actual",
                "expected": str(actual_path),
                "actual": None,
                "reason": "actual merged draft missing",
            }
        ],
        "recommendation": "not_publishable",
        "sample_key": sample_key,
        "report_path": f"{sample_key}.report.json",
    }


def format_evaluation_summary_markdown(
    customer_key: str,
    run_id: str,
    sample_reports: list[dict],
    publishable: bool,
) -> str:
    lines = [
        f"# Evaluation Summary: {customer_key} / {run_id}",
        "",
        f"- Sample count: {len(sample_reports)}",
        f"- Publishable: {publishable}",
    ]
    if not sample_reports:
        lines.extend(["", "No expected files found."])
    else:
        lines.extend(["", "## Samples"])
        for report in sample_reports:
            sample_key = report["sample_key"]
            report_publishable = report["publishable"]
            line = f"- {sample_key}: publishable={report_publishable}"
            if not report_publishable and report.get("blocking_errors"):
                line += f" - {report['blocking_errors'][0]['reason']}"
            lines.append(line)
    return "\n".join(lines) + "\n"


def run_evaluate(lab_root: Path, customer_key: str, run_id: str) -> Path:
    customer_dir = lab_root / "customers" / customer_key
    run_dir = customer_dir / "runs" / run_id
    expected_dir = customer_dir / "expected"
    adjudication_dir = run_dir / "adjudication"
    evaluation_dir = run_dir / "evaluation"
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    sample_reports = []
    for sample_key in sample_keys_for_evaluation(run_dir, expected_dir):
        expected_path = expected_dir / f"{sample_key}.json"
        actual_path = adjudication_dir / f"{sample_key}.merged_draft.json"
        if expected_path.exists() and actual_path.exists():
            report = evaluate_po_result(
                expected=read_json(expected_path),
                actual=read_json(actual_path),
            )
            report["sample_key"] = sample_key
            report["report_path"] = f"{sample_key}.report.json"
            report["expected_missing"] = False
        elif expected_path.exists():
            report = build_missing_actual_report(sample_key, actual_path)
        elif actual_path.exists():
            report = evaluate_draft_quality(sample_key, actual_path)
        else:
            report = build_missing_actual_report(sample_key, actual_path)
        write_json(evaluation_dir / f"{sample_key}.report.json", report)
        sample_reports.append(report)

    publishable = bool(sample_reports) and all(report["publishable"] for report in sample_reports)
    summary = {
        "customer": customer_key,
        "run_id": run_id,
        "sample_count": len(sample_reports),
        "publishable": publishable,
        "reports": sample_reports,
    }
    write_json(evaluation_dir / "summary.json", summary)
    (evaluation_dir / "summary.md").write_text(
        format_evaluation_summary_markdown(
            customer_key=customer_key,
            run_id=run_id,
            sample_reports=sample_reports,
            publishable=publishable,
        ),
        encoding="utf-8",
    )
    return evaluation_dir


def sample_keys_for_evaluation(run_dir: Path, expected_dir: Path) -> list[str]:
    manifest_path = run_dir / "manifest.json"
    keys = []
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        keys.extend(sample_key_from_pdf(Path(sample)) for sample in manifest.get("samples", []))
    keys.extend(path.stem for path in sorted(expected_dir.glob("*.json")))
    return sorted(dict.fromkeys(keys))


def evaluate_draft_quality(sample_key: str, actual_path: Path) -> dict:
    actual = read_json(actual_path)
    report = evaluate_po_result(expected=actual, actual=actual)
    report["publishable"] = False
    report["expected_missing"] = True
    report["recommendation"] = "confirm_expected"
    report["sample_key"] = sample_key
    report["report_path"] = f"{sample_key}.report.json"
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    lab_root = Path(args.lab_root)

    if args.command == "init-customer":
        result = init_customer(
            root=lab_root,
            customer_key=args.customer,
            display_name=args.display_name,
        )
        print(f"initialized customer assets: {result.customer_dir}")
        return 0

    if args.command == "draft":
        run_dir = run_draft(
            lab_root=lab_root,
            customer_key=args.customer,
            run_id=args.run_id,
            skip_render=args.skip_render,
            text_model=args.text_model,
            vision_model=args.vision_model,
        )
        print(f"created draft run: {run_dir}")
        return 0

    if args.command == "evaluate":
        evaluation_dir = run_evaluate(
            lab_root=lab_root,
            customer_key=args.customer,
            run_id=args.run_id,
        )
        print(f"wrote evaluation: {evaluation_dir}")
        return 0

    if args.command == "publish":
        try:
            output_path = publish_profile(
                root=lab_root,
                customer_key=args.customer,
                run_id=args.run_id,
                production_dir=Path(args.production_dir),
            )
        except PublishGateError as error:
            print(error)
            return 1
        print(f"published profile: {output_path}")
        return 0

    parser.error(f"unsupported command reached: {args.command}")
    return 2

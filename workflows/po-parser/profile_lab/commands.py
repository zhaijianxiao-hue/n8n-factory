import argparse
from pathlib import Path
from typing import Sequence

from .adjudicator import adjudicate_sample
from .customer_assets import create_run, init_customer
from .json_io import write_json
from .paths import DEFAULT_LAB_ROOT
from .pdf_pages import render_pdf_pages, sample_key_from_pdf
from .text_candidate import generate_text_candidate
from .vision_candidate import generate_vision_candidate


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

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--customer", required=True)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--customer", required=True)

    return parser


def run_draft(
    lab_root: Path,
    customer_key: str,
    run_id: str,
    skip_render: bool,
) -> Path:
    run = create_run(root=lab_root, customer_key=customer_key, run_id=run_id)
    inputs_dir = run.run_dir / "inputs"

    for pdf_path in sorted(inputs_dir.glob("*.pdf")):
        sample_key = sample_key_from_pdf(pdf_path)
        page_paths: list[Path] = []
        if not skip_render:
            page_paths = render_pdf_pages(pdf_path, run.run_dir / "pages" / sample_key)

        text_path = run.run_dir / "candidates" / "text" / f"{sample_key}.json"
        vision_path = run.run_dir / "candidates" / "vision" / f"{sample_key}.json"
        text_candidate = generate_text_candidate(pdf_path)
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
        )
        print(f"created draft run: {run_dir}")
        return 0

    parser.error(f"unsupported command reached: {args.command}")
    return 2

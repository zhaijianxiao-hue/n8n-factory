import argparse
from pathlib import Path
from typing import Sequence

from .adjudicator import adjudicate_sample
from .customer_assets import create_run, init_customer
from .json_io import write_json
from .llm_client import OpenAICompatibleJsonClient
from .paths import DEFAULT_LAB_ROOT
from .pdf_pages import render_pdf_pages, sample_key_from_pdf
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

    publish = subparsers.add_parser("publish")
    publish.add_argument("--customer", required=True)

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
    model_client = OpenAICompatibleJsonClient() if text_model or vision_model else None

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

    parser.error(f"unsupported command reached: {args.command}")
    return 2

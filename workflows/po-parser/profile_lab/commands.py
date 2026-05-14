import argparse
from pathlib import Path
from typing import Sequence

from .customer_assets import init_customer
from .paths import DEFAULT_LAB_ROOT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="profile-lab")
    parser.add_argument("--lab-root", default=str(DEFAULT_LAB_ROOT))
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_customer_parser = subparsers.add_parser("init-customer")
    init_customer_parser.add_argument("--customer", required=True)
    init_customer_parser.add_argument("--display-name", default=None)

    draft = subparsers.add_parser("draft")
    draft.add_argument("--customer", required=True)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--customer", required=True)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--customer", required=True)

    return parser


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

    parser.error(f"unsupported command reached: {args.command}")
    return 2

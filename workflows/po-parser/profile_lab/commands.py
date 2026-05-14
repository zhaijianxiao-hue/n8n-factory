import argparse
from typing import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="profile-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_customer = subparsers.add_parser("init-customer")
    init_customer.add_argument("--customer", required=True)
    init_customer.add_argument("--display-name", default=None)

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
    parser.error(f"unsupported command reached: {args.command}")
    return 2

import argparse
import sys
import traceback

from docqa_rag import embeddings
from docqa_rag.config import require_env
from docqa_rag.ingest import ingest


def _run_ingest(args: argparse.Namespace) -> None:
    require_env("OPENAI_API_KEY")
    s = ingest(embeddings.embed, args.rebuild)
    print(
        f"{s.files} files: {s.indexed} indexed ({s.chunks} chunks), "
        f"{s.unchanged} unchanged, {s.removed} removed"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="docqa",
        description="Question answering over local markdown documents.",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--verbose", action="store_true", help="show tracebacks on errors"
    )
    subparsers = parser.add_subparsers(dest="command")
    ingest_parser = subparsers.add_parser(
        "ingest",
        parents=[common],
        help="index ./knowledge/ into ./.docqa",
    )
    ingest_parser.add_argument(
        "--rebuild", action="store_true", help="empty the index before ingesting"
    )
    args = parser.parse_args()

    if args.command != "ingest":
        parser.print_help()
        return
    try:
        _run_ingest(args)
    except Exception as e:  # noqa: BLE001 - top-level handler, prints and exits 1
        if args.verbose:
            traceback.print_exc()
        print(f"docqa: {e}", file=sys.stderr)
        sys.exit(1)

import argparse
import os
import sys
import textwrap
import traceback

from docqa_rag import embeddings, store
from docqa_rag.config import TOP_K, require_env
from docqa_rag.ingest import ingest


def _run_ingest(args: argparse.Namespace) -> None:
    require_env("OPENAI_API_KEY")
    s = ingest(embeddings.embed, args.rebuild)
    print(
        f"{s.files} files: {s.indexed} indexed ({s.chunks} chunks), "
        f"{s.unchanged} unchanged, {s.removed} removed"
    )


def _positive_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer: {value!r}") from None
    if n < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return n


def _format_result(rank: int, r: store.SearchResult) -> str:
    lines = [f"[{rank}] {r.score:.3f}  {os.path.relpath(r.source)}"]
    if r.heading_path:
        lines.append(f"    {r.heading_path}")
    lines.append(textwrap.indent(r.text, "    "))
    return "\n".join(lines)


def _run_search(args: argparse.Namespace) -> None:
    require_env("OPENAI_API_KEY")
    collection = store.existing_collection()
    vector = embeddings.embed([args.query])[0]
    results = store.query(collection, vector, args.top_k)
    print("\n\n".join(_format_result(i, r) for i, r in enumerate(results, 1)))


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
    search_parser = subparsers.add_parser(
        "search",
        parents=[common],
        help="show the chunks closest to a query",
    )
    search_parser.add_argument("query", help="text to search for")
    search_parser.add_argument(
        "--top-k",
        type=_positive_int,
        default=TOP_K,
        help=f"number of chunks to return (default {TOP_K})",
    )
    args = parser.parse_args()

    if args.command not in ("ingest", "search"):
        parser.print_help()
        return
    try:
        if args.command == "ingest":
            _run_ingest(args)
        elif args.command == "search":
            _run_search(args)
    except Exception as e:  # top-level handler, prints and exits 1
        if args.verbose:
            traceback.print_exc()
        print(f"docqa: {e}", file=sys.stderr)
        sys.exit(1)

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="docqa",
        description="Question answering over local markdown documents.",
    )
    parser.parse_args()
    parser.print_help()

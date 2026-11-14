"""Where every value the model uses comes from: `python -m xmart_analysis.provenance [--check] [--markdown]`."""

import argparse
import sys
from collections import Counter

from .engine import tables


def render_markdown(rows, sources):
    lines = ["| Table | Item | Status | Source | Note |", "| --- | --- | --- | --- | --- |"]
    lines += [f"| {r['table']} | {r['item']} | {r['status']} | {r['source_ref']} | {r['note']} |" for r in rows]
    lines += ["", "| Source | Title | Publisher | URL |", "| --- | --- | --- | --- |"]
    lines += [f"| {k} | {v['title']} | {v['publisher']} | {v['url']} |" for k, v in sources.items()]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m xmart_analysis.provenance")
    parser.add_argument("--check", action="store_true", help="exit with an error if a value lacks a status or source")
    parser.add_argument("--markdown", action="store_true", help="print the full provenance table")
    args = parser.parse_args(argv)
    rows, problems = tables.provenance(), tables.validate()
    if args.markdown:
        print(render_markdown(rows, tables.sources()))
    else:
        counts = Counter(r["status"] for r in rows)
        print(f"{len(rows)} values: " + ", ".join(f"{n} {k}" for k, n in sorted(counts.items())))
        used = Counter(ref for r in rows for ref in r["source_ref"].split(";") if ref)
        for ref, n in used.most_common():
            print(f"  {n:3d}  {ref}: {tables.sources()[ref]['title']}")
    for problem in problems:
        print("PROBLEM:", problem, file=sys.stderr)
    return 1 if (args.check and problems) else 0


if __name__ == "__main__":
    sys.exit(main())

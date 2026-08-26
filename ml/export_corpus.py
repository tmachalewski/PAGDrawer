"""GML-0 CLI — build an ML corpus from Trivy scan JSON files.

Loads one or more Trivy scans through the existing TrivyDataLoader (enriching
from the NVD/EPSS/CWE caches), unions their CVEs, and writes the deduplicated
``enables`` corpus + diagnostics as JSON.

Enrichment needs the Mongo caches populated (run the backend once against the
scans, or use ``ignore_ttl`` to reuse an old cache offline). For a pure,
Mongo-free path, import ``ml.exporter.build_corpus`` directly with your own
CVE dicts — that is what the unit tests do.

Usage:
    python -m ml.export_corpus examples/**/*.json -o ml/out/corpus.json
    python -m ml.export_corpus scan1.json scan2.json --no-enrich -o corpus.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Any, Dict, List

from ml.exporter import build_corpus


def _load_cves(paths: List[str], enrich: bool, ignore_ttl: bool) -> List[Dict[str, Any]]:
    """Load + enrich CVEs from Trivy scan files via the existing loader."""
    from src.data.loaders.trivy_loader import TrivyDataLoader

    # Enrichment reads the NVD/EPSS/CWE Mongo caches; the standalone CLI must
    # initialize the connection itself (the backend does this on startup).
    if enrich:
        from src.data.mongo_client import init_mongo
        init_mongo()

    all_cves: List[Dict[str, Any]] = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            trivy_json = json.load(fh)
        # Skip files that aren't Trivy reports (e.g. our metrics exports)
        if not (trivy_json.get("Results") or trivy_json.get("results")):
            print(f"  skip (not a Trivy report): {path}", file=sys.stderr)
            continue
        loader = TrivyDataLoader(
            source=trivy_json,
            enrich_from_nvd=enrich,
            enrich_cwe=enrich,
            ignore_ttl=ignore_ttl,
        )
        data = loader.load()
        all_cves.extend(data.cves)
        print(f"  {os.path.basename(path)}: {len(data.cves)} CVEs", file=sys.stderr)
    return all_cves


def _expand(patterns: List[str]) -> List[str]:
    out: List[str] = []
    for p in patterns:
        matches = glob.glob(p, recursive=True)
        out.extend(matches if matches else [p])
    # de-dup, keep order
    seen = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the Graph-ML enables corpus from Trivy scans.")
    ap.add_argument("scans", nargs="+", help="Trivy scan JSON files or globs")
    ap.add_argument("-o", "--out", default="ml/out/corpus.json", help="output JSON path")
    ap.add_argument("--no-enrich", action="store_true", help="skip NVD/CWE enrichment")
    ap.add_argument("--ignore-ttl", action="store_true", help="accept cached NVD/EPSS/CWE regardless of age")
    ap.add_argument("--self-loops", action="store_true", help="keep enables self-loops")
    ap.add_argument("--label-date", default=None, help="EPSS label snapshot date (YYYY-MM-DD) for provenance")
    args = ap.parse_args(argv)

    paths = _expand(args.scans)
    print(f"Loading {len(paths)} file(s)...", file=sys.stderr)
    cves = _load_cves(paths, enrich=not args.no_enrich, ignore_ttl=args.ignore_ttl)
    print(f"Total CVE records before dedup: {len(cves)}", file=sys.stderr)

    meta = {
        "source_files": [os.path.basename(p) for p in paths],
        "enriched": not args.no_enrich,
        "label_snapshot_date": args.label_date,
    }
    corpus = build_corpus(cves, include_self_loops=args.self_loops, meta=meta)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(corpus.to_dict(), fh, indent=2)

    d = corpus.diagnostics
    print(f"\nWrote {args.out}", file=sys.stderr)
    print(f"  nodes={d.node_count} edges={d.edge_count} "
          f"isolated={d.isolated_node_count} ({d.isolated_node_share:.1%})", file=sys.stderr)
    print(f"  quotient classes={d.quotient_class_count} "
          f"(largest: {d.largest_quotient_classes[0] if d.largest_quotient_classes else 'n/a'})",
          file=sys.stderr)
    print(f"  no-prereq={d.no_prereq_count} no-outcome={d.no_outcome_count} "
          f"self-loops={d.self_loop_count}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

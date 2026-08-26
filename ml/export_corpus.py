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


def _load_images(paths: List[str], enrich: bool, ignore_ttl: bool) -> Dict[str, List[Dict[str, Any]]]:
    """Load + enrich CVEs per Trivy scan file, keyed by image name.

    One scan file = one Docker image = one graph in the corpus.
    """
    from src.data.loaders.trivy_loader import TrivyDataLoader

    # Enrichment reads the NVD/EPSS/CWE Mongo caches; the standalone CLI must
    # initialize the connection itself (the backend does this on startup).
    if enrich:
        from src.data.mongo_client import init_mongo
        init_mongo()

    images: Dict[str, List[Dict[str, Any]]] = {}
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            trivy_json = json.load(fh)
        # Skip files that aren't Trivy reports (e.g. our metrics exports)
        if not (trivy_json.get("Results") or trivy_json.get("results")):
            print(f"  skip (not a Trivy report): {path}", file=sys.stderr)
            continue
        image = trivy_json.get("ArtifactName") or os.path.splitext(os.path.basename(path))[0]
        loader = TrivyDataLoader(
            source=trivy_json,
            enrich_from_nvd=enrich,
            enrich_cwe=enrich,
            ignore_ttl=ignore_ttl,
        )
        data = loader.load()
        if not data.cves:
            print(f"  skip (0 CVEs): {os.path.basename(path)}", file=sys.stderr)
            continue
        # If two files map to the same image name, merge their CVEs.
        images.setdefault(image, []).extend(data.cves)
        print(f"  {image}: {len(data.cves)} CVEs", file=sys.stderr)
    return images


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
    ap.add_argument("--label-date", default=None, help="EPSS label snapshot date (YYYY-MM-DD) for provenance")
    args = ap.parse_args(argv)

    paths = _expand(args.scans)
    print(f"Loading {len(paths)} file(s)...", file=sys.stderr)
    images = _load_images(paths, enrich=not args.no_enrich, ignore_ttl=args.ignore_ttl)
    print(f"Images with CVEs: {len(images)}", file=sys.stderr)

    meta = {
        "source_files": [os.path.basename(p) for p in paths],
        "enriched": not args.no_enrich,
        "label_snapshot_date": args.label_date,
        "scenario": "maximal (AV:N,PR:N baseline; AC/UI unfiltered)",
    }
    corpus = build_corpus(images, meta=meta)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(corpus.to_dict(), fh, indent=2)

    d = corpus.diagnostics
    print(f"\nWrote {args.out}", file=sys.stderr)
    print(f"  images={d.image_count}  node-occurrences={d.total_nodes}  "
          f"unique CVEs={d.unique_cves}  edges={d.total_edges}", file=sys.stderr)
    print(f"  all DAGs? {d.all_dags}   unreachable share={d.unreachable_share:.1%}", file=sys.stderr)
    print(f"  depth histogram (depth: nodes): {d.depth_histogram}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

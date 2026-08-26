"""GML-1 — EPSS label snapshot handling.

Per D9/D15 the ML target comes from one FIRST **daily CSV snapshot**
(`epss_scores-YYYY-MM-DD.csv.gz`), not the per-CVE API/cache (which mixes
model dates). The file carries a ``percentile`` column — exactly the D15
target — plus a header line with the model version and score date for
provenance. One atomic file gives every CVE in the corpus a label from the
same model date, and it is archived alongside each training run.

Functions:
  * ``download_snapshot(date, dest)`` — fetch + save the gz file (pure I/O).
  * ``load_snapshot(path)`` — parse header + rows → EpssSnapshot.
  * ``attach_labels(corpus_dict, snapshot)`` — join percentile/epss onto every
    node occurrence by CVE id; report coverage.
"""

from __future__ import annotations

import csv
import gzip
import io
import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from urllib.request import urlopen

# FIRST publishes the full daily model here (host as of 2024+).
SNAPSHOT_URL = "https://epss.empiricalsecurity.com/epss_scores-{date}.csv.gz"


@dataclass
class EpssSnapshot:
    """One day's EPSS model: cve -> (epss, percentile), plus provenance."""
    score_date: str
    model_version: str
    scores: Dict[str, Tuple[float, float]] = field(default_factory=dict)  # cve -> (epss, pct)

    def get(self, cve_id: str) -> Optional[Tuple[float, float]]:
        return self.scores.get(cve_id.upper())

    def __len__(self) -> int:
        return len(self.scores)


def download_snapshot(date: str, dest: str) -> str:
    """Download the FIRST daily snapshot for ``date`` (YYYY-MM-DD) to ``dest``.

    Returns the path written. Raises on HTTP/URL errors.
    """
    url = SNAPSHOT_URL.format(date=date)
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with urlopen(url, timeout=60) as resp:
        data = resp.read()
    with open(dest, "wb") as fh:
        fh.write(data)
    return dest


def _parse_csv_bytes(raw: bytes) -> EpssSnapshot:
    """Parse the (decompressed) FIRST CSV bytes into an EpssSnapshot.

    Format::

        #model_version:v2026.06.15,score_date:2026-08-21T12:03:15Z
        cve,epss,percentile
        CVE-1999-0001,0.03351,0.87749
    """
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()

    model_version = ""
    score_date = ""
    if lines and lines[0].startswith("#"):
        meta = lines[0].lstrip("#")
        for part in meta.split(","):
            if ":" in part:
                k, v = part.split(":", 1)
                k = k.strip()
                if k == "model_version":
                    model_version = v.strip()
                elif k == "score_date":
                    score_date = v.strip()
        lines = lines[1:]

    scores: Dict[str, Tuple[float, float]] = {}
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    for row in reader:
        cve = (row.get("cve") or "").upper()
        if not cve:
            continue
        try:
            epss = float(row.get("epss", ""))
            pct = float(row.get("percentile", ""))
        except (TypeError, ValueError):
            continue
        scores[cve] = (epss, pct)

    return EpssSnapshot(score_date=score_date, model_version=model_version, scores=scores)


def load_snapshot(path: str) -> EpssSnapshot:
    """Load a FIRST snapshot from a .csv.gz (or plain .csv) file."""
    with open(path, "rb") as fh:
        blob = fh.read()
    if path.endswith(".gz"):
        blob = gzip.decompress(blob)
    return _parse_csv_bytes(blob)


@dataclass
class LabelJoinReport:
    total_nodes: int
    labeled_nodes: int
    unique_cves: int
    labeled_cves: int
    missing_cves: list

    @property
    def coverage(self) -> float:
        return self.labeled_cves / self.unique_cves if self.unique_cves else 0.0


def attach_labels(corpus: dict, snapshot: EpssSnapshot) -> LabelJoinReport:
    """Overwrite each node's ``epss_score`` with the snapshot value and add a
    ``epss_percentile`` field (the D15 target). Mutates ``corpus`` in place.

    Returns a coverage report. CVEs absent from the snapshot keep whatever
    ``epss_score`` they had and get ``epss_percentile = None`` — the caller
    decides whether to drop them.
    """
    seen_cves: set = set()
    labeled_cves: set = set()
    missing: set = set()
    total = 0
    labeled = 0

    for g in corpus.get("graphs", []):
        for n in g.get("nodes", []):
            total += 1
            cid = (n.get("cve_id") or "").upper()
            seen_cves.add(cid)
            hit = snapshot.get(cid)
            if hit is not None:
                epss, pct = hit
                n["epss_score"] = epss
                n["epss_percentile"] = pct
                labeled += 1
                labeled_cves.add(cid)
            else:
                n["epss_percentile"] = None
                missing.add(cid)

    corpus.setdefault("meta", {})["epss_snapshot"] = {
        "score_date": snapshot.score_date,
        "model_version": snapshot.model_version,
        "snapshot_size": len(snapshot),
    }

    return LabelJoinReport(
        total_nodes=total,
        labeled_nodes=labeled,
        unique_cves=len(seen_cves),
        labeled_cves=len(labeled_cves),
        missing_cves=sorted(missing),
    )

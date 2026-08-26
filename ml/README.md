# Graph-ML: EPSS prediction (experiment phase)

Implements the experiment stages of
[`Docs/Plans/GraphML_EPSS_Prediction.md`](../Docs/Plans/GraphML_EPSS_Prediction.md).
Per **D16**, this phase is plain scripts — no container, no FastAPI service.
The serving module (GML-3) is built only after the experiment gate.

## Layout

| File | Stage | Role |
|------|-------|------|
| `exporter.py` | GML-0 | Pure corpus builder: dedup, `enables` edges, diagnostics. No Mongo/network. |
| `export_corpus.py` | GML-0 | CLI: load Trivy scans → enrich → write `corpus.json` + diagnostics. |
| (next) `labels.py` | GML-1 | Join a FIRST daily EPSS snapshot as the percentile target. |
| (next) `train.py` | GML-1/2 | XGBoost + GNN rungs, TensorBoard logging. |

## The `enables` relation

`a → b` iff `outcomes(a)` satisfy `prereqs(b)`, using the single source of
truth `src/core/consensual_matrix.prereqs_satisfied` (the same predicate the
graph builder uses — it now delegates here). No attacker baseline is assumed,
so the pairwise relation is **stricter** than in-context reachability: a
`PR:H` prerequisite is met only if the enabler actually grants a `PR:H` (or
higher) Vector Changer. This is the literal reading of the plan's
`outcomes(a) ⊨ prereqs(b)` and keeps the exporter faithful to §9.

## Build a corpus

Pure (no Mongo) — for tests or your own CVE dicts:

```python
from ml.exporter import build_corpus
corpus = build_corpus(cve_dicts)          # cve_dicts = loader output
corpus.to_dict()                          # JSON-ready
```

From Trivy scans (needs the NVD/EPSS/CWE Mongo caches populated; start Mongo
with `bash Scripts/start-mongo.sh`):

```bash
python -m ml.export_corpus "examples/05_concrete_scans_01/**/*.json" \
    --ignore-ttl --label-date 2026-08-21 -o ml/out/corpus.json
```

`--ignore-ttl` reuses an aged cache offline (see MongoDBPersistence.md).
`--no-enrich` skips NVD/CWE lookups (structure only, sparse features).

## Diagnostics (GML-0 acceptance)

Every export includes a `diagnostics` block: node/edge counts, isolated-node
share, degree histograms, and the **quotient-class census** — how many
distinct `(prereq_key, outcome_key)` classes exist and the largest ones.
Per **D13** this census is a *diagnostic*, not a kill-gate: it characterizes
how much of the graph's structure is determined by the VC keys, informing the
A4 class-aggregate ablation later.

## Tests

```bash
PAGDRAWER_SKIP_MONGO=1 venv/Scripts/python.exe -m pytest tests/test_ml_exporter.py -q
```

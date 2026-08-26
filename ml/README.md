# Graph-ML: EPSS prediction (experiment phase)

Implements the experiment stages of
[`Docs/Plans/GraphML_EPSS_Prediction.md`](../Docs/Plans/GraphML_EPSS_Prediction.md).
Per **D16**, this phase is plain scripts — no container, no FastAPI service.
The serving module (GML-3) is built only after the experiment gate.

## Layout

| File | Stage | Role |
|------|-------|------|
| `../src/core/chain.py` | shared | Single-source chain primitives: `escalating_outcomes`, `assign_chain_depths`, `contributes`. The builder and the exporter both use these. |
| `exporter.py` | GML-0 | Pure corpus builder: **per-image DAGs**, depth-layered chains, contribution edges, diagnostics. No Mongo/network. |
| `export_corpus.py` | GML-0 | CLI: load Trivy scans → enrich → write `corpus.json` (set of image graphs). |
| `diagnose.py` | GML-0.5 | Structure↔EPSS analysis (Spearman of degree/depth, η² of classes, per-image density). |
| (next) `labels.py` | GML-1 | Join a FIRST daily EPSS snapshot as the percentile target. |
| (next) `train.py` | GML-1/2 | XGBoost + GNN rungs, TensorBoard logging. |

## Data structure — set of per-image DAGs

The corpus is **one directed acyclic graph per Docker image** (confirmed
vision, 2026-08-26). Chaining happens ONLY between CVEs that co-occur on the
same image — reality-pruning by the container. The same CVE appears in several
image graphs; that is expected and the train/val/test split must group by
`original_cve` so a CVE never straddles folds.

Each image graph is built by the builder's chain logic (`core.chain`):
- **Baseline**: the attacker starts from `{(AV,N),(PR,N)}` — network reach, no
  privileges (the fixed **maximal scenario** for AV/PR).
- **Depth-layered BFS**: admit every CVE whose AV/PR prereqs are met, accumulate
  their **escalating** outcomes (only VCs that strictly raise capability), advance
  a depth. Capability is never lost → the graph is a DAG.
- **Edges** are CVE→CVE *contribution* edges: `a → b` when `depth(a) < depth(b)`
  and a's escalating outcomes supply a Vector Changer b's prereqs require.
  Layer-skipping is allowed (a depth-0 CVE can contribute to a depth-2 CVE —
  "VCs from CVE1 enable CVE3").

## Vector Changers

- **State VCs (AV, PR, EX)** — gate reachability (prereqs) and accumulate
  (outcomes). They build the graph topology.
- **Environmental VCs (AC, UI)** — the **input scenario**: AC = attacker skill,
  UI = whether the user cooperates. Categorical, not numeric; they don't change
  along the chain and don't gate the AV/PR BFS. Here they are per-node
  **features** (`ac`, `ui`), and the scenario is fixed maximal.

## Build a corpus

Pure (no Mongo) — for tests or your own CVE dicts, keyed by image:

```python
from ml.exporter import build_corpus
corpus = build_corpus({"nginx:...": cve_dicts, "redis:...": more_dicts})
corpus.to_dict()                          # JSON-ready
```

From Trivy scans (needs the NVD/EPSS/CWE Mongo caches; start Mongo with
`bash Scripts/start-mongo.sh`):

```bash
python -m ml.export_corpus "examples/*.json" \
    --ignore-ttl --label-date 2026-08-21 -o ml/out/corpus.json
python -m ml.diagnose ml/out/corpus.json
```

`--ignore-ttl` reuses an aged cache offline (see MongoDBPersistence.md).

## Diagnostics

`export_corpus` prints per-image node/edge counts, the depth histogram, and
**verifies every image graph is a DAG**. `diagnose.py` then reports the
structure↔EPSS signal (Spearman of in/out-degree and chain-depth vs EPSS),
η² of the quotient classes, and per-image density — the numbers that decide
how much GNN effort the ladder warrants.

## Tests

```bash
PAGDRAWER_SKIP_MONGO=1 venv/Scripts/python.exe -m pytest tests/test_ml_exporter.py -q
```

# Graph Quality Metrics for ESORICS Paper — Implementation Guide

## Goal

Add three automated graph quality metrics to Table 2 in the PAGDrawer paper, computed at each of the 6 progressive reduction steps. This strengthens the evaluation from "we counted nodes and edges" to "we measured drawing quality improvement."

---

## Three Metrics to Compute

### 1. Edge Crossings (normalized, [0,1], higher = better)

**What:** The fraction of edge pairs that do NOT cross, normalized so 1 = no crossings and 0 = maximum crossings.

**Why:** Most validated readability factor in graph drawing. Universally understood: fewer crossings = easier to read.

**Source:** Purchase, H.C. (2002). "Metrics for Graph Drawing Aesthetics." Journal of Visual Languages and Computing, 13(5), 501–516.

### 2. Drawing Area

**What:** Bounding box area (width × height) of the graph layout in pixels or logical units.

**Why:** Shows the graph gets physically more compact at each step. Less screen real estate = less visual scanning.

**How to compute:** `area = (max_x - min_x) * (max_y - min_y)` across all visible node positions. Optionally account for node dimensions.

**Source:** Purchase (2002), same as above.

### 3. Edge Length Coefficient of Variation

**What:** Standard deviation of edge lengths divided by their mean. Lower = more uniform edge lengths.

**Why:** High variance means some edges are very long (hard to trace) and some very short (hard to see). Uniform lengths make the graph visually predictable.

**How to compute:** For each edge, compute Euclidean distance between source and target positions. Then: `CV = std(lengths) / mean(lengths)`.

**Source:** Purchase (2002); also used in Di Bartolomeo et al. (2024). "Evaluating Graph Layout Algorithms: A Systematic Review." Computer Graphics Forum.

---

## Library: greadability.js

**Repository:** https://github.com/rpgove/greadability

**Not on npm.** Must be downloaded directly from the repo.

**What it provides out of the box:**
- `crossing` — normalized edge crossings [0,1], higher = fewer crossings
- `crossingAngle` — mean deviation from ideal 70° crossing angle [0,1]
- `angularResolutionMin` — deviation from ideal minimum angle per node [0,1]
- `angularResolutionDev` — average angle deviation between incident edges [0,1]

**What it does NOT provide** (must compute manually):
- Drawing area
- Edge length coefficient of variation

### Input format

The library expects:
- `nodes`: array of objects, each with `x` and `y` properties
- `links`: array of objects, each with `source` and `target` properties (either node objects or indices)

```javascript
const greadability = require('./greadability.js');

const result = greadability.greadability(nodes, links);
// Returns: { crossing: 0.95, crossingAngle: 0.7, angularResolutionMin: 0.34, angularResolutionDev: 0.56 }
```

### How to get data from Cytoscape.js

In PAGDrawer's frontend, after each layout completes:

```javascript
// Extract node positions
const nodes = cy.nodes(':visible').map((n, i) => ({
  index: i,
  id: n.id(),
  x: n.position('x'),
  y: n.position('y'),
  w: n.width(),
  h: n.height()
}));

// Extract edges with source/target as objects
const nodeById = {};
nodes.forEach(n => { nodeById[n.id] = n; });

const links = cy.edges(':visible').map(e => ({
  source: nodeById[e.source().id()],
  target: nodeById[e.target().id()]
}));
```

### Computing the three ESORICS metrics

```javascript
const greadability = require('./greadability.js');

// 1. Edge crossings (from greadability.js)
const metrics = greadability.greadability(nodes, links);
const crossingScore = metrics.crossing; // [0,1], higher = fewer crossings

// 2. Drawing area (manual)
const xs = nodes.map(n => n.x);
const ys = nodes.map(n => n.y);
const area = (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys));

// 3. Edge length coefficient of variation (manual)
const lengths = links.map(l => {
  const dx = l.source.x - l.target.x;
  const dy = l.source.y - l.target.y;
  return Math.sqrt(dx * dx + dy * dy);
});
const mean = lengths.reduce((a, b) => a + b, 0) / lengths.length;
const std = Math.sqrt(lengths.reduce((s, l) => s + (l - mean) ** 2, 0) / lengths.length);
const edgeLengthCV = mean > 0 ? std / mean : 0;
```

### Alternative: compute everything from scratch without greadability.js

If integrating the library is awkward, the edge crossing computation is ~40 lines of code:

```javascript
// Line segment intersection test
function segmentsIntersect(x1, y1, x2, y2, x3, y3, x4, y4) {
  const d1 = direction(x3, y3, x4, y4, x1, y1);
  const d2 = direction(x3, y3, x4, y4, x2, y2);
  const d3 = direction(x1, y1, x2, y2, x3, y3);
  const d4 = direction(x1, y1, x2, y2, x4, y4);
  if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
      ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))) {
    return true;
  }
  return false;
}

function direction(xi, yi, xj, yj, xk, yk) {
  return (xk - xi) * (yj - yi) - (xj - xi) * (yk - yi);
}

// Count crossings (skip edges sharing a node)
function countCrossings(nodes, links) {
  let crossings = 0;
  for (let i = 0; i < links.length; i++) {
    for (let j = i + 1; j < links.length; j++) {
      const a = links[i], b = links[j];
      // Skip if edges share a node
      if (a.source === b.source || a.source === b.target ||
          a.target === b.source || a.target === b.target) continue;
      if (segmentsIntersect(
        a.source.x, a.source.y, a.target.x, a.target.y,
        b.source.x, b.source.y, b.target.x, b.target.y
      )) {
        crossings++;
      }
    }
  }
  return crossings;
}
```

---

## Where to run this

**Option A (recommended):** Add a temporary "export metrics" button or console command to PAGDrawer's frontend. At each of the 6 steps, click it to dump the metrics to console. Copy the numbers into the paper.

**Option B:** Export Cytoscape.js layout data as JSON at each step (node positions + edge list), then run a standalone Node.js script that loads the JSON and computes the metrics.

**Option C:** If you already have screenshots/figures for each step, you could extract approximate node positions from the SVG/PDF exports programmatically, but this is more work than Option A or B.

---

## Expected output format for the paper

Add three columns to the existing Table 2:

| Step | Config | N | E | ΔN | ΔE | Cross. | Area (×10³) | EL-CV |
|------|--------|---|---|----|----|--------|-------------|-------|
| 1 | Original | 67 | 88 | — | — | ? | ? | ? |
| 2 | VC→HOST | 47 | 68 | −20 | −20 | ? | ? | ? |
| 3 | Exploit paths | 34 | 54 | −13 | −14 | ? | ? | ? |
| 4 | Hide layers | 17 | 27 | −17 | −27 | ? | ? | ? |
| 5 | Merge prereqs | 18 | 25 | +1 | −2 | ? | ? | ? |
| 6 | Merge outcomes | 19 | 19 | +1 | −6 | ? | ? | ? |

Where:
- **Cross.** = raw crossing count (integer), or normalized [0,1] score from greadability.js
- **Area** = bounding box area in thousands of pixels²
- **EL-CV** = edge length coefficient of variation (dimensionless, lower = more uniform)

One sentence in the paper citing Purchase (2002) establishes the metrics. One sentence noting the tool (greadability.js or manual computation) establishes the method.

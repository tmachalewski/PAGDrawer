# Daily Note: Tooltip Refinements & Graph Behavior
**Date:** 2026-01-13 23:10

## Completed Tasks

### 1. Tooltip Position Persistence ✅
- **Problem:** Dragged tooltips would maintain their *offset* relative to the node. When zooming/panning, this caused them to "jump" or move strictly with the node, which felt unnatural for a "detached" reference.
- **Solution:** Implemented "true detachment". When a tooltip is dragged:
    - It disconnects from the node's coordinate system.
    - We store its absolute screen position (`draggedPositions` map).
    - On zoom/pan/render, we restore this absolute screen position instead of calculating relative to the node.
- **Outcome:** Tooltips stay exactly where you leave them on the screen, independent of graph movement.

### 2. TI Node Selection Bug Fix ✅
- **Problem:** Clicking TI nodes (e.g., `TI:Execute...`) caused the entire graph to dim and the selection validation to fail.
- **Root Cause:** TI node IDs contain complex characters (`:`, `@`, `*`). The code used `CSS.escape(id)` to create a selector (e.g., `#TI\:`), but Cytoscape's selector engine failed to match these complex escaped IDs, resulting in an empty selection set (and thus treating everything as unselected/dimmed).
- **Solution:** Replaced CSS selector logic with `cy.getElementById()`, which handles raw string IDs reliably without intricate escaping.

### 3. Visual Polish
- **Z-Index Management:** Hovered tooltips now pop to the front (`z-index: 10100`) to prevent obstruction by other tooltips (`z-index: 10000`).
- **Text Update:** Changed "Hacker cannot reach this host" to "Cannot exploit until attacker gains foothold in the network" for better technical accuracy.

## Discussion: Node Grouping Behavior
- **Observation:** User noted that `AV:L` (Vector Changer) nodes are connected to multiple TI nodes (convergence), asking if this conflicts with "Singular" grouping.
- **Clarification:** The **"Singular (Per-Host)"** setting for VC nodes implies "One VC node of type X per Host".
    - If multiple attack paths (e.g., *SQL Injection* and *Command Injection*) both result in gaining local access (`AV:L`) on `host-005`, they **correctly converge** into the single `AV:L` node for that host.
    - This confirms the "Singular (Per-Host)" logic is working as intended (reducing redundancy by merging identical states on the same host).

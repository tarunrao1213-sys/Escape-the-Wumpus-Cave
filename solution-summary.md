# Solution Summary — Assignment 1.5: Escape the Wumpus Cave

## 1. Overview

The solution implements a complete PDDL planning pipeline for the Wumpus Cave
assignment. A standalone Python program, `solve.py`, reads each text map,
creates the corresponding PDDL domain and problem descriptions, runs an
external PDDL planner, converts the planner output into the required commands,
and independently validates the resulting plan.

The program can process either one map or every `map*.txt` file in a directory.
For each map, it produces the three required artifacts:

- `mapXYZ.pddl` — generated PDDL problem;
- `mapXYZ.pddl.soln` — raw planner output;
- `mapXYZ-solution.txt` — final assignment-format solution.

The shared domain is generated as `wumpus.pddl` in the output directory.

## 2. Main design

The implementation separates the map into two kinds of information:

1. **Terrain:** whether a cell allows horizontal or vertical movement, whether
   it is a pit, and whether it is a turntable.
2. **Occupancy:** whether the agent, a crate, a Wumpus, or an arrow occupies the
   cell.

This separation is important because the state of a cell can change during a
plan. A turntable can rotate, a Wumpus can be removed, a crate can move, and a
pit can be filled. It also allows a crate to stand on a cell containing an
arrow without permanently removing the arrow.

The domain uses typed PDDL objects:

- `cell` for accessible map positions;
- `arrow` for individual arrows;
- `crate` for individual crates.

Walls are excluded from the PDDL cell objects. Every non-wall cell receives a
stable name such as `cell-r3-c7`.

## 3. PDDL state representation

The most important predicates are:

| Predicate | Meaning |
|---|---|
| `(agent-at ?cell)` | Current agent position |
| `(free ?cell)` | Cell has no agent, crate, or Wumpus |
| `(arrow-at ?arrow ?cell)` | An uncollected arrow is at the cell |
| `(arrow-held ?arrow)` | The agent currently holds the arrow |
| `(wumpus-at ?cell)` | A living Wumpus occupies the cell |
| `(crate-at ?crate ?cell)` | A crate occupies the cell |
| `(pit-at ?cell)` | The cell contains an unfilled pit |
| `(turntable ?cell)` | The cell is a turntable |
| `(horizontal-open ?cell)` | East-west movement is allowed |
| `(vertical-open ?cell)` | North-south movement is allowed |
| `(north-of ?to ?from)` | Two cells are adjacent in one direction |
| `(north-push ?to ?middle ?from)` | Three cells form a valid push line |
| `(exit-north ?cell)` | Walking north from the cell leaves the map |
| `(escaped)` | The assignment goal has been achieved |

Equivalent adjacency, push-line, and exit predicates are generated for east,
south, and west.

Individual arrow objects are used instead of numeric counters. This keeps the
domain compatible with simple STRIPS planners and guarantees that each shot
consumes one specific collected arrow.

## 4. Action modelling

The PDDL domain uses small action variants rather than one action with many
conditional effects. Separate variants are generated for all four directions.

### Walking

An ordinary walking action requires:

- the agent to be in the source cell;
- the destination to be adjacent and free;
- the source and destination terrain to allow movement along the selected
  axis.

A separate `walk-collect` action handles automatic arrow collection when the
agent enters a cell containing an arrow.

### Shooting

A shooting action requires a Wumpus in the immediately adjacent cell and an
arrow held by the agent. Its effects remove the Wumpus, make the target cell
free, and mark the selected arrow as spent. Shooting does not move the agent.

### Crate pushing

A pushing action uses a three-cell relation consisting of the agent cell, crate
cell, and destination cell. The destination must be suitable for the crate, and
the terrain of all relevant cells must permit movement in that direction. The
agent moves into the crate's previous position.

Separate push variants handle the case in which an arrow is located underneath
the crate. When the crate moves away, the agent enters that cell and
automatically collects the arrow.

### Filling pits

When a crate is pushed into a pit, both the crate and the pit are removed from
the dynamic state. The pit cell becomes free and open for both horizontal and
vertical movement.

### Turning turntables

A turn action rotates an adjacent turntable:

- horizontal (`-`) becomes vertical (`|`);
- vertical (`|`) becomes horizontal (`-`).

The agent remains in its current cell. Turntable orientation is modelled
independently of occupancy, so a turntable can still rotate while a crate is
standing on it.

### Escaping

Boundary cells receive exit predicates during problem generation. If the agent
is on a compatible boundary cell and the terrain permits movement in that
direction, an escape action makes `(escaped)` true. The planner's escape action
is converted into the corresponding final `walk` command.

## 5. Map-to-PDDL conversion

The map parser preserves leading and trailing spaces because spaces represent
real empty cells. It verifies that the map is rectangular, contains only known
symbols, and has exactly one starting position.

The following symbols are supported:

| Symbol | Meaning |
|---|---|
| `S` | Agent starting position |
| space | Empty cell |
| `X` | Wall |
| `A` | Arrow |
| `W` | Wumpus |
| `C` | Crate |
| `P` | Pit |
| `-` | Horizontal turntable |
| `|` | Vertical turntable |

For each non-wall cell, the converter generates objects, adjacency facts,
push-line facts, boundary exits, terrain properties, and initial occupancy.
The goal of every generated problem is `(escaped)`.

## 6. Planning and plan conversion

Pyperplan 2.1 is the default planner. It is executed with the FF heuristic and
greedy best-first search. Fast Downward is also supported through the
`lama-first` configuration.

Planner actions contain internal cell and object parameters. The converter
removes these PDDL details and maps each action to one of the external commands
accepted by the assignment:

```text
walk <direction>
shoot <direction>
push <direction>
turn <direction>
```

Comments and optional planner step-number prefixes are ignored during
conversion. Unknown planner actions are rejected rather than silently written
to the final plan.

## 7. Validation and error handling

After conversion, the program runs an independent simulator on every final
solution. The simulator checks:

- legal movement through terrain and turntables;
- collisions with walls, crates, pits, and living Wumpuses;
- arrow collection and consumption;
- legal crate pushing and pit filling;
- turntable rotation;
- correct action syntax;
- successful escape;
- absence of additional actions after escape.

Old plan files are removed before each planner run. Therefore, a failed planner
execution cannot accidentally reuse a stale solution from an earlier run.
Invalid maps, failed planner calls, unrecognized actions, and invalid final
plans produce explicit errors.

The local simulator is intended to detect implementation and conversion
mistakes early. The official assignment `verify.py` remains authoritative.

## 8. Testing and evaluation

The complete pipeline was tested on the 20 available example maps
`map000`–`map019`. All 20 were successfully planned, converted, and accepted by
the independent simulator.

Additional focused maps were used to test features that do not appear in the
first 20 examples:

- ordinary crate pushing;
- pushing a crate into a pit;
- turntable rotation;
- pushing a crate while it occupies a turntable;
- collecting an arrow from underneath a moved crate;
- using the collected arrow to shoot a Wumpus.

All focused tests passed. The remaining assignment maps must still be checked
with the official verifier before final submission.

## 9. Strengths

- The entire pipeline is contained in one standalone Python file.
- The PDDL domain uses basic typed STRIPS constructs supported by both planners.
- Terrain and occupancy are modelled separately, which supports interactions
  between crates, arrows, pits, and turntables.
- Generated final plans are checked independently before verification.
- Both individual-map and directory-based batch solving are supported.
- Valid plans are sufficient; the design does not unnecessarily require
  optimal solutions.

## 10. Limitations

- The program depends on an external PDDL planner.
- Pyperplan can become slow on maps with many objects because grounding creates
  many possible actions.
- Local validation cannot replace the official assignment verifier.
- Only the available example maps and focused feature maps were tested during
  development; final evaluation must include all 80 assignment maps.

## 11. Conclusion

The solution provides an automated and reusable method for translating Wumpus
Cave maps into planning problems and producing valid escape plans. Its modular
internal design, explicit state representation, small PDDL actions, automatic
plan conversion, and independent validation make the implementation easier to
understand and debug while remaining compatible with the assignment's required
output format.

# Assignment 1.5 — Escape the Wumpus Cave

This project solves the Wumpus Cave planning assignment using PDDL. The
standalone `solve.py` reads text maps, generates PDDL files, runs a planner,
converts the planner output into the required command format, and locally
validates every generated solution.

The supported commands are:

- `walk north|east|south|west`
- `shoot north|east|south|west`
- `push north|east|south|west`
- `turn north|east|south|west`

The solver supports walls, arrows, Wumpuses, crates, pits, horizontal
turntables, vertical turntables, and escaping through the map boundary.

## Requirements

- Python 3.10 or newer
- Pyperplan 2.1, or a working Fast Downward installation
- The `requests` package for the official `verify.py`

Install the recommended dependencies in PowerShell:

```powershell
py -m pip install pyperplan==2.1 requests
```

If the `py` command is unavailable, use `python` instead.

## Project structure

The folder can be organized as follows:

```text
assignment/
├── README.md
├── solve.py
├── verify.py
├── example-maps/
│   ├── map000.txt
│   ├── map001.txt
│   └── ...
├── solution-maps/
│   ├── map000-solution.txt
│   ├── map001-solution.txt
│   └── ...
└── maps/
    ├── map000.txt
    ├── map001.txt
    └── ...
```

The directory names may be different. Use the actual names in the commands
and place quotation marks around paths containing spaces.

## How the solver works

For each input map, `solve.py` performs the following steps:

1. Reads and validates the rectangular text map.
2. Generates the reusable `wumpus.pddl` domain.
3. Generates a PDDL problem describing the current map.
4. Runs Pyperplan or Fast Downward to find an escape plan.
5. Converts the planner actions into the assignment command format.
6. Simulates the converted actions and checks that the agent escapes legally.

The complete pipeline is contained inside the standalone `solve.py`; no
additional Python modules are required.

## Test the provided example solutions

The assignment includes example maps and corresponding example solutions. To
check the provided solutions using the official verification server, run:

```powershell
python .\verify.py ".\example-maps" ".\solution-maps"
```

This establishes the expected verifier result before testing newly generated
solutions.

## Solve all example maps

Run the standalone solver on the complete example-map directory:

```powershell
py .\solve.py ".\example-maps" --output ".\generated-example" --planner pyperplan
```

The terminal prints one `OK` line for every map that is successfully solved
and locally validated.

## Verify the generated example solutions

```powershell
py .\verify.py ".\example-map" ".\generated-example"
```

Compare this verifier result with the result obtained for `solution map`.
The command sequences do not need to be identical: several different plans
may correctly solve the same map, and the assignment does not require the
shortest plan.

## Solve the actual assignment maps

```powershell
py .\solve.py ".\maps" --output ".\generated-actual" --planner pyperplan
```

## Verify the actual solutions

```powershell
py .\verify.py ".\maps" ".\generated-actual"
```

The supplied `verify.py` expects all 80 maps, from `map000.txt` through
`map079.txt`. It also expects the final solution files to be named
`map000-solution.txt` through `map079-solution.txt`.

## Solve one map

To solve only `map000.txt`:

```powershell
py .\solve.py ".\maps\map000.txt" --output ".\generated-actual" --planner pyperplan
```

## Generated files

For each `mapXYZ.txt`, the output directory contains:

```text
mapXYZ.pddl
mapXYZ.pddl.soln
mapXYZ-solution.txt
```

| File | Purpose |
|---|---|
| `mapXYZ.pddl` | Generated PDDL problem for the map |
| `mapXYZ.pddl.soln` | Raw plan produced by the PDDL planner |
| `mapXYZ-solution.txt` | Final plan in the assignment command format |
| `wumpus.pddl` | Reusable PDDL domain containing the cave rules |

The official verifier reads the original maps and the final
`mapXYZ-solution.txt` files. The other generated files are required assignment
artifacts but are not passed as the solution directory argument.

## Using Fast Downward instead

Fast Downward can be used after it has been downloaded and built:

```powershell
py .\solve.py ".\maps" `
    --output ".\generated-actual" `
    --planner fast-downward `
    --fast-downward "C:\path\to\downward\fast-downward.py"
```

The solver uses Fast Downward's `lama-first` configuration. A valid plan is
sufficient; optimality is not required.

## Common problems

### `No module named pyperplan`

Install Pyperplan using the same Python command used to run the solver:

```powershell
py -m pip install pyperplan==2.1
```

### `No module named requests`

```powershell
py -m pip install requests
```

### `no map files found`

Check the folder path and confirm that the files follow the `mapXYZ.txt`
naming convention.

### Missing solution reported by `verify.py`

Confirm that every map has a matching file such as:

```text
map000.txt           -> map000-solution.txt
map001.txt           -> map001-solution.txt
```

### Pyperplan says `validate could not be found on the PATH`

This refers to Pyperplan's optional external VAL tool. It is not a solver
failure. The standalone script runs its own independent validation after
converting each plan. A successful map ends with an `OK` message.

## Important notes

- Spaces inside map files represent empty cells and must not be removed.
- A generated route may differ from the provided example route and still be
  correct.
- The included local validation is useful for debugging, but the official
  assignment verifier remains authoritative.
- Run the official verifier on all 80 actual maps before submission.

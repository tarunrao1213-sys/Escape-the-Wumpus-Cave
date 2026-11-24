"""Standalone solver for Assignment 1.5: Escape the Wumpus Cave.

This single file generates the PDDL domain and problem files, runs Pyperplan
or Fast Downward, converts planner output to the assignment command format,
and independently validates each final plan.

Examples:
    py solve.py maps --output generated --planner pyperplan
    py solve.py maps/map000.txt --output generated --planner pyperplan
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# PDDL domain generation
# ---------------------------------------------------------------------------

DOMAIN_DIRECTIONS = {
    "north": ("north-of", "north-push", "vertical-open"),
    "east": ("east-of", "east-push", "horizontal-open"),
    "south": ("south-of", "south-push", "vertical-open"),
    "west": ("west-of", "west-push", "horizontal-open"),
}


def action(name: str, parameters: str, preconditions: list[str], effects: list[str]) -> str:
    pre = "\n            ".join(preconditions)
    eff = "\n            ".join(effects)
    return f"""    (:action {name}
        :parameters ({parameters})
        :precondition (and
            {pre}
        )
        :effect (and
            {eff}
        )
    )"""


def build_domain() -> str:
    actions: list[str] = []

    for direction, (adjacent, push_line, axis) in DOMAIN_DIRECTIONS.items():
        # Walk to an ordinary cell or a cell whose arrow was already collected.
        actions.append(
            action(
                f"walk-{direction}",
                "?from ?to - cell",
                [
                    "(agent-at ?from)",
                    f"({adjacent} ?to ?from)",
                    "(free ?to)",
                    "(no-arrow ?to)",
                    f"({axis} ?from)",
                    f"({axis} ?to)",
                ],
                [
                    "(not (agent-at ?from))",
                    "(free ?from)",
                    "(agent-at ?to)",
                    "(not (free ?to))",
                ],
            )
        )

        # Enter an arrow cell and pick up that particular arrow automatically.
        actions.append(
            action(
                f"walk-collect-{direction}",
                "?from ?to - cell ?arrow - arrow",
                [
                    "(agent-at ?from)",
                    f"({adjacent} ?to ?from)",
                    "(free ?to)",
                    "(arrow-at ?arrow ?to)",
                    f"({axis} ?from)",
                    f"({axis} ?to)",
                ],
                [
                    "(not (agent-at ?from))",
                    "(free ?from)",
                    "(agent-at ?to)",
                    "(not (free ?to))",
                    "(not (arrow-at ?arrow ?to))",
                    "(no-arrow ?to)",
                    "(arrow-held ?arrow)",
                ],
            )
        )

        actions.append(
            action(
                f"shoot-{direction}",
                "?from ?target - cell ?arrow - arrow",
                [
                    "(agent-at ?from)",
                    f"({adjacent} ?target ?from)",
                    "(wumpus-at ?target)",
                    "(arrow-held ?arrow)",
                ],
                [
                    "(not (wumpus-at ?target))",
                    "(free ?target)",
                    "(not (arrow-held ?arrow))",
                    "(arrow-spent ?arrow)",
                ],
            )
        )

        # Push a crate onto a traversable destination.  The two versions are
        # needed because the agent automatically collects an arrow hidden under
        # the crate when it enters the crate's old cell.
        actions.append(
            action(
                f"push-{direction}",
                "?from ?middle ?to - cell ?crate - crate",
                [
                    "(agent-at ?from)",
                    f"({push_line} ?to ?middle ?from)",
                    "(crate-at ?crate ?middle)",
                    "(free ?to)",
                    "(no-arrow ?middle)",
                    f"({axis} ?from)",
                    f"({axis} ?middle)",
                    f"({axis} ?to)",
                ],
                [
                    "(not (agent-at ?from))",
                    "(free ?from)",
                    "(agent-at ?middle)",
                    "(not (crate-at ?crate ?middle))",
                    "(crate-at ?crate ?to)",
                    "(not (free ?to))",
                ],
            )
        )
        actions.append(
            action(
                f"push-collect-{direction}",
                "?from ?middle ?to - cell ?crate - crate ?arrow - arrow",
                [
                    "(agent-at ?from)",
                    f"({push_line} ?to ?middle ?from)",
                    "(crate-at ?crate ?middle)",
                    "(free ?to)",
                    "(arrow-at ?arrow ?middle)",
                    f"({axis} ?from)",
                    f"({axis} ?middle)",
                    f"({axis} ?to)",
                ],
                [
                    "(not (agent-at ?from))",
                    "(free ?from)",
                    "(agent-at ?middle)",
                    "(not (crate-at ?crate ?middle))",
                    "(crate-at ?crate ?to)",
                    "(not (free ?to))",
                    "(not (arrow-at ?arrow ?middle))",
                    "(no-arrow ?middle)",
                    "(arrow-held ?arrow)",
                ],
            )
        )

        # Pushing into a pit consumes the crate and converts the pit into a
        # normal cell.  The destination itself need not already be open.
        actions.append(
            action(
                f"push-pit-{direction}",
                "?from ?middle ?to - cell ?crate - crate",
                [
                    "(agent-at ?from)",
                    f"({push_line} ?to ?middle ?from)",
                    "(crate-at ?crate ?middle)",
                    "(pit-at ?to)",
                    "(no-arrow ?middle)",
                    f"({axis} ?from)",
                    f"({axis} ?middle)",
                ],
                [
                    "(not (agent-at ?from))",
                    "(free ?from)",
                    "(agent-at ?middle)",
                    "(not (crate-at ?crate ?middle))",
                    "(not (pit-at ?to))",
                    "(free ?to)",
                    "(horizontal-open ?to)",
                    "(vertical-open ?to)",
                ],
            )
        )
        actions.append(
            action(
                f"push-pit-collect-{direction}",
                "?from ?middle ?to - cell ?crate - crate ?arrow - arrow",
                [
                    "(agent-at ?from)",
                    f"({push_line} ?to ?middle ?from)",
                    "(crate-at ?crate ?middle)",
                    "(pit-at ?to)",
                    "(arrow-at ?arrow ?middle)",
                    f"({axis} ?from)",
                    f"({axis} ?middle)",
                ],
                [
                    "(not (agent-at ?from))",
                    "(free ?from)",
                    "(agent-at ?middle)",
                    "(not (crate-at ?crate ?middle))",
                    "(not (pit-at ?to))",
                    "(free ?to)",
                    "(horizontal-open ?to)",
                    "(vertical-open ?to)",
                    "(not (arrow-at ?arrow ?middle))",
                    "(no-arrow ?middle)",
                    "(arrow-held ?arrow)",
                ],
            )
        )

        # The direction tells where the turntable is relative to the agent.
        # No free predicate is required, so a crate may be standing on it.
        actions.append(
            action(
                f"turn-{direction}-horizontal-to-vertical",
                "?agent-cell ?table - cell",
                [
                    "(agent-at ?agent-cell)",
                    f"({adjacent} ?table ?agent-cell)",
                    "(turntable ?table)",
                    "(horizontal-open ?table)",
                ],
                [
                    "(not (horizontal-open ?table))",
                    "(vertical-open ?table)",
                ],
            )
        )
        actions.append(
            action(
                f"turn-{direction}-vertical-to-horizontal",
                "?agent-cell ?table - cell",
                [
                    "(agent-at ?agent-cell)",
                    f"({adjacent} ?table ?agent-cell)",
                    "(turntable ?table)",
                    "(vertical-open ?table)",
                ],
                [
                    "(not (vertical-open ?table))",
                    "(horizontal-open ?table)",
                ],
            )
        )

        actions.append(
            action(
                f"escape-{direction}",
                "?from - cell",
                [
                    "(agent-at ?from)",
                    f"(exit-{direction} ?from)",
                    f"({axis} ?from)",
                ],
                ["(escaped)"],
            )
        )

    predicates = """
        (agent-at ?cell - cell)
        (free ?cell - cell)
        (no-arrow ?cell - cell)
        (arrow-at ?arrow - arrow ?cell - cell)
        (arrow-held ?arrow - arrow)
        (arrow-spent ?arrow - arrow)
        (wumpus-at ?cell - cell)
        (crate-at ?crate - crate ?cell - cell)
        (pit-at ?cell - cell)
        (turntable ?cell - cell)
        (horizontal-open ?cell - cell)
        (vertical-open ?cell - cell)
        (north-of ?to ?from - cell)
        (east-of ?to ?from - cell)
        (south-of ?to ?from - cell)
        (west-of ?to ?from - cell)
        (north-push ?to ?middle ?from - cell)
        (east-push ?to ?middle ?from - cell)
        (south-push ?to ?middle ?from - cell)
        (west-push ?to ?middle ?from - cell)
        (exit-north ?cell - cell)
        (exit-east ?cell - cell)
        (exit-south ?cell - cell)
        (exit-west ?cell - cell)
        (escaped)
    """.strip()

    return """(define (domain wumpus-cave)
    (:requirements :strips :typing)
    (:types cell arrow crate)
    (:predicates
        %s
    )

%s
)
""" % (predicates, "\n\n".join(actions))


def write_domain(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_domain(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Map parsing and PDDL problem generation
# ---------------------------------------------------------------------------

VALID_SYMBOLS = {"S", " ", "X", "W", "A", "C", "P", "-", "|"}
MAP_DIRECTIONS = {
    "north": (-1, 0),
    "east": (0, 1),
    "south": (1, 0),
    "west": (0, -1),
}


def cell_name(row: int, column: int) -> str:
    return f"cell-r{row}-c{column}"


@dataclass(frozen=True)
class MapData:
    name: str
    rows: tuple[str, ...]

    @property
    def height(self) -> int:
        return len(self.rows)

    @property
    def width(self) -> int:
        return len(self.rows[0])

    def symbol(self, row: int, column: int) -> str:
        return self.rows[row][column]

    def exists(self, row: int, column: int) -> bool:
        return 0 <= row < self.height and 0 <= column < self.width

    def is_object(self, row: int, column: int) -> bool:
        return self.exists(row, column) and self.symbol(row, column) != "X"


def read_map(path: Path) -> MapData:
    # splitlines() removes line endings but preserves meaningful leading and
    # trailing spaces.  Never use strip() on a map row.
    rows = tuple(path.read_text(encoding="utf-8").splitlines())
    if not rows:
        raise ValueError(f"{path}: empty map")
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError(f"{path}: map must be non-empty and rectangular")
    bad = sorted(set("".join(rows)) - VALID_SYMBOLS)
    if bad:
        raise ValueError(f"{path}: unsupported symbols: {bad}")
    if sum(row.count("S") for row in rows) != 1:
        raise ValueError(f"{path}: expected exactly one S")
    return MapData(path.stem.lower(), rows)


def grouped_objects(names: list[str], type_name: str) -> str:
    return f"        {' '.join(names)} - {type_name}" if names else ""


def build_problem(data: MapData) -> str:
    cells = [
        cell_name(r, c)
        for r in range(data.height)
        for c in range(data.width)
        if data.is_object(r, c)
    ]
    arrows: list[str] = []
    crates: list[str] = []
    init: list[str] = []

    for r in range(data.height):
        for c in range(data.width):
            if not data.is_object(r, c):
                continue
            here = cell_name(r, c)
            symbol = data.symbol(r, c)

            # Static adjacency and the three-cell line relations used by push.
            for direction, (dr, dc) in MAP_DIRECTIONS.items():
                r1, c1 = r + dr, c + dc
                if data.is_object(r1, c1):
                    init.append(f"({direction}-of {cell_name(r1, c1)} {here})")
                    r2, c2 = r + 2 * dr, c + 2 * dc
                    if data.is_object(r2, c2):
                        init.append(
                            f"({direction}-push {cell_name(r2, c2)} "
                            f"{cell_name(r1, c1)} {here})"
                        )

            if r == 0:
                init.append(f"(exit-north {here})")
            if c == data.width - 1:
                init.append(f"(exit-east {here})")
            if r == data.height - 1:
                init.append(f"(exit-south {here})")
            if c == 0:
                init.append(f"(exit-west {here})")

            if symbol not in {"P", "-", "|"}:
                init.extend([f"(horizontal-open {here})", f"(vertical-open {here})"])
            elif symbol == "-":
                init.extend([f"(turntable {here})", f"(horizontal-open {here})"])
            elif symbol == "|":
                init.extend([f"(turntable {here})", f"(vertical-open {here})"])

            if symbol == "S":
                init.extend([f"(agent-at {here})", f"(no-arrow {here})"])
            elif symbol == "W":
                init.extend([f"(wumpus-at {here})", f"(no-arrow {here})"])
            elif symbol == "C":
                crate = f"crate-{len(crates)}"
                crates.append(crate)
                init.extend([f"(crate-at {crate} {here})", f"(no-arrow {here})"])
            elif symbol == "P":
                init.extend([f"(pit-at {here})", f"(no-arrow {here})"])
            elif symbol == "A":
                arrow = f"arrow-{len(arrows)}"
                arrows.append(arrow)
                init.extend([f"(arrow-at {arrow} {here})", f"(free {here})"])
            else:  # ordinary empty cell or a turntable
                init.extend([f"(free {here})", f"(no-arrow {here})"])

    object_lines = [grouped_objects(cells, "cell")]
    if arrows:
        object_lines.append(grouped_objects(arrows, "arrow"))
    if crates:
        object_lines.append(grouped_objects(crates, "crate"))
    objects = "\n".join(line for line in object_lines if line)
    initial_state = "\n        ".join(init)
    problem_name = data.name.replace("_", "-")

    return f"""(define (problem {problem_name})
    (:domain wumpus-cave)
    (:objects
{objects}
    )
    (:init
        {initial_state}
    )
    (:goal (escaped))
)
"""


def generate_problem(map_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_problem(read_map(map_path)), encoding="utf-8")


# ---------------------------------------------------------------------------
# Planner-plan conversion
# ---------------------------------------------------------------------------

ACTION_DIRECTIONS = ("north", "east", "south", "west")


def external_action(planner_action: str) -> str | None:
    line = planner_action.strip().lower()
    if not line or line.startswith(";"):
        return None
    # Fast Downward and pyperplan enclose grounded actions in parentheses.
    line = line.strip("() ")
    name = line.split()[0]

    for direction in ACTION_DIRECTIONS:
        if name in {f"walk-{direction}", f"walk-collect-{direction}", f"escape-{direction}"}:
            return f"walk {direction}"
        if name == f"shoot-{direction}":
            return f"shoot {direction}"
        if name in {
            f"push-{direction}",
            f"push-collect-{direction}",
            f"push-pit-{direction}",
            f"push-pit-collect-{direction}",
        }:
            return f"push {direction}"
        if name.startswith(f"turn-{direction}-"):
            return f"turn {direction}"
    raise ValueError(f"Unknown planner action: {planner_action.rstrip()}")


def convert_plan(raw_plan: Path, output_plan: Path) -> list[str]:
    result: list[str] = []
    for line in raw_plan.read_text(encoding="utf-8").splitlines():
        # Some planners prefix steps with "0:".  Remove that optional prefix.
        line = re.sub(r"^\s*\d+\s*:\s*", "", line)
        converted = external_action(line)
        if converted is not None:
            result.append(converted)
    if not result:
        raise ValueError(f"{raw_plan}: planner returned no actions")
    output_plan.parent.mkdir(parents=True, exist_ok=True)
    output_plan.write_text("\n".join(result) + "\n", encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# Independent final-plan validation
# ---------------------------------------------------------------------------

class InvalidPlan(RuntimeError):
    pass


@dataclass
class State:
    data: MapData
    agent: tuple[int, int]
    arrows: set[tuple[int, int]]
    wumpuses: set[tuple[int, int]]
    crates: set[tuple[int, int]]
    pits: set[tuple[int, int]]
    turntables: dict[tuple[int, int], str]
    arrows_held: int = 0
    escaped: bool = False

    @classmethod
    def from_map(cls, data: MapData) -> "State":
        positions: dict[str, set[tuple[int, int]]] = {
            char: set() for char in "SAWCP"
        }
        turntables: dict[tuple[int, int], str] = {}
        for r, row in enumerate(data.rows):
            for c, char in enumerate(row):
                if char in positions:
                    positions[char].add((r, c))
                elif char in "-|":
                    turntables[(r, c)] = char
        return cls(
            data=data,
            agent=next(iter(positions["S"])),
            arrows=positions["A"],
            wumpuses=positions["W"],
            crates=positions["C"],
            pits=positions["P"],
            turntables=turntables,
        )

    def in_bounds(self, cell: tuple[int, int]) -> bool:
        return self.data.exists(*cell)

    def terrain_open(self, cell: tuple[int, int], direction: str) -> bool:
        if not self.in_bounds(cell) or self.data.symbol(*cell) == "X" or cell in self.pits:
            return False
        orientation = self.turntables.get(cell)
        if orientation == "-":
            return direction in {"east", "west"}
        if orientation == "|":
            return direction in {"north", "south"}
        return True

    def step(self, cell: tuple[int, int], direction: str) -> tuple[int, int]:
        dr, dc = MAP_DIRECTIONS[direction]
        return cell[0] + dr, cell[1] + dc

    def collect(self) -> None:
        if self.agent in self.arrows:
            self.arrows.remove(self.agent)
            self.arrows_held += 1

    def walk(self, direction: str) -> None:
        if not self.terrain_open(self.agent, direction):
            raise InvalidPlan("current turntable blocks this walking direction")
        target = self.step(self.agent, direction)
        if not self.in_bounds(target):
            self.escaped = True
            return
        if not self.terrain_open(target, direction):
            raise InvalidPlan(f"cannot enter blocked cell {target}")
        if target in self.wumpuses:
            raise InvalidPlan(f"Wumpus blocks cell {target}")
        if target in self.crates:
            raise InvalidPlan(f"crate blocks cell {target}")
        self.agent = target
        self.collect()

    def shoot(self, direction: str) -> None:
        target = self.step(self.agent, direction)
        if self.arrows_held < 1:
            raise InvalidPlan("cannot shoot without an arrow")
        if target not in self.wumpuses:
            raise InvalidPlan(f"no adjacent Wumpus at {target}")
        self.arrows_held -= 1
        self.wumpuses.remove(target)

    def push(self, direction: str) -> None:
        if not self.terrain_open(self.agent, direction):
            raise InvalidPlan("current turntable blocks this push direction")
        middle = self.step(self.agent, direction)
        target = self.step(middle, direction)
        if middle not in self.crates:
            raise InvalidPlan(f"no crate at {middle}")
        if not self.terrain_open(middle, direction):
            raise InvalidPlan("turntable under crate blocks this push direction")
        if not self.in_bounds(target):
            raise InvalidPlan("cannot push a crate off the map")
        if self.data.symbol(*target) == "X" or target in self.wumpuses or target in self.crates:
            raise InvalidPlan(f"crate destination {target} is blocked")

        self.crates.remove(middle)
        if target in self.pits:
            self.pits.remove(target)
        else:
            if not self.terrain_open(target, direction):
                raise InvalidPlan(f"crate cannot enter {target} in this direction")
            self.crates.add(target)
        self.agent = middle
        self.collect()

    def turn(self, direction: str) -> None:
        target = self.step(self.agent, direction)
        if target not in self.turntables:
            raise InvalidPlan(f"no turntable at {target}")
        self.turntables[target] = "|" if self.turntables[target] == "-" else "-"

    def apply(self, action: str) -> None:
        if self.escaped:
            raise InvalidPlan("plan contains actions after escape")
        parts = action.lower().split()
        if len(parts) != 2 or parts[0] not in {"walk", "shoot", "push", "turn"}:
            raise InvalidPlan(f"invalid action syntax: {action!r}")
        verb, direction = parts
        if direction not in MAP_DIRECTIONS:
            raise InvalidPlan(f"invalid direction: {direction!r}")
        getattr(self, verb)(direction)


def validate(map_path: Path, plan_path: Path) -> int:
    state = State.from_map(read_map(map_path))
    actions = [line.strip() for line in plan_path.read_text().splitlines() if line.strip()]
    for number, action in enumerate(actions, 1):
        try:
            state.apply(action)
        except InvalidPlan as error:
            raise InvalidPlan(f"action {number} ({action}): {error}") from error
    if not state.escaped:
        raise InvalidPlan("plan ended before the agent escaped")
    return len(actions)


# ---------------------------------------------------------------------------
# Planner execution and command-line interface
# ---------------------------------------------------------------------------

def run_fast_downward(
    executable: Path,
    domain: Path,
    problem: Path,
    raw_plan: Path,
) -> None:
    command = [
        sys.executable,
        str(executable),
        "--alias",
        "lama-first",
        "--plan-file",
        str(raw_plan),
        str(domain),
        str(problem),
    ]
    subprocess.run(command, check=True)


def run_pyperplan(domain: Path, problem: Path, raw_plan: Path) -> None:
    # pyperplan writes <problem>.soln.  Run it in the problem directory and
    # then normalize that filename to the assignment's expected one.
    command = [
        sys.executable,
        "-m",
        "pyperplan",
        "-H",
        "hff",
        "-s",
        "gbf",
        str(domain.resolve()),
        str(problem.resolve()),
    ]
    subprocess.run(command, cwd=problem.parent, check=True)
    produced = problem.with_suffix(problem.suffix + ".soln")
    if not produced.exists():
        # pyperplan 2.1 normally uses map000.pddl.soln, but keep this explicit
        # error in case a future version changes its output convention.
        raise RuntimeError(f"pyperplan found no plan for {problem}")
    if produced != raw_plan:
        produced.replace(raw_plan)


def solve_one(map_path: Path, output_dir: Path, planner: str, fast_downward: Path | None) -> None:
    stem = map_path.stem
    domain = output_dir / "wumpus.pddl"
    problem = output_dir / f"{stem}.pddl"
    raw_plan = output_dir / f"{stem}.pddl.soln"
    final_plan = output_dir / f"{stem}-solution.txt"

    generate_problem(map_path, problem)
    # Never accept a stale plan left by an earlier run if the planner fails.
    raw_plan.unlink(missing_ok=True)
    if planner == "fast-downward":
        if fast_downward is None:
            raise ValueError("--fast-downward is required for planner fast-downward")
        run_fast_downward(fast_downward, domain, problem, raw_plan)
    else:
        run_pyperplan(domain, problem, raw_plan)
    if not raw_plan.exists():
        raise RuntimeError(f"planner found no plan for {map_path}")
    convert_plan(raw_plan, final_plan)
    count = validate(map_path, final_plan)
    print(f"OK {map_path.name}: {count} actions")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("maps", type=Path, help="map file or directory containing map*.txt")
    parser.add_argument("--output", type=Path, default=Path("generated"))
    parser.add_argument("--planner", choices=("pyperplan", "fast-downward"), default="pyperplan")
    parser.add_argument("--fast-downward", type=Path, help="path to fast-downward.py")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    write_domain(args.output / "wumpus.pddl")
    maps = [args.maps] if args.maps.is_file() else sorted(args.maps.glob("map*.txt"))
    if not maps:
        parser.error(f"no map files found at {args.maps}")
    for map_path in maps:
        solve_one(map_path, args.output, args.planner, args.fast_downward)


if __name__ == "__main__":
    main()

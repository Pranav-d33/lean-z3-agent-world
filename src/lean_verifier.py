"""
Lean 4 plan verifier.

Generates a self-contained Lean 4 file containing:
1. The world model (Position, World, Action types)
2. The step function and execPlan function
3. The specific initial state and plan
4. A theorem that the plan succeeds (proved via native_decide)

Runs `lean` on the generated file and parses the result.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import List, Optional, Tuple

from .world_model import (
    WorldState, Action,
    ACTION_MOVE, ACTION_MOVE_CAREFULLY,
    ACTION_TRY_UNLOCK,
    MOVE_DIRECTIONS,
)


LEAN_TEMPLATE = '''
/-- A position in the grid. Uses Int for simpler arithmetic with Move dx/dy. -/
structure Position where
  x : Int
  y : Int
  deriving DecidableEq, Repr

/--
The world state.
- `agentPos` : current agent position
- `keyPos` : position of the key (fixed)
- `doorPos` : position of the door (fixed)
- `hasKey` : whether the agent carries the key
- `doorUnlocked` : whether the door has been unlocked
- `obstacles` : list of blocked cells
- `gridSize` : grid dimension (e.g. 3 for 3×3)
-/
structure World where
  agentPos : Position
  keyPos : Position
  doorPos : Position
  hasKey : Bool
  doorUnlocked : Bool
  obstacles : List Position
  gridSize : Int
  deriving DecidableEq, Repr

/-- An action the agent can take. -/
inductive Action : Type where
  | move (dx : Int) (dy : Int)
  | pickupKey
  | unlockDoor
  | openDoor
  | tryUnlock
  | moveCarefully (dx : Int) (dy : Int)
  deriving DecidableEq, Repr

open Action

/-- Check if a position is within the grid bounds. -/
def isValidPosition (w : World) (pos : Position) : Bool :=
  0 ≤ pos.x ∧ pos.x < w.gridSize ∧ 0 ≤ pos.y ∧ pos.y < w.gridSize

/-- Check if a position is blocked by an obstacle. -/
def isObstacle (w : World) (pos : Position) : Bool :=
  w.obstacles.any (fun o => o.x == pos.x ∧ o.y == pos.y)

/-- Check if a position is free (in bounds and not an obstacle). -/
def isFree (w : World) (pos : Position) : Bool :=
  isValidPosition w pos ∧ ¬ isObstacle w pos

/--
Apply an action to a world state.
Returns the list of all possible next states (empty if precondition violated).
Deterministic actions return a singleton list.
Non-deterministic actions return multiple possible outcomes.
-/
def step (w : World) (a : Action) : List World :=
  match a with
  | .move dx dy =>
    let newX := w.agentPos.x + dx
    let newY := w.agentPos.y + dy
    let newPos := Position.mk newX newY
    if isFree w newPos then
      [{ w with agentPos := newPos }]
    else
      []
  | .pickupKey =>
    if w.agentPos.x == w.keyPos.x ∧ w.agentPos.y == w.keyPos.y ∧ ¬ w.hasKey then
      [{ w with hasKey := true }]
    else
      []
  | .unlockDoor =>
    if w.agentPos.x == w.doorPos.x ∧ w.agentPos.y == w.doorPos.y ∧ w.hasKey ∧ ¬ w.doorUnlocked then
      [{ w with doorUnlocked := true }]
    else
      []
  | .openDoor =>
    if w.agentPos.x == w.doorPos.x ∧ w.agentPos.y == w.doorPos.y ∧ w.doorUnlocked then
      [w]
    else
      []
  | .tryUnlock =>
    if w.agentPos.x == w.doorPos.x ∧ w.agentPos.y == w.doorPos.y ∧ w.hasKey then
      [{ w with doorUnlocked := true }, { w with hasKey := false }]
    else
      []
  | .moveCarefully dx dy =>
    let targetX := w.agentPos.x + dx
    let targetY := w.agentPos.y + dy
    let target := Position.mk targetX targetY
    if ¬ isFree w target then
      []
    else
      let slipOutcomes : List World :=
        (List.range 4).flatMap (fun d =>
          let slipDx := if d = 0 then -1 else if d = 1 then 1 else 0
          let slipDy := if d = 2 then -1 else if d = 3 then 1 else 0
          let slipPos := Position.mk (w.agentPos.x + slipDx) (w.agentPos.y + slipDy)
          if slipPos ≠ target ∧ isFree w slipPos then
            [{ w with agentPos := slipPos }]
          else
            []
        )
      { w with agentPos := target } :: slipOutcomes

/--
Execute a sequence of actions from a starting world.
Returns all possible final states (empty if any precondition fails on all branches).
-/
def execPlan (w : World) (plan : List Action) : List World :=
  match plan with
  | [] => [w]
  | a :: rest =>
    (step w a).flatMap (fun w' => execPlan w' rest)

/--
Safety property: the agent is within the grid and not on an obstacle.
-/
def isSafe (w : World) : Bool :=
  isValidPosition w w.agentPos ∧ ¬ isObstacle w w.agentPos

instance : Inhabited World where
  default := {
    agentPos := { x := 0, y := 0 }
    keyPos := { x := 0, y := 0 }
    doorPos := { x := 0, y := 0 }
    hasKey := false
    doorUnlocked := false
    obstacles := []
    gridSize := 0
  }

/--
Pretty-print an action for debugging.
-/
def actionToStr (a : Action) : String :=
  match a with
  | .move dx dy => s!"Move({dx}, {dy})"
  | .pickupKey => "PickupKey"
  | .unlockDoor => "UnlockDoor"
  | .openDoor => "OpenDoor"
  | .tryUnlock => "TryUnlock"
  | .moveCarefully dx dy => s!"MoveCarefully({dx}, {dy})"

/--
Pretty-print a world state for debugging.
-/
def worldToStr (w : World) : String :=
  s!"World(pos=({w.agentPos.x},{w.agentPos.y}), hasKey={w.hasKey}, doorUnlocked={w.doorUnlocked})"

-- ═══════════════════════════════════════════════════════════════
--  GENERATED SECTION: Initial state and plan
-- ═══════════════════════════════════════════════════════════════

def initialState : World := {GENERATED_INIT_STATE}

def plan : List Action := {GENERATED_PLAN}

/--
Find the first step where a precondition fails.
Returns `none` if the entire plan can be executed (at least one branch).
-/
def failureStep : Option Nat :=
  let rec loop (s : World) (remaining : List Action) (i : Nat) : Option Nat :=
    match remaining with
    | [] => none
    | a :: rest =>
      match step s a with
      | [] => some i
      | outcomes => match outcomes.head? with
        | some s' => loop s' rest (i + 1)
        | none => some i
  loop initialState plan 0

-- ═══════════════════════════════════════════════════════════════
--  Verification
-- ═══════════════════════════════════════════════════════════════

/--
Theorem: There exists at least one successful execution.
All preconditions are satisfied on at least one branch.
-/
theorem plan_feasible : execPlan initialState plan ≠ [] := by
  native_decide

/--
Theorem: All possible outcomes are safe.
The agent stays within bounds and never occupies an obstacle.
-/
theorem all_outcomes_safe : ∀ w ∈ execPlan initialState plan, isSafe w := by
  native_decide

#eval failureStep
#eval execPlan initialState plan
#eval plan.map actionToStr
'''


class LeanVerifier:
    """Generates and runs Lean 4 verification for a plan."""

    def __init__(self, lean_binary: Optional[str] = None):
        if lean_binary is None:
            lean_binary = self._find_lean_binary()
        self.lean_binary = lean_binary
        self._generated_file: Optional[str] = None

    @staticmethod
    def _find_lean_binary() -> str:
        elan_lean = os.path.expanduser("~/.elan/bin/lean")
        try:
            subprocess.run(["lean", "--version"], capture_output=True, timeout=5)
            return "lean"
        except FileNotFoundError:
            if os.path.isfile(elan_lean):
                return elan_lean
        return "lean"

    def _pos_to_lean(self, pos) -> str:
        return f"Position.mk {pos.x} {pos.y}"

    def _obstacles_to_lean(self, obstacles) -> str:
        if not obstacles:
            return "[]"
        items = ", ".join(f"Position.mk {ox} {oy}" for (ox, oy) in obstacles)
        return f"[{items}]"

    def _action_to_lean(self, action: Action) -> str:
        if action.type == ACTION_MOVE:
            return f"Action.move ({action.dx}) ({action.dy})"
        if action.type == ACTION_MOVE_CAREFULLY:
            return f"Action.moveCarefully ({action.dx}) ({action.dy})"
        if action.type == ACTION_TRY_UNLOCK:
            return "Action.tryUnlock"
        return f"Action.{action.type[0].lower()}{action.type[1:]}"

    @staticmethod
    def _parse_failure_step(stdout: str) -> Optional[int]:
        for line in stdout.strip().splitlines():
            line = line.strip()
            if line.startswith("some "):
                try:
                    n = int(line.split()[1])
                    if n >= 0:
                        return n
                except (IndexError, ValueError):
                    pass
            if line == "none":
                return None
        return None

    def _generate_code(self, world: WorldState, plan: List[Action]) -> str:
        state_code = (
            f'{{\n'
            f'    agentPos := {self._pos_to_lean(world.agent_pos)},\n'
            f'    keyPos := {self._pos_to_lean(world.key_pos)},\n'
            f'    doorPos := {self._pos_to_lean(world.door_pos)},\n'
            f'    hasKey := {"true" if world.has_key else "false"},\n'
            f'    doorUnlocked := {"true" if world.door_unlocked else "false"},\n'
            f'    obstacles := {self._obstacles_to_lean(world.obstacles)},\n'
            f'    gridSize := {world.grid_size}\n'
            f'}}'
        )

        if not plan:
            plan_code = "[]"
        else:
            items = ",\n      ".join(self._action_to_lean(a) for a in plan)
            plan_code = f"[\n      {items}\n    ]"

        code = LEAN_TEMPLATE.replace("{GENERATED_INIT_STATE}", state_code)
        code = code.replace("{GENERATED_PLAN}", plan_code)
        return code

    def verify(
        self,
        world: WorldState,
        plan: List[Action],
        output_dir: Optional[str] = None,
    ) -> Tuple[bool, str, str, Optional[int]]:
        """Verify a plan by generating a Lean file and running `lean`.

        Returns:
            (passed: bool, stdout: str, stderr: str, failure_step: Optional[int])
            failure_step is the index of the first failing action, or None if all pass.
        """
        code = self._generate_code(world, plan)

        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(__file__), "..", "lean")

        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "PlanVerifier.lean")
        self._generated_file = filepath

        with open(filepath, "w") as f:
            f.write(code)

        try:
            result = subprocess.run(
                [self.lean_binary, filepath],
                capture_output=True,
                text=True,
                timeout=30,
            )
            passed = result.returncode == 0
            failure_step = self._parse_failure_step(result.stdout) if not passed else None
            return passed, result.stdout, result.stderr, failure_step
        except FileNotFoundError:
            return False, "", (
                f"Lean binary '{self.lean_binary}' not found. "
                f"Install Lean 4 from https://leanprover.github.io/"
            ), None
        except subprocess.TimeoutExpired:
            return False, "", "Lean verification timed out after 30 seconds.", None

    def cleanup(self):
        if self._generated_file and os.path.exists(self._generated_file):
            os.remove(self._generated_file)
            self._generated_file = None

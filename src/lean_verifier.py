from __future__ import annotations

import os
import subprocess
import tempfile
from typing import List, Optional, Tuple

from .world_model import (
    WorldState, Action,
    ACTION_MOVE, ACTION_MOVE_CAREFULLY,
    ACTION_TRY_UNLOCK, ACTION_PASS_ITEM,
    MOVE_DIRECTIONS,
)


LEAN_TEMPLATE = '''
structure Position where
  x : Int
  y : Int
  deriving DecidableEq, Repr

structure World where
  agentPos : Position
  agentBpos : Position
  keyPos : Position
  doorPos : Position
  hasKey : Bool
  hasKeyB : Bool
  doorUnlocked : Bool
  obstacles : List Position
  gridSize : Int
  canPickupA : Bool
  canPickupB : Bool
  canUnlockA : Bool
  canUnlockB : Bool
  deriving DecidableEq, Repr

inductive Action : Type where
  | move (agent : Bool) (dx : Int) (dy : Int)
  | pickupKey (agent : Bool)
  | unlockDoor (agent : Bool)
  | openDoor (agent : Bool)
  | tryUnlock (agent : Bool)
  | moveCarefully (agent : Bool) (dx : Int) (dy : Int)
  | passItem (agent : Bool)
  deriving DecidableEq, Repr

open Action

def isValidPosition (w : World) (pos : Position) : Bool :=
  0 ≤ pos.x ∧ pos.x < w.gridSize ∧ 0 ≤ pos.y ∧ pos.y < w.gridSize

def isObstacle (w : World) (pos : Position) : Bool :=
  w.obstacles.any (fun o => o.x == pos.x ∧ o.y == pos.y)

def isFree (w : World) (pos : Position) : Bool :=
  isValidPosition w pos ∧ ¬ isObstacle w pos

def getAgentPos (w : World) (isB : Bool) : Position :=
  if isB then w.agentBpos else w.agentPos

def hasKeyFor (w : World) (isB : Bool) : Bool :=
  if isB then w.hasKeyB else w.hasKey

def setHasKey (w : World) (isB : Bool) (v : Bool) : World :=
  if isB then { w with hasKeyB := v } else { w with hasKey := v }

def setAgentPos (w : World) (isB : Bool) (pos : Position) : World :=
  if isB then { w with agentBpos := pos } else { w with agentPos := pos }

def canPickup (w : World) (isB : Bool) : Bool :=
  if isB then w.canPickupB else w.canPickupA

def canUnlock (w : World) (isB : Bool) : Bool :=
  if isB then w.canUnlockB else w.canUnlockA

def step (w : World) (a : Action) : List World :=
  match a with
  | .move isB dx dy =>
    let pos := getAgentPos w isB
    let newPos := Position.mk (pos.x + dx) (pos.y + dy)
    if isFree w newPos then
      [setAgentPos w isB newPos]
    else
      []
  | .pickupKey isB =>
    let pos := getAgentPos w isB
    if pos.x == w.keyPos.x ∧ pos.y == w.keyPos.y ∧ ¬ hasKeyFor w isB ∧ ¬ w.hasKey ∧ ¬ w.hasKeyB ∧ canPickup w isB then
      [setHasKey w isB true]
    else
      []
  | .unlockDoor isB =>
    let pos := getAgentPos w isB
    if pos.x == w.doorPos.x ∧ pos.y == w.doorPos.y ∧ hasKeyFor w isB ∧ ¬ w.doorUnlocked ∧ canUnlock w isB then
      [{ w with doorUnlocked := true }]
    else
      []
  | .openDoor isB =>
    let pos := getAgentPos w isB
    if pos.x == w.doorPos.x ∧ pos.y == w.doorPos.y ∧ w.doorUnlocked then
      [w]
    else
      []
  | .tryUnlock isB =>
    let pos := getAgentPos w isB
    if pos.x == w.doorPos.x ∧ pos.y == w.doorPos.y ∧ hasKeyFor w isB ∧ canUnlock w isB then
      [{ w with doorUnlocked := true }, setHasKey w isB false]
    else
      []
  | .moveCarefully isB dx dy =>
    let pos := getAgentPos w isB
    let target := Position.mk (pos.x + dx) (pos.y + dy)
    if ¬ isFree w target then
      []
    else
      let slipOutcomes : List World :=
        (List.range 4).flatMap (fun d =>
          let slipDx := if d = 0 then -1 else if d = 1 then 1 else 0
          let slipDy := if d = 2 then -1 else if d = 3 then 1 else 0
          let slipPos := Position.mk (pos.x + slipDx) (pos.y + slipDy)
          if slipPos ≠ target ∧ isFree w slipPos then
            [setAgentPos w isB slipPos]
          else
            []
        )
      setAgentPos w isB target :: slipOutcomes
  | .passItem isB =>
    let pos := getAgentPos w isB
    let otherPos := getAgentPos w (!isB)
    let dx := otherPos.x - pos.x
    let dy := otherPos.y - pos.y
    if hasKeyFor w isB ∧ ((dx = 1 ∧ dy = 0) ∨ (dx = -1 ∧ dy = 0) ∨ (dx = 0 ∧ dy = 1) ∨ (dx = 0 ∧ dy = -1)) then
      [setHasKey (setHasKey w isB false) (!isB) true]
    else
      []

def execPlan (w : World) (plan : List Action) : List World :=
  match plan with
  | [] => [w]
  | a :: rest =>
    (step w a).flatMap (fun w' => execPlan w' rest)

def isSafe (w : World) : Bool :=
  isValidPosition w w.agentPos ∧ ¬ isObstacle w w.agentPos ∧
  isValidPosition w w.agentBpos ∧ ¬ isObstacle w w.agentBpos

instance : Inhabited World where
  default := {
    agentPos := { x := 0, y := 0 }
    agentBpos := { x := 1, y := 0 }
    keyPos := { x := 0, y := 0 }
    doorPos := { x := 0, y := 0 }
    hasKey := false
    hasKeyB := false
    doorUnlocked := false
    obstacles := []
    gridSize := 0
    canPickupA := true
    canPickupB := true
    canUnlockA := true
    canUnlockB := true
  }

-- ═══════════════════════════════════════════════════════════════
--  GENERATED SECTION
-- ═══════════════════════════════════════════════════════════════

def initialState : World := {GENERATED_INIT_STATE}

def plan : List Action := {GENERATED_PLAN}

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


theorem plan_feasible : execPlan initialState plan ≠ [] := by
  native_decide

theorem all_outcomes_safe : ∀ w ∈ execPlan initialState plan, isSafe w := by
  native_decide

#eval failureStep
#eval execPlan initialState plan
#eval plan.map (fun a => match a with
  | .move isB _ _ => if isB then "[B] Move" else "[A] Move"
  | .pickupKey isB => if isB then "[B] PickupKey" else "[A] PickupKey"
  | .unlockDoor isB => if isB then "[B] UnlockDoor" else "[A] UnlockDoor"
  | .openDoor isB => if isB then "[B] OpenDoor" else "[A] OpenDoor"
  | .tryUnlock isB => if isB then "[B] TryUnlock" else "[A] TryUnlock"
  | .moveCarefully isB _ _ => if isB then "[B] MoveCarefully" else "[A] MoveCarefully"
  | .passItem isB => if isB then "[B] PassItem" else "[A] PassItem")
'''


class LeanVerifier:
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
        agent_flag = "true" if action.agent == "B" else "false"
        if action.type == ACTION_MOVE:
            return f"Action.move {agent_flag} ({action.dx}) ({action.dy})"
        if action.type == ACTION_MOVE_CAREFULLY:
            return f"Action.moveCarefully {agent_flag} ({action.dx}) ({action.dy})"
        if action.type == ACTION_TRY_UNLOCK:
            return f"Action.tryUnlock {agent_flag}"
        if action.type == ACTION_PASS_ITEM:
            return f"Action.passItem {agent_flag}"
        name_map = {
            "PickupKey": "pickupKey",
            "UnlockDoor": "unlockDoor",
            "OpenDoor": "openDoor",
        }
        lean_name = name_map.get(action.type, action.type)
        return f"Action.{lean_name[0].lower()}{lean_name[1:]} {agent_flag}"

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
            f'    agentPos := {self._pos_to_lean(world.agent_a_pos)},\n'
            f'    agentBpos := {self._pos_to_lean(world.agent_b_pos)},\n'
            f'    keyPos := {self._pos_to_lean(world.key_pos)},\n'
            f'    doorPos := {self._pos_to_lean(world.door_pos)},\n'
            f'    hasKey := {"true" if world.key_holder == "A" else "false"},\n'
            f'    hasKeyB := {"true" if world.key_holder == "B" else "false"},\n'
            f'    doorUnlocked := {"true" if world.door_unlocked else "false"},\n'
            f'    obstacles := {self._obstacles_to_lean(world.obstacles)},\n'
            f'    gridSize := {world.grid_size},\n'
            f'    canPickupA := {"true" if world.can_pickup.get("A", True) else "false"},\n'
            f'    canPickupB := {"true" if world.can_pickup.get("B", True) else "false"},\n'
            f'    canUnlockA := {"true" if world.can_unlock.get("A", True) else "false"},\n'
            f'    canUnlockB := {"true" if world.can_unlock.get("B", True) else "false"}\n'
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

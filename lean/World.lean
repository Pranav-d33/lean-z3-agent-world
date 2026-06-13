/--
World model for the Certified SMT Planner.

Reference file — the actual verification uses an auto-generated
self-contained PlanVerifier.lean. This file exists for documentation
and editor support.
-/

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
Returns all possible next states (empty if precondition violated).
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
    agentPos := { x := 0; y := 0 }
    keyPos := { x := 0; y := 0 }
    doorPos := { x := 0; y := 0 }
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

/--
Example: Demo scenario.
-/
def demoState : World := {
  agentPos := Position.mk 0 0,
  keyPos := Position.mk 0 1,
  doorPos := Position.mk 2 2,
  hasKey := false,
  doorUnlocked := false,
  obstacles := [],
  gridSize := 3
}

/--
Demo plan: Move(0,1) → PickupKey → Move(1,0) → Move(1,0) → Move(0,1) → UnlockDoor → OpenDoor
-/
def demoPlan : List Action := [
  Action.move 0 1,
  Action.pickupKey,
  Action.move 1 0,
  Action.move 1 0,
  Action.move 0 1,
  Action.unlockDoor,
  Action.openDoor
]

/-- Theorem: The demo plan succeeds from the demo state. -/
theorem demo_plan_succeeds : execPlan demoState demoPlan ≠ [] := by
  native_decide

#eval execPlan demoState demoPlan
#eval demoPlan.map actionToStr

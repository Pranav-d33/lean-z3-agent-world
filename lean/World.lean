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

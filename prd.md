# Product Requirements Document: Certified SMT Planner for AI Agents

> **Tech Stack:** Z3 (planning), Lean 4 (verification), Python + Tkinter (GUI)
> **Status:** Part 1 — Core Planner + GUI (MVP)

---

## Table of Contents

1. [Overall Goal](#overall-goal)
2. [System Architecture](#system-architecture)
3. [Part 1: Core Planner + GUI (MVP)](#part-1-core-planner--gui-mvp)
4. [Part 2: Counterexample Loop + Non-Deterministic Actions](#part-2-counterexample-loop--non-deterministic-actions)
5. [Part 3: Multi-Agent Extension](#part-3-multi-agent-extension)
6. [Cross-Part Requirements](#cross-part-requirements)
7. [Success Criteria](#success-criteria)

---

## Overall Goal

Build an interactive tool that demonstrates **verifiable AI planning**:

- **Z3** generates a plan (sequence of actions) for a grid-world agent.
- **Lean 4** verifies the plan's safety (preconditions, invariants).
- **GUI** visualizes the world, allows user input, and shows plan + verification results.

The project is split into three incremental parts to manage complexity.

---

## System Architecture

```
┌─────────────┐      JSON Plan       ┌──────────────┐
│   Z3 SMT    │ ──────────────────►  │  Lean 4      │
│   Planner   │                      │  Verifier    │
│  (Python)   │ ◄── counterexample   │  (Lean)      │
└─────────────┘      feedback         └──────────────┘
       │                                     │
       │ JSON plan                           │ pass/fail
       ▼                                     ▼
┌─────────────────────────────────────────────────┐
│              Tkinter GUI                         │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  3×3 Grid    │  │  Controls                 │  │
│  │  (Canvas)    │  │  [Find Plan] [Verify]     │  │
│  │              │  │  Plan text + Stepper      │  │
│  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Data Flow

1. **User Input** → GUI captures initial state + goal condition
2. **Find Plan** → GUI serialises state to JSON → calls Z3 planner → receives plan (JSON)
3. **Verify Plan** → GUI sends plan + initial state to Lean verifier → receives pass/fail
4. **Display** → GUI renders grid, plan text, stepper controls

---

## Part 1: Core Planner + GUI (MVP)

### 1.1 World Model

| Property | Value |
|----------|-------|
| Grid size | 3×3 (fixed, configurable later) |
| Agent | Single position (x, y) |
| Key | Position + boolean (picked up) |
| Door | Position + boolean (locked/unlocked) |
| Obstacles | Optional set of blocked cells |
| Grid state | (x, y, has_key, door_unlocked) |

**State representation:**
```
Agent position:  (x, y)  where 0 ≤ x,y < grid_size
Has key:         boolean
Door unlocked:   boolean
Obstacles:       set of (x, y) positions
```

### 1.2 Actions (Deterministic)

All actions are deterministic in Part 1:

| Action | Precondition | Effect |
|--------|-------------|--------|
| `Move(dx, dy)` | new position inside grid AND not obstacle | agent moves by (dx, dy) |
| `PickupKey` | agent at key's cell AND key not yet picked | has_key := True |
| `UnlockDoor` | agent at door cell AND has_key = True | door_unlocked := True |
| `OpenDoor` | door unlocked AND agent at door | (symbolic pass-through) |

**Domain of Move:** dx, dy ∈ {-1, 0, 1}, not both 0.

### 1.3 Z3 Planner (Bounded Horizon)

**Approach:** Iterative deepening — try horizon = 1, 2, …, max_horizon (default 8). Return the first satisfiable plan (shortest).

**Encoding (via z3 Python API):**
- State variables per time step t (0..horizon):
  - `x[t]`, `y[t]` — Int (grid coordinates)
  - `has_key[t]` — Bool
  - `door_unlocked[t]` — Bool
- Action variables per time step t (0..horizon−1):
  - `action_type[t]` — Int enumeration {Move=0, PickupKey=1, UnlockDoor=2, OpenDoor=3}
  - `dx[t]`, `dy[t]` — Int (only constrained when action_type[t] = Move)
- Constraints:
  - Initial state fixed at t=0
  - Action preconditions => state at t
  - Action effects => state at t+1
  - Frame axioms (unchanged variables carry forward)
  - Goal condition at t=horizon

**Input:** Initial state (JSON), goal condition (JSON), max horizon (int)

**Output:** Plan as list of actions (JSON) or `{"status": "unsat"}`

### 1.4 Lean Verifier

**Approach:** Generate a self-contained Lean 4 file containing:

1. `Position` structure — x: Int, y: Int
2. `World` structure — agent_pos, key_pos, door_pos, has_key, door_unlocked, obstacles, grid_size
3. `Action` inductive type — Move(dx, dy), PickupKey, UnlockDoor, OpenDoor
4. `step : World → Action → Option World` — state transition (None if precondition violated)
5. `execPlan : World → List Action → Option World` — sequential plan execution
6. `theorem plan_succeeds : execPlan initial_state plan ≠ none := by native_decide`

**Verification:** Run `lean PlanVerifier.lean`. Return code 0 = verified, non-zero = verification failed.

**Why `native_decide`:** The proposition `execPlan initial_state plan ≠ none` is decidable for any bounded plan (finite state space, finite plan length). `native_decide` compiles it to native code and decides it automatically.

**Output to Python:** exit code (0 = verified), stdout/stderr for diagnostics.

### 1.5 GUI (Tkinter)

**Layout:**

```
┌─────────────────────────────────────────────┐
│  Certified SMT Planner — Agent World         │
├──────────────┬──────────────────────────────┤
│              │  Controls                     │
│   3×3 Grid   │  ○ Place Agent  ○ Place Key   │
│   (Canvas)   │  ○ Place Door  ○ Obstacle     │
│              │                               │
│   ● Agent    │  Goal: □ door_unlocked         │
│   🔑 Key     │  [Find Plan]  [Verify Plan]   │
│   🚪 Door    │                               │
│   █ Obstacle │  Plan:                        │
│              │  ┌─────────────────────────┐  │
│              │  │ 1. Move(0,1)            │  │
│              │  │ 2. PickupKey            │  │
│              │  │ 3. Move(1,0)            │  │
│              │  └─────────────────────────┘  │
│              │  Status: ✅ Verified          │
│              │                               │
│              │  [◀ Reset] [◀ Back] [Fwd ▶]   │
│              │  Step: 2/5                    │
└──────────────┴──────────────────────────────┘
```

**Grid rendering (on Canvas):**
- Cells drawn as 100×100 rectangles (300×300 total for 3×3)
- Agent: blue filled circle (r=20)
- Key: yellow circle with "K" text
- Door (locked): dark red filled rectangle
- Door (unlocked): green filled rectangle
- Obstacle: dark gray filled square
- Active step: light blue overlay on agent's current cell

**Controls:**
- Radio buttons to select edit mode (agent, key, door, obstacle)
- Click on grid cell to place the selected entity
- "Find Plan" button → runs Z3 planner — displays plan in text widget
- "Verify Plan" button → runs Lean verifier — shows "✅ Verified" or "❌ Failed"
- Stepper buttons → step through plan, highlight agent position

### 1.6 Deliverables (Part 1)

- Working command-line pipeline: Z3 script + Lean verification
- GUI that can invoke both and display results
- Simple demo: initial state (0,0), key at (0,1), door at (2,2) locked
- Expected plan: move to key, pickup, move to door, unlock, open

---

## Part 2: Counterexample Loop + Non-Deterministic Actions

### 2.1 Counterexample Loop (CEGAR-lite)

After Lean verification, if verification fails (e.g., a precondition violated at some step), the Lean script outputs:

1. The step number where the failure occurs
2. The missing condition (which precondition was violated)

The GUI feeds this back to Z3 as an additional constraint, then re-runs the planner to find a new plan that avoids the failure.

Iterate until a verifiable plan is found or Z3 reports unsat (no plan exists).

This creates a simple counterexample-guided refinement loop — a classic AI technique.

### 2.2 Non-Deterministic Actions

Introduce actions with multiple possible outcomes:

| Action | Possible Outcomes |
|--------|------------------|
| `TryUnlock` | Success (door opens) OR Failure (key breaks, door stays locked) |
| `MoveCarefully` | Intended move OR slip to random adjacent cell |

**Z3 encoding:** Existential quantifiers OR multiple possible next states (disjunction).

**Lean verification:** Prove "for all possible outcomes, the agent never violates a safety property" — quantified over all branches.

### 2.3 Deliverables (Part 2)

- Loop that repeatedly refines the plan based on verification counterexamples
- Non-deterministic action example with Lean proof of universal safety
- Updated GUI showing iteration count and final verifiable plan

---

## Part 3: Multi-Agent Extension

### 3.1 Two Cooperative Agents

- Agents A and B on the same grid
- Each has its own key/door or shared resources
- Actions: Move, Pickup, Unlock, Pass (transfer item)
- Z3 encodes interleaved actions with constraints: no collisions, no deadlocks

### 3.2 Lean Verification Properties

- **No collision:** agents never occupy the same cell (proved for all steps)
- **Mutual exclusion:** only one agent holds the shared key at a time
- **Liveness (optional):** if a plan exists, both eventually reach their goals

### 3.3 GUI Enhancements

- Show both agents with different colors
- Step through interleaved actions
- Display individual verification results per agent

---

## Cross-Part Requirements

| Component | Technology | Notes |
|-----------|-----------|-------|
| Z3 integration | z3 Python API | Direct API calls, no subprocess needed |
| Lean verification | Lean 4 + `native_decide` | Self-contained generated files |
| GUI | Python Tkinter | Separated from logic; communicates via function calls |
| Data exchange | JSON | Plan format: `[{"action": "Move", "dx": 1, "dy": 0}, ...]` |
| Error handling | User-friendly messages | If Z3 fails or Lean times out, GUI displays suggestion |

---

## Success Criteria

### Part 1 ✅
- User can input a world state via the GUI
- Z3 generates a valid plan for the demo scenario
- Lean verifies the plan successfully (exit code 0)
- GUI displays plan, stepper, and verification result
- Command-line pipeline works independently of GUI

### Part 2 ✅
- If verification fails, system suggests a corrected plan automatically
- Non-deterministic action proves all outcomes safe via universal quantification

### Part 3 ✅
- Two agents cooperate without collision, verified by Lean
- GUI shows both agents with interleaved action stepping

---

## Project Structure

```
agent_world/
├── prd.md                 # This document
├── README.md              # Quick start guide
├── requirements.txt       # Python dependencies
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── world_model.py     # World state, entities, actions
│   ├── z3_planner.py      # Z3 bounded-horizon planner
│   ├── lean_verifier.py   # Lean verification (file generation + subprocess)
│   ├── gui.py             # Tkinter GUI
│   └── main.py            # Entry point
├── lean/
│   ├── lakefile.lean      # Lean project file (for editor support)
│   └── World.lean         # World model definitions (reference)
└── plans/                 # Generated plan JSON files
```

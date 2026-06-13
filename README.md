# Z3-Lean Agent World

An interactive tool demonstrating **verifiable AI planning** with a CEGAR (Counterexample-Guided Abstraction Refinement) loop.

- **Z3** generates a plan (sequence of actions) for a grid-world agent
- **Lean 4** verifies the plan's safety (preconditions, invariants, all non-deterministic outcomes)
- **Pixel-art 2D GUI** (Pygame) to interact with the world, place entities, and step through plans
- **CEGAR loop** iterates between Z3 and Lean until a verified plan is found
- **Non-deterministic actions** (TryUnlock, MoveCarefully) with Lean proofs over all branches

## Quick Start

### Prerequisites

- Python 3.10+
- [Lean 4](https://leanprover.github.io/) — for plan verification (install via `elan`)
- [Z3](https://github.com/Z3Prover/z3) — installed automatically with `pip`

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
python -m src.main          # Launch the pixel-art GUI
python -m src.main --cli    # Run CLI demo
```

## Project Structure

```
agent_world/
├── prd.md                 # Product Requirements Document
├── lean-toolchain         # Lean toolchain version
├── src/
│   ├── world_model.py     # World state, actions (deterministic + non-deterministic)
│   ├── z3_planner.py      # Z3 bounded-horizon planner
│   ├── lean_verifier.py   # Lean verification (file generation + subprocess)
│   ├── cegar.py           # CEGAR loop (counterexample-guided refinement)
│   ├── gui.py             # Pixel-art 2D GUI (Pygame)
│   └── main.py            # Entry point
├── lean/
│   ├── lakefile.lean      # Lean project file
│   └── World.lean         # World model definitions (reference)
└── plans/                 # Generated plan JSON files
```

## Features

### Part 1: Core (✅ done)
- Grid world with agent, key, door, obstacles
- Deterministic actions: Move, PickupKey, UnlockDoor, OpenDoor
- Z3 bounded-horizon planner (iterative deepening)
- Lean 4 verification via `native_decide`
- Pixel-art 2D GUI (Pygame)

### Part 2: CEGAR + Non-determinism (✅ done)
- **Counterexample loop**: if Lean rejects a plan, the failing step is diagnosed and the plan is refined
- **Non-deterministic actions**:
  - `TryUnlock` — may succeed (door opens) or fail (key breaks)
  - `MoveCarefully` — may reach target or slip to adjacent cell
- Lean proves ALL outcomes are safe (universal quantification over branches)
- `failureStep` diagnostic identifies the first failing action

## Architecture

```
┌─────────────┐  plan  ┌──────────────┐  pass/fail  ┌──────────┐
│   Z3 SMT    │───────►│  Lean 4      │────────────►│  CEGAR   │
│   Planner   │◄───────│  Verifier    │             │  Loop    │
└─────────────┘ refine └──────────────┘             └──────────┘
       │                                                     │
       │                                                     │
       ▼                                                     ▼
    ┌──────────────────────────────────────────────────────────┐
    │              Pixel-art 2D GUI (Pygame)                   │
    │  8×8 grid  |  Edit mode  |  Plan display  |  Stepper   │
    └──────────────────────────────────────────────────────────┘
```

## Actions

| Action | Deterministic? | Precondition | Effect |
|--------|:------------:|-------------|--------|
| Move(dx,dy) | ✅ | target is free | agent moves to target |
| PickupKey | ✅ | at key, not yet picked | has_key := true |
| UnlockDoor | ✅ | at door, has key, door locked | door_unlocked := true |
| OpenDoor | ✅ | at door, door unlocked | (pass-through) |
| TryUnlock | ❌ | at door, has key | success (door opens) OR failure (key breaks) |
| MoveCarefully(dx,dy) | ❌ | target is free | reach target OR slip to adjacent cell |

## Controls

- **Edit Mode**: Select Agent, Key, Door, or Obstacle and click the grid
- **Goal**: Choose "Door unlocked" or "At door + unlocked"
- **Find Plan**: Runs CEGAR loop (Z3 + Lean) to find a verified plan
- **Verify Plan**: Runs Lean on the current plan
- **Stepper**: Step through the plan with |<  <  >  >|

## License

MIT

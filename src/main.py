#!/usr/bin/env python3
"""
Entry point for the Certified SMT Planner.

Usage:
    python -m src.main              # Launch GUI
    python -m src.main --cli        # Run CLI demo (plan + verify)
"""

from __future__ import annotations

import argparse
import sys
import os

from .world_model import WorldState, goal_door_unlocked, plan_to_json
from .z3_planner import Z3Planner
from .lean_verifier import LeanVerifier


def run_cli_demo():
    """Run a command-line demo: generate a plan and verify it."""
    print("=" * 60)
    print("Certified SMT Planner — CLI Demo")
    print("=" * 60)

    world = WorldState.demo()
    print(f"\nInitial state:")
    print(f"  Agent: ({world.agent_pos.x}, {world.agent_pos.y})")
    print(f"  Key:   ({world.key_pos.x}, {world.key_pos.y})")
    print(f"  Door:  ({world.door_pos.x}, {world.door_pos.y}) (locked)")
    print(f"  Grid:  {world.grid_size}\u00d7{world.grid_size}")
    if world.obstacles:
        print(f"  Obstacles: {world.obstacles}")
    else:
        print(f"  Obstacles: none")
    print(f"\n  Goal: door unlocked")

    print(f"\n--- Finding Plan ---")
    planner = Z3Planner(max_horizon=8)
    plan = planner.find_plan(world, goal_door_unlocked)

    if plan is None:
        print("No plan found (unsat within max horizon)")
        sys.exit(1)

    print(f"\nPlan ({len(plan)} actions):")
    for i, action in enumerate(plan, 1):
        print(f"  {i:2d}. {action}")

    print(f"\n--- Verifying with Lean ---")
    verifier = LeanVerifier()
    passed, stdout, stderr, failure_step = verifier.verify(world, plan)

    if passed:
        print(f"  ✅ Plan verified by Lean")
        print(f"\nExecution trace (one possible path):")
        state = world
        for i, action in enumerate(plan, 1):
            results = state.apply_action(action)
            if not results:
                print(f"  ❌ Step {i}: {action} — FAILED (precondition violated)")
                sys.exit(1)
            result = results[0]
            print(f"  {i:2d}. {str(action):20s} \u2192 ({result.agent_pos.x},{result.agent_pos.y}), "
                  f"key={'✓' if result.has_key else '✗'}, "
                  f"door={'✓' if result.door_unlocked else '✗'}")
            state = result
        print(f"\n  Goal achieved!")
    else:
        print(f"  ❌ Verification failed")
        if stderr:
            print(f"  Error: {stderr[:300]}")
        if stdout:
            print(f"  Output: {stdout[:300]}")

    os.makedirs("plans", exist_ok=True)
    plan_path = "plans/demo_plan.json"
    with open(plan_path, "w") as f:
        f.write(plan_to_json(plan))
    print(f"\nPlan saved to {plan_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Certified SMT Planner for AI Agents"
    )
    parser.add_argument(
        "--cli", action="store_true",
        help="Run CLI demo instead of launching GUI"
    )
    args = parser.parse_args()

    if args.cli:
        run_cli_demo()
    else:
        from .gui import AgentWorldGUI

        app = AgentWorldGUI()
        app.run()


if __name__ == "__main__":
    main()

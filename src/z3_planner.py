"""
Z3 bounded-horizon planner for the grid-world agent.

Uses iterative deepening: tries horizons 1..max_horizon and returns
the shortest plan found. Encodes the problem using the z3 Python API
with quantifier-free linear integer arithmetic (QF_LIA) + Booleans.
"""

from __future__ import annotations
from typing import List, Callable, Optional
import logging

from z3 import Int, Bool, Solver, And, Or, Not, Implies, If, sat, Sum  # type: ignore

from .world_model import (
    WorldState, Position, Action,
    ACTION_MOVE, ACTION_PICKUP_KEY, ACTION_UNLOCK_DOOR, ACTION_OPEN_DOOR,
    ACTION_TRY_UNLOCK, ACTION_MOVE_CAREFULLY,
    MOVE_DIRECTIONS, goal_door_unlocked, goal_at_door_and_unlocked,
)

logger = logging.getLogger(__name__)

# Action type encoding
AT_MOVE = 0
AT_PICKUP_KEY = 1
AT_UNLOCK_DOOR = 2
AT_OPEN_DOOR = 3
AT_TRY_UNLOCK = 4
AT_MOVE_CAREFULLY = 5

ACTION_NAMES = {
    AT_MOVE: ACTION_MOVE, AT_PICKUP_KEY: ACTION_PICKUP_KEY,
    AT_UNLOCK_DOOR: ACTION_UNLOCK_DOOR, AT_OPEN_DOOR: ACTION_OPEN_DOOR,
    AT_TRY_UNLOCK: ACTION_TRY_UNLOCK, AT_MOVE_CAREFULLY: ACTION_MOVE_CAREFULLY,
}


class Z3Planner:
    """Bounded-horizon Z3 planner with iterative deepening."""

    def __init__(self, max_horizon: int = 8):
        self.max_horizon = max_horizon

    def find_plan(
        self,
        initial_state: WorldState,
        goal_condition: Callable[[WorldState], bool],
    ) -> List[Action] | None:
        """Try horizons from 1 to max_horizon, return the shortest plan.

        Returns list of Action on success, None if unsat.
        """
        for horizon in range(1, self.max_horizon + 1):
            logger.info(f"Trying horizon = {horizon}")
            plan = self._solve(initial_state, goal_condition, horizon)
            if plan is not None:
                logger.info(f"Plan found at horizon {horizon}")
                return plan
        logger.info("No plan found within max horizon")
        return None

    def _solve(
        self,
        initial_state: WorldState,
        goal_condition: Callable[[WorldState], bool],
        horizon: int,
    ) -> List[Action] | None:
        gs = initial_state.grid_size
        obstacles = initial_state.obstacles
        key_pos = initial_state.key_pos
        door_pos = initial_state.door_pos

        solver = Solver()

        # --- State variables ---
        x = [Int(f"x_{t}") for t in range(horizon + 1)]
        y = [Int(f"y_{t}") for t in range(horizon + 1)]
        has_key = [Bool(f"has_key_{t}") for t in range(horizon + 1)]
        door_unlocked = [Bool(f"door_unlocked_{t}") for t in range(horizon + 1)]

        # --- Action variables ---
        action_type = [Int(f"act_{t}") for t in range(horizon)]
        dx_var = [Int(f"dx_{t}") for t in range(horizon)]
        dy_var = [Int(f"dy_{t}") for t in range(horizon)]

        # --- Initial state ---
        solver.add(x[0] == initial_state.agent_pos.x)
        solver.add(y[0] == initial_state.agent_pos.y)
        solver.add(has_key[0] == initial_state.has_key)
        solver.add(door_unlocked[0] == initial_state.door_unlocked)

        # --- State bounds (grid boundaries) ---
        for t in range(horizon + 1):
            solver.add(x[t] >= 0)
            solver.add(x[t] < gs)
            solver.add(y[t] >= 0)
            solver.add(y[t] < gs)

        # --- Action type constraints ---
        for t in range(horizon):
            solver.add(
                Or(action_type[t] == AT_MOVE,
                   action_type[t] == AT_PICKUP_KEY,
                   action_type[t] == AT_UNLOCK_DOOR,
                   action_type[t] == AT_OPEN_DOOR,
                   action_type[t] == AT_TRY_UNLOCK,
                   action_type[t] == AT_MOVE_CAREFULLY)
            )

        # --- Movement direction constraints (for Move, MoveCarefully) ---
        for t in range(horizon):
            move = Or(action_type[t] == AT_MOVE, action_type[t] == AT_MOVE_CAREFULLY)
            solver.add(Implies(move, Or(
                And(dx_var[t] == -1, dy_var[t] == 0),
                And(dx_var[t] == 1,  dy_var[t] == 0),
                And(dx_var[t] == 0,  dy_var[t] == -1),
                And(dx_var[t] == 0,  dy_var[t] == 1),
            )))

        # --- Transition constraints ---
        for t in range(horizon):
            move = action_type[t] == AT_MOVE
            pickup = action_type[t] == AT_PICKUP_KEY
            unlock = action_type[t] == AT_UNLOCK_DOOR
            open_door = action_type[t] == AT_OPEN_DOOR
            try_unlock = action_type[t] == AT_TRY_UNLOCK
            move_carefully = action_type[t] == AT_MOVE_CAREFULLY

            new_x = x[t] + dx_var[t]
            new_y = y[t] + dy_var[t]
            in_bounds = And(new_x >= 0, new_x < gs, new_y >= 0, new_y < gs)

            not_obstacle = True
            for ox, oy in obstacles:
                not_obstacle = And(not_obstacle, Not(And(new_x == ox, new_y == oy)))

            # Move: precondition = new pos in bounds & not obstacle
            solver.add(Implies(move, And(
                in_bounds,
                not_obstacle,
                x[t + 1] == new_x,
                y[t + 1] == new_y,
                has_key[t + 1] == has_key[t],
                door_unlocked[t + 1] == door_unlocked[t],
            )))

            # PickupKey: precondition = at key position, key not yet picked
            solver.add(Implies(pickup, And(
                x[t] == key_pos.x,
                y[t] == key_pos.y,
                Not(has_key[t]),
                x[t + 1] == x[t],
                y[t + 1] == y[t],
                has_key[t + 1] == True,
                door_unlocked[t + 1] == door_unlocked[t],
            )))

            # UnlockDoor: precondition = at door, has key, door still locked
            solver.add(Implies(unlock, And(
                x[t] == door_pos.x,
                y[t] == door_pos.y,
                has_key[t],
                Not(door_unlocked[t]),
                x[t + 1] == x[t],
                y[t + 1] == y[t],
                has_key[t + 1] == has_key[t],
                door_unlocked[t + 1] == True,
            )))

            # OpenDoor: precondition = at door, door is unlocked
            solver.add(Implies(open_door, And(
                x[t] == door_pos.x,
                y[t] == door_pos.y,
                door_unlocked[t],
                x[t + 1] == x[t],
                y[t + 1] == y[t],
                has_key[t + 1] == has_key[t],
                door_unlocked[t + 1] == door_unlocked[t],
            )))

            # TryUnlock: precondition = at door, has key
            # Non-deterministic: success (door opens) OR failure (key breaks)
            solver.add(Implies(try_unlock, And(
                x[t] == door_pos.x,
                y[t] == door_pos.y,
                has_key[t],
                x[t + 1] == x[t],
                y[t + 1] == y[t],
                Or(
                    And(door_unlocked[t + 1] == True, has_key[t + 1] == has_key[t]),
                    And(door_unlocked[t + 1] == door_unlocked[t], has_key[t + 1] == False),
                ),
            )))

            # MoveCarefully: precondition = target is free
            # Non-deterministic: reach target OR slip to adjacent free cell
            slip_conditions = []
            for sd_x, sd_y in MOVE_DIRECTIONS:
                slip_to_x = x[t] + sd_x
                slip_to_y = y[t] + sd_y
                slip_free = And(slip_to_x >= 0, slip_to_x < gs,
                                slip_to_y >= 0, slip_to_y < gs)
                for ox, oy in obstacles:
                    slip_free = And(slip_free, Not(And(slip_to_x == ox, slip_to_y == oy)))
                slip_not_target = Not(And(slip_to_x == new_x, slip_to_y == new_y))
                slip_conditions.append(And(slip_free, slip_not_target,
                                           x[t + 1] == slip_to_x, y[t + 1] == slip_to_y))

            solver.add(Implies(move_carefully, And(
                in_bounds,
                not_obstacle,
                Or(
                    And(x[t + 1] == new_x, y[t + 1] == new_y),
                    *slip_conditions,
                ),
                has_key[t + 1] == has_key[t],
                door_unlocked[t + 1] == door_unlocked[t],
            )))

        # --- Goal condition at final step ---
        goal_exprs = encode_goal(
            goal_condition, door_pos,
            x[horizon], y[horizon],
            has_key[horizon], door_unlocked[horizon],
        )
        solver.add(And(*goal_exprs))

        # --- Solve ---
        if solver.check() == sat:
            model = solver.model()
            return self._extract_plan(model, horizon, action_type, dx_var, dy_var)

        return None

    def _action_type_id(self, action: Action) -> int:
        for tid, name in ACTION_NAMES.items():
            if name == action.type:
                return tid
        return AT_MOVE

    def _extract_plan(
        self,
        model,
        horizon: int,
        action_type,
        dx_var,
        dy_var,
    ) -> List[Action]:
        plan: List[Action] = []
        for t in range(horizon):
            at = model.eval(action_type[t]).as_long()
            action_name = ACTION_NAMES.get(at)
            if action_name is None:
                logger.warning(f"Unknown action type {at} at step {t}, skipping")
                continue

            if action_name in (ACTION_MOVE, ACTION_MOVE_CAREFULLY):
                dx = model.eval(dx_var[t]).as_long()
                dy = model.eval(dy_var[t]).as_long()
                plan.append(Action(action_name, dx=dx, dy=dy))
            else:
                plan.append(Action(action_name))

        return plan


def encode_goal(
    goal_fn: Callable[[WorldState], bool],
    door_pos: Position,
    x_expr,
    y_expr,
    has_key_expr,
    door_unlocked_expr,
):
    """Encode a goal predicate as Z3 constraints.

    Maps Python goal functions that operate on WorldState to Z3 expressions
    over the final-step state variables.
    """
    if goal_fn is goal_door_unlocked:
        return [door_unlocked_expr == True]

    if goal_fn is goal_at_door_and_unlocked:
        return [
            door_unlocked_expr == True,
            x_expr == door_pos.x,
            y_expr == door_pos.y,
        ]

    raise ValueError(f"Unknown goal function: {goal_fn.__name__}")

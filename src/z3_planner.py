from __future__ import annotations
from typing import List, Callable, Optional
import logging

from z3 import Int, Bool, Solver, And, Or, Not, Implies, sat

from .world_model import (
    WorldState, Position, Action,
    ACTION_MOVE, ACTION_PICKUP_KEY, ACTION_UNLOCK_DOOR, ACTION_OPEN_DOOR,
    ACTION_TRY_UNLOCK, ACTION_MOVE_CAREFULLY, ACTION_PASS_ITEM,
    MOVE_DIRECTIONS, goal_door_unlocked, goal_at_door_and_unlocked,
)

logger = logging.getLogger(__name__)

AT_MOVE = 0
AT_PICKUP_KEY = 1
AT_UNLOCK_DOOR = 2
AT_OPEN_DOOR = 3
AT_TRY_UNLOCK = 4
AT_MOVE_CAREFULLY = 5
AT_PASS_ITEM = 6

ACTION_NAMES = {
    AT_MOVE: ACTION_MOVE, AT_PICKUP_KEY: ACTION_PICKUP_KEY,
    AT_UNLOCK_DOOR: ACTION_UNLOCK_DOOR, AT_OPEN_DOOR: ACTION_OPEN_DOOR,
    AT_TRY_UNLOCK: ACTION_TRY_UNLOCK, AT_MOVE_CAREFULLY: ACTION_MOVE_CAREFULLY,
    AT_PASS_ITEM: ACTION_PASS_ITEM,
}

AGENTS = ["A", "B"]
AGENT_INDICES = [("A", 0), ("B", 1)]


class Z3Planner:
    def __init__(self, max_horizon: int = 20):
        self.max_horizon = max_horizon

    def find_plan(
        self,
        initial_state: WorldState,
        goal_condition: Callable[[WorldState], bool],
    ) -> List[Action] | None:
        for horizon in range(1, self.max_horizon + 1):
            logger.info(f"Trying horizon = {horizon}")
            plan = self._solve(initial_state, goal_condition, horizon)
            if plan is not None:
                logger.info(f"Plan found at horizon {horizon}")
                return plan
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
        init_a = initial_state.agent_a_pos
        init_b = initial_state.agent_b_pos

        solver = Solver()

        ax = [Int(f"ax_{t}") for t in range(horizon + 1)]
        ay = [Int(f"ay_{t}") for t in range(horizon + 1)]
        bx = [Int(f"bx_{t}") for t in range(horizon + 1)]
        by = [Int(f"by_{t}") for t in range(horizon + 1)]
        ha = [Bool(f"ha_{t}") for t in range(horizon + 1)]
        hb = [Bool(f"hb_{t}") for t in range(horizon + 1)]
        du = [Bool(f"du_{t}") for t in range(horizon + 1)]

        wh = [Int(f"wh_{t}") for t in range(horizon)]
        at = [Int(f"at_{t}") for t in range(horizon)]
        di = [Int(f"dx_{t}") for t in range(horizon)]
        dj = [Int(f"dy_{t}") for t in range(horizon)]

        solver.add(ax[0] == init_a.x)
        solver.add(ay[0] == init_a.y)
        solver.add(bx[0] == init_b.x)
        solver.add(by[0] == init_b.y)
        solver.add(ha[0] == (initial_state.key_holder == "A"))
        solver.add(hb[0] == (initial_state.key_holder == "B"))
        solver.add(du[0] == initial_state.door_unlocked)

        for t in range(horizon + 1):
            solver.add(And(ax[t] >= 0, ax[t] < gs, ay[t] >= 0, ay[t] < gs))
            solver.add(And(bx[t] >= 0, bx[t] < gs, by[t] >= 0, by[t] < gs))
            solver.add(Or(ax[t] != bx[t], ay[t] != by[t]))
            solver.add(Not(And(ha[t], hb[t])))

        for t in range(horizon):
            solver.add(Or(wh[t] == 0, wh[t] == 1))
            solver.add(Or(*[at[t] == v for v in ACTION_NAMES]))
            solver.add(Implies(Or(at[t] == AT_MOVE, at[t] == AT_MOVE_CAREFULLY), Or(
                And(di[t] == -1, dj[t] == 0), And(di[t] == 1, dj[t] == 0),
                And(di[t] == 0, dj[t] == -1), And(di[t] == 0, dj[t] == 1),
            )))
            # Agent capability constraints
            for w, who_idx in AGENT_INDICES:
                if not initial_state.can_pickup.get(w, True):
                    solver.add(Not(And(wh[t] == who_idx, at[t] == AT_PICKUP_KEY)))
                if not initial_state.can_unlock.get(w, True):
                    solver.add(Not(And(wh[t] == who_idx, Or(at[t] == AT_UNLOCK_DOOR, at[t] == AT_TRY_UNLOCK))))

        def agent_pos(who, t):
            return (ax[t], ay[t], ax[t+1], ay[t+1]) if who == "A" else (bx[t], by[t], bx[t+1], by[t+1])

        def other_pos(who, t):
            return (bx[t], by[t], bx[t+1], by[t+1]) if who == "A" else (ax[t], ay[t], ax[t+1], ay[t+1])

        def is_who(who, t):
            return wh[t] == (0 if who == "A" else 1)

        def h_self(who, t):
            return ha[t] if who == "A" else hb[t]

        def h_self1(who):
            return ha if who == "A" else hb

        def h_other(who, t):
            return hb[t] if who == "A" else ha[t]

        def h_other1(who):
            return hb if who == "A" else ha

        for t in range(horizon):
            for w in AGENTS:
                ox, oy, ox1, oy1 = other_pos(w, t)
                solver.add(Implies(is_who(w, t), And(
                    ox1 == ox, oy1 == oy,
                    Implies(at[t] != AT_PASS_ITEM, h_other1(w)[t+1] == h_other(w, t)),
                )))
            # Default key-frame for active agent (overridden by pickup/pass/try)
            no_key_change = And(at[t] != AT_PICKUP_KEY, at[t] != AT_TRY_UNLOCK, at[t] != AT_PASS_ITEM)
            for w in AGENTS:
                solver.add(Implies(And(is_who(w, t), no_key_change),
                                   h_self1(w)[t+1] == h_self(w, t)))

            for w in AGENTS:
                cx, cy, nx, ny = agent_pos(w, t)
                a = And(is_who(w, t), at[t] == AT_MOVE)
                nobs = True
                for ox, oy in obstacles:
                    nobs = And(nobs, Not(And(cx + di[t] == ox, cy + dj[t] == oy)))
                solver.add(Implies(a, And(
                    cx + di[t] >= 0, cx + di[t] < gs,
                    cy + dj[t] >= 0, cy + dj[t] < gs,
                    nobs,
                    nx == cx + di[t], ny == cy + dj[t],
                    du[t + 1] == du[t],
                )))

                a = And(is_who(w, t), at[t] == AT_PICKUP_KEY)
                solver.add(Implies(a, And(
                    cx == key_pos.x, cy == key_pos.y,
                    Not(h_self(w, t)), Not(ha[t]), Not(hb[t]),
                    nx == cx, ny == cy,
                    h_self1(w)[t + 1] == True,
                    du[t + 1] == du[t],
                )))

                a = And(is_who(w, t), at[t] == AT_UNLOCK_DOOR)
                solver.add(Implies(a, And(
                    cx == door_pos.x, cy == door_pos.y,
                    h_self(w, t), Not(du[t]),
                    nx == cx, ny == cy,
                    du[t + 1] == True,
                )))

                a = And(is_who(w, t), at[t] == AT_OPEN_DOOR)
                solver.add(Implies(a, And(
                    cx == door_pos.x, cy == door_pos.y, du[t],
                    nx == cx, ny == cy,
                    du[t + 1] == du[t],
                )))

                a = And(is_who(w, t), at[t] == AT_TRY_UNLOCK)
                solver.add(Implies(a, And(
                    cx == door_pos.x, cy == door_pos.y,
                    h_self(w, t),
                    nx == cx, ny == cy,
                    Or(
                        And(du[t + 1] == True, h_self1(w)[t + 1] == h_self(w, t)),
                        And(du[t + 1] == du[t], h_self1(w)[t + 1] == False),
                    ),
                )))

                a = And(is_who(w, t), at[t] == AT_MOVE_CAREFULLY)
                nobs = True
                for ox, oy in obstacles:
                    nobs = And(nobs, Not(And(cx + di[t] == ox, cy + dj[t] == oy)))
                solver.add(Implies(a, And(
                    cx + di[t] >= 0, cx + di[t] < gs,
                    cy + dj[t] >= 0, cy + dj[t] < gs,
                    nobs,
                    nx == cx + di[t], ny == cy + dj[t],
                    du[t + 1] == du[t],
                )))

                act = And(is_who(w, t), at[t] == AT_PASS_ITEM)
                ox, oy, _, _ = other_pos(w, t)
                adj = Or(
                    And(ox == cx + 1, oy == cy),
                    And(ox == cx - 1, oy == cy),
                    And(ox == cx, oy == cy + 1),
                    And(ox == cx, oy == cy - 1),
                )
                solver.add(Implies(act, And(
                    h_self(w, t), adj,
                    nx == cx, ny == cy,
                    h_self1(w)[t + 1] == False,
                    h_other1(w)[t + 1] == True,
                    du[t + 1] == du[t],
                )))

        # Goal
        if goal_condition is goal_door_unlocked:
            solver.add(du[horizon] == True)
        elif goal_condition is goal_at_door_and_unlocked:
            solver.add(du[horizon] == True)
            solver.add(Or(
                And(ax[horizon] == door_pos.x, ay[horizon] == door_pos.y),
                And(bx[horizon] == door_pos.x, by[horizon] == door_pos.y),
            ))
        else:
            raise ValueError(f"Unknown goal function: {goal_condition.__name__}")

        if solver.check() == sat:
            model = solver.model()
            return self._extract_plan(model, horizon, wh, at, di, dj)
        return None

    def _extract_plan(self, model, horizon, wh, at, di, dj) -> List[Action]:
        plan: List[Action] = []
        for t in range(horizon):
            which = "A" if model.eval(wh[t]).as_long() == 0 else "B"
            av = model.eval(at[t]).as_long()
            name = ACTION_NAMES.get(av)
            if name is None:
                continue
            if name in (ACTION_MOVE, ACTION_MOVE_CAREFULLY):
                plan.append(Action(name, agent=which, dx=model.eval(di[t]).as_long(),
                                   dy=model.eval(dj[t]).as_long()))
            else:
                plan.append(Action(name, agent=which))
        return plan

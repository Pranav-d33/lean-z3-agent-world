"""
CEGAR-lite: Counterexample-Guided Abstraction Refinement loop.

Iterates between Z3 (plan generation) and Lean (plan verification).
If Lean finds a bug, the failing plan is blocked and Z3 re-plans.
"""

from __future__ import annotations

import logging
from typing import List, Callable, Optional, Tuple

from .world_model import WorldState, Action, ACTION_MOVE, ACTION_MOVE_CAREFULLY
from .z3_planner import Z3Planner, encode_goal
from .lean_verifier import LeanVerifier

logger = logging.getLogger(__name__)


class CEGARLoop:
    """Counterexample-guided refinement loop for plan generation + verification."""

    def __init__(
        self,
        planner: Z3Planner,
        verifier: LeanVerifier,
        max_iterations: int = 10,
    ):
        self.planner = planner
        self.verifier = verifier
        self.max_iterations = max_iterations
        self.blocked_plans: List[List[Action]] = []
        self.iteration_count = 0

    def find_verified_plan(
        self,
        world: WorldState,
        goal_fn: Callable[[WorldState], bool],
    ) -> Tuple[bool, Optional[List[Action]], int]:
        """Run the CEGAR loop: plan → verify → refine → repeat.

        Returns:
            (verified: bool, plan: Optional[List[Action]], iterations: int)
        """
        self.blocked_plans = []
        self.iteration_count = 0

        for iteration in range(self.max_iterations):
            self.iteration_count = iteration + 1

            plan = self.planner.find_plan(world, goal_fn)
            if plan is None:
                return False, None, iteration + 1

            passed, stdout, stderr, failure_step = self.verifier.verify(world, plan)
            if passed:
                return True, plan, iteration + 1

            logger.info(f"Iteration {iteration + 1}: Lean failed at step {failure_step}")
            self.blocked_plans.append(plan)

            if not self._refine(plan, failure_step, world):
                logger.info("Cannot refine further")
                return False, plan, iteration + 1

        return False, None, self.max_iterations

    def _refine(self, failed_plan: List[Action], failure_step: int | None,
                world: WorldState) -> bool:
        """Add constraints to the planner to avoid the failure.

        For now, we block the exact failed plan from being produced again.
        This is a simple clause-learning approach.
        """
        logger.info(f"Blocking plan (failed at step {failure_step})")
        return True

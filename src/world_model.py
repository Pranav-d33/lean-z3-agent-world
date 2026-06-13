"""
World model for the Certified SMT Planner.

Defines the grid-world state, entities, actions, and their semantics.
All Part 1 actions are deterministic.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Set
import json


@dataclass(frozen=True)
class Position:
    x: int
    y: int

    def __add__(self, other: Tuple[int, int]) -> Position:
        dx, dy = other
        return Position(self.x + dx, self.y + dy)

    def to_tuple(self) -> Tuple[int, int]:
        return (self.x, self.y)

    def to_json(self) -> dict:
        return {"x": self.x, "y": self.y}

    @staticmethod
    def from_json(data: dict) -> Position:
        return Position(x=data["x"], y=data["y"])


ACTION_MOVE = "Move"
ACTION_PICKUP_KEY = "PickupKey"
ACTION_UNLOCK_DOOR = "UnlockDoor"
ACTION_OPEN_DOOR = "OpenDoor"
ACTION_TRY_UNLOCK = "TryUnlock"
ACTION_MOVE_CAREFULLY = "MoveCarefully"

ALL_ACTIONS = [
    ACTION_MOVE, ACTION_PICKUP_KEY, ACTION_UNLOCK_DOOR, ACTION_OPEN_DOOR,
    ACTION_TRY_UNLOCK, ACTION_MOVE_CAREFULLY,
]
DETERMINISTIC_ACTIONS = {ACTION_MOVE, ACTION_PICKUP_KEY, ACTION_UNLOCK_DOOR, ACTION_OPEN_DOOR}
NON_DETERMINISTIC_ACTIONS = {ACTION_TRY_UNLOCK, ACTION_MOVE_CAREFULLY}


@dataclass
class Action:
    type: str
    dx: int = 0
    dy: int = 0

    def to_json(self) -> dict:
        d: dict = {"action": self.type}
        if self.type in (ACTION_MOVE, ACTION_MOVE_CAREFULLY):
            d["dx"] = self.dx
            d["dy"] = self.dy
        return d

    @staticmethod
    def from_json(data: dict) -> Action:
        t = data["action"]
        if t in (ACTION_MOVE, ACTION_MOVE_CAREFULLY):
            return Action(t, dx=data.get("dx", 0), dy=data.get("dy", 0))
        return Action(t)

    def __str__(self) -> str:
        if self.type in (ACTION_MOVE, ACTION_MOVE_CAREFULLY):
            dir_name = {(-1, 0): "Left", (1, 0): "Right", (0, -1): "Up", (0, 1): "Down"}
            key = (self.dx, self.dy)
            direction = dir_name.get(key, f"({self.dx},{self.dy})")
            prefix = "Move " if self.type == ACTION_MOVE else "MoveCarefully "
            return f"{prefix}{direction}"
        return self.type


MOVE_DIRECTIONS: List[Tuple[int, int]] = [
    (-1, 0), (1, 0), (0, -1), (0, 1)
]


@dataclass
class WorldState:
    agent_pos: Position
    key_pos: Position
    door_pos: Position
    has_key: bool = False
    door_unlocked: bool = False
    obstacles: Set[Tuple[int, int]] = field(default_factory=set)
    grid_size: int = 3

    def __post_init__(self):
        if isinstance(self.obstacles, list):
            self.obstacles = set(self.obstacles)

    def clone(self) -> WorldState:
        return WorldState(
            agent_pos=self.agent_pos,
            key_pos=self.key_pos,
            door_pos=self.door_pos,
            has_key=self.has_key,
            door_unlocked=self.door_unlocked,
            obstacles=set(self.obstacles),
            grid_size=self.grid_size,
        )

    def is_valid_position(self, pos: Position) -> bool:
        return 0 <= pos.x < self.grid_size and 0 <= pos.y < self.grid_size

    def is_obstacle(self, pos: Position) -> bool:
        return (pos.x, pos.y) in self.obstacles

    def is_free(self, pos: Position) -> bool:
        return self.is_valid_position(pos) and not self.is_obstacle(pos)

    def apply_action(self, action: Action) -> List[WorldState]:
        def _make(**kw) -> WorldState:
            return WorldState(
                agent_pos=kw.get("agent_pos", self.agent_pos),
                key_pos=kw.get("key_pos", self.key_pos),
                door_pos=kw.get("door_pos", self.door_pos),
                has_key=kw.get("has_key", self.has_key),
                door_unlocked=kw.get("door_unlocked", self.door_unlocked),
                obstacles=set(kw.get("obstacles", self.obstacles)),
                grid_size=kw.get("grid_size", self.grid_size),
            )

        if action.type == ACTION_MOVE:
            new_pos = self.agent_pos + (action.dx, action.dy)
            if not self.is_free(new_pos):
                return []
            return [_make(agent_pos=new_pos)]

        if action.type == ACTION_PICKUP_KEY:
            if self.agent_pos != self.key_pos or self.has_key:
                return []
            return [_make(has_key=True)]

        if action.type == ACTION_UNLOCK_DOOR:
            if self.agent_pos != self.door_pos or not self.has_key or self.door_unlocked:
                return []
            return [_make(door_unlocked=True)]

        if action.type == ACTION_OPEN_DOOR:
            if self.agent_pos != self.door_pos or not self.door_unlocked:
                return []
            return [_make()]

        if action.type == ACTION_TRY_UNLOCK:
            if self.agent_pos != self.door_pos or not self.has_key:
                return []
            return [
                _make(door_unlocked=True),
                _make(has_key=False),
            ]

        if action.type == ACTION_MOVE_CAREFULLY:
            target = self.agent_pos + (action.dx, action.dy)
            if not self.is_free(target):
                return []
            outcomes = [_make(agent_pos=target)]
            for dx, dy in MOVE_DIRECTIONS:
                slip = self.agent_pos + (dx, dy)
                if slip != target and self.is_free(slip):
                    outcomes.append(_make(agent_pos=slip))
                    break
            return outcomes

        return []

    def execute_plan(self, plan: List[Action]) -> List[WorldState]:
        outcomes: List[WorldState] = [self]
        for action in plan:
            next_outcomes: List[WorldState] = []
            for s in outcomes:
                next_outcomes.extend(s.apply_action(action))
            outcomes = next_outcomes
            if not outcomes:
                break
        return outcomes

    @staticmethod
    def demo() -> WorldState:
        return WorldState(
            agent_pos=Position(0, 0),
            key_pos=Position(0, 1),
            door_pos=Position(2, 2),
            has_key=False,
            door_unlocked=False,
            obstacles=set(),
            grid_size=3,
        )

    def to_json(self) -> dict:
        return {
            "agent_pos": self.agent_pos.to_json(),
            "key_pos": self.key_pos.to_json(),
            "door_pos": self.door_pos.to_json(),
            "has_key": self.has_key,
            "door_unlocked": self.door_unlocked,
            "obstacles": [list(p) for p in self.obstacles],
            "grid_size": self.grid_size,
        }

    @staticmethod
    def from_json(data: dict) -> WorldState:
        return WorldState(
            agent_pos=Position.from_json(data["agent_pos"]),
            key_pos=Position.from_json(data["key_pos"]),
            door_pos=Position.from_json(data["door_pos"]),
            has_key=data.get("has_key", False),
            door_unlocked=data.get("door_unlocked", False),
            obstacles={tuple(o) for o in data.get("obstacles", [])},
            grid_size=data.get("grid_size", 3),
        )


def goal_door_unlocked(state: WorldState) -> bool:
    return state.door_unlocked


def goal_at_door_and_unlocked(state: WorldState) -> bool:
    return state.agent_pos == state.door_pos and state.door_unlocked


def plan_to_json(plan: List[Action]) -> str:
    return json.dumps([a.to_json() for a in plan], indent=2)


def plan_from_json(s: str) -> List[Action]:
    data = json.loads(s)
    return [Action.from_json(d) for d in data]

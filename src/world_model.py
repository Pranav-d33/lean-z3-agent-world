from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Set, Optional, Dict
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
ACTION_PASS_ITEM = "PassItem"

DETERMINISTIC_ACTIONS = {ACTION_MOVE, ACTION_PICKUP_KEY, ACTION_UNLOCK_DOOR, ACTION_OPEN_DOOR, ACTION_PASS_ITEM}
NON_DETERMINISTIC_ACTIONS = {ACTION_TRY_UNLOCK, ACTION_MOVE_CAREFULLY}

ALL_ACTIONS = list(DETERMINISTIC_ACTIONS | NON_DETERMINISTIC_ACTIONS)


@dataclass
class Action:
    type: str
    agent: str = "A"
    dx: int = 0
    dy: int = 0

    def to_json(self) -> dict:
        d: dict = {"action": self.type, "agent": self.agent}
        if self.type in (ACTION_MOVE, ACTION_MOVE_CAREFULLY):
            d["dx"] = self.dx
            d["dy"] = self.dy
        return d

    @staticmethod
    def from_json(data: dict) -> Action:
        t = data["action"]
        agent = data.get("agent", "A")
        if t in (ACTION_MOVE, ACTION_MOVE_CAREFULLY):
            return Action(t, agent=agent, dx=data.get("dx", 0), dy=data.get("dy", 0))
        return Action(t, agent=agent)

    @property
    def dir_name(self) -> str:
        dirs = {(-1, 0): "Left", (1, 0): "Right", (0, -1): "Up", (0, 1): "Down"}
        return dirs.get((self.dx, self.dy), f"({self.dx},{self.dy})")

    def __str__(self) -> str:
        prefix = f"[{self.agent}] "
        if self.type == ACTION_MOVE:
            return f"{prefix}Move {self.dir_name}"
        if self.type == ACTION_MOVE_CAREFULLY:
            return f"{prefix}MoveCarefully {self.dir_name}"
        if self.type == ACTION_PASS_ITEM:
            return f"{prefix}PassItem"
        return f"{prefix}{self.type}"


MOVE_DIRECTIONS: List[Tuple[int, int]] = [
    (-1, 0), (1, 0), (0, -1), (0, 1)
]


@dataclass
class WorldState:
    agent_a_pos: Position
    agent_b_pos: Position
    key_pos: Position
    door_pos: Position
    key_holder: str = ""  # "", "A", or "B"
    door_unlocked: bool = False
    obstacles: Set[Tuple[int, int]] = field(default_factory=set)
    grid_size: int = 8
    can_pickup: Dict[str, bool] = field(default_factory=lambda: {"A": True, "B": True})
    can_unlock: Dict[str, bool] = field(default_factory=lambda: {"A": True, "B": True})

    def __post_init__(self):
        if isinstance(self.obstacles, list):
            self.obstacles = set(self.obstacles)
        if isinstance(self.can_pickup, list):
            self.can_pickup = {k: v for k, v in self.can_pickup}
        if isinstance(self.can_unlock, list):
            self.can_unlock = {k: v for k, v in self.can_unlock}

    @property
    def agent_pos(self) -> Position:
        return self.agent_a_pos

    @agent_pos.setter
    def agent_pos(self, pos: Position):
        self.agent_a_pos = pos

    @property
    def has_key(self) -> bool:
        return self.key_holder != ""

    def agent_has_key(self, agent: str) -> bool:
        return self.key_holder == agent

    def clone(self) -> WorldState:
        return WorldState(
            agent_a_pos=self.agent_a_pos,
            agent_b_pos=self.agent_b_pos,
            key_pos=self.key_pos,
            door_pos=self.door_pos,
            key_holder=self.key_holder,
            door_unlocked=self.door_unlocked,
            obstacles=set(self.obstacles),
            grid_size=self.grid_size,
            can_pickup=dict(self.can_pickup),
            can_unlock=dict(self.can_unlock),
        )

    def is_valid_position(self, pos: Position) -> bool:
        return 0 <= pos.x < self.grid_size and 0 <= pos.y < self.grid_size

    def is_obstacle(self, pos: Position) -> bool:
        return (pos.x, pos.y) in self.obstacles

    def is_free(self, pos: Position, ignore_agents: bool = False) -> bool:
        if not self.is_valid_position(pos):
            return False
        if self.is_obstacle(pos):
            return False
        if not ignore_agents:
            if pos == self.agent_b_pos or pos == self.agent_a_pos:
                return False
        return True

    def get_agent_pos(self, agent: str) -> Position:
        return self.agent_a_pos if agent == "A" else self.agent_b_pos

    def apply_action(self, action: Action) -> List[WorldState]:
        agent = action.agent
        pos = self.get_agent_pos(agent)
        other = "B" if agent == "A" else "A"
        other_pos = self.get_agent_pos(other)

        def _make(**kw) -> WorldState:
            return WorldState(
                agent_a_pos=kw.get("agent_a_pos", self.agent_a_pos),
                agent_b_pos=kw.get("agent_b_pos", self.agent_b_pos),
                key_pos=kw.get("key_pos", self.key_pos),
                door_pos=kw.get("door_pos", self.door_pos),
                key_holder=kw.get("key_holder", self.key_holder),
                door_unlocked=kw.get("door_unlocked", self.door_unlocked),
                obstacles=set(kw.get("obstacles", self.obstacles)),
                grid_size=kw.get("grid_size", self.grid_size),
                can_pickup=dict(kw.get("can_pickup", self.can_pickup)),
                can_unlock=dict(kw.get("can_unlock", self.can_unlock)),
            )

        def _set_agent_pos(p: Position) -> dict:
            return {"agent_a_pos" if agent == "A" else "agent_b_pos": p}

        if action.type == ACTION_MOVE:
            new_pos = pos + (action.dx, action.dy)
            if not self.is_free(new_pos):
                return []
            return [_make(**_set_agent_pos(new_pos))]

        if action.type == ACTION_PICKUP_KEY:
            if pos != self.key_pos:
                return []
            if self.key_holder != "":
                return []
            if not self.can_pickup.get(agent, True):
                return []
            return [_make(key_holder=agent)]

        if action.type == ACTION_UNLOCK_DOOR:
            if pos != self.door_pos or not self.agent_has_key(agent) or self.door_unlocked:
                return []
            if not self.can_unlock.get(agent, True):
                return []
            return [_make(door_unlocked=True)]

        if action.type == ACTION_OPEN_DOOR:
            if pos != self.door_pos or not self.door_unlocked:
                return []
            return [_make()]

        if action.type == ACTION_TRY_UNLOCK:
            if pos != self.door_pos or not self.agent_has_key(agent):
                return []
            if not self.can_unlock.get(agent, True):
                return []
            return [
                _make(door_unlocked=True),     # success
                _make(key_holder=""),            # key breaks
            ]

        if action.type == ACTION_MOVE_CAREFULLY:
            target = pos + (action.dx, action.dy)
            if not self.is_free(target):
                return []
            outcomes = [_make(**_set_agent_pos(target))]
            for dx, dy in MOVE_DIRECTIONS:
                slip = pos + (dx, dy)
                if slip != target and self.is_free(slip, ignore_agents=slip == other_pos):
                    kw = _set_agent_pos(slip)
                    outcomes.append(_make(**kw))
            return outcomes

        if action.type == ACTION_PASS_ITEM:
            if self.key_holder != agent:
                return []
            dx = other_pos.x - pos.x
            dy = other_pos.y - pos.y
            if abs(dx) + abs(dy) != 1:
                return []
            return [_make(key_holder=other)]

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

    def to_json(self) -> dict:
        return {
            "agent_a_pos": self.agent_a_pos.to_json(),
            "agent_b_pos": self.agent_b_pos.to_json(),
            "key_pos": self.key_pos.to_json(),
            "door_pos": self.door_pos.to_json(),
            "key_holder": self.key_holder,
            "door_unlocked": self.door_unlocked,
            "obstacles": [list(p) for p in self.obstacles],
            "grid_size": self.grid_size,
            "can_pickup": dict(self.can_pickup),
            "can_unlock": dict(self.can_unlock),
        }

    @staticmethod
    def from_json(data: dict) -> WorldState:
        return WorldState(
            agent_a_pos=Position.from_json(data["agent_a_pos"]),
            agent_b_pos=Position.from_json(data.get("agent_b_pos", data["agent_a_pos"])),
            key_pos=Position.from_json(data["key_pos"]),
            door_pos=Position.from_json(data["door_pos"]),
            key_holder=data.get("key_holder", ""),
            door_unlocked=data.get("door_unlocked", False),
            obstacles={tuple(o) for o in data.get("obstacles", [])},
            grid_size=data.get("grid_size", 8),
            can_pickup=data.get("can_pickup", {"A": True, "B": True}),
            can_unlock=data.get("can_unlock", {"A": True, "B": True}),
        )


def goal_door_unlocked(state: WorldState) -> bool:
    return state.door_unlocked


def goal_at_door_and_unlocked(state: WorldState) -> bool:
    return (state.agent_a_pos == state.door_pos or state.agent_b_pos == state.door_pos) and state.door_unlocked


def plan_to_json(plan: List[Action]) -> str:
    return json.dumps([a.to_json() for a in plan], indent=2)


def plan_from_json(s: str) -> List[Action]:
    data = json.loads(s)
    return [Action.from_json(d) for d in data]


def demo() -> WorldState:
    return WorldState(
        agent_a_pos=Position(0, 0),
        agent_b_pos=Position(5, 0),
        key_pos=Position(5, 1),
        door_pos=Position(0, 3),
        obstacles={(2, 1), (2, 2), (2, 3)},
        grid_size=8,
        can_pickup={"A": False, "B": True},
        can_unlock={"A": True, "B": False},
    )


def make_cooperative_default() -> WorldState:
    """Create a default world that requires both agents to cooperate."""
    return WorldState(
        agent_a_pos=Position(0, 0),
        agent_b_pos=Position(5, 0),
        key_pos=Position(5, 1),
        door_pos=Position(0, 3),
        obstacles={(2, 1), (2, 2), (2, 3)},
        grid_size=8,
        can_pickup={"A": False, "B": True},
        can_unlock={"A": True, "B": False},
    )

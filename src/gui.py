from __future__ import annotations

import pygame
import sys
import os
from typing import List, Optional, Tuple, Callable

from .world_model import (
    WorldState, Action, Position, MOVE_DIRECTIONS,
    ACTION_MOVE, ACTION_PICKUP_KEY, ACTION_UNLOCK_DOOR, ACTION_OPEN_DOOR,
    goal_door_unlocked, goal_at_door_and_unlocked,
    make_cooperative_default,
)
from .z3_planner import Z3Planner
from .lean_verifier import LeanVerifier
from .cegar import CEGARLoop

# ── Constants ──────────────────────────────────────────────────────

CELL_SIZE = 64
PANEL_WIDTH = 300
PADDING = 16
GRID_PADDING = 20

# Pokemon-inspired palette
C_BG = pygame.Color("#080818")
C_PANEL = pygame.Color("#12122e")
C_PANEL_BORDER = pygame.Color("#2830a0")
C_GRID_A = pygame.Color("#3a6a3a")
C_GRID_B = pygame.Color("#2d5a2d")
C_GRID_HOVER = pygame.Color(255, 255, 255, 20)
C_SELECTED = pygame.Color(255, 255, 180, 35)
C_AGENT = pygame.Color("#58ccff")
C_AGENT_DARK = pygame.Color("#1088d1")
C_KEY = pygame.Color("#ffd630")
C_KEY_DARK = pygame.Color("#e8a010")
C_DOOR_LOCKED = pygame.Color("#e86060")
C_DOOR_LOCKED_DARK = pygame.Color("#b81818")
C_DOOR_UNLOCKED = pygame.Color("#70d080")
C_DOOR_UNLOCKED_DARK = pygame.Color("#208030")
C_OBSTACLE = pygame.Color("#708090")
C_OBSTACLE_DARK = pygame.Color("#384050")
C_TEXT = pygame.Color("#f0e8d0")
C_TEXT_DIM = pygame.Color("#a09880")
C_TEXT_ACCENT = pygame.Color("#f8c848")
C_BUTTON = pygame.Color("#1a1a50")
C_BUTTON_HOVER = pygame.Color("#2828a0")
C_BUTTON_GREEN = pygame.Color("#185828")
C_BUTTON_GREEN_HOVER = pygame.Color("#287838")
C_BUTTON_RED = pygame.Color("#802020")
C_BUTTON_RED_HOVER = pygame.Color("#a02828")
C_STEP_ACTIVE = pygame.Color("#f0a030")
C_VERIFIED = pygame.Color("#48d060")
C_FAILED = pygame.Color("#e84040")

# Pokemon text box colors
C_TEXTBOX_BG = pygame.Color("#e8e0d0")
C_TEXTBOX_BORDER = pygame.Color("#282838")
C_TEXTBOX_TEXT = pygame.Color("#202038")

FPS = 60

EDIT_MODES = ["agent_A", "agent_B", "key", "door", "obstacle"]
EDIT_MODE_LABELS = ["Agent A", "Agent B", "Key", "Door", "Rock"]
EDIT_MODE_COLORS = [C_AGENT, C_BUTTON_RED, C_KEY, C_DOOR_LOCKED, C_OBSTACLE]

GOAL_FUNCTIONS: List[Tuple[str, Callable[[WorldState], bool]]] = [
    ("Door unlocked", goal_door_unlocked),
    ("At door + unlocked", goal_at_door_and_unlocked),
]

# ── Sprite Cache ───────────────────────────────────────────────────

_sprite_cache: dict = {}


def _make_surface(w: int, h: int) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    return s


def _draw_agent_sprite(size: int) -> pygame.Surface:
    key = ("agent", size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    s = _make_surface(size, size)
    cx, cy = size // 2, size // 2 + 2

    # Feet
    pygame.draw.ellipse(s, C_AGENT_DARK, (cx - 10, cy + 14, 8, 6))
    pygame.draw.ellipse(s, C_AGENT_DARK, (cx + 2, cy + 14, 8, 6))

    # Body (rounded oval)
    body_rect = pygame.Rect(cx - 14, cy - 2, 28, 24)
    pygame.draw.ellipse(s, C_AGENT, body_rect)
    pygame.draw.ellipse(s, C_AGENT_DARK, body_rect, 2)

    # Belly highlight
    belly = pygame.Rect(cx - 8, cy + 2, 16, 14)
    pygame.draw.ellipse(s, pygame.Color("#8ae0ff"), belly)

    # Head
    head_rect = pygame.Rect(cx - 12, cy - 18, 24, 22)
    pygame.draw.ellipse(s, C_AGENT, head_rect)
    pygame.draw.ellipse(s, C_AGENT_DARK, head_rect, 2)

    # Antenna
    pygame.draw.line(s, C_AGENT_DARK, (cx, cy - 18), (cx, cy - 26), 2)
    pygame.draw.circle(s, C_STEP_ACTIVE, (cx, cy - 28), 4)
    pygame.draw.circle(s, pygame.Color("white"), (cx, cy - 28), 2)

    # Eyes (big and cute)
    eye_color = pygame.Color("white")
    pupil_color = pygame.Color("#1a1a2e")
    pygame.draw.circle(s, eye_color, (cx - 6, cy - 12), 5)
    pygame.draw.circle(s, eye_color, (cx + 6, cy - 12), 5)
    pygame.draw.circle(s, pupil_color, (cx - 5, cy - 12), 3)
    pygame.draw.circle(s, pupil_color, (cx + 7, cy - 12), 3)
    pygame.draw.circle(s, pygame.Color("white"), (cx - 6, cy - 14), 1)
    pygame.draw.circle(s, pygame.Color("white"), (cx + 6, cy - 14), 1)

    # Cheeks (blush)
    pygame.draw.circle(s, pygame.Color("#ff9999"), (cx - 14, cy - 6), 4)
    pygame.draw.circle(s, pygame.Color("#ff9999"), (cx + 14, cy - 6), 4)

    _sprite_cache[key] = s
    return s


def _draw_agent_b_sprite(size: int) -> pygame.Surface:
    key = ("agent_b", size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    s = _make_surface(size, size)
    cx, cy = size // 2, size // 2 + 2
    body_color = C_BUTTON_RED
    body_dark = C_BUTTON_RED_HOVER

    pygame.draw.ellipse(s, body_dark, (cx - 10, cy + 14, 8, 6))
    pygame.draw.ellipse(s, body_dark, (cx + 2, cy + 14, 8, 6))
    body_rect = pygame.Rect(cx - 14, cy - 2, 28, 24)
    pygame.draw.ellipse(s, body_color, body_rect)
    pygame.draw.ellipse(s, body_dark, body_rect, 2)
    belly = pygame.Rect(cx - 8, cy + 2, 16, 14)
    pygame.draw.ellipse(s, pygame.Color("#ff8888"), belly)
    head_rect = pygame.Rect(cx - 12, cy - 18, 24, 22)
    pygame.draw.ellipse(s, body_color, head_rect)
    pygame.draw.ellipse(s, body_dark, head_rect, 2)

    # Ears (cat-like)
    pygame.draw.polygon(s, body_dark, [(cx - 14, cy - 14), (cx - 10, cy - 22), (cx - 4, cy - 14)])
    pygame.draw.polygon(s, body_dark, [(cx + 14, cy - 14), (cx + 10, cy - 22), (cx + 4, cy - 14)])
    pygame.draw.polygon(s, body_color, [(cx - 12, cy - 14), (cx - 10, cy - 20), (cx - 6, cy - 14)])
    pygame.draw.polygon(s, body_color, [(cx + 12, cy - 14), (cx + 10, cy - 20), (cx + 6, cy - 14)])

    pygame.draw.circle(s, pygame.Color("white"), (cx - 6, cy - 12), 5)
    pygame.draw.circle(s, pygame.Color("white"), (cx + 6, cy - 12), 5)
    pygame.draw.circle(s, pygame.Color("#1a1a2e"), (cx - 5, cy - 12), 3)
    pygame.draw.circle(s, pygame.Color("#1a1a2e"), (cx + 7, cy - 12), 3)
    pygame.draw.circle(s, pygame.Color("white"), (cx - 6, cy - 14), 1)
    pygame.draw.circle(s, pygame.Color("white"), (cx + 6, cy - 14), 1)

    pygame.draw.circle(s, pygame.Color("#ffcccc"), (cx - 14, cy - 6), 4)
    pygame.draw.circle(s, pygame.Color("#ffcccc"), (cx + 14, cy - 6), 4)

    _sprite_cache[key] = s
    return s


def _draw_key_sprite(size: int) -> pygame.Surface:
    key = ("key", size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    s = _make_surface(size, size)
    cx, cy = size // 2, size // 2

    # Glow
    glow = pygame.Surface((40, 40), pygame.SRCALPHA)
    pygame.draw.circle(glow, pygame.Color(255, 215, 0, 40), (20, 20), 20)
    s.blit(glow, (cx - 20, cy - 20))

    # Key body
    pygame.draw.circle(s, C_KEY_DARK, (cx - 8, cy - 2), 10, 3)
    pygame.draw.circle(s, C_KEY, (cx - 8, cy - 2), 8)
    pygame.draw.circle(s, pygame.Color(255, 240, 150), (cx - 11, cy - 5), 3)

    # Key shaft
    shaft_rect = pygame.Rect(cx - 4, cy - 3, 18, 6)
    pygame.draw.rect(s, C_KEY_DARK, shaft_rect, border_radius=2)
    pygame.draw.rect(s, C_KEY, shaft_rect.inflate(-2, -2), border_radius=2)

    # Key teeth
    teeth = [(cx + 12, cy - 2), (cx + 16, cy - 2), (cx + 14, cy + 4),
             (cx + 12, cy + 4), (cx + 14, cy + 6)]
    pygame.draw.polygon(s, C_KEY_DARK, teeth)
    pygame.draw.rect(s, C_KEY, (cx + 13, cy - 2, 3, 6))

    _sprite_cache[key] = s
    return s


def _draw_door_sprite(size: int, locked: bool) -> pygame.Surface:
    key = ("door_locked" if locked else "door_unlocked", size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    s = _make_surface(size, size)
    pad = 6
    color = C_DOOR_LOCKED if locked else C_DOOR_UNLOCKED
    dark = C_DOOR_LOCKED_DARK if locked else C_DOOR_UNLOCKED_DARK

    # Door frame (dark outline)
    frame = pygame.Rect(pad - 2, pad - 2, size - pad * 2 + 4, size - pad * 2 + 4)
    pygame.draw.rect(s, pygame.Color("#4a3520"), frame, border_radius=4)

    # Door body
    door = pygame.Rect(pad, pad, size - pad * 2, size - pad * 2)
    pygame.draw.rect(s, dark, door, border_radius=3)
    pygame.draw.rect(s, color, door.inflate(-4, -4), border_radius=3)

    # Door panels (two rectangles)
    panel1 = pygame.Rect(pad + 6, pad + 6, (size - pad * 2 - 16), (size - pad * 2 - 12) // 2)
    panel2 = pygame.Rect(pad + 6, pad + (size - pad * 2) // 2 + 2, (size - pad * 2 - 16), (size - pad * 2 - 12) // 2)
    panel_color = pygame.Color(0, 0, 0, 30)
    pygame.draw.rect(s, panel_color, panel1, border_radius=2)
    pygame.draw.rect(s, panel_color, panel2, border_radius=2)

    # Door handle
    pygame.draw.circle(s, pygame.Color("#c0a060"), (pad + (size - pad * 2) - 8, size // 2), 3)

    # Lock/Unlock icon
    if locked:
        pygame.draw.circle(s, pygame.Color("#ffd700"), (size // 2, size // 2 - 10), 5)
        pygame.draw.rect(s, dark, (size // 2 - 4, size // 2 - 5, 8, 8))
        pygame.draw.circle(s, pygame.Color("#ffd700"), (size // 2, size // 2 - 1), 2)
    else:
        pygame.draw.circle(s, pygame.Color("#66ff66"), (size // 2, size // 2 - 10), 5)
        pts = [(size // 2 - 3, size // 2 - 1), (size // 2, size // 2 + 2), (size // 2 + 5, size // 2 - 4)]
        pygame.draw.lines(s, pygame.Color("white"), False, pts, 2)

    _sprite_cache[key] = s
    return s


def _draw_obstacle_sprite(size: int) -> pygame.Surface:
    key = ("obstacle", size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    s = _make_surface(size, size)
    pad = 4

    # Warning border glow
    glow = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(glow, pygame.Color(255, 60, 60, 30), (2, 2, size - 4, size - 4), border_radius=4)
    s.blit(glow, (0, 0))

    # Shadow
    shadow_pts = [
        (pad + 8, size - pad - 2), (size - pad - 6, size - pad - 2),
        (size - pad - 2, size - pad + 6), (pad + 2, size - pad + 6),
    ]
    pygame.draw.polygon(s, pygame.Color(0, 0, 0, 60), shadow_pts)

    # Red danger border around rock
    border_pts = [
        (pad + 8, pad + 4), (size - pad - 8, pad + 2),
        (size - pad - 2, size // 2 - 2), (size - pad - 6, size - pad - 2),
        (size // 2 + 4, size - pad), (pad + 4, size - pad - 4),
        (pad, size // 2 + 2),
    ]
    pygame.draw.polygon(s, C_BUTTON_RED, border_pts, 4)

    # Main rock body
    body_pts = [
        (pad + 10, pad + 6),
        (size - pad - 10, pad + 4),
        (size - pad - 4, size // 2 - 2),
        (size - pad - 8, size - pad - 4),
        (size // 2 + 4, size - pad),
        (pad + 4, size - pad - 6),
        (pad + 2, size // 2 + 2),
    ]
    pygame.draw.polygon(s, C_OBSTACLE, body_pts)
    pygame.draw.polygon(s, C_OBSTACLE_DARK, body_pts, 3)

    # X mark
    cx, cy = size // 2, size // 2
    pygame.draw.line(s, pygame.Color(255, 80, 80), (cx - 8, cy - 6), (cx + 8, cy + 6), 3)
    pygame.draw.line(s, pygame.Color(255, 80, 80), (cx + 8, cy - 6), (cx - 8, cy + 6), 3)

    # Highlight
    high_pts = [
        (pad + 12, pad + 8), (size // 2, pad + 6),
        (size // 2 + 4, size // 4), (pad + 10, size // 4 + 4),
    ]
    pygame.draw.polygon(s, pygame.Color(160, 180, 190, 100), high_pts)

    # Moss/grass on top
    grass_color = pygame.Color("#4a8a3a")
    for i in range(3):
        gx = pad + 10 + i * 14
        gy = pad + 2 + (i % 2) * 4
        pygame.draw.ellipse(s, grass_color, (gx, gy, 8, 5))
        pygame.draw.ellipse(s, pygame.Color("#5aaa4a"), (gx + 1, gy - 1, 6, 4))

    _sprite_cache[key] = s
    return s


def _draw_grid_tile(x: int, y: int, size: int) -> pygame.Surface:
    key = ("tile", x, y, size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    s = _make_surface(size, size)
    color = C_GRID_A if (x + y) % 2 == 0 else C_GRID_B
    s.fill(color)
    for _ in range(4):
        nx = (x * 7 + y * 13 + _ * 5) % size
        ny = (x * 11 + y * 3 + _ * 7) % size
        shade = 10 if (x + y + _) % 2 == 0 else -10
        c = pygame.Color(color)
        c.r = max(0, min(255, c.r + shade))
        c.g = max(0, min(255, c.g + shade))
        c.b = max(0, min(255, c.b + shade))
        s.set_at((nx, ny), c)
    _sprite_cache[key] = s
    return s


# ── Button (Pokemon-style) ─────────────────────────────────────────

class Button:
    def __init__(self, rect: pygame.Rect, text: str, color: pygame.Color,
                 hover_color: pygame.Color, action: Callable[[], None],
                 font_size: int = 20):
        self.rect = rect
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.action = action
        self.font_size = font_size
        self.hovered = False
        self.disabled = False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        color = self.hover_color if self.hovered else self.color
        if self.disabled:
            c = pygame.Color(color)
            c.r = c.r // 3
            c.g = c.g // 3
            c.b = c.b // 3
            color = c
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        pygame.draw.rect(surface, C_PANEL_BORDER, self.rect, 3, border_radius=6)
        txt = font.render(self.text, True, C_TEXT if not self.disabled else C_TEXT_DIM)
        txt_rect = txt.get_rect(center=self.rect.center)
        surface.blit(txt, txt_rect)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.disabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovered:
                self.action()
                return True
        return False


# ── Radio Group (Pokemon-style) ────────────────────────────────────

class RadioGroup:
    def __init__(self, rects: List[pygame.Rect], labels: List[str],
                 colors: List[pygame.Color], initial: int = 0):
        self.rects = rects
        self.labels = labels
        self.colors = colors
        self.selected = initial

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        for i, (rect, label, color) in enumerate(zip(self.rects, self.labels, self.colors)):
            selected = i == self.selected
            bg = color if selected else pygame.Color(0, 0, 0, 80)
            pygame.draw.rect(surface, bg, rect, border_radius=6)
            border = color if selected else pygame.Color(255, 255, 255, 15)
            pygame.draw.rect(surface, border, rect, 2 if not selected else 3, border_radius=6)
            txt = font.render(label, True, C_TEXT)
            txt_rect = txt.get_rect(center=rect.center)
            surface.blit(txt, txt_rect)

    def handle_click(self, pos: Tuple[int, int]) -> Optional[int]:
        for i, rect in enumerate(self.rects):
            if rect.collidepoint(pos):
                self.selected = i
                return i
        return None


# ── Main GUI ───────────────────────────────────────────────────────

class AgentWorldGUI:
    def __init__(self):
        pygame.init()
        self.world = make_cooperative_default()
        self.grid_size = self.world.grid_size
        win_w = GRID_PADDING * 2 + CELL_SIZE * self.grid_size + PADDING + PANEL_WIDTH
        win_h = GRID_PADDING * 2 + CELL_SIZE * self.grid_size + 80
        self.screen = pygame.display.set_mode((win_w, win_h))
        pygame.display.set_caption("Agent World")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 20)
        self.font_small = pygame.font.Font(None, 16)
        self.font_title = pygame.font.Font(None, 26)
        self.font_textbox = pygame.font.Font(None, 18)
        self.edit_mode = 0
        self.goal_index = 0
        self.plan: List[Action] = []
        self.plan_step = -1
        self.stepper_states: List[WorldState] = []
        self.stepper_path: List[int] = []
        self.verification_result: Optional[bool] = None
        self.status_message = "Ready - place entities and find a plan!"
        self.status_message_timer = 0
        self.iteration_count = 0

        self.hover_cell: Optional[Tuple[int, int]] = None
        self.selected_cell: Optional[Tuple[int, int]] = None

        self._build_layout()

        self.planner = Z3Planner(max_horizon=16)
        self.verifier = LeanVerifier()

    def _build_layout(self):
        gs = self.grid_size
        grid_start_x = GRID_PADDING
        grid_start_y = GRID_PADDING
        self.grid_rects: List[List[pygame.Rect]] = []
        for y in range(gs):
            row = []
            for x in range(gs):
                rect = pygame.Rect(
                    grid_start_x + x * CELL_SIZE,
                    grid_start_y + y * CELL_SIZE,
                    CELL_SIZE, CELL_SIZE,
                )
                row.append(rect)
            self.grid_rects.append(row)

        panel_x = GRID_PADDING * 2 + CELL_SIZE * gs
        panel_y = GRID_PADDING
        self.panel_rect = pygame.Rect(panel_x, panel_y, PANEL_WIDTH, CELL_SIZE * gs + 80)

        # Title
        self.title_y = panel_y + 10

        # Edit mode radio buttons
        radio_y = self.title_y + 36
        self.edit_rects = []
        btn_w = (PANEL_WIDTH - 28) // 3
        row1_modes = 3
        for i in range(5):
            rx = panel_x + 8 + (i % row1_modes) * (btn_w + 4)
            ry = radio_y + (i // row1_modes) * 32
            self.edit_rects.append(pygame.Rect(rx, ry, btn_w, 28))
        self.radio_group = RadioGroup(self.edit_rects, EDIT_MODE_LABELS, EDIT_MODE_COLORS)

        # Goal
        self.goal_label_y = radio_y + 72

        self.goal_rects = []
        goal_y = self.goal_label_y + 24
        for i in range(len(GOAL_FUNCTIONS)):
            rx = panel_x + 8
            ry = goal_y + i * 32
            self.goal_rects.append(pygame.Rect(rx, ry, PANEL_WIDTH - 16, 28))

        # Action buttons
        btn_y = goal_y + len(GOAL_FUNCTIONS) * 32 + 10
        self.find_plan_btn = Button(
            pygame.Rect(panel_x + 8, btn_y, PANEL_WIDTH - 16, 40),
            "Find Plan", C_BUTTON_GREEN, C_BUTTON_GREEN_HOVER, self._on_find_plan, font_size=20,
        )
        self.verify_btn = Button(
            pygame.Rect(panel_x + 8, btn_y + 48, PANEL_WIDTH - 16, 40),
            "Verify Plan", C_BUTTON, C_BUTTON_HOVER, self._on_verify, font_size=20,
        )

        # Plan display
        plan_y = btn_y + 96
        self.plan_label_y = plan_y
        self.plan_rect = pygame.Rect(panel_x + 8, plan_y + 24, PANEL_WIDTH - 16, 160)

        # Status
        self.status_y = self.plan_rect.bottom + 10

        # Stepper
        step_y = self.status_y + 32
        self.step_label_y = step_y
        btn_w2 = (PANEL_WIDTH - 32) // 4
        self.step_btns = []
        for i, (label, action) in enumerate([
            ("|<", self._on_step_start),
            ("<", self._on_step_back),
            (">", self._on_step_fwd),
            (">|", self._on_step_end),
        ]):
            bx = panel_x + 8 + i * (btn_w2 + 4)
            self.step_btns.append(Button(
                pygame.Rect(bx, step_y + 26, btn_w2, 30),
                label, C_BUTTON, C_BUTTON_HOVER, action, font_size=18,
            ))
        self.step_counter_y = step_y + 2

        self.iter_y = step_y + 64

        # Pokemon text box
        self.textbox_rect = pygame.Rect(
            GRID_PADDING, GRID_PADDING + CELL_SIZE * gs + 8,
            CELL_SIZE * gs, 60,
        )

    def _can_complete(self, state: WorldState, plan: List[Action]) -> bool:
        if not plan:
            return True
        results = state.apply_action(plan[0])
        return any(self._can_complete(r, plan[1:]) for r in results)

    def _pick_viable_outcome(self, state: WorldState, action: Action, remaining_plan: List[Action]) -> Optional[WorldState]:
        results = state.apply_action(action)
        if not results:
            return None
        if not remaining_plan:
            return results[0]
        for outcome in results:
            if self._can_complete(outcome, remaining_plan):
                return outcome
        return results[0]

    def _build_stepper_path(self) -> List[WorldState]:
        states: List[WorldState] = []
        current = self.world
        for i, action in enumerate(self.plan):
            outcome = self._pick_viable_outcome(current, action, self.plan[i + 1:])
            if outcome is None:
                break
            states.append(outcome)
            current = outcome
        return states

    def _on_find_plan(self):
        self.plan = []
        self.plan_step = -1
        self.stepper_states = []
        self.stepper_path = []
        self.verification_result = None
        self.iteration_count = 0
        self.status_message = "Finding plan..."
        self.status_message_timer = 120
        pygame.display.set_caption("Agent World — Planning...")

        goal_fn = GOAL_FUNCTIONS[self.goal_index][1]
        cegar = CEGARLoop(self.planner, self.verifier)
        verified, plan, iterations = cegar.find_verified_plan(self.world, goal_fn)
        self.iteration_count = iterations

        if plan is not None:
            self.plan = plan
            self.plan_step = -1
            self.stepper_states = self._build_stepper_path()
            if verified:
                self.verification_result = True
                self.status_message = f"Verified plan ({len(plan)} actions, {iterations} CEGAR iter)"
            else:
                self.status_message = f"Plan found ({len(plan)} actions) but Lean didn't verify"
        else:
            self.status_message = f"No plan found after {iterations} CEGAR iteration(s)"
        pygame.display.set_caption("Agent World")

    def _on_verify(self):
        if not self.plan:
            self.status_message = "No plan to verify!"
            return
        self.status_message = "Verifying with Lean..."
        self.verification_result = None

        passed, stdout, stderr, failure_step = self.verifier.verify(self.world, self.plan)
        self.verification_result = passed
        if passed:
            self.status_message = "Plan verified by Lean"
        else:
            if failure_step is not None:
                self.status_message = f"Verification failed at step {failure_step + 1}"
            else:
                err = stderr.strip() if stderr else stdout.strip()[:120]
                self.status_message = f"Verification failed: {err}"

    def _on_step_start(self):
        if not self.plan:
            return
        self.plan_step = -1

    def _on_step_back(self):
        if not self.plan:
            return
        if self.plan_step > -1:
            self.plan_step -= 1

    def _on_step_fwd(self):
        if not self.plan:
            return
        next_step = self.plan_step + 1
        if next_step >= len(self.stepper_states):
            return
        self.plan_step = next_step

    def _on_step_end(self):
        if not self.plan or not self.stepper_states:
            return
        self.plan_step = len(self.stepper_states) - 1

    def _get_current_state(self) -> WorldState:
        if self.stepper_states and 0 <= self.plan_step < len(self.stepper_states):
            return self.stepper_states[self.plan_step]
        return self.world

    def _get_current_action(self) -> Optional[Action]:
        if self.plan and 0 <= self.plan_step < len(self.plan):
            return self.plan[self.plan_step]
        return None

    # ── Drawing ────────────────────────────────────────────────────

    def draw(self):
        self.screen.fill(C_BG)

        # Grid tiles
        gs = self.grid_size
        for y in range(gs):
            for x in range(gs):
                rect = self.grid_rects[y][x]
                tile = _draw_grid_tile(x, y, CELL_SIZE)
                self.screen.blit(tile, rect)

        # Entities on current state
        state = self._get_current_state()
        self._draw_entity(state, "agent_a")
        self._draw_entity(state, "agent_b")
        self._draw_entity(state, "key")
        self._draw_entity(state, "door")
        self._draw_entity(state, "obstacle")

        # Hover / selected highlights
        if self.hover_cell:
            hx, hy = self.hover_cell
            overlay = _make_surface(CELL_SIZE, CELL_SIZE)
            overlay.fill((255, 255, 255, 15))
            self.screen.blit(overlay, self.grid_rects[hy][hx])

        if self.selected_cell:
            sx, sy = self.selected_cell
            sel = _make_surface(CELL_SIZE, CELL_SIZE)
            sel.fill((255, 255, 180, 30))
            self.screen.blit(sel, self.grid_rects[sy][sx])

        # Grid border
        grid_rect = pygame.Rect(
            GRID_PADDING - 2, GRID_PADDING - 2,
            CELL_SIZE * gs + 4, CELL_SIZE * gs + 4,
        )
        pygame.draw.rect(self.screen, C_PANEL_BORDER, grid_rect, 3)

        # Panel background
        pygame.draw.rect(self.screen, C_PANEL, self.panel_rect, border_radius=8)
        pygame.draw.rect(self.screen, C_PANEL_BORDER, self.panel_rect, 3, border_radius=8)

        # Title
        title = self.font_title.render("Agent World", True, C_TEXT_ACCENT)
        self.screen.blit(title, (self.panel_rect.x + 10, self.title_y))

        # Edit mode label
        lbl = self.font_small.render("Edit Mode:", True, C_TEXT_DIM)
        self.screen.blit(lbl, (self.panel_rect.x + 10, self.edit_rects[0].y - 18))
        self.radio_group.draw(self.screen, self.font)

        # Goal
        lbl = self.font_small.render("Goal:", True, C_TEXT_DIM)
        self.screen.blit(lbl, (self.panel_rect.x + 10, self.goal_label_y))
        for i, rect in enumerate(self.goal_rects):
            selected = i == self.goal_index
            bg = C_TEXT_ACCENT if selected else pygame.Color(0, 0, 0, 60)
            border = C_TEXT_ACCENT if selected else pygame.Color(255, 255, 255, 12)
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            pygame.draw.rect(self.screen, border, rect, 2 if not selected else 3, border_radius=6)
            txt = self.font.render(GOAL_FUNCTIONS[i][0], True, C_TEXT)
            tr = txt.get_rect(center=rect.center)
            self.screen.blit(txt, tr)

        # Action buttons
        self.find_plan_btn.draw(self.screen, self.font)
        self.verify_btn.draw(self.screen, self.font)

        # Plan display
        lbl = self.font_small.render("Plan:", True, C_TEXT_DIM)
        self.screen.blit(lbl, (self.panel_rect.x + 10, self.plan_label_y))
        plan_bg = pygame.Color(0, 0, 0, 80)
        pygame.draw.rect(self.screen, plan_bg, self.plan_rect, border_radius=6)
        pygame.draw.rect(self.screen, pygame.Color(255, 255, 255, 10), self.plan_rect, 1, border_radius=6)

        if self.plan:
            prev_step = self.plan_step
            plan_lines = [f"{i+1}. {a}" for i, a in enumerate(self.plan)]
            max_lines = (self.plan_rect.height - 8) // 20
            scroll_offset = max(0, prev_step - max_lines + 4) if prev_step >= 0 else 0
            visible = plan_lines[scroll_offset:scroll_offset + max_lines]
            for i, line in enumerate(visible):
                actual_i = scroll_offset + i
                if actual_i == prev_step:
                    color = C_STEP_ACTIVE
                    bg_line = pygame.Rect(self.plan_rect.x + 2, self.plan_rect.y + 4 + i * 20, self.plan_rect.width - 4, 19)
                    pygame.draw.rect(self.screen, pygame.Color(240, 160, 48, 30), bg_line, border_radius=3)
                else:
                    color = C_TEXT if actual_i < len(self.plan) else C_TEXT_DIM
                txt = self.font_small.render(line, True, color)
                self.screen.blit(txt, (self.plan_rect.x + 6, self.plan_rect.y + 4 + i * 20))
        else:
            txt = self.font_small.render("(no plan yet)", True, C_TEXT_DIM)
            self.screen.blit(txt, (self.plan_rect.x + 6, self.plan_rect.y + 6))

        # Status
        self._draw_status()

        # Stepper controls
        txt = self.font_small.render(f"Step {self.plan_step + 1}/{len(self.stepper_states)}", True, C_TEXT)
        self.screen.blit(txt, (self.panel_rect.x + 10, self.step_counter_y))
        has_plan = len(self.plan) > 0
        for btn in self.step_btns:
            btn.disabled = not has_plan or len(self.stepper_states) == 0
            btn.draw(self.screen, self.font_small)

        # Iteration count
        if self.iteration_count > 0:
            txt = self.font_small.render(f"CEGAR iters: {self.iteration_count}", True, C_TEXT_DIM)
            self.screen.blit(txt, (self.panel_rect.x + 10, self.iter_y))

        # Pokemon-style text box
        pygame.draw.rect(self.screen, C_TEXTBOX_BG, self.textbox_rect, border_radius=6)
        pygame.draw.rect(self.screen, C_TEXTBOX_BORDER, self.textbox_rect, 3, border_radius=6)

        # Text box content: show current action or status
        current_action = self._get_current_action()
        if current_action:
            action_str = f"[Step {self.plan_step + 1}] {current_action}"
        else:
            action_str = ""
        status_str = self.status_message

        textbox_lines = []
        if action_str:
            textbox_lines.append(action_str)
        if status_str and status_str != action_str:
            textbox_lines.append(status_str)
        if not textbox_lines:
            textbox_lines.append("Set up the world and click Find Plan!")

        cp = self.world.can_pickup
        cu = self.world.can_unlock
        caps = f"A: {'pickup' if cp['A'] else '—'} / {'unlock' if cu['A'] else '—'}  |  B: {'pickup' if cp['B'] else '—'} / {'unlock' if cu['B'] else '—'}"
        textbox_lines.append(caps)

        for i, line in enumerate(textbox_lines):
            txt = self.font_textbox.render(line, True, C_TEXTBOX_TEXT)
            self.screen.blit(txt, (self.textbox_rect.x + 10, self.textbox_rect.y + 8 + i * 22))

        pygame.display.flip()

    def _draw_status(self):
        y = self.status_y
        if self.verification_result is True:
            txt = self.font_small.render("Lean: PASSED", True, C_VERIFIED)
            self.screen.blit(txt, (self.panel_rect.x + 10, y))
        elif self.verification_result is False:
            txt = self.font_small.render("Lean: FAILED", True, C_FAILED)
            self.screen.blit(txt, (self.panel_rect.x + 10, y))

    def _draw_entity(self, state: WorldState, kind: str):
        sprite = None
        px, py = None, None

        if kind == "agent_a":
            sprite = _draw_agent_sprite(CELL_SIZE)
            px, py = state.agent_a_pos.x, state.agent_a_pos.y
        elif kind == "agent_b":
            sprite = _draw_agent_b_sprite(CELL_SIZE)
            px, py = state.agent_b_pos.x, state.agent_b_pos.y
        elif kind == "key" and state.key_holder == "":
            sprite = _draw_key_sprite(CELL_SIZE)
            px, py = state.key_pos.x, state.key_pos.y
        elif kind == "door":
            sprite = _draw_door_sprite(CELL_SIZE, not state.door_unlocked)
            px, py = state.door_pos.x, state.door_pos.y
        elif kind == "obstacle":
            sprite = _draw_obstacle_sprite(CELL_SIZE)
            for (ox, oy) in state.obstacles:
                self.screen.blit(sprite, self.grid_rects[oy][ox])
            return

        if sprite is not None and px is not None and py is not None:
            if 0 <= px < self.world.grid_size and 0 <= py < self.world.grid_size:
                self.screen.blit(sprite, self.grid_rects[py][px])

    # ── Event Loop ─────────────────────────────────────────────────

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.MOUSEMOTION:
                self.hover_cell = None
                gs = self.grid_size
                for y in range(gs):
                    for x in range(gs):
                        if self.grid_rects[y][x].collidepoint(event.pos):
                            self.hover_cell = (x, y)
                            break
                self.find_plan_btn.handle_event(event)
                self.verify_btn.handle_event(event)
                for btn in self.step_btns:
                    btn.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                gs = self.grid_size
                for y in range(gs):
                    for x in range(gs):
                        if self.grid_rects[y][x].collidepoint(pos):
                            self._on_grid_click(x, y)
                            break
                sel = self.radio_group.handle_click(pos)
                if sel is not None:
                    self.edit_mode = sel
                for i, rect in enumerate(self.goal_rects):
                    if rect.collidepoint(pos):
                        self.goal_index = i
                self.find_plan_btn.handle_event(event)
                self.verify_btn.handle_event(event)
                for btn in self.step_btns:
                    btn.handle_event(event)

        return True

    def _on_grid_click(self, x: int, y: int):
        mode = EDIT_MODES[self.edit_mode]
        pos = Position(x, y)

        if mode == "agent_A":
            self.world.agent_a_pos = pos
        elif mode == "agent_B":
            self.world.agent_b_pos = pos
        elif mode == "key":
            self.world.key_pos = pos
        elif mode == "door":
            self.world.door_pos = pos
        elif mode == "obstacle":
            key = (x, y)
            if key in self.world.obstacles:
                self.world.obstacles.remove(key)
            else:
                self.world.obstacles.add(key)
        self.selected_cell = (x, y)
        self.plan = []
        self.plan_step = -1
        self.stepper_states = []
        self.stepper_path = []

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()

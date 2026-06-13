"""
Pixel-art 2D GUI for the Certified SMT Planner.

Replaces the Tkinter GUI with a Pygame-based pixel-art interface.
Features:
- Pixel-art styled grid with entity sprites
- Edit mode for placing entities
- Plan display with stepper controls
- Integration with Z3 planner and Lean verifier
"""

from __future__ import annotations

import pygame
import sys
import os
from typing import List, Optional, Tuple, Callable

from .world_model import (
    WorldState, Action, Position, MOVE_DIRECTIONS,
    ACTION_MOVE, ACTION_PICKUP_KEY, ACTION_UNLOCK_DOOR, ACTION_OPEN_DOOR,
    goal_door_unlocked, goal_at_door_and_unlocked,
)
from .z3_planner import Z3Planner
from .lean_verifier import LeanVerifier
from .cegar import CEGARLoop

# ── Constants ──────────────────────────────────────────────────────

CELL_SIZE = 64
GRID_SIZE = 8
PANEL_WIDTH = 280
PADDING = 16
GRID_PADDING = 20

WIN_WIDTH = GRID_PADDING * 2 + CELL_SIZE * GRID_SIZE + PADDING + PANEL_WIDTH
WIN_HEIGHT = GRID_PADDING * 2 + CELL_SIZE * GRID_SIZE

# Colors
C_BG = pygame.Color("#1a1a2e")
C_PANEL = pygame.Color("#16213e")
C_PANEL_BORDER = pygame.Color("#0f3460")
C_GRID_A = pygame.Color("#3a5a3a")
C_GRID_B = pygame.Color("#2d4a2d")
C_GRID_HOVER = pygame.Color(255, 255, 255, 20)
C_SELECTED = pygame.Color(255, 255, 200, 40)
C_AGENT = pygame.Color("#4fc3f7")
C_AGENT_DARK = pygame.Color("#0288d1")
C_KEY = pygame.Color("#ffd54f")
C_KEY_DARK = pygame.Color("#f9a825")
C_DOOR_LOCKED = pygame.Color("#e57373")
C_DOOR_LOCKED_DARK = pygame.Color("#c62828")
C_DOOR_UNLOCKED = pygame.Color("#81c784")
C_DOOR_UNLOCKED_DARK = pygame.Color("#2e7d32")
C_OBSTACLE = pygame.Color("#78909c")
C_OBSTACLE_DARK = pygame.Color("#37474f")
C_TEXT = pygame.Color("#e0e0e0")
C_TEXT_DIM = pygame.Color("#888888")
C_TEXT_ACCENT = pygame.Color("#ffb74d")
C_BUTTON = pygame.Color("#0f3460")
C_BUTTON_HOVER = pygame.Color("#1a4a7a")
C_BUTTON_GREEN = pygame.Color("#2e7d32")
C_BUTTON_GREEN_HOVER = pygame.Color("#388e3c")
C_BUTTON_RED = pygame.Color("#c62828")
C_BUTTON_RED_HOVER = pygame.Color("#d32f2f")
C_STEP_ACTIVE = pygame.Color("#e67e22")
C_VERIFIED = pygame.Color("#4caf50")
C_FAILED = pygame.Color("#f44336")

FPS = 60

EDIT_MODES = ["agent", "key", "door", "obstacle"]
EDIT_MODE_LABELS = ["Agent", "Key", "Door", "Obstacle"]
EDIT_MODE_COLORS = [C_AGENT, C_KEY, C_DOOR_LOCKED, C_OBSTACLE]

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
    cx, cy = size // 2, size // 2
    r = size // 3
    # Body
    pygame.draw.rect(s, C_AGENT_DARK, (cx - r, cy, r * 2, r * 2), border_radius=3)
    # Head
    pygame.draw.circle(s, C_AGENT, (cx, cy - r // 2), r)
    # Eyes
    pygame.draw.circle(s, pygame.Color("white"), (cx - r // 3, cy - r // 2 - 2), 2)
    pygame.draw.circle(s, pygame.Color("white"), (cx + r // 3, cy - r // 2 - 2), 2)
    # Legs
    pygame.draw.rect(s, C_AGENT_DARK, (cx - r // 2, cy + r * 2 - 2, r // 3, r // 2))
    pygame.draw.rect(s, C_AGENT_DARK, (cx + r // 6, cy + r * 2 - 2, r // 3, r // 2))
    _sprite_cache[key] = s
    return s


def _draw_key_sprite(size: int) -> pygame.Surface:
    key = ("key", size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    s = _make_surface(size, size)
    cx, cy = size // 2, size // 2
    # Key head (circle)
    pygame.draw.circle(s, C_KEY_DARK, (cx - 6, cy), 7, 2)
    pygame.draw.circle(s, C_KEY, (cx - 6, cy), 5)
    # Key shaft
    pygame.draw.line(s, C_KEY_DARK, (cx - 1, cy), (cx + 10, cy), 3)
    # Key teeth
    pygame.draw.line(s, C_KEY_DARK, (cx + 10, cy), (cx + 10, cy + 5), 2)
    pygame.draw.line(s, C_KEY_DARK, (cx + 6, cy), (cx + 6, cy + 4), 2)
    _sprite_cache[key] = s
    return s


def _draw_door_sprite(size: int, locked: bool) -> pygame.Surface:
    key = ("door_locked" if locked else "door_unlocked", size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    s = _make_surface(size, size)
    pad = size // 6
    color = C_DOOR_LOCKED if locked else C_DOOR_UNLOCKED
    dark = C_DOOR_LOCKED_DARK if locked else C_DOOR_UNLOCKED_DARK
    # Door frame
    pygame.draw.rect(s, dark, (pad, pad, size - pad * 2, size - pad * 2), border_radius=3)
    pygame.draw.rect(s, color, (pad + 3, pad + 3, size - pad * 2 - 6, size - pad * 2 - 6), border_radius=2)
    # Lock icon
    if locked:
        pygame.draw.circle(s, pygame.Color("white"), (size // 2, size // 2 + 2), 4)
        pygame.draw.rect(s, dark, (size // 2 - 3, size // 2 + 6, 6, 6))
    else:
        # Check mark
        pts = [(size // 2 - 4, size // 2 + 2), (size // 2 - 1, size // 2 + 6), (size // 2 + 5, size // 2 - 2)]
        pygame.draw.lines(s, pygame.Color("white"), False, pts, 2)
    _sprite_cache[key] = s
    return s


def _draw_obstacle_sprite(size: int) -> pygame.Surface:
    key = ("obstacle", size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    s = _make_surface(size, size)
    pad = size // 8
    # Rock shape
    pts = [
        (pad + 4, pad),
        (size - pad - 8, pad + 2),
        (size - pad - 2, size // 2),
        (size - pad - 6, size - pad - 2),
        (size // 2 + 2, size - pad),
        (pad + 2, size - pad - 4),
    ]
    pygame.draw.polygon(s, C_OBSTACLE_DARK, pts)
    pygame.draw.polygon(s, C_OBSTACLE, [(x + 1, y - 1) for x, y in pts], 3)
    _sprite_cache[key] = s
    return s


def _draw_grid_tile(x: int, y: int, size: int) -> pygame.Surface:
    key = ("tile", x, y, size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    s = _make_surface(size, size)
    color = C_GRID_A if (x + y) % 2 == 0 else C_GRID_B
    s.fill(color)
    # Subtle pixel noise
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


# ── Button ─────────────────────────────────────────────────────────

class Button:
    def __init__(self, rect: pygame.Rect, text: str, color: pygame.Color,
                 hover_color: pygame.Color, action: Callable[[], None],
                 font_size: int = 16):
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
            c.r = c.r // 2
            c.g = c.g // 2
            c.b = c.b // 2
            color = c
        pygame.draw.rect(surface, color, self.rect, border_radius=4)
        pygame.draw.rect(surface, pygame.Color(255, 255, 255, 40), self.rect, 1, border_radius=4)
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


# ── Radio Group ────────────────────────────────────────────────────

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
            bg = color if selected else pygame.Color(0, 0, 0, 60)
            pygame.draw.rect(surface, bg, rect, border_radius=4)
            border = color if selected else pygame.Color(255, 255, 255, 20)
            pygame.draw.rect(surface, border, rect, 1 if not selected else 2, border_radius=4)
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
        self.screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
        pygame.display.set_caption("Agent World — Certified SMT Planner")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 18)
        self.font_small = pygame.font.Font(None, 14)
        self.font_title = pygame.font.Font(None, 22)

        # World state
        self.world = WorldState(
            agent_pos=Position(0, 0),
            key_pos=Position(1, 3),
            door_pos=Position(6, 6),
            obstacles={(3, 3), (3, 4), (4, 3), (2, 5)},
            grid_size=GRID_SIZE,
        )
        self.edit_mode = 0
        self.goal_index = 0
        self.plan: List[Action] = []
        self.plan_step = -1
        self.stepper_states: List[WorldState] = []
        self.verification_result: Optional[bool] = None
        self.status_message = ""
        self.iteration_count = 0

        # Grid highlight
        self.hover_cell: Optional[Tuple[int, int]] = None
        self.selected_cell: Optional[Tuple[int, int]] = None

        # Build UI layout
        self._build_layout()

        # Planner and verifier
        self.planner = Z3Planner(max_horizon=8)
        self.verifier = LeanVerifier()

    def _build_layout(self):
        grid_start_x = GRID_PADDING
        grid_start_y = GRID_PADDING
        self.grid_rects: List[List[pygame.Rect]] = []
        for y in range(GRID_SIZE):
            row = []
            for x in range(GRID_SIZE):
                rect = pygame.Rect(
                    grid_start_x + x * CELL_SIZE,
                    grid_start_y + y * CELL_SIZE,
                    CELL_SIZE, CELL_SIZE,
                )
                row.append(rect)
            self.grid_rects.append(row)

        panel_x = GRID_PADDING * 2 + CELL_SIZE * GRID_SIZE
        panel_y = GRID_PADDING
        self.panel_rect = pygame.Rect(panel_x, panel_y, PANEL_WIDTH, CELL_SIZE * GRID_SIZE)

        # Title
        self.title_y = panel_y + 8

        # Edit mode radio buttons
        radio_y = self.title_y + 32
        self.edit_rects = []
        btn_w = (PANEL_WIDTH - 24) // 2
        for i in range(4):
            rx = panel_x + 8 + (i % 2) * (btn_w + 4)
            ry = radio_y + (i // 2) * 28
            self.edit_rects.append(pygame.Rect(rx, ry, btn_w, 24))
        self.radio_group = RadioGroup(self.edit_rects, EDIT_MODE_LABELS, EDIT_MODE_COLORS)

        # Goal dropdown label
        self.goal_label_y = radio_y + 64

        # Goal buttons (simple toggle)
        self.goal_rects = []
        goal_y = self.goal_label_y + 22
        for i in range(len(GOAL_FUNCTIONS)):
            rx = panel_x + 8
            ry = goal_y + i * 28
            self.goal_rects.append(pygame.Rect(rx, ry, PANEL_WIDTH - 16, 24))

        # Action buttons
        btn_y = goal_y + len(GOAL_FUNCTIONS) * 28 + 8
        self.find_plan_btn = Button(
            pygame.Rect(panel_x + 8, btn_y, PANEL_WIDTH - 16, 32),
            "Find Plan", C_BUTTON_GREEN, C_BUTTON_GREEN_HOVER, self._on_find_plan,
        )
        self.verify_btn = Button(
            pygame.Rect(panel_x + 8, btn_y + 38, PANEL_WIDTH - 16, 32),
            "Verify Plan", C_BUTTON, C_BUTTON_HOVER, self._on_verify,
        )

        # Plan display
        plan_y = btn_y + 80
        self.plan_label_y = plan_y
        self.plan_rect = pygame.Rect(panel_x + 8, plan_y + 22, PANEL_WIDTH - 16, 140)

        # Status
        self.status_y = self.plan_rect.bottom + 8

        # Stepper
        step_y = self.status_y + 28
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
                pygame.Rect(bx, step_y + 22, btn_w2, 26),
                label, C_BUTTON, C_BUTTON_HOVER, action, font_size=14,
            ))

        # Iteration counter
        self.iter_y = step_y + 56

    def _on_find_plan(self):
        self.plan = []
        self.plan_step = -1
        self.stepper_states = []
        self.verification_result = None
        self.iteration_count = 0
        self.status_message = "Planning..."
        pygame.display.set_caption("Agent World — Planning...")

        goal_fn = GOAL_FUNCTIONS[self.goal_index][1]
        cegar = CEGARLoop(self.planner, self.verifier)
        verified, plan, iterations = cegar.find_verified_plan(self.world, goal_fn)
        self.iteration_count = iterations

        if plan is not None:
            self.plan = plan
            self.plan_step = -1
            self.stepper_states = []
            if verified:
                self.verification_result = True
                self.status_message = f"✅ Verified plan ({len(plan)} actions, {iterations} iteration{'s' if iterations > 1 else ''})"
            else:
                self.status_message = f"Plan found ({len(plan)} actions) but not verified"
        else:
            self.status_message = f"No plan found (unsat) after {iterations} iteration{'s' if iterations > 1 else ''}"
        pygame.display.set_caption("Agent World — Certified SMT Planner")

    def _on_verify(self):
        if not self.plan:
            self.status_message = "No plan to verify"
            return
        self.status_message = "Verifying..."
        self.verification_result = None

        passed, stdout, stderr, failure_step = self.verifier.verify(self.world, self.plan)
        self.verification_result = passed
        if passed:
            self.status_message = "✅ Plan verified by Lean"
        else:
            if failure_step is not None:
                self.status_message = f"❌ Verification failed at step {failure_step + 1}"
            else:
                err = stderr.strip() if stderr else stdout.strip()[:120]
                self.status_message = f"❌ Verification failed: {err}"

    def _on_step_start(self):
        if not self.plan:
            return
        self.plan_step = -1
        self.stepper_states = []

    def _on_step_back(self):
        if not self.plan:
            return
        if self.plan_step > -1:
            self.plan_step -= 1
            if self.stepper_states:
                self.stepper_states.pop()

    def _on_step_fwd(self):
        if not self.plan:
            return
        next_step = self.plan_step + 1
        if next_step >= len(self.plan):
            return
        if not self.stepper_states:
            current = self.world
        else:
            current = self.stepper_states[-1]
        results = current.apply_action(self.plan[next_step])
        if results:
            self.stepper_states.append(results[0])
            self.plan_step = next_step

    def _on_step_end(self):
        if not self.plan:
            return
        state = self.world
        self.stepper_states = []
        for i, action in enumerate(self.plan):
            results = state.apply_action(action)
            if not results:
                break
            self.stepper_states.append(results[0])
            state = results[0]
        self.plan_step = len(self.stepper_states) - 1

    def _get_current_state(self) -> WorldState:
        if self.stepper_states:
            return self.stepper_states[-1]
        return self.world

    # ── Drawing ────────────────────────────────────────────────────

    def draw(self):
        self.screen.fill(C_BG)

        # Grid
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                rect = self.grid_rects[y][x]
                tile = _draw_grid_tile(x, y, CELL_SIZE)
                self.screen.blit(tile, rect)

        # Entities
        state = self._get_current_state()
        self._draw_entity(state, "agent")
        self._draw_entity(state, "key")
        self._draw_entity(state, "door")
        self._draw_entity(state, "obstacle")

        # Hover / selected
        if self.hover_cell:
            hx, hy = self.hover_cell
            overlay = _make_surface(CELL_SIZE, CELL_SIZE)
            overlay.fill((255, 255, 255, 15))
            self.screen.blit(overlay, self.grid_rects[hy][hx])

        if self.selected_cell:
            sx, sy = self.selected_cell
            sel = _make_surface(CELL_SIZE, CELL_SIZE)
            sel.fill((255, 255, 200, 30))
            self.screen.blit(sel, self.grid_rects[sy][sx])

        # Grid border
        grid_rect = pygame.Rect(
            GRID_PADDING - 1, GRID_PADDING - 1,
            CELL_SIZE * GRID_SIZE + 2, CELL_SIZE * GRID_SIZE + 2,
        )
        pygame.draw.rect(self.screen, C_PANEL_BORDER, grid_rect, 2)

        # Panel
        pygame.draw.rect(self.screen, C_PANEL, self.panel_rect, border_radius=6)
        pygame.draw.rect(self.screen, C_PANEL_BORDER, self.panel_rect, 2, border_radius=6)

        # Title
        title = self.font_title.render("Agent World", True, C_TEXT_ACCENT)
        self.screen.blit(title, (self.panel_rect.x + 8, self.title_y))

        # Edit mode
        lbl = self.font_small.render("Edit Mode:", True, C_TEXT_DIM)
        self.screen.blit(lbl, (self.panel_rect.x + 8, self.edit_rects[0].y - 16))
        self.radio_group.draw(self.screen, self.font_small)

        # Goal
        lbl = self.font_small.render("Goal:", True, C_TEXT_DIM)
        self.screen.blit(lbl, (self.panel_rect.x + 8, self.goal_label_y))
        for i, rect in enumerate(self.goal_rects):
            selected = i == self.goal_index
            color = C_TEXT_ACCENT if selected else pygame.Color(0, 0, 0, 40)
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            border = C_TEXT_ACCENT if selected else pygame.Color(255, 255, 255, 15)
            pygame.draw.rect(self.screen, border, rect, 1 if not selected else 2, border_radius=4)
            txt = self.font_small.render(GOAL_FUNCTIONS[i][0], True, C_TEXT)
            tr = txt.get_rect(center=rect.center)
            self.screen.blit(txt, tr)

        # Buttons
        self.find_plan_btn.draw(self.screen, self.font)
        self.verify_btn.draw(self.screen, self.font)

        # Plan display
        lbl = self.font_small.render("Plan:", True, C_TEXT_DIM)
        self.screen.blit(lbl, (self.panel_rect.x + 8, self.plan_label_y))
        pygame.draw.rect(self.screen, pygame.Color(0, 0, 0, 60), self.plan_rect, border_radius=4)

        plan_lines: List[str] = []
        if self.plan:
            plan_lines = [f"{i+1}. {a}" for i, a in enumerate(self.plan)]
            for i, line in enumerate(plan_lines[:10]):
                color = C_STEP_ACTIVE if i == self.plan_step else C_TEXT
                txt = self.font_small.render(line, True, color)
                self.screen.blit(txt, (self.plan_rect.x + 6, self.plan_rect.y + 4 + i * 16))
        else:
            txt = self.font_small.render("(no plan)", True, C_TEXT_DIM)
            self.screen.blit(txt, (self.plan_rect.x + 6, self.plan_rect.y + 6))

        # Status
        self._draw_status()

        # Stepper
        lbl = self.font_small.render(f"Step {self.plan_step + 1}/{len(self.plan)}", True, C_TEXT)
        self.screen.blit(lbl, (self.panel_rect.x + 8, self.step_label_y))
        has_plan = len(self.plan) > 0
        for btn in self.step_btns:
            btn.disabled = not has_plan
            btn.draw(self.screen, self.font_small)

        # Iteration count
        if self.iteration_count > 0:
            txt = self.font_small.render(f"Refinements: {self.iteration_count}", True, C_TEXT_DIM)
            self.screen.blit(txt, (self.panel_rect.x + 8, self.iter_y))

        pygame.display.flip()

    def _draw_status(self):
        y = self.status_y
        if self.verification_result is True:
            txt = self.font_small.render("✅ Lean verification: PASSED", True, C_VERIFIED)
            self.screen.blit(txt, (self.panel_rect.x + 8, y))
        elif self.verification_result is False:
            txt = self.font_small.render("❌ Lean verification: FAILED", True, C_FAILED)
            self.screen.blit(txt, (self.panel_rect.x + 8, y))
        if self.status_message:
            txt = self.font_small.render(self.status_message, True, C_TEXT)
            self.screen.blit(txt, (self.panel_rect.x + 8, y + 16))

    def _draw_entity(self, state: WorldState, kind: str):
        sprite = None
        px, py = None, None

        if kind == "agent":
            sprite = _draw_agent_sprite(CELL_SIZE)
            px, py = state.agent_pos.x, state.agent_pos.y
        elif kind == "key" and not state.has_key:
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
            if 0 <= px < GRID_SIZE and 0 <= py < GRID_SIZE:
                self.screen.blit(sprite, self.grid_rects[py][px])

    # ── Event Loop ─────────────────────────────────────────────────

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.MOUSEMOTION:
                self.hover_cell = None
                for y in range(GRID_SIZE):
                    for x in range(GRID_SIZE):
                        if self.grid_rects[y][x].collidepoint(event.pos):
                            self.hover_cell = (x, y)
                            break
                self.find_plan_btn.handle_event(event)
                self.verify_btn.handle_event(event)
                for btn in self.step_btns:
                    btn.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                for y in range(GRID_SIZE):
                    for x in range(GRID_SIZE):
                        if self.grid_rects[y][x].collidepoint(pos):
                            self._on_grid_click(x, y)
                            break
                self.radio_group.handle_click(pos)
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

        if mode == "agent":
            self.world.agent_pos = pos
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
        # Clear stale plan on world change
        self.plan = []
        self.plan_step = -1
        self.stepper_states = []

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()

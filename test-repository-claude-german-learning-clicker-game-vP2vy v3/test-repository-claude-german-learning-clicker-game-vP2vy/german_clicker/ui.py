"""
UI komponenty pro Deutsch Klicker – battle verze.
"""

import pygame
from typing import Optional

# ---------------------------------------------------------------------------
# Barvy (temná cave paleta)
# ---------------------------------------------------------------------------
WHITE       = (255, 255, 255)
BLACK       = (0,   0,   0)
DARK_BG     = (28,  20,  38)
PANEL_BG    = (42,  32,  52)
PANEL_EDGE  = (75,  55,  90)

CORRECT_COLOR  = (80,  200, 120)
WRONG_COLOR    = (220,  60,  60)
NEUTRAL_COLOR  = (80,  100, 170)
HOVER_COLOR    = (110, 135, 210)
DISABLED_COLOR = (55,   55,  75)

GOLD    = (255, 210,  60)
SILVER  = (180, 180, 200)
TEXT_LT = (220, 210, 240)
TEXT_DK = (40,   30,  55)

HP_GREEN  = (70,  200,  80)
HP_YELLOW = (220, 190,  40)
HP_RED    = (210,  55,  55)
HP_BG     = (30,   30,  45)

CURSOR_COLOR = (200, 200, 255)


# ---------------------------------------------------------------------------
# Pomocné funkce
# ---------------------------------------------------------------------------
def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    try:
        return pygame.font.SysFont("dejavu sans", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)


def draw_rounded_rect(surface: pygame.Surface, color, rect: pygame.Rect,
                      radius: int = 12) -> None:
    pygame.draw.rect(surface, color, rect, border_radius=radius)


def draw_text_centered(surface: pygame.Surface, text: str, font: pygame.font.Font,
                       color, cx: int, cy: int) -> pygame.Rect:
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(center=(cx, cy))
    surface.blit(rendered, rect)
    return rect


def draw_text_left(surface: pygame.Surface, text: str, font: pygame.font.Font,
                   color, x: int, y: int) -> pygame.Rect:
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(topleft=(x, y))
    surface.blit(rendered, rect)
    return rect


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------
class Button:
    def __init__(self, rect: pygame.Rect, text: str,
                 font: pygame.font.Font,
                 base_color=NEUTRAL_COLOR,
                 hover_color=HOVER_COLOR,
                 text_color=WHITE,
                 radius: int = 12):
        self.rect        = rect
        self.text        = text
        self.font        = font
        self.base_color  = base_color
        self.hover_color = hover_color
        self.text_color  = text_color
        self.radius      = radius
        self.enabled     = True
        self._feedback_color: Optional[tuple] = None
        self._feedback_timer = 0

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def set_feedback(self, correct: bool, duration_ms: int = 600) -> None:
        self._feedback_color = CORRECT_COLOR if correct else WRONG_COLOR
        self._feedback_timer = duration_ms
        self.enabled = False

    def reset(self) -> None:
        self._feedback_color = None
        self._feedback_timer = 0
        self.enabled = True

    def update(self, dt: int, mouse_pos: tuple) -> None:
        if self._feedback_timer > 0:
            self._feedback_timer = max(0, self._feedback_timer - dt)
            if self._feedback_timer == 0:
                self._feedback_color = None

    def draw(self, surface: pygame.Surface, mouse_pos: tuple | None = None) -> None:
        if self._feedback_color:
            color = self._feedback_color
        elif not self.enabled:
            color = DISABLED_COLOR
        elif mouse_pos and self.rect.collidepoint(mouse_pos):
            color = self.hover_color
        else:
            color = self.base_color

        draw_rounded_rect(surface, color, self.rect, self.radius)
        pygame.draw.rect(surface, WHITE, self.rect, 2, border_radius=self.radius)
        draw_text_centered(surface, self.text, self.font,
                           self.text_color, self.rect.centerx, self.rect.centery)


# ---------------------------------------------------------------------------
# HealthBar – healthbar postavy
# ---------------------------------------------------------------------------
class HealthBar:
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font,
                 label: str = "", align: str = "left"):
        """
        align: "left" = label vlevo, "right" = label vpravo (pro nepřítele)
        """
        self.rect    = rect
        self.font    = font
        self.label   = label
        self.align   = align
        self.hp      = 100
        self.max_hp  = 100

    def set_hp(self, hp: int, max_hp: int) -> None:
        self.hp     = max(0, hp)
        self.max_hp = max_hp

    def draw(self, surface: pygame.Surface) -> None:
        ratio = self.hp / self.max_hp if self.max_hp > 0 else 0

        # Barva HP
        if ratio > 0.5:
            hp_color = HP_GREEN
        elif ratio > 0.25:
            hp_color = HP_YELLOW
        else:
            hp_color = HP_RED

        # Pozadí
        draw_rounded_rect(surface, HP_BG, self.rect, 6)

        # Výplň
        if ratio > 0:
            filled = self.rect.copy()
            filled.width = max(0, int(self.rect.width * ratio))
            if filled.width > 0:
                draw_rounded_rect(surface, hp_color, filled, 6)

        pygame.draw.rect(surface, SILVER, self.rect, 2, border_radius=6)

        # Text HP
        hp_text = f"{self.hp}/{self.max_hp}"
        draw_text_centered(surface, hp_text, self.font, WHITE,
                           self.rect.centerx, self.rect.centery)

        # Label nad/pod barem vykreslíme z venku (game.py)


# ---------------------------------------------------------------------------
# TextInput – textové pole pro překlad
# ---------------------------------------------------------------------------
class TextInput:
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font,
                 placeholder: str = "Napiš odpověď..."):
        self.rect        = rect
        self.font        = font
        self.placeholder = placeholder
        self.text        = ""
        self.active      = True
        self._cursor_visible = True
        self._cursor_timer   = 0

    def clear(self) -> None:
        self.text = ""

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Vrátí True při stisknutí Enter (= potvrzení vstupu)."""
        if not self.active:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                return True
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.text = ""
            else:
                char = event.unicode
                if char and char.isprintable():
                    self.text += char
        return False

    def update(self, dt: int) -> None:
        self._cursor_timer += dt
        if self._cursor_timer >= 500:
            self._cursor_timer = 0
            self._cursor_visible = not self._cursor_visible

    def draw(self, surface: pygame.Surface) -> None:
        # Pozadí
        draw_rounded_rect(surface, (20, 15, 30), self.rect, 8)
        pygame.draw.rect(surface, CURSOR_COLOR if self.active else SILVER,
                         self.rect, 2, border_radius=8)

        # Text nebo placeholder
        if self.text:
            content = self.text
            color   = WHITE
        else:
            content = self.placeholder
            color   = (100, 95, 120)

        # Kurzor
        display = content
        if self.active and self._cursor_visible and self.text is not None:
            display = self.text + "|"
            color   = WHITE

        rendered = self.font.render(display, True, color)
        text_rect = rendered.get_rect(midleft=(self.rect.x + 12,
                                               self.rect.centery))
        # Ořez na šířku pole
        surface.set_clip(self.rect.inflate(-4, -4))
        surface.blit(rendered, text_rect)
        surface.set_clip(None)


# ---------------------------------------------------------------------------
# MessageOverlay
# ---------------------------------------------------------------------------
class MessageOverlay:
    def __init__(self, font: pygame.font.Font):
        self.font    = font
        self.text    = ""
        self.color   = WHITE
        self.timer   = 0
        self.visible = False
        self._max    = 1000

    def show(self, text: str, color=WHITE, duration_ms: int = 1200) -> None:
        self.text    = text
        self.color   = color
        self.timer   = duration_ms
        self._max    = duration_ms
        self.visible = True

    def update(self, dt: int) -> None:
        if self.visible:
            self.timer = max(0, self.timer - dt)
            if self.timer == 0:
                self.visible = False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        alpha = min(255, int(255 * self.timer / max(1, self._max)))
        rendered = self.font.render(self.text, True, self.color)
        rendered.set_alpha(alpha)
        cx = surface.get_width() // 2
        cy = surface.get_height() // 2 - 40
        rect = rendered.get_rect(center=(cx, cy))
        surface.blit(rendered, rect)

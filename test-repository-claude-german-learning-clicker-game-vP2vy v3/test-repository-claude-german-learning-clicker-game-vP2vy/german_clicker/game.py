"""
Deutsch Klicker – Battle Edition

Stavový automat:
  MENU  →  CAMP  →  MAP  →  PLAYER_CHOOSE  →  …battle…  →  VICTORY  →  CAMP
             └─ CAMP_NPC (merchant / blacksmith / mayor)
  (GAME_OVER → MENU)
"""

import pygame
import random
from enum import Enum
from dataclasses import dataclass

from words import CATEGORIES
from ui import (
    Button, HealthBar, TextInput, MessageOverlay,
    load_font, draw_rounded_rect, draw_text_centered, draw_text_left,
    WHITE, TEXT_LT, SILVER, CORRECT_COLOR, WRONG_COLOR, GOLD, PANEL_BG,
)

# ---------------------------------------------------------------------------
# Rozměry a globální konstanty
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 900, 600
FPS = 60

RESOLVE_PAUSE_MS = 1400
ENEMY_TURN_DELAY = 700
FIRE_FRAME_MS    = 380   # ms per campfire frame

# ---------------------------------------------------------------------------
# Paleta pixelů pro sprite renderer
# ---------------------------------------------------------------------------
_C: dict[str, tuple | None] = {
    'G': (76,  153,  50), 'g': (50,  110,  35),
    'E': (15,   15,  15),
    'B': (70,  100, 165), 'b': (45,   70, 120),
    'W': (180, 185, 200), 'w': (130, 135, 150),
    'F': (55,  125,  40),
    'S': (160, 100,  50), 's': (110,  68,  32),
    'K': (50,   50,  60), 'k': (28,   28,  36),
    'R': (180,  60,  60), 'r': (120,  35,  35),
    'P': (130,  60, 180), 'p': (85,   35, 125),
    'Y': (210, 180,  45), 'y': (155, 125,  25),
    '.': None,
}

_PLAYER_ART = [
    "....GGGG....",
    "...GGGGGG...",
    "..GGgEGEgGG.",
    "...GGGGGG...",
    "....GGGG....",
    ".W.BBBBBB...",
    "WW.BBBBBB...",
    "WW.BBBBBB...",
    ".W.BBBBBB...",
    "....BBBB....",
    "...FF..FF...",
    "...FF..FF...",
    "...FF..FF...",
    "..FFF..FFF..",
]

_ENEMY_ART: dict[str, list[str]] = {
    "Šnek": [
        "...SSSSSS...",
        "..SSSSSSSs..",
        ".SSSSSSSSss.",
        ".SSSSSSSSss.",
        "..SSSSSSss..",
        "GGGG....GGGGG",
        "GGGGGgGGGGGGG",
        ".GGGgEGGEgGGG",
        ".GGGGGGGGGGG.",
    ],
    "Pavouk": [
        "K...KKKK...K",
        ".KK.KKKK.KK.",
        "..KKkEEkKK..",
        "...EEEEEE...",
        "...EEEEEE...",
        "..KKkEEkKK..",
        ".KK.KKKK.KK.",
        "K...KKKK...K",
    ],
    "Ještěrka": [
        "....RRRR....",
        "...RRRRRR...",
        "..RRrErErRR.",
        "...RRRRRR...",
        "..RRRRRRR...",
        ".RRRRRRRRR..",
        "RR...RR...RR",
        ".R...RR...R.",
        "......R.....",
    ],
    "Netopýr": [
        "P.......P...",
        "PP.PPPP.PP..",
        "PPP.PP.PPP..",
        "PPPpEpPPPP..",
        "PPP.PP.PPP..",
        "PP.PPPP.PP..",
        "P.......P...",
    ],
    "Drak": [
        "...YYYYYYY..",
        "..YYYYYYYYy.",
        "YYYYyEYEyYYY",
        ".YYYYYYYYYY.",
        "..YYYYYY....",
        "...YYYYYY...",
        "....YYYY....",
        "...YY..YY...",
        "..YY....YY..",
    ],
}

ENEMY_SEQUENCE = ["Šnek", "Pavouk", "Ještěrka", "Netopýr", "Drak"]


def _build_sprite(rows: list[str], scale: int = 5,
                  flip: bool = False) -> pygame.Surface:
    h = len(rows)
    w = max(len(r) for r in rows)
    surf = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            color = _C.get(ch)
            if color:
                pygame.draw.rect(surf, color,
                                 (x * scale, y * scale, scale, scale))
    if flip:
        surf = pygame.transform.flip(surf, True, False)
    return surf


# ---------------------------------------------------------------------------
# Překlad: normalizace vstupu (přijme ae/oe/ue/ss místo přehlásek)
# ---------------------------------------------------------------------------
def _normalize(text: str) -> str:
    t = text.lower().strip()
    for article in ("der ", "die ", "das ", "ein ", "eine "):
        if t.startswith(article):
            t = t[len(article):]
            break
    return (t.replace("ae", "ä").replace("oe", "ö")
             .replace("ue", "ü").replace("ss", "ß"))


def check_translation(user_input: str, correct_de: str) -> bool:
    return _normalize(user_input) == _normalize(correct_de)


# ---------------------------------------------------------------------------
# Datové třídy postav
# ---------------------------------------------------------------------------
@dataclass
class Player:
    hp:        int  = 100
    max_hp:    int  = 100
    attack:    int  = 28
    xp:        int  = 0
    level:     int  = 1
    defending: bool = False

    @property
    def xp_to_next(self) -> int:
        return self.level * 80

    def try_level_up(self) -> bool:
        if self.xp >= self.xp_to_next:
            self.xp     -= self.xp_to_next
            self.level  += 1
            self.max_hp += 15
            self.hp      = self.max_hp
            self.attack  += 5
            return True
        return False


@dataclass
class Enemy:
    name:      str
    hp:        int
    max_hp:    int
    attack:    int
    xp_reward: int
    defending: bool = False


def _make_enemy(name: str, player_level: int) -> Enemy:
    base_hp  = 50 + (player_level - 1) * 20
    base_atk = 18 + (player_level - 1) * 5
    return Enemy(
        name=name,
        hp=base_hp, max_hp=base_hp,
        attack=base_atk,
        xp_reward=30 + (player_level - 1) * 15,
    )


# ---------------------------------------------------------------------------
# NPC data
# ---------------------------------------------------------------------------
NPC_DATA: dict[str, dict] = {
    "obchodnik": {
        "name":   "Obchodník Mirek",
        "color":  (200, 155, 75),
        "text":   "Vítej! Mám výborné lektvary\npro unavené cestovatele.",
        "items": [
            {"label": "Malý lektvar  (+30 HP)",  "cost": 20, "action": "heal_30"},
            {"label": "Velký lektvar (plné HP)",  "cost": 50, "action": "heal_full"},
        ],
    },
    "kovar": {
        "name":  "Kovář Tomáš",
        "color": (160, 100, 70),
        "text":  "Hm. Výbava vypadá opotřebovaně.\nMůžu pomoci za rozumnou cenu.",
        "items": [
            {"label": "Nabrousit zbraň  (+8 útok)",   "cost": 40, "action": "upgrade_atk"},
            {"label": "Posílit zbroj    (+25 max HP)", "cost": 40, "action": "upgrade_hp"},
        ],
    },
    "starosta": {
        "name":  "Starosta Václav",
        "color": (80, 110, 175),
        "text":  (
            "Hrdino! Naše vesnice je v ohrožení.\n"
            "Podivná stvoření přicházejí z jeskyně.\n"
            "Poraz jejich vůdce a zachráníš nás!\n\n"
            "Za každého nepřítele dostaneš zkušenosti.\n"
            "Ty pak můžeš utratit u obchodníka nebo kováře."
        ),
        "items": [],
    },
}


# ---------------------------------------------------------------------------
# Fáze stavového automatu
# ---------------------------------------------------------------------------
class Phase(Enum):
    MENU             = "menu"
    CAMP             = "camp"
    CAMP_NPC         = "camp_npc"
    MAP              = "map"
    PLAYER_CHOOSE    = "player_choose"
    PLAYER_TRANSLATE = "player_translate"
    RESOLVE_PLAYER   = "resolve_player"
    ENEMY_TURN       = "enemy_turn"
    RESOLVE_ENEMY    = "resolve_enemy"
    VICTORY          = "victory"
    GAME_OVER        = "game_over"


# ---------------------------------------------------------------------------
# Mapa – lokace
# ---------------------------------------------------------------------------
MAP_LOCATIONS = [
    {"id": "camp",    "name": "Základní kemp",  "pos": (220, 260), "phase": Phase.CAMP},
    {"id": "dungeon", "name": "Temná jeskyně",  "pos": (690, 260), "phase": Phase.PLAYER_CHOOSE},
]
MAP_NODE_R = 42   # poloměr klikatelné oblasti na mapě


# ---------------------------------------------------------------------------
# Hlavní třída Game
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Deutsch Klicker – Battle")
        self.clock  = pygame.time.Clock()

        # Fonty
        self.f_xl = load_font(52, bold=True)
        self.f_lg = load_font(36, bold=True)
        self.f_md = load_font(26, bold=True)
        self.f_sm = load_font(20)
        self.f_xs = load_font(15)

        # Sprite cache
        self.sprites: dict[str, pygame.Surface] = {}
        self._preload_sprites()

        # Word pool
        self._word_pool: list[dict] = [
            w for cat in CATEGORIES.values() for w in cat
        ]

        # Herní objekty (nová hra inicializuje v _new_game)
        self.player: Player = Player()
        self.enemy_index: int = 0
        self.enemy: Enemy = _make_enemy(ENEMY_SEQUENCE[0], 1)

        # Stavové proměnné
        self.phase   = Phase.MENU
        self.running = True

        # Battle přechodné proměnné
        self.player_action:  str       = ""
        self.current_word:   dict      = {}
        self.battle_log:     list[str] = []
        self._pause_timer:   int       = 0
        self._enemy_delay:   int       = 0
        self._level_up_flag: bool      = False

        # Camp proměnné
        self.current_npc: str = ""
        self._npc_buttons: list[Button] = []
        self._npc_close_btn: Button | None = None
        self._npc_feedback: str = ""
        self._npc_feedback_timer: int = 0

        # Campfire animace
        self._fire_frame: int = 0
        self._fire_timer: int = 0

        # Hvězdy (fixní seed → vždy stejné rozmístění)
        rng = random.Random(7)
        self._stars = [(rng.randint(0, SCREEN_W), rng.randint(10, 340))
                       for _ in range(90)]

        # Mapa – hover
        self._map_hover: str | None = None

        # Sestavení UI
        self._build_ui()

    # ------------------------------------------------------------------
    # Sprite cache
    # ------------------------------------------------------------------
    def _preload_sprites(self) -> None:
        self.sprites["player"] = _build_sprite(_PLAYER_ART, scale=5)
        for name, art in _ENEMY_ART.items():
            self.sprites[name] = _build_sprite(art, scale=5, flip=True)

    # ------------------------------------------------------------------
    # Sestavení UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        cx = SCREEN_W // 2

        # ---- Menu ----
        self.btn_menu_start = Button(
            pygame.Rect(cx - 140, 320, 280, 58), "Hrát", self.f_md)
        self.btn_menu_quit  = Button(
            pygame.Rect(cx - 140, 400, 280, 58), "Ukončit", self.f_md)

        # ---- Camp ----
        camp_y  = SCREEN_H - 108
        btn_w   = 185
        gap     = 14
        total_w = btn_w * 4 + gap * 3
        x0      = (SCREEN_W - total_w) // 2

        self.btn_merchant = Button(
            pygame.Rect(x0, camp_y + 30, btn_w, 52),
            "🧺  Obchodník", self.f_sm,
            base_color=(110, 85, 45), hover_color=(145, 115, 60))
        self.btn_blacksmith = Button(
            pygame.Rect(x0 + btn_w + gap, camp_y + 30, btn_w, 52),
            "⚒  Kovář", self.f_sm,
            base_color=(90, 80, 70), hover_color=(120, 105, 90))
        self.btn_mayor = Button(
            pygame.Rect(x0 + (btn_w + gap) * 2,  camp_y + 30, btn_w, 52),
            "📜  Starosta", self.f_sm,
            base_color=(60, 90, 140), hover_color=(80, 120, 175))
        self.btn_leave = Button(
            pygame.Rect(x0 + (btn_w + gap) * 3,  camp_y + 30, btn_w, 52),
            "🗺  Odejít", self.f_sm,
            base_color=(65, 105, 65), hover_color=(85, 135, 85))

        # ---- Healthbary (battle) ----
        self.hp_player = HealthBar(
            pygame.Rect(30, 52, 240, 22), self.f_xs)
        self.hp_enemy  = HealthBar(
            pygame.Rect(SCREEN_W - 270, 52, 240, 22), self.f_xs, align="right")

        # ---- Battle akční tlačítka ----
        self.btn_attack = Button(
            pygame.Rect(cx - 210, 523, 185, 54), "⚔  Útočit", self.f_md,
            base_color=(145, 55, 55), hover_color=(185, 75, 75))
        self.btn_defend = Button(
            pygame.Rect(cx + 25,  523, 185, 54), "🛡  Bránit", self.f_md,
            base_color=(50, 95, 148), hover_color=(70, 125, 188))

        # ---- Textový vstup ----
        self.text_input = TextInput(
            pygame.Rect(cx - 210, 523, 420, 42), self.f_md,
            placeholder="Napiš německy a stiskni Enter…")

        # ---- Zpráva ----
        self.message = MessageOverlay(self.f_lg)

    # ------------------------------------------------------------------
    # Nová hra / start bitvy
    # ------------------------------------------------------------------
    def _new_game(self) -> None:
        self.player      = Player()
        self.enemy_index = 0
        self.enemy       = _make_enemy(ENEMY_SEQUENCE[0], 1)
        self.battle_log  = []
        self._level_up_flag = False
        self._sync_hp_bars()
        self.phase = Phase.CAMP

    def _start_battle(self) -> None:
        """Spustí bitvu s dalším nepřítelem v sekvenci."""
        self._sync_hp_bars()
        self._pick_word()
        self.battle_log = []
        self.phase = Phase.PLAYER_CHOOSE

    def _sync_hp_bars(self) -> None:
        self.hp_player.set_hp(self.player.hp, self.player.max_hp)
        self.hp_enemy.set_hp(self.enemy.hp,   self.enemy.max_hp)

    def _pick_word(self) -> None:
        self.current_word = random.choice(self._word_pool)
        self.text_input.clear()

    def _add_log(self, msg: str) -> None:
        self.battle_log.append(msg)
        if len(self.battle_log) > 4:
            self.battle_log.pop(0)

    # ------------------------------------------------------------------
    # NPC logika
    # ------------------------------------------------------------------
    def _open_npc(self, npc_id: str) -> None:
        self.current_npc      = npc_id
        self._npc_feedback    = ""
        self._npc_feedback_timer = 0
        self._build_npc_buttons()
        self.phase = Phase.CAMP_NPC

    def _build_npc_buttons(self) -> None:
        data  = NPC_DATA[self.current_npc]
        items = data["items"]
        self._npc_buttons = []

        panel_cx = SCREEN_W // 2
        btn_y    = 390
        for item in items:
            lbl = f"{item['label']}   [{item['cost']} XP]"
            btn = Button(
                pygame.Rect(panel_cx - 260, btn_y, 520, 46),
                lbl, self.f_sm,
                base_color=(70, 90, 130), hover_color=(95, 120, 170))
            btn._action = item["action"]  # type: ignore[attr-defined]
            btn._cost   = item["cost"]    # type: ignore[attr-defined]
            self._npc_buttons.append(btn)
            btn_y += 58

        self._npc_close_btn = Button(
            pygame.Rect(panel_cx - 100, btn_y + 4, 200, 44),
            "Zavřít", self.f_sm,
            base_color=(90, 55, 55), hover_color=(125, 75, 75))

    def _handle_npc_action(self, action: str, cost: int) -> None:
        if self.player.xp < cost:
            self._npc_feedback = "Nedostatek XP!"
            self._npc_feedback_timer = 1800
            return
        self.player.xp -= cost
        if action == "heal_30":
            healed = min(30, self.player.max_hp - self.player.hp)
            self.player.hp += healed
            self._npc_feedback = f"+{healed} HP obnoveno."
        elif action == "heal_full":
            healed = self.player.max_hp - self.player.hp
            self.player.hp = self.player.max_hp
            self._npc_feedback = f"Plné HP! (+{healed} HP)"
        elif action == "upgrade_atk":
            self.player.attack += 8
            self._npc_feedback = f"Útok zvýšen na {self.player.attack}."
        elif action == "upgrade_hp":
            self.player.max_hp += 25
            self.player.hp     += 25
            self._npc_feedback = f"Max HP zvýšeno na {self.player.max_hp}."
        self._npc_feedback_timer = 2000

    # ------------------------------------------------------------------
    # Hlavní smyčka
    # ------------------------------------------------------------------
    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS)
            self._process_events()
            self._update(dt)
            self._draw()
        pygame.quit()

    # ------------------------------------------------------------------
    # Zpracování událostí
    # ------------------------------------------------------------------
    def _process_events(self) -> None:
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            # ---------- MENU ----------
            elif self.phase == Phase.MENU:
                if self.btn_menu_start.handle_event(event):
                    self._new_game()
                if self.btn_menu_quit.handle_event(event):
                    self.running = False

            # ---------- CAMP ----------
            elif self.phase == Phase.CAMP:
                if self.btn_merchant.handle_event(event):
                    self._open_npc("obchodnik")
                elif self.btn_blacksmith.handle_event(event):
                    self._open_npc("kovar")
                elif self.btn_mayor.handle_event(event):
                    self._open_npc("starosta")
                elif self.btn_leave.handle_event(event):
                    self.phase = Phase.MAP

            # ---------- CAMP NPC ----------
            elif self.phase == Phase.CAMP_NPC:
                for btn in self._npc_buttons:
                    if btn.handle_event(event):
                        self._handle_npc_action(
                            btn._action, btn._cost)  # type: ignore[attr-defined]
                if self._npc_close_btn and self._npc_close_btn.handle_event(event):
                    self.phase = Phase.CAMP

            # ---------- MAP ----------
            elif self.phase == Phase.MAP:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for loc in MAP_LOCATIONS:
                        dx = mouse[0] - loc["pos"][0]
                        dy = mouse[1] - loc["pos"][1]
                        if dx * dx + dy * dy <= MAP_NODE_R * MAP_NODE_R:
                            target = loc["phase"]
                            if target == Phase.PLAYER_CHOOSE:
                                self._start_battle()
                            else:
                                self.phase = target
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.phase = Phase.CAMP

            # ---------- BATTLE FÁZE 1 ----------
            elif self.phase == Phase.PLAYER_CHOOSE:
                if self.btn_attack.handle_event(event):
                    self.player_action = "attack"
                    self.phase = Phase.PLAYER_TRANSLATE
                elif self.btn_defend.handle_event(event):
                    self.player_action = "defend"
                    self.phase = Phase.PLAYER_TRANSLATE

            # ---------- BATTLE FÁZE 2 ----------
            elif self.phase == Phase.PLAYER_TRANSLATE:
                if self.text_input.handle_event(event):
                    self._submit_translation()

            # ---------- VICTORY / GAME OVER ----------
            elif self.phase in (Phase.VICTORY, Phase.GAME_OVER):
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    if self.phase == Phase.VICTORY:
                        self._next_enemy()
                    else:
                        self.phase = Phase.MENU

    # ------------------------------------------------------------------
    # Aktualizace
    # ------------------------------------------------------------------
    def _update(self, dt: int) -> None:
        self.message.update(dt)
        self.text_input.update(dt)

        # Campfire animace
        if self.phase in (Phase.CAMP, Phase.CAMP_NPC):
            self._fire_timer += dt
            if self._fire_timer >= FIRE_FRAME_MS:
                self._fire_timer = 0
                self._fire_frame = 1 - self._fire_frame

        # NPC feedback timeout
        if self._npc_feedback_timer > 0:
            self._npc_feedback_timer = max(0, self._npc_feedback_timer - dt)

        # Map hover detection
        if self.phase == Phase.MAP:
            mouse = pygame.mouse.get_pos()
            self._map_hover = None
            for loc in MAP_LOCATIONS:
                dx = mouse[0] - loc["pos"][0]
                dy = mouse[1] - loc["pos"][1]
                if dx * dx + dy * dy <= MAP_NODE_R * MAP_NODE_R:
                    self._map_hover = loc["id"]
                    break

        # Battle timery
        if self.phase == Phase.RESOLVE_PLAYER:
            self._pause_timer -= dt
            if self._pause_timer <= 0:
                self._check_enemy_dead()
        elif self.phase == Phase.ENEMY_TURN:
            self._enemy_delay -= dt
            if self._enemy_delay <= 0:
                self._resolve_enemy_turn()
        elif self.phase == Phase.RESOLVE_ENEMY:
            self._pause_timer -= dt
            if self._pause_timer <= 0:
                self._check_player_dead()

    # ------------------------------------------------------------------
    # Battle logika
    # ------------------------------------------------------------------
    def _submit_translation(self) -> None:
        user_text = self.text_input.text.strip()
        correct   = check_translation(user_text, self.current_word["de"])

        if correct:
            if self.player_action == "attack":
                dmg = self.player.attack
                if self.enemy.defending:
                    dmg = dmg // 2
                    self._add_log(f"Správně! Nepřítel se bránil – {dmg} poškození.")
                else:
                    self._add_log(f"Správně! Útok za {dmg} poškození.")
                self.enemy.hp = max(0, self.enemy.hp - dmg)
                self.message.show(f"⚔  Útok!  −{dmg} HP", CORRECT_COLOR)
            else:
                self.player.defending = True
                self._add_log("Správně! Zaujímáš obranný postoj.")
                self.message.show("🛡  Obrana aktivní!", (100, 160, 220))
        else:
            self._add_log(
                f"Špatně! Správně: „{self.current_word['de']}")
            self.message.show("✗  Špatný překlad – akce selhala!", WRONG_COLOR)

        self._sync_hp_bars()
        self._pick_word()
        self.phase        = Phase.RESOLVE_PLAYER
        self._pause_timer = RESOLVE_PAUSE_MS

    def _check_enemy_dead(self) -> None:
        if self.enemy.hp <= 0:
            xp_gain = self.enemy.xp_reward
            self.player.xp += xp_gain
            self._level_up_flag = self.player.try_level_up()
            self._add_log(f"Nepřítel {self.enemy.name} poražen! +{xp_gain} XP.")
            self.message.show(f"Vítězství!  +{xp_gain} XP", GOLD)
            self.phase = Phase.VICTORY
        else:
            self.phase        = Phase.ENEMY_TURN
            self._enemy_delay = ENEMY_TURN_DELAY

    def _resolve_enemy_turn(self) -> None:
        self.enemy.defending = False
        if random.random() < 0.60:
            dmg = self.enemy.attack
            if self.player.defending:
                dmg = dmg // 2
                self._add_log(
                    f"{self.enemy.name} útočí – tvá obrana snižuje na {dmg} dmg!")
            else:
                self._add_log(f"{self.enemy.name} útočí za {dmg} poškození!")
            self.player.hp = max(0, self.player.hp - dmg)
            self.message.show(f"💀  {self.enemy.name} útočí!  −{dmg} HP", WRONG_COLOR)
        else:
            self.enemy.defending = True
            self._add_log(f"{self.enemy.name} se brání – příští útok bude slabší.")
            self.message.show(f"🛡  {self.enemy.name} se brání!", SILVER)

        self.player.defending = False
        self._sync_hp_bars()
        self.phase        = Phase.RESOLVE_ENEMY
        self._pause_timer = RESOLVE_PAUSE_MS

    def _check_player_dead(self) -> None:
        if self.player.hp <= 0:
            self._add_log("Byl jsi poražen…")
            self.phase = Phase.GAME_OVER
        else:
            self.phase = Phase.PLAYER_CHOOSE

    def _next_enemy(self) -> None:
        self.enemy_index = (self.enemy_index + 1) % len(ENEMY_SEQUENCE)
        name = ENEMY_SEQUENCE[self.enemy_index]
        self.enemy = _make_enemy(name, self.player.level)
        self._sync_hp_bars()
        self._level_up_flag = False
        # Po vítězství → zpět do kempu
        self.phase = Phase.CAMP

    # ------------------------------------------------------------------
    # Kreslení – dispečer
    # ------------------------------------------------------------------
    def _draw(self) -> None:
        self.screen.fill((28, 20, 38))

        if self.phase == Phase.MENU:
            self._draw_cave_bg()
            self._draw_menu()
        elif self.phase in (Phase.CAMP, Phase.CAMP_NPC):
            self._draw_camp_bg()
            self._draw_camp_ui()
            if self.phase == Phase.CAMP_NPC:
                self._draw_npc_overlay()
        elif self.phase == Phase.MAP:
            self._draw_map()
        else:
            # Battle phases
            self._draw_cave_bg()
            self._draw_battle()

        pygame.display.flip()

    # ===================================================================
    # MENU
    # ===================================================================
    def _draw_menu(self) -> None:
        cx = SCREEN_W // 2
        draw_text_centered(self.screen, "Deutsch Klicker",
                           self.f_xl, GOLD, cx, 140)
        draw_text_centered(self.screen, "Battle Edition",
                           self.f_md, SILVER, cx, 200)
        draw_text_centered(self.screen,
                           "Bojuj v jeskyni, uč se německy!",
                           self.f_sm, TEXT_LT, cx, 255)
        mouse = pygame.mouse.get_pos()
        self.btn_menu_start.draw(self.screen, mouse)
        self.btn_menu_quit.draw(self.screen,  mouse)
        draw_text_centered(self.screen, "v2.1  |  Python + Pygame",
                           self.f_xs, (85, 75, 100), cx, SCREEN_H - 18)

    # ===================================================================
    # CAMP – prostředí
    # ===================================================================
    def _draw_camp_bg(self) -> None:
        w, h = SCREEN_W, SCREEN_H
        ground_y = h - 115

        # Noční obloha (gradient simulovaný vrstvami)
        for i, col in enumerate([(22, 16, 40), (28, 20, 50),
                                   (32, 24, 55), (26, 18, 46)]):
            band = ground_y // 4
            pygame.draw.rect(self.screen, col, (0, i * band, w, band + 2))

        # Hvězdy
        for (sx, sy) in self._stars:
            if sy < ground_y:
                pygame.draw.circle(self.screen, (230, 225, 200), (sx, sy), 1)

        # Vzdálené hory (siluety)
        mountain_pts = [
            (0, ground_y), (0, ground_y - 80),
            (120, ground_y - 150), (250, ground_y - 80),
            (380, ground_y - 180), (500, ground_y - 90),
            (620, ground_y - 160), (750, ground_y - 95),
            (870, ground_y - 145), (w, ground_y - 90), (w, ground_y),
        ]
        pygame.draw.polygon(self.screen, (35, 28, 48), mountain_pts)

        # Zem (tráva + hlína)
        pygame.draw.rect(self.screen, (40, 58, 28),  (0, ground_y,      w, 14))
        pygame.draw.rect(self.screen, (55, 42, 32),  (0, ground_y + 14, w, h))

        # Stromy vlevo
        self._draw_tree(55,  ground_y + 5)
        self._draw_tree(115, ground_y - 10)
        self._draw_tree(170, ground_y + 3)

        # Stromy vpravo
        self._draw_tree(w - 55,  ground_y + 5)
        self._draw_tree(w - 115, ground_y - 10)
        self._draw_tree(w - 170, ground_y + 3)

        # Stany
        self._draw_tent(230, ground_y + 5, (135, 95, 55))
        self._draw_tent(670, ground_y + 5, (100, 70, 120))

        # Ohniště (animované)
        self._draw_campfire(w // 2, ground_y + 5)

        # Panel kempu (spodní lišta)
        pygame.draw.rect(self.screen, (33, 24, 44),
                         (0, h - 115, w, 115))
        pygame.draw.line(self.screen, (70, 52, 85),
                         (0, h - 115), (w, h - 115), 2)

    def _draw_tree(self, x: int, base_y: int) -> None:
        # Kmen
        pygame.draw.rect(self.screen, (80, 52, 30), (x - 5, base_y - 35, 10, 35))
        # Tři vrstvy listoví (tmavě zelené)
        for layer in range(3):
            lw = 28 - layer * 5
            lh = 18
            ly = base_y - 45 - layer * 16
            pygame.draw.polygon(self.screen, (30 + layer * 8, 72 + layer * 8, 35), [
                (x, ly - lh), (x - lw, ly), (x + lw, ly)
            ])

    def _draw_tent(self, x: int, base_y: int, color: tuple) -> None:
        # Hlavní plachta stanu
        pts = [(x, base_y - 75), (x - 58, base_y), (x + 58, base_y)]
        pygame.draw.polygon(self.screen, color, pts)
        # Světlejší středový pruh
        light = tuple(min(255, c + 30) for c in color)
        pts2  = [(x, base_y - 75), (x - 14, base_y), (x + 14, base_y)]
        pygame.draw.polygon(self.screen, light, pts2)
        # Dveře
        pygame.draw.rect(self.screen, (30, 22, 15), (x - 10, base_y - 22, 20, 22))
        # Obrys
        pygame.draw.polygon(self.screen, (50, 35, 20), pts, 2)

    def _draw_campfire(self, cx: int, base_y: int) -> None:
        # Kameny
        for dx, dy in [(-18, -2), (18, -2), (0, -4), (-10, -5), (10, -5)]:
            pygame.draw.circle(self.screen, (90, 80, 70), (cx + dx, base_y + dy), 5)
        # Polena
        pygame.draw.rect(self.screen, (100, 60, 28),
                         (cx - 20, base_y - 7, 40, 7))
        # Plameny – frame 0 i 1 mají lehce jiný tvar
        if self._fire_frame == 0:
            outer = [(cx - 2, base_y - 55), (cx - 20, base_y - 28),
                     (cx - 8, base_y - 7),  (cx + 8, base_y - 7),
                     (cx + 20, base_y - 28), (cx + 2, base_y - 55)]
            inner = [(cx, base_y - 45), (cx - 12, base_y - 24),
                     (cx - 5, base_y - 7), (cx + 5, base_y - 7),
                     (cx + 12, base_y - 24)]
        else:
            outer = [(cx + 3, base_y - 58), (cx - 22, base_y - 26),
                     (cx - 8, base_y - 7),  (cx + 8, base_y - 7),
                     (cx + 18, base_y - 30), (cx - 1, base_y - 58)]
            inner = [(cx - 2, base_y - 47), (cx - 14, base_y - 22),
                     (cx - 5, base_y - 7),  (cx + 5, base_y - 7),
                     (cx + 10, base_y - 26)]
        pygame.draw.polygon(self.screen, (210, 100, 15), outer)
        pygame.draw.polygon(self.screen, (255, 195, 40), inner)
        # Záře (průhledný oranžový kruh)
        glow_surf = pygame.Surface((120, 80), pygame.SRCALPHA)
        pygame.draw.ellipse(glow_surf, (255, 140, 0, 35), (0, 0, 120, 80))
        self.screen.blit(glow_surf, (cx - 60, base_y - 30))

    def _draw_camp_ui(self) -> None:
        """Spodní lišta kempu s tlačítky a stavem hráče."""
        cx = SCREEN_W // 2
        h  = SCREEN_H

        # Název místa
        draw_text_centered(self.screen, "⛺  Základní kemp",
                           self.f_md, GOLD, cx, h - 105)

        # Stav hráče (HP + XP + level) vlevo v liště
        draw_text_left(self.screen,
                       f"Lv.{self.player.level}  HP {self.player.hp}/{self.player.max_hp}"
                       f"  XP {self.player.xp}/{self.player.xp_to_next}",
                       self.f_xs, SILVER, 20, h - 60)

        mouse = pygame.mouse.get_pos()
        self.btn_merchant.draw(self.screen, mouse)
        self.btn_blacksmith.draw(self.screen, mouse)
        self.btn_mayor.draw(self.screen, mouse)
        self.btn_leave.draw(self.screen, mouse)

    # ===================================================================
    # CAMP – NPC overlay
    # ===================================================================
    def _draw_npc_overlay(self) -> None:
        data = NPC_DATA[self.current_npc]

        # Stmívací overlay
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 165))
        self.screen.blit(dim, (0, 0))

        # Panel
        panel = pygame.Rect(SCREEN_W // 2 - 290, 95, 580, 420)
        pygame.draw.rect(self.screen, (38, 28, 52), panel, border_radius=16)
        pygame.draw.rect(self.screen, (90, 65, 110), panel, 2, border_radius=16)

        cx = SCREEN_W // 2

        # Portrét NPC (barevný kruh s iniciálou)
        port_x, port_y, port_r = cx, 150, 36
        pygame.draw.circle(self.screen, data["color"], (port_x, port_y), port_r)
        pygame.draw.circle(self.screen, WHITE, (port_x, port_y), port_r, 2)
        init = data["name"][0]
        draw_text_centered(self.screen, init, self.f_lg, WHITE, port_x, port_y)

        # Jméno NPC
        draw_text_centered(self.screen, data["name"], self.f_md,
                           GOLD, cx, 202)

        # Dialog text (podpora víceřádkového textu)
        lines = data["text"].split("\n")
        ty = 238
        for line in lines:
            draw_text_centered(self.screen, line, self.f_xs, TEXT_LT, cx, ty)
            ty += 20

        # Shop tlačítka
        mouse = pygame.mouse.get_pos()
        for btn in self._npc_buttons:
            btn.draw(self.screen, mouse)

        # Feedback zpráva
        if self._npc_feedback and self._npc_feedback_timer > 0:
            alpha = min(255, int(255 * self._npc_feedback_timer / 2000))
            feedback_surf = self.f_sm.render(self._npc_feedback, True, CORRECT_COLOR)
            feedback_surf.set_alpha(alpha)
            fb_rect = feedback_surf.get_rect(center=(cx, 470))
            self.screen.blit(feedback_surf, fb_rect)

        # Zavřít
        if self._npc_close_btn:
            self._npc_close_btn.draw(self.screen, mouse)

    # ===================================================================
    # MAPA
    # ===================================================================
    def _draw_map(self) -> None:
        w, h = SCREEN_W, SCREEN_H

        # Pozadí mapy (pergamenová barva)
        self.screen.fill((185, 160, 110))

        # Okraje / rám
        pygame.draw.rect(self.screen, (140, 110, 70), (0, 0, w, h), 18)
        pygame.draw.rect(self.screen, (100, 75, 45),  (0, 0, w, h), 4)

        # Textury mapy (jemné čáry simulující pergamen)
        for gy in range(0, h, 28):
            pygame.draw.line(self.screen, (175, 150, 100), (0, gy), (w, gy), 1)

        # Lesy (zelené shluky na okrajích)
        self._draw_map_forest(60, 200, 7)
        self._draw_map_forest(100, 390, 5)
        self._draw_map_forest(820, 180, 6)
        self._draw_map_forest(790, 400, 5)

        # Hory uprostřed nahoře
        self._draw_map_mountains(400, 130)
        self._draw_map_mountains(490, 120)
        self._draw_map_mountains(450, 145)

        # Cesta mezi lokacemi
        camp_pos    = MAP_LOCATIONS[0]["pos"]
        dungeon_pos = MAP_LOCATIONS[1]["pos"]
        # Tečkovaná cesta (dirt)
        for t in range(0, 100, 6):
            px = int(camp_pos[0] + (dungeon_pos[0] - camp_pos[0]) * t / 100)
            py = int(camp_pos[1] + (dungeon_pos[1] - camp_pos[1]) * t / 100
                     + 18 * (abs(t - 50) / 50))  # mírný oblouk
            pygame.draw.circle(self.screen, (140, 110, 70), (px, py), 3)

        # Nápis mapy
        draw_text_centered(self.screen, "Mapa světa",
                           self.f_lg, (80, 55, 30), w // 2, 45)
        draw_text_centered(self.screen, "Klikni na lokaci pro cestování",
                           self.f_xs, (110, 80, 45), w // 2, 78)
        draw_text_centered(self.screen, "[ Esc ] → zpět do kempu",
                           self.f_xs, (120, 95, 55), w // 2, h - 22)

        # Lokace
        for loc in MAP_LOCATIONS:
            self._draw_map_node(loc)

    def _draw_map_forest(self, cx: int, cy: int, count: int) -> None:
        rng = random.Random(cx * 31 + cy)
        for _ in range(count):
            tx = cx + rng.randint(-35, 35)
            ty = cy + rng.randint(-20, 20)
            pygame.draw.polygon(self.screen, (55, 110, 50), [
                (tx, ty - 22), (tx - 14, ty), (tx + 14, ty)])
            pygame.draw.polygon(self.screen, (45, 90, 42), [
                (tx, ty - 30), (tx - 9, ty - 14), (tx + 9, ty - 14)])

    def _draw_map_mountains(self, cx: int, cy: int) -> None:
        pygame.draw.polygon(self.screen, (130, 115, 105), [
            (cx, cy - 40), (cx - 30, cy), (cx + 30, cy)])
        pygame.draw.polygon(self.screen, (210, 210, 215), [
            (cx, cy - 40), (cx - 10, cy - 20), (cx + 10, cy - 20)])

    def _draw_map_node(self, loc: dict) -> None:
        px, py  = loc["pos"]
        is_hover = self._map_hover == loc["id"]
        is_dungeon = loc["id"] == "dungeon"

        # Záře při hoveru
        if is_hover:
            glow = pygame.Surface((MAP_NODE_R * 4, MAP_NODE_R * 4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 220, 100, 60),
                               (MAP_NODE_R * 2, MAP_NODE_R * 2), MAP_NODE_R * 2)
            self.screen.blit(glow, (px - MAP_NODE_R * 2, py - MAP_NODE_R * 2))

        # Kruh uzlu
        outer_col = (200, 80, 80) if is_dungeon else (80, 140, 80)
        inner_col = (240, 120, 100) if is_dungeon else (120, 190, 120)
        if is_hover:
            outer_col = tuple(min(255, c + 30) for c in outer_col)
            inner_col = tuple(min(255, c + 30) for c in inner_col)

        pygame.draw.circle(self.screen, (80, 55, 30),   (px, py), MAP_NODE_R + 4)
        pygame.draw.circle(self.screen, outer_col,       (px, py), MAP_NODE_R)
        pygame.draw.circle(self.screen, inner_col,       (px, py), MAP_NODE_R - 8)
        pygame.draw.circle(self.screen, (80, 55, 30),   (px, py), MAP_NODE_R, 3)

        # Ikona uvnitř uzlu
        icon = "🕳" if is_dungeon else "⛺"
        draw_text_centered(self.screen, icon, self.f_md,
                           WHITE, px, py)

        # Label pod uzlem
        label_col = (200, 80, 80) if is_dungeon else (40, 100, 40)
        draw_text_centered(self.screen, loc["name"], self.f_sm,
                           label_col, px, py + MAP_NODE_R + 16)

        # "Klikni" nápověda při hoveru
        if is_hover:
            action = "Vstoupit do bitvy" if is_dungeon else "Vrátit se do kempu"
            draw_text_centered(self.screen, action, self.f_xs,
                               (80, 55, 30), px, py + MAP_NODE_R + 38)

    # ===================================================================
    # BATTLE – pozadí jeskyně
    # ===================================================================
    def _draw_cave_bg(self) -> None:
        w, h = SCREEN_W, SCREEN_H
        pygame.draw.rect(self.screen, (38, 28, 50), (0, 0, w, 88))
        pygame.draw.rect(self.screen, (65, 50, 42), (0, h - 118, w, 118))
        tile = (72, 57, 48)
        for tx in range(0, w, 65):
            pygame.draw.line(self.screen, tile, (tx, h - 118), (tx, h), 1)
        for ty in range(h - 118, h, 32):
            pygame.draw.line(self.screen, tile, (0, ty), (w, ty), 1)
        for sx in [90, 240, 400, 560, 720, 850]:
            pts = [(sx - 13, 0), (sx + 13, 0), (sx, 40)]
            pygame.draw.polygon(self.screen, (50, 38, 65), pts)
        for sx in [50, 200, 370, 530, 690, 820]:
            pts = [(sx - 11, h), (sx + 11, h), (sx, h - 35)]
            pygame.draw.polygon(self.screen, (58, 44, 36), pts)
        pygame.draw.rect(self.screen, (60, 45, 75), (0, h - 120, w, 2))

    # ===================================================================
    # BATTLE – HUD + akce
    # ===================================================================
    def _draw_battle(self) -> None:
        self._draw_characters()
        self._draw_hud()
        self._draw_battle_panel()
        self._draw_battle_log()
        self.message.draw(self.screen)
        if self.phase == Phase.VICTORY:
            self._draw_victory_overlay()
        elif self.phase == Phase.GAME_OVER:
            self._draw_gameover_overlay()

    def _draw_characters(self) -> None:
        floor_y = SCREEN_H - 118
        psurf = self.sprites.get("player")
        if psurf:
            self.screen.blit(psurf, (80, floor_y - psurf.get_height()))
        esurf = self.sprites.get(self.enemy.name)
        if esurf:
            ex = SCREEN_W - 80 - esurf.get_width()
            self.screen.blit(esurf, (ex, floor_y - esurf.get_height()))
        draw_text_centered(self.screen, "VS", self.f_md,
                           (90, 70, 110), SCREEN_W // 2, floor_y - 55)

    def _draw_hud(self) -> None:
        draw_text_left(self.screen,
                       f"Hráč  Lv.{self.player.level}",
                       self.f_xs, GOLD, 30, 28)
        xp_ratio = self.player.xp / max(1, self.player.xp_to_next)
        xp_rect  = pygame.Rect(30, 40, 240, 8)
        pygame.draw.rect(self.screen, (38, 30, 50), xp_rect, border_radius=4)
        if xp_ratio > 0:
            pygame.draw.rect(self.screen, GOLD,
                             pygame.Rect(30, 40, int(240 * xp_ratio), 8),
                             border_radius=4)
        pygame.draw.rect(self.screen, SILVER, xp_rect, 1, border_radius=4)
        self.hp_player.draw(self.screen)

        name_surf = self.f_xs.render(self.enemy.name, True, (220, 100, 100))
        self.screen.blit(name_surf,
                         (SCREEN_W - 30 - name_surf.get_width(), 28))
        self.hp_enemy.draw(self.screen)

    def _draw_battle_panel(self) -> None:
        cx    = SCREEN_W // 2
        h     = SCREEN_H
        mouse = pygame.mouse.get_pos()

        pygame.draw.rect(self.screen, (33, 23, 43), (0, h - 118, SCREEN_W, 118))
        pygame.draw.line(self.screen, (65, 48, 82),
                         (0, h - 118), (SCREEN_W, h - 118), 2)

        if self.phase == Phase.PLAYER_CHOOSE:
            draw_text_centered(self.screen, "Vyber akci:",
                               self.f_sm, TEXT_LT, cx, h - 100)
            self.btn_attack.draw(self.screen, mouse)
            self.btn_defend.draw(self.screen, mouse)

        elif self.phase == Phase.PLAYER_TRANSLATE:
            label = "⚔  Útok" if self.player_action == "attack" else "🛡  Obrana"
            draw_text_centered(self.screen,
                               f"{label}  –  Přelož do němčiny:",
                               self.f_sm, GOLD, cx, h - 105)
            draw_text_centered(self.screen,
                               f'„{self.current_word.get("cz", "?")}"',
                               self.f_md, WHITE, cx, h - 80)
            self.text_input.draw(self.screen)
            draw_text_centered(self.screen, "Tip: ä=ae  ö=oe  ü=ue  ß=ss",
                               self.f_xs, (95, 85, 115), cx, h - 12)

        elif self.phase in (Phase.RESOLVE_PLAYER, Phase.ENEMY_TURN,
                            Phase.RESOLVE_ENEMY):
            draw_text_centered(self.screen, "…", self.f_md,
                               (90, 80, 110), cx, h - 65)

    def _draw_battle_log(self) -> None:
        y = 85
        for msg in self.battle_log[-3:]:
            draw_text_left(self.screen, msg, self.f_xs,
                           (135, 125, 155), 30, y)
            y += 18

    def _draw_victory_overlay(self) -> None:
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        cx, cy = SCREEN_W // 2, SCREEN_H // 2 - 90

        draw_text_centered(self.screen, "Vítězství!", self.f_xl, GOLD, cx, cy)
        draw_text_centered(self.screen, f"+{self.enemy.xp_reward} XP",
                           self.f_lg, CORRECT_COLOR, cx, cy + 72)
        if self._level_up_flag:
            draw_text_centered(self.screen,
                               f"⬆  LEVEL UP!  Nyní Lv.{self.player.level}",
                               self.f_md, GOLD, cx, cy + 128)
        draw_text_centered(self.screen,
                           "Stiskni klávesu nebo klikni pro návrat do kempu",
                           self.f_xs, TEXT_LT, cx, cy + 185)

    def _draw_gameover_overlay(self) -> None:
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 155))
        self.screen.blit(overlay, (0, 0))
        cx, cy = SCREEN_W // 2, SCREEN_H // 2 - 90

        draw_text_centered(self.screen, "Konec hry",
                           self.f_xl, WRONG_COLOR, cx, cy)
        draw_text_centered(self.screen,
                           f"Dosáhl jsi úrovně {self.player.level}"
                           f"  •  XP: {self.player.xp}",
                           self.f_md, SILVER, cx, cy + 78)
        draw_text_centered(self.screen,
                           "Stiskni klávesu nebo klikni pro návrat do menu",
                           self.f_xs, TEXT_LT, cx, cy + 148)

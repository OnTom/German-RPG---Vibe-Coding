"""
Deutsch Klicker – Battle Edition

Stavový automat:
  MENU  →  CAMP  →  MAP  →  PLAYER_CHOOSE  →  …battle…  →  VICTORY  →  CAMP
             └─ CAMP_NPC (merchant / blacksmith / mayor)
  (GAME_OVER → MENU)
"""

import pygame
import random
import json
import os
from enum import Enum
from dataclasses import dataclass, field

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

_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "savegame.json")

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
    defense:   int  = 5
    xp:        int  = 0
    level:     int  = 1
    defending: bool = False

    # Dovednosti
    skill_points:  int = 0
    sila:          int = 0   # síla – bonus k útoku
    charisma:      int = 0
    moudrost:      int = 0   # moudrost
    houzevnatost:  int = 0   # houževnatost – bonus k obraně
    agility:       int = 0

    # Inventář
    gold:      int = 0
    inventory: list = field(default_factory=list)  # list of {"name": str, "icon": str}
    equipment: dict = field(default_factory=lambda: {
        "helma": None, "meč": None, "štít": None,
        "brnění": None, "boty": None, "prsten": None, "náhrdelník": None,
    })

    @property
    def xp_to_next(self) -> int:
        return self.level * 80

    def _equipment_bonus(self, stat_name: str) -> int:
        """Spočítá celkový bonus z nasazené výzbroje pro daný stat."""
        total = 0
        for item in self.equipment.values():
            if item:
                total += item.get("stat_bonuses", {}).get(stat_name, 0)
        return total

    @property
    def effective_attack(self) -> int:
        return self.attack + (self.sila + self._equipment_bonus("sila")) * 3

    @property
    def effective_defense(self) -> int:
        return self.defense + (self.houzevnatost + self._equipment_bonus("houzevnatost")) * 2

    def try_level_up(self) -> bool:
        if self.xp >= self.xp_to_next:
            self.xp     -= self.xp_to_next
            self.level  += 1
            self.max_hp += 15
            self.hp      = self.max_hp
            self.attack  += 5
            self.skill_points += 1
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
    loot_gold: int  = 0
    loot_items: list = field(default_factory=list)  # list of {"name": str, "icon": str}


# Názvy mrtvol nepřátel
_CORPSE_NAMES: dict[str, str] = {
    "Šnek":      "Mrtvola šneka",
    "Pavouk":    "Mrtvola pavouka",
    "Ještěrka":  "Mrtvola ještěrky",
    "Netopýr":   "Mrtvola netopýra",
    "Drak":      "Mrtvola draka",
}

_CORPSE_ICONS: dict[str, str] = {
    "Šnek":      "🐌",
    "Pavouk":    "🕷",
    "Ještěrka":  "🦎",
    "Netopýr":   "🦇",
    "Drak":      "🐉",
}

# Tabulka výzbroje, která může vypadnout z nepřátel
_EQUIPMENT_LOOT: dict[str, list[dict]] = {
    "Šnek": [
        {"name": "Šnečí štít", "icon": "🛡", "slot": "štít",
         "stat_bonuses": {"houzevnatost": 1}},
        {"name": "Slizký prsten", "icon": "💍", "slot": "prsten",
         "stat_bonuses": {"sila": 1}},
    ],
    "Pavouk": [
        {"name": "Pavoučí helma", "icon": "🪖", "slot": "helma",
         "stat_bonuses": {"houzevnatost": 1}},
        {"name": "Pavučinové boty", "icon": "👢", "slot": "boty",
         "stat_bonuses": {"agility": 1}},
    ],
    "Ještěrka": [
        {"name": "Ještěrčí meč", "icon": "⚔", "slot": "meč",
         "stat_bonuses": {"sila": 1}},
        {"name": "Šupinové brnění", "icon": "🦺", "slot": "brnění",
         "stat_bonuses": {"houzevnatost": 1}},
    ],
    "Netopýr": [
        {"name": "Křídlatý náhrdelník", "icon": "📿", "slot": "náhrdelník",
         "stat_bonuses": {"charisma": 1}},
        {"name": "Stínové boty", "icon": "👢", "slot": "boty",
         "stat_bonuses": {"agility": 1}},
    ],
    "Drak": [
        {"name": "Dračí helma", "icon": "🪖", "slot": "helma",
         "stat_bonuses": {"houzevnatost": 2}},
        {"name": "Dračí meč", "icon": "⚔", "slot": "meč",
         "stat_bonuses": {"sila": 2}},
        {"name": "Dračí brnění", "icon": "🦺", "slot": "brnění",
         "stat_bonuses": {"houzevnatost": 2}},
    ],
}


def _make_enemy(name: str, player_level: int) -> Enemy:
    base_hp  = 50 + (player_level - 1) * 20
    base_atk = 18 + (player_level - 1) * 5
    gold = random.randint(1, 5)
    corpse_name = _CORPSE_NAMES.get(name, f"Mrtvola: {name}")
    corpse_icon = _CORPSE_ICONS.get(name, "💀")
    loot = [{"name": corpse_name, "icon": corpse_icon}]
    # 90% šance na drop výzbroje
    if random.random() < 0.90 and name in _EQUIPMENT_LOOT:
        equip = random.choice(_EQUIPMENT_LOOT[name])
        loot.append(dict(equip))
    return Enemy(
        name=name,
        hp=base_hp, max_hp=base_hp,
        attack=base_atk,
        xp_reward=30 + (player_level - 1) * 15,
        loot_gold=gold,
        loot_items=loot,
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
        "text":  "Hrdino! Mám pro tebe úkoly.\nSplň je a budeš odměněn!",
        "items": [],
    },
    "hospoda": {
        "name":  "Hostinský Karel",
        "color": (165, 120, 55),
        "text":  "Vítej v Hospodě U Zlatého draka!\nZa pár zlaťáků ti uložím postup.",
        "items": [
            {"label": "Uložit hru", "cost": 10, "action": "save_game"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Úkoly starosty
# ---------------------------------------------------------------------------
QUEST_DEFS = [
    {
        "id": "kill_spiders",
        "name": "Zabij 2 pavouky",
        "type": "kill",
        "target_enemy": "Pavouk",
        "target_count": 2,
        "reward_gold": 15,
        "reward_xp": 50,
        "reward_items": [],
    },
    {
        "id": "collect_gold",
        "name": "Získej 10 zlaťáků",
        "type": "gold",
        "target_count": 10,
        "reward_gold": 20,
        "reward_xp": 40,
        "reward_items": [],
    },
    {
        "id": "bat_corpses",
        "name": "Dones 3 mrtvoly netopýrů",
        "type": "item",
        "target_item": "Mrtvola netopýra",
        "target_count": 3,
        "reward_gold": 25,
        "reward_xp": 60,
        "reward_items": [{"name": "Netopýří amulet", "icon": "🔮"}],
    },
]

# ---------------------------------------------------------------------------
# Sloty výzbroje  (klíč, výchozí ikona, český název)
# ---------------------------------------------------------------------------
EQUIPMENT_SLOT_INFO: dict[str, tuple[str, str]] = {
    "helma":      ("🪖", "Helma"),
    "meč":        ("⚔",  "Meč"),
    "štít":       ("🛡",  "Štít"),
    "brnění":     ("🦺", "Brnění"),
    "boty":       ("👢", "Boty"),
    "prsten":     ("💍", "Prsten"),
    "náhrdelník": ("📿", "Náhrdelník"),
}


# ---------------------------------------------------------------------------
# Fáze stavového automatu
# ---------------------------------------------------------------------------
class Phase(Enum):
    MENU             = "menu"
    CAMP             = "camp"
    CAMP_NPC         = "camp_npc"
    STATS            = "stats"
    INVENTORY        = "inventory"
    MAP              = "map"
    PLAYER_CHOOSE    = "player_choose"
    PLAYER_TRANSLATE = "player_translate"
    RESOLVE_PLAYER   = "resolve_player"
    ENEMY_TURN       = "enemy_turn"
    RESOLVE_ENEMY    = "resolve_enemy"
    LOOT             = "loot"
    CAVE_CHOICE      = "cave_choice"
    FLEE_RESOLVE     = "flee_resolve"
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

        # Inventář – fáze, ze které se otevřel (pro návrat)
        self._inv_return_phase: Phase = Phase.CAMP
        self._inv_selected_idx: int = -1  # index vybraného předmětu (-1 = nic)
        self._inv_selected_slot: str | None = None  # vybraný slot výzbroje

        # Loot – dočasný loot ke zobrazení
        self._loot_gold:  int  = 0
        self._loot_items: list = []
        self._loot_selected: list[bool] = []
        self._loot_item_rects: list[pygame.Rect] = []

        # Útěk z boje
        self._flee_hit: bool = False

        # Úkoly starosty
        self._kill_counts: dict[str, int] = {}
        self._quests_claimed: list[bool] = [False] * len(QUEST_DEFS)

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
            pygame.Rect(cx - 140, 290, 280, 58), "Hrát", self.f_md)
        self.btn_menu_load  = Button(
            pygame.Rect(cx - 140, 360, 280, 58), "Načíst hru", self.f_md,
            base_color=(70, 90, 130), hover_color=(95, 120, 170))
        self.btn_menu_quit  = Button(
            pygame.Rect(cx - 140, 430, 280, 58), "Ukončit", self.f_md)

        # ---- Camp ----
        camp_y  = SCREEN_H - 108
        btn_w   = 155
        gap     = 10
        total_w = btn_w * 5 + gap * 4
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
            pygame.Rect(x0 + (btn_w + gap) * 2, camp_y + 30, btn_w, 52),
            "📜  Starosta", self.f_sm,
            base_color=(60, 90, 140), hover_color=(80, 120, 175))
        self.btn_inn = Button(
            pygame.Rect(x0 + (btn_w + gap) * 3, camp_y + 30, btn_w, 52),
            "🍺  Hospoda", self.f_sm,
            base_color=(130, 90, 40), hover_color=(170, 120, 55))
        self.btn_leave = Button(
            pygame.Rect(x0 + (btn_w + gap) * 4, camp_y + 30, btn_w, 52),
            "🗺  Odejít", self.f_sm,
            base_color=(65, 105, 65), hover_color=(85, 135, 85))

        # ---- Healthbary (battle) ----
        self.hp_player = HealthBar(
            pygame.Rect(30, 52, 240, 22), self.f_xs)
        self.hp_enemy  = HealthBar(
            pygame.Rect(SCREEN_W - 270, 52, 240, 22), self.f_xs, align="right")

        # ---- Battle akční tlačítka (3 vedle sebe) ----
        btn_bw = 140
        btotal = btn_bw * 3 + 20 * 2
        bx0 = cx - btotal // 2
        self.btn_attack = Button(
            pygame.Rect(bx0, 523, btn_bw, 54), "⚔  Útočit", self.f_md,
            base_color=(145, 55, 55), hover_color=(185, 75, 75))
        self.btn_defend = Button(
            pygame.Rect(bx0 + btn_bw + 20, 523, btn_bw, 54), "🛡  Bránit", self.f_md,
            base_color=(50, 95, 148), hover_color=(70, 125, 188))
        self.btn_flee = Button(
            pygame.Rect(bx0 + 2 * (btn_bw + 20), 523, btn_bw, 54), "🏃  Utéct", self.f_md,
            base_color=(130, 110, 40), hover_color=(170, 145, 55))

        # ---- Textový vstup ----
        self.text_input = TextInput(
            pygame.Rect(cx - 210, 523, 420, 42), self.f_md,
            placeholder="Napiš německy a stiskni Enter…")

        # ---- Cave choice tlačítka (po sběru kořisti) ----
        self.btn_cave_continue = Button(
            pygame.Rect(cx - 245, 380, 225, 54), "⚔  Pokračovat", self.f_md,
            base_color=(145, 55, 55), hover_color=(185, 75, 75))
        self.btn_cave_leave = Button(
            pygame.Rect(cx + 20, 380, 225, 54), "🏕  Odejít", self.f_md,
            base_color=(65, 105, 65), hover_color=(85, 135, 85))

        # ---- Stats tlačítko (pravý horní roh) ----
        self.btn_stats = Button(
            pygame.Rect(SCREEN_W - 160, 10, 150, 42),
            "📊  Staty", self.f_sm,
            base_color=(80, 65, 110), hover_color=(110, 90, 150))

        # ---- Inventář tlačítko (vedle stats) ----
        self.btn_inventory = Button(
            pygame.Rect(SCREEN_W - 320, 10, 150, 42),
            "🎒  Inventář", self.f_sm,
            base_color=(100, 80, 50), hover_color=(135, 110, 70))

        # ---- Inventář panel – zavřít ----
        self._inv_close_btn = Button(
            pygame.Rect(SCREEN_W // 2 - 80, 480, 160, 42),
            "Zavřít", self.f_sm,
            base_color=(90, 55, 55), hover_color=(125, 75, 75))

        # ---- Inventář panel – akční tlačítka pro vybraný předmět ----
        self._inv_equip_btn = Button(
            pygame.Rect(0, 0, 120, 36),
            "Vyzbrojit", self.f_sm,
            base_color=(60, 120, 60), hover_color=(80, 160, 80))
        self._inv_discard_btn = Button(
            pygame.Rect(0, 0, 100, 36),
            "Zahodit", self.f_sm,
            base_color=(140, 55, 55), hover_color=(180, 75, 75))
        self._inv_unequip_btn = Button(
            pygame.Rect(0, 0, 120, 36),
            "Sundat", self.f_sm,
            base_color=(130, 100, 40), hover_color=(170, 135, 55))

        # ---- Loot panel – sebrat vybrané ----
        self._loot_collect_selected_btn = Button(
            pygame.Rect(SCREEN_W // 2 - 245, 430, 225, 48),
            "Sebrat", self.f_md,
            base_color=(60, 120, 60), hover_color=(80, 160, 80))
        # ---- Loot panel – sebrat vše ----
        self._loot_collect_btn = Button(
            pygame.Rect(SCREEN_W // 2 + 20, 430, 225, 48),
            "Sebrat vše", self.f_md,
            base_color=(60, 90, 130), hover_color=(80, 120, 170))

        # ---- Stats panel – tlačítka pro přidělení dovednostních bodů ----
        self._stats_skill_buttons: list[Button] = []
        self._stats_close_btn: Button | None = None
        self._build_stats_buttons()

        # ---- Zpráva ----
        self.message = MessageOverlay(self.f_lg)

    # ------------------------------------------------------------------
    # Stats panel – budování tlačítek
    # ------------------------------------------------------------------
    # Definice dovedností: (attr_name, label, popis)
    SKILL_DEFS = [
        ("sila",         "Síla",         "+3 útok"),
        ("charisma",     "Charisma",     "sociální bonus"),
        ("moudrost",     "Moudrost",     "vědomosti"),
        ("houzevnatost", "Houževnatost", "+2 obrana"),
        ("agility",      "Agility",      "rychlost"),
    ]

    def _build_stats_buttons(self) -> None:
        """Vytvoří + tlačítka pro přidělení dovednostních bodů."""
        cx = SCREEN_W // 2
        self._stats_skill_buttons = []

        btn_y = 310
        for attr_name, label, _desc in self.SKILL_DEFS:
            btn = Button(
                pygame.Rect(cx + 140, btn_y - 14, 36, 28),
                "+", self.f_sm,
                base_color=(60, 120, 60), hover_color=(80, 160, 80))
            btn._skill_attr = attr_name  # type: ignore[attr-defined]
            self._stats_skill_buttons.append(btn)
            btn_y += 36

        self._stats_close_btn = Button(
            pygame.Rect(cx - 80, btn_y + 10, 160, 42),
            "Zavřít", self.f_sm,
            base_color=(90, 55, 55), hover_color=(125, 75, 75))

    def _handle_skill_up(self, attr_name: str) -> None:
        """Přidělí jeden dovednostní bod dané dovednosti."""
        if self.player.skill_points <= 0:
            return
        self.player.skill_points -= 1
        current = getattr(self.player, attr_name)
        setattr(self.player, attr_name, current + 1)

    # ------------------------------------------------------------------
    # Inventář
    # ------------------------------------------------------------------
    def _open_inventory(self) -> None:
        """Otevře inventář z jakékoli obrazovky."""
        self._inv_return_phase = self.phase
        self._inv_selected_idx = -1
        self._inv_selected_slot = None
        self.phase = Phase.INVENTORY

    def _equip_item(self, inv_idx: int) -> None:
        """Nasadí předmět z inventáře do příslušného slotu výzbroje."""
        if inv_idx < 0 or inv_idx >= len(self.player.inventory):
            return
        item = self.player.inventory[inv_idx]
        slot = item.get("slot")
        if not slot or slot not in self.player.equipment:
            return
        # Sundej starý předmět ze slotu (vrátí se do inventáře)
        old_item = self.player.equipment[slot]
        self.player.equipment[slot] = item
        self.player.inventory.pop(inv_idx)
        if old_item:
            self.player.inventory.append(old_item)
        self._inv_selected_idx = -1

    def _unequip_item(self, slot: str) -> None:
        """Sundá předmět z výzbroje do inventáře."""
        item = self.player.equipment.get(slot)
        if not item:
            return
        if len(self.player.inventory) >= 12:
            return  # inventář plný
        self.player.equipment[slot] = None
        self.player.inventory.append(item)

    def _discard_item(self, inv_idx: int) -> None:
        """Zahodí předmět z inventáře."""
        if inv_idx < 0 or inv_idx >= len(self.player.inventory):
            return
        self.player.inventory.pop(inv_idx)
        self._inv_selected_idx = -1

    def _collect_loot(self) -> None:
        """Sebere veškerý loot do inventáře hráče."""
        self.player.gold += self._loot_gold
        for item in self._loot_items:
            self.player.inventory.append(item)
        self._loot_gold  = 0
        self._loot_items = []
        self._loot_selected = []
        self._loot_item_rects = []
        self.phase = Phase.CAVE_CHOICE

    def _collect_loot_selected(self) -> None:
        """Sebere pouze označené předměty do inventáře hráče."""
        self.player.gold += self._loot_gold
        for i, item in enumerate(self._loot_items):
            if i < len(self._loot_selected) and self._loot_selected[i]:
                self.player.inventory.append(item)
        self._loot_gold  = 0
        self._loot_items = []
        self._loot_selected = []
        self._loot_item_rects = []
        self.phase = Phase.CAVE_CHOICE

    def _cave_continue(self) -> None:
        """Pokračuje v průzkumu jeskyně – další nepřítel."""
        self.enemy_index = (self.enemy_index + 1) % len(ENEMY_SEQUENCE)
        name = ENEMY_SEQUENCE[self.enemy_index]
        self.enemy = _make_enemy(name, self.player.level)
        self._sync_hp_bars()
        self._level_up_flag = False
        self._start_battle()

    def _attempt_flee(self) -> None:
        """Pokus o útěk z boje. 50% šance na zásah nepřítelem."""
        if random.random() < 0.5:
            dmg = max(1, self.enemy.attack - self.player.effective_defense)
            self.player.hp = max(0, self.player.hp - dmg)
            self._sync_hp_bars()
            self._add_log(f"Při útěku tě {self.enemy.name} zasáhl za {dmg}!")
            self.message.show(f"💀  Zásah při útěku!  −{dmg} HP", WRONG_COLOR)
            self._flee_hit = True
        else:
            self._add_log("Podařilo se utéct bez zranění!")
            self.message.show("🏃  Úspěšný útěk!", CORRECT_COLOR)
            self._flee_hit = False
        self.phase = Phase.FLEE_RESOLVE
        self._pause_timer = RESOLVE_PAUSE_MS

    def _toggle_loot_selection(self, pos: tuple) -> None:
        """Přepne výběr předmětu v loot panelu."""
        for i, rect in enumerate(self._loot_item_rects):
            if rect.collidepoint(pos):
                if i < len(self._loot_selected):
                    self._loot_selected[i] = not self._loot_selected[i]
                break

    # ------------------------------------------------------------------
    # Ukládání a načítání hry
    # ------------------------------------------------------------------
    def _save_game(self) -> bool:
        """Uloží aktuální stav hry do souboru."""
        data = {
            "player": {
                "hp": self.player.hp, "max_hp": self.player.max_hp,
                "attack": self.player.attack, "defense": self.player.defense,
                "xp": self.player.xp, "level": self.player.level,
                "skill_points": self.player.skill_points,
                "sila": self.player.sila, "charisma": self.player.charisma,
                "moudrost": self.player.moudrost,
                "houzevnatost": self.player.houzevnatost,
                "agility": self.player.agility,
                "gold": self.player.gold,
                "inventory": self.player.inventory,
                "equipment": self.player.equipment,
            },
            "enemy_index": self.enemy_index,
            "kill_counts": self._kill_counts,
            "quests_claimed": self._quests_claimed,
        }
        try:
            with open(_SAVE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def _load_game(self) -> bool:
        """Načte uloženou hru ze souboru."""
        try:
            with open(_SAVE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return False

        pd = data["player"]
        self.player = Player(
            hp=pd["hp"], max_hp=pd["max_hp"],
            attack=pd["attack"], defense=pd["defense"],
            xp=pd["xp"], level=pd["level"],
            skill_points=pd["skill_points"],
            sila=pd["sila"], charisma=pd["charisma"],
            moudrost=pd["moudrost"], houzevnatost=pd["houzevnatost"],
            agility=pd["agility"],
            gold=pd["gold"],
            inventory=pd.get("inventory", []),
            equipment=pd.get("equipment", {
                "helma": None, "meč": None, "štít": None,
                "brnění": None, "boty": None, "prsten": None,
                "náhrdelník": None,
            }),
        )
        self.enemy_index = data["enemy_index"]
        self._kill_counts = data.get("kill_counts", {})
        self._quests_claimed = data.get("quests_claimed",
                                        [False] * len(QUEST_DEFS))

        name = ENEMY_SEQUENCE[self.enemy_index]
        self.enemy = _make_enemy(name, self.player.level)
        self.battle_log = []
        self._level_up_flag = False
        self._sync_hp_bars()
        self.phase = Phase.CAMP
        return True

    @staticmethod
    def _has_save() -> bool:
        return os.path.exists(_SAVE_PATH)

    # ------------------------------------------------------------------
    # Úkoly starosty
    # ------------------------------------------------------------------
    def _get_quest_progress(self, quest: dict) -> tuple[int, int]:
        """Vrátí (aktuální, cíl) pro daný úkol."""
        target = quest["target_count"]
        if quest["type"] == "kill":
            current = self._kill_counts.get(quest["target_enemy"], 0)
        elif quest["type"] == "gold":
            current = self.player.gold
        elif quest["type"] == "item":
            current = sum(1 for item in self.player.inventory
                          if item["name"] == quest["target_item"])
        else:
            current = 0
        return min(current, target), target

    def _claim_quest(self, quest_idx: int) -> None:
        """Vyzvedne odměnu za splněný úkol."""
        quest = QUEST_DEFS[quest_idx]
        progress, target = self._get_quest_progress(quest)
        if progress < target or self._quests_claimed[quest_idx]:
            return

        # Odebrat požadované předměty z inventáře (typ "item")
        if quest["type"] == "item":
            to_remove = quest["target_count"]
            new_inv = []
            for item in self.player.inventory:
                if item["name"] == quest["target_item"] and to_remove > 0:
                    to_remove -= 1
                else:
                    new_inv.append(item)
            self.player.inventory = new_inv

        # Odměny
        self.player.gold += quest["reward_gold"]
        self.player.xp += quest["reward_xp"]
        for item in quest["reward_items"]:
            self.player.inventory.append(dict(item))
        self.player.try_level_up()

        self._quests_claimed[quest_idx] = True
        self._npc_feedback = f"Úkol splněn! +{quest['reward_gold']} 💰, +{quest['reward_xp']} XP"
        self._npc_feedback_timer = 2500
        # Refresh tlačítek
        self._build_npc_buttons()

    # ------------------------------------------------------------------
    # Nová hra / start bitvy
    # ------------------------------------------------------------------
    def _new_game(self) -> None:
        self.player      = Player()
        self.enemy_index = 0
        self.enemy       = _make_enemy(ENEMY_SEQUENCE[0], 1)
        self.battle_log  = []
        self._level_up_flag = False
        self._kill_counts = {}
        self._quests_claimed = [False] * len(QUEST_DEFS)
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
        self._npc_buttons = []

        panel_cx = SCREEN_W // 2

        if self.current_npc == "starosta":
            # Úkoly starosty
            btn_y = 310
            for i, quest in enumerate(QUEST_DEFS):
                progress, target = self._get_quest_progress(quest)
                is_complete = progress >= target
                is_claimed = self._quests_claimed[i]

                if is_claimed:
                    lbl = f"✓  {quest['name']}  [Splněno]"
                    base_c, hover_c = (50, 80, 50), (50, 80, 50)
                elif is_complete:
                    lbl = f"★  {quest['name']}  [Vyzvednout!]"
                    base_c, hover_c = (60, 120, 60), (80, 160, 80)
                else:
                    lbl = f"○  {quest['name']}  [{progress}/{target}]"
                    base_c, hover_c = (60, 55, 75), (60, 55, 75)

                btn = Button(
                    pygame.Rect(panel_cx - 260, btn_y, 520, 46),
                    lbl, self.f_sm,
                    base_color=base_c, hover_color=hover_c)
                btn._action = f"claim_quest_{i}"  # type: ignore[attr-defined]
                btn._cost   = 0                    # type: ignore[attr-defined]
                btn.enabled = is_complete and not is_claimed
                self._npc_buttons.append(btn)
                btn_y += 56
        else:
            # Obchodník / kovář – platba zlaťáky
            items = data["items"]
            btn_y = 390
            for item in items:
                lbl = f"{item['label']}   [{item['cost']} 💰]"
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
        # Úkoly starosty
        if action.startswith("claim_quest_"):
            quest_idx = int(action.split("_")[-1])
            self._claim_quest(quest_idx)
            return

        # Platba zlaťáky
        if self.player.gold < cost:
            self._npc_feedback = "Nedostatek zlata!"
            self._npc_feedback_timer = 1800
            return
        self.player.gold -= cost
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
        elif action == "save_game":
            if self._save_game():
                self._npc_feedback = "Hra uložena!"
            else:
                self.player.gold += cost  # vrátit zlato při chybě
                self._npc_feedback = "Chyba při ukládání!"
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
                if self.btn_menu_load.handle_event(event):
                    self._load_game()
                if self.btn_menu_quit.handle_event(event):
                    self.running = False

            # ---------- CAMP ----------
            elif self.phase == Phase.CAMP:
                if self.btn_inventory.handle_event(event):
                    self._open_inventory()
                elif self.btn_stats.handle_event(event):
                    self.phase = Phase.STATS
                elif self.btn_merchant.handle_event(event):
                    self._open_npc("obchodnik")
                elif self.btn_blacksmith.handle_event(event):
                    self._open_npc("kovar")
                elif self.btn_mayor.handle_event(event):
                    self._open_npc("starosta")
                elif self.btn_inn.handle_event(event):
                    self._open_npc("hospoda")
                elif self.btn_leave.handle_event(event):
                    self.phase = Phase.MAP

            # ---------- STATS ----------
            elif self.phase == Phase.STATS:
                for btn in self._stats_skill_buttons:
                    if btn.handle_event(event):
                        self._handle_skill_up(
                            btn._skill_attr)  # type: ignore[attr-defined]
                if self._stats_close_btn and self._stats_close_btn.handle_event(event):
                    self.phase = Phase.CAMP
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.phase = Phase.CAMP

            # ---------- INVENTORY ----------
            elif self.phase == Phase.INVENTORY:
                if self._inv_close_btn.handle_event(event):
                    self.phase = self._inv_return_phase
                elif self._inv_equip_btn.handle_event(event):
                    if 0 <= self._inv_selected_idx < len(self.player.inventory):
                        self._equip_item(self._inv_selected_idx)
                elif self._inv_discard_btn.handle_event(event):
                    if 0 <= self._inv_selected_idx < len(self.player.inventory):
                        self._discard_item(self._inv_selected_idx)
                elif self._inv_unequip_btn.handle_event(event):
                    slot = getattr(self._inv_unequip_btn, "_slot", None)
                    if slot:
                        self._unequip_item(slot)
                        self._inv_selected_slot = None
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    clicked = False
                    # Klik na předmět v mřížce
                    for i, rect in enumerate(
                            getattr(self, "_inv_item_rects", [])):
                        if (rect.collidepoint(event.pos)
                                and i < len(self.player.inventory)):
                            self._inv_selected_idx = (
                                -1 if self._inv_selected_idx == i else i)
                            self._inv_selected_slot = None
                            clicked = True
                            break
                    # Klik na slot výzbroje
                    if not clicked:
                        for slot_name, rect in getattr(
                                self, "_inv_slot_rects", {}).items():
                            if rect.collidepoint(event.pos):
                                equipped = self.player.equipment.get(slot_name)
                                if equipped:
                                    self._inv_selected_slot = (
                                        None if self._inv_selected_slot == slot_name
                                        else slot_name)
                                    self._inv_selected_idx = -1
                                    clicked = True
                                break
                    if not clicked:
                        self._inv_selected_idx = -1
                        self._inv_selected_slot = None
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.phase = self._inv_return_phase

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
                if self.btn_inventory.handle_event(event):
                    self._open_inventory()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
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
                if self.btn_inventory.handle_event(event):
                    self._open_inventory()
                elif self.btn_attack.handle_event(event):
                    self.player_action = "attack"
                    self.phase = Phase.PLAYER_TRANSLATE
                elif self.btn_defend.handle_event(event):
                    self.player_action = "defend"
                    self.phase = Phase.PLAYER_TRANSLATE
                elif self.btn_flee.handle_event(event):
                    self._attempt_flee()

            # ---------- BATTLE FÁZE 2 ----------
            elif self.phase == Phase.PLAYER_TRANSLATE:
                if self.text_input.handle_event(event):
                    self._submit_translation()

            # ---------- LOOT ----------
            elif self.phase == Phase.LOOT:
                if self._loot_collect_btn.handle_event(event):
                    self._collect_loot()
                elif self._loot_collect_selected_btn.handle_event(event):
                    self._collect_loot_selected()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._toggle_loot_selection(event.pos)

            # ---------- CAVE CHOICE (po sběru kořisti) ----------
            elif self.phase == Phase.CAVE_CHOICE:
                if self.btn_cave_continue.handle_event(event):
                    self._cave_continue()
                elif self.btn_cave_leave.handle_event(event):
                    self._next_enemy()

            # ---------- GAME OVER ----------
            elif self.phase == Phase.GAME_OVER:
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    self.phase = Phase.MENU

    # ------------------------------------------------------------------
    # Aktualizace
    # ------------------------------------------------------------------
    def _update(self, dt: int) -> None:
        self.message.update(dt)
        self.text_input.update(dt)

        # Campfire animace
        if self.phase in (Phase.CAMP, Phase.CAMP_NPC, Phase.STATS, Phase.INVENTORY):
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
        elif self.phase == Phase.FLEE_RESOLVE:
            self._pause_timer -= dt
            if self._pause_timer <= 0:
                if self.player.hp <= 0:
                    self.phase = Phase.GAME_OVER
                else:
                    self.phase = Phase.CAMP

    # ------------------------------------------------------------------
    # Battle logika
    # ------------------------------------------------------------------
    def _submit_translation(self) -> None:
        user_text = self.text_input.text.strip()
        correct   = check_translation(user_text, self.current_word["de"])

        if correct:
            if self.player_action == "attack":
                dmg = self.player.effective_attack
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
            # Počítadlo zabití pro úkoly
            self._kill_counts[self.enemy.name] = (
                self._kill_counts.get(self.enemy.name, 0) + 1)
            self._add_log(f"Nepřítel {self.enemy.name} poražen! +{xp_gain} XP.")
            self.message.show(f"Vítězství!  +{xp_gain} XP", GOLD)
            # Příprava loot obrazovky
            self._loot_gold  = self.enemy.loot_gold
            self._loot_items = list(self.enemy.loot_items)
            self._loot_selected = [False] * len(self._loot_items)
            self._loot_item_rects = []
            self.phase = Phase.LOOT
        else:
            self.phase        = Phase.ENEMY_TURN
            self._enemy_delay = ENEMY_TURN_DELAY

    def _resolve_enemy_turn(self) -> None:
        self.enemy.defending = False
        if random.random() < 0.60:
            dmg = max(1, self.enemy.attack - self.player.effective_defense)
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
        elif self.phase in (Phase.CAMP, Phase.CAMP_NPC, Phase.STATS):
            self._draw_camp_bg()
            self._draw_camp_ui()
            if self.phase == Phase.CAMP_NPC:
                self._draw_npc_overlay()
            elif self.phase == Phase.STATS:
                self._draw_stats_overlay()
        elif self.phase == Phase.INVENTORY:
            # Vykreslíme pozadí podle původní fáze
            if self._inv_return_phase in (Phase.CAMP, Phase.CAMP_NPC, Phase.STATS):
                self._draw_camp_bg()
                self._draw_camp_ui()
            elif self._inv_return_phase == Phase.MAP:
                self._draw_map()
            else:
                self._draw_cave_bg()
                self._draw_battle()
            self._draw_inventory_overlay()
        elif self.phase == Phase.MAP:
            self._draw_map()
        else:
            # Battle phases (including LOOT)
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
        self.btn_menu_load.enabled = self._has_save()
        self.btn_menu_load.draw(self.screen, mouse)
        self.btn_menu_quit.draw(self.screen,  mouse)
        draw_text_centered(self.screen, "v2.4  |  Python + Pygame",
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

        # === Horní HUD s životy, XP, levelem a zlatem ===
        hud_h = 52
        hud_surf = pygame.Surface((SCREEN_W, hud_h), pygame.SRCALPHA)
        hud_surf.fill((20, 14, 30, 180))
        self.screen.blit(hud_surf, (0, 0))
        pygame.draw.line(self.screen, (70, 52, 85),
                         (0, hud_h), (SCREEN_W, hud_h), 1)

        # Level
        draw_text_left(self.screen, f"Lv. {self.player.level}",
                       self.f_md, GOLD, 15, 14)

        # HP bar
        hp_bar_x, hp_bar_y, hp_bar_w, hp_bar_h = 110, 10, 200, 14
        hp_ratio = self.player.hp / max(1, self.player.max_hp)
        draw_text_left(self.screen, "❤", self.f_sm, (210, 55, 55),
                       hp_bar_x - 2, hp_bar_y + 14)
        pygame.draw.rect(self.screen, (30, 22, 40),
                         (hp_bar_x, hp_bar_y, hp_bar_w, hp_bar_h),
                         border_radius=4)
        hp_col = ((70, 200, 80) if hp_ratio > 0.5
                  else (220, 190, 40) if hp_ratio > 0.25
                  else (210, 55, 55))
        if hp_ratio > 0:
            pygame.draw.rect(self.screen, hp_col,
                             (hp_bar_x, hp_bar_y,
                              int(hp_bar_w * hp_ratio), hp_bar_h),
                             border_radius=4)
        draw_text_left(self.screen,
                       f"{self.player.hp}/{self.player.max_hp}",
                       self.f_xs, WHITE,
                       hp_bar_x + 4, hp_bar_y - 1)

        # XP bar
        xp_bar_x, xp_bar_y, xp_bar_w, xp_bar_h = 110, 30, 200, 10
        xp_ratio = self.player.xp / max(1, self.player.xp_to_next)
        draw_text_left(self.screen, "✦", self.f_xs, SILVER,
                       xp_bar_x - 2, xp_bar_y + 6)
        pygame.draw.rect(self.screen, (30, 22, 40),
                         (xp_bar_x, xp_bar_y, xp_bar_w, xp_bar_h),
                         border_radius=3)
        if xp_ratio > 0:
            pygame.draw.rect(self.screen, (100, 140, 220),
                             (xp_bar_x, xp_bar_y,
                              int(xp_bar_w * min(1.0, xp_ratio)), xp_bar_h),
                             border_radius=3)
        draw_text_left(self.screen,
                       f"{self.player.xp}/{self.player.xp_to_next}",
                       self.f_xs, SILVER,
                       xp_bar_x + 4, xp_bar_y - 2)

        # Gold
        draw_text_left(self.screen, f"💰  {self.player.gold}",
                       self.f_sm, GOLD, 330, 14)

        # Název místa
        draw_text_centered(self.screen, "⛺  Základní kemp",
                           self.f_md, GOLD, cx, h - 105)

        mouse = pygame.mouse.get_pos()

        # Inventář tlačítko – pravý horní roh
        self.btn_inventory.draw(self.screen, mouse)

        # Stats tlačítko – pravý horní roh
        self.btn_stats.draw(self.screen, mouse)
        # Indikátor dostupných bodů
        if self.player.skill_points > 0:
            badge_x = self.btn_stats.rect.right - 8
            badge_y = self.btn_stats.rect.top - 4
            pygame.draw.circle(self.screen, (220, 60, 60), (badge_x, badge_y), 10)
            draw_text_centered(self.screen, str(self.player.skill_points),
                               self.f_xs, WHITE, badge_x, badge_y)

        self.btn_merchant.draw(self.screen, mouse)
        self.btn_blacksmith.draw(self.screen, mouse)
        self.btn_mayor.draw(self.screen, mouse)
        self.btn_inn.draw(self.screen, mouse)
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

        # Panel – vyšší pro starostu (kvůli úkolům)
        panel_h = 460 if self.current_npc == "starosta" else 420
        panel = pygame.Rect(SCREEN_W // 2 - 290, 55, 580, panel_h)
        pygame.draw.rect(self.screen, (38, 28, 52), panel, border_radius=16)
        pygame.draw.rect(self.screen, (90, 65, 110), panel, 2, border_radius=16)

        cx = SCREEN_W // 2

        # Portrét NPC (barevný kruh s iniciálou)
        port_x, port_y, port_r = cx, 110, 36
        pygame.draw.circle(self.screen, data["color"], (port_x, port_y), port_r)
        pygame.draw.circle(self.screen, WHITE, (port_x, port_y), port_r, 2)
        init = data["name"][0]
        draw_text_centered(self.screen, init, self.f_lg, WHITE, port_x, port_y)

        # Jméno NPC
        draw_text_centered(self.screen, data["name"], self.f_md,
                           GOLD, cx, 162)

        # Dialog text (podpora víceřádkového textu)
        lines = data["text"].split("\n")
        ty = 192
        for line in lines:
            draw_text_centered(self.screen, line, self.f_xs, TEXT_LT, cx, ty)
            ty += 20

        mouse = pygame.mouse.get_pos()

        if self.current_npc == "starosta":
            # Oddělovač
            sep_y = 235
            pygame.draw.line(self.screen, (90, 65, 110),
                             (cx - 250, sep_y), (cx + 250, sep_y), 1)

            # Nadpis úkolů
            draw_text_left(self.screen, "Úkoly",
                           self.f_md, SILVER, cx - 240, sep_y + 10)

            # Detaily ke každému úkolu + tlačítka
            qy = sep_y + 48
            for i, quest in enumerate(QUEST_DEFS):
                progress, target = self._get_quest_progress(quest)
                is_claimed = self._quests_claimed[i]
                is_complete = progress >= target

                # Odměna popis
                reward_parts = []
                if quest["reward_gold"]:
                    reward_parts.append(f"{quest['reward_gold']} 💰")
                if quest["reward_xp"]:
                    reward_parts.append(f"{quest['reward_xp']} XP")
                for ri in quest["reward_items"]:
                    reward_parts.append(f"{ri['icon']} {ri['name']}")
                reward_str = "Odměna: " + ", ".join(reward_parts)

                draw_text_left(self.screen, reward_str,
                               self.f_xs, (140, 130, 100), cx - 240, qy + 4)

                # Tlačítko
                if i < len(self._npc_buttons):
                    self._npc_buttons[i].rect.y = qy + 22
                    self._npc_buttons[i].draw(self.screen, mouse)

                qy += 76
        else:
            # Shop tlačítka
            for btn in self._npc_buttons:
                btn.draw(self.screen, mouse)

        # Feedback zpráva
        if self._npc_feedback and self._npc_feedback_timer > 0:
            alpha = min(255, int(255 * self._npc_feedback_timer / 2500))
            feedback_surf = self.f_sm.render(self._npc_feedback, True, CORRECT_COLOR)
            feedback_surf.set_alpha(alpha)
            fb_rect = feedback_surf.get_rect(center=(cx, panel.bottom - 30))
            self.screen.blit(feedback_surf, fb_rect)

        # Zavřít
        if self._npc_close_btn:
            self._npc_close_btn.rect.y = panel.bottom + 8
            self._npc_close_btn.draw(self.screen, mouse)

    # ===================================================================
    # STATS – overlay panel
    # ===================================================================
    def _draw_stats_overlay(self) -> None:
        # Stmívací overlay
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 165))
        self.screen.blit(dim, (0, 0))

        # Panel
        panel = pygame.Rect(SCREEN_W // 2 - 290, 50, 580, 480)
        pygame.draw.rect(self.screen, (38, 28, 52), panel, border_radius=16)
        pygame.draw.rect(self.screen, (90, 65, 110), panel, 2, border_radius=16)

        cx = SCREEN_W // 2
        p = self.player

        # Titulek
        draw_text_centered(self.screen, "Statistiky a dovednosti",
                           self.f_lg, GOLD, cx, 90)

        # --- Základní staty ---
        y = 135
        draw_text_left(self.screen, "Základní staty",
                       self.f_md, SILVER, cx - 250, y)
        y += 35

        # Útok
        draw_text_left(self.screen, f"⚔  Síla útoku:",
                       self.f_sm, TEXT_LT, cx - 240, y)
        eq_sila = p._equipment_bonus("sila")
        total_sila = p.sila + eq_sila
        atk_text = f"{p.effective_attack}"
        if total_sila > 0:
            detail = f"{p.attack} + {total_sila * 3}"
            if eq_sila > 0:
                detail += f" [výzbroj +{eq_sila * 3}]"
            atk_text += f"  ({detail})"
        draw_text_left(self.screen, atk_text,
                       self.f_sm, CORRECT_COLOR, cx + 40, y)
        y += 28

        # Obrana
        draw_text_left(self.screen, f"🛡  Síla obrany:",
                       self.f_sm, TEXT_LT, cx - 240, y)
        eq_houz = p._equipment_bonus("houzevnatost")
        total_houz = p.houzevnatost + eq_houz
        def_text = f"{p.effective_defense}"
        if total_houz > 0:
            detail = f"{p.defense} + {total_houz * 2}"
            if eq_houz > 0:
                detail += f" [výzbroj +{eq_houz * 2}]"
            def_text += f"  ({detail})"
        draw_text_left(self.screen, def_text,
                       self.f_sm, (100, 160, 220), cx + 40, y)
        y += 28

        # HP
        draw_text_left(self.screen, f"❤  Životy:",
                       self.f_sm, TEXT_LT, cx - 240, y)
        draw_text_left(self.screen, f"{p.hp}/{p.max_hp}",
                       self.f_sm, (220, 80, 80), cx + 40, y)

        # --- Oddělovač ---
        y += 38
        pygame.draw.line(self.screen, (90, 65, 110),
                         (cx - 250, y), (cx + 250, y), 1)

        # --- Dovednosti ---
        y += 12
        draw_text_left(self.screen, "Dovednosti",
                       self.f_md, SILVER, cx - 250, y)

        # Dostupné body
        pts_color = GOLD if p.skill_points > 0 else (100, 90, 120)
        draw_text_left(self.screen, f"Body: {p.skill_points}",
                       self.f_sm, pts_color, cx + 120, y + 4)

        y += 40
        mouse = pygame.mouse.get_pos()
        for i, (attr_name, label, desc) in enumerate(self.SKILL_DEFS):
            val = getattr(p, attr_name)

            # Název dovednosti
            draw_text_left(self.screen, f"{label}:",
                           self.f_sm, TEXT_LT, cx - 240, y)

            # Hodnota
            draw_text_left(self.screen, str(val),
                           self.f_sm, GOLD, cx + 50, y)

            # Popis
            draw_text_left(self.screen, f"({desc})",
                           self.f_xs, (120, 110, 140), cx + 80, y + 3)

            # + tlačítko
            btn = self._stats_skill_buttons[i]
            btn.rect.y = y - 3
            btn.enabled = p.skill_points > 0
            btn.draw(self.screen, mouse)

            y += 36

        # Zavřít
        if self._stats_close_btn:
            self._stats_close_btn.draw(self.screen, mouse)

    # ===================================================================
    # INVENTÁŘ – overlay panel
    # ===================================================================
    # Mapování stat_bonuses klíčů na čitelné české názvy
    _STAT_LABELS: dict[str, str] = {
        "sila": "Síla", "charisma": "Charisma", "moudrost": "Moudrost",
        "houzevnatost": "Houževnatost", "agility": "Agility",
    }

    def _draw_inventory_overlay(self) -> None:
        # Stmívací overlay
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 175))
        self.screen.blit(dim, (0, 0))

        # Panel (širší – výzbroj + mřížka předmětů)
        panel = pygame.Rect(80, 30, 740, 520)
        pygame.draw.rect(self.screen, (38, 28, 52), panel, border_radius=16)
        pygame.draw.rect(self.screen, (90, 65, 110), panel, 2, border_radius=16)

        cx = SCREEN_W // 2

        # Titulek + zlato
        draw_text_centered(self.screen, "Inventář",
                           self.f_lg, GOLD, cx, 60)
        draw_text_centered(self.screen, f"💰 {self.player.gold}",
                           self.f_sm, GOLD, cx, 92)

        # Svislý oddělovač
        pygame.draw.line(self.screen, (90, 65, 110),
                         (cx, 115), (cx, 510), 1)

        mouse = pygame.mouse.get_pos()

        # === LEVÁ STRANA: Výzbroj (paperdoll) ===
        ecx = 265
        draw_text_centered(self.screen, "Výzbroj",
                           self.f_md, SILVER, ecx, 120)

        slot_size = 56
        row_h = 64
        base_y = 148
        col_left   = ecx - slot_size - 4
        col_right  = ecx + 4
        col_center = ecx - slot_size // 2

        slot_positions = {
            "helma":      (col_center, base_y),
            "meč":        (col_left,   base_y + row_h),
            "štít":       (col_right,  base_y + row_h),
            "brnění":     (col_center, base_y + 2 * row_h),
            "boty":       (col_center, base_y + 3 * row_h),
            "prsten":     (col_left,   base_y + 4 * row_h),
            "náhrdelník": (col_right,  base_y + 4 * row_h),
        }

        # Uložíme rect slotů pro event handling
        self._inv_slot_rects: dict[str, pygame.Rect] = {}
        active_slot = self._inv_selected_slot  # vybraný slot (kliknutím)
        for slot_name, (sx, sy) in slot_positions.items():
            rect = pygame.Rect(sx, sy, slot_size, slot_size)
            self._inv_slot_rects[slot_name] = rect
            equipped = self.player.equipment.get(slot_name)
            is_selected = (slot_name == active_slot and equipped)

            bg = (80, 65, 30) if is_selected else (55, 45, 70) if equipped else (30, 22, 40)
            if rect.collidepoint(mouse) and equipped:
                bg = tuple(min(255, c + 20) for c in bg)

            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            border_col = GOLD if is_selected else (90, 70, 110)
            pygame.draw.rect(self.screen, border_col, rect, 2, border_radius=8)

            info = EQUIPMENT_SLOT_INFO[slot_name]
            if equipped:
                icon = equipped.get("icon", info[0])
                icon_col = WHITE
            else:
                icon = info[0]
                icon_col = (70, 60, 85)

            draw_text_centered(self.screen, icon, self.f_md,
                               icon_col, sx + slot_size // 2,
                               sy + slot_size // 2)

        # Detail vybraného slotu + tlačítko Sundat
        tooltip_y = base_y + 5 * row_h + 12
        if active_slot and self.player.equipment.get(active_slot):
            equipped = self.player.equipment[active_slot]
            info = EQUIPMENT_SLOT_INFO[active_slot]
            tip = f"{info[1]}: {equipped.get('name', '?')}"
            draw_text_centered(self.screen, tip, self.f_xs,
                               TEXT_LT, ecx, tooltip_y)
            # Bonusy nasazeného předmětu
            bonuses = equipped.get("stat_bonuses", {})
            if bonuses:
                parts = []
                for stat, val in bonuses.items():
                    label = self._STAT_LABELS.get(stat, stat)
                    parts.append(f"+{val} {label}")
                draw_text_centered(self.screen, "  ".join(parts),
                                   self.f_xs, CORRECT_COLOR,
                                   ecx, tooltip_y + 16)
            # Tlačítko Sundat
            ubtn_x = ecx - 60
            ubtn_y = tooltip_y + 32
            self._inv_unequip_btn.rect.topleft = (ubtn_x, ubtn_y)
            self._inv_unequip_btn.enabled = len(self.player.inventory) < 12
            self._inv_unequip_btn._slot = active_slot  # type: ignore[attr-defined]
            self._inv_unequip_btn.draw(self.screen, mouse)
        else:
            self._inv_unequip_btn._slot = None  # type: ignore[attr-defined]
            # Hover tooltip pro nepřiřazený slot
            for slot_name, (sx, sy) in slot_positions.items():
                rect = pygame.Rect(sx, sy, slot_size, slot_size)
                if rect.collidepoint(mouse):
                    info = EQUIPMENT_SLOT_INFO[slot_name]
                    equipped = self.player.equipment.get(slot_name)
                    if equipped:
                        tip = f"{info[1]}: {equipped.get('name', '?')}"
                    else:
                        tip = f"{info[1]}: prázdné"
                    draw_text_centered(self.screen, tip, self.f_xs,
                                       TEXT_LT, ecx, tooltip_y)
                    break

        # === PRAVÁ STRANA: Mřížka předmětů 3×4 ===
        grid_cx = 635
        draw_text_centered(self.screen, "Předměty",
                           self.f_md, SILVER, grid_cx, 120)

        cell = 56
        gap = 6
        grid_w = 3 * cell + 2 * gap
        grid_x = grid_cx - grid_w // 2
        grid_y = 155
        hovered_item_idx = -1

        # Uložíme rect předmětů pro event handling
        self._inv_item_rects: list[pygame.Rect] = []

        for row in range(4):
            for col in range(3):
                idx = row * 3 + col
                x = grid_x + col * (cell + gap)
                y = grid_y + row * (cell + gap)
                r = pygame.Rect(x, y, cell, cell)
                self._inv_item_rects.append(r)

                if idx < len(self.player.inventory):
                    item = self.player.inventory[idx]
                    is_selected = (idx == self._inv_selected_idx)
                    bg = (80, 65, 30) if is_selected else (55, 45, 70)
                    if r.collidepoint(mouse):
                        hovered_item_idx = idx
                        bg = (95, 80, 40) if is_selected else (75, 62, 90)
                    pygame.draw.rect(self.screen, bg, r, border_radius=8)
                    border_col = GOLD if is_selected else (90, 70, 110)
                    pygame.draw.rect(self.screen, border_col, r, 2,
                                     border_radius=8)
                    icon = item.get("icon", "?")
                    draw_text_centered(self.screen, icon, self.f_md,
                                       WHITE, x + cell // 2, y + cell // 2)
                else:
                    pygame.draw.rect(self.screen, (30, 22, 40), r,
                                     border_radius=8)
                    pygame.draw.rect(self.screen, (60, 48, 75), r, 1,
                                     border_radius=8)

        # Počet předmětů
        bottom_y = grid_y + 4 * (cell + gap) + 8
        count = len(self.player.inventory)
        draw_text_centered(self.screen, f"{count}/12",
                           self.f_xs, (100, 90, 120), grid_cx, bottom_y)

        # === Detail vybraného předmětu + akční tlačítka ===
        sel = self._inv_selected_idx
        if 0 <= sel < len(self.player.inventory):
            item = self.player.inventory[sel]
            name = item.get("name", "?")
            slot = item.get("slot")
            is_equippable = slot is not None and slot in self.player.equipment

            # Název předmětu
            draw_text_centered(self.screen, name, self.f_sm,
                               GOLD, grid_cx, bottom_y + 20)

            # Bonusy předmětu
            bonuses = item.get("stat_bonuses", {})
            if bonuses:
                parts = []
                for stat, val in bonuses.items():
                    label = self._STAT_LABELS.get(stat, stat)
                    parts.append(f"+{val} {label}")
                draw_text_centered(self.screen, "  ".join(parts),
                                   self.f_xs, CORRECT_COLOR,
                                   grid_cx, bottom_y + 40)

            # Porovnání se stávající výzbrojí (stat diff)
            if is_equippable:
                current_equipped = self.player.equipment.get(slot)
                old_bonuses = current_equipped.get("stat_bonuses", {}) if current_equipped else {}
                new_bonuses = bonuses
                # Spočítej rozdíly
                all_stats = set(list(old_bonuses.keys()) + list(new_bonuses.keys()))
                diff_parts = []
                for stat in sorted(all_stats):
                    old_val = old_bonuses.get(stat, 0)
                    new_val = new_bonuses.get(stat, 0)
                    diff = new_val - old_val
                    if diff != 0:
                        label = self._STAT_LABELS.get(stat, stat)
                        sign = "+" if diff > 0 else ""
                        col = CORRECT_COLOR if diff > 0 else WRONG_COLOR
                        diff_parts.append((f"{sign}{diff} {label}", col))

                if diff_parts:
                    dx = grid_cx - sum(self.f_xs.size(t)[0] for t, _ in diff_parts) // 2
                    dy = bottom_y + 56
                    for text, col in diff_parts:
                        draw_text_left(self.screen, text, self.f_xs, col, dx, dy)
                        dx += self.f_xs.size(text)[0] + 10
                elif current_equipped:
                    draw_text_centered(self.screen, "(beze změny)",
                                       self.f_xs, (100, 90, 120),
                                       grid_cx, bottom_y + 56)

            # Tlačítka Vyzbrojit / Zahodit
            btn_y = bottom_y + 74
            if is_equippable:
                self._inv_equip_btn.rect.topleft = (grid_cx - 125, btn_y)
                self._inv_equip_btn.draw(self.screen, mouse)
                self._inv_discard_btn.rect.topleft = (grid_cx + 15, btn_y)
                self._inv_discard_btn.draw(self.screen, mouse)
            else:
                self._inv_discard_btn.rect.topleft = (grid_cx - 50, btn_y)
                self._inv_discard_btn.draw(self.screen, mouse)
        elif 0 <= hovered_item_idx < len(self.player.inventory):
            # Jen hover – zobraz název
            hname = self.player.inventory[hovered_item_idx].get("name", "?")
            draw_text_centered(self.screen, hname, self.f_xs,
                               TEXT_LT, grid_cx, bottom_y + 18)

        # Zavřít
        self._inv_close_btn.draw(self.screen, mouse)

    # ===================================================================
    # LOOT – overlay po zabití nepřítele
    # ===================================================================
    def _draw_loot_overlay(self) -> None:
        # Stmívací overlay
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_W // 2

        # Panel (výška závisí na počtu předmětů)
        item_count = len(self._loot_items)
        panel_h = 310 + item_count * 40
        panel = pygame.Rect(cx - 270, 80, 540, panel_h)
        pygame.draw.rect(self.screen, (38, 28, 52), panel, border_radius=16)
        pygame.draw.rect(self.screen, (90, 65, 110), panel, 2, border_radius=16)

        # Titulek
        draw_text_centered(self.screen, f"Kořist z {self.enemy.name}",
                           self.f_lg, GOLD, cx, 118)

        # Zlato
        y = 165
        draw_text_centered(self.screen, f"💰  {self._loot_gold} zlaťáků",
                           self.f_md, GOLD, cx, y)

        # Oddělovač
        y += 35
        pygame.draw.line(self.screen, (90, 65, 110),
                         (cx - 220, y), (cx + 220, y), 1)

        # Předměty s checkboxy
        y += 18
        draw_text_centered(self.screen, "Předměty (klikni pro označení):",
                           self.f_sm, SILVER, cx, y)
        y += 32
        self._loot_item_rects = []
        mouse = pygame.mouse.get_pos()
        for i, item in enumerate(self._loot_items):
            icon = item.get("icon", "?")
            name = item.get("name", "Neznámý")
            bonuses = item.get("stat_bonuses", {})
            selected = i < len(self._loot_selected) and self._loot_selected[i]

            # Klikatelný řádek
            row_rect = pygame.Rect(cx - 240, y - 15, 480, 34)
            self._loot_item_rects.append(row_rect)

            # Zvýraznění při hoveru
            if row_rect.collidepoint(mouse):
                pygame.draw.rect(self.screen, (55, 42, 70), row_rect,
                                 border_radius=6)

            # Checkbox
            cb_rect = pygame.Rect(cx - 230, y - 11, 22, 22)
            cb_bg = (60, 100, 60) if selected else (50, 40, 65)
            pygame.draw.rect(self.screen, cb_bg, cb_rect, border_radius=4)
            pygame.draw.rect(self.screen, (110, 90, 140), cb_rect, 2,
                             border_radius=4)
            if selected:
                draw_text_centered(self.screen, "✓", self.f_sm,
                                   CORRECT_COLOR, cb_rect.centerx,
                                   cb_rect.centery)

            # Název předmětu
            text = f"{icon}  {name}"
            text_col = WHITE if selected else TEXT_LT
            draw_text_left(self.screen, text, self.f_sm, text_col,
                           cx - 198, y - 8)

            # Bonusy výzbroje
            if bonuses:
                parts = [f"+{v} {self._STAT_LABELS.get(k, k)}"
                         for k, v in bonuses.items()]
                draw_text_left(self.screen, "  ".join(parts),
                               self.f_xs, GOLD, cx + 130, y - 5)

            y += 38

        # XP info
        y += 10
        draw_text_centered(self.screen, f"+{self.enemy.xp_reward} XP",
                           self.f_sm, CORRECT_COLOR, cx, y)

        if self._level_up_flag:
            y += 25
            draw_text_centered(self.screen,
                               f"⬆  LEVEL UP!  Nyní Lv.{self.player.level}",
                               self.f_sm, GOLD, cx, y)

        # Tlačítka – Sebrat (vybrané) + Sebrat vše
        btn_y = panel.bottom - 60
        self._loot_collect_selected_btn.rect.y = btn_y
        self._loot_collect_selected_btn.enabled = any(self._loot_selected)
        self._loot_collect_selected_btn.draw(self.screen, mouse)

        self._loot_collect_btn.rect.y = btn_y
        self._loot_collect_btn.draw(self.screen, mouse)

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

        # Inventář tlačítko
        mouse = pygame.mouse.get_pos()
        self.btn_inventory.draw(self.screen, mouse)
        draw_text_left(self.screen, f"💰 {self.player.gold}",
                       self.f_xs, (80, 55, 30), SCREEN_W - 320, 56)

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
        if self.phase == Phase.LOOT:
            self._draw_loot_overlay()
        elif self.phase == Phase.CAVE_CHOICE:
            self._draw_cave_choice_overlay()
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

        # Inventář tlačítko v bitvě (pod nepřítelem)
        mouse = pygame.mouse.get_pos()
        self.btn_inventory.draw(self.screen, mouse)
        draw_text_left(self.screen, f"💰 {self.player.gold}",
                       self.f_xs, GOLD, SCREEN_W - 320, 56)

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
            self.btn_flee.draw(self.screen, mouse)

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
                            Phase.RESOLVE_ENEMY, Phase.FLEE_RESOLVE):
            draw_text_centered(self.screen, "…", self.f_md,
                               (90, 80, 110), cx, h - 65)

    def _draw_battle_log(self) -> None:
        y = 85
        for msg in self.battle_log[-3:]:
            draw_text_left(self.screen, msg, self.f_xs,
                           (135, 125, 155), 30, y)
            y += 18

    def _draw_cave_choice_overlay(self) -> None:
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
                           "Chceš pokračovat v průzkumu jeskyně?",
                           self.f_sm, TEXT_LT, cx, cy + 175)
        mouse = pygame.mouse.get_pos()
        self.btn_cave_continue.rect.y = cy + 210
        self.btn_cave_leave.rect.y = cy + 210
        self.btn_cave_continue.draw(self.screen, mouse)
        self.btn_cave_leave.draw(self.screen, mouse)

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

# CLAUDE.md

## Project Overview

**Deutsch Klicker -- Battle Edition** is a German language learning game built with Python and Pygame. Players learn German vocabulary (translated to Czech) through a turn-based battle RPG where correctly translating words deals damage to enemies. Features equipment management, skill progression, quest system, and save/load persistence.

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: Pygame 2.5+
- **No external dependencies** beyond pygame

## Repository Structure

```
test-repository-claude-german-learning-clicker-game-vP2vy v3/
  test-repository-claude-german-learning-clicker-game-vP2vy/
    german_clicker/          # Main game package
      main.py                # Entry point (26 lines)
      game.py                # Core game logic, state machine, rendering (~2360 lines)
      ui.py                  # UI components: Button, HealthBar, TextInput, MessageOverlay (282 lines)
      words.py               # German-Czech vocabulary database, 7 categories, ~71 word pairs (97 lines)
    src/                     # Java learning examples (unrelated to main game)
    requirements.txt
    README.md                # Documentation in Czech
```

## How to Run

```bash
pip install -r "test-repository-claude-german-learning-clicker-game-vP2vy v3/test-repository-claude-german-learning-clicker-game-vP2vy/requirements.txt"
python "test-repository-claude-german-learning-clicker-game-vP2vy v3/test-repository-claude-german-learning-clicker-game-vP2vy/german_clicker/main.py"
```

## Architecture

- **State machine**: `game.py` uses a `Phase` enum with 18 states: MENU, CAMP, CAMP_NPC, CASTLE, CASTLE_NPC, STATS, INVENTORY, MAP, PLAYER_CHOOSE, PLAYER_TRANSLATE, RESOLVE_PLAYER, ENEMY_TURN, RESOLVE_ENEMY, LOOT, CAVE_CHOICE, FLEE_RESOLVE, VICTORY, GAME_OVER
- **Game loop**: Standard Pygame loop -- event handling, update, draw at 60 FPS
- **Sprite system**: Procedural pixel art rendered from ASCII grids with color maps (no external image assets)
- **Translation validation**: Normalizes German umlauts (ae->ä, oe->ö, ue->ü, ss->ß) and strips articles (der/die/das/ein/eine)
- **Save/load**: JSON persistence (`savegame.json`) for player stats, equipment, inventory, quest progress, enemy index

## Key Classes

- `Game` (~2360 lines) -- Main controller managing all game state, input, and rendering
- `Player` -- `@dataclass` with HP, attack, defense, XP, level, 5 skills (sila, charisma, moudrost, houzevnatost, agility), gold, inventory (list, max 12), equipment (7 named slots), and `effective_attack`/`effective_defense` properties that include equipment bonuses
- `Enemy` -- `@dataclass` with HP, attack, XP reward, loot table
- `Phase` -- Enum with 16 game states
- `Button`, `HealthBar`, `TextInput`, `MessageOverlay` -- UI components in `ui.py`

## Code Conventions

- Private methods/variables prefixed with `_`
- snake_case for functions/variables, CamelCase for classes
- Comments and variable names are in Czech
- Type hints used throughout (Python 3.9+ style)
- `@dataclass` for data containers, `Enum` for game phases
- Items are plain dicts: `{"name": str, "icon": str, "slot": str, "stat_bonuses": dict}`

## Testing

No test suite or linting configuration exists. There is no CI/CD pipeline. Use `python -c "import ast; ast.parse(open('game.py').read())"` to verify syntax.

## Game Mechanics

- **Combat**: 5 enemies fought in sequence: Šnek (Snail), Pavouk (Spider), Ještěrka (Lizard), Netopýr (Bat), Drak (Dragon)
- **Battle actions**: Attack (translate word), Defend (reduce damage), Flee (50% escape chance, risk of taking damage)
- **Cave choice**: After defeating an enemy and collecting loot, player chooses to continue fighting or return to camp
- **Locations**: Base camp (always accessible), Castle/Hrad (unlocks at level 3) -- both share same NPC set
- **NPC camp**: Merchant (healing), Blacksmith (upgrades), Mayor (quests), Inn (save for 10 gold)
- **Equipment system**: 7 slots (helma, meč, štít, brnění, boty, prsten, náhrdelník) with stat bonuses applied only when worn
- **Skill system**: 5 skills (síla, charisma, moudrost, houževnatost, agility) with allocatable skill points on level up; síla adds +3 attack, houževnatost adds +2 defense
- **Inventory**: Max 12 items, equip/unequip/discard with stat comparison display
- **Quest system**: 3 quests from mayor NPC with kill/collect objectives and rewards
- **Loot**: Each enemy drops themed equipment with stat_bonuses dicts (e.g. `{"sila": 1}`)
- **XP-based leveling**: `xp_to_next = level * 80`
- **Vocabulary**: 7 categories (Numbers, Colors, Animals, Food, Days, Phrases, Family) -- ~71 German-Czech word pairs

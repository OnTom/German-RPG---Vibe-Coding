# CLAUDE.md

## Project Overview

**Deutsch Klicker -- Battle Edition** is a German language learning game built with Python and Pygame. Players learn German vocabulary (translated to Czech) through a turn-based battle RPG where correctly translating words deals damage to enemies.

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: Pygame 2.5+
- **No external dependencies** beyond pygame

## Repository Structure

```
test-repository-claude-german-learning-clicker-game-vP2vy v3/
  test-repository-claude-german-learning-clicker-game-vP2vy/
    german_clicker/          # Main game package
      main.py                # Entry point
      game.py                # Core game logic, state machine, rendering (~1160 lines)
      ui.py                  # UI components (Button, HealthBar, TextInput, MessageOverlay)
      words.py               # German-Czech vocabulary database (7 categories, ~70 word pairs)
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

- **State machine**: `game.py` uses a `Phase` enum with 10+ states (MENU, CAMP, MAP, PLAYER_TRANSLATE, ENEMY_TURN, VICTORY, GAME_OVER, etc.)
- **Game loop**: Standard Pygame loop -- event handling, update, draw at 60 FPS
- **Sprite system**: Procedural pixel art rendered from ASCII grids with color maps (no external image assets)
- **Translation validation**: Normalizes German umlauts (ae->ä, oe->ö, ue->ü, ss->ß) and strips articles (der/die/das/ein/eine)

## Key Classes

- `Game` -- Main controller managing all game state, input, and rendering
- `Player` / `Enemy` -- `@dataclass` entities with HP, attack, XP, level stats
- `Button`, `HealthBar`, `TextInput`, `MessageOverlay` -- UI components in `ui.py`

## Code Conventions

- Private methods/variables prefixed with `_`
- snake_case for functions/variables, CamelCase for classes
- Comments and variable names are in Czech
- Type hints used throughout (Python 3.9+ style)
- `@dataclass` for data containers, `Enum` for game phases

## Testing

No test suite or linting configuration exists. There is no CI/CD pipeline.

## Game Mechanics

- 5 enemies fought in sequence: Snail, Spider, Lizard, Bat, Dragon
- NPC camp with merchant (healing), blacksmith (upgrades), mayor (quests)
- XP-based leveling system
- 7 vocabulary categories: Numbers, Colors, Animals, Food, Days, Phrases, Family

"""
Deutsch Klicker – vstupní bod aplikace.

Spuštění:
    python main.py

Požadavky:
    pip install pygame
"""

import sys
import os

# Přidej adresář hry do cesty, aby šlo spouštět i z rodiče
sys.path.insert(0, os.path.dirname(__file__))

from game import Game


def main() -> None:
    game = Game()
    game.run()


if __name__ == "__main__":
    main()

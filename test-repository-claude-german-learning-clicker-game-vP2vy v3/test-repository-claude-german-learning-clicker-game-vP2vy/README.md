# Deutsch Klicker 🇩🇪

Klikačka pro učení německých slov s českými překlady. Naprogramováno v Pythonu s pomocí knihovny Pygame.

## Jak hrát

1. Spusť hru: `python german_clicker/main.py`
2. Na obrazovce se zobrazí německé slovo
3. Klikni na správný český překlad ze 4 možností
4. Sbírej body, postupuj na vyšší úrovně a odemykej nové kategorie slov
5. Máš 3 životy — špatná odpověď nebo vypršení času odebere jeden

## Herní mechaniky

| Prvek | Popis |
|---|---|
| Otázky | Německé slovo → 4 možné české překlady |
| Čas | Každá otázka má časový limit (zkracuje se s úrovní) |
| Životy | 3 životy; ztráta za špatnou odpověď nebo vypršení času |
| Body | 10 + bonus za rychlost odpovědi |
| Level-up | Každých 100 bodů postoupíš na vyšší úroveň |
| Kategorie | Čísla → Barvy → Zvířata → Jídlo → Dny → Fráze → Rodina |

## Instalace

```bash
pip install -r requirements.txt
python german_clicker/main.py
```

## Struktura projektu

```
german_clicker/
├── main.py     # Vstupní bod
├── game.py     # Herní logika, stavy (menu / hra / level-up / game over)
├── words.py    # Databáze německo-českých slov podle kategorií
└── ui.py       # UI komponenty: tlačítka, timer, skóre, životy
```

## Požadavky

- Python 3.11+
- pygame 2.5+

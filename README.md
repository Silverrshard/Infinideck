I WILL BE ADDING MORE AND CHANGING THE PROGRAMING LANGUAGE WHEN IT IS GOOD ENOUGH TO BE OUT OF BETA



# Infinideck

An endless card game about huge numbers. Pull cards from a deck that never runs out, earn chips, stack wild modifiers, and grow your chip count from a handful to numbers with millions of digits.

Made with Python and pygame.

## How to play it

0. If you have blender already installed you can open the file location, go to the folder with the name of whatever version your using, then open the folders python, bin, then drag and drop infinideck onto python.exe
1. Install **Python 3.11 or newer** from [python.org](https://www.python.org/downloads/). When installing on Windows, tick **"Add Python to PATH"**.
2. Install pygame. Open a terminal (Command Prompt or PowerShell) and run:
   ```
   pip install pygame
   ```
3. Download the game, **AS A .ZIP** then unzip it, and keep every file together in the `infinideck` folder.
4. Double-click `infinideck.py`, or run this in the folder:
   ```
   python infinideck.py
   ```

`infinideck.py` is the game. The other files (`_art.py`, `_cards.py` and so on) and the `assets` folder are parts of it, so it won't start without them.

## Controls

| Action | How |
|---|---|
| Pull a card | Click the deck, or hold **Space** |
| Open the menu | The button in the top left, or **Esc** |
| Fullscreen on or off | **Alt+Enter**, or the button in the menu |
| Sound on or off | **M**, or the button in the menu |
| Skill tree | Drag to move around, scroll to zoom, click an upgrade to buy it |
| See what a card or upgrade does | Hover over it |

## What's in it

- **Cards and modifiers:** every card pays chips (2 to 10 pay their number, J, Q and K pay 10, Aces pay 11). Cards can roll 30 buffs and 30 debuffs that stack, and every modified card shows how rare it is, like "1 in 4,000".
- **The Skill Tree:** three tabs of upgrades.
  - **Main:** 550 upgrades in 10 paths.
  - **Decks:** 10 card backs, each with its own permanent bonuses.
  - **Transcend:** 144 upgrades bought with Transcendent Points.

  Hover any upgrade to see exactly what it does, with your numbers now and after buying it.
- **Transcending:** reset your run for Transcendent Points, which boost every run after.
- **Perks:** 100 perks with unusual rules. Get them by Shattering: give up a fully maxed-out skill tree for one random perk.
- **Achievements:** 80 normal and 20 secret.
- **Index, Deck and Stats pages:** see every card you've found, duplicate, rank up or delete cards in your deck, and track your records.
- **5 save profiles.** The game saves every 6 minutes, when you quit, and recovers if it closes in the middle of a save.

## Where your saves go

Saves are kept on your computer, not in the game folder:

- **Windows:** `%APPDATA%\Infinideck`

To start completely fresh, delete that folder, or use the **Delete** button on a profile.

## Problems?

- **"No module named pygame":** run `pip install pygame` again. If you have more than one Python installed, try `python -m pip install pygame`.
- **It closes straight away:** run it from a terminal with `python infinideck.py` to see the error message.
- **The window is too big or small:** press **Alt+Enter** to switch between fullscreen and a window.

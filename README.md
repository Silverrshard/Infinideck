# Infinideck

An endless card game about huge numbers. Pull cards from a deck that never runs out, earn chips, stack wild modifiers, and grow your chip count from a handful to numbers with millions of digits.

Made with Python and pygame.

## How to play it

1. Install **Python 3.11 or newer** from [python.org](https://www.python.org/downloads/). When installing on Windows, tick **"Add Python to PATH"**.
2. Install pygame. Open a terminal (Command Prompt or PowerShell) and run:
   ```
   pip install pygame
   ```
3. Download the game, unzip it, and keep everything together in the `infinideck` folder.
4. Double-click `infinideck.py`, or run this in the folder:
   ```
   python infinideck.py
   ```

`infinideck.py` is the game. Everything else lives in the `assets` folder, and the game won't start without it:

| Folder | What's in it |
|---|---|
| `assets\Core` | The rest of the game's code |
| `assets\Images` | The 3D-rendered chips, crystals and medals |
| `assets\Particles` | Over 60 particle sprites (flames, coins, sparkles, shards, smoke...) |
| `assets\Achievements` | One icon for every achievement |
| `assets\Developers` | The developers' profile pictures |
| `assets\Music` | 5 original background tracks |
| `assets\Sound effects` | Every sound in the game |
| `assets\Saves` | Your saves |

## Controls

| Action | How |
|---|---|
| Pull a card | Click the deck, or hold **Space** |
| Open the menu | The button in the top left, or **Esc** |
| Fullscreen on or off | **Alt+Enter**, or Settings |
| Sound on or off | **M**, or Settings |
| Skill tree | Drag to move around, scroll to zoom, click an upgrade to buy it |
| See what a card, modifier or upgrade does | Hover over it |

## What's in it

- **Cards and modifiers:** every card pays chips (2 to 10 pay their number, J, Q and K pay 10, Aces pay 11). Cards can roll 30 buffs and 30 debuffs that stack. Each one has its own animated look and particles, and every modified card shows how rare it is, like "1 in 4,000".
- **The Skill Tree:** three tabs of upgrades.
  - **Main:** 550 upgrades in 10 paths.
  - **Decks:** 10 card backs, each with its own permanent bonuses.
  - **Transcend:** 146 upgrades bought with Transcendent Points, including **Buy All** buttons.

  Hover any upgrade to see exactly what it does, with your numbers now and after buying it.
- **Transcending:** reset your run for Transcendent Points, which boost every run after.
- **Perks:** 100 perks with unusual rules. Get them by Shattering: give up a fully maxed-out skill tree for one random perk.
- **Achievements:** 171 normal and 20 secret, each with its own icon, and a search box.
- **Index:** every card you've found, plus your recent, rarest and biggest-paying cards.
- **Settings:** sound and music volume, choose a track, fullscreen, particle amount, and Discord Rich Presence.
- **5 save profiles.** The game saves every 6 minutes, when you quit, and recovers if it closes in the middle of a save.

## Saves

Saves are `.dat` files in `assets\Saves`, inside the game folder. To move your progress to another copy or a newer version of the game, copy the files from its `assets\Saves` folder. Every version can read older saves.

Saves from the first version (in `%APPDATA%\Infinideck`) are copied over automatically the first time you start this one.

To start completely fresh, use the **Delete** button on a profile.

## Discord Rich Presence

The game shows "Playing Infinideck", the page you're on and your chips on your Discord profile. It's on by default and can be switched off in **Settings**. The Discord desktop app has to be open on the same PC.

## Problems?

- **"No module named pygame":** run `pip install pygame` again. If you have more than one Python installed, try `python -m pip install pygame`.
- **It closes straight away:** run it from a terminal with `python infinideck.py` to see the error message.
- **The window is too big or small:** press **Alt+Enter** to switch between fullscreen and a window.
- **It runs slowly:** set **Particles** to **Low** in Settings.

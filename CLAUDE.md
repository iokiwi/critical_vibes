# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the game

```bash
uv run main.py
```

There are no tests, no linter config, and no build step. The entire game is `main.py`.

## Architecture

Everything lives in `main.py`. The structure is:

- **Constants** — grid size, animation timing, colours, player config at the top. Tweak these to change game feel.
- **`Cell`** — owns a `count` and `owner` (player index or `None`).
- **`WaveAnim`** — snapshot of one explosion wave (all cells firing simultaneously), tracks animation progress through three phases: fireball (0–30%), bombs travel (30–70%), board update + fireball fade (70–100%).
- **`GameState`** — all game logic: placement validation, wave collection, board mutation, elimination, turn advancement. The key methods are `place()` (player click) and `update()` (called every frame to drive animation state).
- **`main()`** — pygame event loop, sprite pre-rendering, calls `state.update()` and draw functions each frame.
- **Draw functions** — `draw_grid()` renders the board and delegates to `draw_bombs()`. Animation overlays (fireballs, travelling bombs) are drawn on top in `draw_grid()` using `state.current_anim`.

## Key game rules (as implemented)

- Threshold per cell = number of orthogonal neighbors (corners=2, edges=3, interior=4).
- All cells at/above threshold explode **simultaneously** as a wave.
- Incoming bombs stack (`count += 1`) and convert the cell to the exploding player's color.
- Remainder after explosion: `count = count % threshold` stays in the cell.
- Chain reaction stops early if only one player's color remains on the board.
- Turn advances immediately on click (cursor flips color), even before animation finishes.
- A player is safe from elimination until they've placed their first bomb.

## Assets

Stored in `assets/`:

- `bomb.svg` — CC BY 3.0 by Lorc via game-icons.net. Loaded with `pygame.image.load_sized_svg()` (pygame-ce only) and tinted per player using `BLEND_RGBA_MULT`.
- `explosion.wav` — sound played once per wave.

# Critical Mass — Rules

## Overview

Critical Mass is a turn-based strategy game for 2 players played on a 5×5 grid. Players place colored bombs on the board and trigger chain explosions to eliminate their opponent. The last player with bombs on the board wins.

## Setup

- The board is 5×5 and starts with 5 bombs randomly placed for each player (1 bomb per cell, no shared cells).
- Players are Red and Blue.
- Red goes first.

## Turn Structure

On your turn, click a valid cell to place one bomb of your color.

**Valid placements:**
- An empty cell
- A cell that already contains one or more of **your own** bombs

You may not place on a cell occupied by the other player's bombs.

Input is locked while an explosion animation is playing.

## Critical Mass Threshold

Each cell has a threshold equal to its number of orthogonal neighbors:

| Position | Neighbors | Threshold |
|----------|-----------|-----------|
| Corner   | 2         | 2         |
| Edge     | 3         | 3         |
| Interior | 4         | 4         |

Corner and edge cells show their threshold number in the top-left corner of the cell.

## Explosions

When any cell reaches or exceeds its threshold, it explodes. **All cells at or above threshold explode simultaneously as a wave.**

When a cell explodes:
1. A fireball appears on the exploding cell.
2. One bomb of the exploding player's color flies to each orthogonal neighbor.
3. Each neighbor absorbs the incoming bomb — its count increases and its color changes to the exploding player's color.
4. The fireball fades out.

**Remainder rule:** if a cell has more bombs than its threshold (e.g. 5 bombs in an interior cell), it keeps the remainder after exploding (`count mod threshold`). Any remainder bombs stay in the cell under the exploding player's color.

**Wave propagation:** after each wave settles, if any cells are again at or above threshold, another wave fires. This continues until no cells are overloaded — **unless** the chain reaction has already wiped out the opponent, in which case propagation stops immediately.

## Claiming Territory

When a bomb arrives in a neighbor cell, that cell's entire contents become the exploding player's color. The count increases by 1 (the incoming bomb stacks on top of existing bombs).

## Elimination & Winning

- A player is eliminated when they have no bombs left on the board, **provided** they have already placed at least one bomb during the game (grace period: a player cannot be eliminated before their first turn).
- The last player with bombs on the board wins.
- A win screen is shown; click anywhere to start a new game.

## Turn Handoff

The cursor switches to the next player's color as soon as a placement is made, even while an explosion animation is still playing.

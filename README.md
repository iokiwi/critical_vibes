# Critical Mass

A two-player bomb strategy game built entirely by vibecoding at the Christchurch Python Meetup, May 2026.

No code was written by hand. The rules, the game logic, the animations, and this README were all produced through a live conversation with Claude Code.

## How to play

```
uv run main.py
```

Red and Blue take turns clicking cells to place bombs. Fill a cell past its threshold and it explodes, sending bombs into adjacent cells and converting them to your colour. Last player standing wins.

See `rules.md` for the full rules.

## Requirements

- Python 3.14+
- [uv](https://github.com/astral-sh/uv)
- pygame-ce (installed automatically via uv)

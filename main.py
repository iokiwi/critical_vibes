import pygame
import sys
import os
import random
import math
import numpy as np
from collections import defaultdict

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
EXPLOSION_SOUND = os.path.join(ASSETS, "explosion.wav")

HEADER_H = 50
WINDOW_W = 600
WINDOW_H = 600 + HEADER_H
GRID_SIZE = 5
CELL_SIZE = 600 // GRID_SIZE

EXPLOSION_MS = 1500
PHASE_TRAVEL = 0.30
PHASE_BOARD  = 0.70
PHASE_DONE   = 1.0

BG_COLOR    = (18, 18, 24)
GRID_COLOR  = (60, 60, 75)
TEXT_COLOR  = (230, 230, 240)
HOVER_COLOR = (60, 60, 80)

PLAYER_COLORS = [
    (160, 50, 220),
    (50, 200, 80),
]
PLAYER_NAMES = ["Purple", "Green"]
NUM_PLAYERS = 2

ORB_RADIUS      = int(CELL_SIZE * 0.07)
ORB_GLOW_RADIUS = int(CELL_SIZE * 0.40)
ORB_ORBIT       = int(CELL_SIZE * 0.22)   # orbit radius for multi-orb cells
ORB_SOLO_ORBIT  = int(CELL_SIZE * 0.10)   # gentle drift for single orb
ORBIT_SPEED     = 1.2   # radians/sec
PULSE_SPEED     = 2.5   # radians/sec


def threshold(row, col):
    edges = (row == 0 or row == GRID_SIZE - 1) + (col == 0 or col == GRID_SIZE - 1)
    return 4 - edges


def neighbors(row, col):
    result = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        r, c = row + dr, col + dc
        if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
            result.append((r, c))
    return result


def cell_center(row, col):
    return (col * CELL_SIZE + CELL_SIZE // 2, HEADER_H + row * CELL_SIZE + CELL_SIZE // 2)


def make_glow_surface(color, radius):
    """Pre-compute a radial gradient glow surface using numpy. Brightest at center, zero at edge."""
    size = radius * 2 + 1
    # ogrid gives (row, col) == (y, x); surfarray uses (x, y) == (col, row)
    y, x = np.ogrid[:size, :size]
    dist = np.sqrt((x - radius) ** 2 + (y - radius) ** 2)
    # Sharp core with a soft halo: mix a tight gaussian with a wide low glow
    tight = np.exp(-(dist ** 2) / (radius * 0.15) ** 2)
    halo  = np.exp(-(dist ** 2) / (radius * 0.55) ** 2) * 0.25
    intensity = np.clip(tight + halo, 0.0, 1.0)
    intensity_t = intensity.T  # (x, y) order for surfarray

    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(surf)       # (w, h, 3)
    alpha = pygame.surfarray.pixels_alpha(surf) # (w, h)
    rgb[:, :, 0] = (color[0] * intensity_t).astype(np.uint8)
    rgb[:, :, 1] = (color[1] * intensity_t).astype(np.uint8)
    rgb[:, :, 2] = (color[2] * intensity_t).astype(np.uint8)
    alpha[:, :] = (255 * intensity_t).astype(np.uint8)
    del rgb, alpha  # release pixel locks
    return surf


# Cache glow surfaces per (color, radius) so we don't recompute each frame
_glow_cache: dict = {}

def get_glow(color, radius):
    key = (color, radius)
    if key not in _glow_cache:
        _glow_cache[key] = make_glow_surface(color, radius)
    return _glow_cache[key]


def draw_orb(screen, cx, cy, color, t_sec, phase_offset=0.0, pulse=True, alpha=255):
    """Draw a single glowing energy orb: tiny bright core, smooth radial gradient glow."""
    pulse_val = (math.sin(t_sec * PULSE_SPEED + phase_offset) + 1) / 2  # 0..1
    glow_r = int(ORB_GLOW_RADIUS * (0.85 + 0.15 * pulse_val)) if pulse else ORB_GLOW_RADIUS

    glow = get_glow(color, glow_r)
    if alpha < 255:
        glow = glow.copy()
        glow.set_alpha(alpha)
    screen.blit(glow, (cx - glow_r, cy - glow_r), special_flags=pygame.BLEND_RGBA_ADD)


def draw_orbs(screen, cx, cy, color, count, t_sec):
    """Draw `count` orbs orbiting (cx, cy)."""
    count = min(count, 4)
    if count == 1:
        ox = cx + int(ORB_SOLO_ORBIT * math.cos(t_sec * ORBIT_SPEED))
        oy = cy + int(ORB_SOLO_ORBIT * math.sin(t_sec * ORBIT_SPEED))
        draw_orb(screen, ox, oy, color, t_sec, phase_offset=0.0)
    else:
        angle_step = (2 * math.pi) / count
        for i in range(count):
            angle = t_sec * ORBIT_SPEED + i * angle_step
            ox = cx + int(ORB_ORBIT * math.cos(angle))
            oy = cy + int(ORB_ORBIT * math.sin(angle))
            draw_orb(screen, ox, oy, color, t_sec, phase_offset=i * angle_step)


def draw_cursor_orb(screen, cx, cy, color, t_sec):
    """Cursor orb — same style as board orbs, slightly larger."""
    draw_orb(screen, cx, cy, color, t_sec, phase_offset=0.0, pulse=True)


def draw_explosion_fireball(screen, cx, cy, t_sec, alpha=255):
    """Expanding fiery burst for exploding cells."""
    max_r = int(CELL_SIZE * 0.55)
    pulse = (math.sin(t_sec * 18) + 1) / 2
    r = int(max_r * (0.85 + 0.15 * pulse))
    surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
    c = r + 1
    for i in range(r, 0, -1):
        frac = i / r
        green = int(180 * (1 - frac) + 60 * frac)
        a = int(alpha * 0.9 * (1 - frac * 0.7))
        pygame.draw.circle(surf, (255, green, 0, a), (c, c), i)
    pygame.draw.circle(surf, (255, 255, 200, int(alpha * 0.95)), (c, c), r // 3)
    screen.blit(surf, (cx - c, cy - c), special_flags=pygame.BLEND_RGBA_ADD)


class Cell:
    def __init__(self):
        self.owner = None
        self.count = 0

    def reset(self):
        self.owner = None
        self.count = 0


class WaveAnim:
    def __init__(self, explosions, start_ms):
        self.explosions = explosions
        self.start_ms = start_ms
        self.board_updated = False

    def progress(self, now_ms):
        return min((now_ms - self.start_ms) / EXPLOSION_MS, 1.0)

    def done(self, now_ms):
        return self.progress(now_ms) >= PHASE_DONE


class GameState:
    def __init__(self):
        self.grid = [[Cell() for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.current_player = 0
        self.has_placed = [False] * NUM_PLAYERS
        self.eliminated = [False] * NUM_PLAYERS
        self.winner = None
        self.pending_wave = False
        self.current_anim = None
        self._preseed(5)

    def _preseed(self, count):
        all_cells = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
        for player in range(NUM_PLAYERS):
            placed = 0
            for r, c in random.sample(all_cells, len(all_cells)):
                if placed >= count:
                    break
                if self.grid[r][c].owner is None:
                    self.grid[r][c].owner = player
                    self.grid[r][c].count = 1
                    placed += 1

    @property
    def animating(self):
        return self.current_anim is not None or self.pending_wave

    def can_place(self, row, col):
        cell = self.grid[row][col]
        return cell.owner is None or cell.owner == self.current_player

    def place(self, row, col):
        if not self.can_place(row, col):
            return
        cell = self.grid[row][col]
        cell.owner = self.current_player
        cell.count += 1
        self.has_placed[self.current_player] = True
        self._advance_turn()
        if cell.count >= threshold(row, col):
            self.pending_wave = True

    def _collect_wave(self):
        explosions = []
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                cell = self.grid[r][c]
                if cell.count >= threshold(r, c):
                    explosions.append((r, c, cell.owner, neighbors(r, c)))
        return explosions

    def update(self, now_ms, sound):
        if self.current_anim is None:
            if not self.pending_wave:
                return
            explosions = self._collect_wave()
            if not explosions:
                self.pending_wave = False
                self._check_elimination()
                return
            self.pending_wave = False
            self.current_anim = WaveAnim(explosions, now_ms)
            sound.play()
            for r, c, player, nbrs in explosions:
                cell = self.grid[r][c]
                t = threshold(r, c)
                cell.count = cell.count % t
                if cell.count == 0:
                    cell.owner = None
            return

        p = self.current_anim.progress(now_ms)

        if p >= PHASE_BOARD and not self.current_anim.board_updated:
            self.current_anim.board_updated = True
            incoming = defaultdict(lambda: [None, 0])
            for r, c, player, nbrs in self.current_anim.explosions:
                for nr, nc in nbrs:
                    incoming[(nr, nc)][0] = player
                    incoming[(nr, nc)][1] += 1
            for (nr, nc), (player, count) in incoming.items():
                ncell = self.grid[nr][nc]
                ncell.owner = player
                ncell.count += count
            if self._has_overloaded_cells() and self._enemy_still_present():
                self.pending_wave = True

        if self.current_anim.done(now_ms):
            self.current_anim = None
            if not self.pending_wave:
                self._check_elimination()

    def _has_overloaded_cells(self):
        return any(
            self.grid[r][c].count >= threshold(r, c)
            for r in range(GRID_SIZE) for c in range(GRID_SIZE)
        )

    def _enemy_still_present(self):
        owners = {
            self.grid[r][c].owner
            for r in range(GRID_SIZE) for c in range(GRID_SIZE)
            if self.grid[r][c].owner is not None
        }
        return len(owners) > 1

    def _check_elimination(self):
        active = []
        for p in range(NUM_PLAYERS):
            if self.eliminated[p]:
                continue
            if not self.has_placed[p]:
                active.append(p)
                continue
            if any(self.grid[r][c].owner == p for r in range(GRID_SIZE) for c in range(GRID_SIZE)):
                active.append(p)
            else:
                self.eliminated[p] = True
        if len(active) == 1:
            self.winner = active[0]

    def _advance_turn(self):
        for _ in range(NUM_PLAYERS):
            self.current_player = (self.current_player + 1) % NUM_PLAYERS
            if not self.eliminated[self.current_player]:
                return


def main():
    pygame.init()
    pygame.mixer.init()
    explosion_sound = pygame.mixer.Sound(EXPLOSION_SOUND)
    explosion_sound.set_volume(0.5)

    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Critical Mass")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 30)
    big_font = pygame.font.SysFont(None, 60)
    small_font = pygame.font.SysFont(None, 18)

    pygame.mouse.set_visible(False)
    state = GameState()
    hover_cell = None

    while True:
        now_ms = pygame.time.get_ticks()
        t_sec = now_ms / 1000.0
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state.winner is not None:
                    state = GameState()
                elif not state.animating:
                    col = event.pos[0] // CELL_SIZE
                    row = (event.pos[1] - HEADER_H) // CELL_SIZE
                    if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE:
                        state.place(row, col)

        mx, my = mouse_pos
        hc = mx // CELL_SIZE
        hr = (my - HEADER_H) // CELL_SIZE
        hover_cell = (hr, hc) if 0 <= hr < GRID_SIZE and 0 <= hc < GRID_SIZE else None

        state.update(now_ms, explosion_sound)

        screen.fill(BG_COLOR)
        draw_header(screen, font, state, t_sec)
        draw_grid(screen, state, small_font, hover_cell, t_sec)
        if state.winner is not None:
            draw_winner(screen, big_font, state.winner)

        draw_cursor_orb(screen, mouse_pos[0], mouse_pos[1], PLAYER_COLORS[state.current_player], t_sec)

        pygame.display.flip()
        clock.tick(60)


def draw_header(screen, font, state, t_sec):
    p = state.current_player
    color = PLAYER_COLORS[p]
    draw_orb(screen, 20, HEADER_H // 2, color, t_sec)
    label = font.render(f"{PLAYER_NAMES[p]}'s turn", True, TEXT_COLOR)
    screen.blit(label, (38, HEADER_H // 2 - label.get_height() // 2))


def draw_grid(screen, state, small_font, hover_cell, t_sec):
    anim = state.current_anim

    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            rect = pygame.Rect(col * CELL_SIZE, HEADER_H + row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            if (row, col) == hover_cell:
                pygame.draw.rect(screen, HOVER_COLOR, rect)
            pygame.draw.rect(screen, GRID_COLOR, rect, 1)

            cell = state.grid[row][col]
            if cell.owner is not None and cell.count > 0:
                cx, cy = cell_center(row, col)
                draw_orbs(screen, cx, cy, PLAYER_COLORS[cell.owner], cell.count, t_sec)

            t = threshold(row, col)
            if t < 4:
                label = small_font.render(str(t), True, (70, 70, 90))
                screen.blit(label, (col * CELL_SIZE + 3, HEADER_H + row * CELL_SIZE + 3))

    if anim is None:
        return

    p = anim.progress(anim.start_ms + int(t_sec * 1000) - anim.start_ms)
    p = anim.progress(int(t_sec * 1000))

    for r, c, player, nbrs in anim.explosions:
        origin = cell_center(r, c)

        # Fireball — fades out after PHASE_BOARD
        if p < PHASE_BOARD:
            fb_alpha = 255
        else:
            fade = 1.0 - (p - PHASE_BOARD) / (PHASE_DONE - PHASE_BOARD)
            fb_alpha = int(255 * fade)
        if fb_alpha > 0:
            draw_explosion_fireball(screen, origin[0], origin[1], t_sec, alpha=fb_alpha)

        # Travelling orbs
        if PHASE_TRAVEL <= p < PHASE_BOARD:
            travel_t = (p - PHASE_TRAVEL) / (PHASE_BOARD - PHASE_TRAVEL)
            travel_t = 1 - (1 - travel_t) ** 2  # ease out
            color = PLAYER_COLORS[player]
            for nr, nc in nbrs:
                dest = cell_center(nr, nc)
                bx = origin[0] + (dest[0] - origin[0]) * travel_t
                by = origin[1] + (dest[1] - origin[1]) * travel_t
                draw_orb(screen, int(bx), int(by), color, t_sec, pulse=False)


def draw_winner(screen, font, winner):
    overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))
    text = font.render(f"{PLAYER_NAMES[winner]} wins!  Click to play again", True, PLAYER_COLORS[winner])
    screen.blit(text, (WINDOW_W // 2 - text.get_width() // 2, WINDOW_H // 2 - text.get_height() // 2))


if __name__ == "__main__":
    main()

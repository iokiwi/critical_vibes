import pygame
import sys
import os
import random
from collections import defaultdict

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
EXPLOSION_SOUND = os.path.join(ASSETS, "explosion.wav")
BOMB_SVG = os.path.join(ASSETS, "bomb.svg")

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


def make_bomb_surface(size, color):
    surf = pygame.image.load_sized_svg(BOMB_SVG, (size, size)).convert_alpha()
    tint = pygame.Surface((size, size), pygame.SRCALPHA)
    tint.fill((*color, 255))
    surf.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return surf


def make_fireball_surface(size):
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy, r = size // 2, size // 2, size // 2
    for i in range(r, 0, -1):
        t = i / r
        green = int(180 * (1 - t) + 80 * t)
        alpha = int(220 * (1 - t * 0.8))
        pygame.draw.circle(surf, (255, green, 0, alpha), (cx, cy), i)
    pygame.draw.circle(surf, (255, 255, 200, 240), (cx, cy), r // 3)
    return surf


class Cell:
    def __init__(self):
        self.owner = None
        self.count = 0

    def reset(self):
        self.owner = None
        self.count = 0


class WaveAnim:
    """One wave: all cells exploding simultaneously this step."""
    def __init__(self, explosions, start_ms):
        # explosions: list of (r, c, player, nbrs)
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
        self.pending_wave = False  # a wave needs to be started
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
        """Find all cells currently at/above threshold and return explosion list."""
        explosions = []
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                cell = self.grid[r][c]
                if cell.count >= threshold(r, c):
                    explosions.append((r, c, cell.owner, neighbors(r, c)))
        return explosions

    def _apply_wave(self, explosions):
        """Apply one wave to the board: explode all cells simultaneously."""
        # Accumulate incoming bombs per neighbor cell: {(r,c): (player, count)}
        # Last writer per cell wins for ownership (wave color), counts stack.
        incoming = defaultdict(lambda: [None, 0])  # (r,c) -> [last_player, total_incoming]

        for r, c, player, nbrs in explosions:
            cell = self.grid[r][c]
            t = threshold(r, c)
            remainder = cell.count % t  # bombs left after full explosion(s)
            cell.count = remainder
            if remainder == 0:
                cell.owner = None
            for nr, nc in nbrs:
                incoming[(nr, nc)][0] = player  # last exploding neighbor wins color
                incoming[(nr, nc)][1] += 1

        for (nr, nc), (player, count) in incoming.items():
            ncell = self.grid[nr][nc]
            ncell.owner = player
            ncell.count += count

    def update(self, now_ms, sound):
        if self.current_anim is None:
            if not self.pending_wave:
                return
            explosions = self._collect_wave()
            if not explosions:
                self.pending_wave = False
                self._check_elimination()
                return
            # Clear exploding cells immediately (remainders applied in _apply_wave at PHASE_BOARD)
            # Store pre-explosion snapshot for animation, apply board changes at PHASE_BOARD
            self.pending_wave = False
            self.current_anim = WaveAnim(explosions, now_ms)
            sound.play()
            # Apply remainder immediately so the cell shows the right leftover count
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
            # Deposit bombs into neighbors
            incoming = defaultdict(lambda: [None, 0])
            for r, c, player, nbrs in self.current_anim.explosions:
                for nr, nc in nbrs:
                    incoming[(nr, nc)][0] = player
                    incoming[(nr, nc)][1] += 1
            for (nr, nc), (player, count) in incoming.items():
                ncell = self.grid[nr][nc]
                ncell.owner = player
                ncell.count += count
            # Queue next wave only if enemies still have bombs (chain stops when they're wiped out)
            if self._has_overloaded_cells() and self._enemy_still_present():
                self.pending_wave = True

        if self.current_anim.done(now_ms):
            self.current_anim = None
            if not self.pending_wave:
                self._check_elimination()

    def _has_overloaded_cells(self):
        return any(
            self.grid[r][c].count >= threshold(r, c)
            for r in range(GRID_SIZE)
            for c in range(GRID_SIZE)
        )

    def _enemy_still_present(self):
        owners = {
            self.grid[r][c].owner
            for r in range(GRID_SIZE)
            for c in range(GRID_SIZE)
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

    solo_size     = int(CELL_SIZE * 0.7)
    group_size    = int(CELL_SIZE * 0.38)
    travel_size   = int(CELL_SIZE * 0.35)
    cursor_size   = int(CELL_SIZE * 0.5)
    fireball_size = int(CELL_SIZE * 0.9)

    bomb_solo   = [make_bomb_surface(solo_size, c) for c in PLAYER_COLORS]
    bomb_group  = [make_bomb_surface(group_size, c) for c in PLAYER_COLORS]
    bomb_travel = [make_bomb_surface(travel_size, c) for c in PLAYER_COLORS]
    bomb_cursor = [make_bomb_surface(cursor_size, c) for c in PLAYER_COLORS]
    fireball    = make_fireball_surface(fireball_size)

    pygame.mouse.set_visible(False)
    state = GameState()
    hover_cell = None

    while True:
        now_ms = pygame.time.get_ticks()
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
        draw_header(screen, font, state)
        draw_grid(screen, state, bomb_solo, bomb_group, bomb_travel, fireball, small_font, hover_cell, now_ms)
        if state.winner is not None:
            draw_winner(screen, big_font, state.winner)

        cursor_surf = bomb_cursor[state.current_player]
        screen.blit(cursor_surf, cursor_surf.get_rect(center=mouse_pos))

        pygame.display.flip()
        clock.tick(60)


def draw_header(screen, font, state):
    p = state.current_player
    pygame.draw.circle(screen, PLAYER_COLORS[p], (20, HEADER_H // 2), 10)
    label = font.render(f"{PLAYER_NAMES[p]}'s turn", True, TEXT_COLOR)
    screen.blit(label, (38, HEADER_H // 2 - label.get_height() // 2))


def draw_grid(screen, state, bomb_solo, bomb_group, bomb_travel, fireball, small_font, hover_cell, now_ms):
    anim = state.current_anim
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            rect = pygame.Rect(col * CELL_SIZE, HEADER_H + row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            if (row, col) == hover_cell:
                pygame.draw.rect(screen, HOVER_COLOR, rect)
            pygame.draw.rect(screen, GRID_COLOR, rect, 1)

            cell = state.grid[row][col]
            if cell.owner is not None:
                draw_bombs(screen, cell, row, col, bomb_solo, bomb_group)

            t = threshold(row, col)
            if t < 4:
                label = small_font.render(str(t), True, (70, 70, 90))
                screen.blit(label, (col * CELL_SIZE + 3, HEADER_H + row * CELL_SIZE + 3))

    if anim is None:
        return

    p = anim.progress(now_ms)

    # Fireball on each exploding cell
    for r, c, player, nbrs in anim.explosions:
        origin = cell_center(r, c)
        if p < PHASE_BOARD:
            fb = fireball
        else:
            fade = 1.0 - (p - PHASE_BOARD) / (PHASE_DONE - PHASE_BOARD)
            fb = fireball.copy()
            fb.set_alpha(int(255 * fade))
        screen.blit(fb, fb.get_rect(center=origin))

        # Travelling bombs
        if PHASE_TRAVEL <= p < PHASE_BOARD:
            travel_t = (p - PHASE_TRAVEL) / (PHASE_BOARD - PHASE_TRAVEL)
            travel_t = 1 - (1 - travel_t) ** 2  # ease out
            surf = bomb_travel[player]
            for nr, nc in nbrs:
                dest = cell_center(nr, nc)
                bx = origin[0] + (dest[0] - origin[0]) * travel_t
                by = origin[1] + (dest[1] - origin[1]) * travel_t
                screen.blit(surf, surf.get_rect(center=(int(bx), int(by))))


def draw_bombs(screen, cell, row, col, bomb_solo, bomb_group):
    p = cell.owner
    cx = col * CELL_SIZE + CELL_SIZE // 2
    cy = HEADER_H + row * CELL_SIZE + CELL_SIZE // 2
    count = min(cell.count, 4)
    if count == 1:
        surf = bomb_solo[p]
        screen.blit(surf, surf.get_rect(center=(cx, cy)))
    else:
        surf = bomb_group[p]
        spacing = int(CELL_SIZE * 0.28)
        offsets = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
        for i in range(count):
            dx, dy = offsets[i]
            screen.blit(surf, surf.get_rect(center=(cx + dx * spacing, cy + dy * spacing)))


def draw_winner(screen, font, winner):
    overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))
    text = font.render(f"{PLAYER_NAMES[winner]} wins!  Click to play again", True, PLAYER_COLORS[winner])
    screen.blit(text, (WINDOW_W // 2 - text.get_width() // 2, WINDOW_H // 2 - text.get_height() // 2))


if __name__ == "__main__":
    main()

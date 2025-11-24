import pygame
import sys
import os

pygame.init()

# --- Screen ---
WIDTH, HEIGHT = 800, 400
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Big Boy Simulator")
clock = pygame.time.Clock()

# --- Colors ---
RED   = (255,   0,   0)
GREEN = (0,   255,   0)
WHITE = (255, 255, 255)
BLACK = (0,     0,   0)
YELLOW = (255, 255, 0)

SPRITE_W, SPRITE_H = 50, 80
GROUND_Y = HEIGHT - 40

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
assets_dir = os.path.join(BASE_DIR, "assets")
BASE_P1 = os.path.join(assets_dir, "player1")
BASE_P2 = os.path.join(assets_dir, "player2")

# ----------------------------------------------------------
# BACKGROUNDS
# ----------------------------------------------------------
bg = pygame.image.load(os.path.join(assets_dir, "background.png")).convert()
bg = pygame.transform.scale(bg, (WIDTH, HEIGHT))

menu_bg = pygame.image.load(os.path.join(assets_dir, "menu_bg.png")).convert()
menu_bg = pygame.transform.scale(menu_bg, (WIDTH, HEIGHT))

# ----------------------------------------------------------
# OPTIONAL UI IMAGES
# ----------------------------------------------------------
def load_ui_image(path, size):
    if not os.path.exists(path):
        return None
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.scale(img, size)

HUD_PANEL_IMG = load_ui_image(os.path.join(assets_dir, "hud_panel.png"), (334, 34))
TIMER_PANEL_IMG = load_ui_image(os.path.join(assets_dir, "timer_panel.png"), (140, 48))
PIXEL_TIMER_BG = load_ui_image(os.path.join(assets_dir, "timer_bg.png"), (140, 48))

def render_pixel_text(text, color, scale=3):
    pixel_base = pygame.font.Font(None, 18)
    surf = pixel_base.render(text, True, color)
    w, h = surf.get_size()
    return pygame.transform.scale(surf, (w * scale, h * scale))


# ----------------------------------------------------------
# UTIL: LOAD SPRITE
# ----------------------------------------------------------
def load_sprite(folder, filename, flip=False):
    full = os.path.join(folder, filename)
    if not os.path.exists(full):
        print("MISSING:", full)
        sys.exit()
    img = pygame.image.load(full).convert_alpha()
    img = pygame.transform.scale(img, (SPRITE_W, SPRITE_H))
    if flip:
        img = pygame.transform.flip(img, True, False)
    return img


# ----------------------------------------------------------
# PROJECTILES
# ----------------------------------------------------------
class Pencil:
    def __init__(self, x, y, direction):
        self.rect = pygame.Rect(x, y, 20, 4)
        self.speed = 12 * direction

    def update(self):
        self.rect.x += self.speed

    def draw(self, surf):
        pygame.draw.rect(surf, YELLOW, self.rect)
        tip = pygame.Rect(self.rect.right - 3, self.rect.y, 3, 4)
        pygame.draw.rect(surf, (120, 80, 20), tip)


class Bottle:
    def __init__(self, x, y, direction):
        self.x = x
        self.y = y
        self.vx = 8 * direction
        self.vy = -10
        self.gravity = 0.5

        img = pygame.image.load(os.path.join(BASE_P1, "p1_bottle1.png")).convert_alpha()
        self.img = pygame.transform.scale(img, (25, 40))

        broken = pygame.image.load(os.path.join(BASE_P1, "p1_bottle_broken.png")).convert_alpha()
        self.broken = pygame.transform.scale(broken, (30, 30))

        self.width = 25
        self.height = 40
        self.dead = False
        self.hit = False
        self.shatter_timer = 0

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def update(self):
        if not self.hit:
            self.x += self.vx
            self.vy += self.gravity
            self.y += self.vy

            if self.y > GROUND_Y - 20:
                self.hit = True
                self.shatter_timer = 15

        elif self.shatter_timer > 0:
            self.shatter_timer -= 1
        else:
            self.dead = True

    def draw(self, surf):
        if self.hit:
            surf.blit(self.broken, (self.x, self.y))
        else:
            surf.blit(self.img, (self.x, self.y))


# ----------------------------------------------------------
# FIGHTER CLASS
# ----------------------------------------------------------
class Fighter:
    def __init__(self, x, folder, idle, walk, attack, hit, win, flip=False,
                 melee_key=None, proj_key=None):

        self.x = x
        self.melee_key = melee_key
        self.proj_key = proj_key

        self.health = 100
        self.velocity = 5

        self.flip = flip
        self.folder = folder

        self.idle_frames   = [load_sprite(folder, f, flip) for f in idle]
        self.walk_frames   = [load_sprite(folder, f, flip) for f in walk]
        self.attack_frames = [load_sprite(folder, f, flip) for f in attack]
        self.hit_frames    = [load_sprite(folder, f, flip) for f in hit]
        self.win_frames    = [load_sprite(folder, f, flip) for f in win]

        self.state = "idle"
        self.frame = 0
        self.counter = 0
        self.idle_speed = 15

        self.rect = self.idle_frames[0].get_rect()
        self.rect.midbottom = (x, GROUND_Y)

        self.vel_y = 0
        self.gravity = 1.0
        self.on_ground = True

        self.attack_cool = 0
        self.proj_cool = 0
        self.just_shot = False
        self.hit_timer = 0
        self.win_timer = 0

        self.image = self.idle_frames[0]

    def set_hit(self):
        self.state = "hit"
        self.frame = 0
        self.hit_timer = 12

    def set_win(self):
        self.state = "win"
        self.frame = 0
        self.win_timer = 999

    def update(self, keys, left, right, jump, opponent):
        if self.win_timer > 0:
            self.animate(self.win_frames, 12)
            return

        if self.hit_timer > 0:
            self.hit_timer -= 1
            self.animate(self.hit_frames, 6)
            return

        self.just_shot = False
        moving = False

        if keys[left]:
            self.rect.x -= self.velocity
            moving = True
        if keys[right]:
            self.rect.x += self.velocity
            moving = True

        if keys[jump] and self.on_ground:
            self.vel_y = -12
            self.on_ground = False

        self.vel_y += self.gravity
        self.rect.y += self.vel_y

        if self.rect.bottom >= GROUND_Y:
            self.rect.bottom = GROUND_Y
            self.vel_y = 0
            self.on_ground = True

        if self.attack_cool > 0:
            self.attack_cool -= 1
        if self.proj_cool > 0:
            self.proj_cool -= 1

        if keys[self.melee_key] and self.attack_cool == 0:
            self.attack_cool = 18
            self.state = "attack"
            if self.rect.colliderect(opponent.rect):
                opponent.health -= 10
                opponent.set_hit()

        elif self.proj_key and keys[self.proj_key] and self.attack_cool == 0 and self.proj_cool == 0:
            self.attack_cool = 20
            self.proj_cool = 60
            self.state = "attack"
            self.just_shot = True
        else:
            self.state = "walk" if moving else "idle"

        if self.state == "idle":
            self.animate(self.idle_frames, self.idle_speed)
        elif self.state == "walk":
            self.animate(self.walk_frames, 8)
        elif self.state == "attack":
            self.animate(self.attack_frames, 6)

    def animate(self, frames, speed):
        self.counter += 1
        if self.counter >= speed:
            self.counter = 0
            self.frame += 1
        if self.frame >= len(frames):
            self.frame = 0
            if self.state == "attack":
                self.state = "idle"
        self.image = frames[self.frame]

    def draw(self, surf):
        surf.blit(self.image, self.rect.topleft)


# ----------------------------------------------------------
# CREATE PLAYERS
# ----------------------------------------------------------
def create_players():
    p1_idle   = ["p1_idle1.png", "p1_idle2.png"]
    p1_walk   = ["p1_walk1.png"]
    p1_attack = ["p1_attack1.png", "p1_attack2.png"]
    p1_hit    = ["p1_hit1.png", "p1_hit2.png"]
    p1_win    = ["p1_win1.png"]

    p2_idle   = ["p2_idle1.png", "p2_idle2.png"]
    p2_walk   = ["p2_walk1.png"]
    p2_attack = ["p2_attack1.png", "p2_attack2.png"]
    p2_hit    = ["p2_hit1.png", "p2_hit2.png"]
    p2_win    = ["p2_win1.png"]

    p1 = Fighter(
        150, BASE_P1,
        p1_idle, p1_walk, p1_attack, p1_hit, p1_win,
        flip=False,
        melee_key=pygame.K_SPACE,
        proj_key=pygame.K_q
    )

    p2 = Fighter(
        650, BASE_P2,
        p2_idle, p2_walk, p2_attack, p2_hit, p2_win,
        flip=False,
        melee_key=pygame.K_RETURN,
        proj_key=pygame.K_p
    )

    return p1, p2


# ----------------------------------------------------------
# DRAW UI
# ----------------------------------------------------------
ui_font = pygame.font.Font(None, 28)
menu_font = pygame.font.Font(None, 80)
timer_font = pygame.font.Font(None, 60)
controls_font = pygame.font.Font(None, 36)

menu_title = menu_font.render("Big Boy Simulator", True, WHITE)
start_prompt = timer_font.render("Press ENTER to start", True, WHITE)

p1_controls = [
    controls_font.render("Player 1: Move A/D, Jump W", True, WHITE),
    controls_font.render("Melee: SPACE  |  Throw: Q", True, WHITE)
]
p2_controls = [
    controls_font.render("Player 2: Move ←/→, Jump ↑", True, WHITE),
    controls_font.render("Melee: ENTER  |  Throw: P", True, WHITE)
]

title_pos = menu_title.get_rect(center=(WIDTH // 2, 80))
prompt_pos = start_prompt.get_rect(center=(WIDTH // 2, 260))

left_x = 60
right_x = WIDTH - 60
top_y = 150
spacing = 40

p1_control_positions = [(left_x, top_y + i * spacing) for i in range(len(p1_controls))]
p2_control_positions = [(right_x - ctrl.get_width(), top_y + i * spacing)
                        for i, ctrl in enumerate(p2_controls)]


# ----------------------------------------------------------
# MAIN MENU — FIXED ✅
# ----------------------------------------------------------
def main_menu():
    while True:
        screen.blit(menu_bg, (0, 0))
        screen.blit(menu_title, title_pos)
        screen.blit(start_prompt, prompt_pos)

        for line, pos in zip(p1_controls, p1_control_positions):
            screen.blit(line, pos)

        for line, pos in zip(p2_controls, p2_control_positions):
            screen.blit(line, pos)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return

        pygame.display.flip()
        clock.tick(60)


# ----------------------------------------------------------
# ROUND COUNTDOWN — FIXED INDENTATION ✅
# ----------------------------------------------------------
def draw_countdown_frame(p1, p2, label, starting_time):
    screen.blit(bg, (0, 0))
    p1.draw(screen)
    p2.draw(screen)
    draw_ui(p1, p2, starting_time, countdown_text=label)

    overlay = render_pixel_text(label, WHITE, 5)
    outline = overlay.copy()
    outline.fill((0, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    outline_rect = overlay.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    shadow = outline_rect.move(4, 4)
    screen.blit(outline, shadow)
    screen.blit(overlay, outline_rect)

    pygame.display.flip()


def run_round_countdown(p1, p2, starting_time):
    steps = ["3", "2", "1", "GO"]
    for label in steps:
        target_ms = 800 if label == "GO" else 1000
        elapsed = 0
        while elapsed < target_ms:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return

            draw_countdown_frame(p1, p2, label, starting_time)
            elapsed += clock.tick(60)


# ----------------------------------------------------------
# SINGLE ROUND
# ----------------------------------------------------------
def play_round(p1, p2):
    time_left = 60
    tick = 0
    projectiles = []
    bottles = []

    run_round_countdown(p1, p2, time_left)

    while True:
        screen.blit(bg, (0, 0))
        keys = pygame.key.get_pressed()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        p1.update(keys, pygame.K_a, pygame.K_d, pygame.K_w, p2)
        p2.update(keys, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, p1)

        if p1.just_shot:
            bottles.append(Bottle(p1.rect.centerx, p1.rect.y, 1))

        if p2.just_shot:
            projectiles.append(Pencil(p2.rect.left, p2.rect.centery, -1))

        for p in projectiles[:]:
            p.update()
            if p.rect.colliderect(p1.rect):
                p1.health -= 5
                p1.set_hit()
                projectiles.remove(p)
            elif p.rect.right < 0:
                projectiles.remove(p)

        for b in bottles[:]:
            prev_hit = b.hit
            b.update()
            if not prev_hit and b.hit:
                hitbox = pygame.Rect(b.x, b.y, 40, 40)
                if hitbox.colliderect(p2.rect):
                    p2.health -= 15
                    p2.set_hit()
            if b.dead or b.x > WIDTH + 40 or b.x < -40:
                bottles.remove(b)

        for p in projectiles:
            p.draw(screen)
        for b in bottles:
            b.draw(screen)

        p1.draw(screen)
        p2.draw(screen)

        draw_ui(p1, p2, time_left)

        pygame.display.flip()
        clock.tick(60)

        tick += 1
        if tick >= 60:
            tick = 0
            time_left -= 1

        if time_left <= 0:
            return 1 if p1.health > p2.health else 2
        if p1.health <= 0:
            return 2
        if p2.health <= 0:
            return 1


# ----------------------------------------------------------
# GAME LOOP
# ----------------------------------------------------------
def game_loop():
    main_menu()

    p1_score = 0
    p2_score = 0

    while p1_score < 2 and p2_score < 2:
        p1, p2 = create_players()
        winner = play_round(p1, p2)

        if winner == 1:
            p1_score += 1
            p1.set_win()
        else:
            p2_score += 1
            p2.set_win()

        pygame.time.delay(1500)

    screen.fill(BLACK)
    txt = menu_font.render(
        "PLAYER 1 WINS!" if p1_score > p2_score else "PLAYER 2 WINS!",
        True, WHITE
    )
    screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - 50))
    pygame.display.flip()
    pygame.time.delay(3000)


# ----------------------------------------------------------
# START GAME
# ----------------------------------------------------------
if __name__ == "__main__":
    game_loop()
    pygame.quit()
    sys.exit()
+39
-0

import importlib
import os

import pytest


@pytest.fixture(scope="module")
def pygame_mod():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    return pytest.importorskip("pygame")


def test_pencil_collision_reduces_health(pygame_mod):
    main = importlib.import_module("main")
    pencil = main.Pencil(200, 100, direction=-1)

    class DummyFighter:
        def __init__(self):
            self.rect = pygame_mod.Rect(100, 96, 40, 12)
            self.health = 100
            self.hit_called = False

        def set_hit(self):
            self.hit_called = True

    fighter = DummyFighter()

    for _ in range(10):
        pencil.update()
        if pencil.rect.colliderect(fighter.rect):
            fighter.health -= 5
            fighter.set_hit()
            break
    else:
        pytest.fail("Pencil never collided with the fighter")

    assert fighter.health == 95
    assert fighter.hit_called
+53
-0

import importlib
import os

import pygame


HEADLESS_VARS = {
    "SDL_VIDEODRIVER": "dummy",
    "SDL_AUDIODRIVER": "dummy",
}


def initialize_pygame_headless():
    """Initialize pygame with a dummy video driver for headless testing."""
    for key, value in HEADLESS_VARS.items():
        os.environ.setdefault(key, value)

    pygame.display.init()
    if not pygame.display.get_surface():
        pygame.display.set_mode((1, 1))


def test_bottle_hit_and_shatter(monkeypatch):
    for key, value in HEADLESS_VARS.items():
        monkeypatch.setenv(key, value)

    initialize_pygame_headless()

    def dummy_load(_path):
        """Return a minimal surface to avoid loading external assets."""
        return pygame.Surface((1, 1), pygame.SRCALPHA)

    monkeypatch.setattr(pygame.image, "load", dummy_load)

    main = importlib.reload(importlib.import_module("main"))

    bottle = main.Bottle(x=0, y=0, direction=1)

    steps = 0
    while not bottle.hit and not bottle.dead:
        bottle.update()
        steps += 1
        assert steps < 1000, "Bottle never hit the ground"

    assert bottle.hit is True
    assert bottle.dead is False
    assert bottle.shatter_timer == 15

    for _ in range(15):
        bottle.update()
        assert bottle.hit is True
        assert bottle.dead is False

    assert bottle.shatter_timer == 0

    bottle.update()
    assert bottle.dead is True


    pygame.quit()

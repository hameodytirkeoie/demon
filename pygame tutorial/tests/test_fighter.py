import importlib
import sys
import os

import pytest

HEADLESS_VARS = {
    "SDL_VIDEODRIVER": "dummy",
    "SDL_AUDIODRIVER": "dummy",
}


@pytest.fixture(autouse=True)
def set_headless_env(monkeypatch):
    """Force pygame to use dummy drivers so imports stay headless."""
    for key, value in HEADLESS_VARS.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def pygame_mod():
    """Provide an initialized, headless pygame module for tests."""
    pygame = pytest.importorskip("pygame")
    pygame.display.init()
    if not pygame.display.get_surface():
        pygame.display.set_mode((1, 1))
    yield pygame
    pygame.quit()


@pytest.fixture
def main_module(monkeypatch, pygame_mod):
    """Import the game module with asset loading stubbed out."""
    def dummy_load(_path):
        return pygame_mod.Surface((1, 1), pygame_mod.SRCALPHA)

    monkeypatch.setattr(pygame_mod.image, "load", dummy_load)

    importlib.invalidate_caches()
    if "main" in sys.modules:
        module = importlib.reload(sys.modules["main"])
    else:
        module = importlib.import_module("main")
    return module


def test_pencil_collision_reduces_health(main_module, pygame_mod):
    pencil = main_module.Pencil(200, 100, direction=-1)

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


def test_bottle_hit_and_shatter(main_module, pygame_mod):
    bottle = main_module.Bottle(x=0, y=0, direction=1)

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

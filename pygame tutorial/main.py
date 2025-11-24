import os

import pytest

# Use the dummy video driver so pygame can initialize headlessly during tests.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

import main


def make_keys(pressed):
    class _Keys:
        def __getitem__(self, key):
            return pressed.get(key, False)

    return _Keys()


def test_fighter_attack_cooldown_and_idle():
    fighter, opponent = main.create_players()

    # Trigger an initial melee attack.
    attack_keys = make_keys({fighter.me: True})
    fighter.update(attack_keys, pygame.K_a, pygame.K_d, pygame.K_w, opponent)

    assert fighter.state == "attack"
    assert fighter.attack_cool == 18

    # Advance a few frames to allow the fighter to return to idle.
    idle_keys = make_keys({})
    for _ in range(5):
        fighter.update(idle_keys, pygame.K_a, pygame.K_d, pygame.K_w, opponent)

    assert fighter.state == "idle"

    # Attempt to attack again during cooldown; it should not restart the attack.
    fighter.update(attack_keys, pygame.K_a, pygame.K_d, pygame.K_w, opponent)
    assert fighter.attack_cool < 18
    assert fighter.state == "idle"

    # Let the cooldown expire, then ensure another attack is allowed.
    while fighter.attack_cool > 0:
        fighter.update(idle_keys, pygame.K_a, pygame.K_d, pygame.K_w, opponent)

    fighter.update(attack_keys, pygame.K_a, pygame.K_d, pygame.K_w, opponent)
    assert fighter.state == "attack"
    assert fighter.attack_cool == 18

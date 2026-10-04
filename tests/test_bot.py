"""Runs the bot loop against a simulated device (no phone needed)."""

import numpy as np
import pytest

import farmbot.bot as bot_module
from farmbot.bot import Bot
from farmbot.config import load
from farmbot.loot import Loot
from farmbot.vision import Match

from tests.test_config import EXAMPLE

# screen state -> visible button; tapping a button moves to the next state
FLOW = {
    "home": ("attack_button", "menu"),
    "menu": ("find_match", "base"),
    "base": ("next_button", "searching"),
    "battle_end": ("return_home", "home"),
}


class FakeDevice:
    size = (1000, 500)

    def __init__(self):
        self.state = "home"
        self.taps = []
        self.battle_frames = 0

    def ensure_connected(self):
        pass

    def screenshot(self):
        if self.state == "searching":  # one frame of clouds, then the next base appears
            self.state = "clouds"
        elif self.state == "clouds":
            self.state = "base"
        elif self.state == "battle":
            self.battle_frames += 1
            if self.battle_frames > 2:
                self.state = "battle_end"
        return np.zeros((500, 1000, 3), np.uint8)

    def tap(self, x, y):
        self.taps.append((x, y))
        if (x, y) == (1, 1) and self.state in FLOW:
            self.state = FLOW[self.state][1]

    def restart_app(self, package):
        self.state = "home"


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setattr(bot_module.time, "sleep", lambda s: None)
    cfg = load(EXAMPLE)
    cfg.train_sequence = []
    cfg.surrender_after = None
    cfg.max_attacks = 2
    for slot in cfg.slots:
        if slot.ability_after is not None:
            slot.ability_after = 0
    device = FakeDevice()
    b = Bot(cfg, device)
    b.templates.find = lambda screen, name, **kw: (
        Match(0, 0, 3, 3, 1.0) if FLOW.get(device.state, (None,))[0] == name else None
    )
    b.templates.has = lambda name: False
    return b


def test_full_attack_loop(bot, monkeypatch):
    bases = iter([Loot(10_000, 10_000, 0), Loot(600_000, 550_000, 0)] * 2)
    monkeypatch.setattr(bot, "read_loot", lambda screen: next(bases))
    original_deploy = bot.deploy

    def deploy():
        result = original_deploy()
        bot.device.state = "battle"
        bot.device.battle_frames = 0
        return result

    monkeypatch.setattr(bot, "deploy", deploy)
    bot.run()

    assert bot.attacks == 2
    troops = sum(s.count for s in bot.cfg.slots)
    abilities = sum(1 for s in bot.cfg.slots if s.ability_after is not None)
    # per attack: deploy taps + slot selections + hero abilities
    deploy_taps = [t for t in bot.device.taps if t != (1, 1)]
    assert len(deploy_taps) == 2 * (troops + len(bot.cfg.slots) + abilities)

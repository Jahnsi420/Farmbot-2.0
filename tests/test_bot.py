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
        self.holds = []
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

    def tap_streams(self, streams):
        self.streams = streams
        for stream in streams:
            for x, y in stream:
                self.tap(x, y)

    def hold(self, x, y, ms):
        self.holds.append((x, y, ms))

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


@pytest.fixture
def battle(bot, monkeypatch):
    """Bot in a running battle with a fake clock; returns (bot, clock, surrender times)."""
    clock = [0.0]
    monkeypatch.setattr(bot_module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(bot_module.time, "sleep", lambda s: clock.__setitem__(0, clock[0] + s))
    bot.templates.has = lambda name: True
    bot.cfg.surrender_when_idle = 15
    bot.cfg.surrender_after = None
    bot.cfg.surrender_min_time = 0
    bot.device.state = "battle"
    bot.device.battle_frames = -10_000  # the battle only ends by surrendering
    surrendered = []

    def surrender(screen):
        surrendered.append(clock[0])
        bot.device.state = "battle_end"

    monkeypatch.setattr(bot, "surrender", surrender)
    return bot, clock, surrendered


def test_surrenders_once_loot_stops_dropping(battle, monkeypatch):
    bot, clock, surrendered = battle
    # goblins walk (loot unchanged), then loot two storages, then nothing left to take
    readings = iter([Loot(500_000, 500_000, 0)] * 3 + [Loot(400_000, 450_000, 0), Loot(300_000, 300_000, 0)]
                    + [Loot(300_000, 300_000, 0), Loot(390_000, 300_000, 0)] * 50)
    monkeypatch.setattr(bot, "read_loot", lambda screen: next(readings))
    bot.wait_battle_end([])
    # last drop at the 5th reading (t=6.0s); a higher misreading must not reset the timer
    assert surrendered == [pytest.approx(21.0)]


def test_no_idle_surrender_before_loot_starts_dropping(battle, monkeypatch):
    bot, clock, surrendered = battle
    bot.cfg.surrender_after = 60
    monkeypatch.setattr(bot, "read_loot", lambda screen: Loot(500_000, 500_000, 0))
    bot.wait_battle_end([])
    assert surrendered == [pytest.approx(60.0)]


def test_surrenders_when_loot_only_trickles(battle, monkeypatch):
    bot, clock, surrendered = battle
    bot.cfg.surrender_min_loot = 20_000
    # big storages first (100k per reading), then collectors trickle 1k per reading (~10k per 15s)
    totals = [2_000_000] * 3 + [2_000_000 - 100_000 * i for i in range(1, 6)]
    totals += [totals[-1] - 1_000 * i for i in range(1, 200)]
    readings = iter(Loot(t // 2, t - t // 2, 0) for t in totals)
    monkeypatch.setattr(bot, "read_loot", lambda screen: next(readings))
    bot.wait_battle_end([])
    # last big drop at t=10.5s: the 15s window behind it holds >= 20k until t=10.5+15
    assert len(surrendered) == 1 and 24.0 <= surrendered[0] <= 27.0


def test_surrender_after_counts_from_deploy_start(battle, monkeypatch):
    bot, clock, surrendered = battle
    bot.cfg.surrender_when_idle = None
    bot.cfg.surrender_after = 120
    clock[0] = 50.0  # deploying took 50s
    bot.wait_battle_end([], start=0.0)
    assert surrendered == [pytest.approx(120.5)]


def test_deploy_points_split_count_over_parallel_streams(bot):
    bot.cfg.deploy_points = 4
    slot = bot.cfg.slots[0]
    slot.count = 301
    streams = bot.deploy_streams(slot)
    assert [len(s) for s in streams] == [76, 75, 75, 75]
    assert all(len(set(s)) == 1 for s in streams)  # each stream taps one point
    assert len({s[0] for s in streams}) == 4

    bot.cfg.deploy_points = 0
    (single,) = bot.deploy_streams(slot)
    assert len(single) == 301 and len(set(single)) > 4


def test_no_stall_surrender_before_min_time(battle, monkeypatch):
    bot, clock, surrendered = battle
    bot.cfg.surrender_min_time = 45
    # a few edge collectors are looted right away, then nothing until the goblins reach storages
    readings = iter([Loot(950_000, 950_000, 0), Loot(945_000, 950_000, 0)] + [Loot(945_000, 950_000, 0)] * 200)
    monkeypatch.setattr(bot, "read_loot", lambda screen: next(readings))
    bot.wait_battle_end([])
    assert surrendered == [pytest.approx(45.0)]


def test_next_base_waits_for_different_loot_and_retaps(bot, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(bot_module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(bot_module.time, "sleep", lambda s: clock.__setitem__(0, clock[0] + s))
    old, new = Loot(100_000, 100_000, 0), Loot(800_000, 700_000, 0)
    # first tap is lost: the same base stays for > 5s, then the retap loads the new one
    readings = iter([old] * 30 + [new])
    monkeypatch.setattr(bot, "read_loot", lambda screen: next(readings))
    bot.device.state = "stuck"
    bot.templates.find = lambda screen, name, **kw: Match(0, 0, 3, 3, 1.0)
    taps_before = len(bot.device.taps)
    screen, loot = bot.next_base(old)
    assert loot == new
    assert len(bot.device.taps) - taps_before >= 2


def test_leftovers_are_held_down_until_card_is_empty(bot, monkeypatch):
    slot = bot.cfg.slots[0]
    bot.templates.has = lambda name: True
    bot.cfg.leftover_hold = 0.8
    checks = iter([False, False, False, True])  # card empties after the 3rd hold
    monkeypatch.setattr(bot, "slot_empty", lambda s: next(checks))
    bot.deploy_leftovers(slot)
    assert len(bot.device.holds) == 3
    assert all(ms == 800 for _, _, ms in bot.device.holds)
    assert len({(x, y) for x, y, _ in bot.device.holds}) == 3  # a bad spot is not hit twice in a row


def test_leftovers_give_up_after_timeout(bot, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(bot_module.time, "monotonic", lambda: clock[0])
    bot.templates.has = lambda name: True
    bot.cfg.leftover_timeout = 10
    monkeypatch.setattr(bot, "slot_empty", lambda s: False)
    monkeypatch.setattr(bot.device, "hold", lambda x, y, ms: clock.__setitem__(0, clock[0] + 1.5))
    bot.deploy_leftovers(bot.cfg.slots[0])
    assert clock[0] == pytest.approx(10.5)


def test_slot_empty_detects_greyed_out_card(bot, tmp_path, monkeypatch):
    from farmbot import imaging
    from farmbot.vision import Templates

    imaging.imwrite(tmp_path / "slot_goblin.png", np.zeros((20, 20, 3), np.uint8))
    bot.templates = Templates(tmp_path)
    slot = bot.cfg.slots[0]
    slot.pos = (0.5, 0.9)
    full = np.zeros((500, 1000, 3), np.uint8)
    full[440:460, 490:510] = (40, 200, 60)  # colorful card
    grey = full.copy()
    grey[440:460, 490:510] = (120, 120, 120)
    monkeypatch.setattr(bot.device, "screenshot", lambda: full)
    assert not bot.slot_empty(slot)
    monkeypatch.setattr(bot.device, "screenshot", lambda: grey)
    assert bot.slot_empty(slot)

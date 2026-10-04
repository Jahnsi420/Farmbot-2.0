"""Load and validate the YAML configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from farmbot.deploy import SIDES, Diamond
from farmbot.loot import LootFilter
from farmbot.vision import Rect


class ConfigError(ValueError):
    pass


@dataclass
class TroopSlot:
    name: str
    pos: tuple[float, float]  # relative position of the slot in the troop bar
    count: int = 1            # taps to deploy (1 for heroes / clan castle)
    sides: list[str] | None = None  # overrides army.deploy_sides
    ability_after: float | None = None  # heroes: tap slot again after N seconds
    template: str | None = None  # find the slot in the troop bar by image instead of pos


@dataclass
class Config:
    serial: str | None = None
    adb_path: str = "adb"
    package: str = "com.supercell.clashofclans"

    templates_dir: str = "templates"
    threshold: float = 0.85

    loot_filter: LootFilter = field(default_factory=LootFilter)
    loot_regions: dict[str, Rect] = field(default_factory=dict)
    max_skips: int = 100
    attack_on_unreadable: bool = False

    slots: list[TroopSlot] = field(default_factory=list)
    deploy_sides: list[str] = field(default_factory=lambda: list(SIDES))
    deploy_outward: float = 0.03
    deploy_margin: float = 0.1
    tap_delay: float = 0.08
    diamond: Diamond = field(default_factory=lambda: Diamond((0.5, 0.1), (0.9, 0.5), (0.5, 0.9), (0.1, 0.5)))

    battle_max_duration: float = 180
    surrender_after: float | None = None

    train_sequence: list[str] = field(default_factory=list)
    wait_after_train: float = 0

    max_attacks: int = 0  # 0 = unlimited
    pause_between_attacks: float = 5

    timeouts: dict[str, float] = field(default_factory=dict)


def _rel_point(value: Any, where: str) -> tuple[float, float]:
    if not (isinstance(value, (list, tuple)) and len(value) == 2):
        raise ConfigError(f"{where}: erwartet [x, y], bekommen {value!r}")
    x, y = float(value[0]), float(value[1])
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ConfigError(f"{where}: Koordinaten müssen relativ (0..1) sein, bekommen {value!r}")
    return x, y


def _rel_rect(value: Any, where: str) -> Rect:
    if not (isinstance(value, (list, tuple)) and len(value) == 4):
        raise ConfigError(f"{where}: erwartet [x1, y1, x2, y2], bekommen {value!r}")
    x1, y1 = _rel_point(value[:2], where)
    x2, y2 = _rel_point(value[2:], where)
    if x2 <= x1 or y2 <= y1:
        raise ConfigError(f"{where}: x2/y2 müssen größer als x1/y1 sein")
    return x1, y1, x2, y2


def _sides(value: Any, where: str) -> list[str]:
    sides = list(value)
    for s in sides:
        if s not in SIDES:
            raise ConfigError(f"{where}: unbekannte Seite '{s}', erlaubt: {', '.join(SIDES)}")
    return sides


def parse(data: dict[str, Any]) -> Config:
    cfg = Config()
    device = data.get("device") or {}
    cfg.serial = device.get("serial")
    cfg.adb_path = device.get("adb_path", cfg.adb_path)
    cfg.package = (data.get("game") or {}).get("package", cfg.package)

    templates = data.get("templates") or {}
    cfg.templates_dir = templates.get("dir", cfg.templates_dir)
    cfg.threshold = float(templates.get("threshold", cfg.threshold))

    search = data.get("search") or {}
    try:
        cfg.loot_filter = LootFilter(
            min_gold=int(search.get("min_gold", 0)),
            min_elixir=int(search.get("min_elixir", 0)),
            min_dark=int(search.get("min_dark", 0)),
            mode=search.get("mode", "any"),
            min_total=int(search.get("min_total", 0)),
        )
    except ValueError as e:
        raise ConfigError(str(e)) from e
    cfg.max_skips = int(search.get("max_skips", cfg.max_skips))
    cfg.attack_on_unreadable = bool(search.get("attack_on_unreadable", False))
    cfg.loot_regions = {
        name: _rel_rect(rect, f"loot_regions.{name}")
        for name, rect in (data.get("loot_regions") or {}).items()
    }

    army = data.get("army") or {}
    cfg.deploy_sides = _sides(army.get("deploy_sides", SIDES), "army.deploy_sides")
    cfg.deploy_outward = float(army.get("deploy_outward", cfg.deploy_outward))
    cfg.deploy_margin = float(army.get("deploy_margin", cfg.deploy_margin))
    if not 0 <= cfg.deploy_margin < 0.5:
        raise ConfigError("army.deploy_margin muss zwischen 0 und 0.5 liegen")
    cfg.tap_delay = float(army.get("tap_delay", cfg.tap_delay))
    for i, slot in enumerate(army.get("slots") or []):
        where = f"army.slots[{i}]"
        cfg.slots.append(TroopSlot(
            name=str(slot.get("name", f"slot{i}")),
            pos=_rel_point(slot.get("pos"), f"{where}.pos"),
            count=int(slot.get("count", 1)),
            sides=_sides(slot["sides"], f"{where}.sides") if "sides" in slot else None,
            ability_after=float(slot["ability_after"]) if slot.get("ability_after") is not None else None,
            template=slot.get("template"),
        ))
    if not cfg.slots:
        raise ConfigError("army.slots ist leer – mindestens ein Truppen-Slot wird benötigt.")

    d = data.get("map_diamond") or {}
    if d:
        cfg.diamond = Diamond(*(_rel_point(d.get(k), f"map_diamond.{k}") for k in ("top", "right", "bottom", "left")))

    battle = data.get("battle") or {}
    cfg.battle_max_duration = float(battle.get("max_duration", cfg.battle_max_duration))
    if battle.get("surrender_after") is not None:
        cfg.surrender_after = float(battle["surrender_after"])

    training = data.get("training") or {}
    cfg.train_sequence = list(training.get("sequence") or [])
    cfg.wait_after_train = float(training.get("wait_after", 0))

    session = data.get("session") or {}
    cfg.max_attacks = int(session.get("max_attacks", 0))
    cfg.pause_between_attacks = float(session.get("pause_between_attacks", cfg.pause_between_attacks))

    cfg.timeouts = {k: float(v) for k, v in (data.get("timeouts") or {}).items()}
    return cfg


def load(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Konfiguration {path} nicht gefunden. Tipp: config.example.yaml nach {path} kopieren.")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    cfg = parse(data)
    # Relative template dirs are resolved next to the config file.
    if not Path(cfg.templates_dir).is_absolute():
        cfg.templates_dir = str(path.parent / cfg.templates_dir)
    return cfg

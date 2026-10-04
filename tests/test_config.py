from pathlib import Path

import pytest
import yaml

from farmbot.config import ConfigError, load, parse

EXAMPLE = Path(__file__).parent.parent / "config.example.yaml"


def test_example_config_loads():
    cfg = load(EXAMPLE)
    assert cfg.slots[0].name == "barbarian"
    assert cfg.slots[2].ability_after == 10
    assert set(cfg.loot_regions) == {"gold", "elixir", "dark"}
    assert Path(cfg.templates_dir) == EXAMPLE.parent / "templates"


def _example():
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def test_rejects_absolute_pixel_coordinates():
    data = _example()
    data["army"]["slots"][0]["pos"] = [120, 900]
    with pytest.raises(ConfigError, match="relativ"):
        parse(data)


def test_rejects_unknown_side():
    data = _example()
    data["army"]["deploy_sides"] = ["left"]
    with pytest.raises(ConfigError):
        parse(data)


def test_requires_slots():
    data = _example()
    data["army"]["slots"] = []
    with pytest.raises(ConfigError):
        parse(data)

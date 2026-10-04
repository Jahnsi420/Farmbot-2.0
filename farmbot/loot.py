"""Decide whether a searched base is worth attacking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Loot:
    gold: int | None
    elixir: int | None
    dark: int | None

    def __str__(self) -> str:
        def fmt(v: int | None) -> str:
            return "?" if v is None else f"{v:,}".replace(",", ".")

        return f"Gold {fmt(self.gold)} | Elixier {fmt(self.elixir)} | Dunkles {fmt(self.dark)}"


@dataclass
class LootFilter:
    min_gold: int = 0
    min_elixir: int = 0
    min_dark: int = 0
    # any: one resource reaches its minimum; all: every resource does;
    # sum: gold + elixir reach min_total.
    mode: str = "any"
    min_total: int = 0

    def __post_init__(self) -> None:
        if self.mode not in ("any", "all", "sum"):
            raise ValueError(f"search.mode muss any, all oder sum sein, nicht '{self.mode}'")

    def accept(self, loot: Loot) -> bool:
        if self.mode == "sum":
            if loot.gold is None or loot.elixir is None:
                return False
            return loot.gold + loot.elixir >= self.min_total

        checks = []
        for value, minimum in ((loot.gold, self.min_gold), (loot.elixir, self.min_elixir),
                               (loot.dark, self.min_dark)):
            if minimum <= 0:
                continue
            checks.append(value is not None and value >= minimum)
        if not checks:
            return True
        return any(checks) if self.mode == "any" else all(checks)

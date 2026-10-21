"""Rubrics live as Markdown files in lahja/rubrics/<name>.md. One rubric = one question."""

from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class Rubric:
    name: str
    text: str


def available_rubrics() -> list[str]:
    folder = resources.files("lahja") / "rubrics"
    return sorted(p.name.removesuffix(".md") for p in folder.iterdir() if p.name.endswith(".md"))


def load_rubric(name: str) -> Rubric:
    path = resources.files("lahja") / "rubrics" / f"{name}.md"
    if not path.is_file():
        raise ValueError(f"no rubric {name!r}; available: {', '.join(available_rubrics())}")
    return Rubric(name=name, text=path.read_text(encoding="utf-8"))

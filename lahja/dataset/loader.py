"""Read JSONL eval cases and store them as a dataset."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from lahja.dataset.schema import EvalCase
from lahja.db import Case, Dataset


class DatasetError(ValueError):
    pass


def read_cases(path: Path) -> list[EvalCase]:
    """Parse one case per line. Collects every error so you can fix the file in one pass."""
    cases: list[EvalCase] = []
    errors: list[str] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(EvalCase.model_validate_json(line))
        except ValidationError as e:
            details = "; ".join(f"{'.'.join(map(str, err['loc'])) or 'case'}: {err['msg']}" for err in e.errors())
            errors.append(f"line {lineno}: {details}")
    dupes = [cid for cid, n in Counter(c.id for c in cases).items() if n > 1]
    if dupes:
        errors.append(f"duplicate ids: {', '.join(sorted(dupes))}")
    if errors:
        raise DatasetError("\n".join(errors))
    if not cases:
        raise DatasetError(f"{path} contains no cases")
    return cases


def coverage(cases: list[EvalCase]) -> Counter[tuple[str, str]]:
    """Case counts per (language, script). Per-language verdicts need enough cases in each cell."""
    return Counter((c.language, c.script) for c in cases)


def import_dataset(session: Session, name: str, cases: list[EvalCase], system_prompt: str = "") -> Dataset:
    if session.scalar(select(Dataset).where(Dataset.name == name)) is not None:
        raise DatasetError(f"dataset {name!r} already exists; pick a new name (e.g. {name}-v2)")
    dataset = Dataset(name=name, system_prompt=system_prompt)
    dataset.cases = [
        Case(
            external_id=c.id,
            language=c.language,
            script=c.script,
            code_switch=list(c.code_switch),
            intent=c.intent,
            input=c.input,
            reference=c.reference,
            notes=c.notes,
        )
        for c in cases
    ]
    session.add(dataset)
    session.commit()
    return dataset


def get_dataset(session: Session, name: str) -> Dataset:
    dataset = session.scalar(select(Dataset).where(Dataset.name == name))
    if dataset is None:
        raise DatasetError(f"no dataset named {name!r} (see `lahja dataset list`)")
    return dataset

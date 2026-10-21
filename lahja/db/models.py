"""SQLAlchemy 2.0 schema.

Dataset ─< Case
Dataset ─< Run ─< Response >─ Case        (one Run per (dataset, model))
Response ─< Judgment                       (one per (response, rubric, judge model))
Response ─< HumanLabel                     (one per (response, rubric))

The unique constraints double as caches: re-running a step only fills in what is missing.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=_now)

    cases: Mapped[list[Case]] = relationship(back_populates="dataset", order_by="Case.id")
    runs: Mapped[list[Run]] = relationship(back_populates="dataset")


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (UniqueConstraint("dataset_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    external_id: Mapped[str] = mapped_column(String(100))  # the "id" from the JSONL file
    language: Mapped[str] = mapped_column(String(10))
    script: Mapped[str] = mapped_column(String(10))
    code_switch: Mapped[list[str]] = mapped_column(JSON, default=list)
    intent: Mapped[str] = mapped_column(String(100))
    input: Mapped[str] = mapped_column(Text)
    reference: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")

    dataset: Mapped[Dataset] = relationship(back_populates="cases")


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (UniqueConstraint("dataset_id", "model"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    model: Mapped[str] = mapped_column(String(200))  # ModelSpec.key
    created_at: Mapped[datetime] = mapped_column(default=_now)

    dataset: Mapped[Dataset] = relationship(back_populates="runs")
    responses: Mapped[list[Response]] = relationship(
        back_populates="run", order_by="(Response.case_id, Response.trial)"
    )


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (UniqueConstraint("run_id", "case_id", "trial"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))
    trial: Mapped[int]
    output: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    run: Mapped[Run] = relationship(back_populates="responses")
    case: Mapped[Case] = relationship()


class Judgment(Base):
    __tablename__ = "judgments"
    __table_args__ = (UniqueConstraint("response_id", "rubric", "judge_model"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("responses.id"))
    rubric: Mapped[str] = mapped_column(String(100))
    judge_model: Mapped[str] = mapped_column(String(200))
    passed: Mapped[bool]
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=_now)

    response: Mapped[Response] = relationship()


class HumanLabel(Base):
    __tablename__ = "human_labels"
    __table_args__ = (UniqueConstraint("response_id", "rubric"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("responses.id"))
    rubric: Mapped[str] = mapped_column(String(100))
    passed: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(default=_now)

    response: Mapped[Response] = relationship()

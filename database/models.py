"""SQLAlchemy ORM models for bot data storage."""
from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ScheduleBell(Base):
    """Bell schedule row. day=-1: regular days; 0..6: custom per weekday."""
    __tablename__ = "schedule_bells"
    __table_args__ = (UniqueConstraint("day", "shift", "number", name="uq_schedule_bells_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="-1")
    shift: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[str] = mapped_column(String(5), nullable=False)
    ends_at: Mapped[str] = mapped_column(String(5), nullable=False)
    note: Mapped[str | None] = mapped_column(String(60), nullable=True)


class ScheduleLesson(Base):
    """Weekly lesson schedule. week: upper|lower|both."""
    __tablename__ = "schedule_lessons"
    __table_args__ = (UniqueConstraint("day", "number", "week", name="uq_schedule_lessons_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[str] = mapped_column(String(5), nullable=False)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    room: Mapped[str | None] = mapped_column(String(20), nullable=True)
    teacher: Mapped[str | None] = mapped_column(String(60), nullable=True)


class ScheduleSetting(Base):
    """Key-value config storage: anchor_monday, anchor_parity, lessons_shift, replacements_group."""
    __tablename__ = "schedule_settings"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(String(64), nullable=False)


class ReplacementState(Base):
    """Replacement sync state: snapshot (JSON), empty_streak."""
    __tablename__ = "shapt_replacements_state"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)

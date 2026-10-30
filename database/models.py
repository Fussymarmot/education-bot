"""SQLAlchemy ORM models for bot data storage."""
from sqlalchemy import BigInteger, Float, Index, Integer, String, Text, UniqueConstraint
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


class AiMessage(Base):
    """Короткая память ИИ-собеседника: последние сообщения чата (role: user|assistant). Чистится автоматически."""
    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_chat_id_id", "chat_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    author: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

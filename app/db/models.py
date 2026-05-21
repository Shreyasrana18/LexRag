import uuid
from datetime import datetime
from sqlalchemy import String, Text, Date, ForeignKey, Integer, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base

class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    court: Mapped[str] = mapped_column(String(255), nullable=False)
    case_number: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    respondents: Mapped[str] = mapped_column(Text, nullable=False)
    petitioners: Mapped[str] = mapped_column(Text, nullable=False)  
    decision_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=True,
        index=True
    )
    citation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    chunks: Mapped[list["CaseChunk"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )

class CaseChunk(Base):
    __tablename__ = "case_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    case: Mapped["Case"] = relationship(back_populates="chunks")
    __table_args__ = (
        Index("ix_case_chunks_case_id_chunk_index", "case_id", "chunk_index"),
    )
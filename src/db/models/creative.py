from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, BigInteger, Date, SmallInteger, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from .base import Base

if TYPE_CHECKING:
    from .user import User


class Creative(Base):
    __tablename__ = "creatives"

    creative_id: Mapped[str] = mapped_column(String, primary_key=True)
    geo: Mapped[str] = mapped_column(String, nullable=False)
    telegram_file_id: Mapped[str] = mapped_column(String, nullable=False)
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Deprecated Google Drive fields (kept for compatibility)
    drive_file_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    drive_link: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    uploader_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    uploader_buyer_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    original_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ext: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    upload_dt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    custom_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    uploader: Mapped["User"] = relationship(
        "User", back_populates="uploaded_creatives", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Creative(creative_id={self.creative_id}, geo={self.geo})>"


class GeoCounter(Base):
    __tablename__ = "geo_counters"
    __table_args__ = (UniqueConstraint("geo", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    geo: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    last_seq: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    def __repr__(self) -> str:
        return f"<GeoCounter(geo={self.geo}, date={self.date}, last_seq={self.last_seq})>"
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, SmallInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User


class DigestSettings(Base, TimestampMixin):
    __tablename__ = "digest_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False
    )
    daily: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly: Mapped[bool] = mapped_column(Boolean, default=False)
    time_hour: Mapped[int] = mapped_column(SmallInteger, default=10)
    time_minute: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="digest_settings", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DigestSettings(id={self.id}, user_id={self.user_id}, daily={self.daily})>"
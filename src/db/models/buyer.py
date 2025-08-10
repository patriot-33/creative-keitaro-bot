from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User
    from .team import Team


class Buyer(Base, TimestampMixin):
    __tablename__ = "buyers"

    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    team_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("teams.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="buyers", lazy="selectin"
    )
    team: Mapped[Optional["Team"]] = relationship(
        "Team", back_populates="buyers", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Buyer(id={self.id}, buyer_id={self.buyer_id}, is_active={self.is_active})>"
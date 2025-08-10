from typing import List, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User
    from .buyer import Buyer


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    lead_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    # Relationships
    lead: Mapped["User"] = relationship(
        "User", back_populates="teams_as_lead", lazy="selectin"
    )
    members: Mapped[List["TeamMember"]] = relationship(
        "TeamMember", back_populates="team", lazy="selectin", cascade="all, delete-orphan"
    )
    buyers: Mapped[List["Buyer"]] = relationship(
        "Buyer", back_populates="team", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name={self.name})>"


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id"),)

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True
    )

    # Relationships
    team: Mapped["Team"] = relationship(
        "Team", back_populates="members", lazy="selectin"
    )
    user: Mapped["User"] = relationship(
        "User", back_populates="team_memberships", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<TeamMember(team_id={self.team_id}, user_id={self.user_id})>"
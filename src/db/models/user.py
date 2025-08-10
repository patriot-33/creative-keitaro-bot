from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, BigInteger, Boolean, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import sys
from pathlib import Path
from .base import Base, TimestampMixin

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.enums import UserRole

if TYPE_CHECKING:
    from .team import Team, TeamMember
    from .buyer import Buyer
    from .creative import Creative
    from .audit import AuditLog
    from .digest import DigestSettings


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    tg_username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    buyer_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    created_by: Mapped[Optional["User"]] = relationship(
        "User", remote_side="User.id", lazy="selectin"
    )
    teams_as_lead: Mapped[List["Team"]] = relationship(
        "Team", back_populates="lead", lazy="selectin"
    )
    team_memberships: Mapped[List["TeamMember"]] = relationship(
        "TeamMember", back_populates="user", lazy="selectin"
    )
    buyers: Mapped[List["Buyer"]] = relationship(
        "Buyer", back_populates="user", lazy="selectin"
    )
    uploaded_creatives: Mapped[List["Creative"]] = relationship(
        "Creative", back_populates="uploader", lazy="selectin"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="user", lazy="selectin"
    )
    digest_settings: Mapped[Optional["DigestSettings"]] = relationship(
        "DigestSettings", back_populates="user", uselist=False, lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, tg_user_id={self.tg_user_id}, role={self.role})>"
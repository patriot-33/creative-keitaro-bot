"""
Custom GEO model for persistent storage
"""

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class CustomGeo(Base, TimestampMixin):
    """Model for custom geographical regions"""
    
    __tablename__ = "custom_geos"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(4), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    def __repr__(self):
        return f"<CustomGeo(id={self.id}, code='{self.code}', is_active={self.is_active})>"
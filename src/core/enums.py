from enum import Enum, auto


class UserRole(str, Enum):
    BUYER = "buyer"
    TEAMLEAD = "teamlead"
    HEAD = "head"
    OWNER = "owner"
    BIZDEV = "bizdev"
    FINANCE = "finance"
    
    @classmethod
    def has_admin_rights(cls, role: str) -> bool:
        """Check if role has admin privileges"""
        return role in [cls.HEAD, cls.OWNER]
    
    @classmethod
    def can_approve_users(cls, role: str) -> bool:
        """Check if role can approve new users"""
        return role in [cls.TEAMLEAD, cls.HEAD, cls.OWNER]
    
    @classmethod
    def can_view_all_stats(cls, role: str) -> bool:
        """Check if role can view all statistics"""
        return role in [cls.HEAD, cls.OWNER, cls.BIZDEV, cls.FINANCE]


class AuditAction(str, Enum):
    UPLOAD = "upload"
    EXPORT = "export"
    STATS_QUERY = "stats_query"
    ADMIN_UPDATE = "admin_update"
    USER_APPROVED = "user_approved"
    USER_REJECTED = "user_rejected"
    BUYER_CREATED = "buyer_created"
    BUYER_UPDATED = "buyer_updated"
    BUYER_DEACTIVATED = "buyer_deactivated"


class ReportPeriod(str, Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_24H = "last_24h"
    LAST_3D = "last_3d"
    LAST_7D = "last_7d"
    LAST_15D = "last_15d"
    LAST_30D = "last_30d"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    CUSTOM = "custom"


class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"


class CreativeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
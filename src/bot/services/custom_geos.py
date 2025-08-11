"""
Service for managing custom GEO codes with persistent database storage
"""

import logging
from typing import List
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from db.database import get_db_session
from db.models.custom_geo import CustomGeo

logger = logging.getLogger(__name__)


class CustomGeosService:
    """Service for managing custom geographical regions"""
    
    @staticmethod
    async def get_all_custom_geos() -> List[str]:
        """Get all active custom GEO codes"""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(CustomGeo.code)
                    .where(CustomGeo.is_active == True)
                    .order_by(CustomGeo.code)
                )
                custom_geos = [row[0] for row in result.fetchall()]
                logger.error(f"📋 CUSTOM GEOS DB: Retrieved {len(custom_geos)} active custom geos: {custom_geos}")
                return custom_geos
                
        except Exception as e:
            logger.error(f"❌ CUSTOM GEOS DB: Error retrieving custom geos: {e}")
            return []
    
    @staticmethod
    async def add_custom_geo(code: str) -> bool:
        """Add a new custom GEO code"""
        try:
            code = code.upper().strip()
            
            async with get_db_session() as session:
                # Check if already exists
                result = await session.execute(
                    select(CustomGeo)
                    .where(CustomGeo.code == code)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    if existing.is_active:
                        logger.error(f"⚠️ CUSTOM GEOS DB: Code {code} already exists and is active")
                        return False
                    else:
                        # Reactivate existing code
                        existing.is_active = True
                        logger.error(f"🔄 CUSTOM GEOS DB: Reactivated existing code {code}")
                else:
                    # Create new custom geo
                    new_geo = CustomGeo(code=code, is_active=True)
                    session.add(new_geo)
                    logger.error(f"➕ CUSTOM GEOS DB: Added new code {code}")
                
                await session.commit()
                logger.error(f"✅ CUSTOM GEOS DB: Successfully saved code {code} to database")
                return True
                
        except IntegrityError as e:
            logger.error(f"❌ CUSTOM GEOS DB: Integrity error adding code {code}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ CUSTOM GEOS DB: Error adding custom geo {code}: {e}")
            return False
    
    @staticmethod
    async def remove_custom_geo(code: str) -> bool:
        """Remove (deactivate) a custom GEO code"""
        try:
            code = code.upper().strip()
            
            async with get_db_session() as session:
                result = await session.execute(
                    select(CustomGeo)
                    .where(CustomGeo.code == code)
                )
                geo = result.scalar_one_or_none()
                
                if not geo:
                    logger.error(f"⚠️ CUSTOM GEOS DB: Code {code} not found")
                    return False
                
                geo.is_active = False
                await session.commit()
                
                logger.error(f"🗑️ CUSTOM GEOS DB: Deactivated code {code}")
                return True
                
        except Exception as e:
            logger.error(f"❌ CUSTOM GEOS DB: Error removing custom geo {code}: {e}")
            return False
    
    @staticmethod
    async def exists_custom_geo(code: str) -> bool:
        """Check if custom GEO code exists and is active"""
        try:
            code = code.upper().strip()
            
            async with get_db_session() as session:
                result = await session.execute(
                    select(func.count(CustomGeo.id))
                    .where(CustomGeo.code == code)
                    .where(CustomGeo.is_active == True)
                )
                count = result.scalar()
                
                exists = count > 0
                logger.error(f"🔍 CUSTOM GEOS DB: Code {code} exists check: {exists}")
                return exists
                
        except Exception as e:
            logger.error(f"❌ CUSTOM GEOS DB: Error checking custom geo {code}: {e}")
            return False
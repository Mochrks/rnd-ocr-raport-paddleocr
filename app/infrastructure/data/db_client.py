"""
app/infrastructure/data/db_client.py
======================================
Provides database connectivity and utility functions, primarily for
fetching dynamic configuration flags such as `use_ai_ocr` from PostgreSQL.
"""

import logging
import asyncpg
from asyncpg.exceptions import PostgresError

from app.core.config import settings

logger = logging.getLogger(__name__)


async def get_use_ai_ocr_flag() -> bool:
    """
    Connects to the PostgreSQL database and fetches the `use_ai_ocr` flag
    from the `global_configuration` table.
    
    If the table doesn't exist, connection fails, or row doesn't exist,
    returns False as a safe fallback (i.e., use manual PaddleOCR).
    """
    try:
        conn = await asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            timeout=3.0  # short timeout so it doesn't block OCR requests if DB is down
        )
    except Exception as e:
        logger.warning(f"DB Connection failed: {e}. Fallback to manual OCR (use_ai_ocr=False)")
        logger.info("OCR Mode: Using Manual PaddleOCR Model")
        return False

    try:
        query = "SELECT use_ai_ocr FROM global_configurations LIMIT 1;"
        row = await conn.fetchrow(query)
        if row is not None:
            # Assumes column is boolean
            use_ai = bool(row["use_ai_ocr"])
            if use_ai:
                logger.info("OCR Mode: Using AI Model")
            else:
                logger.info("OCR Mode: Using Manual PaddleOCR Model")
            return use_ai
        else:
            logger.warning("global_configurations table is empty. Fallback to manual OCR (use_ai_ocr=False)")
            logger.info("OCR Mode: Using Manual PaddleOCR Model")
            return False
    except PostgresError as e:
        logger.warning(f"DB Query failed (maybe table doesn't exist?): {e}. Fallback to manual OCR")
        logger.info("OCR Mode: Using Manual PaddleOCR Model")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error fetching use_ai_ocr: {e}. Fallback to manual OCR")
        logger.info("OCR Mode: Using Manual PaddleOCR Model")
        return False
    finally:
        await conn.close()

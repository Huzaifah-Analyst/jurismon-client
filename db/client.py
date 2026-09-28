"""JurisMon Database Client.

Provides access to Supabase via its official client. When Supabase credentials
are absent the repository layer falls back to local SQLite.

DATABASE_URL is read for future direct-PostgreSQL use but is not wired up yet;
all production reads and writes currently go through the Supabase client.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("jurismon.db")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

try:
    from supabase import create_client, Client
    SUPABASE_LIB_AVAILABLE = True
except ImportError:
    SUPABASE_LIB_AVAILABLE = False


class DatabaseClient:
    """Singleton database connector for Supabase / PostgreSQL."""

    _supabase_instance: Optional["Client"] = None

    @classmethod
    def get_supabase(cls) -> Optional["Client"]:
        """Returns initialized Supabase Client if credentials are provided."""
        if cls._supabase_instance is not None:
            return cls._supabase_instance

        if not SUPABASE_LIB_AVAILABLE:
            logger.warning("Supabase python library not installed.")
            return None

        if SUPABASE_URL and SUPABASE_KEY and not SUPABASE_URL.startswith("https://your-project"):
            try:
                cls._supabase_instance = create_client(SUPABASE_URL, SUPABASE_KEY)
                logger.info("Connected to Supabase client successfully.")
                return cls._supabase_instance
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                return None
        return None

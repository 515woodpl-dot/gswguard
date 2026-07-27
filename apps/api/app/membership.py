from __future__ import annotations

import logging
from uuid import UUID

from .auth import AppRole

logger = logging.getLogger(__name__)


class MembershipRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def resolve(self, user_id: UUID) -> tuple[AppRole, UUID] | None:
        query = """
            select role::text, organization_id
            from public.organization_memberships
            where user_id = %s
            order by created_at asc
            limit 1
        """
        try:
            import psycopg

            with psycopg.connect(self.database_url, connect_timeout=5) as connection:
                row = connection.execute(query, (user_id,)).fetchone()
        except ImportError:
            logger.exception("PostgreSQL driver is not installed")
            return None
        except Exception:
            logger.exception("Unable to resolve organization membership")
            return None
        if row is None:
            return None
        role, organization_id = row
        return AppRole(str(role)), organization_id

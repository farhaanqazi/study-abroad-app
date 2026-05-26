"""Grant (or revoke) a platform role directly in the database.

An ops/bootstrap alternative to the PLATFORM_SUPERADMINS env allowlist — useful
to seed the first superadmin or fix access without a redeploy. The user must
already exist (i.e. have logged in at least once, since users are provisioned
lazily from Clerk).

Usage (from backend/, with DATABASE_URL pointing at the target DB):
    PYTHONPATH=. python scripts/grant_platform_role.py <email-or-clerk_id> <role>

    role ∈ {none, support, admin, superadmin}

Examples:
    PYTHONPATH=. python scripts/grant_platform_role.py you@example.com superadmin
    PYTHONPATH=. python scripts/grant_platform_role.py user_3EFf... admin
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import or_, select

from app.core.enums import PlatformRole
from app.db.models.tenant import User
from app.db.session import db_session


async def _run(identifier: str, role: PlatformRole) -> int:
    async with db_session.session_factory() as session:
        user = await session.scalar(
            select(User).where(
                or_(User.email == identifier, User.clerk_id == identifier)
            )
        )
        if user is None:
            print(f"ERROR: no user found for '{identifier}'. "
                  "They must sign in once before a role can be granted.")
            return 2
        old = user.platform_role
        user.platform_role = role
        await session.commit()
        print(f"OK: {user.email} ({user.clerk_id}) platform_role {old.value} -> {role.value}")
        return 0


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    identifier, role_str = sys.argv[1], sys.argv[2].strip().lower()
    try:
        role = PlatformRole(role_str)
    except ValueError:
        print(f"ERROR: invalid role '{role_str}'. "
              f"Choose one of: {', '.join(r.value for r in PlatformRole)}")
        sys.exit(1)
    sys.exit(asyncio.run(_run(identifier, role)))


if __name__ == "__main__":
    main()

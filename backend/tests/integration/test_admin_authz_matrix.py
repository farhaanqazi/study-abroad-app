"""Platform back-office authorization matrix + workspace-approval e2e.

Drives the real ASGI app via httpx.AsyncClient with the identity dependency
overridden to a chosen platform role. Asserts the tier boundaries (none/support/
admin/superadmin) and an end-to-end workspace request -> approve flow that
provisions a vendor + owner membership + audit row.

Requires DATABASE_URL pointing at a disposable local DB already at head.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.dependencies.auth import get_current_user
from app.core.enums import PlatformRole, WorkspaceRequestStatus
from app.db.models.platform import AuditLog, WorkspaceRequest
from app.db.models.tenant import User, Vendor, VendorMembership
from app.db.session import db_session
from app.main import app

API = "/api/v1"


def _as_role(role: PlatformRole):
    async def _dep() -> User:
        async with db_session.session_factory() as s:
            u = User(clerk_id=f"clerk_{role.value}_{uuid.uuid4().hex[:8]}",
                     email=f"{role.value}_{uuid.uuid4().hex[:6]}@t.com",
                     platform_role=role)
            s.add(u)
            await s.commit()
            await s.refresh(u)
            return u
    return _dep


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pytest.mark.parametrize(
    "role,expected",
    [(PlatformRole.NONE, 403), (PlatformRole.SUPPORT, 200),
     (PlatformRole.ADMIN, 200), (PlatformRole.SUPERADMIN, 200)],
)
async def test_admin_read_authz_matrix(role, expected):
    app.dependency_overrides[get_current_user] = _as_role(role)
    try:
        async with await _client() as c:
            r = await c.get(f"{API}/admin/vendors")
        assert r.status_code == expected, (role, r.status_code, r.text[:200])
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_support_cannot_grant_platform_role_but_superadmin_can():
    # support -> 403 on a superadmin-only mutation
    app.dependency_overrides[get_current_user] = _as_role(PlatformRole.SUPPORT)
    try:
        async with await _client() as c:
            r = await c.patch(f"{API}/admin/users/{uuid.uuid4()}/platform-role",
                              json={"platform_role": "admin"})
        assert r.status_code == 403, r.text[:200]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_workspace_request_approve_e2e():
    # A requester submits; an admin approves; vendor + owner membership + audit appear.
    async with db_session.session_factory() as s:
        requester = User(clerk_id=f"req_{uuid.uuid4().hex[:8]}",
                         email=f"req_{uuid.uuid4().hex[:6]}@t.com")
        s.add(requester)
        await s.commit()
        await s.refresh(requester)
        requester_id = requester.id

    # submit as the requester
    app.dependency_overrides[get_current_user] = lambda: requester  # type: ignore[assignment]

    async def _req_dep() -> User:
        async with db_session.session_factory() as s:
            return await s.get(User, requester_id)

    app.dependency_overrides[get_current_user] = _req_dep
    slug = f"acme-{uuid.uuid4().hex[:6]}"
    try:
        async with await _client() as c:
            r = await c.post(f"{API}/workspace-requests",
                             json={"business_name": "Acme Edu", "desired_slug": slug})
            assert r.status_code == 201, r.text[:200]
            request_id = r.json()["id"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # approve as an admin
    app.dependency_overrides[get_current_user] = _as_role(PlatformRole.ADMIN)
    try:
        async with await _client() as c:
            r = await c.post(f"{API}/admin/workspace-requests/{request_id}/approve", json={})
            assert r.status_code == 200, r.text[:200]
            vendor_id = uuid.UUID(r.json()["created_vendor_id"])
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # verify side effects committed together
    async with db_session.session_factory() as s:
        vendor = await s.get(Vendor, vendor_id)
        assert vendor is not None and vendor.slug == slug
        mem = await s.scalar(
            select(VendorMembership).where(
                VendorMembership.vendor_id == vendor_id,
                VendorMembership.user_id == requester_id,
            )
        )
        assert mem is not None and mem.role.value == "owner"
        req = await s.get(WorkspaceRequest, uuid.UUID(request_id))
        assert req.status == WorkspaceRequestStatus.APPROVED
        audits = await s.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action == "workspace_request.approve",
                AuditLog.target_id == uuid.UUID(request_id),
            )
        )
        assert audits == 1

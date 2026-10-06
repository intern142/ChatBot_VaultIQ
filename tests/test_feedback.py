"""VQ-305: Tests for answer feedback capture."""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Answer, AnswerFeedback
from app.models.user import User
from app.auth.password import hash_password
from app.auth.jwt import create_access_token


class TestAnswerFeedback:
    """Tests for answer feedback CRUD operations."""

    @pytest_asyncio.fixture
    async def setup_tenant_and_users(self, db_engine):
        """Create a tenant with client_admin and employee."""
        async with db_engine.begin() as conn:
            from app.models.tenant import Tenant
            result = await conn.execute(
                text("""
                    INSERT INTO tenants (short_code, name, status, storage_quota_mb)
                    VALUES ('FEEDBACK_TEST', 'Feedback Test', 'active', 2048)
                    RETURNING id
                """)
            )
            tenant_id = result.scalar()

            ph = hash_password("StrongPass1!")
            result = await conn.execute(
                text("""
                    INSERT INTO users (tenant_id, email, password_hash, role)
                    VALUES (:tid, 'admin@feedback.com', :ph, 'client_admin'),
                           (:tid, 'emp@feedback.com', :ph, 'employee')
                    RETURNING id, email, role
                """),
                {"tid": tenant_id, "ph": ph}
            )
            users = result.mappings().all()
            admin_uid = users[0]["id"]
            emp_uid = users[1]["id"]

            admin_sid = uuid.uuid4()
            emp_sid = uuid.uuid4()
            await conn.execute(
                text("""
                    INSERT INTO sessions (id, user_id, tenant_id, token_hash, expires_at)
                    VALUES (:sid1, :uid1, :tid, '', now() + interval '24 hours'),
                           (:sid2, :uid2, :tid, '', now() + interval '24 hours')
                """),
                {"sid1": admin_sid, "uid1": admin_uid, "sid2": emp_sid, "uid2": emp_uid, "tid": tenant_id}
            )

            return {
                "tenant_id": tenant_id,
                "client_admin": {"id": admin_uid, "email": users[0]["email"], "role": users[0]["role"], "session_id": admin_sid},
                "employee": {"id": emp_uid, "email": users[1]["email"], "role": users[1]["role"], "session_id": emp_sid},
            }

    @pytest.fixture
    def token_admin(self, setup_tenant_and_users):
        u = setup_tenant_and_users["client_admin"]
        return create_access_token(
            user_id=u["id"],
            role=u["role"],
            tenant_id=setup_tenant_and_users["tenant_id"],
            session_id=u["session_id"],
        )

    @pytest.fixture
    def token_emp(self, setup_tenant_and_users):
        u = setup_tenant_and_users["employee"]
        return create_access_token(
            user_id=u["id"],
            role=u["role"],
            tenant_id=setup_tenant_and_users["tenant_id"],
            session_id=u["session_id"],
        )

    @pytest_asyncio.fixture
    async def answer(self, db_session: AsyncSession, setup_tenant_and_users):
        """Create a test answer."""
        tenant_id = setup_tenant_and_users["tenant_id"]
        user_id = setup_tenant_and_users["employee"]["id"]

        answer = Answer(
            tenant_id=tenant_id,
            user_id=user_id,
            question="What is the vacation policy?",
            answer_text="Vacation requests must be submitted 2 weeks in advance.",
            confidence=0.9,
            source_document_ids=[uuid.uuid4()],
            source_chunk_ids=[uuid.uuid4()],
        )
        db_session.add(answer)
        await db_session.commit()
        await db_session.refresh(answer)
        return answer

    @pytest.mark.asyncio
    async def test_create_feedback_success(self, async_client: AsyncClient, token_emp, answer):
        """Employee can submit feedback on an answer."""
        headers = {"Authorization": f"Bearer {token_emp}"}
        resp = await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": 1, "comment": "Helpful answer"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["vote"] == 1
        assert data["comment"] == "Helpful answer"
        assert data["answer_id"] == str(answer.id)

    @pytest.mark.asyncio
    async def test_create_feedback_negative_vote(self, async_client: AsyncClient, token_emp, answer):
        """Employee can submit negative feedback."""
        headers = {"Authorization": f"Bearer {token_emp}"}
        resp = await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": -1, "comment": "Not helpful"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["vote"] == -1

    @pytest.mark.asyncio
    async def test_create_feedback_no_comment(self, async_client: AsyncClient, token_emp, answer):
        """Employee can submit feedback without comment."""
        headers = {"Authorization": f"Bearer {token_emp}"}
        resp = await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": 1},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["comment"] is None

    @pytest.mark.asyncio
    async def test_create_feedback_duplicate_fails(self, async_client: AsyncClient, token_emp, answer):
        """Cannot submit feedback twice for same answer."""
        headers = {"Authorization": f"Bearer {token_emp}"}
        await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": 1},
            headers=headers,
        )
        resp = await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": -1},
            headers=headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_update_feedback(self, async_client: AsyncClient, token_emp, answer, db_session: AsyncSession):
        """Employee can update their feedback."""
        headers = {"Authorization": f"Bearer {token_emp}"}
        # Create initial feedback
        await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": 1, "comment": "Initial"},
            headers=headers,
        )

        # Update feedback
        resp = await async_client.patch(
            f"/answers/{answer.id}/feedback",
            json={"vote": -1, "comment": "Changed my mind"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["vote"] == -1
        assert data["comment"] == "Changed my mind"

    @pytest.mark.asyncio
    async def test_get_own_feedback(self, async_client: AsyncClient, token_emp, answer):
        """Employee can retrieve their own feedback."""
        headers = {"Authorization": f"Bearer {token_emp}"}
        await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": 1, "comment": "Test"},
            headers=headers,
        )

        resp = await async_client.get(
            f"/answers/{answer.id}/feedback",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["vote"] == 1

    @pytest.mark.asyncio
    async def test_employee_cannot_see_others_feedback(self, async_client: AsyncClient, token_emp, token_admin, answer, db_session: AsyncSession):
        """Employee cannot see another user's feedback."""
        admin_headers = {"Authorization": f"Bearer {token_admin}"}
        emp_headers = {"Authorization": f"Bearer {token_emp}"}

        # Admin creates feedback
        await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": 1, "comment": "Admin feedback"},
            headers=admin_headers,
        )

        # Employee tries to get it - should 404
        resp = await async_client.get(
            f"/answers/{answer.id}/feedback",
            headers=emp_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_client_admin_sees_all_feedback(self, async_client: AsyncClient, token_admin, token_emp, answer):
        """Client admin can see all feedback on an answer."""
        emp_headers = {"Authorization": f"Bearer {token_emp}"}
        admin_headers = {"Authorization": f"Bearer {token_admin}"}

        # Employee creates feedback
        await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": -1, "comment": "Employee feedback"},
            headers=emp_headers,
        )

        # Admin can see it
        resp = await async_client.get(
            f"/answers/{answer.id}/feedback",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["vote"] == -1

    @pytest.mark.asyncio
    async def test_list_feedback_client_admin(self, async_client: AsyncClient, token_admin, answer, setup_tenant_and_users, db_session: AsyncSession):
        """Client admin can list all feedback in tenant."""
        headers = {"Authorization": f"Bearer {token_admin}"}
        tenant_id = setup_tenant_and_users["tenant_id"]
        emp_id = setup_tenant_and_users["employee"]["id"]

        # Create feedback directly in DB
        fb = AnswerFeedback(
            tenant_id=tenant_id,
            user_id=emp_id,
            answer_id=answer.id,
            vote=1,
            comment="Test feedback",
        )
        db_session.add(fb)
        await db_session.commit()

        resp = await async_client.get("/answers/feedback", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["feedback"]) >= 1

    @pytest.mark.asyncio
    async def test_list_feedback_filter_by_answer(self, async_client: AsyncClient, token_admin, answer, setup_tenant_and_users, db_session: AsyncSession):
        """Client admin can filter feedback by answer_id."""
        headers = {"Authorization": f"Bearer {token_admin}"}
        tenant_id = setup_tenant_and_users["tenant_id"]
        emp_id = setup_tenant_and_users["employee"]["id"]

        # Create feedback for this answer
        fb = AnswerFeedback(
            tenant_id=tenant_id,
            user_id=emp_id,
            answer_id=answer.id,
            vote=1,
        )
        db_session.add(fb)

        # Create another answer and feedback
        other_answer = Answer(
            tenant_id=tenant_id,
            user_id=emp_id,
            question="Other question?",
            answer_text="Other answer",
            confidence=0.5,
            source_document_ids=[],
            source_chunk_ids=[],
        )
        db_session.add(other_answer)
        await db_session.flush()

        fb2 = AnswerFeedback(
            tenant_id=tenant_id,
            user_id=emp_id,
            answer_id=other_answer.id,
            vote=-1,
        )
        db_session.add(fb2)
        await db_session.commit()

        resp = await async_client.get(
            f"/answers/feedback?answer_id={answer.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(f["answer_id"] == str(answer.id) for f in data["feedback"])

    @pytest.mark.asyncio
    async def test_list_feedback_filter_by_vote(self, async_client: AsyncClient, token_admin, answer, setup_tenant_and_users, db_session: AsyncSession):
        """Client admin can filter feedback by vote."""
        headers = {"Authorization": f"Bearer {token_admin}"}
        tenant_id = setup_tenant_and_users["tenant_id"]
        emp_id = setup_tenant_and_users["employee"]["id"]

        fb = AnswerFeedback(
            tenant_id=tenant_id,
            user_id=emp_id,
            answer_id=answer.id,
            vote=1,
        )
        db_session.add(fb)
        await db_session.commit()

        resp = await async_client.get(
            "/answers/feedback?vote=1",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(f["vote"] == 1 for f in data["feedback"])

    @pytest.mark.asyncio
    async def test_super_admin_denied_on_feedback(self, async_client: AsyncClient, super_admin_token, answer):
        """Super admin cannot access feedback endpoints."""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        resp = await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": 1},
            headers=headers,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_vote_rejected(self, async_client: AsyncClient, token_emp, answer):
        """Vote must be 1 or -1."""
        headers = {"Authorization": f"Bearer {token_emp}"}
        resp = await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": 2},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_comment_length_limit(self, async_client: AsyncClient, token_emp, answer):
        """Comment max 500 chars."""
        headers = {"Authorization": f"Bearer {token_emp}"}
        resp = await async_client.post(
            f"/answers/{answer.id}/feedback",
            json={"vote": 1, "comment": "x" * 501},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_feedback_on_nonexistent_answer(self, async_client: AsyncClient, token_emp):
        """Feedback on non-existent answer returns 404."""
        headers = {"Authorization": f"Bearer {token_emp}"}
        resp = await async_client.post(
            f"/answers/{uuid.uuid4()}/feedback",
            json={"vote": 1},
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_tenant_feedback_isolation(self, async_client: AsyncClient, db_engine, token_emp):
        """Tenant A cannot create feedback on Tenant B's answer."""
        # Create tenant B with an answer
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            from app.models.tenant import Tenant
            result = await session.execute(
                text("""
                    INSERT INTO tenants (short_code, name, status, storage_quota_mb)
                    VALUES ('TENANT_B_FB', 'Tenant B FB', 'active', 2048)
                    RETURNING id
                """)
            )
            tenant_b_id = result.scalar()
            ph = hash_password("StrongPass1!")
            result = await session.execute(
                text("""
                    INSERT INTO users (tenant_id, email, password_hash, role)
                    VALUES (:tid, 'emp@b.com', :ph, 'employee')
                    RETURNING id
                """),
                {"tid": tenant_b_id, "ph": ph}
            )
            user_b_id = result.scalar()

            answer = Answer(
                tenant_id=tenant_b_id,
                user_id=user_b_id,
                question="Tenant B question?",
                answer_text="Tenant B answer",
                confidence=0.8,
                source_document_ids=[],
                source_chunk_ids=[],
            )
            session.add(answer)
            await session.flush()
            answer_id = answer.id
            await session.commit()

        # Try to create feedback with tenant A token
        headers = {"Authorization": f"Bearer {token_emp}"}
        resp = await async_client.post(
            f"/answers/{answer_id}/feedback",
            json={"vote": 1},
            headers=headers,
        )
        assert resp.status_code == 404  # Answer not found due to RLS
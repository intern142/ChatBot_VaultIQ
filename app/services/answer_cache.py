import hashlib
from uuid import UUID
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.answer_cache import AnswerCache
from app.models.tenant import Tenant


class AnswerCacheService:
    """Service for managing tenant-scoped answer cache."""

    @staticmethod
    def _question_hash(question: str) -> str:
        """Compute SHA-256 hash of normalized question."""
        normalized = question.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    async def get(
        db: AsyncSession,
        tenant_id: UUID,
        role: str,
        question: str,
        kb_version: int,
    ) -> Optional[AnswerCache]:
        """
        Look up a cached answer.
        
        Args:
            db: Database session (must have tenant context set)
            tenant_id: Tenant UUID
            role: User role ('client_admin' or 'employee')
            question: Raw question text
            kb_version: Current knowledge base version for the tenant
            
        Returns:
            AnswerCache entry if found, None otherwise
        """
        qhash = AnswerCacheService._question_hash(question)
        result = await db.execute(
            select(AnswerCache).where(
                AnswerCache.tenant_id == tenant_id,
                AnswerCache.role == role,
                AnswerCache.question_hash == qhash,
                AnswerCache.kb_version == kb_version,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def set(
        db: AsyncSession,
        tenant_id: UUID,
        role: str,
        question: str,
        kb_version: int,
        answer_text: str,
        source_document_id: UUID,
        source_chunk_id: UUID,
        expires_at: str | None = None,
    ) -> AnswerCache:
        """
        Store a new cached answer.
        
        Args:
            db: Database session (must have tenant context set)
            tenant_id: Tenant UUID
            role: User role
            question: Raw question text
            kb_version: Current KB version
            answer_text: The answer sentence to cache
            source_document_id: Document UUID the answer came from
            source_chunk_id: Chunk UUID the answer came from
            expires_at: Optional TTL (ISO format datetime string)
            
        Returns:
            The created AnswerCache entry
        """
        qhash = AnswerCacheService._question_hash(question)
        entry = AnswerCache(
            tenant_id=tenant_id,
            role=role,
            question_hash=qhash,
            kb_version=kb_version,
            answer_text=answer_text,
            source_document_id=source_document_id,
            source_chunk_id=source_chunk_id,
            expires_at=expires_at,
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def invalidate_tenant(db: AsyncSession, tenant_id: UUID) -> int:
        """
        Invalidate all cache entries for a tenant (called on KB version bump).
        
        Args:
            db: Database session
            tenant_id: Tenant UUID
            
        Returns:
            Number of entries deleted
        """
        result = await db.execute(
            select(AnswerCache).where(AnswerCache.tenant_id == tenant_id)
        )
        entries = result.scalars().all()
        count = len(entries)
        for entry in entries:
            await db.delete(entry)
        return count

    @staticmethod
    async def get_kb_version(db: AsyncSession, tenant_id: UUID) -> int:
        """Get current KB version for a tenant."""
        result = await db.execute(
            select(Tenant.knowledge_base_version).where(Tenant.id == tenant_id)
        )
        version = result.scalar_one_or_none()
        return version or 0
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user_with_tenant
from app.auth.permissions import require_roles_with_tenant
from app.models.user import User
from app.schemas.answer import AnswerRequest, AnswerResponse
from app.services.answers import answer_question
from app.services.search import SearchTenantRequiredError

router = APIRouter(prefix="/answers", tags=["answers"])


@router.post("", response_model=AnswerResponse)
async def answer_endpoint(
    request: AnswerRequest,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    """
    Answer a question strictly from the requesting tenant's documents.

    Extractive, retrieval-only: the answer is a sentence lifted verbatim
    from the tenant's own chunks. If the documents do not answer the
    question, routing is "no_answer" and no excerpt is presented.
    """
    _, tenant_id_str = current_user_tenant
    tenant_id = uuid.UUID(tenant_id_str)

    try:
        return await answer_question(
            db=db,
            tenant_id=tenant_id,
            question=request.question,
            top_k=request.top_k,
            hybrid_weight=request.hybrid_weight,
        )
    except SearchTenantRequiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
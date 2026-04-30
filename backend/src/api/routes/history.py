"""User's agent run history."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import get_current_user
from src.db.session import get_db
from src.models.agent_run import AgentRun
from src.models.user import User
from src.schemas.agent import AgentRunResponse, RunListResponse

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=RunListResponse)
async def list_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count()).where(AgentRun.user_id == current_user.id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.user_id == current_user.id)
        .options(selectinload(AgentRun.tool_calls))
        .order_by(desc(AgentRun.started_at))
        .offset(offset)
        .limit(page_size)
    )
    runs = result.scalars().all()
    return RunListResponse(runs=list(runs), total=total)


@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.user_id == current_user.id)
        .options(selectinload(AgentRun.tool_calls))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

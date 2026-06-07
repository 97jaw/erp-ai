"""FastAPI routes for the Visualize agent (separate from main chat)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from admin.auth.dependencies import require_chat_user
from visualize.agent import stream_visualize_chat
from visualize.brain import run_full_brain, run_inspection, run_pattern_analysis, run_recommendation
from visualize.direct_build import ensure_session_brain, execute_direct_build
from visualize.layouts import list_layouts
from visualize.prompt import DEFAULT_OUTPUT_ACTIONS
from visualize.themes import list_themes
from visualize.sessions import (
    create_session,
    get_session,
    initial_response,
    update_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visualize", tags=["visualize"])
_http_bearer = HTTPBearer(auto_error=False)


class DroppedItemModel(BaseModel):
    id: str | None = None
    queryId: int | str | None = None
    question: str | None = None
    text: str | None = None
    visualization: dict | None = None
    vizType: str | None = None
    createdAt: int | None = None


class VisualizeStartRequest(BaseModel):
    items: list[DroppedItemModel] = Field(default_factory=list)
    chat_session_id: str | None = None


class VisualizeStartResponse(BaseModel):
    session_id: str
    greeting: str
    actions: list[dict]
    item_count: int
    brain: dict | None = None


class VisualizeBuildRequest(BaseModel):
    session_id: str
    format: str | None = Field(None, alias="format")
    theme: str | None = None
    layout: str | None = None
    include_logo: bool = True
    page_numbers: bool = True
    watermark: str | None = "none"
    title: str | None = None

    model_config = {"populate_by_name": True}


class VisualizeBuildResponse(BaseModel):
    output: dict
    format: str


class VisualizeChatRequest(BaseModel):
    session_id: str
    message: str
    items: list[DroppedItemModel] | None = None


class VisualizeBrainItemsRequest(BaseModel):
    items: list[DroppedItemModel] = Field(default_factory=list)


class VisualizeAnalyzeRequest(BaseModel):
    items: list[DroppedItemModel] = Field(default_factory=list)
    inspection: dict | None = None


class VisualizeRecommendRequest(BaseModel):
    inspection: dict
    analysis: dict


class VisualizeSessionResponse(BaseModel):
    session_id: str
    dropped_items: list[dict]
    output_type: str | None = None
    last_output: dict | None = None
    message_count: int
    brain: dict | None = None


def _items_to_dicts(items: list[DroppedItemModel]) -> list[dict]:
    return [item.model_dump(exclude_none=True) for item in items]


async def _require_session(session_id: str, user_id: int | None):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Visualize session not found")
    if session.user_id is not None and user_id is not None and session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Visualize session access denied")
    return session


@router.post("/inspect")
async def visualize_inspect(
    request: VisualizeBrainItemsRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    await require_chat_user(http_request, credentials)
    items = _items_to_dicts(request.items)
    if not items:
        raise HTTPException(status_code=400, detail="items are required")
    return {"inspection": run_inspection(items)}


@router.post("/analyze")
async def visualize_analyze(
    request: VisualizeAnalyzeRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    await require_chat_user(http_request, credentials)
    items = _items_to_dicts(request.items)
    if not items:
        raise HTTPException(status_code=400, detail="items are required")
    inspection = request.inspection or run_inspection(items)
    analysis = run_pattern_analysis(items, inspection)
    return {"inspection": inspection, "analysis": analysis}


@router.post("/recommend")
async def visualize_recommend(
    request: VisualizeRecommendRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    await require_chat_user(http_request, credentials)
    if not request.inspection or not request.analysis:
        raise HTTPException(status_code=400, detail="inspection and analysis are required")
    return {
        "recommendation": run_recommendation(request.inspection, request.analysis),
    }


@router.post("/brain")
async def visualize_brain(
    request: VisualizeBrainItemsRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    """Full Layer 1 pipeline in one call."""
    await require_chat_user(http_request, credentials)
    items = _items_to_dicts(request.items)
    if not items:
        raise HTTPException(status_code=400, detail="items are required")
    return run_full_brain(items)


@router.get("/themes")
async def visualize_list_themes():
    return {"themes": list_themes()}


@router.get("/layouts")
async def visualize_list_layouts():
    return {"layouts": list_layouts()}


@router.post("/start", response_model=VisualizeStartResponse)
async def visualize_start(
    request: VisualizeStartRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    chat_user = await require_chat_user(
        http_request,
        credentials,
        session_id=request.chat_session_id,
    )
    items = _items_to_dicts(request.items)
    session = create_session(
        user_id=chat_user.id if chat_user else None,
        items=items,
        chat_session_id=request.chat_session_id,
    )
    intro = initial_response(items)
    brain = None
    if items:
        brain = run_full_brain(items)
        update_session(
            session.session_id,
            brain_inspection=brain.get("inspection"),
            brain_analysis=brain.get("analysis"),
            brain_recommendation=brain.get("recommendation"),
        )
    return VisualizeStartResponse(
        session_id=session.session_id,
        greeting=intro["greeting"],
        actions=intro.get("actions") or DEFAULT_OUTPUT_ACTIONS,
        item_count=intro["item_count"],
        brain=brain,
    )


@router.post("/build", response_model=VisualizeBuildResponse)
async def visualize_build(
    request: VisualizeBuildRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    """Layer 2: build PDF/Excel directly from cached brain + UI options (no Claude loop)."""
    chat_user = await require_chat_user(http_request, credentials)
    session = await _require_session(
        request.session_id,
        chat_user.id if chat_user else None,
    )
    result = execute_direct_build(
        session,
        output_format=request.format,
        theme=request.theme,
        layout=request.layout,
        include_logo=request.include_logo,
        page_numbers=request.page_numbers,
        watermark=request.watermark,
        title=request.title,
    )
    if result.get("error"):
        raise HTTPException(
            status_code=400,
            detail=result.get("message") or result["error"],
        )
    fmt = "xlsx" if result.get("excel_url") or result.get("format") == "xlsx" else "pdf"
    return VisualizeBuildResponse(output=result, format=fmt)


@router.post("/chat/stream")
async def visualize_chat_stream(
    request: VisualizeChatRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    chat_user = await require_chat_user(http_request, credentials)
    session = await _require_session(
        request.session_id,
        chat_user.id if chat_user else None,
    )

    if request.items is not None:
        update_session(session.session_id, dropped_items=_items_to_dicts(request.items))

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    refreshed = get_session(session.session_id) or session

    async def generate():
        async for line in stream_visualize_chat(refreshed, message):
            yield line

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/sessions/{session_id}", response_model=VisualizeSessionResponse)
async def visualize_get_session(
    session_id: str,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    chat_user = await require_chat_user(http_request, credentials)
    session = await _require_session(session_id, chat_user.id if chat_user else None)
    brain = None
    if session.brain_recommendation:
        brain = ensure_session_brain(session)
    return VisualizeSessionResponse(
        session_id=session.session_id,
        dropped_items=session.dropped_items,
        output_type=session.output_type,
        last_output=session.last_output,
        message_count=len(session.messages),
        brain=brain,
    )

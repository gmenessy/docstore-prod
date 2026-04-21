"""
API-Routen: Entscheider-Briefing + Synthesis + Export.

- /briefing: 4-Fragen-Synthese fuer Entscheider
- /risks: nur Risiko-Analyse
- /synthesis: Pipeline-Trace (wie entstand das Briefing?)
- /briefing/export/{format}: PPTX / DOCX / PDF Download
"""
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db, get_store_or_404
from app.services.briefing_service import generate_briefing
from app.services.risk_service import analyze_store_risks
from app.services.synthesis_service import get_synthesis_trace
from app.services.briefing_export_service import (
    export_briefing_pptx, export_briefing_docx, export_briefing_pdf,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stores", tags=["Briefing"])


@router.get("/{store_id}/briefing")
async def get_briefing(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Entscheider-Briefing in einem Call."""
    await get_store_or_404(db, store_id)
    briefing = await generate_briefing(db, store_id)
    return briefing


@router.get("/{store_id}/risks")
async def get_risks(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """Nur die Risiko-Analyse."""
    await get_store_or_404(db, store_id)
    return await analyze_store_risks(db, store_id)


@router.get("/{store_id}/synthesis")
async def get_synthesis(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Pipeline-Trace der Briefing-Entstehung.
    Zaehler pro Stufe + Verbindungen zwischen Stufen.
    """
    await get_store_or_404(db, store_id)
    return await get_synthesis_trace(db, store_id)


@router.get("/{store_id}/briefing/export/{fmt}")
async def export_briefing(
    store_id: str,
    fmt: str,
    db: AsyncSession = Depends(get_db),
    auth: str = Depends(verify_api_key),
):
    """
    Briefing als Datei herunterladen.
    fmt: pptx | docx | pdf
    """
    await get_store_or_404(db, store_id)
    briefing = await generate_briefing(db, store_id)

    fmt = fmt.lower()
    store_name = briefing.get("store", {}).get("name", "Briefing").replace(" ", "_")

    if fmt == "pptx":
        data = export_briefing_pptx(briefing)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f'attachment; filename="Briefing_{store_name}.pptx"'},
        )
    elif fmt == "docx":
        data = export_briefing_docx(briefing)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="Briefing_{store_name}.docx"'},
        )
    elif fmt == "pdf":
        data = export_briefing_pdf(briefing)
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="Briefing_{store_name}.pdf"'},
        )
    else:
        return {"error": f"Format '{fmt}' nicht unterstuetzt. Erlaubt: pptx, docx, pdf"}


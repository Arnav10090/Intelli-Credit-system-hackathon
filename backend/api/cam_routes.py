"""
api/cam_routes.py — CAM document generation and download endpoints.
Full implementation: Step 7 (llm_narrator.py + doc_builder.py).
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session
from config import OUTPUT_DIR

router = APIRouter()


@router.post("/cases/{case_id}/cam", summary="Generate Credit Appraisal Memo")
async def generate_cam(case_id: str, session: AsyncSession = Depends(get_session)):
    """
    Triggers CAM generation. Requires scoring to be complete.
    LLM generates narrative sections; python-docx assembles the Word document.
    Returns download URL for the .docx file.
    Full implementation: Step 7.
    """
    raise HTTPException(status_code=501, detail="CAM generator: implemented in Step 7")


@router.get("/cases/{case_id}/cam/download", summary="Download generated CAM document")
async def download_cam(case_id: str, session: AsyncSession = Depends(get_session)):
    """
    Returns the generated CAM .docx file as a file download.
    Returns 404 if CAM has not been generated yet.
    """
    cam_path = OUTPUT_DIR / f"{case_id}_CAM.docx"
    if not cam_path.exists():
        raise HTTPException(status_code=404, detail="CAM document not found. Run /cam first.")
    return FileResponse(
        path=str(cam_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"CreditAppraisalMemo_{case_id[:8]}.docx",
    )
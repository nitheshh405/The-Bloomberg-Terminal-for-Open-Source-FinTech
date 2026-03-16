from fastapi import APIRouter
from pathlib import Path

router = APIRouter()
REPORTS_DIR = Path("automation/reports")


@router.get("/reports")
async def list_reports():
    """List all generated weekly intelligence reports."""
    if not REPORTS_DIR.exists():
        return []
    reports = sorted(REPORTS_DIR.glob("*-weekly-intelligence.md"), reverse=True)
    return [
        {
            "filename": r.name,
            "date": r.name.split("-weekly-")[0],
            "size_bytes": r.stat().st_size,
        }
        for r in reports[:52]  # last 52 weeks
    ]


@router.get("/reports/{date}")
async def get_report(date: str):
    """Return the Markdown content of a specific report."""
    from fastapi import HTTPException
    path = REPORTS_DIR / f"{date}-weekly-intelligence.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return {"date": date, "content": path.read_text(encoding="utf-8")}

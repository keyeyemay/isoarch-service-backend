"""The same SPA shell serves all views; data and actions use JSON APIs."""
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(include_in_schema=False)


@router.get("/")
@router.get("/api/pages/isotopic_signatures/list", name="isotopic_signatures_list")
@router.get("/api/pages/isotopic_signatures/feed/{isotopic_signature_id}", name="isotopic_signatures_feed")
@router.get("/api/pages/isotopic_signatures/draft", name="isotopic_signatures_draft")
@router.get("/api/pages/isotopic_signatures/unavailable", name="isotopic_signatures_unavailable")
@router.get("/login", name="login_page")
def spa(isotopic_signature_id: int | None = None):
    return FileResponse("templates/spa.html", headers={"Cache-Control": "no-cache"})

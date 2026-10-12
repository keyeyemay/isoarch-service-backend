from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from db.session import get_db
from repositories.isotopic_signatures import soft_delete
from services import isotopic_signatures as service

router = APIRouter(prefix="/isotopic_signatures")
templates = Jinja2Templates(directory="templates")


@router.get("/list", name="isotopic_signatures_list")
def get_isotopic_signatures(request: Request, c13_max: str = "", filter: str = "", db: Session = Depends(get_db)):
    return templates.TemplateResponse(request=request, name="tiles.html", context=service.catalog_context(db, c13_max, filter))


@router.get("/feed/{isotopic_signature_id}", name="isotopic_signatures_feed")
def get_isotopic_signature_feed(request: Request, isotopic_signature_id: int, db: Session = Depends(get_db)):
    name, context, status_code = service.feed_context(db, isotopic_signature_id)
    return templates.TemplateResponse(request=request, name=name, context=context, status_code=status_code)


@router.get("/draft", name="isotopic_signatures_draft")
def get_isotopic_signature_draft(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request=request, name="add.html", context=service.draft_context(db))


@router.post("/draft", name="isotopic_signatures_create")
def create_isotopic_signature_draft(request: Request, title: str = Form(...), db: Session = Depends(get_db)):
    service.create_draft(db, title)
    return RedirectResponse(request.url_for("isotopic_signatures_draft"), status_code=303)


@router.post("/draft/publish", name="isotopic_signatures_publish")
def publish_isotopic_signature_draft(request: Request, description: str = Form(...),
                                    delta_n15: float = Form(...), delta_c13: float = Form(...), db: Session = Depends(get_db)):
    record_id = service.publish_draft(db, description, delta_n15, delta_c13)
    return RedirectResponse(request.url_for("isotopic_signatures_feed", isotopic_signature_id=record_id), status_code=303)


@router.post("/{isotopic_signature_id}/delete", name="isotopic_signatures_delete")
def delete_isotopic_signature(request: Request, isotopic_signature_id: int):
    soft_delete(isotopic_signature_id)
    return RedirectResponse(request.url_for("isotopic_signatures_list"), status_code=303)

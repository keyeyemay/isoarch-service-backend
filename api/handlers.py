from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from db.session import get_db
from api.dependencies import get_current_user
from models.user import User
from services import isotopic_signatures as service
from services.presentation import isotopic_signature_display
from repositories.isotopic_signatures import first_published
from core.config import DEFAULT_IMAGE_URL, DEFAULT_VIDEO_URL

router = APIRouter(prefix="/api/pages/isotopic_signatures", tags=["HTML pages"])
templates = Jinja2Templates(directory="templates")


def navigation(db):
    first = first_published(db)
    return {"feed_entry_id": first.id if first else None}


@router.get("/list", name="isotopic_signatures_list", include_in_schema=False)
def get_isotopic_signatures(request: Request, c13_max: float | None = None, filter: str = "",
                           db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    context = navigation(db)
    context.update(isotopic_signatures=[isotopic_signature_display(s, current_user.id)
                   for s in service.list_services(db, c13_max, filter)],
                   c13_max=c13_max if c13_max is not None else -10, is_filtered=c13_max is not None or bool(filter))
    return templates.TemplateResponse(request=request, name="tiles.html", context=context)


@router.get("/feed/{isotopic_signature_id}", name="isotopic_signatures_feed", include_in_schema=False)
def get_isotopic_signature_feed(request: Request, isotopic_signature_id: int, next: bool = False,
                               db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        record = service.get_feed(db, isotopic_signature_id, next)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        # Never expose even the title or ID of a deleted/private/missing record.
        return templates.TemplateResponse(request=request, name="deleted.html", context=navigation(db), status_code=404)
    return templates.TemplateResponse(request=request, name="feed.html", context={
        **navigation(db), "isotopic_signature": isotopic_signature_display(record, current_user.id)})


@router.get("/draft", name="isotopic_signatures_draft", include_in_schema=False)
def get_isotopic_signature_draft(request: Request, db: Session = Depends(get_db),
                                current_user: User = Depends(get_current_user)):
    draft = service.get_draft(db, current_user.id)
    return templates.TemplateResponse(request=request, name="add.html", context={**navigation(db),
        "draft": isotopic_signature_display(draft, current_user.id) if draft else None,
        "has_draft": draft is not None, "default_image_url": DEFAULT_IMAGE_URL,
        "default_video_url": DEFAULT_VIDEO_URL})


@router.get("/unavailable", name="isotopic_signatures_unavailable", include_in_schema=False)
def unavailable(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="deleted.html", context=navigation(db), status_code=404)

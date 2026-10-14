from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Response
from sqlalchemy.orm import Session
from api.schemas import ServiceResponse, ServiceDraftResponse, PublishRequest, LikeRequest
from db.session import get_db
from models.user import User
from api.dependencies import get_current_user
from services import isotopic_signatures as service
from services.presentation import isotopic_signature_display

router = APIRouter(prefix="/api/services", tags=["Services API"])


@router.get("", response_model=list[ServiceResponse])
def get_services(c13_max: float | None = None, filter: str = "", db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    return [isotopic_signature_display(s, current_user.id) for s in service.list_services(db, c13_max, filter)]


@router.get("/feed", response_model=ServiceResponse)
def get_feed(id: int | None = None, next: bool = False, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    return isotopic_signature_display(service.get_feed(db, id, next), current_user.id)


@router.get("/draft", response_model=ServiceDraftResponse | None)
def get_draft(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return service.get_draft(db, current_user.id)


async def validate_create_fields(request: Request):
    form = await request.form()
    if set(form) - {"title", "image", "video"}:
        raise HTTPException(422, "Only title, image and video may be supplied")
    if any(len(form.getlist(key)) != 1 for key in form):
        raise HTTPException(422, "Duplicate form fields are not allowed")


@router.post("", response_model=ServiceDraftResponse, status_code=201,
             dependencies=[Depends(validate_create_fields)])
def create_draft(title: str = Form(...), image: UploadFile = File(...), video: UploadFile = File(...),
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return service.create_draft(db, current_user.id, title, image, video)


@router.put("/{id}", response_model=ServiceResponse)
def publish_draft(id: int, pub_data: PublishRequest, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    return isotopic_signature_display(service.publish_draft(db, id, current_user.id, pub_data), current_user.id)


@router.delete("/{id}", status_code=204)
def delete_service(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service.delete_service(db, id, current_user.id)
    return Response(status_code=204)


@router.post("/{id}/like")
def toggle_like(id: int, req: LikeRequest, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    return service.toggle_like(db, id, current_user.id, req.like)

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Response, Query
from sqlalchemy.orm import Session
from api.schemas import ServiceResponse, ServiceDraftResponse, PublishRequest, LikeRequest, LikeResponse
from db.session import get_db
from models.user import User
from api.dependencies import get_current_user, get_optional_user
from services import isotopic_signatures as service
from services.presentation import isotopic_signature_display

router = APIRouter(tags=["Изотопные исследования"])
public_security = {"security": [{}, {"SessionCookie": []}]}
protected_responses = {401: {"description": "Требуется вход"}, 403: {"description": "Только автор может изменить запись"},
                       404: {"description": "Запись недоступна"}, 409: {"description": "Конфликт состояния"}}


@router.get("", response_model=list[ServiceResponse], summary="Опубликованные услуги с фильтрацией", openapi_extra=public_security)
def get_services(c13_max: float | None = Query(None, allow_inf_nan=False, description="Верхний порог δ¹³C (‰)"),
                 filter: str = Query("", max_length=255, description="Поиск по названию"), db: Session = Depends(get_db),
                 current_user: User | None = Depends(get_optional_user)):
    """Публичный список. Для гостя is_creator/is_liked=0; для сессии — персональные флаги 0/1."""
    return [isotopic_signature_display(s, current_user.id if current_user else None)
            for s in service.list_services(db, c13_max, filter)]


@router.get("/feed", response_model=ServiceResponse, summary="Первая публикация ленты",
            openapi_extra=public_security,
            responses={404: {"description": "Лента пуста"}})
def get_feed(db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    """Публичная лента; черновики и удалённые записи скрыты."""
    return isotopic_signature_display(service.get_feed(db), current_user.id if current_user else None)


@router.get("/feed/{id}", response_model=ServiceResponse, summary="Публикация или следующая запись ленты",
            openapi_extra=public_security,
            responses={404: {"description": "Публикация недоступна"}})
def get_feed_by_id(id: int, next: bool = Query(False, description="Перейти к следующей публикации по кругу"),
                   db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    """Выдать опубликованную запись; next=true переводит к следующей по ID с возвратом к первой."""
    return isotopic_signature_display(service.get_feed(db, id, next), current_user.id if current_user else None)


@router.get("/draft", response_model=ServiceDraftResponse | None, summary="Собственный черновик по сессии",
            responses={401: {"description": "Требуется вход"}})
def get_draft(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Единственный черновик текущего пользователя либо null. ID пользователя не принимается."""
    draft = service.get_draft(db, current_user.id)
    return isotopic_signature_display(draft, current_user.id) if draft else None


async def validate_create_fields(request: Request):
    form = await request.form()
    if set(form) - {"title", "image", "video"}:
        raise HTTPException(422, "Only title, image and video may be supplied")
    if any(len(form.getlist(key)) != 1 for key in form):
        raise HTTPException(422, "Duplicate form fields are not allowed")


@router.post("", response_model=ServiceDraftResponse, status_code=201,
             dependencies=[Depends(get_current_user), Depends(validate_create_fields)],
             summary="Создать черновик с фото и коротким видео", responses=protected_responses)
def create_draft(title: str = Form(..., description="Название исследования"),
                 image: UploadFile = File(..., description="PNG/JPEG/WebP до 10 МиБ"),
                 video: UploadFile = File(..., description="MP4 до 64 МиБ, до 60 секунд"),
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Автор определяется сессией. Проверить оба бинарных файла, загрузить в MinIO, сохранить черновик."""
    draft = service.create_draft(db, current_user.id, title, image, video)
    return isotopic_signature_display(draft, current_user.id)


@router.put("/{id}", response_model=ServiceResponse, summary="Опубликовать или обновить собственную запись",
            responses=protected_responses)
def publish_draft(id: int, pub_data: PublishRequest, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    """Опубликовать черновик или обновить публикацию. Повторный PUT сохраняет дату публикации; чужие и удалённые записи недоступны."""
    return isotopic_signature_display(service.publish_draft(db, id, current_user.id, pub_data), current_user.id)


@router.delete("/{id}", status_code=204, summary="Логически удалить собственную услугу", responses=protected_responses)
def delete_service(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Только автор. Строка, лайки и файлы сохраняются; статус меняется на deleted."""
    service.delete_service(db, id, current_user.id)
    return Response(status_code=204)


@router.post("/{id}/like", response_model=LikeResponse, summary="Поставить (1) или снять (0) лайк",
             responses={401: {"description": "Требуется вход"}, 404: {"description": "Публикация недоступна"}})
def toggle_like(id: int, req: LikeRequest, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    """Идемпотентный лайк текущего пользователя; только для опубликованных услуг."""
    return service.toggle_like(db, id, current_user.id, req.like)


# Keep LR3 clients working; canonical routes above are shown in Swagger.
router.add_api_route("/", get_services, methods=["GET"], response_model=list[ServiceResponse], include_in_schema=False)
router.add_api_route("/", create_draft, methods=["POST"], response_model=ServiceDraftResponse, status_code=201,
                     dependencies=[Depends(get_current_user), Depends(validate_create_fields)], include_in_schema=False)
router.add_api_route("/{id}/publish", publish_draft, methods=["PUT"], response_model=ServiceResponse, include_in_schema=False)

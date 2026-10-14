from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

from api.handlers import router
from api.users_api import router as users_api_router
from api.services_api import router as services_api_router
from db.seed import seed_database, seed_media
from db.migrate import upgrade_database
from core.minio_client import init_minio
from core.redis_client import init_redis, redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Автоматическая инициализация таблиц БД и первичное сидирование при старте
    upgrade_database()
    init_minio()
    init_redis()
    seed_database()
    seed_media()
    try:
        yield
    finally:
        redis_client.close()


app = FastAPI(title="IsoArch — Изотопные сигнатуры", version="4.0.0", lifespan=lifespan, docs_url=None,
              description="ЛР4. Публичное чтение; черновики и изменения требуют cookie-сессии. "
                          "Сначала выполните POST /auth/login. Браузер отправляет cookie автоматически. "
                          "В Postman: Cookie: session_id=<UUID> из Set-Cookie. "
                          "Регистрация и вход доступны гостям. Статус операции задаёт HTTP-код; "
                          "поле status услуги обозначает её состояние в предметной области.")


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Invalid input may contain Infinity or secrets; return only safe diagnostics.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]})

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)
app.include_router(users_api_router)
app.include_router(services_api_router, prefix="/services")
app.include_router(services_api_router, prefix="/api/services", include_in_schema=False)


@app.get("/docs", include_in_schema=False)
def swagger_docs():
    """Serve Swagger locally so the demonstration does not depend on a CDN."""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url, title=f"{app.title} — Swagger UI",
        swagger_js_url="/static/vendor/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/vendor/swagger-ui/swagger-ui.css",
        swagger_favicon_url="/static/vendor/swagger-ui/favicon-32x32.png",
    )


@app.get("/api/docs", include_in_schema=False)
def legacy_docs():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/docs")


@app.middleware("http")
async def private_cache_control(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/services", "/api/services", "/auth", "/api/users")):
        response.headers["Cache-Control"] = "no-store"
    return response

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

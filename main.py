from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.handlers import router
from api.users_api import router as users_api_router
from api.services_api import router as services_api_router
from db.seed import seed_database, seed_media
from db.migrate import upgrade_database
from core.minio_client import init_minio


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Автоматическая инициализация таблиц БД и первичное сидирование при старте
    upgrade_database()
    init_minio()
    seed_database()
    seed_media()
    yield


app = FastAPI(title="IsoArch — Изотопные сигнатуры", lifespan=lifespan,
              docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json",
              swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect")


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
app.include_router(services_api_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

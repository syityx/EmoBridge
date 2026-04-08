from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.admin import router as admin_router
from core.config import get_settings


settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(title="EmoBridge API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(admin_router)
    return app


app = create_app()


def main() -> None:
    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=False)


if __name__ == "__main__":
    main()
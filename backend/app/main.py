import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, floor_plans, insights, misc, projects, videos
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.core.ratelimit import RateLimitMiddleware

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        import app.models  # noqa: F401
        from app.core.db import Base, add_missing_columns, engine

        Base.metadata.create_all(engine)
        add_missing_columns(engine)
    if settings.auto_seed:
        from app.seed.seed import run

        run()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    install_error_handlers(app)
    for r in (auth.router, projects.router, floor_plans.router, misc.router, insights.router, videos.router):
        app.include_router(r)

    @app.get("/health")
    def health():
        return {"status": "ok", "ai_provider": settings.ai_provider, "job_mode": settings.job_mode}

    return app


app = create_app()

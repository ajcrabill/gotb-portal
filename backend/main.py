from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from esb.core.config import settings
from esb.core.database import init_db
from esb.core.logging import configure_logging
from esb.routers import health
from esb.routers import auth as auth_router
from esb.routers import irr as irr_router
from esb.routers import assessment as assessment_router

configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("esb_portal.startup", environment=settings.environment)
    await init_db()
    from esb.core.database import AsyncSessionLocal
    from esb.services.scoring import seed_initial_config
    async with AsyncSessionLocal() as db:
        await seed_initial_config(db)
        await db.commit()
    yield
    log.info("esb_portal.shutdown")


app = FastAPI(
    title="ESB Portal API",
    version="0.1.0",
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.include_router(health.router)
app.include_router(auth_router.router)
app.include_router(irr_router.router)
app.include_router(assessment_router.router)

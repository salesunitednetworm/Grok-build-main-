from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import settings
from app.db import init_db
from app.routers.homes import router as homes_router
from app.routers.projects import router as projects_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.artifact_root.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(
    title="Home Energy Modeling Platform",
    version=__version__,
    description=(
        "Canonical building model, HPXML authoring, and OpenStudio-HPXML / EnergyPlus jobs. "
        "This software is not DOE HOMES approved. Design loads are preliminary."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(homes_router)
app.include_router(projects_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}

"""The FastAPI application."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import tomllib
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI

from app.afk import routes as afk_routes
from app.alerts import routes as alert_routes
from app.auth import require_internal
from app.automod import routes as automod_routes
from app.bear_trap import routes as bear_trap_routes
from app.config import Settings
from app.dashboard import routes as dashboard_routes
from app.economy import routes as economy_routes
from app.errors import ERROR_RESPONSES, install_error_handlers
from app.giveaways import routes as giveaway_routes
from app.greetings import routes as greeting_routes
from app.leveling import routes as leveling_routes
from app.log import routes as log_routes
from app.moderation import routes as moderation_routes
from app.settings import routes as settings_routes
from app.shop import routes as shop_routes
from app.snapshots import routes as snapshot_routes
from app.starboard import routes as starboard_routes
from app.state import AppState, build_state
from app.status import routes as status_routes
from app.tickets import routes as ticket_routes

__all__ = ("app", "create_app")

type StateFactory = Callable[[Settings], AbstractAsyncContextManager[AppState]]


def _version() -> str:
	"""Read the API's version from ``pyproject.toml``.

	Returns:
		The ``project.version`` value.
	"""
	pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
	return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]


def create_app(config: Settings | None = None, state_factory: StateFactory = build_state) -> FastAPI:
	"""Build the API app.

	Args:
		config: The configuration. Read from the environment at startup if omitted.
		state_factory: Opens the app state for the app's lifetime.

	Returns:
		The app.
	"""

	@asynccontextmanager
	async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
		"""Hold the app state open while the app runs.

		Args:
			app: The app.

		Yields:
			Nothing. The state is on ``app.state.fm01``. The status sampler runs meanwhile, if enabled.
		"""
		async with state_factory(config or Settings.from_env()) as state:
			app.state.fm01 = state
			sampler = asyncio.create_task(state.status.run_sampler()) if state.config.status_sampler else None
			try:
				yield
			finally:
				if sampler is not None:
					sampler.cancel()
					with contextlib.suppress(asyncio.CancelledError):
						await sampler

	app = FastAPI(
		title="fm01 API",
		version=_version(),
		lifespan=lifespan,
		responses=ERROR_RESPONSES,
		generate_unique_id_function=lambda route: route.name,  # readable operation names in the generated TS
	)
	install_error_handlers(app)

	internal = APIRouter(prefix="/internal", dependencies=[Depends(require_internal)])
	internal.include_router(economy_routes.internal)
	internal.include_router(settings_routes.internal)
	internal.include_router(bear_trap_routes.internal)
	internal.include_router(starboard_routes.internal)
	for routes in (
		greeting_routes,
		automod_routes,
		log_routes,
		moderation_routes,
		ticket_routes,
		leveling_routes,
		afk_routes,
		snapshot_routes,
		shop_routes,
		giveaway_routes,
		alert_routes,
	):
		internal.include_router(routes.internal)

	dashboard = APIRouter(prefix="/dashboard")
	dashboard.include_router(dashboard_routes.router)
	dashboard.include_router(settings_routes.dashboard)
	dashboard.include_router(bear_trap_routes.dashboard)
	dashboard.include_router(starboard_routes.dashboard)

	public = APIRouter(prefix="/public")
	public.include_router(status_routes.public)

	app.include_router(internal, tags=["internal"])
	app.include_router(dashboard, tags=["dashboard"])
	app.include_router(public, tags=["public"])

	@app.get("/health", tags=["health"])
	async def health() -> dict[str, str]:
		"""Report that the API is up.

		\f
		Returns:
			``{"status": "ok"}``.
		"""
		return {"status": "ok"}

	return app


def _app() -> FastAPI:
	"""Build the app Uvicorn serves.

	Returns:
		The app, with ``.env`` loaded and logging set up.
	"""
	load_dotenv()
	logging.basicConfig(level=logging.INFO)
	return create_app()


app = _app()
"""The ASGI entry point (``uvicorn app.main:app``)."""

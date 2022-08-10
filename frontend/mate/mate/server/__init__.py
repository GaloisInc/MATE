"""Initialization logic, callbacks, and routines for the MATE REST API server."""

import json
import logging
from typing import Final

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

import mate.server.api.analyses as analyses_routes
import mate.server.api.artifacts as artifacts_routes
import mate.server.api.builds as builds_routes
import mate.server.api.compilations as compilations_routes
import mate.server.api.graphs.routes as graph_routes
import mate.server.api.manticore as manticore_routes
import mate.server.api.proxy.routes as proxy_routes
import mate.server.api.status as status_routes
import mate.server.api.types as types_routes
from mate import assertions
from mate.config import MATE_SERVER_CONCURRENCY
from mate.integration.challenge_broker import BrokerError
from mate.logging import logger
from mate_query import db, storage

_API_V1_PREFIX: Final[str] = "/api/v1"


async def logging_dependency(request: Request) -> None:
    logger.setLevel(logging.DEBUG)
    try:
        json_payload = request._json
    except:
        json_payload = None
    try:
        query_params = request._query_params
    except:
        query_params = None

    request_log = {
        "method": str(request.method),
        "url": str(request.url),
        "json_payload": str(json_payload),
        "query_params": str(query_params),
    }
    logger.debug(f"REQUEST: {json.dumps(request_log)}")


api = FastAPI(openapi_url="/api/openapi.json", docs_url="/api/v1", redoc_url=None)
api.include_router(
    builds_routes.router, prefix=_API_V1_PREFIX, dependencies=[Depends(logging_dependency)]
)
api.include_router(
    compilations_routes.router, prefix=_API_V1_PREFIX, dependencies=[Depends(logging_dependency)]
)
api.include_router(
    artifacts_routes.router, prefix=_API_V1_PREFIX, dependencies=[Depends(logging_dependency)]
)
api.include_router(
    analyses_routes.router, prefix=_API_V1_PREFIX, dependencies=[Depends(logging_dependency)]
)
api.include_router(
    status_routes.router, prefix=_API_V1_PREFIX, dependencies=[Depends(logging_dependency)]
)
api.include_router(
    graph_routes.router, prefix=_API_V1_PREFIX, dependencies=[Depends(logging_dependency)]
)
api.include_router(
    manticore_routes.router, prefix=_API_V1_PREFIX, dependencies=[Depends(logging_dependency)]
)
api.include_router(
    proxy_routes.router, prefix=_API_V1_PREFIX, dependencies=[Depends(logging_dependency)]
)
api.include_router(
    types_routes.router, prefix=_API_V1_PREFIX, dependencies=[Depends(logging_dependency)]
)


@api.on_event("startup")
def initialize_db() -> None:
    db.initialize("postgresql://mate@db/mate", create=False)


@api.on_event("startup")
def initialize_storage() -> None:
    storage.initialize("storage:9000")


@api.on_event("startup")
def initialize_poi_analyses() -> None:
    from mate import poi

    poi.initialize()


@api.exception_handler(BrokerError)
def handle_broker_error(_req: Request, exc: BrokerError) -> None:
    return JSONResponse(status_code=503, content={"message": str(exc)})


@api.exception_handler(assertions.RuntimeAssertionError)
def handle_runtime_assertion(_req: Request, exc: assertions.RuntimeAssertionError) -> None:
    return JSONResponse(status_code=500, content={"message": exc.message})


class Server:
    """The managing class for all of the different long-running services."""

    def run(self) -> None:
        logger.debug("Initializing database")
        db.initialize("postgresql://mate@db/mate", create=True)
        logger.debug("Initializing storage")
        initialize_storage()
        logger.debug(f"Starting API server with {MATE_SERVER_CONCURRENCY} workers")
        uvicorn.run(
            "mate.server:api",
            host="0.0.0.0",
            log_level="info",
            workers=MATE_SERVER_CONCURRENCY,
        )

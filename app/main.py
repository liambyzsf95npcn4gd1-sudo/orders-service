"""FastAPI application entrypoint exposing the orders deduplication endpoint."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.client import UpstreamError, fetch_upstream_orders
from app.deduplicator import deduplicate_and_calculate_stats
from app.models import OrdersResponse

app = FastAPI(
    title="Orders Normalizer and Deduplicator Service",
    description="Fetches raw orders from upstream, normalizes Russian phones, deduplicates clients, and returns clean accounting stats.",
    version="1.0.0",
)


@app.exception_handler(UpstreamError)
async def upstream_error_handler(request: Request, exc: UpstreamError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "error": "UpstreamServiceError"},
    )


@app.get(
    "/",
    response_model=OrdersResponse,
    response_model_exclude_unset=False,
    summary="Fetch and normalize orders",
    description="Retrieves raw orders from the upstream API, applies normalization and deduplication, and returns the clients and statistics.",
)
async def get_normalized_orders() -> OrdersResponse:
    """Public GET endpoint at / returning the required JSON directly."""
    raw_orders = await fetch_upstream_orders()
    result = deduplicate_and_calculate_stats(raw_orders)
    return result


@app.get("/health", summary="Health Check")
async def health_check():
    """Service health check endpoint for monitoring and container readiness."""
    return {"status": "ok"}

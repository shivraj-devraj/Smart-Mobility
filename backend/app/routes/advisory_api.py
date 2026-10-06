"""HTTP endpoint for persisted historical corridor advisory information."""

from fastapi import APIRouter, HTTPException, Path

from backend.app.schemas.advisory import CorridorAdvisoryResponse
from backend.app.services.advisory_service import AdvisoryDataError, get_corridor_advisory

router = APIRouter(prefix="/api/advisory", tags=["advisory"])


@router.get(
    "/corridors/{corridor}",
    response_model=CorridorAdvisoryResponse,
    responses={
        404: {"description": "No historical advisory rows exist for this corridor."},
        500: {"description": "Persisted advisory data is unavailable or invalid."},
    },
)
def read_corridor_advisory(
    corridor: str = Path(min_length=1, description="Exact persisted historical corridor name."),
) -> CorridorAdvisoryResponse:
    try:
        return get_corridor_advisory(corridor)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=f"No historical advisory data available for corridor: {corridor}",
        ) from error
    except AdvisoryDataError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

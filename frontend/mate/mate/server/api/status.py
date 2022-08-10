from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class GetStatus(BaseModel):
    status: str


@router.get("/status", response_model=GetStatus)
def status() -> GetStatus:
    return GetStatus(status="pass")

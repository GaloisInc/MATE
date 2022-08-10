from typing import Any, Dict, Optional

from fastapi import APIRouter, Response
from httpx import AsyncClient
from pydantic import BaseModel, Field

router = APIRouter()


class NewNotebookBody(BaseModel):
    copy_from: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    ext: Optional[str] = None
    type_: Optional[str] = Field(None, alias="type")


@router.get("/proxy/_notebook/{path:path}", include_in_schema=False)
async def _proxy_get_request(path: str, response: Response) -> Any:
    async with AsyncClient() as client:
        # "notebook-server" (and port) come from `docker-compose.notebook.yml`
        proxy = await client.get(f"http://notebook-server:8889/{path}")
        response.body = proxy.content
        response.status_code = proxy.status_code
        return response


@router.put("/proxy/_notebook/{path:path}", include_in_schema=False)
async def _proxy_post_request(
    path: str, response: Response, body: Optional[NewNotebookBody] = None
) -> Any:
    async with AsyncClient() as client:
        url = f"http://notebook-server:8889/{path}"
        # "notebook-server" (and port) come from `docker-compose.notebook.yml`
        if body is None:
            proxy = await client.put(url)
        else:
            proxy = await client.put(url, json=body.dict())

        response.body = proxy.content
        response.status_code = proxy.status_code
        return response

import uvicorn
import httpx
from ext import app
from configs import app_config
from fastapi_mcp import FastApiMCP
from utils.logging import setup_logging

mcp = FastApiMCP(
    app,
    include_operations=["html_content_parse"],
    http_client=httpx.AsyncClient(
        base_url=f"http://{app_config.host}:{app_config.port}", timeout=20
    ),
)
mcp.mount_http()

setup_logging()

if __name__ == "__main__":
    uvicorn.run("main:app", host=app_config.host, port=app_config.port, log_config=None)

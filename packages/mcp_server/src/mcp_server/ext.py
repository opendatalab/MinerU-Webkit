import uuid
import traceback
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from apps.html.views import api_router
from configs import model_config
from contextlib import asynccontextmanager
from utils.logging import request_id_var
from apps.html.batch_processor import batch_processor
from utils.custom_response import Response as _Response

from loguru import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    with logger.contextualize(request_id_var="SYSTEM"):
        # --- 启动逻辑 ---
        # 在应用启动时进行自定义校验
        if not model_config.model_path:
            logger.warning(
                "启动异常：配置项 'model_path' 不能为空。请检查环境变量或 .env 文件设置。"
            )
        else:
            # 检查路径是否存在且有效
            from pathlib import Path

            model_file = Path(model_config.model_path)
            if not model_file.exists():
                logger.error(
                    f"启动失败：指定的模型文件不存在于路径 {model_config.model_path}"
                )
            else:
                logger.info("✅ 配置校验通过，应用启动中...")
                await batch_processor.start()
    yield
    with logger.contextualize(request_id_var="SYSTEM"):
        # --- 关闭逻辑 ---
        logger.info("🛑 应用关闭，清理资源...")
        await batch_processor.stop()


app = FastAPI(lifespan=lifespan, redoc_url="/redoc")
app.include_router(router=api_router, prefix="/api")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """
    中间件：为每个请求生成唯一ID，并注入日志上下文和响应头。
    """
    # 1. 尝试从请求头获取现有ID，若无则生成一个新的UUIDv4
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # 2. 将请求ID设置到ContextVar中
    token = request_id_var.set(rid)
    try:
        # 3. 使用loguru的contextualize为当前协程的所有日志添加request_id字段
        with logger.contextualize(request_id_var=rid):
            logger.info(f"{request.method} {request.url.path}")
            response = await call_next(request)
    except Exception:
        with logger.contextualize(request_id_var=rid):
            logger.error(f"{traceback.format_exc()}")
        raise traceback.format_exc()
    finally:
        # 4. 确保在请求处理后清理ContextVar，避免内存泄漏
        request_id_var.reset(token)

    # 5. 将请求ID添加到响应头，方便前端或下游服务追踪
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    全局处理 Pydantic 参数校验错误，并返回统一的 Response 格式。
    """
    errors = exc.errors()
    if errors:
        first_error = errors[0]
        # 将错误位置（如 ('body', 'html_content')）转换为更易读的字符串
        field = " -> ".join(str(loc) for loc in first_error["loc"])
        if len(first_error["loc"]) > 1:
            field = first_error["loc"][1]
        error_message = f"{field}: {first_error['msg']}"
    else:
        error_message = "参数校验失败"

    error_response = _Response(
        code=status.HTTP_402_PAYMENT_REQUIRED,  # 使用 402 状态码
        message=error_message,
        data=None,
    )

    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content=error_response.model_dump(),  # 对于 Pydantic V2，使用 model_dump()
    )

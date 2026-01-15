import traceback
from pathlib import Path

from configs import request_id_var
from configs.response_example import response_example
from fastapi import Form
from loguru import logger
from utils.custom_response import Response
from utils.path_utils import get_proj_root_dir

from . import api_router
from .batch_processor import batch_processor
from .schemas import FileParseRequest, HTMLUrlParseItem


def file_form_to_model(
    compress: bool = Form(..., description="是否压缩转换结果"),
    category: str | None = Form(None, description="上传的文件类型"),
    description: str | None = Form(None, description="描述"),
) -> FileParseRequest:
    """依赖项函数，将分散的表单参数组装成 FileParseRequest 模型."""
    return FileParseRequest(
        compress=compress,
        category=category,
        description=description,
    )


# @api_router.post("/content_parse", operation_id="html_content_parse", responses=response_example)
# async def html_content_parse(params: HTMLContentParseItem):
#     """HTML转Markdown(依赖HTML内容)"""
#     html_content = params.html_content
#     compress = params.compress
#     request_id = request_id_var.get()
#     return await html_content_conversion(html_content, compress, request_id)


@api_router.post("/url_parse", operation_id="html_url_parse", responses=response_example)
async def html_url_parse(params: HTMLUrlParseItem):
    """HTML转Markdown(依赖HTML链接)"""
    logger.info(f"Parsing Params: {params.dict()}")
    file_urls = params.file_urls
    compress = params.compress
    request_id = request_id_var.get()
    file_url_list = [item.model_dump() for item in file_urls]

    local_dir = Path(get_proj_root_dir()) / f"doc/{request_id}"

    try:
        # 异步批处理调用
        batch_result = await batch_processor.add_request(request_id, file_url_list, compress, str(local_dir))

        # 每个请求获得自己专属的结果
        successful_results = batch_result["successful_results"]
        failed_results = batch_result["failed_results"]

        logger.info(f"✅ 请求完成: {request_id}, 总文件数: {len(file_url_list)}, 成功文件: {len(successful_results)}, 失败文件: {len(failed_results)}")

        # 直接返回结果给客户端
        return Response(
            data={
                "request_id": request_id,
                "successful_count": len(successful_results),
                "failed_count": len(failed_results),
                "results": successful_results + failed_results,
            }
        )

    except Exception as e:
        logger.error(f"❌ 请求处理失败 {request_id}: {traceback.format_exc()}")
        return Response(code=500, message=f"处理失败: {str(e)}")


# @api_router.post("/file_parse", operation_id="html_file_parse", responses=response_example)
# async def html_file_parse(file: UploadFile = File(..., description="HTML文件"),
#                           form_data: FileParseRequest = Depends(file_form_to_model)):
#     """HTML转Markdown(依赖HTML文件)"""
#     print(f"app_config: {app_config}")
#     compress = form_data.compress
#     file_extension = Path(file.filename).suffix.lower()
#     allowed_mime_types = ['text/html', 'application/xhtml+xml']
#     if file_extension not in ['.html', '.htm'] or file.content_type not in allowed_mime_types:
#         return Response(code=400, message="文件类型不支持，请上传HTML文件（.html 或 .htm）")
#     content = await file.read()
#     html_content = content.decode('utf-8')
#     request_id = request_id_var.get()
#     return await html_content_conversion(html_content, compress, request_id)

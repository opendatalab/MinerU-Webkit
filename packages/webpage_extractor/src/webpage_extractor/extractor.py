import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

from loguru import logger

from .core.layout_batch_parser import LayoutBatchParser
from .core.tag_mapping import MapItemToHtmlTagsParser


class BatchHtmlExtractor:
    def __init__(self):
        self.map_parser = MapItemToHtmlTagsParser({})
        self.layout_parser = LayoutBatchParser({})


extractor = BatchHtmlExtractor()


def check_and_install_markdown_dependency():
    """检查 mineru-webkit[webpage_converter] 依赖库."""
    try:
        # 尝试导入 mineru_webkit 或相关转换模块
        from webpage_converter.convert import convert_html_to_structured_data

        extractor.convert_html_to_structured_data = convert_html_to_structured_data
        return True
    except ImportError:
        logger.error("未找到 MinerU-Webkit[webpage_converter] 库，请安装依赖，访问项目页面获取：https://github.com/ccprocessor/MinerU-Webkit")
        return False


def process_single_item(typical_data_result, pre_data, enable_markdown_conversion=False):
    """处理单个HTML数据的函数，用于并发执行."""
    try:
        task_data = typical_data_result.copy()
        task_data.update({"html_source": pre_data["html"]})

        parts = extractor.layout_parser.parse(task_data)
        main_html_body = parts["main_html_body"]
        pre_data["is_main_html_extracted"] = True
        pre_data["main_html_body"] = main_html_body
        if enable_markdown_conversion:
            pre_data["main_html_markdown"] = extractor.convert_html_to_structured_data(main_html_body)
    except Exception as e:
        pre_data["is_main_html_extracted"] = False
        pre_data["main_html_body"] = None
        if enable_markdown_conversion:
            pre_data["main_html_markdown"] = None
        pre_data["error"] = str(e)

    return pre_data


def main_html_extractor(typical_data: dict, pre_data_list: dict, enable_markdown: bool = False):
    """批量处理HTML提取任务.

    Args:
        typical_data:
            {
                'typical_raw_tag_html': typical_raw_tag_html,
                'typical_raw_html': typical_raw_tag_html,
                'llm_response': llm_response,
                'html_source': html_source  # 这是会变化的参数
            }
        pre_data_list: HTML字典列表
        enable_markdown: 是否启用 Markdown 转换功能

    Returns:
        list: 包含每个输入对应的main_html的列表
    """
    # 检查 Markdown 依赖
    if enable_markdown:
        logger.info("Markdown 转换功能已启用，检查依赖...")
        dependency_ok = check_and_install_markdown_dependency()
        if not dependency_ok:
            logger.error("错误：Markdown转换功能依赖库不可用，程序退出。")
            sys.exit(1)

    # 映射
    typical_data_result = extractor.map_parser.parse(typical_data)
    # 推广
    typical_data_result.update(
        {
            "dynamic_id_enable": True,
            "dynamic_classid_enable": True,
            "more_noise_enable": True,
        }
    )

    results = []

    # 使用进程池并发处理
    with ProcessPoolExecutor() as executor:
        # 提交所有任务
        future_to_data = {executor.submit(process_single_item, typical_data_result, pre_data, enable_markdown): pre_data for pre_data in pre_data_list}

        # 按完成顺序获取结果
        for future in as_completed(future_to_data):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                failed_data = future_to_data[future]
                failed_data["is_main_html_extracted"] = False
                failed_data["main_html_body"] = None
                if enable_markdown:
                    failed_data["main_html_markdown"] = None
                failed_data["error"] = str(e)
                results.append(failed_data)

    return results

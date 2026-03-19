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


def process_single_item(mapping_data_result, pre_data, enable_markdown_conversion=False):
    """处理单个HTML数据的函数，用于并发执行."""
    try:
        task_data = mapping_data_result.copy()
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


def main_html_mapping(typical_data: dict):
    """mian_html特征映射.

    Args:
        typical_data:
            {
                 # 带item_id的模板原网页
                'typical_raw_tag_html': typical_raw_tag_html,
                 # 模板原网页
                'typical_raw_html': typical_raw_html,
                 # 模型打标字典
                'llm_response': llm_response
            }

    Returns:
        dict: {
                 # 带item_id的模板原网页
                'typical_raw_tag_html': typical_raw_tag_html,
                 # 模板原网页
                'typical_raw_html': typical_raw_html,
                 # 模型打标字典
                'llm_response': llm_response,
                 # 推广原网页
                'html_source': html_source,
                 # similarity between typical main html and html
                'typical_main_html_sim': typical_main_html_sim,
                 # 模版网页提取正文成功标签, bool类型
                'typical_main_html_success': typical_main_html_success,
                 # 相似度计算层数
                'similarity_layer': similarity_layer,
                 # 模版网页提取的正文html
                'typical_main_html': typical_main_html,
                 # 映射模版正文时的文本列表
                'html_target_list': html_target_list,
                 # 映射模版正文树结构的元素字典
                'html_element_dict': html_element_dict,
                 # 用于生成element dict的html
                'typical_dict_html': typical_dict_html,
            }
    """
    mapping_data_result = extractor.map_parser.parse(typical_data)

    return mapping_data_result


def main_html_extractor(mapping_data: dict, pre_data_list: list, enable_markdown: bool = False):
    """mian_html批量推广.

    Args:
        mapping_data:
            Required: 必填参数
            {
                 # 用于生成element dict的html
                'typical_dict_html': typical_dict_html,
                 # 映射模版正文树结构的元素字典
                'html_element_dict': html_element_dict,
                 # 模版网页提取的正文html
                'typical_main_html': typical_main_html,
                 # 相似度计算层数
                'similarity_layer': similarity_layer,
            }
            optional: 可选参数
            {
                 # 动态id开关
                'dynamic_id_enable': False,
                 # 动态classid开关
                'dynamic_classid_enable': False,
                 # 正文噪音开关
                'more_noise_enable': False,
                 # 动态classid相似度阈值
                'dynamic_classid_similarity_threshold': 0.85,
                 # 模型结果都为0
                'llm_response_empty': False,
            }
        pre_data_list: HTML字典列表
            [
                {
                     # 要推广的原网页
                    'html': html,
                    ...，
                },
                ...,
            ]
        enable_markdown: 是否启用 Markdown 转换功能

    Returns:
        list: 包含每个输入对应的main_html的列表
            {
                ...,
                 # 是否推广成功
                'is_main_html_extracted': is_main_html_extracted,
                 # 推广出的正文网页
                'main_html_body': main_html_body,
                 # 推广出的正文网页的Markdown
                'main_html_markdown': main_html_markdown,
            }
    """
    # 检查 Markdown 依赖
    if enable_markdown:
        logger.info("Markdown 转换功能已启用，检查依赖...")
        dependency_ok = check_and_install_markdown_dependency()
        if not dependency_ok:
            logger.error("错误：Markdown转换功能依赖库不可用，程序退出。")
            sys.exit(1)

    # 推广
    mapping_data.update(
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
        future_to_data = {executor.submit(process_single_item, mapping_data, pre_data, enable_markdown): pre_data for pre_data in pre_data_list}

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

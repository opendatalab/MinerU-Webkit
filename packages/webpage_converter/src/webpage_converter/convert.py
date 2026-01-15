import threading
import uuid
from datetime import datetime
from .utils.cfg_reader import load_pipe_tpl
from .convert_chain import ExtractSimpleFactory
from .schemas.datajson import DataJson
from .exception.exception import InvalidOutputFormatException


class PipeTpl:
    NOCLIP = "noclip_html"  # 输入main_html，输出markdown
    NOCLIP_TEST = "noclip_html_test"  # 输入main_html，输出markdown


class ExtractorFactory:
    """线程安全的转换器工厂."""

    # 提取器缓存
    _extractors = {}
    # 线程锁，保证多线程安全
    _lock = threading.Lock()

    @staticmethod
    def get_extractor(pipe_tpl_name: str):
        """获取指定类型的转换器（带缓存，线程安全）

        Args:
            pipe_tpl_name: 管道模板名称，对应 PipeTpl 中的常量

        Returns:
            转换器链实例
        """
        # 双重检查锁定模式，避免不必要的锁竞争
        if pipe_tpl_name not in ExtractorFactory._extractors:
            with ExtractorFactory._lock:
                # 再次检查，防止在获取锁期间其他线程已经创建了实例
                if pipe_tpl_name not in ExtractorFactory._extractors:
                    extractor_cfg = load_pipe_tpl(pipe_tpl_name)
                    chain = ExtractSimpleFactory.create(extractor_cfg)
                    ExtractorFactory._extractors[pipe_tpl_name] = chain

        return ExtractorFactory._extractors[pipe_tpl_name]


def _convert_html(
    html_content: str,
    pipe_tpl: str,
    url: str = "http://www.example.com",
    language: str = "en",
) -> DataJson:
    """内部使用的统一HTML提取方法，返回处理后的DataJson对象.

    Args:
        url: 网页URL
        html_content: 原始HTML内容（或main_html，取决于pipe_tpl）
        pipe_tpl: 处理类型，支持：
            # 只执行第二阶段：
            - PipeTpl.NOCLIP: 从main_html转换为markdown
        language: 语言，可选：'en' 或 'zh'

    Returns:
        DataJson: 处理后的DataJson对象，包含main_html和content_list等信息
    """
    extractor = ExtractorFactory.get_extractor(pipe_tpl)

    input_data_dict = {
        "track_id": str(uuid.uuid4()),
        "url": url,
        "html": html_content,
        "dataset_name": f"webkit-{pipe_tpl}",
        "data_source_category": "HTML",
        "file_bytes": len(html_content),
        "language": language,
        "meta_info": {"input_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
    }

    d = DataJson(input_data_dict)
    return extractor.extract(d)


def convert_html_to_structured_data(
    main_html: str,
    url: str = "http://www.example.com",
    output_format: str = "mm_md",
    language: str = "en",
    use_raw_image_url: bool = True,
) -> str:
    """将main_html转markdown

    Args:
        url: 网页URL
        main_html: 已经抽取的主要HTML内容
        output_format: 输出格式，'md' 或 'mm_md' 或 'plain_md' 或 'json' 或 'txt'
        language: 语言，可选：'en' 或 'zh'
        use_raw_image_url: 是否使用原始图片URL（仅对mm_md格式有效）

    Returns:
        str: 结构化的内容（markdown格式）
    """
    result = _convert_html(main_html, PipeTpl.NOCLIP, url, language)
    content_list = result.get_content_list()

    if output_format == "md":
        result = content_list.to_nlp_md()
    elif output_format == "mm_md":
        result = content_list.to_mm_md(use_raw_image_url=use_raw_image_url)
    elif output_format == "plain_md":
        result = content_list.to_plain_md()
    elif output_format == "json":
        result = content_list.to_json()
    elif output_format == "txt":
        result = content_list.to_txt()
    else:
        raise InvalidOutputFormatException(f"Invalid output format: {output_format}")

    return result



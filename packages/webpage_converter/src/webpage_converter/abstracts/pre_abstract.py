from abc import ABC, abstractmethod

from overrides import override

from ..schemas.datajson import DataJson
from ..utils.file_type_matcher import FileTypeMatcher


class AbstractPreConverter(ABC):
    """实现数据集的预处理 例如，从文件中读取数据，从数据库中读取数据等等."""

    def __init__(self, config: dict, *args, **kwargs):
        """从参数指定的配置中初始化这个流水线链.

        Args:
            config (dict): 配置字典
        """
        self.__config = config

    def pre_convert(self, data_json: DataJson) -> DataJson:
        """实现针对一条输入数据的预处理.

        Args:
            data_json (ContentList): _description_

        Returns:
            dict: _description_
        """
        if self._filter_by_rule(data_json):
            d = self._do_pre_convert(data_json)
            return d
        else:
            return data_json

    @abstractmethod
    def _filter_by_rule(self, data_json: DataJson) -> bool:
        """根据规则过滤content_list.

        Args:
            content_list (DataJson): 判断content_list是否是自己想要拦截处理的数据

        Returns:
            bool: 如果是希望处理的数据，返回True，否则返回False
        """
        raise NotImplementedError("Subclass must implement abstract method")

    @abstractmethod
    def _do_pre_convert(self, data_json: DataJson) -> DataJson:
        """实现真正的数据集预处理.

        Args:
            content_list (ContentList): 需要处理的数据集

        Returns:
            dict: 返回处理后的数据
        """
        raise NotImplementedError("Subclass must implement abstract method")


class BaseRuleFilterPreConverter(AbstractPreConverter):
    """实现一个基础的规则过滤器 例如，根据文件名的后缀拦截数据并进行基础的预处理.

    Args:
        AbstractPreExtractor (_type_): _description_
    """

    def __init__(self, config: dict, *args, **kwargs):
        super().__init__(config, *args, **kwargs)


class BaseFileFormatFilterPreConverter(BaseRuleFilterPreConverter, FileTypeMatcher):
    """实现一个基础的文件格式过滤器 例如，根据文件名的后缀拦截数据并进行基础的预处理.

    Args:
        BaseRuleFilterPreExtractor (_type_): _description_
    """

    def __init__(self, config: dict, *args, **kwargs):
        super().__init__(config, *args, **kwargs)


class NoOpPreConverter(AbstractPreConverter):
    """一个空的预处理器，不做任何处理 用于测试."""

    def __init__(self, config: dict, *args, **kwargs):
        super().__init__(config, *args, **kwargs)

    @override
    def _filter_by_rule(self, data_json: DataJson) -> bool:
        return True

    @override
    def _do_pre_convert(self, data_json: DataJson) -> DataJson:
        return data_json

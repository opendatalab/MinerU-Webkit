import traceback
from typing import List, Union
import commentjson as json
from .exception.exception import (
    ExtractorChainBaseException,
    ExtractorChainConfigException,
    ExtractorChainInputException,
    ExtractorInitException,
    ExtractorNotFoundException,
    LlmWebKitBaseException,
)
from .abstracts.pre_abstract import AbstractPreConverter
from .abstracts.converter_abstract import AbstractConverter
from .abstracts.post_abstract import AbstractPostConverter
from .schemas.datajson import DataJson
from .utils.class_loader import load_python_class_by_name


# ##########################################################
# extractor chain
# ##########################################################
class ExtractorChain:
    """Handles extraction by chaining main_html_parser, pre_extractors,
    extractors and post_extractors."""

    def __init__(self, config: dict):
        """Initialize extractor chain from config.

        Args:
            config (dict): Config dict containing extractor_pipe configuration
        """
        self.__pre_extractors: List[AbstractPreConverter] = []
        self.__extractors: List[AbstractConverter] = []
        self.__post_extractors: List[AbstractPostConverter] = []

        # Get extractor pipe config
        extractor_config = config.get("extractor_pipe", {})

        # Load extractors
        self.__init_main_html_parser(extractor_config)
        self.__load_extractors(extractor_config)

    def extract(self, data: DataJson) -> DataJson:
        """Run the extraction extractor."""
        # Validate input
        self.__validate_extract_input(data)

        try:
            # Pre extractors
            for pre_ext in self.__pre_extractors:
                data = pre_ext.pre_convert(data)
            # Main extractors
            for ext in self.__extractors:
                data = ext.convert(data)

            # Post extractors
            for post_ext in self.__post_extractors:
                data = post_ext.post_convert(data)

        except KeyError as e:
            exc = ExtractorChainInputException(f"Required field missing: {str(e)}")
            exc.dataset_name = data.get_dataset_name()
            exc.traceback_info = traceback.format_exc()
            raise exc
        except ExtractorChainBaseException as e:
            e.dataset_name = data.get_dataset_name()
            e.traceback_info = traceback.format_exc()
            raise
        except LlmWebKitBaseException as e:
            e.dataset_name = data.get_dataset_name()
            e.traceback_info = traceback.format_exc()
            raise
        except Exception as e:
            wrapped = ExtractorChainBaseException(f"Error during extraction: {str(e)}")
            wrapped.dataset_name = data.get_dataset_name()
            wrapped.traceback_info = traceback.format_exc()
            raise wrapped from e

        return data

    def __init_main_html_parser(self, config: dict):
        """Initialize main HTML parser from config."""
        for parser_config in config.get("main_html_parser", []):
            if parser_config and parser_config.get("enable"):
                main_html_parser = self.__create_extractor(parser_config)
                self.__main_html_parser.append(main_html_parser)

    def __load_extractors(self, config: dict):
        """Load extractors from extractor_pipe config."""
        # Load pre extractors
        for pre_config in config.get("pre_extractor", []):
            if pre_config.get("enable"):
                pre_extractor = self.__create_extractor(pre_config)
                self.__pre_extractors.append(pre_extractor)

        # Load main extractors
        for ext_config in config.get("extractor", []):
            if ext_config.get("enable"):
                extractor = self.__create_extractor(ext_config)
                self.__extractors.append(extractor)

        # Load post extractors
        for post_config in config.get("post_extractor", []):
            if post_config.get("enable"):
                post_extractor = self.__create_extractor(post_config)
                self.__post_extractors.append(post_extractor)

    def __create_extractor(
        self, config: dict
    ) -> Union[AbstractPreConverter, AbstractConverter, AbstractPostConverter]:
        """Create extractor instance from config."""
        python_class = config.get("python_class")
        if not python_class:
            raise ExtractorChainConfigException(
                "python_class not specified in extractor config"
            )

        try:
            kwargs = config.get("class_init_kwargs", {})
            return load_python_class_by_name(python_class, config, kwargs)
        except ImportError:
            raise ExtractorNotFoundException(
                f"Extractor class not found: {python_class}"
            )
        except Exception as e:
            raise ExtractorInitException(
                f"Failed to initialize extractor {python_class}: {str(e)}"
            )

    def __validate_extract_input(self, data_json: DataJson):
        """校验一下配置里必须满足的条件，否则抛出异常.

        Args:
            data_json (DataJson): _description_
        """
        self.__validate_input_data_format(data_json)

    def __validate_input_data_format(self, data_json):
        """校验一下输入的data_json对象是否是DataJson对象，否则抛出异常."""
        if not isinstance(data_json, DataJson):
            raise ExtractorChainInputException(
                f"input data is not DataJson object, data type is {type(data_json)}"
            )


class ExtractSimpleFactory:
    """Factory to create ExtractorChain instances."""

    @staticmethod
    def create(config: Union[str, dict]) -> ExtractorChain:
        """Create ExtractorChain from config.

        Args:
            config: Config dict or path to config file

        Returns:
            ExtractorChain instance
        """
        # Load config if file path provided
        if isinstance(config, str):
            with open(config) as f:
                config = json.load(f)

        # Create and return chain
        return ExtractorChain(config)

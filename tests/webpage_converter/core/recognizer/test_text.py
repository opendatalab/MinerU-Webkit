import unittest
from pathlib import Path
from webpage_converter.convert_chain import ExtractSimpleFactory
from webpage_converter.core.recognizer.text import TextParagraphRecognizer
from webpage_converter.schemas.datajson import DataJson
from webpage_converter.utils.cfg_reader import load_pipe_tpl
from webpage_converter.utils.html_utils import html_to_element, element_to_html_unescaped


class TestTextParagraphRecognize(unittest.TestCase):

    def setUp(self):
        self.text_recognize = TextParagraphRecognizer()
        # Config for HTML extraction
        self.config = load_pipe_tpl('noclip_html_test')

    def test_text_1(self):
        """
        测试1  s3://llm-pdf-text-1/qa/quyuan/output/part-67c01310620e-000064.jsonl
        Returns:

        """
        with open(Path(__file__).resolve().parent.parent / 'assets/html/text.html', 'r') as file:
            html_content = file.read()
        assert self.text_recognize._TextParagraphRecognizer__combine_text('知识乱象\n',
                                                                          '中共中央政治局召开会议审议《成-2020年10月16日新闻联播',
                                                                          'zh') == '知识乱象\n中共中央政治局召开会议审议《成-2020年10月16日新闻联播'
        result = self.text_recognize.recognize('http://www.baidu.com', [(html_to_element(html_content), html_to_element(html_content))], html_content)
        assert '知识乱象\\n 中共中央政治局' in element_to_html_unescaped(result[587][0])

    def test_text_2(self):
        """
        测试2  s3://llm-pdf-text-1/qa/quyuan/output/part-67c01310620e-004720.jsonl
        Returns:

        """
        chain = ExtractSimpleFactory.create(self.config)
        self.assertIsNotNone(chain)
        test_data = {
            'track_id': 'text_md',
            'dataset_name': 'text_md',
            'url': 'https://www.aircraftspruce.com/catalog/pnpages/AT108AR-5_32.php',
            'data_source_category': 'HTML',
            'html_name': 'text2.html',
            'main_html_name': 'text2.html',
            'file_bytes': 1000,
            'meta_info': {'input_datetime': '2020-01-01 00:00:00'}
        }
        input_data = DataJson(test_data)
        result = chain.extract(input_data)
        content_md = result.get_content_list().to_mm_md()
        print(repr(content_md))
        # assert 'Selecting Rivet Sets:\n To develop maximum power' in content_md
        with open('/home/PJLAB/houlinfeng/projects/custom_plugins/000.md', 'w', encoding='utf-8') as f:
            f.write(content_md)

    def test_text_1204(self):
        """
        兼容段落可能为None的情况
        Returns:

        """
        chain = ExtractSimpleFactory.create(self.config)
        self.assertIsNotNone(chain)
        test_data = {
            'track_id': 'text_md',
            'dataset_name': 'text_md',
            'url': 'https://br.wikipedia.org/wiki/Faustina_an_Hena%C3%B1',
            'data_source_category': 'HTML',
            'html_name': '000.html',
            'main_html_name': '000.html',
            'file_bytes': 1000,
            'meta_info': {'input_datetime': '2020-01-01 00:00:00'},
            'language': 'en'
        }
        input_data = DataJson(test_data)
        result = chain.extract(input_data)
        content_md = result.get_content_list().to_mm_md(use_raw_image_url=True)
        with open('/home/PJLAB/houlinfeng/projects/custom_plugins/000.md', 'w', encoding='utf-8') as f:
            f.write(content_md)

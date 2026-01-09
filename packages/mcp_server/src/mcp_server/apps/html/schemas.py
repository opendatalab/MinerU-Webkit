import re
import validators
from urllib.parse import quote
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class HTMLContentParseItem(BaseModel):
    html_content: str = Field(None, description="HTML文件内容")
    compress: bool = Field(False, description="是否压缩转换结果")

    @field_validator("html_content")
    def validate_html_content(cls, v: str) -> str:
        """基本的HTML内容验证"""
        if len(v.strip()) == 0:
            raise ValueError("HTML内容不能仅为空白字符")

        # 简单的HTML标签检查（可选）
        if not re.search(r"<[^>]+>", v):
            raise ValueError("内容似乎不包含有效的HTML标签")

        return v


class FileUrlItem(BaseModel):
    file_id: Optional[str] = Field(None, description="文件ID（可选）")
    file_url: str = Field(..., description="文件链接URL")
    url: Optional[str] = Field(None, description="网页URL（可选）")
    name: Optional[str] = Field(None, description="文件名称（可选）")
    type: Optional[str] = Field(None, description="文件类型（可选）")


class HTMLUrlParseItem(BaseModel):
    file_urls: List[FileUrlItem] = Field(..., description="HTML文件链接字典列表")
    compress: bool = Field(False, description="是否压缩转换结果")

    @field_validator("file_urls", mode="before")
    def validate_url_format(cls, v: str) -> str:
        """URL格式验证"""

        for item in v:
            if not isinstance(item, dict):
                raise ValueError("file_urls格式不正确")
            file_url = item.get("file_url")
            if not file_url:
                raise ValueError("缺失file_url字段")
            encoded_file_url = quote(file_url, safe=':/')
            if not isinstance(file_url, str) or not validators.url(encoded_file_url):
                raise ValueError("file_url格式不正确，请提供有效的http或https链接")

            _url = item.get("url")
            if _url:
                encoded_url = quote(_url, safe=':/')
                if not isinstance(_url, str) or not validators.url(encoded_url):
                    raise ValueError("url格式不正确，请提供有效的http或https链接")

        return v


class FileParseRequest(BaseModel):
    """HTML文件解析请求模型"""

    compress: bool = Field(False, description="是否压缩转换结果")
    category: Optional[str] = Field(None, description="上传的文件类型（可选）")
    description: Optional[str] = Field(None, description="描述（可选）")

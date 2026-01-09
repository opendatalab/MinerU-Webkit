import os
import uuid
from pathlib import Path

import requests
from configs import oss_config
from .path_utils import extract_filename_and_ext_from_url
from loguru import logger


def check_mkdir(file_path: str):
    try:
        if not os.path.exists(os.path.join(file_path)):
            os.makedirs(os.path.join(file_path))
        logger.debug(f"mkdir success-{file_path}")
    except Exception as e:
        raise Exception(f"failed mkdir-{file_path}.err:{e}")


def fetch_url(file_url: str, local_dir: str, file_name: str = "") -> str:
    """
    Downloads a file from the given file_url and saves it to the local_path.

    Parameters:
    - file_url (str): The URL of the file to be downloaded.
    - local_dir (str): The path where the file should be saved locally. like /tmp/data
    - file_name (str): The name of file,like hash-sh256

    Returns:
    - local_file_path(str): The path of file. like /tmp/data/a.jpg
    """
    # Check if the directory of the local path exists, create it if not
    check_mkdir(local_dir)

    # use internal endpoint
    file_url = file_url.replace(
        oss_config.cdn_host,
        "https://" + oss_config.bucket + "." + oss_config.end_point + "/",
    )
    file_url = file_url.replace(oss_config.external_end_point, oss_config.end_point)
    logger.debug(f"file_url:{file_url}")

    if file_name:
        local_file_path = os.path.join(local_dir, file_name)
    else:
        _, file_ext = extract_filename_and_ext_from_url(file_url)
        unique_file_name = uuid.uuid4().hex + "." + file_ext
        logger.info(
            f"file_url:{file_url}, file_ext:{file_ext}, unique_file_name:{unique_file_name}"
        )
        local_file_path = os.path.join(local_dir, unique_file_name)

    # Send a GET request to retrieve the file content
    response = requests.get(file_url, stream=True)

    # Check if the request was successful
    if response.status_code == 200:
        # Open the local file in binary write mode
        with open(local_file_path, "wb") as file:
            # Write the response content to the local file in chunks
            for chunk in response.iter_content(chunk_size=1024):
                file.write(chunk)
        logger.debug(
            f"file {file_url} downloaded successfully and saved to: {local_file_path}"
        )
    else:
        logger.debug(f"request failed with status code: {response.status_code}")
        raise Exception(
            f"download file {file_url} failed, status code: {response.status_code} err_msg:{response.text}"
        )
    return local_file_path


def is_html_file(file_path):
    """
    校验文件是否为HTML格式
    使用多种方法确保准确性
    """
    # 方法1: 检查文件扩展名 [9](@ref)
    valid_extensions = {".html", ".htm"}
    file_extension = Path(file_path).suffix.lower()

    if file_extension not in valid_extensions:
        return False

    try:
        with open(file_path, "rb") as f:
            content_start = f.read(1024)  # 读取前1KB内容

        # 使用字节字符串（bytes）进行匹配，因为文件是以二进制模式（'rb'）读取的
        html_content_indicators = [b"<!doctype html", b"<html", b"<head", b"<body"]

        # 检查是否包含任何预定义的HTML标识
        # 读取的是二进制数据，直接在 bytes 内容中进行搜索
        has_html_structure = any(
            indicator in content_start.lower() for indicator in html_content_indicators
        )

        return has_html_structure

    except Exception as e:
        logger.error(f"文件类型校验错误: {e}")
        return False

import os
import zipfile
from pathlib import Path

from loguru import logger


def compress_directory_to_zip(directory_path, output_zip_path):
    """
    压缩指定目录到一个 ZIP 文件。
    :param directory_path: 要压缩的目录路径
    :param output_zip_path: 输出的 ZIP 文件路径
    """
    try:
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, str(Path(directory_path)))
                    zipf.write(file_path, arcname)
        return 0
    except Exception as e:
        logger.exception(e)
        return -1

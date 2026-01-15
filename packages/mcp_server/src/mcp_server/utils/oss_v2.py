import os
import signal
import sys
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlparse

import alibabacloud_oss_v2 as oss
import requests
from configs import oss_config
from loguru import logger
from requests.exceptions import ConnectTimeout, HTTPError, ReadTimeout, RequestException, Timeout
from utils.compress import compress_directory_to_zip

OBJECT_ACL_DEFAULT = "default"
OBJECT_ACL_PRIVATE = "private"
OBJECT_ACL_PUBLIC_READ = "public-read"
OBJECT_ACL_PUBLIC_READ_WRITE = "public-read-write"


@lru_cache
def get_oss_client():
    def get_credentials_wrapper():
        # 返回长期凭证
        return oss.credentials.Credentials(access_key_id=oss_config.ak, access_key_secret=oss_config.sk)

    credentials_provider = oss.credentials.CredentialsProviderFunc(func=get_credentials_wrapper)
    # 加载SDK的默认配置，并设置凭证提供者
    cfg = oss.config.load_default()
    cfg.credentials_provider = credentials_provider

    # 设置应用读写数据的超时时间, 默认值 20秒
    cfg.readwrite_timeout = oss_config.readwrite_timeout

    # 设置配置中的区域信息
    cfg.region = oss_config.region
    # 设置是否使用内网域名访问同地域的OSS资源
    # cfg.use_internal_endpoint = oss_config.use_internal_endpoint

    # 设置是否使用传输加速域名访问同地域的OSS资源
    cfg.use_accelerate_endpoint = oss_config.use_accelerate_endpoint

    client = oss.Client(cfg)

    return client


# Oss客户端
oss_client = get_oss_client()


class UploadTask:
    """上传任务类."""

    def __init__(
        self,
        file_id: str,
        file_url: str,
        url: str,
        local_path: str,
        compress: bool,
        size: int = 0,
    ):
        self.file_id = file_id
        self.file_url = file_url
        self.url = url
        self.local_path = local_path
        self.compress = compress
        self.size = size


class UploadResult:
    """上传结果类."""

    def __init__(self, file_id: str, file_url: str, url: str, success: bool = False, size: int = 0, error_code: int | None = None, error: str | None = None):
        self.file_id = file_id
        self.file_url = file_url
        self.url = url
        self.success = success
        self.size = size
        self.error_code = error_code
        self.error = error

    def to_dict(self):
        """将实例转换为字典."""
        return self.__dict__.copy()


class BatchUploader:
    """批量上传器."""

    def __init__(self, client: oss.Client, bucket: str, max_workers: int = 5):
        self.client = client
        self.bucket = bucket
        self.max_workers = max_workers
        self.stop_thread_event = threading.Event()

    def list_objects(self, file_url_list=None, max_keys: int = 1000) -> list[UploadTask]:
        """列举待上传的所有对象."""
        if file_url_list is None:
            file_url_list = []
        tasks = []

        logger.info(f"待上传的所有文件: {file_url_list}")

        while not self.stop_thread_event.is_set():
            try:
                # 处理列举结果
                for obj in file_url_list:
                    _upload_task = UploadTask(
                        file_id=obj["file_id"],
                        file_url=obj["file_url"],
                        url=obj["url"],
                        local_path=obj["local_path"],
                        compress=obj["compress"],
                        size=0,
                    )
                    tasks.append(_upload_task)
                break
            except Exception as e:
                raise Exception(f"列举对象失败: {str(e)}")

        return tasks

    def upload_file(self, task: UploadTask, local_dir: str):
        """上传文件 file :param task:

        :param local_dir:
        :return:
        """
        start_time = time.time()
        result = UploadResult(file_id=task.file_id, file_url=task.file_url, url=task.url, size=task.size)
        compress = task.compress

        try:
            result_dir = Path(task.local_path).parent
            file_id = task.file_id
            today = datetime.now().strftime("%Y-%m-%d")
            if compress:
                full_local_path = Path(local_dir) / f"{file_id}.zip"
                zip_archive_success = compress_directory_to_zip(result_dir, full_local_path)
                if zip_archive_success == 0:
                    logger.info("压缩成功")
                else:
                    logger.error("压缩失败")
                obj_key = f"{oss_config.root_path}/{today}/{file_id}.zip"
            else:
                file_name = Path(task.local_path).stem
                # full_local_path = Path(result_dir) / f"{file_name}.md"
                # obj_key = f"{oss_config.root_path}/{today}/{file_id}/{file_name}.md"
                full_local_path = Path(result_dir) / "book.html"
                obj_key = f"{oss_config.root_path}/{today}/{file_id}/book.html"

            _resp = oss_client.put_object_from_file(
                oss.PutObjectRequest(
                    bucket=oss_config.bucket,  # 存储空间名称
                    key=obj_key,  # 对象名称
                ),
                str(full_local_path),  # 本地文件路径
            )
            oss_client.put_object_acl(
                oss.PutObjectAclRequest(
                    bucket=oss_config.bucket,  # 存储空间名称
                    key=obj_key,  # 对象键名
                    acl=OBJECT_ACL_PUBLIC_READ,  # 新的ACL值
                )
            )

            # pre_result = oss_client.presign(
            #     oss.GetObjectRequest(
            #         bucket=oss_config.bucket,
            #         key=obj_key,
            #     ),
            #     expires=timedelta(seconds=3600)
            # )

            zip_without_params = urljoin(oss_config.cdn_host, obj_key)

            result.success = True
            result.zip_url = zip_without_params
            result.date = _resp.headers["date"]
        except Exception:
            result.success = False
            result.error_code = 40001
            result.error = traceback.format_exc()

        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"上传文件 {Path(full_local_path).name} 耗时: {duration:.2f} 秒")

        return result

    def batch_upload(self, tasks: list[UploadTask], local_dir: str):
        """执行批量上传."""
        results = []
        completed = 0
        total = len(tasks)

        logger.info(f"开始上传 {total} 个文件，使用 {self.max_workers} 个并发...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有下载任务
            future_to_task = {executor.submit(self.upload_file, task, local_dir): task for task in tasks}

            # 处理完成的任务
            for future in as_completed(future_to_task):
                if self.stop_thread_event.is_set():
                    break

                task = future_to_task[future]
                try:
                    result = future.result()

                    # 显示进度
                    if result.success:
                        logger.info(f"✓ [{completed}/{total} 上传文件] {task.file_url} ({format_bytes(result.size)})")
                    else:
                        logger.error(f"✗ [{completed}/{total} 上传文件] {task.file_url} - 错误: {result.error}")
                        result.error = "上传文件失败"

                    results.append(result.to_dict())
                    completed += 1

                except Exception:
                    result = UploadResult(
                        file_id=task.file_id,
                        file_url=task.file_url,
                        url=task.url,
                        error_code=40002,
                        error="上传文件发生未知错误",
                    )
                    results.append(result.to_dict())
                    completed += 1
                    logger.error(f"✗ [{completed}/{total} 上传文件] {task.file_url} - 异常: {traceback.format_exc()}")

        return results

    def stop(self):
        """停止上传."""
        self.stop_thread_event.set()
        logger.info("\n正在停止上传...")


class DownloadTask:
    """下载任务类."""

    def __init__(self, file_id: str, file_url: str, url: str, local_path: str, size: int):
        self.file_id = file_id
        self.file_url = file_url
        self.url = url
        self.local_path = local_path
        self.size = size


class DownloadResult:
    """下载结果类."""

    def __init__(self, file_id: str, file_url: str, url: str, success: bool = False, size: int = 0, error_code: int | None = None, error: str | None = None):
        self.file_id = file_id
        self.file_url = file_url
        self.url = url
        self.success = success
        self.size = size
        self.error_code = error_code
        self.error = error

    def to_dict(self):
        """将实例转换为字典."""
        return self.__dict__.copy()


class BatchDownloader:
    """批量下载器."""

    def __init__(self, client: oss.Client, bucket: str, max_workers: int = 5):
        self.client = client
        self.bucket = bucket
        self.max_workers = max_workers
        self.stop_thread_event = threading.Event()

    def list_objects(self, file_url_list=None, max_keys: int = 1000) -> list[DownloadTask]:
        """列举待下载的所有对象."""
        if file_url_list is None:
            file_url_list = []
        tasks = []

        logger.info(f"待下载的所有文件: {file_url_list}")

        while not self.stop_thread_event.is_set():
            try:
                # 处理列举结果
                for obj in file_url_list:
                    # 计算本地文件路径
                    _url = obj.get("url")
                    file_url = obj.get("file_url")
                    file_url_without_params = file_url.split("?")[0]
                    file_name = f"{Path(file_url_without_params).suffix}"
                    if not file_name:
                        file_name = ".html"
                    _index = obj.get("file_id")
                    if not _index:
                        _index = str(uuid.uuid4())
                    relative_path = f"{str(_index)}/{str(_index)}{file_name}"
                    _download_task = DownloadTask(file_id=_index, file_url=file_url, url=_url, local_path=relative_path, size=0)
                    tasks.append(_download_task)
                break
            except Exception as e:
                raise Exception(f"列举对象失败: {str(e)}")

        return tasks

    def download_file(self, task: DownloadTask, local_dir: str, stream: bool, encoding: str) -> DownloadResult:
        """下载单个文件."""
        start_time = time.time()
        result = DownloadResult(file_id=task.file_id, file_url=task.file_url, url=task.url, size=task.size)

        # 计算完整的本地文件路径
        full_local_path = os.path.join(local_dir, task.local_path)

        # 创建本地文件目录
        os.makedirs(os.path.dirname(full_local_path), exist_ok=True)

        # 检查文件是否已存在且大小一致（断点续传）
        # if os.path.exists(full_local_path):
        #     local_size = os.path.getsize(full_local_path)
        #     if local_size == task.size:
        #         result.success = True
        #         return result
        result.success = True
        result.local_path = full_local_path

        try:
            parsed_url = urlparse(result.file_url)
            hostname_parts = parsed_url.hostname.split(".")
            if len(hostname_parts) < 4:
                with requests.get(result.file_url, stream=stream, timeout=(1.0, 2.0)) as resp:
                    resp.raise_for_status()  # 自动检查状态码

                    if stream:
                        # 流式下载：分块写入，节省内存，适合大文件
                        content_bytes = bytearray()  # 用于累积字节内容
                        with open(full_local_path, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=8192):
                                f.write(chunk)
                                content_bytes.extend(chunk)  # 累积字节数据
                        # 将累积的字节数据解码为字符串
                        result.html = content_bytes.decode(encoding)
                    else:
                        # 非流式下载：一次性读取内容，适合小文件
                        with open(full_local_path, "wb") as f:
                            content = resp.content
                            f.write(resp.content)
                            result.html = content.decode(encoding)
            else:
                object_key = parsed_url.path.lstrip("/")
                # 创建下载请求
                get_request = oss.GetObjectRequest(bucket=oss_config.bucket, key=object_key)

                # 执行下载
                resp = self.client.get_object(get_request)

                if stream:
                    # 保存文件
                    with open(full_local_path, "wb") as f:
                        content_bytes = bytearray()
                        with resp.body as body_stream:
                            # 分块读取并写入
                            for chunk in body_stream.iter_bytes(block_size=1024 * 1024):  # 1MB块
                                if self.stop_thread_event.is_set():
                                    raise Exception("下载被中断")
                                f.write(chunk)
                                content_bytes.extend(chunk)
                        result.html = content_bytes.decode(encoding)
                else:
                    with open(full_local_path, "wb") as f:
                        content = resp.body.content
                        f.write(content)
                        result.html = content.decode(encoding)
        except ConnectTimeout as e:
            result.success = False
            result.error_code = 10001
            result.error = f"连接服务器超时：{e}"
        except ReadTimeout as e:
            result.success = False
            result.error_code = 10002
            result.error = f"下载文件超时：{e}"
        except HTTPError as e:
            result.success = False
            result.error_code = 10003
            result.error = f"HTTP错误：{resp.status_code}: {e}"
        except Timeout as e:
            result.success = False
            result.error_code = 10004
            result.error = f"请求超时：{e}"
        except RequestException as e:
            result.success = False
            result.error_code = 10005
            result.error = f"网络请求异常：{e}"
        except Exception as e:
            result.success = False
            result.error_code = 10006
            result.error = f"下载失败：{e}"

        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"下载文件 {Path(task.file_url).name} 耗时: {duration:.2f} 秒")

        return result

    def batch_download(
        self,
        tasks: list[DownloadTask],
        local_dir: str,
        stream: bool = False,
        encoding: str = "utf-8",
    ) -> list[DownloadResult]:
        """执行批量下载."""
        results = []
        completed = 0
        total = len(tasks)

        logger.info(f"开始下载 {total} 个文件，使用 {self.max_workers} 个并发...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有下载任务
            future_to_task = {executor.submit(self.download_file, task, local_dir, stream, encoding): task for task in tasks}

            # 处理完成的任务
            for future in as_completed(future_to_task):
                if self.stop_thread_event.is_set():
                    break

                task = future_to_task[future]
                try:
                    result = future.result()

                    # 显示进度
                    if result.success:
                        logger.info(f"✓ [{completed}/{total} 下载文件] {result.file_url} ({format_bytes(result.size)})")
                    else:
                        logger.error(f"✗ [{completed}/{total} 下载文件] {result.file_url} - 错误: {result.error}")
                        result.error = result.error.split("：")[0]

                    results.append(result.to_dict())
                    completed += 1

                except Exception:
                    result = DownloadResult(file_id=task.file_id, file_url=task.file_url, url=task.url, error_code=10007, error="下载文件发生未知错误)")
                    results.append(result.to_dict())
                    completed += 1
                    logger.error(f"✗ [{completed}/{total} 下载文件] {task.file_url} - 异常: {traceback.format_exc()}")

        return results

    def stop(self):
        """停止下载."""
        self.stop_thread_event.set()
        logger.info("\n正在停止下载...")


def format_bytes(bytes_size: int) -> str:
    """格式化字节数为可读格式."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def signal_handler(signum, frame):
    """信号处理器."""
    logger.info(f"\n接收到信号 {signum}，正在停止...")
    if hasattr(signal_handler, "downloader"):
        signal_handler.downloader.stop()
    if hasattr(signal_handler, "uploader"):
        signal_handler.uploader.stop()
    sys.exit(0)


# 创建Oss批量下载器
oss_downloader = BatchDownloader(oss_client, oss_config.bucket, oss_config.workers)
# 设置信号处理器以支持优雅停止
signal_handler.downloader = oss_downloader

# 创建Oss批量上传器
oss_uploader = BatchUploader(oss_client, oss_config.bucket, oss_config.workers)
# 设置信号处理器以支持优雅停止
signal_handler.uploader = oss_uploader

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

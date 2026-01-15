import asyncio
import os
import re
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any

from configs import batch_config, dripper_client
from loguru import logger
from utils.oss_v2 import oss_downloader, oss_uploader
from webpage_converter.convert import PipeTpl, _convert_html


@dataclass
class BatchRequest:
    """批处理请求对象."""

    request_id: str
    file_url_list: list[dict]
    compress: bool
    local_dir: str
    future: asyncio.Future  # 用于异步返回专属结果
    created_at: float = time.time()


class HighPerformanceBatchProcessor:
    """高性能异步批处理器."""

    def __init__(
        self,
        batch_size: int = 15,
        batch_timeout: float = 0.8,
        max_concurrent_batches: int = 2,
    ):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_concurrent_batches = max_concurrent_batches

        # 异步队列和信号量控制
        self.task_queue = asyncio.Queue()
        self.processing_semaphore = asyncio.Semaphore(max_concurrent_batches)
        self._processor_task = None
        self._initialized = False  # 添加初始化状态标志
        # 停止事件
        self._stop_event = asyncio.Event()

    async def start(self):
        """在事件循环运行后手动启动处理器."""
        if not self._initialized:
            self._processor_task = asyncio.create_task(self._batch_processor_worker())
            self._initialized = True

    async def add_request(self, request_id: str, file_url_list: list[dict], compress: bool, local_dir: str) -> Any:
        """
        添加请求到批处理器 - 完全异步非阻塞

        关键特性：每个请求都会获得自己专属的结果
        """
        # 创建Future用于异步返回专属结果
        future = asyncio.Future()
        batch_req = BatchRequest(request_id, file_url_list, compress, local_dir, future)
        # 非阻塞放入队列
        await self.task_queue.put(batch_req)

        # 等待专属结果返回
        return await future

    async def _batch_processor_worker(self):
        """批处理工作器 - 核心积攒逻辑"""
        logger.info("🚀 高性能批处理器已启动")

        # 循环条件：只要停止事件未被设置，就继续工作
        while not self._stop_event.is_set():
            try:
                # 1. 智能收集一批请求
                # logger.info(f"开始收集数据........")
                batch_requests = await self._collect_batch()
                if not batch_requests:
                    # 在等待时也检查停止事件
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=0.01)
                    except TimeoutError:
                        pass
                    continue

                # 2. 如果收集到任务，但此时停止事件已被设置，则不再处理
                if self._stop_event.is_set():
                    logger.info("收到停止信号，放弃处理已收集的批次。")
                    break

                # 3. 使用信号量控制并发批次数量
                async with self.processing_semaphore:
                    await self._process_batch(batch_requests)

            except asyncio.CancelledError:
                logger.info("批处理工作器被取消。")
                break
            except Exception as e:
                logger.error(f"批处理工作器错误: {e}")
                # 发生错误时也可以选择等待一下再继续，避免日志刷屏
                await asyncio.sleep(1)

        logger.info("批处理工作器已停止。")

    async def _collect_batch(self) -> list[BatchRequest]:
        """智能收集一批请求."""
        batch_requests = []
        start_time = time.time()
        timeout_occurred = False

        while len(batch_requests) < self.batch_size and not timeout_occurred and not self._stop_event.is_set():
            elapsed = time.time() - start_time
            if elapsed >= self.batch_timeout:
                # logger.info(f"总时间窗口 {self.batch_timeout} 秒已到，停止收集。")
                break

            remaining_time = max(0.01, self.batch_timeout - elapsed)

            try:
                # 创建需要监听的Future
                get_task_future = asyncio.ensure_future(self.task_queue.get())
                timeout_future = asyncio.ensure_future(asyncio.sleep(remaining_time))
                stop_signal_future = asyncio.ensure_future(self._stop_event.wait())

                # 等待任意一个Future完成
                done, pending = await asyncio.wait(
                    [get_task_future, timeout_future, stop_signal_future],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=remaining_time,  # 添加外层超时控制
                )

                # 精确清理未完成的Future
                for future in [get_task_future, timeout_future, stop_signal_future]:
                    if future not in done and not future.done():
                        future.cancel()
                        try:
                            await future  # 等待取消完成
                        except asyncio.CancelledError:
                            pass

                # 判断完成的事件类型
                if get_task_future in done and not self._stop_event.is_set():
                    try:
                        task = get_task_future.result()
                        batch_requests.append(task)
                        logger.info(f"收到任务 {task.request_id}, 当前批次大小: {len(batch_requests)}")

                        if len(batch_requests) >= self.batch_size:
                            logger.info(f"达到批量大小 {self.batch_size}，立即处理")
                            break
                    except asyncio.CancelledError:
                        logger.warning("任务获取被取消")
                        continue

                elif stop_signal_future in done:
                    logger.info("收集过程中收到停止信号，立即退出。")
                    break

                elif timeout_future in done:
                    logger.info(f"等待超时，停止收集。已收集 {len(batch_requests)} 个任务")
                    timeout_occurred = True

            except asyncio.CancelledError:
                logger.warning("批次收集过程被取消。")
                break
            except Exception as e:
                logger.error(f"在收集任务时发生意外错误: {e}")
                await asyncio.sleep(0.1)  # 错误时短暂休眠
                break
        if batch_requests:
            logger.info(f"批次收集完成，共 {len(batch_requests)} 个任务")
        return batch_requests

    async def _process_batch(self, batch_requests: list[BatchRequest]):
        """处理批次并确保每个请求获得专属结果."""
        try:
            # 合并所有请求的文件进行批量处理
            all_files, request_mapping = self._merge_requests(batch_requests)

            if not all_files:
                return

            # 执行批量处理流程
            batch_results = await self._execute_batch_processing(all_files, batch_requests[0].local_dir)

            # 关键步骤：将批量结果精确分发给每个请求
            self._distribute_results(batch_requests, batch_results, request_mapping)

        except Exception as e:
            logger.error(f"批次处理失败: {e}")
            self._handle_batch_failure(batch_requests, e)

    def _merge_requests(self, batch_requests: list[BatchRequest]):
        """合并请求并建立映射关系."""
        all_files = []
        request_mapping = {}  # 文件到请求的映射

        for batch_req in batch_requests:
            tem_file_id = []
            for file_info in batch_req.file_url_list:
                file_id = file_info.get("file_id")
                if not file_id:
                    file_id = str(uuid.uuid4())
                file_info["file_id"] = file_id
                file_info["compress"] = batch_req.compress
                all_files.append(file_info)
                tem_file_id.append(file_id)
            # 建立唯一映射：request_id -> file_id
            request_mapping[batch_req.request_id] = tem_file_id

        return all_files, request_mapping

    async def _execute_batch_processing(self, file_url_list: list[dict], local_dir: str) -> dict:
        """
        执行批量处理 - 包装您现有的处理逻辑
        保持您现有的下载、推理、转换、上传流程不变
        """
        try:
            failed_results = []
            # ############## 下载文件 ###############
            start_time = time.time()
            download_success = []
            # 列举所有需要下载的对象
            tasks = oss_downloader.list_objects(file_url_list)
            # 批量下载文件
            download_results = oss_downloader.batch_download(tasks, local_dir)
            # 提取成功数据，并根据 file_id 匹配并赋值 html
            id_to_html = {item["file_id"]: item for item in download_results}
            for item in file_url_list:
                file_id = item["file_id"]
                if file_id in id_to_html:
                    item_download = id_to_html[file_id]
                    if item_download["success"]:
                        item["html"] = item_download["html"]
                        download_success.append(item)
                    else:
                        failed_results.append({"file_id": file_id, "file_url": item_download["file_url"], "url": item_download["url"], "success": False, "error_code": item_download["error_code"], "error": item_download["error"]})
            end_time = time.time()
            download_duration = end_time - start_time
            logger.info(f"下载文件总耗时: {download_duration:.2f} 秒")

            # ############## GPU模型推理 ###############
            start_time = time.time()
            token_success_html = []
            extract_results = []
            html_list = []
            try:
                for item in download_success:
                    _html = item["html"]
                    if dripper_client.check_token(_html):
                        token_success_html.append(item)
                        html_list.append(_html)
                    else:
                        failed_results.append({"file_id": item["file_id"], "file_url": item["file_url"], "url": item["url"], "success": False, "error_code": 20002, "error": "HTML token超过模型最大序列长度"})
                logger.error(f"需要推理的HTML数量: {len(html_list)}")
                if html_list:
                    extract_results = dripper_client.process(html_list)
            except Exception as e:
                error_message = str(e)
                target_string = "Model response contains no main content labels"
                if target_string in error_message:
                    logger.error("网页不包含主要内容")
                logger.error(f"模型推理失败: {traceback.format_exc()}")
                # token_success_html = download_success
            logger.error(f"extract_results: {extract_results}")
            for n, _item in enumerate(extract_results):
                token_success_html[n]["main_html"] = decode_http_urls_only(_item.main_html)
            end_time = time.time()
            model_duration = end_time - start_time
            logger.info(f"模型推理结果: {[item.to_dict() for item in extract_results]}")
            logger.info(f"模型推理总耗时: {model_duration:.2f} 秒")
            # ############## HTML转Markdown ###############
            start_time = time.time()
            convert_results = []
            completed = 0
            total = len(token_success_html)
            with ThreadPoolExecutor() as executor:
                future_to_task = {executor.submit(html_content_conversion, task, str(local_dir)): task for task in token_success_html}

                # 处理完成的任务
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        result = future.result()

                        # 显示进度
                        if result.get("success"):
                            logger.info(f"✓ [{completed}/{total} HTML转Markdown] {result.get('file_id', '')}")
                        else:
                            logger.error(f"✗ [{completed}/{total} HTML转Markdown] {result.get('file_id', '')} - 错误: {result.get('error')}")
                            result["error"] = "HTML转Markdown失败"

                        convert_results.append(result)
                        completed += 1

                    except Exception:
                        result = {"file_id": task.get("file_id", ""), "error_code": 30002, "error": "HTML转Markdown发生未知错误"}
                        convert_results.append(result)
                        completed += 1
                        logger.error(f"✗ [{completed}/{total} HTML转Markdown] {task.get('file_id', '')} - 异常: {traceback.format_exc()}")
            # 提取成功数据，并根据 file_id 匹配并赋值 compress
            convert_success = []
            id_to_compress = {item["file_id"]: item["compress"] for item in file_url_list}
            id_to_md = {item["file_id"]: item for item in convert_results}
            for item in convert_results:
                file_id = item["file_id"]
                success = item["success"]
                if success:
                    if file_id in id_to_md:
                        item["compress"] = id_to_compress[file_id]
                        convert_success.append(item)
                else:
                    failed_results.append({"file_id": file_id, "file_url": item["file_url"], "success": False, "error_code": item["error_code"], "error": item["error"]})
            end_time = time.time()
            to_md_duration = end_time - start_time
            logger.info(f"HTML转Markdown总耗时: {to_md_duration:.2f} 秒")
            # ############## 上传文件 ############## #
            start_time = time.time()
            # 列举所有需要上传的对象
            upload_tasks = oss_uploader.list_objects(convert_success)
            # 批量上传文件
            upload_results = oss_uploader.batch_upload(upload_tasks, local_dir)
            end_time = time.time()
            upload_duration = end_time - start_time
            logger.info(f"上传文件总耗时: {upload_duration:.2f} 秒")
            # 提取成功数据
            upload_success = []
            for item in upload_results:
                file_id = item["file_id"]
                success = item["success"]
                if success:
                    upload_success.append(item)
                else:
                    failed_results.append({"file_id": file_id, "file_url": item["file_url"], "success": False, "error_code": item["error_code"], "error": item["error"]})

            batch_results = {
                "successful": upload_success,
                "failed": failed_results,
            }
            logger.info(f"批次总耗时: {download_duration + model_duration + to_md_duration + upload_duration} 秒")
            return batch_results

        except Exception:
            logger.error(f"批量处理执行错误: {traceback.format_exc()}")
            return {}

    def _distribute_results(
        self,
        batch_requests: list[BatchRequest],
        batch_results: dict,
        request_mapping: dict,
    ):
        """将批量结果精确分发给每个请求."""
        # 按请求ID分组结果
        results_by_request = {}
        for batch_req in batch_requests:
            results_by_request[batch_req.request_id] = {
                "successful_results": [],
                "failed_results": [],
                "request_id": batch_req.request_id,
                "compress": batch_req.compress,
            }

        # 将每个文件结果分配给对应的请求
        for batch_res in batch_results.get("successful", []):
            file_id = batch_res.get("file_id")
            found_keys = [key for key, value_list in request_mapping.items() if file_id in value_list]
            for found_key in found_keys:
                if found_key and found_key in results_by_request:
                    results_by_request[found_key]["successful_results"].append(batch_res)

        for batch_res in batch_results.get("failed", []):
            file_id = batch_res.get("file_id")
            found_keys = [key for key, value_list in request_mapping.items() if file_id in value_list]
            for found_key in found_keys:
                if found_key and found_key in results_by_request:
                    results_by_request[found_key]["failed_results"].append(batch_res)

        # 设置每个请求的专属结果
        for batch_req in batch_requests:
            if batch_req.request_id in results_by_request:
                batch_req.future.set_result(results_by_request[batch_req.request_id])
            else:
                batch_req.future.set_exception(Exception("未找到对应结果"))

    def _handle_batch_failure(self, batch_requests: list[BatchRequest], error: Exception):
        """处理批次失败情况."""
        for batch_req in batch_requests:
            if not batch_req.future.done():
                batch_req.future.set_exception(error)

    async def stop(self):
        """停止处理器."""
        if self._processor_task:
            logger.info("正在停止批处理器...")
            # 1. 设置停止事件，通知工作协程主动退出
            self._stop_event.set()

            # 2. 取消任务，作为双重保障
            self._processor_task.cancel()
            try:
                # 等待工作协程处理完取消信号并退出
                await asyncio.wait_for(self._processor_task, timeout=5.0)
                logger.info("批处理器已正常停止。")
            except asyncio.CancelledError:
                logger.info("批处理器任务已被取消。")
            except TimeoutError:
                logger.error("等待批处理器停止超时，可能发生阻塞。")
            finally:
                self._processor_task = None
                self._initialized = False
                self._stop_event.clear()  # 重置事件，以便后续可能的重启


def html_content_conversion(html_dict: dict, local_dir: str):
    """内容转换依赖项，统一处理是否压缩的逻辑。

    参数:
        html_content: 要转换的HTML内容字符串。
        compress: 是否进行压缩转换的布尔值。
        request_id: 请求ID。
        result_dir: 下载文件的保存目录。

    返回:
        一个统一的 Response 对象。
    """
    start_time = time.time()
    file_id = html_dict.get("file_id")
    url = html_dict.get("url")
    convert_result = {"file_id": file_id, "file_url": html_dict["file_url"], "url": url, "local_path": "", "json_path": "", "success": True}

    try:
        main_html = html_dict.get("main_html")
        if not main_html:
            logger.warning(f"{file_id} 未发现 main_html")
            main_html = html_dict.get("html")

        result = _convert_html(main_html, PipeTpl.NOCLIP, url=url)
        content_list = result.get_content_list()
        content_md = content_list.to_mm_md(use_raw_image_url=True)
        content_json = content_list.to_json()

        md_path = Path(local_dir) / f"{file_id}/full.md"
        json_path = Path(local_dir) / f"{file_id}/content_list.json"
        main_html_path = Path(local_dir) / f"{file_id}/main.html"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content_md)
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(content_json)
        with open(main_html_path, "w", encoding="utf-8") as f:
            f.write(main_html)

        convert_result["local_path"] = md_path
        convert_result["json_path"] = json_path

        html_path = Path(local_dir) / f"{file_id}/{file_id}.html"
        if Path.exists(html_path):
            os.remove(html_path)

    except Exception:
        convert_result["success"] = False
        convert_result["error_code"] = 30001
        convert_result["error"] = traceback.format_exc()

    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"HTML转Markdown {Path(html_dict['file_url']).name} 耗时: {duration:.2f} 秒")

    return convert_result


# 全局高性能批处理器实例
batch_processor = HighPerformanceBatchProcessor(
    batch_size=batch_config.batch_size,  # 匹配GPU并行处理能力
    batch_timeout=batch_config.batch_timeout,  # 平衡延迟和吞吐
    max_concurrent_batches=batch_config.max_concurrent_batches,  # 避免GPU过载
)


def decode_http_urls_only(html_str):
    def decode_match(match):
        prefix = match.group(1)  # href=" 或 src="
        url = match.group(2)
        suffix = match.group(3)  # "

        if url.startswith(("http://", "https://", "ftp://", "//")):
            decoded_url = unescape(url)
            return f"{prefix}{decoded_url}{suffix}"
        return match.group(0)

    pattern = r'(href="|src=")(.*?)(")'
    return re.sub(pattern, decode_match, html_str, flags=re.IGNORECASE | re.DOTALL)

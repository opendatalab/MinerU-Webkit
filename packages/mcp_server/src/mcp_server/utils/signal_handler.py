import signal
import threading
from loguru import logger  # 或使用 logging


class GlobalSignalHandler:
    """全局信号处理器，用于协调多个服务的优雅停止"""

    def __init__(self):
        # 创建一个全局事件来通知停止
        self.shutdown_event = threading.Event()
        self.downloader = None
        self.uploader = None
        # 可以添加一个锁来确保资源安全操作（如果需要）
        # self._lock = threading.Lock()

    def __call__(self, signum, frame):
        """
        当捕获到信号（如SIGINT, SIGTERM）时，此方法被调用。
        """
        logger.info(f"捕获到信号 {signum}，开始执行优雅停止...")

        # 1. 设置全局停止事件，通知所有监听此事件的循环或线程
        self.shutdown_event.set()

        # 2. 依次调用各个服务的停止方法
        # 先停止下载器（如果存在且有必要先停止）
        if self.downloader is not None:
            try:
                logger.info("正在停止下载器...")
                # 假设您的 BatchDownloader 有一个 stop() 方法
                self.downloader.stop()
                logger.info("下载器已停止。")
            except Exception as e:
                logger.error(f"停止下载器时发生错误: {e}")

        # 再停止上传器（如果存在）
        if self.uploader is not None:
            try:
                logger.info("正在停止上传器...")
                # 假设您的 BatchUploader 有一个 stop() 方法
                self.uploader.stop()
                logger.info("上传器已停止。")
            except Exception as e:
                logger.error(f"停止上传器时发生错误: {e}")

        logger.info("优雅停止流程完成。")


# 创建全局信号处理器实例
signal_handler = GlobalSignalHandler()

# 将您的下载器和上传器实例赋值给信号处理器
signal_handler.downloader = oss_downloader
signal_handler.uploader = oss_uploader

# 注册信号处理函数
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

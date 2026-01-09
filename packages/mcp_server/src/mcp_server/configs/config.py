from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from utils.path_utils import get_proj_root_dir


class AppConfig(BaseModel):
    """应用配置设置."""

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # 缓存配置
    cache_ttl: int = 3600  # 1小时

    # 日志配置
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_filename: str = "app.log"


class BatchConfig(BaseModel):
    batch_size: int = 20  # 最大批次大小
    batch_timeout: float = 1.0  # 时间窗口
    max_concurrent_batches: int = 2  # 避免GPU过载
    max_concurrent: int = 50  # 最大并发数


class OssConfig(BaseModel):
    # ak: str = "LTAI5t9nGwatk85zetzojXbn"
    # sk: str = "cpvUkFL2VVRt014rPucKr44aaKGLD4"
    # end_point: str = "oss-cn-shanghai.aliyuncs.com"
    # external_end_point: str = "oss-cn-shanghai.aliyuncs.com"
    # bucket: str = "mineru"
    # cdn_host: str = "https://cdn-mineru.openxlab.org.cn/"
    # root_path: str = "pdf/staging/"
    # workers: int = 10
    ak: str = "LTAI5tRATsmNwx1fiHL5UDRf"
    sk: str = "VnfozquVN7tEWwAdPmoqN0ToB4T1iG"
    region: str = "cn-shanghai"
    use_internal_endpoint: bool = True
    use_accelerate_endpoint: bool = True
    readwrite_timeout: int = 5
    bucket: str = "mineru"
    cdn_host: str = "https://cdn-mineru.openxlab.org.cn/"
    root_path: str = "html/release"

    workers: int = 20


class ModelConfig(BaseModel):
    model_path: str = "/tmp/models"


class Config(BaseSettings):
    app_cf: AppConfig = Field(default_factory=AppConfig)
    batch_cf: BatchConfig = Field(default_factory=BatchConfig)
    oss_cf: OssConfig = Field(default_factory=OssConfig)
    model_cf: ModelConfig = Field(default_factory=ModelConfig)

    # 统一使用 Pydantic V2 配置语法
    model_config = SettingsConfigDict(
        env_file=f"{get_proj_root_dir()}/.env",
        case_sensitive=False,
        extra="allow",
        env_nested_delimiter="__",  # 按照此分隔符将环境变量拆分为多级
    )

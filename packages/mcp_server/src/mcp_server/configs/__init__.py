from contextvars import ContextVar
from functools import lru_cache

from dripper.api import Dripper

from .config import Config


@lru_cache
def get_configs() -> Config:
    """获取应用配置单例."""
    return Config()


global_config = get_configs()
oss_config = global_config.oss_cf
batch_config = global_config.batch_cf
app_config = global_config.app_cf
model_config = global_config.model_cf

# 全链路 request_id
request_id_var: ContextVar[str] = ContextVar("request_id", default="SYSTEM")

# 模型
_model_config = {"model_path": model_config.model_path, "early_load": True}
dripper_client = Dripper(config=_model_config)

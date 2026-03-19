from pathlib import Path


def get_proj_root_dir():
    """获取项目的根目录.也就是含有.github, docs, llm_web_kit目录的那个目录."""
    root_path = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    return root_path


def get_py_pkg_root_dir():
    """获取python包的根目录.也就是含有__init__.py的那个目录.

    Args:
        None
    Returns:
        str: 项目的根目录
    """
    project_root = Path(__file__).resolve().parent.parent
    return project_root

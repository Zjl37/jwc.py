import os
from .cache import jwc_cache_dir
from ..phxp.api_model import PhxpResponse


def LoadUsedLabCourses(path: str | None = None) -> PhxpResponse:
    if path is None:
        path = f"{jwc_cache_dir()}/phxp/response-LoadUsedLabCourses.json"
    if not os.path.isfile(path):
        print(
            f"[!] LoadUsedLabCourses 缓存文件不存在。请手动将该请求的响应内容存入 {path} 文件。"
        )
        exit(1)

    with open(path) as json_file:
        return PhxpResponse.model_validate_json(json_file.read())

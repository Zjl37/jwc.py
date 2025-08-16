import json
import os
from .cache import jwc_cache_dir


def LoadUsedLabCourses(path: str | None = None):
    if path is None:
        path = f"{jwc_cache_dir()}/phxp/response-LoadUsedLabCourses.json"
    if not os.path.isfile(path):
        print(
            f"[!] LoadUsedLabCourses 缓存文件不存在。请手动将该请求的响应内容存入 {path} 文件。"
        )
        exit(1)

    with open(path) as json_file:
        return json.load(json_file)

import datetime
import time
from typing import cast
import click
import os

from pydantic import ValidationError
import requests

from .fetch import get_session
from ..jwapi_model import (
    CurrentSemester,
    RlZcSjResponse,
    XsksByxhListResponse,
    XsksList,
    XszykbzongResponse,
)


def jwc_cache_dir():
    dir = "./jwc-cache"
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return dir


def request_current_semester() -> CurrentSemester:
    session = get_session()
    response = session.post(
        url="http://jw.hitsz.edu.cn/component/querydangqianxnxq", verify=False
    )
    if response.ok:
        return CurrentSemester.model_validate(response.json())
    raise ConnectionError(f"获取当前学期失败: {response.status_code}")


def current_semester() -> tuple[str, str]:
    cache_file = f"{jwc_cache_dir()}/current_semester.json"
    try:
        if not os.path.exists(cache_file):
            return refresh_semester_cache()

        # Force refresh if cache is old
        if (
            datetime.datetime.now().timestamp() - os.path.getmtime(cache_file)
        ) > 30 * 86400:
            click.secho("[i] 学期信息缓存超过30天，自动刷新...", fg="yellow")
            return refresh_semester_cache()
        with open(cache_file) as f:
            semester = CurrentSemester.model_validate_json(f.read())
        return semester.XN, semester.XQ
    except:
        return refresh_semester_cache()


def refresh_semester_cache():
    cache_file = f"{jwc_cache_dir()}/current_semester.json"
    semester = request_current_semester()
    with open(cache_file, "w") as f:
        _ = f.write(semester.model_dump_json())
    return semester.XN, semester.XQ


def semester_cache_dir(xn: str, xq: str) -> str:
    dir_path = f"{jwc_cache_dir()}/{xn}-{xq}"
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


def request_xszykbzong(xn: str, xq: str):
    session = get_session()
    request_data = {"xn": xn, "xq": xq}

    response = session.post(
        url="http://jw.hitsz.edu.cn/xszykb/queryxszykbzong",
        data=request_data,
        verify=False,
    )

    if response.ok:
        print(f"[i] 已更新 xszykbzong")
        cache_dir = semester_cache_dir(xn, xq)
        path = f"{cache_dir}/response-queryxszykbzong.json"
        with open(path, "w") as file:
            _ = file.write(response.text)
        # Validate the response immediately
        try:
            _ = XszykbzongResponse.model_validate_json(response.text)
        except Exception as e:
            click.secho(f"[!] 验证课表数据时出错: {e}", fg="red")
    else:
        print(f"[!] 在请求 queryxszykbzong 时出错了：{response.status_code}")


def xszykbzong(xn: str, xq: str, path: str = "", text: str = "") -> XszykbzongResponse:
    """返回缓存的 queryxszykbzong 数据，如未找到则向服务器请求"""
    if text != "":
        return XszykbzongResponse.model_validate_json(text)

    default_path = f"{semester_cache_dir(xn, xq)}/response-queryxszykbzong.json"
    path = path or default_path

    def should_fetch():
        if not os.path.isfile(path):
            return True

        now = time.time()
        DAY = 24 * 60 * 60  # seconds
        stale_time = now - os.path.getmtime(path)

        if stale_time > 7 * DAY:
            ans = click.prompt(  # pyright: ignore[reportAny]
                f"[?] 缓存中的课表已有 {int(stale_time) // DAY} 天未更新，要重新获取吗？[Y/n]",
                default="y",
                type=str,
                show_default=False,
            )
            return not cast(str, ans).lower().startswith("n")

    if should_fetch():
        request_xszykbzong(xn, xq)

    with open(path) as f:
        return XszykbzongResponse.model_validate_json(f.read())


def request_semester_start_date(xn: str, xq: str):
    session = get_session()
    response = session.post(
        url="http://jw.hitsz.edu.cn/component/queryRlZcSj",
        data={"xn": xn, "xq": xq, "djz": "1"},
        verify=False,
    )

    if response.ok:
        data = RlZcSjResponse.model_validate(response.json())
        # 找到星期一（xqj=1）的日期
        for entry in data.content:
            if entry.xqj == "1":
                start_date = datetime.datetime.strptime(entry.rq, "%Y-%m-%d").date()
                cache_file = f"{semester_cache_dir(xn, xq)}/semester_start_date.txt"
                with open(cache_file, "w") as f:
                    _ = f.write(start_date.isoformat())
                return start_date
        raise ValueError("未找到第一周星期一的日期")
    else:
        raise ConnectionError(f"获取学期开始日期失败: {response.status_code}")


def semester_start_date(xn: str, xq: str) -> datetime.date:
    """动态获取学期开始日期"""
    cache_file = f"{semester_cache_dir(xn, xq)}/semester_start_date.txt"
    kb_file = f"{jwc_cache_dir()}/response-queryxszykbzong.json"

    # 如果缓存存在且有效
    if (
        os.path.exists(cache_file)
        and os.path.exists(kb_file)
        and os.path.getmtime(cache_file) >= os.path.getmtime(kb_file)
    ):
        try:
            with open(cache_file) as f:
                return datetime.date.fromisoformat(f.read().strip())
        except:
            pass

    # 否则请求接口并缓存
    try:
        d0 = request_semester_start_date(xn, xq)
        click.secho(f"[i] 获取到学期开始日期: {d0.strftime('%Y-%m-%d')}", fg="green")
        return d0
    except Exception as e:
        click.secho(f"[!] 自动获取学期开始日期失败: {e}", fg="yellow")
        click.secho("[!] 将使用预置的日期，如有误请联系开发者更新配置", fg="yellow")
        # 保底返回已知日期
        # return datetime.date(2024, 3, 4)
        # return datetime.date(2024, 7, 8)
        # return datetime.date(2024, 8, 26)
        return datetime.date(2025, 2, 24)


def request_XsksByxhList():
    session = get_session()
    q = {
        "ppylx": "",
        "pkkyx": "",
        "pxn": "2024-2025",
        "pxq": "2",
    }

    resp = request_XsksByxhList_page(session, q, 1)
    l = resp.list

    # Process remaining pages
    for i in range(2, resp.navigateLastPage + 1):
        l += request_XsksByxhList_page(session, q, i).list

    print(f"[i] 已更新 XsksByxhList")
    # Create XsksResponse from validated entries
    all_entries = XsksList(l)
    with open(f"{jwc_cache_dir()}/response-queryXsksByxhList.json", "w") as file:
        _ = file.write(all_entries.model_dump_json())
    return all_entries


def request_XsksByxhList_page(
    session: requests.Session, q: dict[str, str], page: int
) -> XsksByxhListResponse:
    request_data = q | {
        "pageNum": str(page),
        "pageSize": "100",
    }

    response = session.post(
        url="http://jw.hitsz.edu.cn/kscxtj/queryXsksByxhList",
        data=request_data,
        verify=False,
    )
    if not response.ok:
        print(f"[!] 在请求 queryxszykbzong 时出错了：{response.status_code}")

    try:
        return XsksByxhListResponse.model_validate_json(response.text)
    except ValidationError as e:
        click.secho(response.text, fg="yellow")
        click.secho(f"[!] ↑ 原始数据", fg="yellow")
        click.secho(
            f"[!] request_XsksByxhList: 验证第1页考试条目时出错: {e}", fg="yellow"
        )
        raise ValueError("由于以上错误，无法继续。请向开发者反馈此问题。")


def XsksByxhList(path: str = "", text: str = "") -> XsksList:
    """返回缓存的 queryXsksByxhList 数据，如未找到则向服务器请求"""
    if text != "":
        return XsksList.model_validate_json(text)

    if path == "":
        path = f"{jwc_cache_dir()}/response-queryXsksByxhList.json"

    def should_fetch():
        if not os.path.isfile(path):
            return True

        now = time.time()
        DAY = 24 * 60 * 60  # seconds
        stale_time = now - os.path.getmtime(path)

        if stale_time > 7 * DAY:
            ans = click.prompt(  # pyright: ignore [reportAny]
                f"[?] 缓存中的考试安排已有 {int(stale_time) // DAY} 天未更新，要重新获取吗？[Y/n]",
                default="y",
                type=str,
                show_default=False,
            )
            return not cast(str, ans).lower().startswith("n")

    if should_fetch():
        return request_XsksByxhList()

    with open(path) as f:
        return XsksList.model_validate_json(f.read())

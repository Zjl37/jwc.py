from collections.abc import Mapping, Sequence
import json
import datetime
from typing import TypeAlias, cast
import click
import requests
import os

from jwc.login import auth_login

JSON_ro: TypeAlias = Mapping[str, "JSON_ro"] \
    | Sequence["JSON_ro"] | str | int | float | bool | None


def jwc_cache_dir():
    dir = './jwc-cache'
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return dir


globalSession: requests.Session | None = None  # type: ignore


def init_session(session: requests.Session | None = globalSession, force: bool = False) -> requests.Session:
    # global session
    if not force and session is not None:
        return session

    session = requests.Session()

    auth_choice: str = click.prompt(
        """认证方式？
        [1] 密码
        [2] Cookie
        """, prompt_suffix='> ')

    if auth_choice.strip().startswith('2'):
        session.headers.update({
            'Pragma': 'no-cache',
            'Proxy-Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0',
            'X-Requested-With': 'XMLHttpRequest',
            'Cookie': click.prompt("输入 Cookie，形如“route=???; JSESSIONID=???”", hide_input=True)
        })
        return session
    else:
        click.echo("=== 正在代为你登录*深圳校区*统一身份认证系统 ===")
        username: str = click.prompt("请输入用户名（学号）", prompt_suffix="：")
        password: str = click.prompt(
            "请输入密码", prompt_suffix="：", hide_input=True
        )
        success, msg = auth_login(session, username.strip(), password)
        if success:
            click.echo('[i] ' + msg)
            return session
        click.echo('[!] ' + msg)
        session = None
        raise Exception(msg)


def request_xszykbzong():
    session = init_session()

    request_data = {'xn': '2024-2025', 'xq': '2'}

    response = session.post(
        url='http://jw.hitsz.edu.cn/xszykb/queryxszykbzong',
        data=request_data,
        verify=False
    )

    if response.ok:
        print(f'[i] 已更新 xszykbzong')
        with open(f'{jwc_cache_dir()}/response-queryxszykbzong.json', 'w') as file:
            _ = file.write(response.text)
    else:
        print(f'[!] 在请求 queryxszykbzong 时出错了：{response.status_code}')


def xszykbzong(path: str = "", text: str = "") -> JSON_ro:
    """返回缓存的 queryxszykbzong 的 JSON 对象，如未找到则向服务器请求"""
    if text != "":
        return cast(JSON_ro, json.loads(text))

    if path == "":
        path = f'{jwc_cache_dir()}/response-queryxszykbzong.json'
    if not os.path.isfile(path):
        request_xszykbzong()

    with open(path) as json_file:
        return cast(JSON_ro, json.load(json_file))


def semester_start_date():
    # TODO: 从网页请求
    # return datetime.date(2024, 3, 4)
    # return datetime.date(2024, 7, 8)
    # return datetime.date(2024, 8, 26)
    return datetime.date(2025, 2, 24)

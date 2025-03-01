from collections.abc import Mapping, Sequence
import json
import datetime
from typing import TypeAlias, cast
import click
import requests
import os

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
        [1] 本部统一身份认证平台（哈工大APP扫码）
        [2] 深圳校区统一身份认证系统（密码登录）
        [3] Cookie
        """, prompt_suffix='> ')

    if auth_choice.strip().startswith('3'):
        # Cookie
        session.headers.update({
            'Pragma': 'no-cache',
            'Proxy-Connection': 'keep-alive',
            'X-Requested-With': 'XMLHttpRequest',
            'Cookie': click.prompt("输入本研教学管理与服务平台的 Cookie，形如“route=???; JSESSIONID=???”", hide_input=True)
        })
        return session
    elif auth_choice.strip().startswith('2'):
        # 深圳校区统一身份认证系统（密码登录）
        click.echo("=== 正在代为你登录*深圳校区*统一身份认证系统 ===")
        username: str = click.prompt("请输入用户名（学号）", prompt_suffix="：")
        password: str = click.prompt(
            "请输入密码", prompt_suffix="：", hide_input=True
        )

        from jwc.login import auth_login
        success, msg = auth_login(session, username.strip(), password)
        if success:
            click.echo('[i] ' + msg)
            return session
        click.echo('[!] ' + msg)
        session = None
        raise Exception(msg)
    else:
        # 本部统一身份认证平台（哈工大APP扫码）
        click.echo("=== 正在代为你登录*本部*统一身份认证平台 ===")

        from jwc.qr_login import get_qrcode, get_qrcode_image, HITIDS_HOST, get_status, login

        qr_token = get_qrcode(session)
        click.echo("[i] 请用哈工大APP扫描以下二维码：")
        click.echo(HITIDS_HOST + "/authserver/qrCode/getCode?uuid=" + qr_token)

        qr_img = get_qrcode_image(session, qr_token)
        from PIL import Image
        import io
        qr_img = Image.open(io.BytesIO(qr_img))
        from textual_image.renderable import Image
        import rich
        rich.print(Image(qr_img))

        login_status = '0'
        while login_status != '1':
            click.prompt("当你在移动设备上确认登录后，按下回车", prompt_suffix="：", default='')
            login_status = get_status(session, qr_token)
            if login_status == '0':
                click.echo('[i] 尚未扫码！')
            elif login_status == '2':
                click.echo('[i] 请在移动设备上确认登录。')
            elif login_status != '1':
                click.echo('[!] 二维码已失效，请重试。')
                if login_status != '3':
                    click.echo(
                        f'[!] 未知的 login_status "{login_status}"，请向开发者报告此情况。')
                raise Exception("二维码已失效")

        success, msg = login(session, qr_token)
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

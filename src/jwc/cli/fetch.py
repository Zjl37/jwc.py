import click
import requests
import fake_useragent
from idshit.pwd_login import auth_login, check_need_captcha
from idshit.qr_login import get_qr_token, get_qr_image, get_status, login
from idshit.common import HITIDS_HOST
from PIL import Image
import io
from textual_image.renderable import Image as TextImage
import rich
from typing import cast

from jwc.jwapi_common import heartbeat


def cli_auth_cookie(session: requests.Session):
    # Cookie
    session.headers.update(
        {
            "Pragma": "no-cache",
            "Proxy-Connection": "keep-alive",
            "X-Requested-With": "XMLHttpRequest",
            "Cookie": click.prompt(
                "输入本研教学管理与服务平台的 Cookie，形如“route=???; JSESSIONID=???”",
                hide_input=True,
            ),
        }
    )


def cli_auth_idshit_pwd(session: requests.Session):
    # 本部统一身份认证平台（密码登录）
    click.echo("=== 正在代为你登录*本部*统一身份认证平台 ===")

    username = cast(str, click.prompt("请输入用户名（学号）", prompt_suffix="："))

    try:
        need_captcha = check_need_captcha(session, username)
    except:
        click.secho("[!] 无法获取 need capcha 信息！请检查网络。", fg="yellow")
        raise

    if need_captcha:
        msg = "[!] 你的账号当前需要安全验证，动量神蚣 CLI 无法代为你完成密码登录。请你用浏览器自行完成一次登录后再尝试使用此工具，或改用扫码登录方式。"
        click.secho(msg, bg="black", fg="yellow")
        raise NotImplementedError(msg)

    password = cast(str, click.prompt("请输入密码", prompt_suffix="：", hide_input=True))

    err, res = auth_login(
        session, username.strip(), password, service="http://jw.hitsz.edu.cn/casLogin"
    )
    if not res.ok:
        print(f"[!] 登录请求失败！（{res.status_code}）")
    if err:
        if err is not True:
            click.echo("[!] 错误提示：" + err)
        raise Exception(err)

    if "/authentication/main" not in res.url:
        print(f"[!] 登录失败。跳转异常：#{res.url}#")
        raise Exception("登录失败。跳转异常")

    click.echo("[i] 登录成功")
    return


def cli_auth_qr(session: requests.Session):
    # 本部统一身份认证平台（哈工大APP扫码）
    click.echo("=== 正在代为你登录*本部*统一身份认证平台 ===")

    qr_token = get_qr_token(session)
    click.echo("[i] 请用哈工大 APP 扫描以下二维码：")
    click.echo(HITIDS_HOST + "/authserver/qrCode/getCode?uuid=" + qr_token)

    qr_img_data = get_qr_image(session, qr_token)

    qr_img = Image.open(io.BytesIO(qr_img_data))

    rich.print(TextImage(qr_img))

    login_status = "0"
    while login_status != "1":
        click.prompt(
            "当你在移动设备上确认登录后，按下回车", prompt_suffix="：", default=""
        )
        login_status = get_status(session, qr_token)
        if login_status == "0":
            click.echo("[i] 尚未扫码！")
        elif login_status == "2":
            click.echo("[i] 请在移动设备上确认登录。")
        elif login_status != "1":
            click.echo("[!] 二维码已失效，请重试。")
            if login_status != "3":
                click.echo(
                    f'[!] 未知的 login_status "{login_status}"，请向开发者报告此情况。'
                )
            raise Exception("二维码已失效")

    err, res = login(session, qr_token, service="http://jw.hitsz.edu.cn/casLogin")
    if not res.ok:
        print(f"[!] 登录请求失败！（{res.status_code}）")
    if err:
        if err is not True:
            click.echo("[!] 错误提示：" + err)
        raise Exception(err)

    if "/authentication/main" not in res.url:
        print(f"[!] 登录失败。跳转异常：#{res.url}#")
        raise Exception("登录失败。跳转异常")

    click.echo("[i] 登录成功")


globalSession: requests.Session | None = None


def get_session(force: bool = False) -> requests.Session:
    global globalSession

    if not force and globalSession is not None:
        return globalSession

    session = requests.Session()

    session.headers.update(
        {"User-Agent": fake_useragent.UserAgent(platforms="desktop").random}
    )

    auth_choice: str = click.prompt(  # pyright: ignore[reportAny]
        """认证方式？
        [1] 本部统一身份认证平台（哈工大APP扫码）〔推荐〕
        [2] 本部统一身份认证平台（密码登录）
        [3] Cookie
        """,
        type=click.Choice(["1", "2", "3"]),
        default="1",
        show_choices=False,
        show_default=False,
        prompt_suffix=">",
    )

    if auth_choice.strip().startswith("3"):
        cli_auth_cookie(session)
    elif auth_choice.strip().startswith("2"):
        cli_auth_idshit_pwd(session)
    else:
        cli_auth_qr(session)

    if not heartbeat(session):
        click.secho("[!] 登录状态异常！请检查登录依据是否有效。", fg="yellow")
        raise Exception("登录状态异常！请检查登录依据是否有效。")

    globalSession = session
    return session

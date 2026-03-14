from dataclasses import dataclass
from http import cookiejar
import click
import requests
import requests.cookies
import fake_useragent
from idshit.pwd_login import auth_login, check_need_captcha
from idshit.qr_login import get_qr_token, get_qr_image, get_status, login
from idshit.common import HITIDS_HOST, visit_ids_try_autologin
from PIL import Image
import io
from textual_image.renderable import Image as TextImage
import rich
from typing import cast
import os
import time
import stat
import pickle
import json
from http.cookies import SimpleCookie
from urllib.parse import quote

from jwc.jwapi_common import heartbeat

JW_CAS_SERVICE = "http://jw.hitsz.edu.cn/casLogin"
REAUTH_VIEW_URL = (
    f"{HITIDS_HOST}/authserver/reAuthCheck/reAuthLoginView.do"
    f"?isMultifactor=true&service={quote(JW_CAS_SERVICE, safe='')}"
)


@dataclass
class SessionCache:
    cookies: requests.cookies.RequestsCookieJar
    headers: dict[str, str | bytes]
    created_at: float


@dataclass(frozen=True)
class MfaTypeConfig:
    reauth_type: int
    auth_code_type_name: str | None
    needs_dynamic_code: bool


MFA_TYPE_CONFIGS: dict[str, tuple[str, MfaTypeConfig]] = {
    "1": ("短信验证码", MfaTypeConfig(3, "reAuthDynamicCodeType", True)),
    "2": ("哈工大APP验证码", MfaTypeConfig(13, "reAuthWeLinkDynamicCodeType", True)),
    "3": ("邮箱验证码", MfaTypeConfig(11, "reAuthEmailDynamicCodeType", True)),
    "4": ("数盾OTP", MfaTypeConfig(10, None, False)),
}


def get_session_cache_path() -> str:
    """获取session缓存文件路径"""
    from jwc.cli.cache import jwc_cache_dir

    cache_dir = jwc_cache_dir()
    return os.path.join(cache_dir, "session-v1.json")


def save_session(session: requests.Session) -> None:
    """将session序列化保存到文件"""
    cache_path = get_session_cache_path()

    # 使用pickle保存整个session状态
    session_data = SessionCache(
        cookies=session.cookies,  # 直接保存CookieJar对象
        headers=dict(session.headers),
        created_at=time.time(),
    )

    try:
        with open(cache_path, "wb") as f:
            pickle.dump(session_data, f)

        # 设置文件权限为仅当前用户可读写
        os.chmod(cache_path, stat.S_IRUSR | stat.S_IWUSR)
        click.echo("[i] Session已保存到缓存")
    except Exception as e:
        click.secho(f"[!] 保存session缓存失败: {e}", fg="yellow")


def load_session() -> requests.Session | None:
    """从文件加载session，如果文件不存在或无效则返回None"""
    cache_path = get_session_cache_path()

    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, "rb") as f:
            session_data: SessionCache = pickle.load(f)

        # 重建session对象
        session = requests.Session()

        # 恢复cookies（直接使用pickle保存的CookieJar）
        session.cookies = session_data.cookies

        # 恢复headers
        for name, value in session_data.headers.items():
            session.headers[name] = value

        click.echo("[i] 已加载缓存的session")
        return session

    except Exception as e:
        click.secho(f"[!] 加载session缓存失败: {e}", fg="yellow")
        # clear_session_cache()
        return None


def clear_session_cache() -> None:
    """清除session缓存文件"""
    cache_path = get_session_cache_path()
    try:
        if os.path.exists(cache_path):
            os.remove(cache_path)
            click.echo("[i] 已清除session缓存")
    except Exception as e:
        click.secho(f"[!] 清除session缓存失败: {e}", fg="yellow")


def cli_auth_cookie(session: requests.Session):
    # Cookie
    header = click.prompt(
        "输入本研教学管理与服务平台的 Cookie，形如“route=???; JSESSIONID=???”",
        hide_input=True,
    )

    simple_cookie = SimpleCookie()
    simple_cookie.load(header)

    for key, morsel in simple_cookie.items():
        c: cookiejar.Cookie = requests.cookies.create_cookie(  # pyright: ignore[reportUnknownVariableType]
            name=key, value=morsel.value, domain="jw.hitsz.edu.cn"
        )
        session.cookies.set_cookie(c)  # pyright: ignore[reportUnknownArgumentType]


def dump_auth_error(session: requests.Session, res: requests.Response):
    """将认证错误信息用 pickle 储存到文件以便调试"""
    from jwc.cli.cache import jwc_cache_dir
    import pickle

    cache_dir = jwc_cache_dir()
    dump_info = {
        "session": session,
        "response": res,
        "time": time.time(),
    }
    filename = f"auth_error_{time.time()}.pkl"
    with open(os.path.join(cache_dir, filename), "wb") as f:
        pickle.dump(dump_info, f)


def _is_mfa_page(url: str, body: str) -> bool:
    lower_url = url.lower()
    if "reauthloginview.do" in lower_url or "ismultifactor=true" in lower_url:
        return True

    lower_body = body.lower()
    return "reauthloginview.do" in lower_body or "ismultifactor=true" in lower_body


def _is_auth_login_page(url: str, body: str) -> bool:
    lower_url = url.lower()
    lower_body = body.lower()
    return "/authserver/login" in lower_url and (
        "#pwdfromid" in lower_body
        or 'id="pwdfromid"' in lower_body
        or "pwdencryptsalt" in lower_body
    )


def _response_location(response: requests.Response) -> str:
    location = response.headers.get("Location")
    if isinstance(location, str):
        return location
    location = response.headers.get("location")
    return location if isinstance(location, str) else ""


def _session_expired_from_response(response: requests.Response) -> bool:
    location = _response_location(response).lower()
    return "/authserver/login" in response.url.lower() or "/authserver/login" in location


def _post_ids_form(
    session: requests.Session,
    url: str,
    form: dict[str, str],
    as_ajax: bool = True,
    allow_redirects: bool = True,
) -> requests.Response:
    headers: dict[str, str] = {"Origin": HITIDS_HOST, "Referer": REAUTH_VIEW_URL}
    if as_ajax:
        headers["X-Requested-With"] = "XMLHttpRequest"
    return session.post(
        url,
        data=form,
        headers=headers,
        allow_redirects=allow_redirects,
    )


def _refresh_reauth_view(session: requests.Session) -> None:
    session.get(REAUTH_VIEW_URL, headers={"Referer": REAUTH_VIEW_URL})


def _change_reauth_type(session: requests.Session, reauth_type: int) -> None:
    _post_ids_form(
        session,
        f"{HITIDS_HOST}/authserver/reAuthCheck/changeReAuthType.do",
        {
            "isMultifactor": "true",
            "reAuthType": str(reauth_type),
            "service": JW_CAS_SERVICE,
        },
    )


def _try_parse_json_object(content: str) -> dict[str, object] | None:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_message(data: dict[str, object]) -> str:
    for key in ("message", "returnMessage", "msg"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _ensure_dynamic_code_sent(response: requests.Response) -> str:
    if response.status_code >= 400:
        raise Exception("验证码发送失败，请稍后重试")
    if _session_expired_from_response(response):
        raise Exception("会话已失效，请重新登录")
    body_text = response.text.strip()
    if not body_text:
        raise Exception("验证码发送失败，请稍后重试")
    parsed = _try_parse_json_object(body_text)
    if parsed is None:
        raise Exception("验证码发送失败，请稍后重试")

    err_code = parsed.get("errCode")
    if isinstance(err_code, str) and err_code == "206302":
        raise Exception("会话已失效，请重新登录")

    success = parsed.get("success")
    if isinstance(success, bool):
        if success:
            return "验证码已发送，请查收。"
        raise Exception(_extract_message(parsed) or "验证码发送失败，请稍后重试")

    res = parsed.get("res")
    if isinstance(res, str):
        if res.lower() == "success":
            return "验证码已发送，请查收。"
        raise Exception(_extract_message(parsed) or "验证码发送失败，请稍后重试")

    code = parsed.get("code")
    if isinstance(code, str) and code == "200":
        return "验证码已发送，请查收。"

    raise Exception("验证码发送失败，请稍后重试")


def _send_mfa_code(
    session: requests.Session, username: str, config: MfaTypeConfig
) -> str:
    if not config.needs_dynamic_code:
        return "已切换到令牌验证方式，请输入 OTP。"
    if username.strip() == "":
        raise Exception("缺少账号，无法发送验证码")

    response = _post_ids_form(
        session,
        f"{HITIDS_HOST}/authserver/dynamicCode/getDynamicCodeByReauth.do",
        {
            "userName": username.strip(),
            "authCodeTypeName": config.auth_code_type_name or "",
        },
    )
    return _ensure_dynamic_code_sent(response)


def _is_submit_success(response: requests.Response) -> bool:
    location = _response_location(response)
    lower_location = location.lower()
    if "jw.hitsz.edu.cn" in lower_location:
        return True
    if "caslogin" in lower_location and "ticket=" in lower_location:
        return True

    body_text = response.text.strip()
    if not body_text:
        return False
    if "reauth_success" in body_text.lower():
        return True

    parsed = _try_parse_json_object(body_text)
    if parsed is None:
        return False
    code = parsed.get("code")
    return isinstance(code, str) and code.lower() == "reauth_success"


def _submit_mfa_code(
    session: requests.Session, code: str, config: MfaTypeConfig
) -> None:
    if code.strip() == "":
        raise Exception("请输入验证码或 OTP")

    response = _post_ids_form(
        session,
        f"{HITIDS_HOST}/authserver/reAuthCheck/reAuthSubmit.do",
        {
            "service": JW_CAS_SERVICE,
            "reAuthType": str(config.reauth_type),
            "isMultifactor": "true",
            "password": "",
            "dynamicCode": code.strip() if config.needs_dynamic_code else "",
            "uuid": "",
            "answer1": "",
            "answer2": "",
            "otpCode": "" if config.needs_dynamic_code else code.strip(),
            "skipTmpReAuth": "false",
        },
        as_ajax=False,
        allow_redirects=False,
    )
    if not _is_submit_success(response):
        raise Exception("二次验证失败，请检查验证码或 OTP")


def _finalize_mfa_login(session: requests.Session) -> None:
    response = session.get(
        f"{HITIDS_HOST}/authserver/login",
        params={"service": JW_CAS_SERVICE},
        headers={"Referer": REAUTH_VIEW_URL},
    )
    if _is_mfa_page(response.url, response.text):
        raise Exception("二次验证未生效，请重试")
    if _is_auth_login_page(response.url, response.text):
        raise Exception("会话已失效，请重新登录")


def cli_auth_idshit_mfa(session: requests.Session, username: str | None = None) -> None:
    click.secho("[i] 统一身份认证要求二次验证，继续完成验证。", fg="yellow")
    username = username.strip() if isinstance(username, str) else ""

    while True:
        choice = click.prompt(
            """二次认证方式？
        [1] 短信验证码
        [2] 哈工大APP验证码
        [3] 邮箱验证码
        [4] 数盾OTP
        """,
            type=click.Choice(list(MFA_TYPE_CONFIGS.keys())),
            default="1",
            show_choices=False,
            show_default=False,
            prompt_suffix=">",
        )
        label, config = MFA_TYPE_CONFIGS[choice]
        try:
            _refresh_reauth_view(session)
            _change_reauth_type(session, config.reauth_type)

            if config.needs_dynamic_code:
                if username == "":
                    username = cast(
                        str,
                        click.prompt("请输入用户名（学号，用于发送验证码）", prompt_suffix="："),
                    ).strip()
                click.echo(f"[i] 正在发送{label}...")
            message = _send_mfa_code(session, username, config)
            click.echo(f"[i] {message}")

            code = cast(str, click.prompt("请输入验证码或 OTP", prompt_suffix="："))
            _submit_mfa_code(session, code, config)
            _finalize_mfa_login(session)
            click.echo("[i] 二次验证成功")
            return
        except Exception as e:
            click.secho(f"[!] 二次验证失败：{e}", fg="yellow")
            if not click.confirm("[?] 是否重试二次验证？", default=True):
                raise


def cli_auth_idshit_pwd(
    session: requests.Session, form_info: dict[str, str] | None = None
):
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
        session,
        username.strip(),
        password,
        service=JW_CAS_SERVICE,
        form_info=form_info,
    )
    if not res.ok:
        print(f"[!] 登录请求失败！（{res.status_code}）")
    if err:
        if err is not True:
            click.echo("[!] 错误提示：" + err)
        dump_auth_error(session, res)
        raise Exception(err)

    if _is_mfa_page(res.url, res.text):
        cli_auth_idshit_mfa(session, username)
        click.echo("[i] 登录成功")
        return

    if "/authentication/main" not in res.url:
        print(f"[!] 登录失败。跳转异常：#{res.url}#")
        raise Exception("登录失败。跳转异常")

    click.echo("[i] 登录成功")
    return


def cli_auth_qr(session: requests.Session, form_info: dict[str, str] | None = None):
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

    err, res = login(
        session, qr_token, service=JW_CAS_SERVICE, form_info=form_info
    )
    if not res.ok:
        print(f"[!] 登录请求失败！（{res.status_code}）")
    if err:
        if err is not True:
            click.echo("[!] 错误提示：" + err)
        dump_auth_error(session, res)
        raise Exception(err)

    if _is_mfa_page(res.url, res.text):
        cli_auth_idshit_mfa(session)
        click.echo("[i] 登录成功")
        return

    if "/authentication/main" not in res.url:
        print(f"[!] 登录失败。跳转异常：#{res.url}#")
        raise Exception("登录失败。跳转异常")

    click.echo("[i] 登录成功")


globalSession: requests.Session | None = None


def ask_save_session(session: requests.Session) -> None:
    """询问用户是否保存session到缓存"""
    if click.confirm(
        """[i] 是否储存登录状态以便下次使用？
    请注意，若选储存，jwc-cache 文件夹中将含有你的敏感账号会话信息。请妥善保管，避免被他人利用。
    你可以随时通过 `jwc session` 子命令清除会话状态。
    """,
        default=True,
    ):
        save_session(session)


def get_session(force: bool = False) -> requests.Session:
    global globalSession

    if not force and globalSession is not None:
        return globalSession

    session = globalSession
    resumed_from_file = False
    form_info = None

    if not force:
        # 如果不是强制登录，尝试加载缓存的session
        session = load_session()
        if session is not None:
            resumed_from_file = True

            # 验证session是否仍然有效
            if heartbeat(session):
                globalSession = session
                return session

            autologgedin, _other = visit_ids_try_autologin(
                session, service=JW_CAS_SERVICE
            )
            if autologgedin:
                click.secho("[i] 统一身份认证：7天免登录成功", fg="green")
                if not heartbeat(session):
                    click.secho("[!] 登录状态异常！请检查登录凭据是否有效。", fg="yellow")
                    raise Exception("登录状态异常！请检查登录凭据是否有效。")
                globalSession = session
                save_session(session)
                return session
            form_info = cast(dict[str, str], _other)
            click.secho("[!] 缓存的session已失效，将重新登录", fg="yellow")
            # clear_session_cache()

    if session is None:
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
        cli_auth_idshit_pwd(session, form_info=form_info)
    else:
        cli_auth_qr(session, form_info=form_info)

    if not heartbeat(session):
        click.secho("[!] 登录状态异常！请检查登录凭据是否有效。", fg="yellow")
        raise Exception("登录状态异常！请检查登录凭据是否有效。")

    # 登录成功后保存session到缓存
    (save_session if resumed_from_file else ask_save_session)(session)
    globalSession = session
    return session

from collections.abc import Mapping, Sequence
import json
import datetime
import time
from typing import TypeAlias, cast
from pydantic import BaseModel


class CurrentSemester(BaseModel):
    XNXQ_EN: str
    XN: str
    XNXQ: str
    XQ: str


class KbEntry(BaseModel):
    KCWZSM: None | str
    RWH: None | str
    SKFS: None | str
    SFFXEXW: None | str
    FILEURL: str | None = None
    SKSJ: str
    XB: int
    SKSJ_EN: None | str = None
    KEY: str


class XsksEntry(BaseModel):
    KCMC: str
    KSSJDMC: str
    CDDM: str
    KSJTSJ: str
    KSRQ: str


import click
import requests
import os
import fake_useragent

JSON_ro: TypeAlias = (
    Mapping[str, "JSON_ro"] | Sequence["JSON_ro"] | str | int | float | bool | None
)


def jwc_cache_dir():
    dir = "./jwc-cache"
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return dir


def request_current_semester() -> CurrentSemester:
    session = init_session()
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
        semester = CurrentSemester.model_validate(json.load(open(cache_file)))
        return semester.XN, semester.XQ
    except:
        return refresh_semester_cache()


def refresh_semester_cache():
    cache_file = f"{jwc_cache_dir()}/current_semester.json"
    semester = request_current_semester()
    with open(cache_file, "w") as f:
        json.dump(semester.model_dump(), f)
    return semester.XN, semester.XQ


def semester_cache_dir(xn: str, xq: str) -> str:
    dir_path = f"{jwc_cache_dir()}/{xn}-{xq}"
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


globalSession: requests.Session | None = None  # type: ignore


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

    from idshit.pwd_login import auth_login, check_need_captcha

    username: str = click.prompt("请输入用户名（学号）", prompt_suffix="：")

    try:
        need_captcha = check_need_captcha(session, username)
    except:
        click.secho("[!] 无法获取 need capcha 信息！请检查网络。", fg="yellow")
        raise

    if need_captcha:
        msg = "[!] 你的账号当前需要安全验证，动量神蚣 CLI 无法代为你完成密码登录。请你用浏览器自行完成一次登录后再尝试使用此工具，或改用扫码登录方式。"
        click.secho(msg, bg="black", fg="yellow")
        raise NotImplementedError(msg)

    password: str = click.prompt("请输入密码", prompt_suffix="：", hide_input=True)

    err, res = auth_login(
        session, username.strip(), password, service="http://jw.hitsz.edu.cn/casLogin"
    )
    if not res.ok:
        print(f"[!] 登录请求失败！（{res.status_code}）")
    if err:
        if err is not True:
            click.echo("[!] 错误提示：" + err)
        session = None
        raise Exception(err)

    if "/authentication/main" not in res.url:
        print(f"[!] 登录失败。跳转异常：#{res.url}#")
        raise Exception("登录失败。跳转异常")

    click.echo("[i] 登录成功")
    return


def cli_auth_szsso(session: requests.Session):
    """
    深圳校区统一身份认证系统（密码登录）〔已失效，请勿使用！〕
    """
    click.echo("=== 正在代为你登录*深圳校区*统一身份认证系统 ===")
    username: str = click.prompt("请输入用户名（学号）", prompt_suffix="：")
    password: str = click.prompt("请输入密码", prompt_suffix="：", hide_input=True)

    from jwc.szsso_login import auth_login

    success, msg = auth_login(session, username.strip(), password)
    if not success:
        click.echo("[!] " + msg)
        session = None
        raise Exception(msg)
    click.echo("[i] " + msg)


def cli_auth_union_szsso(session: requests.Session):
    """
    本部统一身份认证平台联合登录，跳转深圳校区统一身份认证系统（密码登录）〔已失效，请勿使用！〕
    """
    # 深圳校区统一身份认证系统（密码登录）
    click.echo("=== 正在代为你登录*深圳校区*统一身份认证系统 ===")
    username: str = click.prompt("请输入用户名（学号）", prompt_suffix="：")
    password: str = click.prompt("请输入密码", prompt_suffix="：", hide_input=True)

    from jwc.login import auth_login

    success, msg = auth_login(session, username.strip(), password)
    if not success:
        click.echo("[!] " + msg)
        session = None
        raise Exception(msg)
    click.echo("[i] " + msg)


def cli_auth_qr(session: requests.Session):
    # 本部统一身份认证平台（哈工大APP扫码）
    click.echo("=== 正在代为你登录*本部*统一身份认证平台 ===")

    from idshit.qr_login import get_qr_token, get_qr_image, get_status, login
    from idshit.common import HITIDS_HOST

    qr_token = get_qr_token(session)
    click.echo("[i] 请用哈工大 APP 扫描以下二维码：")
    click.echo(HITIDS_HOST + "/authserver/qrCode/getCode?uuid=" + qr_token)

    qr_img = get_qr_image(session, qr_token)
    from PIL import Image
    import io

    qr_img = Image.open(io.BytesIO(qr_img))
    from textual_image.renderable import Image
    import rich

    rich.print(Image(qr_img))

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
            session = None
        raise Exception(err)

    if "/authentication/main" not in res.url:
        print(f"[!] 登录失败。跳转异常：#{res.url}#")
        raise Exception("登录失败。跳转异常")

    click.echo("[i] 登录成功")


def init_session(force: bool = False) -> requests.Session:
    global globalSession

    if not force and globalSession is not None:
        return globalSession

    session = requests.Session()

    session.headers.update(
        {"User-Agent": fake_useragent.UserAgent(platforms="desktop").random}
    )

    auth_choice: str = input(
        """认证方式？
        [1] 本部统一身份认证平台（哈工大APP扫码）〔推荐〕
        [2] 本部统一身份认证平台（密码登录）
        [3] Cookie
        > """
    )

    if auth_choice.strip().startswith("3"):
        cli_auth_cookie(session)
    elif auth_choice.strip().startswith("2"):
        cli_auth_idshit_pwd(session)
    else:
        cli_auth_qr(session)

    return (globalSession := session)


def request_xszykbzong(xn: str, xq: str):
    session = init_session()
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
    else:
        print(f"[!] 在请求 queryxszykbzong 时出错了：{response.status_code}")


def xszykbzong(xn: str, xq: str, path: str = "", text: str = "") -> list[KbEntry]:
    """返回缓存的 queryxszykbzong 数据，如未找到则向服务器请求"""
    if text != "":
        raw_data = json.loads(text)
    else:
        default_path = f"{semester_cache_dir(xn, xq)}/response-queryxszykbzong.json"
        path = path or default_path

        def should_fetch():
            if not os.path.isfile(path):
                return True

            now = time.time()
            DAY = 24 * 60 * 60  # seconds
            stale_time = now - os.path.getmtime(path)

            if stale_time > 7 * DAY:
                ans = click.prompt(
                    f"[?] 缓存中的课表已有 {int(stale_time) // DAY} 天未更新，要重新获取吗？[Y/n]",
                    default="y",
                    type=str,
                    show_default=False,
                )
                return not cast(str, ans).lower().startswith("n")

        if should_fetch():
            request_xszykbzong(xn, xq)

        with open(path) as f:
            raw_data = json.load(f)

    return [KbEntry.model_validate(item) for item in raw_data]


def request_semester_start_date(xn: str, xq: str):
    session = init_session()
    response = session.post(
        url="http://jw.hitsz.edu.cn/component/queryRlZcSj",
        data={"xn": xn, "xq": xq, "djz": "1"},
        verify=False,
    )

    if response.ok:
        data = response.json()
        # 找到星期一（xqj=1）的日期
        for entry in data.get("content", []):
            if entry.get("xqj") == "1":
                start_date = datetime.datetime.strptime(entry["rq"], "%Y-%m-%d").date()
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
    session = init_session()
    q = {
        "ppylx": "",
        "pkkyx": "",
        "pxn": "2024-2025",
        "pxq": "2",
    }

    resp = request_XsksByxhList_page(session, q, 1)

    l = resp["list"]
    for i in range(2, resp["navigateLastPage"] + 1):
        l += request_XsksByxhList_page(session, q, i)

    print(f"[i] 已更新 XsksByxhList")
    with open(f"{jwc_cache_dir()}/response-queryXsksByxhList.json", "w") as file:
        _ = file.write(json.dumps(l, ensure_ascii=False))


def request_XsksByxhList_page(session, q, page):
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
    return response.json()


def XsksByxhList(path: str = "", text: str = "") -> list[XsksEntry]:
    """返回缓存的 queryXsksByxhList 数据，如未找到则向服务器请求"""
    if text != "":
        raw_data = json.loads(text)

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
        request_XsksByxhList()

    with open(path) as f:
        raw_data = json.load(f)

    return [XsksEntry.model_validate(item) for item in raw_data]

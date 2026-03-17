import importlib.metadata
import os
import pickle
import time
import platform

import requests

from idshit.cli_login import LoginCliConfig, LoginSessionManager, SessionCache

from jwc.jwapi_common import heartbeat


JW_CAS_SERVICE = "http://jw.hitsz.edu.cn/casLogin"


def get_session_cache_path() -> str:
    """获取 session 缓存文件路径"""
    from jwc.cli.cache import jwc_cache_dir

    cache_dir = jwc_cache_dir()
    return os.path.join(cache_dir, "session-v1.json")


def dump_auth_error(session: requests.Session, res: requests.Response) -> None:
    """将认证错误信息用 pickle 储存到文件以便调试"""
    from jwc.cli.cache import jwc_cache_dir

    cache_dir = jwc_cache_dir()
    dump_info = {
        "session": session,
        "response": res,
        "time": time.time(),
    }
    filename = f"auth_error_{time.time()}.pkl"
    with open(os.path.join(cache_dir, filename), "wb") as f:
        pickle.dump(dump_info, f)


def _accept_login_response(response: requests.Response) -> bool:
    return "/authentication/main" in response.url


_USER_AGENT = f"Zjl37/jwc.py/{importlib.metadata.version('jwc')} ({requests.utils.default_user_agent()}, {platform.system()} {platform.machine()})"

_LOGIN_MANAGER = LoginSessionManager(
    LoginCliConfig(
        service=JW_CAS_SERVICE,
        session_cache_path=get_session_cache_path,
        validate_session=heartbeat,
        dump_auth_error=dump_auth_error,
        accept_login_response=_accept_login_response,
        target_name="本研教学管理与服务平台",
        username_prompt="请输入用户名（学号）",
        mfa_username_prompt="请输入用户名（学号，用于发送验证码）",
        allow_cookie_login=True,
        autologin_success_message="[i] 统一身份认证：7天免登录成功",
        user_agent_factory=lambda: _USER_AGENT,
    )
)


def save_session(session: requests.Session) -> None:
    _LOGIN_MANAGER.save_session(session)


def load_session() -> requests.Session | None:
    return _LOGIN_MANAGER.load_session()


def clear_session_cache() -> None:
    _LOGIN_MANAGER.clear_session_cache()


def ask_save_session(session: requests.Session) -> None:
    _LOGIN_MANAGER.ask_save_session(session)


def cli_auth_cookie(session: requests.Session) -> None:
    _LOGIN_MANAGER.cli_inject_cookie(session)


def cli_auth_idshit_mfa(session: requests.Session, username: str | None = None) -> None:
    _LOGIN_MANAGER.cli_auth_mfa(session, username)


def cli_auth_idshit_pwd(
    session: requests.Session, form_info: dict[str, str] | None = None
) -> None:
    _LOGIN_MANAGER.cli_auth_pwd(session, form_info=form_info)


def cli_auth_qr(
    session: requests.Session, form_info: dict[str, str] | None = None
) -> None:
    _LOGIN_MANAGER.cli_auth_qr(session, form_info=form_info)


def get_session(force: bool = False) -> requests.Session:
    return _LOGIN_MANAGER.get_session(force=force)

import base64
import random
import time
from cryptography.hazmat.primitives import padding
import requests
from bs4 import BeautifulSoup as bs
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HITIDS_HOST = "https://ids.hit.edu.cn"
SZSSO_HOST = "https://sso.hitsz.edu.cn:7002"

AES_CHARS = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"


def random_string(n: int):
    return "".join(random.choices(AES_CHARS, k=n)).encode()


def aes_encrypt_password(
    n: str, f: str, iv: bytes | None = None, prefix1: bytes | None = None
):
    if not f:
        return n
    iv = iv or random_string(16)
    prefix1 = prefix1 or random_string(64)
    data = prefix1 + n.encode()

    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()

    cipher = Cipher(algorithms.AES(f.encode()), modes.CBC(iv))

    encryptor = cipher.encryptor()

    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode()


def auth_login(
    session: requests.Session, username: str, password: str, captcha: str = ""
):
    try:
        html_doc = session.get(
            HITIDS_HOST
            + "/authserver/login?service=http%3A%2F%2Fjw.hitsz.edu.cn%2FcasLogin"
        ).text
        soup = bs(html_doc, "html5lib")
        execution = soup.select_one("#pwdFromId > input[name='execution']")
        if execution is None:
            raise Exception("未找到 excution")
        execution = execution["value"]
        if type(execution) != str:
            raise Exception("excution 异常")

        pwd_salt = soup.select_one("#pwdFromId > input#pwdEncryptSalt")
        if pwd_salt is None:
            raise Exception("未找到 pwdEncryptSalt")
        pwd_salt = pwd_salt["value"]
        if type(pwd_salt) != str:
            raise Exception("pwdEncryptSalt 异常")

        # go_auth(session, execution, qr_token)
        form_data = {
            "username": username,
            "password": aes_encrypt_password(password, pwd_salt),
            "captcha": captcha,
            "_eventId": "submit",
            "cllt": "userNameLogin",
            "dllt": "generalLogin",
            "lt": "",
            "execution": execution,
        }
        auth_res = session.post(
            HITIDS_HOST
            + "/authserver/login?service=http%3A%2F%2Fjw.hitsz.edu.cn%2FcasLogin",
            data=form_data,
        )

        if not auth_res.ok:
            print("[!] 登录请求失败！")
            print("[!] status code: ", auth_res.status_code)
            print("[!] resp url: ", auth_res.url)
            print("[!] resp headers: ", auth_res.headers)
            msg = None
            try:
                soup = bs(auth_res.text, "html5lib")
                errorTip = soup.select_one("#showErrorTip")
                warnTip = soup.select_one("#showWarnTip")
                if errorTip is not None:
                    errorTip = str(errorTip.text)
                    print("[!] 错误提示：", errorTip)
                    msg = errorTip
                elif warnTip is not None:
                    warnTip = str(warnTip.text)
                    print("[!] 错误提示：", warnTip)
                    msg = warnTip

                print("[!] resp body: ", auth_res.text)
            except:
                pass
            print("[!] resp body: ", auth_res.text)
            return False, (
                f"登录请求失败：{msg}"
                if msg is not None
                else "登录请求失败。出错了。"
            )

        if "/authentication/main" not in auth_res.url:
            return False, f"登录失败。跳转异常：#{auth_res.url}#"

        return True, "登录成功"
    except Exception as e:
        return False, str(e)


def check_need_captcha(session: requests.Session, username: str) -> bool:
    res = session.get(
        HITIDS_HOST + "/authserver/checkNeedCaptcha.htl",
        params={"username": username.strip(), "_": int(time.time() * 1000)},
    ).json()
    return res["isNeed"]


if __name__ == "__main__":
    print("=== 正在代为你登录*本部*统一身份认证平台 ===")
    session = requests.Session()
    username: str = input("请输入用户名（学号）：")

    try:
        need_captcha = check_need_captcha(session, username)
    except:
        print("[!] 无法获取 need capcha 信息！请检查网络。")
        raise

    if need_captcha:
        msg = "[!] 你的账号当前需要安全验证，动量神蚣 CLI 无法代为你完成密码登录。请你用浏览器自行完成一次登录后再尝试使用此工具，或改用扫码登录方式。"
        print(msg)
        raise NotImplementedError(msg)

    password: str = input("请输入密码")

    success, msg = auth_login(session, username.strip(), password)

    print(msg)

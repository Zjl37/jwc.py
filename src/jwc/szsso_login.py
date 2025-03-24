import requests
from bs4 import BeautifulSoup as bs

SZSSO_HOST = "https://sso.hitsz.edu.cn:7002"


def auth_login(
    session: requests.Session, username: str, password: str
) -> tuple[bool, str]:
    try:
        html = session.get(
            SZSSO_HOST + "/cas/login?service=http%3A%2F%2Fjw.hitsz.edu.cn%2FcasLogin"
        ).text
        soup = bs(html, "html5lib")

        lt = soup.select_one("form#fm1 input[name='lt']")
        if lt is None:
            raise Exception("未找到 lt")
        lt = lt["value"]
        if type(lt) != str:
            raise Exception("lt 异常")

        execution = soup.select_one("form#fm1 input[name='execution']")
        if execution is None:
            raise Exception("未找到 execution")
        execution = execution["value"]
        if type(execution) != str:
            raise Exception("execution 异常")

        form_data = {
            "username": username,
            "password": password,
            "lt": lt,
            "execution": execution,
            "_eventId": "submit",
            "openid": "",
            "vc_username": "",
            "vc_password": "",
        }
        auth_res = session.post(
            SZSSO_HOST + "/cas/login?service=http%3A%2F%2Fjw.hitsz.edu.cn%2FcasLogin",
            data=form_data,
        )

        if not auth_res.ok:
            return False, "登录请求失败。请检查账号密码是否正确"

        if "/authentication/main" not in auth_res.url:
            return False, "登录失败。请检查账号密码是否正确"

        return True, "登录成功"

    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    session = requests.Session()
    username = input("请输入账号：")
    password = input("请输入密码：")
    print(auth_login(session, username, password))

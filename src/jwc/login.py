import requests
from bs4 import BeautifulSoup as bs

HITIDS_HOST = 'https://ids.hit.edu.cn'
SZSSO_HOST = "https://sso.hitsz.edu.cn:7002"


def goto_bind_auth():
    bind_auth_req = requests.Request(
        'GET', HITIDS_HOST + '/authserver/login?service=http%3A%2F%2Fjw.hitsz.edu.cn%2FcasLogin'
    )
    return bind_auth_req


def goto_sz_auth(hitids_html: str, parse: bool = False):
    def parse_login_url(hitids_html: str):
        soup = bs(hitids_html, 'html.parser')
        ulogin_elems = soup.select('.idsUnion_loginFont_a')
        ulogin_elem = next(
            (e for e in ulogin_elems if '深圳' in e.getText()), None
        )
        if ulogin_elem is None:
            raise Exception("未找到联合登录元素")
        sz_login_url = HITIDS_HOST + str(ulogin_elem['href']) + \
            "&success=http%3A%2F%2Fjw.hitsz.edu.cn%2FcasLogin"
        sz_login_url = sz_login_url.replace("&amp;", "&")
        return sz_login_url

    if parse:
        try:
            sz_login_url = parse_login_url(hitids_html)
        except:
            raise Exception("获取登录地址失败")
    else:
        sz_login_url = HITIDS_HOST + \
            '/authserver/combinedLogin.do?type=IDSUnion&appId=ff2dfca3a2a2448e9026a8c6e38fa52b&success=http%3A%2F%2Fjw.hitsz.edu.cn%2FcasLogin'

    jump_to_login_request = requests.Request('GET', sz_login_url)
    return jump_to_login_request


def generate_login_form(soup: bs, username: str, password: str):
    try:
        el = soup.select_one("#authZForm > input[name=redirect_uri]")
        if el is None:
            raise Exception("未找到 redirect_uri input 元素")
        redirect_url = el['value']

        el = soup.select_one("#authZForm > input[name=client_id]")
        if el is None:
            raise Exception("未找到 client_id input 元素")
        client_id = el['value']

        el = soup.select_one("#authZForm > input[name=state]")
        if el is None:
            raise Exception("未找到 state input 元素")
        state = el['value']

        form = {
            "action": "authorize",
            "response_type": "code",
            "redirect_uri": redirect_url,
            "client_id": client_id,
            "scope": "",
            "state": state,
            "username": username,
            "password": password,
        }
        return form
    except:
        raise Exception("生成登录表单失败")


def login_request(szsso_html: str, username: str, password: str):
    soup = bs(szsso_html, 'html.parser')
    try:
        form_elem = soup.select_one("#authZForm")
        if form_elem is None:
            raise Exception("未找到表单元素")
        login_url = SZSSO_HOST + str(form_elem['action'])
    except:
        raise Exception("获取登录地址失败")
    login_request = requests.Request(
        'POST', login_url, data=generate_login_form(soup, username, password)
    )
    return login_request


# def auth_ticket(ticket_url):
#     auth_ticket_request = requests.Request('GET', ticket_url)
#     return auth_ticket_request


def auth_login(session: requests.Session, username: str, password: str) -> tuple[bool, str]:
    try:
        bind_auth_req = goto_bind_auth()
        bind_auth_res = session.send(bind_auth_req.prepare())

        if not bind_auth_res.ok:
            return False, "访问联合认证失败"

        goto_sz_req = goto_sz_auth(bind_auth_res.text)
        goto_sz_res = session.send(goto_sz_req.prepare())

        if not goto_sz_res.ok:
            return False, "跳转至深圳登录界面失败"

        login_req = login_request(goto_sz_res.text, username, password)
        login_res = session.send(login_req.prepare())

        if not login_res.ok:
            return False, "登录请求失败。请检查账号密码是否正确"

        if "/authentication/main" not in login_res.url:
            return False, "登录失败。请检查账号密码是否正确"

        return True, "登录成功"

    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    session = requests.Session()
    # proxy = {
    #     "http": "http://127.0.0.1:7723",
    #     "https": "http://127.0.0.1:7723"
    # }
    username = input("请输入账号：")
    password = input("请输入密码：")
    # print(auth_login(session, username, password, proxy))
    print(auth_login(session, username, password))

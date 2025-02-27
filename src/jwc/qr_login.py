import requests
from bs4 import BeautifulSoup as bs

# import matplotlib.pyplot as plt

HITIDS_HOST = "https://ids.hit.edu.cn"
SZSSO_HOST = "https://sso.hitsz.edu.cn:7002"


def get_qrcode(session: requests.Session):
    """
    从认证服务器获取二维码及其关联的 token。

    参数:
        session (requests.Session): 当前的session对象。

    返回:
        tuple: 包含 token (str) 和二维码内容 (bytes) 的元组。

    异常:
        Exception: 如果在获取二维码 token 或二维码时发生错误。

    """
    try:
        qr_token_res = session.get(HITIDS_HOST + "/authserver/qrCode/getToken")
        if not qr_token_res.ok:
            raise Exception("获取二维码 token 失败")
        qr_token = qr_token_res.content.decode("utf-8")
        qr_code = session.get(
            HITIDS_HOST + f"/authserver/qrCode/getCode?uuid={qr_token}"
        )
        if not qr_code.ok:
            raise Exception("获取二维码失败")
        return qr_token, qr_code.content

    except Exception as e:
        raise Exception("获取二维码失败")


def go_auth(session: requests.Session, excution: str, qr_token: str):
    """
    使用二维码登录进行认证。

    参数:
        session (requests.Session): 用于发起HTTP请求的session对象。
        excution (str): 认证过程中需要的execution令牌。
        qr_token (str): 用于二维码登录的QR令牌。

    异常:
        Exception: 如果认证失败。

    返回:
        None
    """
    form_data = {
        "lt": "",
        "uuid": qr_token,
        "cllt": "qrLogin",
        "dllt": "generalLogin",
        "execution": excution,
        "_eventId": "submit",
        "rmShown": 1,
    }
    auth_res = session.post(
        HITIDS_HOST
        + "/authserver/login?display=qrLogin&service=http%3A%2F%2Fjw.hitsz.edu.cn%2FcasLogin",
        data=form_data,
    )
    if "/authentication/main" not in auth_res.url:
        raise Exception("认证失败")


def login(session: requests.Session, qr_token: str):
    """
    在二维码上确认登录之后，使用二维码渠道登录系统。

    参数:
    session (requests.Session): 用于发送HTTP请求的会话对象。
    qr_token (str): 二维码令牌。

    返回:
    tuple: 包含两个元素的元组，第一个元素是布尔值，表示登录是否成功；第二个元素是字符串，包含登录结果的消息。

    异常:
    Exception: 当未找到 excution 或 excution 异常时抛出异常。
    """
    try:
        html_doc = session.get(
            HITIDS_HOST
            + "/authserver/login?service=http%3A%2F%2Fjw.hitsz.edu.cn%2FcasLogin"
        ).text
        soup = bs(html_doc, "html5lib")
        excution = soup.select_one("#qrLoginForm > input[name='execution']")
        if excution is None:
            raise Exception("未找到 excution")
        excution = excution["value"]
        print(excution)
        if type(excution) != str:
            raise Exception("excution 异常")
        go_auth(session, excution, qr_token)
        return True, "登录成功"
    except Exception as e:
        return False, str(e)

# if __name__ == "__main__":
#     proxy = {
#         "http": "http://127.0.0.1:7723",
#         "https": "http://127.0.0.1:7723"
#     }
#     session = requests.Session()
#     session.proxies = proxy
#     session.verify = False
#     QRcode = get_qrcode(session)
#     with open("QRcode.png", "wb") as f:
#         f.write(QRcode[1])
#     img = plt.imread("QRcode.png")
#     plt.imshow(img)
#     plt.show()
#     # input()
#     # print(login(session, QRcode[0]))

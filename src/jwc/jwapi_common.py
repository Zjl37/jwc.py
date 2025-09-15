import requests


class JwcValueError(Exception):
    pass


class JwcRequestError(Exception):
    pass


def heartbeat(session: requests.Session):
    resp = session.post("http://jw.hitsz.edu.cn/component/online")
    if resp.status_code != 200:
        return False
    try:
        resp.json()
        return True
    except:
        return False


def jwapi_get_username(session: requests.Session) -> str | None:
    response = session.post("http://jw.hitsz.edu.cn/UserManager/queryxsxx")
    if not response.ok:
        return None
    resp = response.json()
    return resp["XH"]

import requests


def heartbeat(session: requests.Session):
    resp = session.post("http://jw.hitsz.edu.cn/component/online")
    if resp.status_code != 200:
        return False
    try:
        resp.json()
        return True
    except:
        return False

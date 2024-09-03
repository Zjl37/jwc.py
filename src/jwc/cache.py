import json
import datetime
import click
import requests
import os


def jwc_cache_dir():
    return './jwc-cache'


session: requests.Session = None  # type: ignore


def init_session():
    global session
    if session is not None:
        return
    session = requests.Session()
    session.headers.update({
        'Pragma': 'no-cache',
        'Proxy-Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0',
        'X-Requested-With': 'XMLHttpRequest',
        'Cookie': click.prompt("输入 Cookie，形如“_gscu_651000777=???; route=???; _gscbrs_651000777=?; JSESSIONID=???”", hide_input=True)
    })


def request_xszykbzong():
    init_session()

    request_data = {'xn': '2024-2025', 'xq': '1'}

    response = session.post(
        url='http://jw.hitsz.edu.cn/xszykb/queryxszykbzong',
        data=request_data,
        verify=False
    )

    if response.ok:
        print(f'[i] 已更新 xszykbzong')
        with open(f'{jwc_cache_dir()}/response-queryxszykbzong.json', 'w') as file:
            file.write(response.text)
    else:
        print(f'[!] 在请求 queryxszykbzong 时出错了：{response.status_code}')


def xszykbzong(path=f'{jwc_cache_dir()}/response-queryxszykbzong.json'):
    """返回缓存的 queryxszykbzong 的 JSON 对象，如未找到则向服务器请求"""
    if not os.path.isfile(path):
        request_xszykbzong()

    with open(path) as json_file:
        return json.load(json_file)


def semester_start_date():
    # TODO: 从网页请求
  #   return datetime.date(2024, 3, 4)
  #   return datetime.date(2024, 7, 8)
    return datetime.date(2024, 8, 26)

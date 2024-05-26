import json
import datetime


def dir():
    return './jwc-cache'


def xszykbzong(path=f'{dir()}/response-queryxszykbzong.json'):
    """返回缓存的 queryxszykbzong 的 JSON 对象"""
    with open(path) as json_file:
        return json.load(json_file)


def semester_start_date():
    # TODO: 从网页请求
    return datetime.date(2024, 3, 4)


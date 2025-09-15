import datetime
import requests

from jwc.jwapi_common import JwcRequestError
from jwc.jwapi_model import RlZcSjResponse


def jwapi_get_semester_start_date(
    session: requests.Session, xn: str, xq: str
) -> datetime.date | None:
    response = session.post(
        url="http://jw.hitsz.edu.cn/component/queryRlZcSj",
        data={"xn": xn, "xq": xq, "djz": "1"},
        verify=False,
    )

    if response.ok:
        data = RlZcSjResponse.model_validate(response.json())
        # 找到星期一（xqj=1）的日期
        for entry in data.content:
            if entry.xqj == "1":
                start_date = datetime.datetime.strptime(entry.rq, "%Y-%m-%d").date()
                return start_date
        return None

    raise JwcRequestError(f"获取学期开始日期失败: {response.status_code}")

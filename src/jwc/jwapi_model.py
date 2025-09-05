from typing import Optional
from pydantic import BaseModel, RootModel


class CurrentSemester(BaseModel):
    XNXQ_EN: str
    XN: str
    XNXQ: str
    XQ: str


class KbEntry(BaseModel):
    KCWZSM: None | str
    RWH: None | str
    SKFS: Optional[str] = None
    SFFXEXW: None | str
    FILEURL: str | None = None
    SKSJ: str
    XB: int
    SKSJ_EN: None | str = None
    KEY: str


class XszykbzongResponse(RootModel[list[KbEntry]]):
    """学生专业课表总"""


class XsksEntry(BaseModel):
    KCMC: str
    KSSJDMC: str
    CDDM: str
    KSJTSJ: str
    KSRQ: str


class XsksResponse(RootModel[list[XsksEntry]]):
    """学生考试"""


class ErrorEntry(BaseModel):
    entry: str
    reason: str


class RlZcSjEntry(BaseModel):
    """日历周次时间"""

    xqj: str  # 星期几
    rq: str  # 日期


class RlZcSjResponse(BaseModel):
    """日历周次时间"""

    content: list[RlZcSjEntry]


class XsksList(RootModel[list[XsksEntry]]):
    """学生考试"""


class XsksByxhListResponse(BaseModel):
    """学生考试？？？？"""

    list: list[XsksEntry]  # 原始数据列表
    navigateLastPage: int  # 最后一页页码

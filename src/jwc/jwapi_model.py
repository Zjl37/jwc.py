from typing import Optional
from pydantic import BaseModel, RootModel


class CurrentSemester(BaseModel):
    XNXQ_EN: str
    XN: str
    XNXQ: str
    XQ: str


class KbEntry(BaseModel):
    # 课程文字说明
    KCWZSM: None | str
    # 任务号
    RWH: None | str
    # 上课方式
    SKFS: Optional[str] = None  # 此字段于 2025-8/9 月份间见新加
    # 是否？？二学位（？）
    SFFXEXW: None | str
    # 附件网址
    FILEURL: str | None = None
    # 上课时间
    SKSJ: str
    # （？）
    XB: int
    # 上课时间（英文）
    SKSJ_EN: None | str = None
    # 单元格标识
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

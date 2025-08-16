from pydantic import BaseModel


class CurrentSemester(BaseModel):
    XNXQ_EN: str
    XN: str
    XNXQ: str
    XQ: str


class KbEntry(BaseModel):
    KCWZSM: None | str
    RWH: None | str
    SKFS: None | str
    SFFXEXW: None | str
    FILEURL: str | None = None
    SKSJ: str
    XB: int
    SKSJ_EN: None | str = None
    KEY: str


class XsksEntry(BaseModel):
    KCMC: str
    KSSJDMC: str
    CDDM: str
    KSJTSJ: str
    KSRQ: str

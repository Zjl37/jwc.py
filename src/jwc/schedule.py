from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Self
from enum import Enum
import ics
import json
import zoneinfo
import datetime
import re
import traceback
from . import preprocess
from jwc.jwapi_model import XsksEntry
from jwc.jwapi_model import KbEntry


ScheduleEntryKind = Enum("ScheduleEntryKind", ["LESSON", "EXAM", "LAB"])
LESSON, EXAM, LAB = ScheduleEntryKind


def get_semester_desc_brief(xn: str, xq: str):
    year = xn.split("-")[0 if xq == "1" else 1]
    season = {"1": "秋", "2": "春", "3": "夏"}[xq]
    return f"{year[-2:]}{season}"


def get_semester_description(xn: str, xq: str):
    year = xn.split("-")[0 if xq == "1" else 1]
    season = {"1": "秋", "2": "春", "3": "夏"}[xq]
    return f"{year}年{season}季学期"


def get_calendar_name(semester_desc: str, kind: ScheduleEntryKind = LESSON):
    base_name = f"{semester_desc}{'考试' if kind == EXAM else '课程'}"
    return f"{base_name} - {datetime.date.today().strftime('%m月%d日')}更新"


def _to_range(text: str) -> tuple[int, int]:
    """将表示范围的字符串转为元组"""
    """_to_range('1-4') -> (1, 4)"""
    """_to_range('3') -> (3, 3)"""
    items = list(map(int, text.split("-")))
    return (items[0], items[-1])


def _to_ranges(text: str) -> list[tuple[int, int]]:
    """将表示一个或多个范围的字符串转为元组的列表"""
    """_to_ranges('1-4,6,8-10') -> [(1, 4), (6, 6), (8, 10)]"""
    return [_to_range(r) for r in text.split(",")]


def _to_time_span(
    from_hr, from_min, to_hr, to_min
) -> tuple[datetime.time, datetime.time]:
    zone = zoneinfo.ZoneInfo("Asia/Shanghai")
    return (
        datetime.time(from_hr, from_min, 0, tzinfo=zone),
        datetime.time(to_hr, to_min, 0, tzinfo=zone),
    )


time_slot_mapping = {
    1: _to_time_span(8, 30, 9, 20),
    2: _to_time_span(9, 25, 10, 15),
    3: _to_time_span(10, 30, 11, 20),
    4: _to_time_span(11, 25, 12, 15),
    5: _to_time_span(14, 0, 14, 50),
    6: _to_time_span(14, 55, 15, 45),
    7: _to_time_span(16, 0, 16, 50),
    8: _to_time_span(16, 55, 17, 45),
    9: _to_time_span(18, 45, 19, 35),
    10: _to_time_span(19, 40, 20, 30),
    11: _to_time_span(20, 45, 21, 35),
    12: _to_time_span(21, 40, 22, 30),
}


@dataclass
class ScheduledDates:
    weeks: list[int]
    day_of_week: Literal[1, 2, 3, 4, 5, 6, 7]

    def all_dates(self, semester_start_date):
        return (
            semester_start_date
            + datetime.timedelta(days=7 * (week - 1) + (self.day_of_week - 1))
            for week in self.weeks
        )

    def contains(self, q_week_id: int, q_day_of_week: int):
        return q_day_of_week == self.day_of_week and q_week_id in self.weeks


def _parse_date(text: str, d0: datetime.date) -> datetime.date:
    """根据当前学年，解析缺少年份的日期"""
    result = re.match(r"(\d+)月(\d+)日", text)
    if result is None:
        raise ValueError(f'_parse_date: 无法解析 "{text}"')
    mmdd = result.groups()
    date = datetime.date(d0.year, *map(int, mmdd))
    if date < d0:
        date = datetime.date(d0.year + 1, *map(int, mmdd))
    return date


def _parse_scheduled_weeks(text: str) -> list[int]:
    result = []
    for span in text.split(","):
        if "-" not in span:
            result.append(int(span))
        elif span[-1] == "双":
            w0, w1 = map(int, span[:-1].split("-"))
            result.extend(filter(lambda x: x % 2 == 0, range(w0, w1 + 1)))
        elif span[-1] == "单":
            w0, w1 = map(int, span[:-1].split("-"))
            result.extend(filter(lambda x: x % 2 == 1, range(w0, w1 + 1)))
        else:
            w0, w1 = map(int, span.split("-"))
            result.extend(range(w0, w1 + 1))
    return result


@dataclass
class ScheduleEntry:
    name: str
    dates: ScheduledDates | datetime.date
    time_ranges: list[tuple[datetime.time, datetime.time]]
    location: str
    kind: ScheduleEntryKind
    teacher: str = ""
    description: str = ""
    lab_name: str = ""

    @staticmethod
    def parse_day_of_week(obj: KbEntry) -> Literal[1, 2, 3, 4, 5, 6, 7]:
        r = int(obj.KEY[2])
        if r not in [1, 2, 3, 4, 5, 6, 7]:
            raise ValueError(f"weird day_of_week {r} on this entry")
        return r

    @staticmethod
    def determine_time_slot_ranges(
        slot_info: str | None, slot_key: str
    ) -> list[tuple[int, int]]:
        k = int(slot_key)
        if slot_info is None:
            return [(2 * k - 1, 2 * k)]
        ranges = _to_ranges(slot_info)
        if 2 * k - 1 <= ranges[0][0] <= 2 * k:
            return ranges
        # 连课会显示在多个单元格里，这样避免创建重复日程
        return []

    @classmethod
    def parse_lesson(cls, obj: KbEntry) -> Self | None:
        pattern = r"""(?P<名称>[^\[\]]+)
\[(?P<教师>[^\[\]]*)\]
\[(?P<周次>[^\[\]]+)周\]\[(?P<地点>[^\[\]]*)\](
第(?P<节次>.+)节)?"""

        result = re.match(pattern, obj.SKSJ)

        if result is None:
            return None

        name = result.group("名称")
        teacher = result.group("教师")
        location = result.group("地点")
        time_slot_ranges = cls.determine_time_slot_ranges(
            result.group("节次"),
            obj.KEY[6],  # '5' as in 'xq1_jc5'
        )
        time_ranges = [
            (time_slot_mapping[t[0]][0], time_slot_mapping[t[1]][1])
            for t in time_slot_ranges
        ]
        description = ""

        dates = ScheduledDates(
            _parse_scheduled_weeks(result.group("周次")), cls.parse_day_of_week(obj)
        )

        if obj.FILEURL is not None:
            description = f"""【课程交流码】
http://jw.hitsz.edu.cn/byyfile{obj.FILEURL}
{obj.KCWZSM or ""}"""

        return cls(
            name,
            dates,
            time_ranges,
            location,
            LESSON,
            teacher=teacher,
            description=description,
        )

    @classmethod
    def parse_lab(cls, obj: KbEntry) -> Self | None:
        pattern = r"""【实验】(?P<课程名称>[^\[\]]+)(\[(?P<实验名称>[^\[\]]+)\])?
\[(?P<节次>[^\[\]]+)节\]\[(?P<周次>[^\[\]]+)周\]
\[(?P<地点>[^\[\]]*)\]"""

        result = re.match(pattern, obj.SKSJ)

        if result is None:
            return None

        name = result.group("课程名称")
        lab_name = result.group("实验名称")
        location = result.group("地点")
        time_slot_ranges = cls.determine_time_slot_ranges(
            result.group("节次"),
            obj.KEY[6],  # '5' as in 'xq1_jc5'
        )
        time_ranges = [
            (time_slot_mapping[t[0]][0], time_slot_mapping[t[1]][1])
            for t in time_slot_ranges
        ]

        dates = ScheduledDates(
            _parse_scheduled_weeks(result.group("周次")), cls.parse_day_of_week(obj)
        )

        return cls(name, dates, time_ranges, location, LAB, lab_name=lab_name)

    @classmethod
    def parse_exam(cls, obj: KbEntry, d0: datetime.date) -> Self | None:
        pattern = r"""【[^【】]*考试】\n?(?P<名称>.+)
(?P<日期>.+)
(?P<时间>.+)
(?P<地点>.+)"""

        result = re.match(pattern, obj.SKSJ)

        if result is None:
            return None

        name = result.group("名称")
        location = result.group("地点")
        time_ranges_str = result.group("时间").split("-")
        time_ranges = [
            _to_time_span(
                *map(
                    int, [*time_ranges_str[0].split(":"), *time_ranges_str[-1].split(":")]
                )
            )
        ]

        return cls(
            name, _parse_date(result.group("日期"), d0), time_ranges, location, EXAM
        )

    @classmethod
    def from_XsksByxhList_item(cls, obj: XsksEntry):
        name = f"{obj.KCMC} {obj.KSSJDMC}考试"
        location = obj.CDDM
        time_ranges_str = obj.KSJTSJ.split("-")
        time_ranges = [
            _to_time_span(
                *map(
                    int, [*time_ranges_str[0].split(":"), *time_ranges_str[-1].split(":")]
                )
            )
        ]

        return cls(
            name,
            datetime.datetime.fromisoformat(obj.KSRQ).astimezone(
                zoneinfo.ZoneInfo("Asia/Shanghai")
            ),
            time_ranges,
            location,
            EXAM,
        )

    def get_ics_alarms(self) -> list[ics.DisplayAlarm]:
        if self.kind == LAB:
            return [
                ics.DisplayAlarm(datetime.timedelta(days=-2)),
                ics.DisplayAlarm(datetime.timedelta(minutes=-30)),
                ics.DisplayAlarm(datetime.timedelta(minutes=-15)),
            ]
        return [
            ics.DisplayAlarm(datetime.timedelta(minutes=dt))
            for dt in ([-15, -30] if self.kind == LESSON else [-30, -60, -120])
        ]

    def get_ics_name(self):
        match self.kind:
            case ScheduleEntryKind.LAB:
                return preprocess.transform_lab_name(self.name, self.lab_name) + (
                    f"［{self.teacher}］" if self.teacher else ""
                )
            case ScheduleEntryKind.LESSON:
                name = preprocess.transform_lesson_name(self.name)
                return f"{name}［{self.teacher}］"
            case ScheduleEntryKind.EXAM:
                return f"【考试】{self.name}"

    def get_ics_description(self):
        # 如实验日程具有实验名称，则会作为日程标题，故将课程名称放在描述中
        return f"""{self.name + "\n" if self.kind == LAB and self.lab_name else ""}
        {self.description}"""

    def to_ics_event(self, semester_start_date, categories) -> Iterable[ics.Event]:
        for t0, t1 in self.time_ranges:
            # ics-py 尚未支持重复日程，故作展开
            # https://github.com/ics-py/ics-py/issues/14
            match self.dates:
                case datetime.date():
                    dates = [self.dates]
                case ScheduledDates(week_ranges, day_of_week):
                    dates = list(self.dates.all_dates(semester_start_date))
            for date in dates:
                d0 = datetime.datetime.combine(date, t0)
                d1 = datetime.datetime.combine(date, t1)
                event = ics.Event(
                    name=self.get_ics_name(),
                    begin=d0,
                    end=d1,
                    description=self.get_ics_description(),
                    location=preprocess.location_detail(self.location),
                    categories=categories,
                    alarms=self.get_ics_alarms(),
                )
                yield event

    def overlaps_with(self, time_span: tuple[datetime.time, datetime.time]):
        s2, e2 = time_span
        for (
            s1,
            e1,
        ) in self.time_ranges:
            if max(s1, s2) < min(e1, e2):
                return True
        return False


@dataclass
class Schedule:
    entries: list[ScheduleEntry]
    semester_desc: str
    start_date: datetime.date

    @classmethod
    def from_kb(
        cls,
        obj: list[KbEntry],
        semester_desc: str,
        start_date: datetime.date,
        error_entries: list[dict[str, str]] | None = None,
    ):
        entries: list[ScheduleEntry] = []
        for item in obj:
            if item.KEY == "bz":
                # 忽略备注条目
                continue
            entry = None
            try:
                entry = (
                    ScheduleEntry.parse_exam(item, start_date)
                    or ScheduleEntry.parse_lab(item)
                    or ScheduleEntry.parse_lesson(item)
                )
            except ValueError as e:
                if error_entries is not None:
                    error_entries.append({
                        "entry": json.dumps(item, ensure_ascii=False),
                        "reason": str(e)
                    })
                continue
            if entry is not None:
                entries.append(entry)
        return cls(entries, semester_desc, start_date)

    def to_ics(self) -> ics.Calendar:
        cal = ics.Calendar()
        for entry in self.entries:
            cal.events.update(
                entry.to_ics_event(
                    self.start_date,
                    categories=[get_calendar_name(self.semester_desc, entry.kind)],
                )
            )
        return cal

    def query_lesson_at(
        self,
        q_week_id: int,
        q_date: datetime.date,
        q_day_of_week: int,
        q_time_span: tuple[int, int],
    ):
        for entry in self.entries:
            match entry.dates:
                case datetime.date():
                    if entry.dates != q_date:
                        continue
                case ScheduledDates():
                    if not entry.dates.contains(q_week_id, q_day_of_week):
                        continue
            if entry.overlaps_with(
                (
                    time_slot_mapping[q_time_span[0]][0],
                    time_slot_mapping[q_time_span[1]][1],
                )
            ):
                yield entry

    @classmethod
    def from_xsks(
        cls,
        obj: list[XsksEntry],
        semester_desc: str,
        start_date: datetime.date,
        error_entries: list[dict[str, str]] | None = None,
    ):
        entries: list[ScheduleEntry] = []
        for item in obj:
            entry = None
            try:
                entry = ScheduleEntry.from_XsksByxhList_item(item)
            except ValueError as e:
                if error_entries is not None:
                    error_entries.append({
                        "entry": json.dumps(item, ensure_ascii=False),
                        "reason": str(e)
                    })
                continue
            entries.append(entry)
        return cls(entries, semester_desc, start_date)

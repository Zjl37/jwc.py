import datetime
from collections.abc import Iterable
from enum import Enum
from dataclasses import dataclass, field
from functools import partial
import re
import ics  # pyright: ignore[reportMissingTypeStubs]
from ics.alarm.display import timedelta  # pyright: ignore[reportMissingTypeStubs]

from jwc.schedule_preset_trules import TransformationResults
from jwc.schedule_preference import JwcSchedulePreference, TextRules1
from jwc.jwapi_model import XsksEntry, KbEntry
from typing import cast, Self, Literal
import zoneinfo


def get_emoji(name: str, emoji_rules: TextRules1) -> tuple[str, bool]:
    for pattern, emoji in emoji_rules:
        if re.search(pattern, name, flags=re.M):
            return emoji, True
    return "", False


def get_lab_emoji(name: str, pref: JwcSchedulePreference) -> tuple[str, bool]:
    """取实验 emoji（只根据课程名称）"""
    if not pref.enable_emoji_prefix:
        return ("", True)
    return get_emoji(name, pref.lab_emoji_rules)


def get_lesson_emoji(name: str, pref: JwcSchedulePreference) -> tuple[str, bool]:
    """取课程 emoji"""
    if not pref.enable_emoji_prefix:
        return ("", True)
    return get_emoji(name, pref.lesson_emoji_rules)


def apply_trules(text: str, trules: TextRules1):
    for pattern, repl in trules:
        try:
            res, n = re.subn(pattern, repl, text)
            if n:
                return res, True
        except:
            continue
    return text, False


def transform_lesson_name_with_preference(
    name: str, pref: JwcSchedulePreference
) -> tuple[str, bool]:
    """取课程课程显示名称（添加emoji前缀）"""
    emoji, has_emoji = get_lesson_emoji(name, pref)
    name, _ = apply_trules(name, pref.lesson_trules)

    return emoji + name, has_emoji


def transform_lab_name_with_preference(
    name: str, lab_name: str, pref: JwcSchedulePreference
) -> tuple[str, bool]:
    """取实验显示名称（添加emoji前缀）"""
    emoji, has_emoji = get_lab_emoji(name, pref)

    if lab_name:
        match pref.lab_lesson_name_display_option:
            case "both" | "in_title":
                name, _ = apply_trules(name, pref.lesson_trules)
                return f"{emoji}{lab_name}（{name}）", has_emoji
            case _:
                return emoji + lab_name, has_emoji
    name, _ = apply_trules(name, pref.lesson_trules)
    return emoji + name, has_emoji


def location_detail_with_preference(
    location: str, preference: JwcSchedulePreference
) -> tuple[str, bool]:
    """取地点显示名称详情"""
    if not preference.enable_location_transformation:
        return location, False

    # 先应用用户规则
    for pattern, replacement in preference.location_trules:
        try:
            compiled_pattern = re.compile(pattern, flags=re.M)
            res, n = re.subn(compiled_pattern, replacement, location)
            if n:
                return res, True
        except:
            continue

    return location, False


ScheduleEntryKind = Enum("ScheduleEntryKind", ["LESSON", "EXAM", "LAB"])
LESSON, EXAM, LAB = ScheduleEntryKind


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
    from_hr: int, from_min: int, to_hr: int, to_min: int
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
    # 特殊节次
    13: _to_time_span(12, 15, 14, 0),
    14: _to_time_span(17, 50, 18, 40),
}


@dataclass
class ScheduledDates:
    weeks: list[int]
    day_of_week: Literal[1, 2, 3, 4, 5, 6, 7]

    def __hash__(self) -> int:
        h = 0
        for w in self.weeks:
            # 我们期望 w 的取值为 0~60 之间的整数，此时该哈希函数一定不会冲突
            h |= 1 << w
        return h << 3 | self.day_of_week

    def all_dates(self, semester_start_date: datetime.date):
        return (
            semester_start_date
            + datetime.timedelta(days=7 * (week - 1) + (self.day_of_week - 1))
            for week in self.weeks
        )

    def contains(self, q_week_id: int, q_day_of_week: int):
        return q_day_of_week == self.day_of_week and q_week_id in self.weeks


def _parse_scheduled_weeks(text: str) -> list[int]:
    result: list[int] = []
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


# 注意：这个类若加新字段时，请同时更新 time_range_smart_merge 中的 make_identifying_key 函数
@dataclass
class ScheduleEntry:
    name: str
    dates: ScheduledDates | datetime.date
    time_ranges: list[tuple[datetime.time, datetime.time]]
    location: str
    kind: ScheduleEntryKind
    teacher: str = ""
    description: list[str] = field(default_factory=lambda: [])
    lab_name: str = ""

    @staticmethod
    def parse_day_of_week(obj: KbEntry) -> Literal[1, 2, 3, 4, 5, 6, 7]:
        r = int(obj.KEY[2])
        if r not in [1, 2, 3, 4, 5, 6, 7]:
            raise ValueError(f"weird day_of_week {r} on this entry")
        return cast(Literal[1, 2, 3, 4, 5, 6, 7], r)

    @staticmethod
    def determine_time_slot_ranges(
        slot_info: str | None, slot_key: str | None
    ) -> list[tuple[int, int]]:
        if slot_info is None:
            if slot_key is None:
                return []
            k = int(slot_key)
            return [(2 * k - 1, 2 * k)]
        ranges = _to_ranges(slot_info)
        return ranges

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
        try:
            time_slot_ranges = cls.determine_time_slot_ranges(
                result.group("节次"),
                obj.KEY[6] if len(obj.KEY) >= 7 else None,  # '5' as in 'xq1_jc5'
            )
            time_ranges = [
                (time_slot_mapping[t[0]][0], time_slot_mapping[t[1]][1])
                for t in time_slot_ranges
            ]
        except:
            raise ValueError(f"parse_lesson: 无法解析节次：{result.group('节次')}")
        description: list[str] = []

        dates = ScheduledDates(
            _parse_scheduled_weeks(result.group("周次")), cls.parse_day_of_week(obj)
        )

        if obj.FILEURL is not None:
            description.append(f"""【课程交流码】
http://jw.hitsz.edu.cn/byyfile{obj.FILEURL}
{obj.KCWZSM or ""}""")

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
        try:
            time_slot_ranges = cls.determine_time_slot_ranges(
                result.group("节次"),
                obj.KEY[6] if len(obj.KEY) >= 7 else None,  # '5' as in 'xq1_jc5'
            )
            time_ranges = [
                (time_slot_mapping[t[0]][0], time_slot_mapping[t[1]][1])
                for t in time_slot_ranges
            ]
        except:
            raise ValueError(f"parse_lab: 无法解析节次：{result.group('节次')}")

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
    def from_XsksList_item(cls, obj: XsksEntry):
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

    def get_reminders_with_preference(
        self,
        pref: JwcSchedulePreference,
    ) -> list[datetime.timedelta]:
        if self.kind == EXAM:
            return pref.exam_reminders

        for pattern, reminders in pref.lesson_reminder_rules:
            if re.search(pattern, self.name, flags=re.M):
                return reminders

        if self.kind == LAB:
            return pref.lab_reminders
        # elif self.kind == LESSON:
        return pref.lesson_reminders

    def get_ics_alarms(self, preference: JwcSchedulePreference) -> list[ics.DisplayAlarm]:
        """根据用户偏好生成提醒设置"""
        reminders = self.get_reminders_with_preference(preference)

        return [ics.DisplayAlarm(reminder) for reminder in reminders]

    def get_ics_name(
        self,
        transformation_results: TransformationResults,
        preference: JwcSchedulePreference,
    ):
        str_teacher = f"［{self.teacher}］" if self.teacher else ""
        if not preference.enable_emoji_prefix:
            match self.kind:
                case ScheduleEntryKind.LAB:
                    return (self.lab_name or self.name) + str_teacher
                case ScheduleEntryKind.LESSON:
                    return f"{self.name}{str_teacher}"
                case ScheduleEntryKind.EXAM:
                    return f"【考试】{self.name}"

        match self.kind:
            case ScheduleEntryKind.LAB:
                transformed_name, was_transformed = transform_lab_name_with_preference(
                    self.name, self.lab_name, preference
                )
                if not was_transformed:
                    transformation_results.untransformed_labs.add(self.name)
                return transformed_name + str_teacher
            case ScheduleEntryKind.LESSON:
                transformed_name, was_transformed = transform_lesson_name_with_preference(
                    self.name, preference
                )
                if not was_transformed:
                    transformation_results.untransformed_lessons.add(self.name)
                return f"{transformed_name}{str_teacher}"
            case ScheduleEntryKind.EXAM:
                return f"【考试】{self.name}"

    def get_ics_description(self, preference: JwcSchedulePreference):
        desc = []
        if self.kind == LAB and self.lab_name:
            match preference.lab_lesson_name_display_option:
                case "both" | "in_description":
                    desc = [self.name]
                case _:
                    pass
        if preference.enable_description:
            desc += self.description
        return "\n".join(desc)

    def to_ics_event(
        self,
        semester_start_date: datetime.date,
        categories: list[str],
        transformation_results: TransformationResults,
        preference: JwcSchedulePreference,
    ) -> Iterable[ics.Event]:
        combine = datetime.datetime.combine
        match self.dates:
            case datetime.date():
                dates = [self.dates]
            case ScheduledDates():
                dates = list(self.dates.all_dates(semester_start_date))

        if not self.time_ranges:
            # 生成全天日程
            t0 = time_slot_mapping[1][0]
            # 不知为何这里要去掉时区才对
            zone = zoneinfo.ZoneInfo("UTC")
            for date in dates:
                event = ics.Event(
                    name=self.get_ics_name(transformation_results, preference),
                    begin=combine(date, t0, zone),
                    description=self.get_ics_description(preference),
                    location=self.location,
                    categories=categories,
                )
                event.make_all_day()
                yield event
            return

        for t0, t1 in self.time_ranges:
            # ics-py 尚未支持重复日程，故作展开
            # https://github.com/ics-py/ics-py/issues/14
            match self.dates:
                case datetime.date():
                    dates = [self.dates]
                case ScheduledDates():
                    dates = list(self.dates.all_dates(semester_start_date))
            for date in dates:
                d0 = combine(date, t0)
                d1 = combine(date, t1)

                transformed_location, location_was_transformed = (
                    location_detail_with_preference(self.location, preference)
                )
                if not location_was_transformed:
                    transformation_results.untransformed_locations.add(self.location)

                event = ics.Event(
                    name=self.get_ics_name(transformation_results, preference),
                    begin=d0,
                    end=d1,
                    description=self.get_ics_description(preference),
                    location=transformed_location,
                    categories=categories,
                    alarms=self.get_ics_alarms(preference),
                )
                yield event

    def overlaps_with(self, time_span: tuple[datetime.time, datetime.time]):
        s2, e2 = time_span
        for s1, e1 in self.time_ranges:
            if max(s1, s2) < min(e1, e2):
                return True
        return False

    def overlaps_or_adjacent_to(
        self, time_span: tuple[datetime.time, datetime.time], allow_gap: int = 0
    ):
        s2, e2 = time_span
        _to_datetime = partial(datetime.datetime.combine, datetime.date(2025, 9, 1))
        for s1, e1 in self.time_ranges:
            if _to_datetime(max(s1, s2)) - timedelta(minutes=allow_gap) <= _to_datetime(
                min(e1, e2)
            ):
                return True
        return False

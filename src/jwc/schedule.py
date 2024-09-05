from dataclasses import dataclass
from typing import Iterable, List, Literal, Tuple, Self
from enum import Enum
import click
import ics
import json
import zoneinfo
import datetime
import re
import traceback
from . import cache
from . import preprocess


ScheduleEntryKind = Enum('ScheduleEntryKind', ['LESSON', 'EXAM', 'LAB'])
LESSON, EXAM, LAB = ScheduleEntryKind


def get_calendar_name(kind: ScheduleEntryKind = LESSON):
    # TODO: determine semester dynamically
    return f'24秋{"考试" if kind == EXAM else "课程"} - {datetime.date.today().strftime("%m月%d日")}更新'


def _to_range(text: str) -> Tuple[int, int]:
    """将表示范围的字符串转为元组"""
    """_to_range('1-4') -> (1, 4)"""
    """_to_range('3') -> (3, 3)"""
    items = list(map(int, text.split('-')))
    return (items[0], items[-1])


def _to_ranges(text: str) -> List[Tuple[int, int]]:
    """将表示一个或多个范围的字符串转为元组的列表"""
    """_to_ranges('1-4,6,8-10') -> [(1, 4), (6, 6), (8, 10)]"""
    return [_to_range(r) for r in text.split(',')]


def _to_time_span(from_hr, from_min, to_hr, to_min) -> Tuple[datetime.time, datetime.time]:
    zone = zoneinfo.ZoneInfo('Asia/Shanghai')
    return (
        datetime.time(from_hr, from_min, 0, tzinfo=zone),
        datetime.time(to_hr, to_min, 0, tzinfo=zone)
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
    12: _to_time_span(21, 40, 22, 30)
}


@dataclass
class ScheduledDates:
    weeks: List[int]
    day_of_week: Literal[1, 2, 3, 4, 5, 6, 7]

    def all_dates(self, semester_start_date):
        return (
            semester_start_date +
            datetime.timedelta(days=7 * (week - 1) + (self.day_of_week - 1))
            for week in self.weeks
        )

    def contains(self, q_week_id: int, q_day_of_week: int):
        return q_day_of_week == self.day_of_week and q_week_id in self.weeks


def _parse_date(text: str) -> datetime.date:
    """根据当前学年，解析缺少年份的日期"""
    d0 = cache.semester_start_date()
    result = re.match(r'(\d+)月(\d+)日', text)
    if result is None:
        raise ValueError(f'_parse_date: 无法解析 "{text}"')
    mmdd = result.groups()
    date = datetime.date(d0.year, *map(int, mmdd))
    if date < d0:
        date = datetime.date(d0.year + 1, *map(int, mmdd))
    return date


def _parse_scheduled_weeks(text: str) -> List[int]:
    result = []
    for span in text.split(','):
        if '-' not in span:
            result.append(int(span))
        elif span[-1] == '双':
            w0, w1 = map(int, span[:-1].split('-'))
            result.extend(filter(lambda x: x % 2 == 0, range(w0, w1+1)))
        elif span[-1] == '单':
            w0, w1 = map(int, span[:-1].split('-'))
            result.extend(filter(lambda x: x % 2 == 1, range(w0, w1+1)))
        else:
            w0, w1 = map(int, span.split('-'))
            result.extend(range(w0, w1+1))
    return result


@dataclass
class ScheduleEntry:
    name: str
    dates: ScheduledDates | datetime.date
    time_ranges: List[Tuple[datetime.time, datetime.time]]
    location: str
    kind: ScheduleEntryKind
    teacher: str = ''
    description: str = ''
    lab_name: str = ''

    @staticmethod
    def parse_day_of_week(obj: dict) -> Literal[1, 2, 3, 4, 5, 6, 7]:
        r = int(obj['KEY'][2])
        if r not in [1, 2, 3, 4, 5, 6, 7]:
            print(f"[!] warning: weird day_of_week {r} on this entry:")
            print(json.dumps(obj, ensure_ascii=False))
        return r            # type: ignore

    @classmethod
    def parse_lesson(cls, obj: dict) -> Self | None:
        pattern = r'''(?P<名称>[^\[\]]+)
\[(?P<教师>[^\[\]]*)\]
\[(?P<周次>[^\[\]]+)周\]\[(?P<地点>[^\[\]]*)\]
第(?P<节次>.+)节'''

        result = re.match(pattern, obj['SKSJ'])

        if result is None:
            return None

        name = result.group('名称')
        teacher = result.group('教师')
        location = result.group('地点')
        time_slot_ranges = _to_ranges(result.group('节次'))
        time_ranges = [(time_slot_mapping[t[0]][0], time_slot_mapping[t[1]][1])
                       for t in time_slot_ranges]
        description = ''

        dates = ScheduledDates(_parse_scheduled_weeks(
            result.group('周次')), cls.parse_day_of_week(obj))

        if obj['FILEURL'] is not None:
            description = f"""【课程交流码】
http://jw.hitsz.edu.cn/byyfile{obj['FILEURL']}
{obj['KCWZSM'] or ''}"""

        return cls(name, dates, time_ranges, location, LESSON,
                   teacher=teacher, description=description)

    @classmethod
    def parse_lab(cls, obj: dict) -> Self | None:
        pattern = r'''【实验】(?P<课程名称>[^\[\]]+)(\[(?P<实验名称>[^\[\]]+)\])?
\[(?P<节次>[^\[\]]+)节\]\[(?P<周次>[^\[\]]+)周\]
\[(?P<地点>[^\[\]]*)\]'''

        result = re.match(pattern, obj['SKSJ'])

        if result is None:
            return None

        name = result.group('课程名称')
        lab_name = result.group('实验名称')
        location = result.group('地点')
        time_slot_ranges = _to_ranges(result.group('节次'))
        time_ranges = [(time_slot_mapping[t[0]][0], time_slot_mapping[t[1]][1])
                       for t in time_slot_ranges]

        dates = ScheduledDates(_parse_scheduled_weeks(
            result.group('周次')), cls.parse_day_of_week(obj))

        return cls(name, dates, time_ranges, location, LAB, lab_name=lab_name)

    @classmethod
    def parse_exam(cls, obj: dict) -> Self | None:
        pattern = r'''【[^【】]*考试】\n?(?P<名称>.+)
(?P<日期>.+)
(?P<时间>.+)
(?P<地点>.+)'''

        result = re.match(pattern, obj['SKSJ'])

        if result is None:
            return None

        name = result.group('名称')
        location = result.group('地点')
        time_ranges_str = result.group('时间').split('-')
        time_ranges = [_to_time_span(*map(int, [*time_ranges_str[0].split(':'),
                                                *time_ranges_str[-1].split(':')]))]

        return cls(name, _parse_date(result.group('日期')), time_ranges, location, EXAM)

    def get_ics_alarms(self) -> List[ics.DisplayAlarm]:
        if self.kind == LAB:
            return [
                ics.DisplayAlarm(datetime.timedelta(days=-2)),
                ics.DisplayAlarm(datetime.timedelta(minutes=-30)),
                ics.DisplayAlarm(datetime.timedelta(minutes=-15)),
            ]
        return [ics.DisplayAlarm(datetime.timedelta(minutes=dt))
                for dt in ([-15, -30] if self.kind == LESSON else [-30, -60])]

    def get_ics_name(self):
        match self.kind:
            case ScheduleEntryKind.LAB:
                return preprocess.transform_lab_name(self.name, self.lab_name) + \
                    (f'［{self.teacher}］' if self.teacher else '')
            case ScheduleEntryKind.LESSON:
                name = preprocess.transform_lesson_name(self.name)
                return f'{name}［{self.teacher}］'
            case ScheduleEntryKind.EXAM:
                return f'【考试】{self.name}'

    def get_ics_description(self):
        # 如实验日程具有实验名称，则会作为日程标题，故将课程名称放在描述中
        return f'''{self.name + '\n' if self.kind == LAB and self.lab_name else ''}
        {self.description}'''

    def to_ics_event(self, semester_start_date) -> Iterable[ics.Event]:
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
                    begin=d0, end=d1,
                    description=self.get_ics_description(),
                    location=preprocess.location_detail(self.location),
                    categories=[get_calendar_name(self.kind)],
                    alarms=self.get_ics_alarms(),
                )
                yield event

    def overlaps_with(self, time_span: Tuple[datetime.time, datetime.time]):
        s2, e2 = time_span
        for s1, e1, in self.time_ranges:
            if max(s1, s2) < min(e1, e2):
                return True
        return False


@dataclass
class Schedule:
    entries: List[ScheduleEntry]

    @classmethod
    def from_json(cls, obj: List[dict[str, dict]]):
        entries = []
        for item in obj:
            if item['KEY'] == 'bz':
                # 忽略备注条目
                continue
            entry = None
            try:
                entry = ScheduleEntry.parse_exam(item) or ScheduleEntry.parse_lab(item) \
                    or ScheduleEntry.parse_lesson(item)
            except Exception:
                print(traceback.format_exc())
            if entry is None:
                print(json.dumps(item, ensure_ascii=False))
                click.secho(f'[!] 遇到无法解析的课表条目。上述课程将不会添加到生成的日历中。', fg='red')
                continue
            entries.append(entry)
        return cls(entries)

    def to_ics(self) -> ics.Calendar:
        cal = ics.Calendar()
        d0 = cache.semester_start_date()

        for entry in self.entries:
            cal.events.update(entry.to_ics_event(d0))
        return cal

    def query_lesson_at(
            self,
            q_week_id: int,
            q_date: datetime.date,
            q_day_of_week: int,
            q_time_span: Tuple[int, int]
    ):
        for entry in self.entries:
            match entry.dates:
                case datetime.date():
                    if entry.dates != q_date:
                        continue
                case ScheduledDates():
                    if not entry.dates.contains(q_week_id, q_day_of_week):
                        continue
            if entry.overlaps_with((
                    time_slot_mapping[q_time_span[0]][0],
                    time_slot_mapping[q_time_span[1]][1]
            )):
                yield entry

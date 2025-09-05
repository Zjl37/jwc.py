from dataclasses import dataclass
from typing_extensions import Hashable
import ics  # pyright: ignore[reportMissingTypeStubs]
import datetime
from jwc.schedule_preset_trules import TransformationResults

from jwc.jwapi_model import (
    ErrorEntry,
    XsksList,
    XszykbzongResponse,
)

from jwc.schedule_utils import (
    EXAM,
    LESSON,
    ScheduleEntryKind,
    ScheduleEntry,
    ScheduledDates,
    time_slot_mapping,
)


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


def time_range_smart_merge(entries: list[ScheduleEntry]):
    print(f"[debug] time_range_smart_merge: {len(entries)} entries before merging")

    def make_identifying_key(e: ScheduleEntry):
        # 将以下这些字段全同的条目视为可合并的同一课程
        # 目前，我们不对 ScheduledDates 中的周次做进一步的细拆
        return (e.name, e.dates, e.location, e.kind, e.teacher, e.lab_name)

    grouped_entries: dict[Hashable, list[ScheduleEntry]] = {}

    # def debug_pprint_entry(entry: ScheduleEntry):
    #     from pprint import pprint

    #     pprint(entry)
    #     print("---")

    for entry in sorted(entries, key=lambda e: e.name):
        key = make_identifying_key(entry)
        if key not in grouped_entries:
            grouped_entries[key] = []
        grouped_entries[key].append(entry)

    final_entries: list[ScheduleEntry] = []

    for key, group in grouped_entries.items():
        # print(f"#####  GROUP {key}  #####")

        def is_candidate_or_finalize(e: ScheduleEntry):
            """如果条目是考试，或者没有具体时间范围，则直接加入最终结果，并返回 False
            否则返回 True，表示该条目是潜在可合并的候选条目"""
            if not e.time_ranges or e.kind == EXAM:
                final_entries.append(e)
                return False
            return True

        def get_start_time(e: ScheduleEntry) -> datetime.time:
            return e.time_ranges[0][0]

        group = sorted(filter(is_candidate_or_finalize, group), key=get_start_time)

        # print(f"#####  group have {len(group)} candidate entries")
        # for e in group:
        #     debug_pprint_entry(e)

        # 对同一课程时间重叠或相邻的条目进行合并
        # 相邻的条件是：一条目开始时间不晚于另一条目结束的后 15 分钟
        # 目前假定 time_ranges 中只会有一个范围

        # 不能使用 for 循环，因为待会要删元素
        i = 0
        while i < len(group):
            entryA = group[i]
            stA = group[i].time_ranges[0][0]
            etA = group[i].time_ranges[0][1]

            j = i + 1
            while j < len(group):
                entryB = group[j]
                etB = group[j].time_ranges[0][1]
                if entryA.overlaps_or_adjacent_to(entryB.time_ranges[0], allow_gap=15):
                    newEntry = ScheduleEntry(
                        name=entryA.name,
                        dates=entryA.dates,
                        time_ranges=[(stA, max(etA, etB))],
                        location=entryA.location,
                        kind=entryA.kind,
                        teacher=entryA.teacher,
                        lab_name=entryA.lab_name,
                        description=list(
                            set(entryA.description) | set(entryB.description)
                        ),
                    )
                    # print(f"[debug] new merged entry:")
                    # debug_pprint_entry(newEntry)

                    group[i] = newEntry
                    del group[j]
                    j -= 1
                j += 1
            i += 1

        final_entries.extend(group)

    # print(f"[debug] time_range_smart_merge: {len(final_entries)} entries after merging")
    return final_entries


@dataclass
class Schedule:
    entries: list[ScheduleEntry]
    semester_desc: str
    start_date: datetime.date

    @classmethod
    def from_kb(
        cls,
        obj: XszykbzongResponse,
        semester_desc: str,
        start_date: datetime.date,
        error_entries: list[ErrorEntry] | None = None,
    ):
        entries: list[ScheduleEntry] = []
        for item in obj.root:
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
                    error_entries.append(
                        ErrorEntry(entry=item.model_dump_json(), reason=str(e))
                    )
                continue
            if entry is not None:
                entries.append(entry)

        entries = time_range_smart_merge(entries)

        return cls(entries, semester_desc, start_date)

    def to_ics(self) -> tuple[ics.Calendar, TransformationResults]:
        cal = ics.Calendar()
        transformation_results = TransformationResults(set(), set(), set())

        for entry in self.entries:
            cal.events.update(
                entry.to_ics_event(
                    self.start_date,
                    categories=[get_calendar_name(self.semester_desc, entry.kind)],
                    transformation_results=transformation_results,
                )
            )
        return cal, transformation_results

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
        obj: XsksList,
        semester_desc: str,
        start_date: datetime.date,
        error_entries: list[ErrorEntry] | None = None,
    ):
        entries: list[ScheduleEntry] = []
        for item in obj.root:
            entry = None
            try:
                entry = ScheduleEntry.from_XsksList_item(item)
            except ValueError as e:
                if error_entries is not None:
                    error_entries.append(
                        ErrorEntry(entry=item.model_dump_json(), reason=str(e))
                    )
                continue
            entries.append(entry)
        return cls(entries, semester_desc, start_date)

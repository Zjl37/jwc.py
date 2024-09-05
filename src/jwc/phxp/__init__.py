
import json
import zoneinfo
from . import cache
import datetime

from typing import Optional, Tuple
from jwc.schedule import LAB, Schedule, ScheduleEntry


def arrange(in_file: str, out_file: Optional[str], schedule: Schedule):
    import pandas as pd

    df = pd.read_excel(in_file, index_col=[0, 1, 2, 3])

    df.insert(len(df.columns), '冲突课程', '')

    for i in df.index:
        try:
            week_id, date, day_of_week, time_span = i
            q_day_of_week = {
                '周一': 1,
                '周二': 2,
                '周三': 3,
                '周四': 4,
                '周五': 5,
                '周六': 6,
                '周日': 7,
            }[day_of_week]
        except:
            print(f"[i] ignored row in phxp table with index: {i}")
            continue
        q_week_id = int(week_id)
        q_date = datetime.datetime.strptime(date, '%Y.%m.%d')
        q_time_span: Tuple[int, int] = \
            tuple(map(int, time_span.split('、')))  # type: ignore

        conflict_entries = schedule.query_lesson_at(
            q_week_id, q_date, q_day_of_week, q_time_span
        )

        conflict_names = map(lambda e: e.lab_name or e.name, conflict_entries)

        df.at[i, '冲突课程'] = '，'.join(conflict_names)

    if out_file is None:
        sections = in_file.split('.')
        sections[-2] = sections[-2] + '+arranged'
        out_file = '.'.join(sections)

    df.to_excel(out_file)
    print(f"[i] 输出文件已写到 {out_file}")


def parse_lab_entry(item: dict):
    zone = zoneinfo.ZoneInfo('Asia/Shanghai')
    return ScheduleEntry(
        item['ModuleName'],
        datetime.datetime.strptime(
            item['ClassDate'], '%Y/%m/%d %H:%M:%S').date(),
        [tuple(map(lambda t: datetime.datetime.strptime(
            # type: ignore
            t, '%H:%M').time().replace(tzinfo=zone), [item['StartTime'], item['EndTime']]))],
        item['ClassRoom'],
        LAB,
        teacher=item['TeacherName'],
        lab_name=item['LabName']
    )


def create_schedule_from(obj: dict):
    entries = []
    for item in obj['rows']:
        entry = parse_lab_entry(item)
        if entry is None:
            print(json.dumps(item))
            raise ValueError(f'遇到无法解析的课表条目。')
        entries.append(entry)
    return Schedule(entries)

import os
import re
import click
import datetime
from typing import cast

from click.decorators import FC
from . import cache
from .schedule import Schedule, get_calendar_name, get_semester_desc_brief
import jwc.phxp
import jwc.phxp.cache

def parse_semester_arg(s: str) -> tuple[str, str]:
    """解析命令行中的学期选项，返回 (学年, 学期) 元组"""
    match = re.match(r"^(\d+)(sp|su|au|fa|[afs春夏秋])?", s.lower())
    if not match:
        raise ValueError(f"无效的学期格式: {s}")

    year_part, season_part = match.groups()
    base_year_raw = int(year_part)
    if base_year_raw < 100:
        base_year = 2000 + int(year_part)
    else:
        base_year = base_year_raw

    # Determine season
    if season_part in {"春", "sp", "s"}:
        xq = "2"
        xn = f"{base_year - 1}-{base_year}"
    elif season_part in {"夏", "su"}:
        xq = "3"
        xn = f"{base_year - 1}-{base_year}"
    elif season_part in {"秋", "f", "au", "fa"} or season_part is None:  # Default to fall
        xq = "1"
        xn = f"{base_year}-{base_year + 1}"
    else:
        raise ValueError(f"未知的季节标识: {season_part}")

    return (xn, xq)


@click.group()
def cli():
    click.echo("[动量神蚣 · jwc.py CLI]")
    pass


def add_semester_option(func: FC) -> FC:
    return click.option("-s", "semester", help="指定学期，格式如 24秋/25s/2025夏")(func)


@cli.command()
# @click.option('-i', '--id', prompt='学号')
@add_semester_option
def fetch(semester: str | None):
    """更新中间文件的缓存"""
    xn, xq = parse_semester_arg(semester) if semester else cache.refresh_semester_cache()
    cache.request_xszykbzong(xn, xq)
    _ = cache.request_semester_start_date(xn, xq)
    click.echo("[i] 缓存已更新")


def report_error_entries(error_entries: list[dict[str, str]], kind: str = "课表"):
    if len(error_entries):
        click.secho(
            f"[!] 遇到无法解析的{kind}条目。以下课程将不会添加到生成的日历中。可能需要向开发者反馈此问题。",
            fg="red",
        )
        for e in error_entries:
            click.secho(e["entry"], fg="yellow")
            click.secho(" ↳ 原因：" + e["reason"], fg="red")


@cli.command()
@add_semester_option
@click.option("-o", "out_file", default=None, help="输出文件名")
def to_ics(semester: str | None, out_file: str):
    """【教务课表导出】由课程表生成 ics 日历文件"""
    xn, xq = parse_semester_arg(semester) if semester else cache.current_semester()
    data = cache.xszykbzong(xn, xq)
    error_entries: list[dict[str, str]] = []
    # 动态获取学期开始日期
    start_date = cache.semester_start_date(xn, xq)
    schedule = Schedule.from_kb(
        data, get_semester_desc_brief(xn, xq), start_date, error_entries
    )
    report_error_entries(error_entries)

    calendar = schedule.to_ics()
    calendar_name = get_calendar_name(get_semester_desc_brief(xn, xq))
    ics_filename = out_file or f"{cache.jwc_cache_dir()}/out/{calendar_name}.ics"
    os.makedirs(os.path.dirname(ics_filename), exist_ok=True)
    with open(ics_filename, "w") as f:
        _ = f.write(calendar.serialize())
        print(f"[i] 日历已写入 {ics_filename} 文件。")


@cli.command()
@add_semester_option
@click.option("-o", "out_file", default=None, help="输出文件名")
def exam_to_ics(semester: str | None, out_file: str) -> None:
    """【教务考试导出】由考试安排生成 ics 日历文件"""
    xn, xq = parse_semester_arg(semester) if semester else cache.current_semester()
    data = cache.XsksByxhList()
    start_date = cache.semester_start_date(xn, xq)
    semester_desc = get_semester_desc_brief(xn, xq)
    error_entries: list[dict[str, str]] = []
    schedule = Schedule.from_xsks(data, semester_desc, start_date, error_entries)
    report_error_entries(error_entries, kind="考试")

    calendar = schedule.to_ics()
    from .schedule import EXAM

    calendar_name = get_calendar_name(get_semester_desc_brief(xn, xq), EXAM)
    ics_filename = out_file or f"{cache.jwc_cache_dir()}/out/{calendar_name}.ics"
    os.makedirs(os.path.dirname(ics_filename), exist_ok=True)
    with open(ics_filename, "w") as f:
        _ = f.write(calendar.serialize())
        print(f"[i] 日历已写入 {ics_filename} 文件。")


@cli.command()
@click.argument("in_file")
@add_semester_option
@click.option("-o", "out_file", default=None, help="输出文件名")
def phxp_arrange(in_file: str, out_file: str | None, semester: str | None):
    """
    【大物实验排课辅助】向给定的大物实验排课表旁边添加“冲突课程”一列

    IN_FILE 应为教师发布的大物实验排课表 Excel 文件。
    """
    xn, xq = parse_semester_arg(semester) if semester else cache.current_semester()
    data = cache.xszykbzong(xn, xq)
    start_date = cache.semester_start_date(xn, xq)
    semester_desc = get_semester_desc_brief(xn, xq)
    schedule = Schedule.from_kb(data, semester_desc, start_date)

    if not out_file:
        parts = in_file.rsplit(".", 1)
        out_file = (
            f"{parts[0]}+arranged.xlsx" if len(parts) > 1 else f"{in_file}+arranged"
        )

    error_entries: list[dict[str, str]] = []
    jwc.phxp.arrange(in_file, out_file, schedule, error_entries)

    if len(error_entries):
        click.secho(f"[i] 跳过了表格中的这些行：", fg="yellow")
        for e in error_entries:
            click.secho(e["entry"])
            click.secho(" ↳ 原因：" + e["reason"], fg="yellow")

    print(f"[i] 输出文件已写到 {out_file}")


@cli.command()
@add_semester_option
@click.option("-o", "out_file", default=None, help="输出文件名")
def phxp_to_ics(out_file: str, semester: str | None):
    """【大物实验课表导出】从物理实验选课平台生成 ics 日历"""

    xn, xq = parse_semester_arg(semester) if semester else cache.current_semester()
    start_date = cache.semester_start_date(xn, xq)
    semester_desc = get_semester_desc_brief(xn, xq)

    obj = jwc.phxp.cache.LoadUsedLabCourses()
    schedule = jwc.phxp.create_schedule_from(obj, semester_desc, start_date)
    calendar = schedule.to_ics()
    course_name = obj["rows"][0]["CourseName"]
    ics_filename = (
        out_file
        or f"{cache.jwc_cache_dir()}/out/{course_name} - {datetime.date.today().strftime('%m月%d日')}更新.ics"
    )
    os.makedirs(os.path.dirname(ics_filename), exist_ok=True)
    with open(ics_filename, "w") as f:
        _ = f.write(calendar.serialize())
        print(f"[i] 日历已写入 {ics_filename} 文件。")


if __name__ == "__main__":
    cli()

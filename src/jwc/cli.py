import os
import click
import datetime
from . import cache
from .schedule import Schedule, get_calendar_name


@click.group()
def cli():
    click.echo("[动量神蚣 · jwc.py CLI]")
    pass


@cli.command("fetch")
# @click.option('-i', '--id', prompt='学号')
def fetch(**kwargs):
    """更新中间文件的缓存"""
    cache.request_xszykbzong()
    _ = cache.request_semester_start_date()
    click.echo("[i] 缓存已更新")


@cli.command("")
@click.option("-o", "out_file", default=None, help="输出文件名")
def to_ics(out_file):
    """【教务课表导出】由课程表生成 ics 日历文件"""
    json = cache.xszykbzong()
    error_entries: set[str] = set()
    # 获取动态学期开始日期
    start_date = cache.semester_start_date()
    schedule = Schedule.from_json(json, error_entries, start_date=start_date)
    if error_entries:
        click.secho(
            f"[!] 遇到无法解析的课表条目。以下课程将不会添加到生成的日历中。", fg="red"
        )
        for e in error_entries:
            click.secho(e, fg="red")

    calendar = schedule.to_ics()
    ics_filename = out_file or f"{cache.jwc_cache_dir()}/out/{get_calendar_name()}.ics"
    os.makedirs(os.path.dirname(ics_filename), exist_ok=True)
    with open(ics_filename, "w") as f:
        f.write(calendar.serialize())
        print(f"[i] 日历已写入 {ics_filename} 文件。")


@cli.command("")
@click.option("-o", "out_file", default=None, help="输出文件名")
def exam_to_ics(out_file) -> None:
    """【教务考试导出】由考试安排生成 ics 日历文件"""
    json = cache.XsksByxhList()
    start_date = cache.semester_start_date()
    error_entries: set[str] = set()
    schedule = Schedule.from_exam_json(json, error_entries, start_date=start_date)
    if error_entries:
        click.secho(
            f"[!] 遇到无法解析的考试条目。以下课程将不会添加到生成的日历中。", fg="red"
        )
        for e in error_entries:
            click.secho(e, fg="red")

    calendar = schedule.to_ics()
    from .schedule import EXAM

    ics_filename = (
        out_file or f"{cache.jwc_cache_dir()}/out/{get_calendar_name(EXAM)}.ics"
    )
    os.makedirs(os.path.dirname(ics_filename), exist_ok=True)
    with open(ics_filename, "w") as f:
        f.write(calendar.serialize())
        print(f"[i] 日历已写入 {ics_filename} 文件。")


@cli.command("")
@click.argument("in_file")
@click.option("-o", "out_file", default=None, help="输出文件名")
def phxp_arrange(in_file, out_file):
    """
    【大物实验排课辅助】向给定的大物实验排课表旁边添加“冲突课程”一列

    IN_FILE 应为教师发布的大物实验排课表 Excel 文件。
    """
    json = cache.xszykbzong()
    schedule = Schedule.from_json(json)

    from . import phxp

    phxp.arrange(in_file, out_file, schedule)


@cli.command("")
@click.option("-o", "out_file", default=None, help="输出文件名")
def phxp_to_ics(out_file):
    """【大物实验课表导出】从物理实验选课平台生成 ics 日历"""
    from . import phxp

    obj = phxp.cache.LoadUsedLabCourses()
    schedule = phxp.create_schedule_from(obj)
    calendar = schedule.to_ics()
    course_name = obj["rows"][0]["CourseName"]
    ics_filename = (
        out_file
        or f"{cache.jwc_cache_dir()}/out/{course_name} - {datetime.date.today().strftime('%m月%d日')}更新.ics"
    )
    os.makedirs(os.path.dirname(ics_filename), exist_ok=True)
    with open(ics_filename, "w") as f:
        f.write(calendar.serialize())
        print(f"[i] 日历已写入 {ics_filename} 文件。")


if __name__ == "__main__":
    cli()

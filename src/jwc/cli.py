import click
import datetime
from . import cache
from .schedule import Schedule, get_calendar_name


@click.group()
def cli():
    click.echo('[神蚣 · jwc.py CLI]')
    pass


@cli.command('fetch')
# @click.option('-i', '--id', prompt='学号')
def fetch(**kwargs):
    """更新中间文件的缓存"""
    cache.request_xszykbzong()
    click.echo("[i] 缓存已更新")


@cli.command('')
@click.option('-o', 'out_file', default='./schedule.json', help="输出文件名")
def to_ics(out_file):
    """由课程表生成 ics 日历文件"""
    json = cache.xszykbzong()
    schedule = Schedule.from_json(json)
    calendar = schedule.to_ics()
    ics_filename = f'{cache.jwc_cache_dir()}/{get_calendar_name()}.ics'
    with open(ics_filename, 'w') as f:
        f.write(calendar.serialize())
        print(f"[i] 日历已写入 {ics_filename} 文件。")


@cli.command('')
@click.argument('in_file')
@click.option('-o', 'out_file', default=None, help="输出文件名")
def phxp_arrange(in_file, out_file):
    """向给定的大物实验排课表旁边添加“冲突”一列"""
    json = cache.xszykbzong()
    schedule = Schedule.from_json(json)

    from . import phxp

    phxp.arrange(in_file, out_file, schedule)


if __name__ == '__main__':
    cli()

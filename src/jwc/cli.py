import click
import datetime
from . import cache
from .schedule import Schedule, get_calendar_name


@click.group()
def cli():
    click.echo('[jwc cli]')
    pass


@cli.command('fetch')
@click.option('-i', '--id', prompt='学号')
def fetch(**kwargs):
    """Only fetch"""
    click.echo('Fetch!')


@cli.command('')
@click.option('-o', 'out_file', default='./schedule.json')
def main(out_file):
    """根据缓存的中间文件生成 ics 日程表"""
    json = cache.xszykbzong()
    schedule = Schedule.from_json(json)
    calendar = schedule.to_ics()
    ics_filename = f'{cache.dir()}/{get_calendar_name()}.ics'
    with open(ics_filename, 'w') as f:
        f.write(calendar.serialize())
        print(f"[i] 日历已写入 {ics_filename} 文件。")


if __name__ == '__main__':
    cli()

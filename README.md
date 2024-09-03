# 神蚣

神蚣（jwc.py）是一个 CLI 应用，可以代你从 HITSZ 的教务网站上获取课表信息，将其转换为 iCalendar 日历文件，从而可以方便地导入各种日历应用。此外还附带一些其他功能。

## 功能介绍

- ✅ 无隐私泄露顾虑，源代码开放易读。
- 🚧 支持使用用户名与密码便捷登录，并自动获取所有课表生成需要的信息。
- ✅ 每个课程名称前添一 emoji，直观易辨认
- ✅ 除了普通课程，还支持考试、实验日程。
- 🚧 支持自动获取学期开始日期。
- 🚧 支持手动指定部分参数。

## 使用方法

请看 `--help`：

```
Usage: jwc [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  fetch         更新中间文件的缓存
  phxp-arrange  【大物实验排课辅助】向给定的大物实验排课表旁边添加“冲突课程”一列
  phxp-to-ics   【大物实验课表导出】从物理实验选课平台生成 ics 日历
  to-ics        【教务课表导出】由课程表生成 ics 日历文件
```

运行后，日历文件会写入到 jwc-cache 文件夹中（连同一些中间缓存文件）。

## Development

本项目用 [PDM](https://pdm-project.org) 作 python 包与依赖管理器。在成功执行 ```pdm install``` 后，可以使用 ```pdm run jwc``` 运行之。

## Credit

- rewired 的 [hitsz_course_schedule_ics_converter](https://github.com/rewired-gh/hitsz_course_schedule_ics_converter/) ——这是本项目的原型。

## 许可证

以 GPLv3 许可。本项目无任何保证。

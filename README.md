# 动量神蚣

动量神蚣（jwc.py）是一个 CLI 应用，可以代你从 HITSZ 的教务网站上获取课表信息，将其转换为 iCalendar 日历文件，从而可以方便地导入各种日历应用。此外还附带一些其他功能。

## 功能介绍

- ✅ 无隐私泄露顾虑，源代码开放易读
- ✅ 支持哈工大 APP 扫码便捷登录
- ✅ 每个课程名称前添一 emoji，直观易辨认
- ✅ 除了普通课程，还支持考试、实验日程
- ✅ 支持自动获取当前学期和学期开始日期。
- 🚧 支持手动指定部分参数。

## 使用方法

首先，确保你在校园网环境中使用该工具；确保你的系统上安装有 Python 3.12 以上版本，如无，[前往 Python 官网下载](https://www.python.org/downloads/)并安装。

然后，[下载 jwc.py 的最新发布的 .whl 文件](https://github.com/Zjl37/jwc.py/releases)

挑选一空文件夹，在其中打开终端，依次执行以下命令

    # 创建虚拟环境
    python -m venv venv

    # 激活虚拟环境
    ## 如果是 Windows 系统，根据你使用的是 Powershell 还是 cmd，执行以下两条之一
    .\venv\Scripts\Activate.ps1
    .\venv\Scripts\Activate.bat
    ## 如果是类 Unix 系统，则执行
    source venv/bin/activate

    # 安装 jwc 及其依赖，请替换成该 .whl 文件的实际路径
    pip install -i https://mirrors.osa.moe/pypi/web/simple /path/to/jwc-0.2.0-py3-none-any.whl

    # 走你
    python -m jwc.cli

你将看到命令行帮助：

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

像这样运行子命令：

```
python -m jwc.cli to-ics
```

之后按程序的输出指引操作。

运行后，日历文件（连同一些中间缓存文件）会写入到 jwc-cache 文件夹中。

后续使用时，在同一文件夹中打开终端，可跳过【创建虚拟环境】【安装 jwc 及其依赖】步骤。当 jwc.py 发布新版本时，可以使用新的 .whl 文件，重新执行 `pip install` 步骤。

## Development

本项目用 [PDM](https://pdm-project.org) 作 python 包与依赖管理器。在成功执行 ```pdm install``` 后，可以使用 ```pdm run jwc``` 运行之。

## Credit

- rewired 的 [hitsz_course_schedule_ics_converter](https://github.com/rewired-gh/hitsz_course_schedule_ics_converter/) ——这是本项目的原型。

## 许可证

以 GPLv3 许可。本项目无任何保证。

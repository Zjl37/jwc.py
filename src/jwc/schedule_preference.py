"""
用户偏好设置模块
提供灵活的课程表处理和日历生成偏好配置
"""

from __future__ import annotations
from typing_extensions import Literal
from pydantic import BaseModel, Field
import datetime


type TextRules1 = list[tuple[str, str]]

type LabLessonNameDisplayOptionSimple = (
    Literal["in_description"] | Literal["none"] | Literal["in_title"] | Literal["both"]
)


class JwcSchedulePreference(BaseModel):
    """用户偏好设置数据结构"""

    # 全局开关
    enable_emoji_prefix: bool = True
    enable_description: bool = True
    enable_location_transformation: bool = True

    # 提醒设置
    lesson_reminders: list[datetime.timedelta] = Field(
        default_factory=lambda: [
            datetime.timedelta(minutes=-15),
            datetime.timedelta(minutes=-30),
        ]
    )

    lab_reminders: list[datetime.timedelta] = Field(
        default_factory=lambda: [
            datetime.timedelta(days=-2),
            datetime.timedelta(minutes=-30),
            datetime.timedelta(minutes=-15),
        ]
    )

    exam_reminders: list[datetime.timedelta] = Field(
        default_factory=lambda: [
            datetime.timedelta(minutes=-30),
            datetime.timedelta(minutes=-60),
            datetime.timedelta(minutes=-120),
        ]
    )

    lesson_emoji_rules: TextRules1 = Field(default_factory=list)
    lab_emoji_rules: TextRules1 = Field(default_factory=list)
    location_trules: TextRules1 = Field(default_factory=list)

    lesson_trules: TextRules1 = Field(default_factory=list)
    lesson_reminder_rules: list[tuple[str, list[datetime.timedelta]]] = Field(
        default_factory=list
    )

    lab_lesson_name_display_option: LabLessonNameDisplayOptionSimple = "in_description"

    def merge_with_preset_rules(
        self,
        preset_lesson_emoji_rules: TextRules1,
        preset_lab_emoji_rules: TextRules1,
        preset_location_trules: TextRules1,
    ):
        """
        追加预置规则
        原地操作
        """

        self.lesson_emoji_rules += preset_lesson_emoji_rules
        self.lab_emoji_rules += preset_lab_emoji_rules
        self.location_trules += preset_location_trules

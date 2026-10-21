"""提醒重复规则的纯函数测试。

这些用例不碰数据库、不需要事件循环，因此单独成文件，
避免被模块级的 asyncio 标记污染。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException

from yuxi.services import reminder_service
from yuxi.storage.postgres.models_family import Reminder

pytestmark = [pytest.mark.unit]

# 上海 2026-10-19 20:00 == UTC 2026-10-19 12:00（naive）
ANCHOR = datetime(2026, 10, 19, 12, 0)


def _make_reminder(remind_at: datetime, rule: dict) -> Reminder:
    """构造不落库的提醒对象，只用于验证展开逻辑。"""
    return Reminder(
        owner_uid="child_1",
        target_uid="elder_1",
        title="测试",
        remind_at=remind_at,
        repeat_rule=rule,
        enabled=True,
    )


def test_single_reminder_only_fires_on_anchor_day():
    reminder = _make_reminder(ANCHOR, {"type": "none"})

    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 19)) == ANCHOR
    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 20)) is None


def test_daily_reminder_fires_every_day_after_anchor():
    reminder = _make_reminder(ANCHOR, {"type": "daily"})

    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 18)) is None
    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 20)) == datetime(2026, 10, 20, 12, 0)
    assert reminder_service.occurrence_time_on(reminder, date(2026, 11, 30)) == datetime(2026, 11, 30, 12, 0)


def test_weekly_reminder_only_fires_on_selected_weekdays():
    # 2026-10-20 是周二（isoweekday=2），10-21 是周三
    reminder = _make_reminder(ANCHOR, {"type": "weekly", "weekdays": [2]})

    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 20)) == datetime(2026, 10, 20, 12, 0)
    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 21)) is None


def test_custom_interval_skips_odd_days():
    reminder = _make_reminder(ANCHOR, {"type": "custom", "interval": 2})

    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 19)) is not None
    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 20)) is None
    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 21)) is not None


def test_repeat_rule_stops_after_until():
    reminder = _make_reminder(ANCHOR, {"type": "daily", "until": "2026-10-20"})

    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 20)) is not None
    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 21)) is None


def test_unknown_repeat_type_is_not_expanded():
    reminder = _make_reminder(ANCHOR, {"type": "monthly"})

    assert reminder_service.occurrence_time_on(reminder, date(2026, 10, 20)) is None


@pytest.mark.parametrize(
    "rule",
    [
        {"type": "monthly"},
        {"type": "weekly", "weekdays": []},
        {"type": "weekly", "weekdays": [8]},
        {"type": "custom", "interval": 0},
        {"type": "custom", "interval": 999},
        {"type": "daily", "until": "2026-10-18"},
        {"type": "daily", "until": "not-a-date"},
    ],
)
def test_normalize_repeat_rule_rejects_invalid_input(rule):
    with pytest.raises(HTTPException) as exc_info:
        reminder_service.normalize_repeat_rule(rule, anchor=ANCHOR)
    assert exc_info.value.status_code == 400


def test_normalize_repeat_rule_keeps_only_known_fields():
    normalized = reminder_service.normalize_repeat_rule(
        {"type": "weekly", "weekdays": [3, 1, 3], "until": "2026-12-31", "evil": "drop-me"},
        anchor=ANCHOR,
    )

    assert normalized == {"type": "weekly", "weekdays": [1, 3], "until": "2026-12-31"}


def test_daily_range_covers_full_local_day():
    start, end = reminder_service.today_range_utc()
    assert end - start == timedelta(days=1)
    # 上海当天 00:00 对应前一天 16:00Z
    assert start.hour == 16

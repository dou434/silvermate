"""演示数据 seed 的数据构建测试（纯函数，冻结时钟下完全确定，不触库）。

冻结时钟锚定 2026-10-25（周日）10:00 上海时间：
- 历史窗口为 10-19（周一）~ 10-24（周六），窗口内的周二只有 10-20；
- 量血压漏服日为 D-4=10-21、D-2=10-23。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from scripts import seed_demo
from yuxi.utils.datetime_utils import SHANGHAI_TZ

pytestmark = [pytest.mark.unit]

_NOW = datetime(2026, 10, 25, 10, 0, tzinfo=SHANGHAI_TZ)  # 周日 10:00
_NOW_LATE = datetime(2026, 10, 25, 16, 0, tzinfo=SHANGHAI_TZ)  # 周日 16:00，下午三点已过
_NOW_TUESDAY = datetime(2026, 10, 20, 10, 0, tzinfo=SHANGHAI_TZ)  # 周二 10:00


def _utc(month, day, hour, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=UTC).replace(tzinfo=None)


def _reminders_by_key(spec):
    return {item["key"]: item for item in spec["reminders"]}


def _occurrences(spec, key):
    return [item for item in spec["occurrences"] if item["reminder_key"] == key]


# ---------- 提醒：时刻与重复规则 ----------


def test_reminder_set_is_fixed_and_owned_as_designed():
    """5 条提醒：4 条子女建 + 晨间遛弯老人自建；全部指向 demo 老人。"""
    spec = seed_demo.build_demo_spec(_NOW)
    by_key = _reminders_by_key(spec)

    assert [item["key"] for item in spec["reminders"]] == ["bp_med", "bp_measure", "clinic", "water", "walk"]
    assert by_key["walk"]["owner_uid"] == seed_demo.ELDER_UID
    assert all(by_key[key]["owner_uid"] == seed_demo.CHILD_UID for key in ("bp_med", "bp_measure", "clinic", "water"))
    assert all(item["target_uid"] == seed_demo.ELDER_UID for item in spec["reminders"])
    assert by_key["walk"]["title"] == "晨间遛弯"  # 展示语音自建的那条


def test_reminder_schedules_in_utc():
    """提醒时刻：上海时间锚定历史窗口首日；复诊锚窗口内首个周二；换算成 naive UTC 落库。"""
    spec = seed_demo.build_demo_spec(_NOW)
    by_key = _reminders_by_key(spec)

    assert by_key["bp_med"]["remind_at"] == _utc(10, 19, 0, 0)  # 上海 10-19 08:00
    assert by_key["bp_med"]["repeat_rule"] == {"type": "daily"}
    assert by_key["bp_measure"]["remind_at"] == _utc(10, 19, 13, 0)  # 上海 10-19 21:00
    assert by_key["walk"]["remind_at"] == _utc(10, 18, 23, 30)  # 上海 10-19 07:30
    assert by_key["clinic"]["remind_at"] == _utc(10, 20, 1, 0)  # 上海 10-20（周二）09:00
    assert by_key["clinic"]["repeat_rule"] == {"type": "weekly", "weekdays": [2]}
    assert by_key["water"]["remind_at"] == _utc(10, 25, 7, 0)  # 上海当天 15:00
    assert by_key["water"]["repeat_rule"] == {"type": "none"}


def test_water_rolls_to_tomorrow_when_afternoon_passed():
    """当天 15:00 已过：单次「喝水」顺延到明天，不造永不触发的僵尸提醒。"""
    spec = seed_demo.build_demo_spec(_NOW_LATE)
    assert _reminders_by_key(spec)["water"]["remind_at"] == _utc(10, 26, 7, 0)  # 上海 10-26 15:00


def test_clinic_anchors_today_when_window_has_no_tuesday():
    """冻结在周二：窗口（前 6 天）没有周二，复诊锚到今天上午，过去记录里没有复诊。"""
    spec = seed_demo.build_demo_spec(_NOW_TUESDAY)
    by_key = _reminders_by_key(spec)

    assert by_key["clinic"]["remind_at"] == _utc(10, 20, 1, 0)  # 上海今天（周二）09:00
    assert _occurrences(spec, "clinic") == []


# ---------- 执行记录：条数与状态分布 ----------


def test_occurrence_counts_and_status_distribution():
    """过去 6 天：吃降压药/晨间遛弯全完成，量血压 4 完成 2 漏服，复诊落周二，共 19 条。"""
    spec = seed_demo.build_demo_spec(_NOW)

    assert len(_occurrences(spec, "bp_med")) == 7  # 6 天 done + 当天 missed（见下一条用例）
    assert all(item["status"] == "done" for item in _occurrences(spec, "walk")[:-1])
    assert len(_occurrences(spec, "walk")) == 7  # 6 天 done + 当天 done
    measure = [item for item in _occurrences(spec, "bp_measure") if item["scheduled_at"] < _utc(10, 25, 0, 0)]
    assert len(measure) == 6
    missed = [item for item in measure if item["status"] == "missed"]
    assert [item["scheduled_at"].day for item in missed] == [21, 23]  # D-4 / D-2
    assert all(item["confirmed_at"] is None and item["finished_at"] is None for item in missed)

    clinic = _occurrences(spec, "clinic")
    assert [item["scheduled_at"] for item in clinic] == [_utc(10, 20, 1, 0)]  # 窗口内唯一的周二
    assert clinic[0]["status"] == "done"

    assert len(spec["occurrences"]) == 21  # 6 天 19 条 + 当天 2 条（宽限期已过）


def test_today_slots_beyond_grace_are_seeded_others_left_to_scheduler():
    """当天槽位：已过宽限期（+2h）的才由 seed 写入——晨间遛弯 done、吃降压药 missed；
    未过宽限期的量血压（21:00）/喝水（15:00）不写，留给调度器补齐。"""
    spec = seed_demo.build_demo_spec(_NOW)

    today_rows = [item for item in spec["occurrences"] if item["scheduled_at"] >= _utc(10, 24, 16, 0)]
    by_key = {item["reminder_key"]: item for item in today_rows}
    assert set(by_key) == {"walk", "bp_med"}

    assert by_key["walk"]["scheduled_at"] == _utc(10, 24, 23, 30)  # 上海 10-25 07:30
    assert by_key["walk"]["status"] == "done"
    assert by_key["walk"]["confirmed_at"] and by_key["walk"]["finished_at"]

    assert by_key["bp_med"]["scheduled_at"] == _utc(10, 25, 0, 0)  # 上海 10-25 08:00
    assert by_key["bp_med"]["status"] == "missed"
    assert by_key["bp_med"]["confirmed_at"] is None and by_key["bp_med"]["finished_at"] is None


def test_done_occurrences_carry_confirmed_and_finished():
    """完成记录带确认与完成时间，且都在计划时刻之后（上海 21:00 量血压 +5 分钟仍在当天）。"""
    spec = seed_demo.build_demo_spec(_NOW)

    done_items = [item for item in spec["occurrences"] if item["status"] == "done"]
    assert done_items
    assert all(item["confirmed_at"] and item["finished_at"] for item in done_items)
    assert all(item["confirmed_at"] > item["scheduled_at"] for item in done_items)
    assert all(item["finished_at"] > item["scheduled_at"] for item in done_items)


# ---------- 留言与紧急事件 ----------


def test_messages_carry_one_unread_and_mirror_emergency_format():
    spec = seed_demo.build_demo_spec(_NOW)

    unread = [item for item in spec["messages"] if item["read_at"] is None]
    assert len(unread) == 1
    assert unread[0]["from_uid"] == seed_demo.CHILD_UID  # 子女→老人 关怀留言驱动角标
    assert "降温" in unread[0]["content"]

    sos_messages = [item for item in spec["messages"] if "【紧急求助】" in item["content"]]
    assert len(sos_messages) == 2
    assert all(item["from_uid"] == seed_demo.ELDER_UID for item in sos_messages)
    assert "按下了 SOS 求助按钮" in sos_messages[0]["content"]
    assert "10月24日 14:00" in sos_messages[0]["content"]
    assert "我没事了" in sos_messages[1]["content"]
    assert "10月24日 14:05" in sos_messages[1]["content"]
    assert all(item["read_at"] is not None for item in sos_messages)


def test_emergency_event_is_resolved_with_five_minute_timeline():
    spec = seed_demo.build_demo_spec(_NOW)

    assert len(spec["emergency_events"]) == 1
    event = spec["emergency_events"][0]
    assert event["source"] == "sos"
    assert event["status"] == "resolved"
    assert event["resolved_at"] - event["created_at"] == timedelta(minutes=5)
    assert event["created_at"] == _utc(10, 24, 6, 0)  # 上海 10-24 14:00


# ---------- uid 边界与安全 ----------


def test_spec_only_references_demo_accounts():
    spec = seed_demo.build_demo_spec(_NOW)
    demo_uids = {seed_demo.ELDER_UID, seed_demo.CHILD_UID}
    uids = (
        {spec["elder_uid"], spec["child_uid"]}
        | {item["owner_uid"] for item in spec["reminders"]}
        | {item["target_uid"] for item in spec["reminders"] + spec["occurrences"]}
        | {item["from_uid"] for item in spec["messages"]}
        | {item["to_uid"] for item in spec["messages"]}
        | {item["elder_uid"] for item in spec["emergency_events"]}
    )
    assert uids <= demo_uids


def test_missing_password_fails_before_touching_db(monkeypatch, capsys):
    """缺 YUXI_DEMO_PASSWORD：不触库、退出码非零、报错只含变量名。"""
    monkeypatch.delenv(seed_demo.DEMO_PASSWORD_ENV, raising=False)
    # 容器内 /app/.env 可能带着该变量，屏蔽 .env 读取以模拟"任何渠道都没配"
    monkeypatch.setattr(seed_demo, "load_project_env", lambda: None)

    async def _must_not_run(*args, **kwargs):
        raise AssertionError("seed_demo 不应在缺少密码时触库")

    monkeypatch.setattr(seed_demo, "seed_demo", _must_not_run)

    assert seed_demo.main(argv=[]) == 1
    err = capsys.readouterr().err
    assert seed_demo.DEMO_PASSWORD_ENV in err


def test_success_message_never_contains_password():
    spec = seed_demo.build_demo_spec(_NOW)

    message = seed_demo.build_success_message(spec, already_ready=False)
    assert seed_demo.ELDER_NAME in message and seed_demo.CHILD_NAME in message
    assert "18 完成 / 3 漏服" in message  # 6 天 17/2 + 当天宽限期已过的遛弯 done、降压药 missed
    assert "请勿用于真实环境" in message

    ready_message = seed_demo.build_success_message(spec, already_ready=True)
    assert "--reset" in ready_message

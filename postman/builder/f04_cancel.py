# -*- coding: utf-8 -*-
"""04 取消：R4 正常取消、释放时段、重复取消、取消窗口、原因边界。"""

from __future__ import annotations

from . import err, folder, ok, req

KEY = "tst-{{run_ts}}-"


def booking(cabinet_id: int, start: str, end: str, *, key: str, size: str = "SMALL") -> dict:
    return {
        "cabinet_id": cabinet_id,
        "start_time": start,
        "end_time": end,
        "luggage_size": size,
        "idempotency_key": key,
        "luggage_count": 1,
    }


FOLDER = folder(
    "04 取消（R4）",
    [
        req(
            "04-01 正常取消并释放时段",
            "POST",
            "/reservations/{{order_no_reserved}}/cancel",
            body={"reason": "行程变更"},
            tests=ok(
                200,
                "const b = pm.response.json();",
                "pm.test('状态与释放数', () => {",
                "    pm.expect(b.status).to.eql('CANCELLED');",
                "    pm.expect(b.released_slot_count).to.eql(2);",
                "});",
                "pm.test('取消时间非空', () => pm.expect(b.cancelled_at).to.be.a('string').and.not.empty);",
            ),
            desc="对应 TC-CAN-01 / BR-20：released_slot_count 必须等于订单 slot_count，否则说明时段表与订单不一致。",
        ),
        req(
            "04-02 取消后同一时段可以再约",
            "POST",
            "/reservations",
            body=booking(1, "{{t_tomorrow_10}}", "{{t_tomorrow_11}}", key=KEY + "rebook"),
            tests=ok(
                201,
                "const b = pm.response.json();",
                "pm.collectionVariables.set('order_no_rebook', b.order_no);",
                "pm.test('重新预约成功', () => pm.expect(b.status).to.eql('RESERVED'));",
            ),
            desc="对应 TC-RES-21 / BR-20：取消是物理释放占用记录，不是只改订单状态。",
        ),
        req(
            "04-03 重复取消（终态保护）",
            "POST",
            "/reservations/{{order_no_reserved}}/cancel",
            body={},
            tests=err(409, "ORDER_STATUS_NOT_ALLOWED"),
            desc="对应 TC-CAN-05 / BR-34：终态订单不可再变更。",
        ),
        req(
            "04-04 取消 144 个时段的订单（批量释放）",
            "POST",
            "/reservations/{{order_no_144}}/cancel",
            body={"reason": "边界用例清理"},
            tests=ok(
                200,
                "const b = pm.response.json();",
                "pm.test('释放数 = 144', () => pm.expect(b.released_slot_count).to.eql(144));",
            ),
            desc="对应 TC-CAN-01 的批量释放分支：一条订单对应 144 条 reservation_slots。",
        ),
        req(
            "04-05 管理端：把取消窗口改为 2880 分钟",
            "PUT",
            "/admin/configs/cancel_ahead_minutes",
            auth="admin",
            body={"value": "2880"},
            tests=ok(
                200,
                "const b = pm.response.json();",
                "pm.test('配置已更新', () => {",
                "    pm.expect(b.key).to.eql('cancel_ahead_minutes');",
                "    pm.expect(b.value).to.eql('2880');",
                "});",
            ),
            desc="对应 TC-CAN-02 的构造手法：不改数据库时间，通过合法配置把「提前 2 天截止」变成已过期。",
        ),
        req(
            "04-06 创建一笔明日订单（用于取消窗口测试）",
            "POST",
            "/reservations",
            body=booking(4, "{{t_tomorrow_10}}", "{{t_tomorrow_11}}", key=KEY + "late"),
            tests=ok(
                201,
                "const b = pm.response.json();",
                "pm.collectionVariables.set('order_no_late', b.order_no);",
                "pm.test('订单已创建', () => pm.expect(b.status).to.eql('RESERVED'));",
            ),
            desc="该订单不会被取消，05 文件夹复用它验证签到窗口。",
        ),
        req(
            "04-07 取消窗口已过期",
            "POST",
            "/reservations/{{order_no_late}}/cancel",
            body={},
            tests=err(409, "CANCEL_WINDOW_EXPIRED"),
            desc="对应 TC-CAN-03 / BR-19：明日 10:00 开始，要求提前 2880 分钟（2 天）取消，截止时间已过。",
        ),
        req(
            "04-08 管理端：恢复取消窗口为 30 分钟",
            "PUT",
            "/admin/configs/cancel_ahead_minutes",
            auth="admin",
            body={"value": "30"},
            tests=ok(
                200,
                "const b = pm.response.json();",
                "pm.test('配置已恢复默认值', () => pm.expect(b.value).to.eql('30'));",
            ),
            desc="故障恢复点：无论 04-07 是否通过，都应执行本请求，避免污染后续运行。",
        ),
        req(
            "04-09 取消原因超长（129 字符）",
            "POST",
            "/reservations/{{order_no_rebook}}/cancel",
            body={"reason": "x" * 129},
            tests=err(400, "VALIDATION_ERROR"),
            desc="对应 TC-CAN-07：reason 上限 128，超长在进入业务逻辑前就被拒绝，订单应保持 RESERVED。",
        ),
        req(
            "04-10 清理：取消 04-02 的订单",
            "POST",
            "/reservations/{{order_no_rebook}}/cancel",
            body={"reason": "Postman 用例清理"},
            tests=ok(
                200,
                "const b = pm.response.json();",
                "pm.test('04-09 失败未改变订单状态', () => pm.expect(b.status).to.eql('CANCELLED'));",
            ),
            desc="清理动作：若 04-09 的校验失败仍然写入了取消，这里会得到 409 而不是 200，可反向验证「失败请求无残留」。",
        ),
    ],
    desc="依赖 03 创建的 order_no_reserved / order_no_144；04-05~04-08 会临时修改系统配置并在同一文件夹内恢复。",
)

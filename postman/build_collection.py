# -*- coding: utf-8 -*-
"""生成 Postman Collection 与 Environment。

为什么用脚本生成而不是手写 JSON：
1. 120 多个请求的 URL、鉴权、事件结构高度重复，手写容易出现字段名或括号错误；
2. 生成后可运行 verify_collection.py，把集合里的 (method, path) 与 FastAPI
   的 openapi() 逐条比对，从机制上避免"集合里有、代码里没有"的接口；
3. 接口变更时只改 builder/ 下的模块，重新生成即可。

用法（在项目根目录）：
    python postman/build_collection.py
输出：
    postman/luggage-locker.postman_collection.json
    postman/luggage-locker-local.postman_environment.json
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
import sys

BASE_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from builder import COLLECTION_PREREQUEST, BEARER_USER  # noqa: E402
from builder import f00_login, f01_auth, f02_query, f03_create  # noqa: E402
from builder import f04_cancel, f05_lifecycle, f06_orders  # noqa: E402
from builder import f07_admin_master, f08_admin_ops  # noqa: E402

COLLECTION_PATH = BASE_DIR / "luggage-locker.postman_collection.json"
ENVIRONMENT_PATH = BASE_DIR / "luggage-locker-local.postman_environment.json"

# 运行期变量（由请求的测试脚本写入）。导出 Collection 时会带上当前值，
# 但 Environment 不保存 token，避免把运行期凭据写进环境文件。
COLLECTION_VARIABLES = [
    "token_user",
    "token_admin",
    "token_user2",
    "user_id",
    "user2_id",
    "admin_id",
    "run_ts",
    "reg_username",
    "order_no_reserved",
    "order_no_adjacent",
    "order_no_idem",
    "order_no_144",
    "order_no_large",
    "order_no_late",
    "order_no_rebook",
    "order_no_inuse",
    "order_no_completed",
    "order_no_force",
    "tst_point_id",
    "tst_group_id",
    "tst_type_id",
    "tst_cabinet_id",
]


def build_collection() -> dict:
    return {
        "info": {
            "name": "智能行李寄存柜预约系统 · 接口测试集合",
            "description": (
                "基于 backend/app/api/v1 实际实现生成，覆盖 36 个操作。\n\n"
                "【执行顺序】必须按文件夹 00 → 08 顺序运行：\n"
                "00 登录准备 token → 01 认证异常 → 02 查询 → 03 创建 → 04 取消 → "
                "05 生命周期 → 06 订单 → 07/08 管理端。\n\n"
                "【前置条件】服务已启动（默认 http://127.0.0.1:8138/api/v1）、"
                "数据库为种子基线、admin/user01/user02 密码均为 Demo@123456。\n\n"
                "【断言口径】只断言 HTTP 状态码、业务错误码与响应字段；"
                "数据库层不变量（如 reservation_slots 是否真的删除）见 docs/03-测试方案.md。\n\n"
                "【未覆盖】真并发（Postman 单线程，见 JMeter 方案）、"
                "需要 SQL 构造时间的用例（签到超时、任务释放）、性能。\n\n"
                "【结果】所有用例的“实际结果”默认为待执行，执行后再回填，不预填通过。"
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": BEARER_USER,
        "event": [
            {
                "listen": "prerequest",
                "script": {"type": "text/javascript", "exec": COLLECTION_PREREQUEST},
            }
        ],
        "variable": [{"key": key, "value": "", "type": "string"} for key in COLLECTION_VARIABLES],
        "item": [
            f00_login.FOLDER,
            f01_auth.FOLDER,
            f02_query.FOLDER,
            f03_create.FOLDER,
            f04_cancel.FOLDER,
            f05_lifecycle.FOLDER,
            f06_orders.FOLDER,
            f07_admin_master.FOLDER,
            f08_admin_ops.FOLDER,
        ],
    }


def build_environment() -> dict:
    values = [
        ("base_url", "http://127.0.0.1:8138/api/v1", "default"),
        ("username", "user01", "default"),
        ("password", "Demo@123456", "secret"),
        ("admin_username", "admin", "default"),
        ("admin_password", "Demo@123456", "secret"),
        ("user2_username", "user02", "default"),
        ("user2_password", "Demo@123456", "secret"),
        ("point_id", "1", "default"),
        ("group_id", "1", "default"),
        ("cabinet_id", "1", "default"),
        ("cabinet_maintenance_id", "12", "default"),
        ("cabinet_large_id", "11", "default"),
    ]
    return {
        "id": "6f1c2a40-0000-4000-8000-000000000001",
        "name": "行李寄存-本地",
        "values": [
            {"key": k, "value": v, "type": t, "enabled": True} for k, v, t in values
        ],
        "_postman_variable_scope": "environment",
        "_postman_exported_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "_postman_exported_using": "postman/build_collection.py",
    }


def main() -> None:
    collection = build_collection()
    environment = build_environment()
    COLLECTION_PATH.write_text(
        json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    ENVIRONMENT_PATH.write_text(
        json.dumps(environment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    def count(items: list[dict]) -> int:
        return sum(count(i["item"]) if "item" in i else 1 for i in items)

    print(f"collection: {COLLECTION_PATH}")
    print(f"environment: {ENVIRONMENT_PATH}")
    print(f"folders: {len(collection['item'])}, requests: {count(collection['item'])}")


if __name__ == "__main__":
    main()

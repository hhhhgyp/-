# -*- coding: utf-8 -*-
"""Postman 集合构造基础设施。

各 folder 模块只描述"请求长什么样"，URL / 鉴权 / 事件 / JSON 结构
统一由本模块生成，避免 120 多个请求手写 JSON 时出现结构不一致。

所有请求路径都来自 backend/app/api/v1/*.py，可用 postman/verify_collection.py
与 FastAPI 的 openapi() 做机器比对。
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------- 鉴权
BEARER_ADMIN = {
    "type": "bearer",
    "bearer": [{"key": "token", "value": "{{token_admin}}", "type": "string"}],
}
BEARER_USER = {
    "type": "bearer",
    "bearer": [{"key": "token", "value": "{{token_user}}", "type": "string"}],
}
BEARER_USER2 = {
    "type": "bearer",
    "bearer": [{"key": "token", "value": "{{token_user2}}", "type": "string"}],
}
NO_AUTH = {"type": "noauth"}

AUTH_MAP = {
    "admin": BEARER_ADMIN,
    "user": BEARER_USER,
    "user2": BEARER_USER2,
    "none": NO_AUTH,
}

# ---------------------------------------------------------------- 时间变量
# 集合级预请求脚本：每个请求发出前重新计算，保证跨天/跨时段执行仍然成立。
# 只使用本机本地时区，避免 toISOString() 的 UTC 偏移把 10:00 变成 02:00。
COLLECTION_PREREQUEST = [
    "// ===== 时间变量：每次请求前重算（本地时区） =====",
    "const pad = n => String(n).padStart(2, '0');",
    "const fmt = d => d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':00';",
    "const at = (dayOffset, h, m) => {",
    "    const d = new Date();",
    "    d.setDate(d.getDate() + dayOffset);",
    "    d.setHours(h, m, 0, 0);",
    "    return fmt(d);",
    "};",
    "const setVar = (k, v) => pm.collectionVariables.set(k, v);",
    "",
    "setVar('t_yesterday_10', at(-1, 10, 0));",
    "setVar('t_yesterday_11', at(-1, 11, 0));",
    "setVar('t_tomorrow_0730', at(1, 7, 30));",
    "setVar('t_tomorrow_0830', at(1, 8, 30));",
    "setVar('t_tomorrow_10', at(1, 10, 0));",
    "setVar('t_tomorrow_1015', at(1, 10, 15));",
    "setVar('t_tomorrow_1030', at(1, 10, 30));",
    "setVar('t_tomorrow_11', at(1, 11, 0));",
    "setVar('t_tomorrow_1115', at(1, 11, 15));",
    "setVar('t_tomorrow_1130', at(1, 11, 30));",
    "setVar('t_tomorrow_12', at(1, 12, 0));",
    "setVar('t_tomorrow_13', at(1, 13, 0));",
    "setVar('t_tomorrow_14', at(1, 14, 0));",
    "setVar('t_tomorrow_15', at(1, 15, 0));",
    "setVar('t_tomorrow_16', at(1, 16, 0));",
    "setVar('t_tomorrow_17', at(1, 17, 0));",
    "setVar('t_tomorrow_2130', at(1, 21, 30));",
    "setVar('t_tomorrow_2230', at(1, 22, 30));",
    "setVar('t_day4_10', at(4, 10, 0));",
    "setVar('t_day4_1030', at(4, 10, 30));",
    "",
    "// 超出 7 天窗口：now + 8 天再向下对齐到 30 分钟，任何时刻执行都 > now + 7 天",
    "const plus8 = new Date(Date.now() + 8 * 24 * 3600 * 1000);",
    "plus8.setSeconds(0, 0);",
    "plus8.setMinutes(plus8.getMinutes() - (plus8.getMinutes() % 30));",
    "setVar('t_plus8d', fmt(plus8));",
    "const plus8End = new Date(plus8.getTime() + 3600 * 1000);",
    "setVar('t_plus8d_end', fmt(plus8End));",
    "// 一次运行内保持稳定：由 00-01 在每次运行开始时强制刷新",
    "if (!pm.collectionVariables.get('run_ts')) { setVar('run_ts', String(Date.now())); }",
]


# ---------------------------------------------------------------- 构造器
def make_url(path: str, query: list[tuple[str, str]] | None = None) -> dict:
    raw = "{{base_url}}" + path
    if query:
        raw += "?" + "&".join(f"{k}={v}" for k, v in query)
    url: dict[str, Any] = {
        "raw": raw,
        "host": ["{{base_url}}"],
        "path": [seg for seg in path.strip("/").split("/") if seg],
    }
    if query:
        url["query"] = [{"key": k, "value": v} for k, v in query]
    return url


def raw_json(obj: dict) -> dict:
    return {
        "mode": "raw",
        "raw": json.dumps(obj, ensure_ascii=False, indent=2),
        "options": {"raw": {"language": "json"}},
    }


def _events(pre: list[str] | None, tests: list[str] | None) -> list[dict]:
    events: list[dict] = []
    if pre:
        events.append(
            {"listen": "prerequest", "script": {"type": "text/javascript", "exec": pre}}
        )
    if tests:
        events.append(
            {"listen": "test", "script": {"type": "text/javascript", "exec": tests}}
        )
    return events


def req(
    name: str,
    method: str,
    path: str,
    *,
    auth: str | None = None,
    query: list[tuple[str, str]] | None = None,
    body: dict | None = None,
    headers: list[tuple[str, str]] | None = None,
    pre: list[str] | None = None,
    tests: list[str] | None = None,
    desc: str = "",
) -> dict:
    """构造一个 Postman 请求项。

    auth=None 表示继承文件夹/集合鉴权；"none" 表示显式无鉴权。
    """
    request: dict[str, Any] = {
        "method": method.upper(),
        "header": [],
        "url": make_url(path, query),
        "description": desc,
    }
    if headers:
        request["header"].extend({"key": k, "value": v} for k, v in headers)
    if body is not None:
        request["header"].append({"key": "Content-Type", "value": "application/json"})
        request["body"] = raw_json(body)
    if auth is not None:
        request["auth"] = AUTH_MAP[auth]
    item: dict[str, Any] = {"name": name, "request": request}
    events = _events(pre, tests)
    if events:
        item["event"] = events
    return item


def folder(
    name: str,
    items: list[dict],
    *,
    auth: str | None = None,
    desc: str = "",
) -> dict:
    node: dict[str, Any] = {"name": name, "item": items}
    if desc:
        node["description"] = desc
    if auth is not None:
        node["auth"] = AUTH_MAP[auth]
    return node


# ---------------------------------------------------------------- 断言片段
def ok(status: int, *extra: str) -> list[str]:
    return [f"pm.test('HTTP {status}', () => pm.response.to.have.status({status}));", *extra]


def err(status: int, code: str, *extra: str) -> list[str]:
    return [
        f"pm.test('HTTP {status}', () => pm.response.to.have.status({status}));",
        "const b = pm.response.json();",
        f"pm.test('业务码 = {code}', () => pm.expect(b.code).to.eql('{code}'));",
        *extra,
    ]

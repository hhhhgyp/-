# -*- coding: utf-8 -*-
"""一致性校验：Collection 中的每个请求都必须对应 FastAPI 实际存在的操作。

校验内容：
1. (method, path) 与 app.openapi() 双向比对：
   - 集合调用了代码里没有的接口 -> 失败（防止编造接口）
   - 代码里有但集合没覆盖的接口 -> 失败（防止"完整集合"名不副实）
2. 请求名唯一；
3. 每个请求都有 test 脚本，且至少包含一个 pm.test；
4. 关键路径拼写（check-in / release-expired/run / groups/{id}/cabinets）。

用法（项目根目录）：
    python postman/verify_collection.py
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys

BASE_DIR = pathlib.Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent / "backend"
COLLECTION_PATH = BASE_DIR / "luggage-locker.postman_collection.json"
API_PREFIX = "/api/v1"


def walk(items: list[dict]):
    for item in items:
        if "item" in item:
            yield from walk(item["item"])
        else:
            yield item


def norm_collection_path(raw: str) -> str:
    path = raw.split("?")[0]
    path = path.replace("{{base_url}}", "")
    path = re.sub(r"\{\{[^}]+\}\}", "{}", path)
    return "/" + path.strip("/")


def norm_openapi_path(path: str) -> str:
    if path.startswith(API_PREFIX):
        path = path[len(API_PREFIX):]
    path = re.sub(r"\{[^}]+\}", "{}", path)
    return "/" + path.strip("/") or "/"


def main() -> int:
    collection = json.loads(COLLECTION_PATH.read_text(encoding="utf-8"))
    requests = list(walk(collection["item"]))

    # ---- 名称唯一 ----
    names = [item["name"] for item in requests]
    duplicates = sorted({name for name in names if names.count(name) > 1})

    # ---- 每个请求必须有断言 ----
    no_tests = [
        item["name"]
        for item in requests
        if not any(
            event.get("listen") == "test"
            and any("pm.test(" in line for line in event["script"]["exec"])
            for event in item.get("event", [])
        )
    ]

    # ---- 与 OpenAPI 比对 ----
    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))
    from app.main import app  # noqa: E402

    spec = app.openapi()
    openapi_ops = {
        (method.upper(), norm_openapi_path(path))
        for path, operations in spec["paths"].items()
        for method in operations
        if method.lower() in {"get", "post", "put", "patch", "delete"}
    }
    collection_ops = {
        (item["request"]["method"].upper(), norm_collection_path(item["request"]["url"]["raw"]))
        for item in requests
    }

    # 路径模板匹配：集合里的 99999 / cancel_ahead_minutes 等字面量，
    # 只要能被 OpenAPI 的同位置参数占位符匹配，就算同一条接口。
    openapi_by_shape: dict[tuple[str, int], list[str]] = {}
    for method, path in openapi_ops:
        segs = [s for s in path.strip("/").split("/") if s]
        openapi_by_shape.setdefault((method, len(segs)), []).append(path)

    def find_openapi(method: str, path: str) -> tuple[str, str] | None:
        # 字面量路由优先：/reservations/my 必须命中 /reservations/my，
        # 而不是被 /reservations/{order_no} 的模板抢走。
        if (method, path) in openapi_ops:
            return (method, path)
        segs = [s for s in path.strip("/").split("/") if s]
        for candidate in openapi_by_shape.get((method, len(segs)), []):
            osegs = [s for s in candidate.strip("/").split("/") if s]
            if all(o == "{}" or o == c for o, c in zip(osegs, segs)):
                return (method, candidate)
        return None

    matched: set[tuple[str, str]] = set()
    invented: list[tuple[str, str]] = []
    for op in sorted(collection_ops):
        hit = find_openapi(*op)
        if hit is None:
            invented.append(op)
        else:
            matched.add(hit)

    uncovered = sorted(openapi_ops - matched)

    print(f"requests           : {len(requests)}")
    print(f"unique names       : {'OK' if not duplicates else duplicates}")
    print(f"requests w/o tests : {'OK' if not no_tests else no_tests}")
    print(f"openapi operations : {len(openapi_ops)}")
    print(f"covered operations : {len(matched)}")
    print(f"invented endpoints : {'OK' if not invented else invented}")
    print(f"uncovered endpoints: {'OK' if not uncovered else uncovered}")

    # ---- 关键路径拼写（防止把 check-in 写成 checkin）----
    expected_snippets = [
        "/reservations/{{order_no_late}}/check-in",
        "/reservations/{{order_no_force}}/check-in",
        "/admin/jobs/release-expired/run",
        "/admin/groups/{{tst_group_id}}/cabinets",
    ]
    raws = [item["request"]["url"]["raw"] for item in requests]
    missing_snippets = [s for s in expected_snippets if not any(s in raw for raw in raws)]
    print(f"key paths          : {'OK' if not missing_snippets else missing_snippets}")

    # ---- 变量闭环：所有 {{var}} 必须有定义（环境变量 / 集合变量 / 预请求脚本）----
    environment = json.loads(
        (BASE_DIR / "luggage-locker-local.postman_environment.json").read_text(encoding="utf-8")
    )
    defined = {item["key"] for item in collection.get("variable", [])}
    defined |= {item["key"] for item in environment["values"]}
    for event in collection.get("event", []):
        if event.get("listen") == "prerequest":
            for line in event["script"]["exec"]:
                defined.update(re.findall(r"setVar\('([^']+)'", line))
    used = set(re.findall(r"\{\{([^}]+)\}\}", json.dumps(collection, ensure_ascii=False)))
    undefined = sorted(used - defined)
    print(f"undefined variables: {'OK' if not undefined else undefined}")

    ok = not (duplicates or no_tests or invented or uncovered or missing_snippets or undefined)
    print("RESULT             :", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

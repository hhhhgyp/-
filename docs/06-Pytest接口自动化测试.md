# 06 - Pytest 接口自动化测试指南

> 适用代码：`backend/tests/`  
> 技术栈：Python 3.11、pytest 8.3.4、requests 2.32.3、pytest-html 4.1.1、SQLAlchemy 2.x  
> 测试对象：本项目真实 FastAPI 服务 + 真实 MySQL 数据库，**不使用 mock，不伪造执行结果**。  
> 最近一次全量执行：2026-10-20，**71 passed / 0 failed，5.54 s**，HTML 报告已生成。

---

## 1. 这套测试解决什么问题

Postman 集合解决的是“接口契约 + 手工可回放”的问题；pytest 套件解决的是“可持续回归 + 数据隔离 + 数据库断言 + 并发验证”的问题。两者分工如下：

| 维度 | Postman | pytest |
|---|---|---|
| 接口契约、请求示例 | ✅ 128 个请求 | 覆盖核心接口 |
| 业务规则回归 | 断言为主 | 断言 + 数据库状态 |
| 测试数据隔离 | 依赖集合脚本清理 | session 级隔离柜组 + 函数级清理 |
| 并发正确性 | 不做 | ✅ 8 线程同柜格抢锁、并发幂等 |
| 可重复执行 | Newman CLI | `pytest` + HTML/JUnit 报告 |

---

## 2. 目录结构

```text
backend/
├─ pytest.ini                       # testpaths、markers、严格模式
├─ requirements-dev.txt             # requests / pytest / pytest-html
└─ tests/
   ├─ __init__.py
   ├─ config.py                     # 环境变量配置；时间/幂等键工具
   ├─ api_client.py                 # ApiClient 公共请求封装、login、assert_error
   ├─ db.py                         # 数据库校验助手（只读查询）
   ├─ factories.py                  # 预约请求体构造
   ├─ conftest.py                   # 全部 fixtures
   ├─ test_01_auth.py               # 13 例：认证与权限
   ├─ test_02_query.py              # 12 例：寄存点 / 柜体 / 可用性
   ├─ test_03_reservation.py        # 18 例：创建 / 冲突 / 边界 / 幂等
   ├─ test_04_lifecycle.py          # 14 例：取消 / 签到 / 取件 / 强制取消
   ├─ test_05_admin.py              # 12 例：管理端查询 / 统计 / 任务 / 配置
   ├─ test_06_concurrency.py        #  2 例：真实多线程并发
   └─ reports/
      └─ api-report.html            # 运行后生成（自包含 HTML）
```

设计原则：

1. **公共请求封装**：所有请求经 `ApiClient.request()`，统一 base_url、超时、Bearer Token、状态码断言；失败信息带 URL 和响应体。
2. **配置外置**：`config.py` 只从环境变量读取，不在代码里写死账号或地址。
3. **三层断言**：HTTP 状态码 → 业务 `code` → 字段/关系/数据库状态。
4. **测试数据自建自清**：不依赖“数据库里刚好有某条数据”，也不把清理责任留给下一个人。

---

## 3. 依赖安装

在 `backend` 目录执行（Windows PowerShell）：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# 首次安装测试依赖（会同时校验运行依赖）
pip install -r requirements-dev.txt

# 确认版本
python -m pytest --version
```

`requirements-dev.txt` 内容：

```text
-r requirements.txt
requests==2.32.3
pytest==8.3.4
pytest-html==4.1.1
```

> 如果不想动现有虚拟环境，也可以新建一个 venv，但仍需先安装 `requirements.txt`，因为测试会直接导入 `app.db.session` 做数据库校验。

---

## 4. 环境配置

### 4.1 前置条件

1. MySQL 8 已启动，`luggage_locker` 库已按 `sql/01-schema.sql`、`sql/02-seed.sql` 初始化。
2. 后端服务已启动（建议关闭 scheduler，避免定时任务与手工任务用例互相干扰）：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python run.py --port 8138 --no-reload --no-scheduler
```

3. 健康检查可访问：

```powershell
Invoke-WebRequest http://127.0.0.1:8138/api/v1/health -UseBasicParsing
```

返回 `status=ok` 且 `database.ok=true` 再执行测试。

### 4.2 环境变量

全部有默认值，本地基线数据可直接运行；换环境时只改环境变量，不改代码。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `TEST_BASE_URL` | `http://127.0.0.1:8138/api/v1` | 被测服务地址（含 `/api/v1`） |
| `TEST_USERNAME` | `user01` | 普通用户 1 |
| `TEST_PASSWORD` | `Demo@123456` | 普通用户 1 密码 |
| `TEST_USER2_USERNAME` | `user02` | 普通用户 2（越权用例） |
| `TEST_USER2_PASSWORD` | `Demo@123456` | 普通用户 2 密码 |
| `TEST_ADMIN_USERNAME` | `admin` | 管理员 |
| `TEST_ADMIN_PASSWORD` | `Demo@123456` | 管理员密码 |
| `TEST_TIMEOUT` | `10` | 单请求超时（秒） |

PowerShell 示例：

```powershell
$env:TEST_BASE_URL = "http://127.0.0.1:8138/api/v1"
$env:TEST_USERNAME = "user01"
$env:TEST_PASSWORD = "Demo@123456"
python -m pytest -m core -v
```

> 数据库校验直接复用后端 `.env` 中的 `DATABASE_URL`。如果测试进程连不到库，先检查 `.env`，而不是在测试里另写一套连接串。

---

## 5. 运行命令

### 5.1 先跑核心（推荐第一次这样验证）

```powershell
cd backend
python -m pytest -m core -v
```

预期：`43 passed`。

### 5.2 再跑扩展

```powershell
python -m pytest -m extended -v
```

预期：`28 passed`。

### 5.3 API 全量（不含 UI）

```powershell
python -m pytest -m "not ui" -v
```

接口 + UI 全量（需要 Chrome/Edge 与可访问前端）：

```powershell
python -m pytest -v
```

### 5.4 只跑某个文件 / 某个用例

```powershell
python -m pytest tests/test_03_reservation.py -v
python -m pytest tests/test_04_lifecycle.py::test_checkin_and_complete_lifecycle -v
```

### 5.5 查看用例清单

```powershell
python -m pytest --collect-only -q
```

当前共 **71** 个 API 用例（参数化展开后）；加上 `tests/ui/` 的 8 条 Selenium UI 用例（含 2 条管理页守卫回归），全量为 **79**。

> 建议顺序执行。不要用 `pytest-xdist` 并行跑全量：`test_05_admin.py` 里有全局统计和任务日志断言，多进程会互相改变分母；并发能力由 `test_06_concurrency.py` 内部 8 线程真实验证，不需要进程级并行。

---

## 6. 测试报告

### 6.1 HTML（自包含，单文件可发）

```powershell
python -m pytest -v `
  --html=tests/reports/api-report.html `
  --self-contained-html
```

打开：

```powershell
start tests\reports\api-report.html
```

报告包含：用例总数、通过/失败、耗时、失败堆栈、环境信息（Python、pytest、插件版本）。

### 6.2 JUnit XML（给 CI / Jenkins / GitLab）

```powershell
python -m pytest -q --junitxml=tests/reports/junit.xml
```

### 6.3 终端精简输出

```powershell
python -m pytest -q
```

---

## 7. fixtures 设计

| fixture | 作用域 | 说明 |
|---|---|---|
| `config` | session | 读取环境变量，生成 `Settings` |
| `anon` | session | 未登录客户端 |
| `admin` | session | 管理员登录后的客户端 |
| `user_api` / `user_api_body` | session | `user01` 客户端与登录响应 |
| `user2_api` | session | `user02` 客户端，用于越权用例 |
| `sandbox` | session | **隔离测试数据**：新建寄存点 + 柜体 + 6 个 S 柜格 |
| `slot_factory` | session | 为每个测试分配互不重叠的柜格与时段 |
| `order_cleanup` | function | 登记本用例创建的订单，结束后取消；失败则管理员强制取消 |
| `book` | function | 创建预约、自动登记清理，返回 response |
| `config_override` | function | 修改系统配置并在用例结束后恢复原值 |
| `temp_user` / `temp_user_client` | function | 注册临时用户，结束后按用户名删除 |

### 7.1 为什么需要 `sandbox`

种子数据（SP001、A-01~A-12）是所有演示和 Postman 共用的，直接拿来跑写操作用例会互相污染。`sandbox` 在 session 开始时通过管理端真实接口创建：

```text
POST /admin/points
POST /admin/points/{point_id}/groups
POST /admin/groups/{group_id}/cabinets   (prefix=PYxxxx-, count=6, type=S)
```

测试只写这 6 个柜格。session 结束时按 FK 顺序清理：

```text
reservation_status_logs → reservation_slots → reservations
→ cabinets → cabinet_groups → storage_points
```

即使建柜格时中途失败，也会按 `group_id` 反查已创建的柜格再删，不会留下悬挂数据。

### 7.2 时段分配

`slot_factory` 用递增计数器分配：

```text
6 个柜格 × 每天 10:00 / 13:00 / 16:00 × D+2 起
```

每个测试拿到不同的 `(cabinet_id, start, end)`，所以同一柜格可以在不同时间段被多个用例复用；单条用例结束时会释放自己的订单。

### 7.3 配置回滚

`config_override` 先读取当前值，再修改；用例结束按原值 PUT 回去。当前覆盖过的键：

- `checkin_early_minutes`：15 → 10080（让未来订单可签到）
- `cancel_ahead_minutes`：30 → 2880（构造“已过取消窗口”）

全量执行后已核对：`30 / 15 / 144 / 500` 均恢复基线。

### 7.4 订单清理

`order_cleanup` 对每个登记订单：

1. 先调用用户取消 `POST /reservations/{order_no}/cancel`；
2. 返回 200 → 已释放；
3. 非 200（已签到、已完成、已取消等终态）→ 调用管理员强制取消；
4. 强制取消也失败（已终态）→ 忽略，最终由 `sandbox` 的 SQL 清理兜底。

---

## 8. 用例清单（71 例）

### 8.1 认证与权限（13）

| # | 用例 | 关键断言 |
|---|---|---|
| 1 | 健康检查 | `status=ok`、`database.ok=true`、有 `server_time` |
| 2 | 登录成功 | `token_type=bearer`、`expires_in>0`、用户资料无口令字段 |
| 3 | `/auth/me` | 用户名、角色、`token_version` |
| 4-5 | 错误口令 / 不存在用户 | 401 `AUTH_INVALID_CREDENTIALS` |
| 6 | 不带 Token | 401 `AUTH_TOKEN_MISSING` |
| 7 | 伪造 Token | 401 `AUTH_TOKEN_INVALID` |
| 8 | 普通用户访问管理端 | 403 `AUTH_FORBIDDEN` |
| 9 | 登出后旧 Token | 登出 200，再访问 `/auth/me` → 401 `AUTH_TOKEN_INVALID` |
| 10 | 重复用户名注册 | 409 `USERNAME_EXISTS` |
| 11-13 | 注册参数校验 | 用户名过短 / 密码缺字母 / 密码过短 → 400 `VALIDATION_ERROR` |

### 8.2 查询（12）

| # | 用例 | 关键断言 |
|---|---|---|
| 1 | 寄存点分页 + 关键字 | 分页字段、`total=len(items)`、能搜到 sandbox 点 |
| 2 | `page_size=101` | 400 `VALIDATION_ERROR` |
| 3 | 寄存点详情 | SP001：2 个柜体、20 个柜格 |
| 4 | 柜体列表 | A 组 12 格、B 组 8 格、均为 NORMAL |
| 5 | 规格列表 | 至少含 S/M/L，粒度为 30 分钟，单价 > 0 |
| 6 | Q5 全空闲 | 6 个柜格全部可用，`slot_count=2` |
| 7 | Q5 尺寸过滤 | S 柜格对 `LARGE` 可用数为 0 |
| 8-10 | Q5 时间窗异常 | 未对齐 → `TIME_NOT_ALIGNED`；零时长 → `DURATION_OUT_OF_RANGE` |
| 11 | Q6 单柜格可用 | `available=true`、无冲突 |
| 12 | Q6 不存在柜格 | 404 `RESOURCE_NOT_FOUND` |

### 8.3 预约创建（18）

| # | 用例 | 关键断言 |
|---|---|---|
| 1 | 正常创建 | 201；`RESERVED`；金额=单价×时段数；签到截止=开始+30 分钟；DB 2 条 slot；日志 `None→RESERVED` |
| 2 | 相邻时段 | 第一单 10:00-11:00，第二单 11:00-12:00 → 均 201 |
| 3 | 完全重叠 | 409 `CABINET_TIME_CONFLICT`；DB 仍只有 2 条 slot |
| 4 | 部分重叠 | 10:30-11:30 → 409 |
| 5 | 冲突后取消再订 | 取消释放 slot 后同窗口可再次 201 |
| 6-9 | 创建参数规则 | `luggage_count=2/0` → `MULTI_LUGGAGE_NOT_SUPPORTED`；S 柜格订 LARGE → `SIZE_NOT_MATCH`；7 位幂等键 → `VALIDATION_ERROR` |
| 10 | 过去时间 | 400 `TIME_IN_PAST` |
| 11 | 超过 7 天 | 400 `BOOKING_WINDOW_EXCEEDED` |
| 12 | 结束=开始 | 400 `DURATION_OUT_OF_RANGE` |
| 13 | 不存在柜格 | 404 `RESOURCE_NOT_FOUND` |
| 14 | 维护中柜格 A-12 | 409 `CABINET_NOT_AVAILABLE` |
| 15 | 144 个时段（72h） | 201；DB 144 条 slot；取消释放 144 |
| 16 | 145 个时段 | 400 `DURATION_OUT_OF_RANGE` |
| 17 | 顺序重复提交 | 同幂等键第二次 → 200；`idempotent_replay=true`；同一 `order_no`；DB 仅 1 单 |
| 18 | 下单后 Q6 | `available=false`，`conflicts` 非空 |

### 8.4 状态流转（14）

| # | 用例 | 关键断言 |
|---|---|---|
| 1 | 用户取消 | 200；`CANCELLED`；释放 2；DB `cancelled_at/reason`；日志 `RESERVED→CANCELLED` |
| 2 | 重复取消 | 409 `ORDER_STATUS_NOT_ALLOWED` |
| 3 | 过早签到 | 409 `CHECKIN_WINDOW_INVALID`，状态仍 RESERVED |
| 4 | 未签到直接取件 | 409 `ORDER_STATUS_NOT_ALLOWED` |
| 5 | 签到→取件 | 改配置后可签到：`IN_USE`；取件：`COMPLETED`，释放 2；日志三段完整 |
| 6 | 取消后签到 | 409 `ORDER_STATUS_NOT_ALLOWED` |
| 7 | 管理员强制取消使用中订单 | 200；`FORCE_CANCELLED`；释放 2；日志操作人 ADMIN、备注一致 |
| 8 | 强制取消原因校验 | 缺失 / 129 字符 → 400 `VALIDATION_ERROR` |
| 9 | 强制取消终态订单 | 409 `ORDER_STATUS_NOT_ALLOWED` |
| 10 | 已过取消窗口 | `cancel_ahead_minutes=2880` 时取消 D+1 订单 → 409 `CANCEL_WINDOW_EXPIRED` |
| 11 | 他人订单越权 | 403 `AUTH_FORBIDDEN`（详情、取消）；他人列表不含该单 |
| 12 | 订单不存在 | 404 `RESOURCE_NOT_FOUND` |
| 13 | 我的订单状态筛选 | `status=RESERVED/CANCELLED` 过滤正确，取消后从 RESERVED 列表消失 |
| 14 | 签到截止时间 | 详情中的 `checkin_deadline` = 开始时间 + 30 分钟 |

### 8.5 管理端（12）

| # | 用例 | 关键断言 |
|---|---|---|
| 1 | M6b 柜体柜格 | 6 条、编号与 sandbox 一致、`point_id` 正确 |
| 2 | M6 批量创建全有或全无 | 重复编号 → 409 `DUPLICATE_CODE`，柜格数仍为 6 |
| 3 | M10 按订单号 | `total=1`、用户名正确、可强制取消 |
| 4 | M10 按用户名+状态 | 只返回 RESERVED，且包含目标单 |
| 5 | 运营统计关系 | `point_count≥3`、`cabinet_count≥26`、活动单≥1、分子≤分母 |
| 6 | M13 手工跑任务 + M14 日志 | 两次均 SUCCESS，第二次 `affected_count=0`，日志≥2 条 |
| 7 | M15 配置契约 | 含 `max_slot_count`，`default_value=144`，有上下界 |
| 8-11 | 配置校验 | 未知键 404；0 / 非数字 / 超界 → 400 |
| 12 | 普通用户访问管理端 | 403 `AUTH_FORBIDDEN`（统计、日志、配置） |

### 8.6 并发（2）

| # | 用例 | 验证方式 |
|---|---|---|
| 1 | 同一柜格同一时段 8 线程抢锁 | `Barrier` 同时发起；**恰好 1 个 201**，其余 409；DB 只有 2 条 slot、1 个活动订单 |
| 2 | 同一幂等键 8 线程重复提交 | **恰好 1 个 201 + 7 个 200**；8 个响应 `order_no` 相同；DB 仅 1 单 |

> 这两条是“并发正确性”验证，不是性能压测；线程数、吞吐、P95 等指标留给 JMeter。

---

## 9. 数据库校验点

测试不只信接口返回，关键流程都直接查库：

| 校验 | 表 | 用途 |
|---|---|---|
| 订单状态 / 金额 / 快照 / 截止时间 | `reservations` | 防止“接口说成功、库里没落” |
| 时段占用 | `reservation_slots` | 验证 2 条、144 条、释放后 0 条 |
| 状态审计链 | `reservation_status_logs` | 验证状态顺序、操作人类型、备注 |
| 幂等键唯一 | `reservations.idempotency_key` | 顺序/并发重复提交只落 1 单 |
| 窗口内 slot 数 | `reservation_slots` | 冲突请求不能留下半条占用 |
| 活动订单数 | `reservations` | 并发后只允许 1 个成功订单 |

SQL 全部在 `tests/db.py`，只读；唯一写库的地方是 fixture 清理（删除本套件创建的数据），不碰种子数据。

---

## 10. 真实执行结果

### 10.1 最终 API 全量

```text
platform win32 -- Python 3.11.9, pytest-8.3.4, pluggy-1.7.0
plugins: anyio-4.15.1, html-4.1.1, metadata-3.1.1
collected 71 items

tests/test_01_auth.py .................... 13 passed
tests/test_02_query.py ................... 12 passed
tests/test_03_reservation.py ............. 18 passed
tests/test_04_lifecycle.py ............... 14 passed
tests/test_05_admin.py ................... 12 passed
tests/test_06_concurrency.py .............  2 passed

71 passed in 5.54s
```

HTML 报告：

```text
backend/tests/reports/api-report.html
大小：约 79 KB（自包含）
生成时间：2026-10-20 09:45:44
```

### 10.2 分阶段结果

| 阶段 | 命令 | 结果 |
|---|---|---|
| 核心首轮 | `pytest -m core` | 18 passed / 25 errors |
| 核心第二轮 | `pytest -m core` | 33 passed / 10 failed |
| 核心修正后 | `pytest -m core` | **43 passed** |
| 扩展首轮 | `pytest -m extended` | 23 passed / 5 failed |
| 扩展修正后 | `pytest -m extended` | **28 passed** |
| 全量 | `pytest` | **71 passed，5.54 s** |

### 10.3 失败原因与修正（不是伪造通过）

首轮失败全部是**测试代码对接口契约的假设错误**，不是服务端缺陷；逐条核对 OpenAPI/源码后修正：

1. M6 批量创建响应字段是 `created`，不是 `items`；同时清理逻辑改为按 `group_id` 反查柜格，避免半成品数据卡住 FK。
2. 时间窗错误码是细分的 `TIME_NOT_ALIGNED` / `DURATION_OUT_OF_RANGE` / `TIME_IN_PAST` / `BOOKING_WINDOW_EXCEEDED`，不是统一的 `VALIDATION_ERROR`。
3. 创建响应不返回 `idempotency_key`（只在库中），改为断言请求键与 DB 值一致。
4. `luggage_count=0` 也走 `MULTI_LUGGAGE_NOT_SUPPORTED`，不是参数校验错误。
5. `cabinets` 表没有 `point_id`，需 join `cabinet_groups` 获取。
6. 取消窗口方向理解反了：`cancel_ahead_minutes` 是“至少提前多久”，要构造“即将开始”的订单才会触发 `CANCEL_WINDOW_EXPIRED`。
7. 配置键是 `max_slot_count`，不是 `max_booking_slots`。

> 这些修正同时反向校验了接口文档：错误码、字段名、配置键都以代码和 OpenAPI 为准。

---

## 11. 数据清理与基线恢复

全量执行后已用 SQL 核对：

| 检查项 | 结果 |
|---|---|
| `storage_points` 中 `TST-PY-%` | 0 |
| `cabinets` 中 `PY%-%` | 0 |
| `reservations` 中 `idempotency_key LIKE 'pytest-%'` | 0 |
| `users` 中 `pytest_%` | 0 |
| 活动订单（RESERVED/IN_USE/OVERDUE） | 0 |
| `cancel_ahead_minutes / checkin_early_minutes / max_slot_count / release_job_batch_size` | `30 / 15 / 144 / 500` |

说明：

- `job_execution_logs` 中保留了手工触发任务的审计记录，这是正常业务日志，不建议删除；如需绝对干净，可按 `trigger_type='MANUAL' AND created_at` 时间范围清理。
- 若测试进程被强杀，`sandbox` 的 `finally` 可能来不及执行；下次运行前执行兜底脚本：

```powershell
cd backend
python tests\cleanup_test_data.py --dry-run   # 先确认要删除的 ID
python tests\cleanup_test_data.py             # 再执行删除
```

脚本只处理 `TST-PY-%` 寄存点、其下柜体/柜格、这些柜格上的订单与时段/日志，以及 `pytest_xxxxxxxx` 临时用户；不会碰 SP001/SP002 和种子柜格。

---

## 12. 已知边界与未覆盖项

| 项 | 说明 |
|---|---|
| 精确 30 分钟边界 | 例如“结束时间恰好等于闭店时间”“签到截止时间恰好等于当前秒”，受真实时钟影响，自动化里不构造；已在 `docs/04` 标记为待执行，由人工在固定时间点验证 |
| 调度器进程 | 本套件用 `--no-scheduler` 启动，验证的是 M13 手工任务接口与幂等；APScheduler 的进程级行为已在第四阶段单独验证 |
| 支付 | 本期为模拟支付，不参与业务规则，未覆盖支付回调 |
| 性能 | 并发用例只验证正确性（1 个成功），不做吞吐/P95/资源监控；这部分交给 JMeter |
| 种子基线 | 用例假设 SP001 有 20 个柜格、A-12 为维护中、S/M/L 三种规格存在；换库后需同步调整 |
| 并行执行 | 不建议 `pytest-xdist` 跑全量；管理端统计/任务日志是全局视角 |

---

## 13. 常见问题

**Q1：启动测试直接报连接拒绝？**  
先确认 `python run.py --port 8138 --no-reload --no-scheduler` 已启动，再访问 `/api/v1/health`。测试不会自动拉起服务。

**Q2：`sandbox` fixture 创建失败？**  
检查管理员账号是否能登录、`cabinet-types` 中是否有启用的 S 规格、柜格前缀是否与历史数据冲突。失败时 `finally` 仍会清理已创建的点/柜体。

**Q3：为什么不用 mock？**  
本项目要验证的是锁、唯一索引、状态机、配置回滚这些真实行为；mock 掉数据库就失去了测试价值。所有结果均来自真实 HTTP + MySQL。

**Q4：报告里没有请求/响应体？**  
pytest-html 默认记录失败堆栈；`ApiClient` 的断言消息已包含 URL 和响应体前 1000 字符，失败时可直接定位。需要完整请求留痕时，用 Postman/Newman 的 `--reporters cli,json` 互补。

**Q5：能只跑某个 marker 吗？**  
可以：`pytest -m core`、`pytest -m extended`、`pytest -m db`（只跑带数据库断言的用例）。

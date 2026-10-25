# 08 - JMeter 并发预约测试设计与执行记录

> 测试对象：本项目的真实 FastAPI 服务 + MySQL 8；不是 mock，也不是只根据 HTTP 成功率推断业务正确性。  
> JMeter：**5.6.3**，Java 8；数据核对通过 `backend/.venv` 中的 SQLAlchemy 直接查询 MySQL。  
> 本次执行时间：2026-10-20 10:17–10:41（CST）；服务地址：`http://127.0.0.1:8138`，启动参数 `--no-reload --no-scheduler`。  
> 本文只记录**实际执行的配置、响应计数和数据库事实**；不预设吞吐量、响应时间 SLA 或“系统可支撑 N 并发”的结论。

---

## 1. 先核实的接口、鉴权和数据库约束

### 1.1 预约创建

| 项目 | 已核实内容 |
|---|---|
| 方法与路径 | `POST /api/v1/reservations` |
| 鉴权 | `Authorization: Bearer <access_token>`；token 来自 `POST /auth/login` |
| 请求体 | `cabinet_id`、`start_time`、`end_time`、`luggage_size`、`idempotency_key` |
| 时间格式 | ISO 本地时间，例如 `2026-10-22T10:00:00`；开始/结束需按 30 分钟对齐 |
| 新订单 | **HTTP 201**，`idempotent_replay=false` |
| 幂等重放 | 同一 `user_id + idempotency_key` **HTTP 200**，`idempotent_replay=true`，订单号相同 |
| 柜格已占 | **HTTP 409 `CABINET_TIME_CONFLICT`** |
| 其他失败 | 400 参数/时间规则；404 资源不存在；409 状态或资源冲突；503 `LOCK_TIMEOUT` |

并发语义的关键实现位置：

- `reservations` 表：`uk_reservations_user_idem (user_id, idempotency_key)`，所以**幂等键不是全局唯一，而是按用户隔离**。S3 因此使用同一个用户、同一个 key。
- `reservation_slots` 表：`uk_slots_cabinet_slot (cabinet_id, slot_start)`，从数据库层保证同一柜格同一时段最多一条占用记录；这是判断超卖的最终事实，而不是 HTTP 201 计数。
- 创建预约时先对柜格行执行 `SELECT ... FOR UPDATE`，再检查冲突并写入时段；并发下仍由唯一索引兜底。
- 占用状态只包括 `RESERVED / IN_USE / OVERDUE`；取消/完成/过期/强取消的订单不继续占用时段。

### 1.2 取消订单

| 项目 | 已核实内容 |
|---|---|
| 方法与路径 | `POST /api/v1/reservations/{order_no}/cancel` |
| 鉴权 | 必须为订单所有者，`Authorization: Bearer <token>` |
| 请求体 | `{"reason": "..."}`，`reason` 可选，最大 128 字符 |
| 成功 | **HTTP 200**，`status=CANCELLED`，`released_slot_count` 为实际删除的时段数 |
| 重复/并发取消 | 只有一个请求能成功；其余通常为 **HTTP 409 `ORDER_STATUS_NOT_ALLOWED`** |
| 取消窗口 | 默认 `cancel_ahead_minutes=30`；本次数据使用未来时段，因此并发取消不受窗口阻挡 |

取消的业务正确性不能只看 200：还要核对订单状态、`reservation_slots` 是否释放、以及是否只有一条取消状态日志。

---

## 2. 测试数据：可重复、隔离、可清理

数据准备脚本：`jmeter/tools/jmeter_data.py`。每次运行生成随机 `run_id`，创建独立数据，避免使用种子数据 `A-12` 等共享资源：

| 数据 | 本次做法 |
|---|---|
| 寄存点 | `JM-<run_id>`，营业时间 08:00–22:00 |
| 柜体/柜格 | `JMG-<run_id>` / `JM<run_id前4位>-NN`；规格 `S`，仅本次测试使用 |
| 用户 | `jmeter_<run_id>_NN`，密码 `Jmeter@123456`；每个线程一个用户（重复/取消场景只需一个所有者） |
| 时段 | 运行日 + 2 天，固定 10:00–11:00；30 分钟对齐，处于未来预约窗口内 |
| 幂等键 | S1/S2 每次请求生成 `run_id + UUID`；S3 使用固定 key；S4 使用准备阶段创建的订单 |
| 清理 | 按本次 `run.json` 的 point/group/order/user 删除；不触碰种子账号 `123`、`user01`、`user02` |

### 2.1 数据准备、核对、清理命令

在项目根目录执行：

```powershell
# 创建“同一柜格竞争”数据：4 个用户、1 个柜格
backend\.venv\Scripts\python.exe jmeter\tools\jmeter_data.py prepare `
  --scenario same --users 4 --cabinets 1

# 创建“有限柜格竞争”数据：12 个用户、6 个柜格
backend\.venv\Scripts\python.exe jmeter\tools\jmeter_data.py prepare `
  --scenario limited --users 12 --cabinets 6

# 创建“幂等重复提交”数据：1 个用户、1 个柜格
backend\.venv\Scripts\python.exe jmeter\tools\jmeter_data.py prepare `
  --scenario duplicate --users 1 --cabinets 1

# 创建“并发取消”数据：1 个用户、1 个柜格，并预先创建一个待取消订单
backend\.venv\Scripts\python.exe jmeter\tools\jmeter_data.py prepare `
  --scenario cancel --users 1 --cabinets 1

# 清理当前 data/run.json 对应的本次测试数据
backend\.venv\Scripts\python.exe jmeter\tools\jmeter_data.py cleanup
```

`prepare` 会生成：

```text
jmeter/data/threads.csv          # token,username,cabinet_id,idempotency_key
jmeter/data/scenario.properties # host/port/时段/柜格/token/订单号/场景
jmeter/data/run.json             # point/group/cabinet/user 元数据，供核对和清理
```

> `threads.csv` 和 `scenario.properties` 含临时 token，属于运行时文件，不应提交到仓库。

### 2.2 清理后的实际核对

最后一次运行结束后执行清理，并用 SQL 核对：

```sql
SELECT COUNT(*) FROM storage_points WHERE code LIKE 'JM-%';       -- 0
SELECT COUNT(*) FROM cabinet_groups WHERE code LIKE 'JMG-%';      -- 0
SELECT COUNT(*) FROM cabinets WHERE code LIKE 'JM%';              -- 0
SELECT COUNT(*) FROM users WHERE username LIKE 'jmeter_%';        -- 0
SELECT COUNT(*) FROM reservations r
JOIN storage_points p ON p.id = r.point_id
WHERE p.code LIKE 'JM-%';                                        -- 0
```

本次四个场景全部执行并清理后，以上计数均为 **0**；没有遗留 JMeter 测试订单或用户。

---

## 3. 线程组、并发用户数、Ramp-up、循环次数

### 3.1 设计原则

1. **一个线程先完成登录和数据准备，负载只测预约/取消接口**：避免把登录成功率和 token 过期混入并发预约结论。
2. **S1/S2 每个线程使用不同用户**：验证“多用户竞争”而不是同一账号重复提交。
3. **S3 故意使用同一用户、同一幂等键**：验证幂等约束，而不是资源冲突。
4. **S4 故意使用同一订单、同一所有者 token**：验证并发取消的状态机条件更新。
5. **Ramp-up 只用于错开启动、让请求重叠**；JMeter 线程启动不是硬同步，最终以数据库唯一索引和订单事实为准。
6. **核心正确性场景 loops=1**；`loops>1` 可用于观察重复轮次，但 S1/S2 每轮都会生成新的幂等键，不能把第二轮当成新资源。

### 3.2 四个线程组

| 场景 | 计划文件 | 初始线程数 | Ramp-up | 循环 | 资源设置 | 预期 HTTP 结果 | 数据库必须满足 |
|---|---|---|---:|---:|---:|---|---|
| S1 竞争同一柜格 | `jmeter/plans/same-cabinet.jmx` | 4 | 1 s | 1 | 1 柜格、4 用户 | 1×201，3×409 | 1 活动订单、2 时段、1 个柜格、0 重复槽 |
| S2 竞争有限柜格 | `jmeter/plans/limited-cabinets.jmx` | 12 | 2 s | 1 | 6 柜格、12 用户 | 6×201，6×409 | 6 活动订单、12 时段、6 个不同柜格、0 重复槽 |
| S3 重复提交 | `jmeter/plans/duplicate-submit.jmx` | 8 | 1 s | 1 | 1 柜格、同一用户/key | 1×201，7×200 | 1 订单、2 时段、所有响应同一订单号 |
| S4 并发取消 | `jmeter/plans/concurrent-cancel.jmx` | 8 | 1 s | 1 | 一个待取消订单 | 1×200，7×409 | `CANCELLED`、0 时段、1 条取消日志 |

加压时**增加线程数**，而不是把 S1/S2 的 loops 调大：

| 场景 | 初始 | 加压后本次实际执行 |
|---|---:|---:|
| S1 | 4 用户 | 16 用户，ramp 2 s |
| S2 | 12 用户 / 6 柜格 | 24 用户 / 6 柜格，ramp 3 s |
| S3 | 8 线程 | 16 线程，ramp 1 s |
| S4 | 8 线程 | 16 线程，ramp 1 s |

> 本次没有继续盲目加大到 32/64。原因是 JMeter、FastAPI、MySQL 同机运行，且没有独立的压测机；继续加负载前应先采集 CPU、内存、MySQL 连接数/锁等待，否则容易把环境饱和误判为业务缺陷或系统容量。

---

## 4. 请求参数、断言与结果监听

### 4.1 请求参数

S1/S2 的请求体由 JSR223 PreProcessor 生成：

```json
{
  "cabinet_id": 123,
  "start_time": "2026-10-22T10:00:00",
  "end_time": "2026-10-22T11:00:00",
  "luggage_size": "SMALL",
  "idempotency_key": "<run_id>-<UUID>"
}
```

S3 固定使用 `data/scenario.properties` 中的 `cabinet_id` 和 `idempotency_key`；S4 使用预先创建的 `${order_no}` 和所有者 token：

```text
POST /api/v1/reservations/{order_no}/cancel
{"reason":"JMeter 并发取消测试"}
```

认证头由 HTTP Header Manager 统一设置：

```text
Authorization: Bearer ${token}
Content-Type: application/json
```

S1/S2 的 `${token}` 来自 CSV；S3/S4 使用 `${__P(token)}`。

### 4.2 断言策略

每个采样器有：

1. **Response Assertion（Assume Success）**：允许 4xx 进入业务断言。竞争场景的 409 是预期业务结果，不应该被 JMeter 默认的“4xx=失败”掩盖；但这也意味着 **JMeter 的 `Err: 0` 不能当作业务正确性证明**。
2. **JSR223 业务语义断言**：
   - S1/S2：201 必须是 `status=RESERVED`、`idempotent_replay=false`、有 `order_no`；409 的业务码必须是 `CABINET_TIME_CONFLICT`；503 直接判失败并提示环境饱和；其他状态失败。
   - S3：只允许 200/201；201 必须是首次创建；200 必须是 `idempotent_replay=true`；必须有 `order_no`。
   - S4：200 必须是 `CANCELLED` 且 `released_slot_count=2`；409 必须是 `ORDER_STATUS_NOT_ALLOWED`；其他状态失败。
3. **JTL 样本变量**：后置处理器把 `jm_code`、`jm_order_no`、`jm_idem_replay` 写入 JTL，供外部脚本统计业务码和订单号，而不是只读取 HTTP 状态。
4. **数据库事实核对**：`jmeter/tools/jmeter_data.py verify` 读取 JTL 后，先核对“样本数 = 线程数 × 循环数”，再直接查询 MySQL，核对成功数、活动订单、时段数、柜格唯一性、重复 `(cabinet_id, slot_start)`、幂等订单号、取消状态与日志。样本数检查用于防止线程未真正发出请求时被少量响应“蒙混过关”。

另外做了一次**故意失败探针**：把 `start_time` 改为未对齐的 `10:15`，服务返回 400 `TIME_NOT_ALIGNED`；JTL 的 `success=false`，`failureMessage` 记录了业务错误，证明“Assume Success”不会吞掉 JSR223 业务断言失败。探针证据保留在 `jmeter/results/assertion-failure-probe.jtl`。

### 4.3 监听与报告

| 用途 | 做法 |
|---|---|
| 原始结果 | `-l results/<name>.jtl`（CSV，保留响应码、线程、时间、sample variables） |
| 汇总查看 | `-e -o results/<name>-html` 生成 JMeter HTML Dashboard |
| 失败定位 | `results/<name>.log` + JTL 的 `failureMessage`；不在压测中打开 View Results Tree |
| 业务核对 | `verify` 输出 `results/verify-<scenario>-<run_id>.json`，逐条列出 PASS/FAIL |

不使用响应时间阈值作为本次通过条件；本次目标是并发正确性，不是容量验收。

---

## 5. 执行步骤

### 5.1 安装与启动

1. 安装 JMeter 5.6.3（Java 8+）。Windows 可解压到例如 `C:\apache-jmeter-5.6.3`。
2. 确认后端已启动：

```powershell
Invoke-WebRequest http://127.0.0.1:8138/api/v1/health -UseBasicParsing
```

3. 确认 Python 虚拟环境可用：

```powershell
backend\.venv\Scripts\python.exe --version
```

### 5.2 一键运行（推荐）

`jmeter/run.ps1` 会依次执行：清理旧数据 → 准备新数据 → JMeter 非 GUI 运行 → JTL 核对 → 清理数据。

```powershell
$env:JMETER_HOME = "C:\apache-jmeter-5.6.3"   # 改成自己的解压目录

# 初始规模
.\jmeter\run.ps1 -Scenario same -Threads 4 -Ramp 1 -Loops 1
.\jmeter\run.ps1 -Scenario limited -Threads 12 -Cabinets 6 -Ramp 2 -Loops 1
.\jmeter\run.ps1 -Scenario duplicate -Threads 8 -Ramp 1 -Loops 1
.\jmeter\run.ps1 -Scenario cancel -Threads 8 -Ramp 1 -Loops 1

# 加压（本次实际执行）
.\jmeter\run.ps1 -Scenario same -Threads 16 -Ramp 2 -Loops 1
.\jmeter\run.ps1 -Scenario limited -Threads 24 -Cabinets 6 -Ramp 3 -Loops 1
.\jmeter\run.ps1 -Scenario duplicate -Threads 16 -Ramp 1 -Loops 1
.\jmeter\run.ps1 -Scenario cancel -Threads 16 -Ramp 1 -Loops 1
```

如果 JMeter 已经在 `PATH` 中，可以不设置 `JMETER_HOME`。也可以设置 `JMETER_CMD` 指向 `jmeter.bat` 的完整路径。

需要同时采集本机 CPU、内存、MySQL 连接数和 InnoDB 锁等待时，加 `-Monitor`：

```powershell
.\jmeter\run.ps1 -Scenario same -Threads 20 -Ramp 1 -Loops 2 -Monitor
```

它会额外生成 `results\<scenario>-<threads>-resources.csv` 和同名 `.summary.json`。监控器与 JMeter 同机运行，只用于观测，不改变 JMeter 的断言/数据库核对逻辑。

### 5.3 手工运行单个计划

```powershell
cd jmeter

# 先准备数据（在项目根目录执行，见 §2.1），然后：

& "$env:JMETER_HOME\bin\jmeter.bat" -n `
  -t plans\same-cabinet.jmx `
  -q data\scenario.properties `
  -Jthreads=4 -Jramp=1 -Jloops=1 `
  "-Jsample_variables=jm_code,jm_order_no,jm_idem_replay" `
  "-Jjmeter.save.saveservice.output_format=csv" `
  "-Jjmeter.save.saveservice.response_data=false" `
  "-Jjmeter.save.saveservice.assertion_results_failure_message=true" `
  -l results\same.jtl -e -o results\same-html

# 回到项目根目录做数据库事实核对（--samples = 线程数 × 循环数）
cd ..
backend\.venv\Scripts\python.exe jmeter\tools\jmeter_data.py verify `
  --jtl jmeter\results\same.jtl --samples 4
```

> JMeter 的 `-J` 参数值里含逗号时必须整体加引号（PowerShell 下尤其如此）。

---

## 6. 实际执行结果

以下为本次在本机实际执行的结果，均来自 JTL 与 MySQL 核对，未使用预设指标。

### 6.1 初始小规模

| 场景 | 样本数 | HTTP 计数 | 业务码计数 | 数据库事实 | 核对结果 |
|---|---:|---|---|---|---|
| S1 同一柜格（4 用户） | 4 | 201=1，409=3 | `CABINET_TIME_CONFLICT`=3 | 活动订单 1，时段 2，柜格 1，重复槽 0 | PASS |
| S2 有限柜格（12 用户 / 6 格） | 12 | 201=6，409=6 | `CABINET_TIME_CONFLICT`=6 | 活动订单 6，时段 12，不同柜格 6，重复槽 0 | PASS |
| S3 重复提交（8 线程） | 8 | 201=1，200=7 | 无错误业务码 | 订单 1，时段 2，订单号集合 1 | PASS |
| S4 并发取消（8 线程） | 8 | 200=1，409=7 | `ORDER_STATUS_NOT_ALLOWED`=7 | `CANCELLED`，时段 0，取消日志 1 | PASS |

初始运行中 503 均为 **0**，JSR223 断言失败数均为 **0**。

### 6.2 加压后

| 场景 | 样本数 | HTTP 计数 | 业务码计数 | 数据库事实 | 核对结果 |
|---|---:|---|---|---|---|
| S1 同一柜格（16 用户） | 16 | 201=1，409=15 | `CABINET_TIME_CONFLICT`=15 | 活动订单 1，时段 2，柜格 1，重复槽 0 | PASS |
| S2 有限柜格（24 用户 / 6 格） | 24 | 201=6，409=18 | `CABINET_TIME_CONFLICT`=18 | 活动订单 6，时段 12，不同柜格 6，重复槽 0 | PASS |
| S3 重复提交（16 线程） | 16 | 201=1，200=15 | 无错误业务码 | 订单 1，时段 2，订单号集合 1 | PASS |
| S4 并发取消（16 线程） | 16 | 200=1，409=15 | `ORDER_STATUS_NOT_ALLOWED`=15 | `CANCELLED`，时段 0，取消日志 1 | PASS |

另外执行了一次 **loops=2** 的 S1 探针（4 用户、8 个请求）：201=1、409=7；数据库仍只有 1 个活动订单、2 条时段。它验证了“每轮生成新幂等键”后，循环不会把第二轮的重复提交误当作新的资源成功。对应文件为 `jmeter/results/loops2-probe.jtl` / `verify-same-6f663a.json`。

### 6.3 结果文件

| 内容 | 路径 |
|---|---|
| 初始 S1 JTL / HTML | `jmeter/results/same.jtl` / `same-html/` |
| 初始 S2 JTL / HTML | `jmeter/results/limited.jtl` / `limited-html/` |
| 初始 S3 JTL / HTML | `jmeter/results/duplicate.jtl` / `duplicate-html/` |
| 初始 S4 JTL / HTML | `jmeter/results/cancel.jtl` / `cancel-html/` |
| 加压 S1 JTL / HTML | `jmeter/results/same-16.jtl` / `same-16-html/` |
| 加压 S2 JTL / HTML | `jmeter/results/limited-24.jtl` / `limited-24-html/` |
| 加压 S3 JTL / HTML | `jmeter/results/duplicate-16.jtl` / `duplicate-16-html/` |
| 加压 S4 JTL / HTML | `jmeter/results/cancel-16.jtl` / `cancel-16-html/` |
| 逐项 PASS/FAIL JSON | `jmeter/results/verify-<scenario>-<run_id>.json` |
| loops=2 探针 | `jmeter/results/loops2-probe.jtl` / `verify-same-6f663a.json` |
| 资源监控补充运行 | `jmeter/results/same-20.jtl` / `verify-same-16d971.json` / `same-20-resources.csv` / `same-20-resources.summary.json` |
| 故意失败探针 | `jmeter/results/assertion-failure-probe.jtl` |

本次主要 `run_id`：S1 `74bb5d` / `78fb52`；S2 `e46578` / `b76d48`；S3 `8c55cb` / `544974`；S4 `8423f4` / `8210cc`。资源补充运行 `run_id=16d971`。对应的 `verify-<scenario>-<run_id>.json` 即逐项核对记录。

JTL 中 409/200 是**预期业务响应**，所以 JMeter 控制台显示 `Err: 0`；这不是“所有请求都成功”，真正的通过条件是上表的数据库事实和 `verify` 检查。反过来，即使 HTTP 201 很多，只要活动订单数、时段数或唯一索引核对不通过，也必须判失败。

### 6.4 资源监控补充运行（20 线程 × 2 循环）

为了回答“这次并发到底把机器压到什么程度”，补了一次带资源监控的 S1：20 线程、Ramp-up 1 s、loops=2，共 40 个样本。它是**补充观测**，不计入上面的 8 组 / 104 样本主结果。

| 项 | 实测 |
|---|---|
| 结果 | 40 样本，201=1，409=39；`CABINET_TIME_CONFLICT`=39；31.57 req/s；平均 432 ms，最小 278 ms，最大 619 ms |
| 数据库事实 | 活动订单 1、slot 2、不同柜格 1、重复槽 0；`verify-same-16d971.json` 全部 PASS |
| 监控窗口 | 8 个样本（约 1~2 s/次，含 JMeter 结束后的 verify/cleanup），CSV + summary 见下表 |
| 整机 CPU | 平均 8.47%，峰值 13.06%（整机 0~100） |
| 可用内存 | 最低 1357.3 MB / 总 15607.7 MB；峰值负载前约 1717 MB |
| 后端进程 | CPU 峰值 7.81%（单核百分比），工作集峰值 102.1 MB |
| JMeter 进程 | CPU 峰值 282.81%（单核百分比，多核可超过 100），工作集峰值 443.0 MB |
| MySQL 连接 | `Threads_connected`=11；`Max_used_connections` 17→21；`max_connections`=151；`processlist`=12 |
| InnoDB 行锁 | `Innodb_row_lock_waits` 173→211（本窗口 +38）；`Innodb_row_lock_current_waits` 采样点均为 0；平均锁等待 57→72 ms，最大 228→270 ms |
| 慢查询 | `Slow_queries` 全程 0 |
| mysqld 进程 CPU | WMI 读数为 0，且服务进程句柄被拒绝；**不能据此判断 MySQL 空闲**，MySQL 活动以 Questions 单次采样最大增量 805（含监控自身查询）、锁等待 +38 为准 |

文件：`jmeter/results/same-20-resources.csv`、`same-20-resources.summary.json`、`same-20.jtl`、`verify-same-16d971.json`。运行后复查 JMeter 测试点/柜体/柜格/用户均为 0，订单/时段/状态日志也为 0。

**怎么读：**

- JMeter 是主要 CPU 消耗者，峰值 282.81%（单核百分比）约相当于 2.8 个核在跑；整机峰值只有 13.06%，因为本机有 16 个逻辑处理器，不能把“整机 13%”理解成“服务端很轻松”。
- 后端进程 CPU 峰值 7.81%、工作集约 100 MB，说明本次瓶颈不在 Python 内存；但这只是 20 线程、40 个请求的短时观测。
- `Max_used_connections` 只有 21/151，连接池不是本次瓶颈；`Innodb_row_lock_waits` 增长 38 次、当前等待采样为 0，说明冲突主要由数据库行锁/唯一约束串行化，而不是连接耗尽。
- 采样间隔约 1~2 s，且包含 verify/cleanup，峰值可能漏采；这些数字只能作为**本机短时诊断**，不能当 SLA 或容量上限。

---

## 7. 为什么不能只看请求成功率

本次专门做了两层核对：

1. **响应层**：HTTP 状态 + 业务码 + `idempotent_replay` / 订单号 / 取消状态。
2. **数据库层**：`reservations` 活动订单数、`reservation_slots` 行数、不同柜格数、`(cabinet_id, slot_start)` 重复组数、幂等键对应订单数、取消后的时段释放和状态日志。

如果只看 JMeter 的 `Err: 0`，会把 409 冲突当成成功；如果只看 201 数量，又可能忽略“订单写入了但 slot 不一致”。因此 `verify` 对每个场景都设置了硬性事实检查，任何一项不满足都会返回非 0 并以 `VERIFY FAILED` 结束。

---

## 8. 避免环境资源不足导致结论失真

本次执行和后续加压应遵守：

1. **同机风险**：JMeter、FastAPI、MySQL 在同一台 Windows 机器上；JMeter 的 CPU/GC 会抢占服务端资源。当前结果只能说明“本机该规模下功能正确”，不能外推为生产容量。
2. **503 单独处理**：`LOCK_TIMEOUT` 映射为 503，是锁等待/资源饱和信号。它不是 409 业务冲突，也不能算“预约失败符合预期”；一旦出现应停止加压，记录日志、降低线程数或延长数据库锁等待，而不是继续加线程。
3. **连接池边界**：服务默认 `DB_POOL_SIZE=10`、`DB_MAX_OVERFLOW=20`；高并发下需要同时观察 MySQL 连接数、`InnoDB` 锁等待和 Uvicorn 进程 CPU。线程数不应无限增加。`run.ps1 -Monitor` 会把 CPU/内存/连接/锁等待写入 `*-resources.csv`，但监控与压测同机，监控本身也会占资源。
4. **不要用 GUI 压测**：使用 `-n` 非 GUI；关闭 View Results Tree；仅保留 JTL 和 HTML Dashboard，避免 JMeter 自身成为瓶颈。
5. **数据隔离**：每次先 `cleanup` 再 `prepare`；不要复用同一批订单，否则第二轮会被幂等重放或已取消状态污染。
6. **时间窗口**：统一使用未来 2 天的整点时段；若服务器时区/当前时间变化，API 可能在进入并发前就以 400/过去时间拒绝，需先确认健康检查和系统时间。
7. **逐步加压**：先在 4/8/12 线程确认断言和数据库事实，再按 16/24 增加；每次观察 503、错误码分布和 `verify` 结果，不预设“必须达到多少 TPS”。
8. **资源读数要结合环境解释**：JMeter 的进程 CPU 是“单核百分比”，多核机器上可超过 100%；整机 CPU 是 0~100%。mysqld 以服务账号运行，进程句柄可能被拒绝，本次 mysqld CPU 的 WMI 读数不可靠，应同时看 `Questions` 增量和 `Innodb_row_lock_waits`。

---

## 9. 已知边界

- 本测试只覆盖**预约创建**和**取消**的并发正确性；没有测试登录接口的并发性能、前端 UI 并发、支付（项目为模拟支付）和定时任务。
- 预置 token 在数据准备阶段获取，负载阶段不包含登录耗时；这是有意的隔离，不应把本结果解释为“登录+预约”的端到端容量。
- S1/S2 的 JMeter 线程启动不是严格同一瞬间；Ramp-up 会产生毫秒级错开。真正防止超卖的是数据库唯一索引，`verify` 的重复槽/订单事实检查比“看起来同时”更重要。
- 本次主结果最大规模为 24 线程（S2）和 16 线程（S1/S3/S4）；资源补充运行另做了 20 线程 × 2 循环。都不代表系统上限。若继续扩容，建议使用独立压测机、监控服务端与 MySQL，并把 503/锁等待作为停止条件之一。
- 资源监控只覆盖 1 次 20 线程补充运行，采样 8 点（约 1~2 s/次），没有 JMeter GC 日志、没有 MySQL `SHOW ENGINE INNODB STATUS` 的逐锁快照，也没有长时间稳定性曲线；不能据此写容量结论。

---

## 10. 相关文件

```text
jmeter/
├─ plans/
│  ├─ same-cabinet.jmx
│  ├─ limited-cabinets.jmx
│  ├─ duplicate-submit.jmx
│  └─ concurrent-cancel.jmx
├─ tools/
│  ├─ build_plans.py        # 从模板生成四个 JMX，避免手写漂移
│  ├─ jmeter_data.py        # prepare / verify / cleanup
│  └─ resource_monitor.py   # CPU/内存/MySQL 连接与行锁采样（-Monitor）
├─ data/                    # 运行时数据（含临时 token，勿提交）
├─ results/                 # JTL、HTML Dashboard、verify JSON、*-resources.csv/summary.json
└─ run.ps1                  # 一键清理→准备→执行→核对→清理；-Monitor 采集资源
```

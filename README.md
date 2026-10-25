# 智能行李寄存柜预约系统

一个面向**软件测试实践与求职作品集**的行李寄存柜在线预约系统。
业务场景：旅游景点 / 车站的行李寄存柜，支持用户按时段提前预约柜格。

> 项目**不是**简单的增删改查：它包含可验证的业务规则、真实并发竞争场景、
> 数据库状态一致性要求，以及可被自动化断言的资源占用模型。

---

## 一、技术栈

| 层次 | 技术 |
|---|---|
| 后端 | Python 3.11 + FastAPI |
| 数据库 | MySQL 8.0（InnoDB / utf8mb4） |
| 数据访问 | SQLAlchemy 2.0 |
| 认证 | JWT（PyJWT）+ token_version |
| 定时任务 | APScheduler（进程内，单 worker） |
| 前端 | 原生 HTML / CSS / JavaScript（由 FastAPI 静态托管） |
| 测试 | Postman/Newman、Requests + pytest、Selenium、JMeter；关键流程直查 MySQL |

---

## 二、环境要求

| 项 | 版本 | 检查命令 |
|---|---|---|
| Python | 3.11 及以上 | `python --version` |
| MySQL | 8.0 及以上 | `mysql --version` |
| 浏览器 | Chrome / Edge | —— |

---

## 三、安装与配置

### 1. 启动 MySQL 服务（Windows）

```powershell
# 查看服务状态
Get-Service MySQL8

# 启动（需要管理员权限的 PowerShell）
net start MySQL8
```

### 2. 创建虚拟环境并安装依赖

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> 如果 PowerShell 提示「禁止运行脚本」，先执行：
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 3. 准备配置文件

```powershell
cd backend
Copy-Item .env.example .env
notepad .env
```

必须修改的项：

```ini
DB_PASSWORD=你的MySQL密码
JWT_SECRET_KEY=随便填一串32位以上的随机字符串
```

### 4. 初始化数据库

```powershell
# 建库 + 建表 + 写入 system_config 默认配置
python -m app.db.init_db --create-db

# 写入示例数据（幂等，可重复执行）
python -m app.db.seed
```

### 5. 启动服务

```powershell
python run.py
```

也可以直接双击 `backend\start.bat` 一键启动。

可用参数：

```powershell
python run.py --port 8001     # 换端口（8000 被占用时用）
python run.py --no-reload     # 关闭热重载（排查问题时推荐）
python run.py --force         # 跳过端口占用检查
```

| 地址 | 用途 |
|---|---|
| http://127.0.0.1:8000/ | 前端首页 |
| http://127.0.0.1:8000/docs | Swagger 接口文档 |
| http://127.0.0.1:8000/api/v1/health | 健康检查（含数据库连通性） |

---

## 四、示例账号（仅开发/测试环境）

| 角色 | 用户名 | 密码 |
|---|---|---|
| 管理员 | `admin` | `Demo@123456` |
| 普通用户 | `user01` | `Demo@123456` |
| 普通用户 | `user02` | `Demo@123456` |

**安全说明**

- 密码可用环境变量 `SEED_ADMIN_PASSWORD` / `SEED_USER_PASSWORD` 覆盖；
- `APP_ENV=production` 时若未配置上述变量，种子脚本会**直接拒绝执行**；
- `APP_ENV=production` 时若 `JWT_SECRET_KEY` 仍是默认值或 `DEBUG=true`，
  **应用会拒绝启动**，从机制上杜绝生产环境硬编码密钥。

---

## 五、目录结构

```
行李寄存/
├── docs/                        设计与测试文档（01-12）
│   ├── 01-项目设计方案.md
│   ├── 02-项目交付汇总.md
│   ├── 03-测试方案.md
│   ├── 04-测试用例.md
│   ├── 05-Postman接口测试指南.md
│   ├── 06-Pytest接口自动化测试.md
│   ├── 07-Selenium-UI自动化测试.md
│   ├── 08-JMeter并发预约测试.md
│   ├── 09-测试核验指南.md        MySQL 核验 SQL + Fiddler 抓包对比
│   ├── 10-测试交付成果与复盘.md  执行统计、缺陷、回归、JMeter 指标与简历描述
│   ├── 11-用例追溯矩阵.md        123 条用例 → 自动化/验收脚本/证据 → 缺口
│   └── 12-简历项目描述与面试追问清单.md  简历表述、自述模板、追问回答与边界
├── sql/
│   ├── 01-schema.sql            建表 DDL（由 ORM 自动生成，勿手工修改）
│   └── 02-seed.sql              示例数据 SQL（手工执行用，可选）
├── jmeter/                      JMeter 并发预约测试（plans / tools / results / run.ps1，支持 -Monitor 资源采集）
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── run.py                   启动入口
│   ├── frontend/                静态页面（无框架、无构建）
│   │   ├── index.html           P3 寄存点列表
│   │   ├── point.html           P4 寄存点详情 + 可用柜格查询
│   │   ├── reserve.html         P5 预约确认（提交流程）
│   │   ├── my-orders.html       P6 我的订单（列表 + 取消）
│   │   ├── order.html           P7 订单详情 + 状态流转时间线
│   │   ├── login.html / register.html
│   │   ├── css/common.css
│   │   └── js/api.js, js/common.js
│   ├── tests/                    pytest API + Selenium UI 自动化
│   ├── tools/
│   │   ├── phase3_e2e_reservation.py   第三阶段端到端 + 真并发验收脚本
│   │   ├── phase4_e2e_lifecycle.py     生命周期验收脚本
│   │   ├── phase4_e2e_jobs.py          超时任务 + 调度器验收脚本
│   │   ├── phase4_e2e_admin.py         管理端验收脚本
│   │   ├── run_b1_auth_query.py        B1 认证/查询 26 条 API + MySQL 断言
│   │   └── phase5_consistency_check.py 四方一致性检查
│   └── app/
│       ├── main.py              FastAPI 应用装配
│       ├── core/                配置、常量、错误码、异常、日志、安全、依赖
│       ├── db/                  引擎、基类、建表工具、种子数据、验收脚本
│       ├── models/              SQLAlchemy 模型（10 张表）
│       ├── schemas/             Pydantic 请求/响应模型
│       ├── services/            业务规则与事务（时间窗口、柜格、寄存点、预约）
│       └── api/v1/              接口路由（auth / points / cabinet-types / cabinets / reservations）
└── README.md
```

> `docs/13`、`docs/14` 与 `docs/execution/` 是内部目标模板/执行计划，不代表已执行结果；当前真实完成度见 `docs/10` 和 `docs/11`。

---

## 六、数据库表一览

| 表 | 说明 |
|---|---|
| `users` | 用户（USER / ADMIN） |
| `storage_points` | 寄存点 |
| `cabinet_groups` | 柜体（柜机） |
| `cabinet_types` | 柜格规格（尺寸等级、单价） |
| `cabinets` | 柜格（最小预约资源单位） |
| `reservations` | 预约订单 |
| `reservation_slots` | 时段占用（唯一索引防超卖） |
| `reservation_status_logs` | 订单状态变更审计 |
| `job_execution_logs` | 定时任务执行日志 |
| `system_config` | 业务规则可配置项 |

**核心设计：柜格占用状态不落库。**
`cabinets.physical_status` 只表示运维维度（可用 / 维护中 / 停用）；
"已预约 / 使用中"由预约订单派生计算，因此不存在"订单已取消但柜格仍显示已预约"的双写不一致。

---

## 七、常用命令速查

```powershell
# 重新生成建表 SQL（不连数据库，离线编译 ORM 模型）
python -m app.db.init_db --dump-ddl

# 危险：删表重建（仅开发/测试环境）
python -m app.db.init_db --create-db --drop

# 重复执行种子数据（幂等，不会产生重复记录）
python -m app.db.seed

# 数据库验收：核对表 / 索引 / 种子数据，并验证幂等性
python -m app.db.verify --check-idempotent

# 第三阶段验收：端到端 + 真并发（需先启动服务，默认打 http://127.0.0.1:8131）
python tools\phase3_e2e_reservation.py
```

---

## 八、开发阶段

| 阶段 | 内容 | 状态 |
|---|---|---|
| S1 | 项目骨架、数据库连接、数据模型、初始化数据 | 已完成 |
| S2 | 用户认证、权限控制、基础查询（Q1~Q7） | 已完成 |
| S3 | 预约创建 / 取消 / 冲突校验 / 订单管理（R1~R4）+ 前端 P5~P7 | 已完成 |
| S4 | 签到取件（R5/R6）、超时释放任务、管理员功能、前端后台页 | 已完成 |
| S5 | 集成检查、启动验证、缺陷修复、测试交付与复盘 | 已完成 |

### 第三阶段的并发正确性（已实测）

"两个请求同时抢同一个柜格的同一时段，只能有一个成功"由**两道独立防线**保证：

1. **应用层悲观锁**：事务内对 `cabinets` 行执行 `SELECT ... FOR UPDATE`，
   冲突检测必须在拿到锁之后做；
2. **数据库唯一索引**：`reservation_slots.uk_slots_cabinet_slot(cabinet_id, slot_start)`。

实测结论（`tools/phase3_e2e_reservation.py` 的 K 段）：
16 个并发请求抢同一时段，**恰好 1 个返回 201、15 个返回 409**，
数据库中只多出 1 条订单。值得注意的实测现象是——
这 15 个失败请求**大部分是被唯一索引拦下的，而不是应用层的冲突检测**。
原因是 MySQL 默认 REPEATABLE READ：冲突检测是一次普通 `SELECT`，
读的是本事务快照，读不到"锁等待期间对方刚提交"的那条订单。
所以唯一索引不是"多余的保险"，而是并发场景下真正兜底的那一道。

---

## 九、常见问题（排查手册）

### Q1：启动报「端口 8000 已被占用」

启动脚本会直接告诉你占用进程的 PID，并给出处理命令：

```
启动失败：端口 8000 已被占用
占用该端口的进程：
    PID = 29012
请任选一种方式处理：
    1) 结束占用进程（需要【管理员】终端）: taskkill /PID 29012 /F
    2) 换一个端口启动            : python run.py --port 8001
```

**为什么会出现这种情况？**
uvicorn 开启热重载时会在 Windows 上派生子进程。如果你直接关掉黑窗口，
子进程可能被留了下来并继续占用端口；如果当初是用管理员权限启动的，
普通权限的 `taskkill` 还结束不掉它，必须用管理员终端。

查看谁占用了端口：

```powershell
netstat -ano | findstr :8000
```

> 注意：本机 `Get-NetTCPConnection` 出现 `无效的类 / HRESULT 0x80041010` 报错，
> 该 Cmdlet 已损坏，请改用 `netstat -ano`。

### Q2：服务启动了，但浏览器一直转圈、接口不返回任何响应

**最常见的原因：Windows 控制台的「快速编辑模式」把进程挂起了。**

你在控制台窗口里点了一下鼠标（或拖选了文本），窗口标题栏出现「选择」字样，
此时进程的所有标准输出都会被阻塞，而 FastAPI 的日志正是往控制台写的，
于是整个请求处理被卡住 —— 表现为端口在监听、TCP 连接已建立，但永远没有响应。

**处理办法**：点一下控制台窗口，按 `Esc` 或回车解除选择模式，请求立刻恢复。

**如何避免**：

1. 服务启动后不要在它的控制台窗口里点击/拖选；
2. 或者关闭快速编辑模式：右键控制台标题栏 → 属性 → 选项 → 取消勾选「快速编辑模式」；
3. 排查问题时用 `python run.py --no-reload`，减少进程数量，问题更容易定位。

如果确认不是控制台挂起，按下面顺序排查：

```powershell
# 1) 服务器进程是否还在
netstat -ano | findstr :8000

# 2) 本机访问是否正常
curl.exe --noproxy "*" --max-time 5 http://127.0.0.1:8000/api/v1/health
#   exit 7  = 连接被拒绝（服务没起来）
#   exit 28 = 超时（服务起来了但被挂起，见上文）
#   200     = 正常

# 3) 检查是否有系统代理影响
Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" |
  Select-Object ProxyEnable, ProxyServer, ProxyOverride
```

> 浏览器访问时请用 `http://127.0.0.1:8000/`，不要用 `https://`。
> 如果本机装有代理软件，请确认 `127.0.0.1`、`localhost` 在代理的白名单/绕过列表里。

### Q3：启动报 `Access denied for user 'root'@'localhost'`

`.env` 里的 `DB_PASSWORD` 与本机 MySQL 密码不一致。

### Q4：启动报 `Can't connect to MySQL server on '127.0.0.1'`

MySQL 服务未启动。需要**管理员权限**的 PowerShell：

```powershell
net start MySQL8
```

普通权限执行会报「系统错误 5，拒绝访问」，这是权限问题，不是服务本身的问题。

### Q5：`RuntimeError: cryptography is required`

执行 `pip install cryptography`（已包含在 requirements.txt 中）。

### Q6：健康检查显示 `database.ok = false`

访问 `http://127.0.0.1:8000/api/v1/health` 查看 `database.error` 字段的具体错误，
再对照 Q3 / Q4 处理。

### Q7：如何确认数据库建得对不对

```powershell
cd backend
python -m app.db.verify --check-idempotent
```

会逐项核对表清单、关键索引（含防重复提交的唯一键、防超卖的
`uk_slots_cabinet_slot`）、种子数据行数，并验证种子脚本的幂等性。
全部一致时退出码为 0。

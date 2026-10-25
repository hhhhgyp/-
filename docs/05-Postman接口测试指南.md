# Postman 接口测试指南

> 对应项目：智能行李寄存柜预约系统
> 对应接口实现：`backend/app/api/v1/`
> 对应测试用例：`docs/04-测试用例.md`
> 本文档中的“实际结果”只有两种来源：Newman 真实执行输出，或明确标注“待执行”。**没有把未执行的用例写成通过。**

---

## 1. 先核对，再建集合

### 1.1 核对方法

1. 从 `backend/app/api/v1/router.py` 找出所有被挂载的路由模块；
2. 逐个读取 `@router.get/post/put/patch` 装饰器，记录 **方法 + 路径 + response_model + 鉴权依赖**；
3. 用 `app.openapi()` 导出 36 个操作，与人工清单交叉比对；
4. 只有同时出现在代码和 OpenAPI 里的接口，才允许进入 Collection；
5. 生成后再跑 `postman/verify_collection.py` 做机器比对（结果见 §14）。

### 1.2 核对结论

| 项目 | 结果 |
|---|---|
| OpenAPI 路径 / 操作 | 35 条路径 / **36 个操作** |
| 公开接口（无需登录） | 11 个（健康检查、注册/登录、Q1~Q8） |
| 登录用户接口 | 8 个（登出、当前用户、R1~R6） |
| 管理端接口 | 17 个（M1~M15，含 M6b） |
| 集合覆盖 | **36 / 36**，无编造接口，无遗漏接口 |

### 1.3 核对中发现并修正的文档偏差

| # | 文档原写法 | 代码实际 | 处理 |
|---|---|---|---|
| 1 | `PUT /admin/configs/{key}` body `{"config_value": "..."}` | `ConfigUpdate.value`，字段名是 **`value`** | 已修正 `docs/04` 的 TC-ADM-15 / TC-JOB-10 |
| 2 | 强制取消 `reason` 上限 255 | `ForceCancelRequest.reason` **max_length=128** | 已修正 `docs/04` 的 TC-ADM-13 |
| 3 | 易误写成 `/checkin` | 实际路径是 `/reservations/{order_no}/check-in`（**带连字符**） | 集合按代码实现 |
| 4 | 易误写成 `/admin/jobs/run` | 实际是 `/admin/jobs/release-expired/run` | 集合按代码实现 |
| 5 | M6 易误写成 `/admin/cabinets/batch` | 实际新增柜格是 `POST /admin/groups/{group_id}/cabinets`，与 M6b 的 GET **同路径** | 集合按代码实现 |
| 6 | 易给 Q6 加 `luggage_size` | `GET /cabinets/{id}/availability` **只有** `start_time` / `end_time` | 集合未传该参数 |

> 第 1、2 条是文档与代码的真实不一致，已改文档；第 3~6 条是建集合时最容易凭印象写错的地方，已在 `verify_collection.py` 里加入关键路径检查，防止回归。

### 1.4 错误响应统一结构

所有业务错误（400/401/403/404/409）都由 `app/core/errors.py` 统一输出：

```json
{
  "code": "CABINET_TIME_CONFLICT",
  "message": "该时段已被预约",
  "detail": { "...": "..." },
  "request_id": "..."
}
```

因此断言分三层：**HTTP 状态码 → `code` 业务码 → 关键字段/字段间关系**。只断言状态码不足以证明返回到的是预期错误。

---

## 2. 交付文件

| 文件 | 用途 |
|---|---|
| `postman/luggage-locker.postman_collection.json` | 可直接导入的 Collection（9 个文件夹 / 128 个请求） |
| `postman/luggage-locker-local.postman_environment.json` | 本地环境变量（地址、账号、种子 ID） |
| `postman/build_collection.py` | 生成脚本；接口变更后改 `postman/builder/` 再重新生成 |
| `postman/builder/*.py` | 按文件夹拆分的请求定义，便于 review 与维护 |
| `postman/verify_collection.py` | 与 `app.openapi()` 做双向比对 + 变量闭环检查 |
| `docs/05-Postman接口测试指南.md` | 本文档 |

> 为什么不直接手写一份 JSON：128 个请求的 URL、鉴权、事件结构高度重复，手写必然出现字段名或括号错误；用脚本生成后可以用机器校验“集合里的每个接口都真实存在”，这比人工 review 可靠。

---

## 3. 启动服务与导入

### 3.1 启动后端（Windows PowerShell）

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python run.py --port 8138 --no-reload --no-scheduler
```

- `--no-scheduler`：执行接口用例时关闭调度器，避免定时任务在两次断言之间修改订单状态；
- 需要验证调度器时再单独启动（见 `docs/02-项目交付汇总.md` 的运行手册）；
- 健康检查：`http://127.0.0.1:8138/api/v1/health` 返回 `status=ok` 且 `database.ok=true` 才继续。

### 3.2 导入 Postman

1. 打开 Postman → 左上角 **Import**；
2. 把 `postman/luggage-locker.postman_collection.json` 和 `postman/luggage-locker-local.postman_environment.json` 一起拖入；
3. 右上角环境下拉框选择 **行李寄存-本地**；
4. 打开 Collection，确认根级 **Authorization** 为 `Bearer {{token_user}}`（集合已配置，无需手工加 Header）。

### 3.3 首次运行

1. 右键 Collection → **Run collection**；
2. 保持文件夹顺序 **00 → 08**，不要单独跳着跑；
3. `Delay` 设为 30~50 ms（给配置修改留出提交时间，本项目单机足够）；
4. 关闭 “Stop run if an error occurs”，否则一个失败会掩盖后续问题；
5. 点 **Run**。

命令行等价方式：

```powershell
cd backend
npx --yes newman run ..\postman\luggage-locker.postman_collection.json `
  -e ..\postman\luggage-locker-local.postman_environment.json `
  --delay-request 30 --reporters cli,json --reporter-json-export newman-report.json
```

---

## 4. 环境变量与集合变量

### 4.1 环境变量（`luggage-locker-local`）

| 变量 | 示例值 | 说明 |
|---|---|---|
| `base_url` | `http://127.0.0.1:8138/api/v1` | 已含 `/api/v1`，请求里不要再重复 |
| `username` | `user01` | 普通用户 |
| `password` | `Demo@123456` | 类型 secret |
| `admin_username` | `admin` | 管理员 |
| `admin_password` | `Demo@123456` | 类型 secret |
| `user2_username` | `user02` | 用于越权测试 |
| `user2_password` | `Demo@123456` | 类型 secret |
| `point_id` | `1` | SP001 西湖景区北门寄存点 |
| `group_id` | `1` | A 号柜机 |
| `cabinet_id` | `1` | A-01（SMALL） |
| `cabinet_maintenance_id` | `12` | A-12（MAINTENANCE） |
| `cabinet_large_id` | `11` | A-11（LARGE） |

> 这些账号是项目内的演示账号，不是生产凭据。换成其他环境时只改环境文件，不改 Collection。

### 4.2 集合变量（运行期写入）

| 变量 | 写入位置 | 用途 |
|---|---|---|
| `token_user` / `token_admin` / `token_user2` | 00-02 / 00-03 / 00-04（01-10 刷新） | 三种身份的 Bearer token |
| `user_id` / `user2_id` / `admin_id` | 登录响应 | 断言 `user_id` 隔离 |
| `run_ts` | 00-01 预请求脚本 | 每次运行的时间戳，保证幂等键与 TST 编码唯一 |
| `reg_username` | 01-03 预请求脚本 | 注册用随机用户名 |
| `order_no_reserved` | 03-01 | 04-01 取消、04-03 重复取消 |
| `order_no_adjacent` | 03-02 | 05-14 未签到取件、06-05 详情、06-06 越权、06-10 清理 |
| `order_no_idem` | 03-20 | 03-21 重放、03-22 同 key 不同 body、03-24 清理 |
| `order_no_144` | 03-08 | 04-04 批量释放 144 条 |
| `order_no_large` | 03-13 | 03-14 清理 |
| `order_no_late` | 04-06 | 05-01 签到太早、05-03 签到成功 |
| `order_no_rebook` | 04-02 | 04-09 原因超长、04-10 清理 |
| `order_no_inuse` | 05-03 | 05-04 取消 IN_USE、05-05 取件 |
| `order_no_completed` | 05-05 | 05-06 重复取件、06-04 详情、08-03 精确查询 |
| `order_no_force` | 05-08 | 05-12 强制取消、05-13 终态保护 |
| `tst_point_id` / `tst_group_id` / `tst_type_id` / `tst_cabinet_id` | 07-01 / 07-05 / 07-07 / 07-09 | 隔离测试主数据 |

> Token 放在**集合变量**而不是环境变量：导出 Environment 时不会把运行期 token 写进文件，减少误提交凭据的风险。

---

## 5. 集合级预请求脚本：时间变量

### 5.1 为什么需要

预约接口的时间规则（BR-01~05）都以数据库 `NOW()` 为基准。如果用例里写死 `2026-10-20T10:00:00`，第二天执行就会变成“过去时间”。集合级预请求脚本在**每个请求发出前**重算一次：

```js
const at = (dayOffset, h, m) => {
    const d = new Date();
    d.setDate(d.getDate() + dayOffset);
    d.setHours(h, m, 0, 0);
    return d.getFullYear() + '-' + ... ;
};
```

只使用本机本地时区（部署要求 +08:00），**不用** `toISOString()`，否则 10:00 会被转成 02:00。

### 5.2 变量清单

| 变量 | 含义 | 主要使用处 |
|---|---|---|
| `t_yesterday_10` / `t_yesterday_11` | 昨天 10:00 / 11:00 | TIME_IN_PAST |
| `t_tomorrow_0730` / `t_tomorrow_0830` | 明天 07:30 / 08:30 | 营业前 |
| `t_tomorrow_10` | 明天 10:00 | 主流程、Q5、144 段起点 |
| `t_tomorrow_1015` / `t_tomorrow_1030` / `t_tomorrow_1115` / `t_tomorrow_1130` | 未对齐 / 重叠边界 | 对齐、部分重叠 |
| `t_tomorrow_11` / `t_tomorrow_12` | 明天 11:00 / 12:00 | 相邻时段、Q5 窗口 |
| `t_tomorrow_13` / `t_tomorrow_14` / `t_tomorrow_15` | 明天 13:00 / 14:00 / 15:00 | 尺寸、幂等、强制取消 |
| `t_tomorrow_16` / `t_tomorrow_17` | 明天 16:00 / 17:00 | 预留（价格快照类用例） |
| `t_tomorrow_2130` / `t_tomorrow_2230` | 明天 21:30 / 22:30 | 营业后 |
| `t_day4_10` / `t_day4_1030` | 第 4 天 10:00 / 10:30 | 144 / 145 段边界 |
| `t_plus8d` / `t_plus8d_end` | now+8 天（向下对齐 30 分钟）及 +1 小时 | 超过 7 天窗口 |
| `run_ts` | 每次运行的时间戳 | 幂等键、TST- 编码 |

> `t_plus8d` 不用“第 8 天 10:00”：如果当天 23:00 执行，第 8 天 10:00 只比现在晚 6 天 11 小时，反而落在 7 天窗口内。用 `now + 8 天` 并对齐到 30 分钟，才能保证任何时刻执行都超窗。

### 5.3 `run_ts` 的刷新时机

- 集合级脚本只在 `run_ts` 为空时兜底生成；
- **00-01 健康检查**的请求级预请求脚本每次运行都强制刷新 `run_ts`；
- 因此：**必须从 00 文件夹开始跑**。只跑 03 文件夹时，`run_ts` 可能还是上一次运行的值，幂等键会命中旧订单，`03-01` 会得到 200 重放而不是 201 新建。

## 6. 请求清单（128 个）

> 下表由 `postman/build_collection.py` 生成后导出，**与 Collection 一一对应**；“期望”列里的业务码来自请求的 test 脚本，不是另外维护的一份清单。时间为相对时间变量，实际值由 §5 的脚本在运行时计算。

### 00 健康检查与登录（5 个请求）

先执行健康检查与三个账号登录；后续文件夹依赖此处写入的 token_user / token_admin / token_user2。

| 编号 | 名称 | 方法与路径 | 鉴权 | 期望 |
|---|---|---|---|---|
| 00-01 | 健康检查 | `GET /health` | 公开 | 200 |
| 00-02 | 登录 user01（普通用户） | `POST /auth/login` | 公开 | 200 |
| 00-03 | 登录 admin（管理员） | `POST /auth/login` | 公开 | 200 |
| 00-04 | 登录 user02（用于越权测试） | `POST /auth/login` | 公开 | 200 |
| 00-05 | 当前登录用户 | `GET /auth/me` | USER | 200 |

### 01 认证与异常（12 个请求）

认证类正常/异常路径。执行顺序有依赖：01-08 → 01-09 → 01-10 必须连续执行。

| 编号 | 名称 | 方法与路径 | 鉴权 | 期望 |
|---|---|---|---|---|
| 01-01 | 登录：密码错误 | `POST /auth/login` | 公开 | 401 `AUTH_INVALID_CREDENTIALS` |
| 01-02 | 登录：用户不存在（错误码与密码错误一致） | `POST /auth/login` | 公开 | 401 `AUTH_INVALID_CREDENTIALS` |
| 01-03 | 注册：新用户成功 | `POST /auth/register` | 公开 | 201 |
| 01-04 | 注册：用户名已存在 | `POST /auth/register` | 公开 | 409 `USERNAME_EXISTS` |
| 01-05 | 注册：弱口令（纯数字） | `POST /auth/register` | 公开 | 400 `VALIDATION_ERROR` |
| 01-06 | 鉴权：未携带 token | `GET /auth/me` | 公开 | 401 `AUTH_TOKEN_MISSING` |
| 01-07 | 鉴权：伪造 token | `GET /auth/me` | 公开 | 401 `AUTH_TOKEN_INVALID` |
| 01-08 | 登出 user02 | `POST /auth/logout` | user02 | 200 |
| 01-09 | 登出后旧 token 失效 | `GET /auth/me` | user02 | 401 `AUTH_TOKEN_INVALID` |
| 01-10 | 重新登录 user02（恢复后续越权测试所需 token） | `POST /auth/login` | 公开 | 200 |
| 01-11 | 越权：普通用户访问管理接口 | `GET /admin/stats/overview` | USER | 403 `AUTH_FORBIDDEN` |
| 01-12 | 越权：未登录访问管理接口 | `GET /admin/stats/overview` | 公开 | 401 `AUTH_TOKEN_MISSING` |

### 02 柜格查询（公开接口）（16 个请求）

公开查询接口，全部无需 token。时间变量由集合级预请求脚本在每次请求前重算。

| 编号 | 名称 | 方法与路径 | 鉴权 | 期望 |
|---|---|---|---|---|
| 02-01 | Q1 寄存点列表 | `GET /points` | 公开 | 200 |
| 02-02 | Q1 按城市 + 关键字筛选 | `GET /points?city=杭州&keyword=东站` | 公开 | 200 |
| 02-03 | Q1 分页边界：page=0 | `GET /points?page=0` | 公开 | 400 `VALIDATION_ERROR` |
| 02-04 | Q1 分页边界：page_size=101 | `GET /points?page_size=101` | 公开 | 400 `VALIDATION_ERROR` |
| 02-05 | Q2 寄存点详情（含统计） | `GET /points/{{point_id}}` | 公开 | 200 |
| 02-06 | Q2 寄存点不存在 | `GET /points/99999` | 公开 | 404 `RESOURCE_NOT_FOUND` |
| 02-07 | Q3 柜体列表与柜格统计 | `GET /points/{{point_id}}/groups` | 公开 | 200 |
| 02-08 | Q4 柜格规格列表 | `GET /cabinet-types` | 公开 | 200 |
| 02-09 | Q8 城市筛选选项 | `GET /points/cities` | 公开 | 200 |
| 02-10 | Q5 可用性：正常窗口 | `GET /cabinets/availability?point_id={{point_id}}&start_time={{t_tomorrow_10}}&end_time={{t_tomorrow_12}}` | 公开 | 200 |
| 02-11 | Q5 时间未对齐（10:15） | `GET /cabinets/availability?point_id={{point_id}}&start_time={{t_tomorrow_1015}}&end_time={{t_tomorrow_12}}` | 公开 | 400 `TIME_NOT_ALIGNED` |
| 02-12 | Q5 营业时间外（07:30 开始） | `GET /cabinets/availability?point_id={{point_id}}&start_time={{t_tomorrow_0730}}&end_time={{t_tomorrow_0830}}` | 公开 | 400 `OUT_OF_BUSINESS_HOURS` |
| 02-13 | Q5 尺寸匹配：LARGE | `GET /cabinets/availability?point_id={{point_id}}&start_time={{t_tomorrow_10}}&end_time={{t_tomorrow_11}}&luggage_size=LARGE` | 公开 | 200 |
| 02-14 | Q6 单柜可用性：无冲突 | `GET /cabinets/{{cabinet_id}}/availability?start_time={{t_tomorrow_10}}&end_time={{t_tomorrow_11}}` | 公开 | 200 |
| 02-15 | Q6 柜格不存在 | `GET /cabinets/99999/availability?start_time={{t_tomorrow_10}}&end_time={{t_tomorrow_11}}` | 公开 | 404 `RESOURCE_NOT_FOUND` |
| 02-16 | Q7 柜格详情：维护中柜格 | `GET /cabinets/{{cabinet_maintenance_id}}` | 公开 | 200 |

### 03 预约创建（R1）（24 个请求）

依赖 00 文件夹的 token_user。时间变量在每次请求前由集合级脚本重算；幂等键以 run_ts 保证每次运行唯一。

| 编号 | 名称 | 方法与路径 | 鉴权 | 期望 |
|---|---|---|---|---|
| 03-01 | 正常创建：A-01 明日 10:00-11:00 | `POST /reservations` | USER | 201 |
| 03-02 | 相邻时段：A-01 11:00-12:00 必须允许 | `POST /reservations` | USER | 201 |
| 03-03 | 完全重叠：A-01 10:00-11:00 | `POST /reservations` | USER | 409 `CABINET_TIME_CONFLICT` |
| 03-04 | 部分重叠：A-01 10:30-11:30 | `POST /reservations` | USER | 409 `CABINET_TIME_CONFLICT` |
| 03-05 | 时间未对齐：10:15 开始 | `POST /reservations` | USER | 400 `TIME_NOT_ALIGNED` |
| 03-06 | 时长边界：开始 = 结束 | `POST /reservations` | USER | 400 `DURATION_OUT_OF_RANGE` |
| 03-07 | 时长边界：145 个时段（超过 72 小时） | `POST /reservations` | USER | 400 `DURATION_OUT_OF_RANGE` |
| 03-08 | 时长边界：144 个时段（恰好 72 小时） | `POST /reservations` | USER | 201 |
| 03-09 | 开始时间已过去 | `POST /reservations` | USER | 400 `TIME_IN_PAST` |
| 03-10 | 超过 7 天预约窗口 | `POST /reservations` | USER | 400 `BOOKING_WINDOW_EXCEEDED` |
| 03-11 | 营业开始前：07:30 | `POST /reservations` | USER | 400 `OUT_OF_BUSINESS_HOURS` |
| 03-12 | 营业结束后：22:30 结束 | `POST /reservations` | USER | 400 `OUT_OF_BUSINESS_HOURS` |
| 03-13 | 尺寸匹配：大柜放小行李 | `POST /reservations` | USER | 201 |
| 03-14 | 清理：取消 03-13 的订单 | `POST /reservations/{{order_no_large}}/cancel` | USER | 200 |
| 03-15 | 尺寸不匹配：小柜放大行李 | `POST /reservations` | USER | 400 `SIZE_NOT_MATCH` |
| 03-16 | 行李尺寸枚举非法 | `POST /reservations` | USER | 400 `VALIDATION_ERROR` |
| 03-17 | 柜格维护中：A-12 | `POST /reservations` | USER | 409 `CABINET_NOT_AVAILABLE` |
| 03-18 | 柜格不存在 | `POST /reservations` | USER | 404 `RESOURCE_NOT_FOUND` |
| 03-19 | 多件行李 | `POST /reservations` | USER | 400 `MULTI_LUGGAGE_NOT_SUPPORTED` |
| 03-20 | 幂等首次提交 | `POST /reservations` | USER | 201 |
| 03-21 | 幂等重放：同 key 同 body | `POST /reservations` | USER | 200 |
| 03-22 | 幂等边界：同 key 不同请求体 | `POST /reservations` | USER | 200 |
| 03-23 | 幂等键过短：7 个字符 | `POST /reservations` | USER | 400 `VALIDATION_ERROR` |
| 03-24 | 清理：取消幂等测试订单 | `POST /reservations/{{order_no_idem}}/cancel` | USER | 200 |

### 04 取消（R4）（10 个请求）

依赖 03 创建的 order_no_reserved / order_no_144；04-05~04-08 会临时修改系统配置并在同一文件夹内恢复。

| 编号 | 名称 | 方法与路径 | 鉴权 | 期望 |
|---|---|---|---|---|
| 04-01 | 正常取消并释放时段 | `POST /reservations/{{order_no_reserved}}/cancel` | USER | 200 |
| 04-02 | 取消后同一时段可以再约 | `POST /reservations` | USER | 201 |
| 04-03 | 重复取消（终态保护） | `POST /reservations/{{order_no_reserved}}/cancel` | USER | 409 `ORDER_STATUS_NOT_ALLOWED` |
| 04-04 | 取消 144 个时段的订单（批量释放） | `POST /reservations/{{order_no_144}}/cancel` | USER | 200 |
| 04-05 | 管理端：把取消窗口改为 2880 分钟 | `PUT /admin/configs/cancel_ahead_minutes` | ADMIN | 200 |
| 04-06 | 创建一笔明日订单（用于取消窗口测试） | `POST /reservations` | USER | 201 |
| 04-07 | 取消窗口已过期 | `POST /reservations/{{order_no_late}}/cancel` | USER | 409 `CANCEL_WINDOW_EXPIRED` |
| 04-08 | 管理端：恢复取消窗口为 30 分钟 | `PUT /admin/configs/cancel_ahead_minutes` | ADMIN | 200 |
| 04-09 | 取消原因超长（129 字符） | `POST /reservations/{{order_no_rebook}}/cancel` | USER | 400 `VALIDATION_ERROR` |
| 04-10 | 清理：取消 04-02 的订单 | `POST /reservations/{{order_no_rebook}}/cancel` | USER | 200 |

### 05 生命周期（签到/取件/强制取消）（15 个请求）

依赖 04 创建的 order_no_late 与 03 创建的 order_no_adjacent。本文件夹会临时修改 checkin_early_minutes，并在每个分支后恢复为 15。

| 编号 | 名称 | 方法与路径 | 鉴权 | 期望 |
|---|---|---|---|---|
| 05-01 | 签到太早（默认只允许提前 15 分钟） | `POST /reservations/{{order_no_late}}/check-in` | USER | 409 `CHECKIN_WINDOW_INVALID` |
| 05-02 | 管理端：临时允许提前 7 天签到 | `PUT /admin/configs/checkin_early_minutes` | ADMIN | 200 |
| 05-03 | 签到成功：RESERVED -> IN_USE | `POST /reservations/{{order_no_late}}/check-in` | USER | 200 |
| 05-04 | IN_USE 订单不可取消（状态优先于时间窗口） | `POST /reservations/{{order_no_inuse}}/cancel` | USER | 409 `ORDER_STATUS_NOT_ALLOWED` |
| 05-05 | 取件成功：IN_USE -> COMPLETED | `POST /reservations/{{order_no_inuse}}/complete` | USER | 200 |
| 05-06 | 重复取件 | `POST /reservations/{{order_no_completed}}/complete` | USER | 409 `ORDER_STATUS_NOT_ALLOWED` |
| 05-07 | 管理端：恢复签到提前量（15 分钟） | `PUT /admin/configs/checkin_early_minutes` | ADMIN | 200 |
| 05-08 | 创建一笔用于强制取消的订单（A-05 明日 14:00） | `POST /reservations` | USER | 201 |
| 05-09 | 管理端：允许提前签到（强制取消用例） | `PUT /admin/configs/checkin_early_minutes` | ADMIN | 200 |
| 05-10 | 签到该订单（进入 IN_USE） | `POST /reservations/{{order_no_force}}/check-in` | USER | 200 |
| 05-11 | 管理端：恢复签到提前量（15 分钟） | `PUT /admin/configs/checkin_early_minutes` | ADMIN | 200 |
| 05-12 | 管理端强制取消 IN_USE 订单 | `POST /admin/reservations/{{order_no_force}}/force-cancel` | ADMIN | 200 |
| 05-13 | 终态订单再次强制取消 | `POST /admin/reservations/{{order_no_force}}/force-cancel` | ADMIN | 409 `ORDER_STATUS_NOT_ALLOWED` |
| 05-14 | RESERVED 订单不可直接取件 | `POST /reservations/{{order_no_adjacent}}/complete` | USER | 409 `ORDER_STATUS_NOT_ALLOWED` |
| 05-15 | 强制取消缺少原因 | `POST /admin/reservations/{{order_no_adjacent}}/force-cancel` | ADMIN | 400 `VALIDATION_ERROR` |

### 06 订单查询（R2 / R3）（10 个请求）

依赖 03/05 创建的订单号。06-06 使用 token_user2，验证「存在但非本人 -> 403」。

| 编号 | 名称 | 方法与路径 | 鉴权 | 期望 |
|---|---|---|---|---|
| 06-01 | 我的订单列表：只含本人 + 创建时间倒序 | `GET /reservations/my` | USER | 200 |
| 06-02 | 状态过滤：CANCELLED | `GET /reservations/my?status=CANCELLED&page_size=50` | USER | 200 |
| 06-03 | 非法状态值 | `GET /reservations/my?status=FOO` | USER | 400 `VALIDATION_ERROR` |
| 06-04 | 详情：COMPLETED 订单的 can_* 与状态日志 | `GET /reservations/{{order_no_completed}}` | USER | 200 |
| 06-05 | 详情：RESERVED 订单的 can_* | `GET /reservations/{{order_no_adjacent}}` | USER | 200 |
| 06-06 | 越权：user02 读取 user01 的订单 | `GET /reservations/{{order_no_adjacent}}` | user02 | 403 `AUTH_FORBIDDEN` |
| 06-07 | 订单不存在 | `GET /reservations/NO_SUCH_ORDER_123` | USER | 404 `RESOURCE_NOT_FOUND` |
| 06-08 | 未登录查询订单 | `GET /reservations/my` | 公开 | 401 `AUTH_TOKEN_MISSING` |
| 06-09 | 分页参数越界：page_size=101 | `GET /reservations/my?page_size=101` | USER | 400 `VALIDATION_ERROR` |
| 06-10 | 清理：取消 03-02 创建的订单 | `POST /reservations/{{order_no_adjacent}}/cancel` | USER | 200 |

### 07 管理端主数据（M1~M9 + M6b）（23 个请求）

全部基于新建的 TST- 寄存点/柜体/规格/柜格，不修改种子数据。中途失败只影响隔离数据。

| 编号 | 名称 | 方法与路径 | 鉴权 | 期望 |
|---|---|---|---|---|
| 07-01 | M1 新建寄存点 | `POST /admin/points` | ADMIN | 201 |
| 07-02 | M1 编码重复 | `POST /admin/points` | ADMIN | 409 `DUPLICATE_CODE` |
| 07-03 | M1 营业时间非法（开始 >= 结束） | `POST /admin/points` | ADMIN | 400 `VALIDATION_ERROR` |
| 07-04 | M2 部分更新：只改名称 | `PUT /admin/points/{{tst_point_id}}` | ADMIN | 200 |
| 07-05 | M4 在测试寄存点下新建柜体 | `POST /admin/points/{{tst_point_id}}/groups` | ADMIN | 201 |
| 07-06 | M4 同一寄存点下柜体编码重复 | `POST /admin/points/{{tst_point_id}}/groups` | ADMIN | 409 `DUPLICATE_CODE` |
| 07-07 | M8 新建柜格规格 | `POST /admin/cabinet-types` | ADMIN | 201 |
| 07-08 | M9 修改规格价格 | `PUT /admin/cabinet-types/{{tst_type_id}}` | ADMIN | 200 |
| 07-09 | M6 批量新增 3 个柜格 | `POST /admin/groups/{{tst_group_id}}/cabinets` | ADMIN | 201 |
| 07-10 | M6 批量新增冲突：全有或全无 | `POST /admin/groups/{{tst_group_id}}/cabinets` | ADMIN | 409 `DUPLICATE_CODE` |
| 07-11 | M6b 查询柜体下全部柜格 | `GET /admin/groups/{{tst_group_id}}/cabinets` | ADMIN | 200 |
| 07-12 | M7 柜格切维护中 | `PATCH /admin/cabinets/{{tst_cabinet_id}}/status` | ADMIN | 200 |
| 07-13 | M7 柜格恢复可用 | `PATCH /admin/cabinets/{{tst_cabinet_id}}/status` | ADMIN | 200 |
| 07-14 | M5 整机维护 | `PUT /admin/groups/{{tst_group_id}}` | ADMIN | 200 |
| 07-15 | R1 柜体维护中不可预约 | `POST /reservations` | USER | 409 `CABINET_NOT_AVAILABLE` |
| 07-16 | M5 恢复柜体正常 | `PUT /admin/groups/{{tst_group_id}}` | ADMIN | 200 |
| 07-17 | M3 关闭测试寄存点 | `PATCH /admin/points/{{tst_point_id}}/status` | ADMIN | 200 |
| 07-18 | R1 寄存点关闭不可预约 | `POST /reservations` | USER | 409 `POINT_CLOSED` |
| 07-19 | M3 重新开放测试寄存点 | `PATCH /admin/points/{{tst_point_id}}/status` | ADMIN | 200 |
| 07-20 | M9 停用测试规格 | `PUT /admin/cabinet-types/{{tst_type_id}}` | ADMIN | 200 |
| 07-21 | R1 规格停用不可预约 | `POST /reservations` | USER | 409 `CABINET_TYPE_DISABLED` |
| 07-22 | M6b 停用规格的柜格仍在管理端可见 | `GET /admin/groups/{{tst_group_id}}/cabinets` | ADMIN | 200 |
| 07-23 | M9 恢复测试规格启用 | `PUT /admin/cabinet-types/{{tst_type_id}}` | ADMIN | 200 |

### 08 管理端运营与配置（M10 / M12~M15）（13 个请求）

管理端运营接口。08-05/08-06 会写 job_execution_logs；08-12/08-13 修改并恢复单次扫描上限。

| 编号 | 名称 | 方法与路径 | 鉴权 | 期望 |
|---|---|---|---|---|
| 08-01 | M10 按用户名模糊查询 | `GET /admin/reservations?username=user01&page_size=100` | ADMIN | 200 |
| 08-02 | M10 非法状态值 | `GET /admin/reservations?status=FOO` | ADMIN | 400 `VALIDATION_ERROR` |
| 08-03 | M10 按订单号精确查询 | `GET /admin/reservations?order_no={{order_no_completed}}` | ADMIN | 200 |
| 08-04 | M12 总览统计：占用率可复算 | `GET /admin/stats/overview` | ADMIN | 200 |
| 08-05 | M13 手动触发超时释放任务 | `POST /admin/jobs/release-expired/run` | ADMIN | 200 |
| 08-06 | M13 重复触发：幂等（第二次 affected=0） | `POST /admin/jobs/release-expired/run` | ADMIN | 200 |
| 08-07 | M14 任务日志（按任务名过滤） | `GET /admin/jobs/logs?job_name=release_expired_reservations&page_size=20` | ADMIN | 200 |
| 08-08 | M14 非法任务名 | `GET /admin/jobs/logs?job_name=not_a_job` | ADMIN | 400 `VALIDATION_ERROR` |
| 08-09 | M15 查询全部配置 | `GET /admin/configs` | ADMIN | 200 |
| 08-10 | M15 未知配置键 | `PUT /admin/configs/not_exists` | ADMIN | 404 `RESOURCE_NOT_FOUND` |
| 08-11 | M15 配置值越界 | `PUT /admin/configs/cancel_ahead_minutes` | ADMIN | 400 `VALIDATION_ERROR` |
| 08-12 | M15 修改配置：release_job_batch_size=1 | `PUT /admin/configs/release_job_batch_size` | ADMIN | 200 |
| 08-13 | M15 恢复配置：release_job_batch_size=500 | `PUT /admin/configs/release_job_batch_size` | ADMIN | 200 |


## 7. 变量传递链与执行顺序

### 7.1 为什么不能乱序

这套集合不是 128 个互相独立的请求，而是一条**有状态的主线**：

```text
00 登录
  └─ token_user / token_admin / token_user2
01 认证异常（登出 user02 → 旧 token 401 → 重新登录）
02 查询（必须在任何预约创建之前，否则可用数不再是基线）
03 创建
  ├─ order_no_reserved  (A-01 明日 10:00-11:00)
  ├─ order_no_adjacent  (A-01 明日 11:00-12:00，相邻边界)
  ├─ order_no_idem      (A-02，幂等三连)
  ├─ order_no_144       (A-03，144 段)
  └─ order_no_large     (A-11，大柜放小；随即取消)
04 取消
  ├─ 取消 order_no_reserved → 同一时段可再约 → order_no_rebook
  ├─ 取消 order_no_144      → 批量释放 144
  ├─ 配置 cancel_ahead=2880 → 创建 order_no_late → 取消失败 → 恢复 30
  └─ 取消 order_no_rebook（清理）
05 生命周期
  ├─ order_no_late: 签到太早 → 改配置 → 签到成功 → 取件完成 (order_no_completed)
  ├─ order_no_force: 新建 → 签到 → 强制取消
  └─ order_no_adjacent: 未签到取件 409；强制取消缺 reason 400
06 订单查询
  ├─ 列表 / 过滤 / 详情 / 越权
  └─ 取消 order_no_adjacent（清理）
07/08 管理端（TST- 隔离数据 + 配置）
```

### 7.2 关键依赖

| 后置请求 | 依赖 | 依赖内容 |
|---|---|---|
| 01-09 | 01-08 | 01-08 让 user02 的旧 token 失效 |
| 01-11 / 06-06 | 01-10 | 重新登录拿到新 token_user2，否则得到 401 而非 403 |
| 03-03 / 03-04 | 03-01 | 已有 10:00-11:00 订单才能制造重叠 |
| 03-21 / 03-22 | 03-20 | 同一 `idempotency_key` 才能命中重放 |
| 04-02 | 04-01 | 取消释放时段后才能再约 |
| 04-07 | 04-05 | 取消窗口改成 2880 分钟才会过期 |
| 04-09 / 04-10 | 04-02 | 需要 `order_no_rebook` |
| 05-03 | 05-02 | 提前签到量改成 7 天才允许立即签到 |
| 05-05 | 05-03 | 必须 IN_USE 才能取件 |
| 05-12 | 05-08 / 05-10 | 先建单再签到，才能强制取消 IN_USE |
| 06-04 | 05-05 | 需要已完成订单看终态 `can_*` |
| 07-09 | 07-05 / 07-07 | 柜格必须挂在测试柜体、使用测试规格 |
| 07-15 / 07-18 / 07-21 | 07-09 | 测试柜格存在才能验证维护/关点/停用规格 |
| 08-03 | 05-05 | 按 `order_no_completed` 精确查询 |

### 7.3 清理动作为什么放在主流程里

Postman 没有“teardown 一定执行”的保证。因此每个会产生残留数据的请求后面，紧跟一个**同文件夹内的清理请求**：

- 03-14 取消 03-13 的订单；
- 03-24 取消幂等订单；
- 04-10 取消 04-02 的订单；
- 05-05 取件释放时段；
- 06-10 取消 03-02 的订单。

这样即使运行到 06 就中断，A-01/A-02/A-11 也已经是空闲状态，下一轮 02 文件夹的可用数不会漂移。

> 局限：如果脚本在“创建成功、清理请求之前”中断，仍会残留一笔 RESERVED 订单。恢复方法见 §9.3。

---

## 8. 断言设计

### 8.1 三层断言

| 层 | 例子 | 为什么必须有 |
|---|---|---|
| HTTP 状态码 | `pm.response.to.have.status(409)` | 区分“业务拒绝”和“服务器错误” |
| 业务错误码 | `pm.expect(b.code).to.eql('CABINET_TIME_CONFLICT')` | 409 可能是状态冲突、编码重复、越权……只断言 409 无法定位 |
| 字段 / 字段关系 | `released_slot_count === slot_count`、`occupancy_rate === numerator / denominator` | 防止“状态码对了但数据错了” |

### 8.2 本集合刻意采用的写法

- **金额断言字符串**：`unit_price === '1.00'`。MySQL `DECIMAL` 经 Pydantic 序列化为字符串，写成数字 `1.0` 会失败，这不是缺陷。
- **时间断言用 `include`**：`checkin_deadline` 含 `T10:30:00`，不比较完整日期，避免时区/毫秒格式差异造成假失败。
- **关系断言优先于绝对值**：占用率断言 `rate = numerator / denominator`，而不是写死 `0.42`；分母为 0 时断言 `rate === null`。
- **状态机断言三个布尔值**：`can_cancel / can_checkin / can_complete` 与对应的 `cannot_*_reason` 同时断言，防止“按钮该禁用却可点”。
- **不泄露订单号**：Q6 的 `conflicts` 明确不返回订单号，集合断言响应对象没有 `order_no` 顶层字段。
- **不预填结果**：所有用例的“实际结果”在执行前都是“待执行”，执行后再回填。

### 8.3 断言数量

最终集合共 **311 条 `pm.test` 断言**（128 个请求的平均 2.4 条）。断言总数由 Newman 统计，不是人工估算。

---

## 9. 会修改系统状态的请求

### 9.1 配置修改与恢复

| 请求 | 修改 | 恢复请求 | 恢复值 |
|---|---|---|---|
| 04-05 | `cancel_ahead_minutes = 2880` | 04-08 | `30` |
| 05-02 | `checkin_early_minutes = 10080` | 05-07 | `15` |
| 05-09 | `checkin_early_minutes = 10080` | 05-11 | `15` |
| 08-12 | `release_job_batch_size = 1` | 08-13 | `500` |

设计原则：

1. **只用接口改配置，不直接改数据库时间**。这样“取消窗口已过期”“允许提前 7 天签到”都是系统真实规则产生的结论；
2. 每个“改”后面在**同一文件夹内**跟一个“恢复”，不依赖最后一个文件夹；
3. 08-09 会断言 `cancel_ahead_minutes` 当前值是 `30`，相当于一个**配置哨兵**：如果之前某次运行中断导致没恢复，这里会立刻暴露。

### 9.2 中断后的恢复（按顺序执行）

**方式 A：用 Postman 手工发 3 个请求**

```text
PUT {{base_url}}/admin/configs/cancel_ahead_minutes      Body: {"value":"30"}
PUT {{base_url}}/admin/configs/checkin_early_minutes    Body: {"value":"15"}
PUT {{base_url}}/admin/configs/release_job_batch_size   Body: {"value":"500"}
```

**方式 B：直接 SQL（MySQL）**

```sql
UPDATE system_config SET config_value = '30'  WHERE config_key = 'cancel_ahead_minutes';
UPDATE system_config SET config_value = '15'  WHERE config_key = 'checkin_early_minutes';
UPDATE system_config SET config_value = '500' WHERE config_key = 'release_job_batch_size';
```

**残留预约**（取消窗口/签到窗口用例中途失败时）：

```sql
-- 先看有没有残留占用
SELECT order_no, cabinet_id, status, start_time, end_time
FROM reservations
WHERE status IN ('RESERVED', 'IN_USE', 'OVERDUE')
ORDER BY id DESC;
```

优先用接口取消；确实无法取消时，再按 §9.3 的清理脚本处理（会同时删除审计日志，只建议在测试库使用）。

### 9.3 测试数据清理

**A. 清理 TST- 主数据**（每次运行会新建 1 个寄存点 / 1 个柜体 / 1 个规格 / 3 个柜格）：

```sql
DELETE c FROM cabinets c
JOIN cabinet_groups g ON c.group_id = g.id
JOIN storage_points p ON g.point_id = p.id
WHERE p.code LIKE 'TST-PM-%';

DELETE g FROM cabinet_groups g
JOIN storage_points p ON g.point_id = p.id
WHERE p.code LIKE 'TST-PM-%';

DELETE FROM storage_points WHERE code LIKE 'TST-PM-%';
DELETE FROM cabinet_types  WHERE code LIKE 'TST-%';
```

**B. 清理本次运行产生的订单与注册用户**（仅测试库）：

```sql
DELETE l FROM reservation_status_logs l
JOIN reservations r ON l.reservation_id = r.id
WHERE r.idempotency_key LIKE 'tst-%';

DELETE s FROM reservation_slots s
JOIN reservations r ON s.reservation_id = r.id
WHERE r.idempotency_key LIKE 'tst-%';

DELETE FROM reservations WHERE idempotency_key LIKE 'tst-%';
DELETE FROM users WHERE username REGEXP '^tst_pm_[0-9]+$';
```

> 所有测试订单的幂等键都以 `tst-` 开头、所有测试用户名都以 `tst_pm_` 开头，所以清理只需要两条前缀条件，不会误删种子数据（`admin` / `user01` / `user02` / `123`）。

**C. 任务日志**：`job_execution_logs` 会保留每次手动触发记录，属于审计数据，默认不删。若确实要清：

```sql
DELETE FROM job_execution_logs WHERE trigger_type = 'MANUAL' AND job_name = 'release_expired_reservations';
```

---

## 10. 真实执行结果

### 10.1 执行环境

| 项 | 值 |
|---|---|
| 日期 | 2026-10-19 22:59（本地时区 +08:00） |
| 服务 | `python run.py --port 8138 --no-reload --no-scheduler` |
| 基线 | 2 个寄存点 / 3 种规格 / 20 个种子柜格 / 0 笔活动订单 / 配置全默认 |
| 执行器 | Newman 6.2.3（Node 24.17.0） |
| 命令 | 见 §3.3 |

### 10.2 结果

| 指标 | 结果 |
|---|---|
| 请求 | **128 / 128 成功发出** |
| 请求失败（网络/超时/脚本异常） | **0** |
| 断言 | **311 / 311 通过** |
| 总耗时 | 20.2 s |
| 平均响应 | 27 ms |
| 最大响应 | 304 ms |

> “请求 0 失败”指 Newman 没有出现连接失败、超时或脚本抛错；“断言全过”指 311 条 `pm.test` 全部为绿。两者是不同维度，所以分开列。

### 10.3 首轮发现的 2 个集合缺陷（已修复）

第一次执行时是 **309/311**，失败的 2 条都出在集合脚本本身，不是被测系统：

| # | 请求 | 现象 | 根因 | 修复 |
|---|---|---|---|---|
| 1 | 02-10 Q5 正常窗口 | `Cannot read properties of undefined (reading 'available')` | 把 A-12（L 规格）的断言写在了 S 规格的 `cabinets` 里 | 把 A-12 断言移到 L 规格；同时补 A-12 `total=2 / available=1` |
| 2 | 03-01 正常创建 | `expected '2026-10-20T10:30:00' to include 'T11:00:00'` | 签到截止 = 开始 + 30 分钟宽限，10:00 开始应为 10:30，脚本误写成 11:00 | 断言改为 `T10:30:00` |

修复后重新生成 Collection 并完整复跑，得到 §10.2 的全绿结果。**这两条记录保留下来**，因为“首轮 309/311、定位为测试脚本缺陷、修复后 311/311”比直接声称“一次全过”更可信。

### 10.4 执行后的数据库状态

| 检查项 | 结果 |
|---|---|
| `status IN ('RESERVED','IN_USE','OVERDUE')` | 0 |
| `cancel_ahead_minutes` | `30` |
| `checkin_early_minutes` | `15` |
| `release_job_batch_size` | `500` |
| TST- 寄存点 / 规格 | 已按 §9.3 清理为 0 |
| 种子寄存点 | SP001 / SP002 均为 OPEN |

### 10.5 这次执行能证明什么、不能证明什么

**能证明：**

- 36 个操作在真实服务 + 真实 MySQL 上可被调用，路径、方法、鉴权、请求体字段与代码一致；
- 正常路径返回 200/201，异常路径返回约定的 400/401/403/404/409 与业务码；
- 状态机（RESERVED → IN_USE → COMPLETED / CANCELLED / FORCE_CANCELLED）与 `can_*` 派生字段符合设计；
- 幂等重放、相邻时段、144 段边界、取消窗口、签到窗口、强制取消等规则在接口层成立；
- 集合可以重复执行（第二轮起不再依赖“第一次的干净库”）。

**不能证明：**

- **并发安全**：Postman/Newman 是单线程顺序执行，无法制造“两个请求同时抢同一柜格”。`SELECT ... FOR UPDATE` + 唯一索引的效果必须用 JMeter 或 pytest 多线程验证（见 §11）。
- **数据库不变量**：Postman 只能看响应，不能证明 `reservation_slots` 真的删除了、`reservation_status_logs` 真的写了。需要 `docs/03-测试方案.md` 里的 C-01~C-12 SQL 校验。
- **精确时间边界**：`now + 5 分钟`、`now + 7 天`、签到宽限期的“恰好等于”分支，依赖数据库时钟，Postman 无法稳定构造。
- **性能与容量**：本集合只测功能正确性，不测 QPS、响应时间分布、连接池耗尽。
- **前端交互**：登录回跳、按钮禁用、管理页表格渲染等，需要浏览器用例（`docs/04` 的 TC-UI 系列）。

---

## 11. 未覆盖范围与替代方案

| 未覆盖内容 | 原因 | 替代方案 |
|---|---|---|
| 同一柜格并发下单只成功 1 笔 | Newman 顺序执行 | JMeter 10/20/50 线程同时 POST；或 `tools/phase3_e2e_reservation.py` 的并发段 |
| 签到超时自动释放 | 需要把 `checkin_deadline` 改到过去 | pytest + SQL 构造，再调 `POST /admin/jobs/release-expired/run` |
| 超时未取件标记 OVERDUE | 需要把 `end_time` 改到过去 | 同上 |
| 精确 5 分钟 / 7 天边界 | 依赖 `NOW()` | pytest 用 `db_now()` 计算并断言 |
| 取消窗口“恰好等于截止时间” | 秒级竞态 | pytest 单测服务层 |
| 时段表/日志表不变量 | Postman 无数据库连接 | `docs/03` 的 12 条 SQL 校验 |
| 索引与锁行为 | 需要 `EXPLAIN` / `SHOW ENGINE INNODB STATUS` | DBA 脚本 |
| 性能 | 非功能测试 | JMeter 压测方案 |
| 页面跳转与权限守卫 | 非接口层 | Selenium / Playwright |

> 因此本集合的定位是：**接口契约与业务规则的回归网**，不是“全部测试”。§10.5 已经把边界写清楚，避免把“311 条断言全过”误读为“系统没有并发问题”。

---

## 12. 导出 Collection 与 Environment

### 12.1 从 Postman 导出

**Collection：**

1. 左侧 Collections 面板，鼠标移到集合名称上；
2. 点 **⋯**（更多操作）→ **Export**；
3. 选择 **Collection v2.1**（推荐，兼容 Newman 6）；
4. 文件名建议：`luggage-locker.postman_collection.json`；
5. 导出前如果刚跑过，建议先清空运行期变量（见 12.3）。

**Environment：**

1. 左侧 **Environments** → 选中 **行李寄存-本地**；
2. 点右上角 **⋯** → **Export**；
3. 文件名建议：`luggage-locker-local.postman_environment.json`。

### 12.2 在另一台机器导入

1. Postman → **Import** → 选择两个 JSON；
2. 右上角环境选择 **行李寄存-本地**；
3. 修改 `base_url` 为新机器地址；
4. 确认账号存在（`admin` / `user01` / `user02`，密码 `Demo@123456`）；
5. **从 00 文件夹开始跑**（原因见 §5.3）。

### 12.3 导出前的凭据处理

Postman 导出 Collection 时会带上**集合变量的当前值**，包括 `token_user`、`token_admin`、`order_no_*`。这些是短期 JWT 和测试订单号，不是长期密钥，但仍建议：

- 导出前在 Collection 的 **Variables** 页把 `token_*` 清空；或
- 导出后手动把这三个值改成空字符串；或
- 只提交 `postman/build_collection.py` 生成的版本（变量默认为空）。

Environment 文件里只有演示账号密码（已标记 secret），**不含 token**——这是把 token 放在集合变量而不是环境变量的直接好处。

### 12.4 版本管理建议

```text
postman/
  build_collection.py                 # 源文件，提交
  builder/                            # 源文件，提交
  verify_collection.py                # 源文件，提交
  luggage-locker.postman_collection.json          # 生成物，可提交（变量为空时）
  luggage-locker-local.postman_environment.json   # 生成物，可提交（演示账号）
```

接口变更时的正确做法：改 `backend/app/api/v1/*.py` → 改 `postman/builder/f0x_*.py` → 运行 `python postman/build_collection.py` → 运行 `python postman/verify_collection.py`，而不是直接在 Postman 里改完再导出（否则下次生成会被覆盖）。

---

## 13. 结果回填模板

执行前所有行都是“待执行”；执行后只填真实观察到的东西。

| 请求编号 | 结果 | 实际 HTTP | 实际业务码 | 备注 / 缺陷 ID |
|---|---|---|---|---|
| 00-01 | 待执行 |  |  |  |
| 01-01 | 待执行 |  |  |  |
| 02-10 | 待执行 |  |  |  |
| 03-01 | 待执行 |  |  |  |
| 03-21 | 待执行 |  |  |  |
| 04-07 | 待执行 |  |  |  |
| 05-12 | 待执行 |  |  |  |
| 06-06 | 待执行 |  |  |  |
| 07-10 | 待执行 |  |  |  |
| 08-06 | 待执行 |  |  |  |

填写规则：

- **结果**只允许：通过 / 失败 / 阻塞 / 未执行；
- “通过”必须同时满足：HTTP 状态码、业务码、该请求的全部 `pm.test` 都为绿；
- 失败必须记录实际值与期望值，并按 `docs/03` 的缺陷模板提缺陷；
- 阻塞要写清阻塞原因（环境未启动、前置数据缺失、依赖接口未实现）。

---

## 14. 一致性校验脚本

### 14.1 用法

```powershell
python postman/verify_collection.py
```

脚本会：

1. 读取 Collection，抽取每个请求的 `(method, path)`；
2. `chdir` 到 `backend` 并 `import app.main`，取 `app.openapi()`；
3. 做**双向**比对：
   - 集合里有、代码里没有 → `invented endpoints`（编造接口）；
   - 代码里有、集合没覆盖 → `uncovered endpoints`（覆盖不全）；
4. 检查请求名唯一、每个请求都有 `pm.test`；
5. 检查关键路径拼写（`check-in`、`release-expired/run`、`groups/{id}/cabinets`）；
6. 检查所有 `{{变量}}` 都有定义（环境变量 / 集合变量 / 预请求脚本）。

### 14.2 当前输出

```text
requests           : 128
unique names       : OK
requests w/o tests : OK
openapi operations : 36
covered operations : 36
invented endpoints : OK
uncovered endpoints: OK
key paths          : OK
undefined variables: OK
RESULT             : PASS
```

### 14.3 路径模板匹配规则

Collection 里的 `99999`、`cancel_ahead_minutes`、`NO_SUCH_ORDER_123` 是**字面量**，OpenAPI 里对应的是 `{cabinet_id}`、`{key}`、`{order_no}`。脚本按“同方法 + 同段数 + 逐段相等或对方为参数占位符”匹配；字面量路由优先（`/reservations/my` 不会被 `/reservations/{order_no}` 抢走）。这样既能发现编造接口，又不会把合法的 404/配置键用例误判为编造。

---

## 15. 常见问题

### Q1：01-09 期望 401，却返回 200？

01-08 登出的是 **user02**，01-09 用的必须是 `token_user2`。如果手工跳过了 01-08，旧 token 仍然有效。按顺序执行 01-08 → 01-09 → 01-10。

### Q2：01-11 / 06-06 期望 403，却返回 401？

`token_user2` 还是 01-08 之前的旧 token。01-10 的作用就是重新登录刷新它；跳过 01-10 会得到 401 `AUTH_TOKEN_INVALID`，这反而证明“登出即失效”生效了。

### Q3：03-01 期望 201，却返回 200 且 `idempotent_replay=true`？

`run_ts` 是上一次运行的值，幂等键命中了旧订单。解决：从 **00-01** 开始跑（它会强制刷新 `run_ts`），或手工清空集合变量 `run_ts`。

### Q4：02-07 的 `available_cabinet_count` 不是 11？

说明库里有覆盖“当前时刻”的活动订单（手工测试遗留）。`available_cabinet_count` 是**当前时刻**口径，不是“明天 10:00”口径。先按 §9.2 检查并取消残留订单，或接受该断言失败并记录为“基线不干净”而不是产品缺陷。

### Q5：04-07 期望 409 `CANCEL_WINDOW_EXPIRED`，却返回 200？

04-05 没有成功（通常是 401/403），配置仍是 30 分钟，订单当然可以取消。先看 04-05 的响应；必要时按 §9.2 手工恢复。

### Q6：05-01 期望 409 `CHECKIN_WINDOW_INVALID`，却返回 200？

`checkin_early_minutes` 不是 15，通常是上一次运行在 05-02 之后中断。先恢复配置，再重跑 05。

### Q7：金额断言为什么是字符串？

`DECIMAL(10,2)` 经 Pydantic v2 序列化为字符串（`"2.00"`），避免 JS 浮点误差。断言写成 `"2.00"` 是**故意**的；写成 `2.0` 会失败。

### Q8：07-01 返回 409 `DUPLICATE_CODE`？

正常运行时不会：编码是 `TST-PM-{run_ts}`，每次运行唯一。若手工在同一个 `run_ts` 下重发，才会冲突——这也顺带验证了唯一索引。

### Q9：控制台中文乱码？

Windows 控制台默认代码页不是 UTF-8，Newman 的中文输出会显示成 `?`。执行 `chcp 65001` 后再跑，或只看 `newman-report.json`；乱码不影响断言结果。

### Q10：能只跑某个文件夹吗？

可以，但要知道依赖：

- 只跑 07/08：需要先跑 00 拿 token；
- 只跑 02：需要干净基线（无活动订单）；
- 只跑 03~06：需要 00 + 03 的完整链路，且从 03-01 开始；
- 任意“只跑一个请求”都可能因为变量为空而失败（例如 `{{order_no_adjacent}}` 未赋值）。

---

## 16. 附：集合与用例文档的对应关系

| Collection 文件夹 | `docs/04` 用例 | 说明 |
|---|---|---|
| 00 健康检查与登录 | TC-AUTH-01、TC-UI-*（前置） | 登录只验证接口，不验证页面跳转 |
| 01 认证与异常 | TC-AUTH-02~06、08~10、TC-AUTHZ-01~02 | 禁用账号（TC-AUTH-11）需 SQL 改状态，未纳入 |
| 02 柜格查询 | TC-QRY-01~11、14~15 | Q4 为补充用例；TC-QRY-12/13 需构造订单，已在 03/06 间接覆盖 |
| 03 预约创建 | TC-RES-01~04、06~08、10~13、17~20、22~24、26 | 5 分钟/7 天精确边界、跨天、停用规格在 07 |
| 04 取消 | TC-CAN-01~05、07 | 06（他人订单取消）在 06 文件夹以查询越权替代 |
| 05 生命周期 | TC-CHK-01~09、TC-ADM-12~13 | 签到超时（TC-CHK-03/04）需 SQL，未纳入 |
| 06 订单查询 | TC-ORD-01~07、TC-AUTHZ-03 |  |
| 07 管理端主数据 | TC-ADM-01~10、16、TC-RES-14~16 |  |
| 08 管理端运营 | TC-ADM-11、14~15、TC-JOB-07~10 | 任务超时释放的“有数据”分支需 SQL，未纳入 |

> 未被 Collection 覆盖的用例仍然保留在 `docs/04`，状态为“待执行”，不能用本集合的全绿结果替代它们的执行结论。

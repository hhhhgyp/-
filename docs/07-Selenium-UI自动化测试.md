# 07 - Selenium UI 自动化测试指南

> 代码位置：`backend/tests/ui/`  
> 技术栈：Python 3.11.9、Selenium 4.51.0、pytest 8.3.4、pytest-html 4.1.1  
> 被测对象：本项目真实前端页面（原生 HTML/CSS/JS）+ 真实 FastAPI 服务 + MySQL  
> 最近一次执行：2026-10-20，Chrome headless **8 passed / 50.29 s**；Edge 完整 E2E **1 passed**；接口 + UI 全量 **79 passed**（71 API + 8 UI）。

---

## 1. 覆盖范围

优先覆盖用户核心链路，不追求“把每个按钮都点一遍”：

| 流程 | 页面 | 是否覆盖 |
|---|---|---|
| 登录成功 / 登录失败 | `/login.html` | ✅ |
| 首页按关键字搜索寄存点 | `/index.html` | ✅ |
| 查询指定时段、指定尺寸的可用柜格 | `/point.html` | ✅ |
| 从可用柜格进入确认页并创建预约 | `/reserve.html` | ✅ |
| 查看订单详情、状态流转记录 | `/order.html` | ✅ |
| 我的订单列表查看与取消 | `/my-orders.html` | ✅ |
| 未登录点“预约”被引导登录 | `/point.html` → `/login.html` | ✅ |
| 退出登录后访问我的订单被拦截 | 导航栏 → `/my-orders.html` | ✅ |
| 已占用柜格不再显示“预约”按钮 | `/point.html` | ✅ |
| 普通用户访问管理页被拒绝并显示原因（D-03） | `/admin/index.html`、`/admin/orders.html` → `/login.html?denied=1` | ✅（2 条） |
| 管理员登录后回到原管理页 | `/login.html` → `/admin/index.html` | ✅ |

**先验证一条完整链路，再扩展**：`test_e2e_login_search_book_view_cancel` 是第一条被跑通的用例；确认页面元素、等待方式、数据清理都可靠后，才补登录失败、搜索、占用态、未登录、退出登录 5 条基础用例；D-03 回归时再补 2 条管理页守卫用例。

---

## 2. 环境与依赖

### 2.1 实际验证过的环境

| 项 | 版本 / 说明 |
|---|---|
| 操作系统 | Windows 10.0.22631 |
| Python | 3.11.9（`backend/.venv`） |
| Selenium | 4.51.0 |
| Chrome | 155.0.8059.80 |
| Edge | 155.0.4283.62 |
| 驱动 | **无需手工下载**；Selenium Manager 自动匹配并缓存 chromedriver/msedgedriver |
| 服务 | `http://127.0.0.1:8138`，`--no-scheduler` |

> Chrome 全量 8 条、Edge 完整 E2E 1 条均已真实执行通过。没有把“理论上支持”写成“已验证”。

### 2.2 安装

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

`requirements-dev.txt` 已包含：

```text
selenium==4.51.0
pytest==8.3.4
pytest-html==4.1.1
```

第一次运行需要网络，Selenium Manager 会下载浏览器驱动；下载后缓存，后续离线可复用。

### 2.3 启动被测服务

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python run.py --port 8138 --no-reload --no-scheduler
```

确认：

```powershell
Invoke-WebRequest http://127.0.0.1:8138/api/v1/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8138/login.html -UseBasicParsing
```

UI 测试**不会自动拉起服务**；服务不可用时，driver 能打开页面但接口请求失败，用例会在显式等待超时处失败。

---

## 3. 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `TEST_UI_BASE_URL` | 由 `TEST_BASE_URL` 去掉 `/api/v1` 得到，默认 `http://127.0.0.1:8138` | 前端根地址 |
| `TEST_BROWSER` | `chrome` | `chrome` / `edge` |
| `TEST_HEADLESS` | `1` | `0` 打开真实浏览器窗口，便于观察 |
| `TEST_UI_TIMEOUT` | `15` | 显式等待上限（秒） |
| `TEST_USERNAME` / `TEST_PASSWORD` | `user01` / `Demo@123456` | 登录账号 |
| `TEST_BASE_URL` | `http://127.0.0.1:8138/api/v1` | API 与数据库清理复用 |

示例：

```powershell
$env:TEST_UI_BASE_URL = "http://127.0.0.1:8138"
$env:TEST_BROWSER = "chrome"
$env:TEST_HEADLESS = "0"       # 想看着浏览器跑就设 0
$env:TEST_UI_TIMEOUT = "20"
python -m pytest -m ui -v
```

---

## 4. 运行命令

### 4.1 先只跑一条完整 E2E

```powershell
python -m pytest `
  tests/ui/test_01_core_flow.py::test_e2e_login_search_book_view_cancel `
  -v -s
```

这是推荐的第一步：确认登录、搜索、查柜、下单、详情、取消、数据库状态全链路。

### 4.2 跑全部 UI 用例

```powershell
python -m pytest -m ui -v
# 或
python -m pytest tests/ui -v
```

### 4.3 生成 UI HTML 报告

```powershell
python -m pytest tests/ui -v `
  --html=tests/ui/reports/ui-report.html `
  --self-contained-html
```

打开：

```powershell
start tests\ui\reports\ui-report.html
```

### 4.4 可见模式 / Edge

```powershell
$env:TEST_HEADLESS = "0"
python -m pytest -m ui -v

$env:TEST_BROWSER = "edge"
python -m pytest tests/ui/test_01_core_flow.py::test_e2e_login_search_book_view_cancel -v
```

### 4.5 接口 + UI 全量

```powershell
python -m pytest -v
```

当前基线：**79 passed**（71 API + 8 UI）。

---

## 5. 目录结构

```text
backend/tests/ui/
├─ conftest.py                 # driver、页面 fixtures、失败证据 hook
├─ support.py                  # 产物路径、截图、page-source
├─ pages/
│  ├─ base_page.py             # 显式等待、导航、datetime-local、alert
│  ├─ login_page.py            # 登录成功/失败
│  ├─ points_page.py           # 首页搜索、打开寄存点
│  ├─ point_detail_page.py     # 时段查询、柜格状态、点击预约
│  ├─ reserve_page.py          # 确认页、提交、取订单号
│  ├─ my_orders_page.py        # 列表、状态、原生 prompt 取消
│  └─ order_detail_page.py     # 状态标签、时间线、按钮可用性
├─ test_01_core_flow.py        # 8 条用例
├─ artifacts/
│  ├─ screenshots/             # 失败截图 + E2E 成功截图
│  ├─ page-source/             # 失败时 DOM 快照
│  └─ logs/ui.log              # 操作步骤、失败 URL、浏览器 console
└─ reports/ui-report.html      # 运行后生成
```

---

## 6. Page Object 与显式等待

### 6.1 定位器只存在于页面对象

用例只写业务动作：

```python
login_page.login(config.username, config.password)
points_page.search(sandbox.point_name, expected_cards=1)
points_page.open_point_by_name(sandbox.point_name)
point_page.set_window(slot.start, slot.end, "SMALL")
point_page.reserve(slot.cabinet_code)
order_no = reserve_page.submit()
orders_page.cancel(order_no, "UI 自动化 E2E 取消")
```

不在用例里散落 `By.ID`，页面改版时只改一个 Page Object。

### 6.2 已核对的稳定定位器

| 页面 | 定位器 | 用途 |
|---|---|---|
| 登录 | `#username`、`#password`、`#submit-btn` | 表单 |
| 首页 | `#filter-keyword`、`#btn-search`、`.point-card` | 搜索、卡片 |
| 柜格页 | `#start-time`、`#end-time`、`#luggage-size`、`#btn-query` | 查询条件 |
| 柜格页 | `.cabinet-chip`、`.code`、`button[data-reserve]` | 柜格、编号、预约按钮 |
| 确认页 | `#preview`、`#size-select`、`#btn-submit`、`#result code` | 预览、提交、订单号 |
| 详情页 | `#detail-wrap .tag`、`#timeline-wrap`、`#btn-cancel` | 状态、时间线、动作 |
| 我的订单 | `#list-wrap table`、`button[data-cancel]`、`#filter-status` | 行、取消、筛选 |
| 导航 | `#navbar`、`#nav-logout` | 登录态、退出 |

编号、订单号这类动态值用 XPath 精确匹配：

```python
//tr[.//code[normalize-space()='LZ2026...']]
```

比“取第 3 行 / 第 2 个按钮”稳定。

### 6.3 全部使用显式等待

代码中**没有 `time.sleep`**。统一封装：

```python
WebDriverWait(driver, 15).until(EC.visibility_of_element_located(locator))
```

典型等待点：

- 登录后：`url_contains("/index.html")`；
- 搜索后：`#list-wrap` 不再显示“加载中”，且卡片数符合预期；
- 查柜后：结果标题里出现**本次查询的 start_time**，证明新响应已渲染，而不是旧 DOM；
- 确认页：`#preview table` 出现且 `#btn-submit` 变为 enabled；
- 提交后：`#result .card` 出现并出现订单号；
- 取消后：先等 `alert-success`，再等该行 `.tag-CANCELLED`；
- 未登录/退出：直接等 URL 跳到 `/login.html`。

`datetime-local` 不用 `send_keys` 硬拼格式，而是写 value 并触发 `input/change`：

```python
driver.execute_script("""
  const el = document.getElementById(arguments[0]);
  el.value = arguments[1];
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
""", "start-time", "2026-10-22T10:00")
```

原生 `window.prompt` 用 Selenium 的 alert API 处理，不用键盘模拟：

```python
alert = wait.until(lambda d: d.switch_to.alert)
alert.send_keys("UI 自动化 E2E 取消")
alert.accept()
```

---

## 7. 测试数据可控与清理

UI 写操作不碰种子柜格，复用 `tests/conftest.py` 的隔离设施：

1. **session 级 `sandbox`**：通过管理端真实接口创建 `TST-PY-*` 寄存点、`G-*` 柜体、6 个 `PYxxxx-*` S 柜格。
2. **唯一搜索词**：用 `sandbox.point_name`（含随机后缀）在首页搜索，断言只命中 1 个点。
3. **唯一时段**：`slot_factory` 给每个用例分配 D+2 起的 `(柜格, 时段)`，UI 操作和 API 预备数据不会互相抢。
4. **订单登记**：UI 创建成功后立即 `order_cleanup.register(order_no)`；用例内先通过页面取消，teardown 仍有兜底。
5. **双层清理**：`order_cleanup` 先用户取消，失败再管理员强制取消；最终 `sandbox` 按 FK 顺序删除日志、时段、订单、柜格、柜体、寄存点。
6. **浏览器隔离**：每个用例新建 Chrome/Edge 实例，退出即销毁，localStorage 不跨用例。

执行后已核对：

| 检查项 | 结果 |
|---|---|
| `TST-PY-%` 寄存点 | 0 |
| `PY%-%` 测试柜格 | 0 |
| `web_%` UI 订单 | 0 |
| 活动订单（RESERVED/IN_USE/OVERDUE） | 0 |
| 配置值 | `cancel_ahead_minutes=30`、`checkin_early_minutes=15`、`checkin_grace_minutes=30`、`max_slot_count=144` |

---

## 8. 页面状态断言

不是“点完就算通过”，关键节点同时看页面、接口、数据库：

| 节点 | 页面断言 | 接口 / 数据库 |
|---|---|---|
| 登录成功 | URL 进入 `/index.html` | 后续接口 200 |
| 搜索 | 只出现 1 张卡片，名称包含随机后缀 | — |
| 查柜 | 目标柜格 chip 有 `is-available` 和 `[data-reserve]` | — |
| 创建成功 | 确认页显示订单号 | 订单 `RESERVED`、`slot_count=2`、DB 2 条 slot |
| 详情 | `tag-RESERVED`，取消按钮 enabled，时间线含创建记录 | — |
| 我的订单 | 目标行 `tag-RESERVED`，取消按钮存在 | — |
| 取消后 | 行变为 `tag-CANCELLED`，取消按钮消失；详情同步 | 订单 `CANCELLED`、DB slot 0、状态日志有取消 |
| 已占用柜格 | 无 `is-available`、无预约按钮、标签 `tag-RESERVED` | 前置 API 订单占位 |
| 未登录 | 跳 `/login.html?redirect=...reserve.html...` | 未创建订单 |
| 退出登录 | 跳 `/login.html`；再访问我的订单仍被拦截 | 旧 token 已清 |

E2E 还会保存两张成功截图：

```text
tests/ui/artifacts/screenshots/e2e-order-<order_no>-<timestamp>.png
tests/ui/artifacts/screenshots/e2e-cancelled-<order_no>-<timestamp>.png
```

---

## 9. 失败截图与日志

### 9.1 失败时自动保存

`tests/ui/conftest.py` 的 `pytest_runtest_makereport` 在用例 call 阶段失败时执行：

```text
tests/ui/artifacts/screenshots/<nodeid>-<timestamp>.png
tests/ui/artifacts/page-source/<nodeid>-<timestamp>.html
tests/ui/artifacts/logs/ui.log
```

同时把以下信息写进日志：

- 失败用例 nodeid、当前 URL、页面 title；
- 截图和 page-source 绝对路径；
- 最近 30 条浏览器 console（含 favicon 404 这类噪声，便于排查）。

### 9.2 HTML 报告内嵌截图

失败截图会以 base64 内嵌进 pytest-html 报告，单文件发送不会丢图。已用一条**故意失败**的临时探针验证：

- 截图文件生成；
- page-source 生成；
- `ui.log` 有 `FAILED / SCREENSHOT / PAGE_SOURCE`；
- 报告含 `data:image/png;base64` 内嵌图；
- 探针验证后已删除；当前最终套件 8/8 通过。

### 9.3 成功也留证据

E2E 用例在订单详情和取消完成时各截图一张，便于简历/答辩展示“真实页面最终状态”。

---

## 10. 用例清单（8 条）

| # | 用例 | 关键动作 | 关键断言 |
|---|---|---|---|
| 1 | `test_e2e_login_search_book_view_cancel` | 登录→搜索→查柜→预约→详情→我的订单→prompt 取消→详情 | 页面状态 + 订单 RESERVED→CANCELLED + slot 2→0 + 日志 |
| 2 | `test_login_rejects_wrong_password` | 错误密码登录 | 停留登录页，alert 含“用户名或密码” |
| 3 | `test_point_search_filters_sandbox_point` | 按唯一名称搜索并打开 | 仅 1 张卡片，详情含测试点编号 |
| 4 | `test_booked_slot_is_not_offered_again` | API 先占位，再 UI 查同一时段 | 无 `is-available`、无预约按钮、标签 `tag-RESERVED` |
| 5 | `test_unauthenticated_reserve_redirects_to_login` | 未登录直接点预约 | 跳登录页，redirect 指向 `reserve.html` |
| 6 | `test_non_admin_guard_redirects_to_login_without_loop` | `user01` 访问 `/admin/index.html`，再换 `admin` 登录 | `denied=1` + 提示可见 + 1 s 不跳 + 管理员回到管理页 |
| 7 | `test_non_admin_guard_on_orders_page_stays_denied` | `user01` 访问 `/admin/orders.html` | `redirect=%2Fadmin%2Forders.html` + 3 s URL 不变 |
| 8 | `test_logout_clears_session_and_guards_my_orders` | 登录→退出→访问我的订单 | 退出到登录页；再访问仍被拦截 |

---

## 11. 真实执行结果

### 11.1 Chrome 全量

```text
platform win32 -- Python 3.11.9, pytest-8.3.4, pluggy-1.7.0
plugins: anyio-4.15.1, html-4.1.1, metadata-3.1.1
collected 8 items

tests/ui/test_01_core_flow.py::test_e2e_login_search_book_view_cancel PASSED
tests/ui/test_01_core_flow.py::test_login_rejects_wrong_password PASSED
tests/ui/test_01_core_flow.py::test_point_search_filters_sandbox_point PASSED
tests/ui/test_01_core_flow.py::test_booked_slot_is_not_offered_again PASSED
tests/ui/test_01_core_flow.py::test_unauthenticated_reserve_redirects_to_login PASSED
tests/ui/test_01_core_flow.py::test_non_admin_guard_redirects_to_login_without_loop PASSED
tests/ui/test_01_core_flow.py::test_non_admin_guard_on_orders_page_stays_denied PASSED
tests/ui/test_01_core_flow.py::test_logout_clears_session_and_guards_my_orders PASSED

8 passed, 71 deselected in 50.29s
```

报告：`backend/tests/ui/reports/ui-report.html`（自包含）。

### 11.2 Edge 抽查

```text
TEST_BROWSER=edge
test_e2e_login_search_book_view_cancel PASSED
1 passed in 13.19s
```

### 11.3 接口 + UI 全量

```text
79 passed in 55.98s
```

### 11.4 第一次 E2E 并不是一次就绿

第一条 E2E 首次失败在：

```text
assert sandbox.point_code in point_page.text((By.ID, "point-card"))
E AssertionError: assert 'TST-PY-13edef' in '加载中...'
```

原因：`open_point_by_name` 只等到 URL 变化，详情接口还没返回；测试紧接着读 `#point-card` 就读到了“加载中”。修正方式是让 `PointDetailPage.wait_loaded()` 显式等待 `#point-card` 不再包含“加载中”，并等标题/柜格出现。修正后同一用例通过，随后才扩展其余 5 条基础用例；D-03 回归时又补了 2 条守卫用例。

这类失败是**等待条件不完整**，不是页面缺功能；记录在此，避免把“第一次就全绿”写成事实。后续新增 2 条 D-03 管理页守卫用例后，当前套件为 8 条。

---

## 12. 已知边界

| 项 | 说明 |
|---|---|
| 浏览器矩阵 | Chrome 全量已验证；Edge 只验了完整 E2E；Firefox/Safari 未配置 |
| 原生 prompt | 取消原因使用 `window.prompt`，已按 Chrome/Edge 处理；无头模式下仍可被 Selenium 接管 |
| 精确时钟边界 | 30 分钟对齐、签到截止“恰好当前秒”等仍由接口用例/人工覆盖，UI 不构造真实时钟临界 |
| 调度器 | 服务以 `--no-scheduler` 启动，避免定时任务干扰；M13 手工任务由接口用例覆盖 |
| 像素级视觉 | 没有做截图 diff / 响应式多分辨率；当前断言是 DOM 状态而非视觉回归 |
| 数据基线 | 依赖种子账号 `user01`、S 规格启用；写操作只使用隔离 sandbox |
| 并行 | 建议串行执行；多个浏览器同时跑会共享同一 sandbox 的统计口径，收益不大 |

---

## 13. 常见问题

**Q1：`SessionNotCreatedException` / 找不到驱动？**  
先确认 Chrome/Edge 可正常启动；Selenium Manager 首次需要网络。删掉 `%USERPROFILE%\.cache\selenium` 后重试，或指定已安装的浏览器。

**Q2：页面一直“加载中”，最后超时？**  
先手工打开 `http://127.0.0.1:8138` 确认服务和接口正常；再看 `ui.log` 里失败 URL 和截图。UI 测试不会自动启动后端。

**Q3：想看着浏览器执行？**  
`$env:TEST_HEADLESS="0"`，再用 `-s` 运行单条 E2E。CI 默认 headless。

**Q4：报告里截图裂开？**  
本套件已把失败截图转 base64 内嵌；如果自行改成文件路径，`--self-contained-html` 会提示外部资源警告。

**Q5：失败后残留订单怎么办？**  
正常情况 `order_cleanup` + sandbox 会清理；异常强杀后执行：

```powershell
python tests\cleanup_test_data.py --dry-run
python tests\cleanup_test_data.py
```

**Q6：能不能只跑 UI，不跑接口？**  
可以：`python -m pytest -m ui -v`。接口用例用 `-m "not ui"`。

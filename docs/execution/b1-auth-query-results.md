# B1 认证与查询执行结果

- 执行时间：2026-10-20T17:07:41
- 执行方式：自动化脚本（API + MySQL 断言），不是人工点击
- 目标日期：D0+1 = 2026-10-21
- 结果：**26/26 通过，0 失败**

| 用例 | 标题 | 结果 | 实际结果 / 失败原因 | 耗时 |
|---|---|---|---|---:|
| TC-AUTH-01 | 用户登录成功 | PASS | 200 bearer/7200；/auth/me=user01；token_version=12 未变；last_login_at 已更新（2026-10-20 17:07:35） | 448 ms |
| TC-AUTH-02 | 密码错误 | PASS | 401 AUTH_INVALID_CREDENTIALS；响应无 token；last_login_at 未更新 | 463 ms |
| TC-AUTH-03 | 用户名不存在 | PASS | 两次均 401 AUTH_INVALID_CREDENTIALS；message 一致（'用户名或密码错误'） | 407 ms |
| TC-AUTH-04 | 注册成功 | PASS | 201；role=USER/status=ACTIVE；响应无密码字段；DB bcrypt 哈希且非明文 | 445 ms |
| TC-AUTH-05 | 注册唯一性冲突 | PASS | 用户名冲突=409 USERNAME_EXISTS；手机号冲突=409 PHONE_EXISTS；用户数未增加。注：用例写 13900000002，实际种子为 13800000002，按实际数据执行 | 40 ms |
| TC-AUTH-06 | 注册参数非法（逐项） | PASS | 五条均 400 VALIDATION_ERROR 且 detail 指向字段；无用户落库；username=ab->username；username=ab-cd->username；password=12345678->password；password=abcdefgh->password；phone=12345678901->phone | 62 ms |
| TC-AUTH-07 | 用户名长度边界 | PASS | 32 位=201；33 位=400 VALIDATION_ERROR（username 字段） | 480 ms |
| TC-AUTH-08 | 未携带 token 访问受保护接口 | PASS | GET /auth/me 与 /reservations/my 均 401 AUTH_TOKEN_MISSING | 10 ms |
| TC-AUTH-09 | 非法 token 与过期 token | PASS | 篡改签名=401 AUTH_TOKEN_INVALID；过期 token=401 AUTH_TOKEN_EXPIRED | 512 ms |
| TC-AUTH-10 | 登出后旧 token 立即失效 | PASS | 登出 200；token_version 3->4；旧 token 401；新 token 200 | 993 ms |
| TC-AUTH-11 | 禁用账号 | PASS | 禁用后登录=403 USER_DISABLED；旧 token=403；恢复 ACTIVE 后登录=200 | 1321 ms |
| TC-QRY-01 | 寄存点列表默认分页 | PASS | 200；total=2/page=1/page_size=20；两项字段完整 | 9 ms |
| TC-QRY-02 | 城市与关键字筛选 | PASS | city=杭州→2；keyword=东站→SP002；city=上海→0 | 73 ms |
| TC-QRY-03 | 分页参数越界 | PASS | 三条均 400 VALIDATION_ERROR 且 detail 指向字段；{'page': 0}->page；{'page_size': 0}->page_size；{'page_size': 101}->page_size | 73 ms |
| TC-QRY-04 | 寄存点详情与不存在 | PASS | point 1：group_count=2/cabinet_count=20；99999→404 RESOURCE_NOT_FOUND | 31 ms |
| TC-QRY-05 | 柜体列表的柜格统计 | PASS | 2 项；A=12/11（A-12 维护中）；B=8/8 | 38 ms |
| TC-QRY-06 | 城市列表 | PASS | 200；去重升序 ['杭州'] | 8 ms |
| TC-QRY-07 | 按时间段查询可用柜格（Q5） | PASS | 200；slot_count=4；A-01 可用；A-12 MAINTENANCE；A/S=6/6 | 113 ms |
| TC-QRY-08 | 查询时间未对齐 | PASS | 10:15 与 10:00:30 均 400 TIME_NOT_ALIGNED | 30 ms |
| TC-QRY-09 | 查询时长非法 | PASS | end=start、end<start、145 段均 400 DURATION_OUT_OF_RANGE（145 段用 D0+4 10:30） | 40 ms |
| TC-QRY-10 | 查询超出营业时间 | PASS | 07:30→09:00、20:00→22:30 均 400；08:00→22:00 返回 200 | 76 ms |
| TC-QRY-11 | 行李尺寸过滤 | PASS | LARGE：A/S=0、A/M=0、A/L=1（A-12 维护）、B/L=3 | 17 ms |
| TC-QRY-12 | 已预约时段与相邻时段 | PASS | 10:00–11:00 预约 A-01；10:00–12:00 重叠→RESERVED/false；11:00–12:00 相邻→AVAILABLE/true | 523 ms |
| TC-QRY-13 | 寄存点关闭时的派生状态 | PASS | 关闭 SP002→10 个柜格均 UNAVAILABLE/false；恢复 OPEN 后 D-01=AVAILABLE/true | 52 ms |
| TC-QRY-14 | 单柜格可用性（Q6） | PASS | 重叠 10:30–11:30→false/RESERVED 且无 order_no；11:00–12:00→true/[]；99999→404 | 527 ms |
| TC-QRY-15 | 柜格详情：物理状态与派生状态 | PASS | 12→MAINTENANCE/MAINTENANCE；1→AVAILABLE/AVAILABLE；DB cabinets 无 derived_status 列 | 37 ms |

> 脚本执行结果只代表本次环境、本次数据；不把脚本执行写成“人工执行”。
>
> 首轮实际为 **24/26**：TC-QRY-05、TC-QRY-06 失败，原因是脚本把 Q3/Q8 的数组响应包成了 `{"_data": [...]}`，导致断言读错结构；修正 `response_json` 后复跑 **26/26**。这两条是测试脚本问题，不是产品缺陷。
>
> B1 执行后复跑 pytest API：**71 passed, 8 deselected in 6.89s**；数据库核对为 0 条测试用户、0 订单、0 时段、0 状态日志，寄存点全部 OPEN。

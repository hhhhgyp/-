-- ============================================================
-- 智能行李寄存柜预约系统 - 示例数据（开发/测试环境专用）
-- ============================================================
-- 【重要】
-- 1. 推荐方式：python -m app.db.seed   （幂等，可重复执行）
-- 2. 本文件用于不启动 Python 时手工导入，可重复执行（使用 INSERT IGNORE）
-- 3. 其中三个示例账号的密码哈希对应明文 Demo@123456
--    生产环境禁止使用本文件，请改用环境变量配置真实密码
-- ============================================================

USE `luggage_locker`;

-- ---------- 柜格规格 ----------
INSERT IGNORE INTO cabinet_types (code, name, size_level, width_mm, height_mm, depth_mm, max_weight_kg, price_per_slot, slot_minutes, is_active, description) VALUES ('S', '小型柜', 'SMALL', 300, 250, 400, 5, 1.0, 30, 1, '适合背包、手提袋等小件行李');
INSERT IGNORE INTO cabinet_types (code, name, size_level, width_mm, height_mm, depth_mm, max_weight_kg, price_per_slot, slot_minutes, is_active, description) VALUES ('M', '中型柜', 'MEDIUM', 400, 350, 500, 10, 2.0, 30, 1, '适合 20 寸登机箱');
INSERT IGNORE INTO cabinet_types (code, name, size_level, width_mm, height_mm, depth_mm, max_weight_kg, price_per_slot, slot_minutes, is_active, description) VALUES ('L', '大型柜', 'LARGE', 550, 450, 600, 20, 3.0, 30, 1, '适合 28 寸大行李箱');

-- ---------- 寄存点 ----------
INSERT IGNORE INTO storage_points (code, name, city, address, contact_phone, open_time, close_time, status, description) VALUES ('SP001', '西湖景区北门寄存点', '杭州', '杭州市西湖区北山街 1 号（景区北门游客服务中心旁）', '0571-88880001', '08:00:00', '22:00:00', 'OPEN', '靠近断桥，适合景区一日游行李寄存');
INSERT IGNORE INTO storage_points (code, name, city, address, contact_phone, open_time, close_time, status, description) VALUES ('SP002', '杭州东站东广场寄存点', '杭州', '杭州市江干区全福桥路 2 号（东广场地下一层 B1-08）', '0571-88880002', '06:00:00', '23:30:00', 'OPEN', '火车站进出站旅客短时寄存');

-- ---------- 柜体 ----------
SET @p1 = (SELECT id FROM storage_points WHERE code = 'SP001');
SET @p2 = (SELECT id FROM storage_points WHERE code = 'SP002');
INSERT IGNORE INTO cabinet_groups (point_id, code, name, status) VALUES (@p1, 'A', 'A 号柜机', 'NORMAL');
INSERT IGNORE INTO cabinet_groups (point_id, code, name, status) VALUES (@p1, 'B', 'B 号柜机', 'NORMAL');
INSERT IGNORE INTO cabinet_groups (point_id, code, name, status) VALUES (@p2, 'C', 'C 号柜机', 'NORMAL');
INSERT IGNORE INTO cabinet_groups (point_id, code, name, status) VALUES (@p2, 'D', 'D 号柜机', 'NORMAL');

-- ---------- 柜格 ----------
SET @t_S = (SELECT id FROM cabinet_types WHERE code = 'S');
SET @t_M = (SELECT id FROM cabinet_types WHERE code = 'M');
SET @t_L = (SELECT id FROM cabinet_types WHERE code = 'L');
SET @g_A = (SELECT id FROM cabinet_groups WHERE point_id = @p1 AND code = 'A');
SET @g_B = (SELECT id FROM cabinet_groups WHERE point_id = @p1 AND code = 'B');
SET @g_C = (SELECT id FROM cabinet_groups WHERE point_id = @p2 AND code = 'C');
SET @g_D = (SELECT id FROM cabinet_groups WHERE point_id = @p2 AND code = 'D');
INSERT IGNORE INTO cabinets (group_id, type_id, code, physical_status, remark) VALUES
(@g_A, @t_S, 'A-01', 'AVAILABLE', NULL),
(@g_A, @t_S, 'A-02', 'AVAILABLE', NULL),
(@g_A, @t_S, 'A-03', 'AVAILABLE', NULL),
(@g_A, @t_S, 'A-04', 'AVAILABLE', NULL),
(@g_A, @t_S, 'A-05', 'AVAILABLE', NULL),
(@g_A, @t_S, 'A-06', 'AVAILABLE', NULL),
(@g_A, @t_M, 'A-07', 'AVAILABLE', NULL),
(@g_A, @t_M, 'A-08', 'AVAILABLE', NULL),
(@g_A, @t_M, 'A-09', 'AVAILABLE', NULL),
(@g_A, @t_M, 'A-10', 'AVAILABLE', NULL),
(@g_A, @t_L, 'A-11', 'AVAILABLE', NULL),
(@g_A, @t_L, 'A-12', 'MAINTENANCE', '初始示例数据：演示维护中状态'),
(@g_B, @t_M, 'B-01', 'AVAILABLE', NULL),
(@g_B, @t_M, 'B-02', 'AVAILABLE', NULL),
(@g_B, @t_M, 'B-03', 'AVAILABLE', NULL),
(@g_B, @t_M, 'B-04', 'AVAILABLE', NULL),
(@g_B, @t_M, 'B-05', 'AVAILABLE', NULL),
(@g_B, @t_L, 'B-06', 'AVAILABLE', NULL),
(@g_B, @t_L, 'B-07', 'AVAILABLE', NULL),
(@g_B, @t_L, 'B-08', 'AVAILABLE', NULL),
(@g_C, @t_S, 'C-01', 'AVAILABLE', NULL),
(@g_C, @t_S, 'C-02', 'AVAILABLE', NULL),
(@g_C, @t_S, 'C-03', 'AVAILABLE', NULL),
(@g_C, @t_S, 'C-04', 'AVAILABLE', NULL),
(@g_C, @t_M, 'C-05', 'AVAILABLE', NULL),
(@g_C, @t_M, 'C-06', 'AVAILABLE', NULL),
(@g_D, @t_L, 'D-01', 'AVAILABLE', NULL),
(@g_D, @t_L, 'D-02', 'AVAILABLE', NULL),
(@g_D, @t_L, 'D-03', 'AVAILABLE', NULL),
(@g_D, @t_L, 'D-04', 'AVAILABLE', NULL);

-- ---------- 示例账号 ----------
-- 密码明文均为 Demo@123456（仅开发/测试环境使用！）
INSERT IGNORE INTO users (username, password_hash, phone, role, status, token_version) VALUES
('admin',  '$2b$12$MBlg1nfQ5HoiMT1Cvs05S.32iXmJQwmFiHDAq0Kp72y8uLWZ8b.BW', '13800000000', 'ADMIN', 'ACTIVE', 0),
('user01', '$2b$12$MBlg1nfQ5HoiMT1Cvs05S.32iXmJQwmFiHDAq0Kp72y8uLWZ8b.BW', '13800000001', 'USER',  'ACTIVE', 0),
('user02', '$2b$12$MBlg1nfQ5HoiMT1Cvs05S.32iXmJQwmFiHDAq0Kp72y8uLWZ8b.BW', '13800000002', 'USER',  'ACTIVE', 0);

-- ---------- 业务规则配置 ----------
INSERT IGNORE INTO system_config (config_key, config_value, description) VALUES ('slot_minutes', '30', '预约时间粒度（分钟），BR-01');
INSERT IGNORE INTO system_config (config_key, config_value, description) VALUES ('min_slot_count', '1', '最短预约时长（时段数），BR-02');
INSERT IGNORE INTO system_config (config_key, config_value, description) VALUES ('max_slot_count', '144', '最长预约时长（时段数），72 小时，BR-02');
INSERT IGNORE INTO system_config (config_key, config_value, description) VALUES ('min_advance_minutes', '5', '最早可预约提前量（分钟），BR-03');
INSERT IGNORE INTO system_config (config_key, config_value, description) VALUES ('max_advance_days', '7', '最多提前预约天数，BR-04');
INSERT IGNORE INTO system_config (config_key, config_value, description) VALUES ('checkin_grace_minutes', '30', '存入宽限期（分钟），超时即释放，BR-22');
INSERT IGNORE INTO system_config (config_key, config_value, description) VALUES ('checkin_early_minutes', '15', '允许提前签到分钟数，BR-21');
INSERT IGNORE INTO system_config (config_key, config_value, description) VALUES ('cancel_ahead_minutes', '30', '取消需提前的分钟数，BR-19');
INSERT IGNORE INTO system_config (config_key, config_value, description) VALUES ('release_job_interval_seconds', '60', '超时释放任务执行周期（秒），BR-41');
INSERT IGNORE INTO system_config (config_key, config_value, description) VALUES ('release_job_batch_size', '500', '单次任务扫描的候选订单上限');

-- ---------- 校验 ----------
-- 期望：规格 3、寄存点 2、柜体 4、柜格 30、用户 3、配置 10
SELECT 'cabinet_types' AS tbl, COUNT(*) AS cnt FROM cabinet_types
UNION ALL SELECT 'storage_points', COUNT(*) FROM storage_points
UNION ALL SELECT 'cabinet_groups', COUNT(*) FROM cabinet_groups
UNION ALL SELECT 'cabinets', COUNT(*) FROM cabinets
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'system_config', COUNT(*) FROM system_config;

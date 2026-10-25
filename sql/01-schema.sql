-- ============================================================
-- 智能行李寄存柜预约系统 - 数据库建表脚本（自动生成，请勿手工修改）
-- 生成方式：python -m app.db.init_db --dump-ddl
-- ORM 模型位置：backend/app/models/*.py
-- ============================================================

CREATE DATABASE IF NOT EXISTS `luggage_locker`
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

USE `luggage_locker`;

-- ---------- cabinet_types ----------
CREATE TABLE cabinet_types (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	code VARCHAR(32) NOT NULL COMMENT '如 S / M / L', 
	name VARCHAR(32) NOT NULL COMMENT '如 小型柜', 
	size_level ENUM('SMALL','MEDIUM','LARGE') NOT NULL COMMENT '尺寸等级，BR-08 比较依据', 
	width_mm SMALLINT UNSIGNED NOT NULL COMMENT '宽(mm)', 
	height_mm SMALLINT UNSIGNED NOT NULL COMMENT '高(mm)', 
	depth_mm SMALLINT UNSIGNED NOT NULL COMMENT '深(mm)', 
	max_weight_kg NUMERIC(5, 2) COMMENT '展示用，本期不做重量校验', 
	price_per_slot NUMERIC(10, 2) NOT NULL COMMENT '每个时段(30 分钟)单价', 
	slot_minutes SMALLINT UNSIGNED NOT NULL COMMENT '计费/时间粒度(分钟)' DEFAULT '30', 
	is_active BOOL NOT NULL COMMENT '停用后不可用于新预约（BR-12），历史订单不受影响' DEFAULT '1', 
	description VARCHAR(255), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_general_ci;
CREATE INDEX idx_types_active ON cabinet_types (is_active);
CREATE UNIQUE INDEX uk_types_code ON cabinet_types (code);

-- ---------- job_execution_logs ----------
CREATE TABLE job_execution_logs (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	job_name VARCHAR(64) NOT NULL, 
	trigger_type ENUM('SCHEDULER','MANUAL','SCRIPT') NOT NULL, 
	started_at DATETIME NOT NULL, 
	finished_at DATETIME, 
	scanned_count INTEGER UNSIGNED NOT NULL DEFAULT '0', 
	affected_count INTEGER UNSIGNED NOT NULL DEFAULT '0', 
	result ENUM('SUCCESS','FAILED','PARTIAL') NOT NULL, 
	error_message VARCHAR(500), 
	PRIMARY KEY (id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_general_ci;
CREATE INDEX idx_job_logs_name_started ON job_execution_logs (job_name, started_at);

-- ---------- storage_points ----------
CREATE TABLE storage_points (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	code VARCHAR(32) NOT NULL COMMENT '业务编码，如 SP001', 
	name VARCHAR(64) NOT NULL COMMENT '如 西湖景区北门寄存点', 
	city VARCHAR(32) NOT NULL COMMENT '城市，用于列表筛选', 
	address VARCHAR(255) NOT NULL, 
	contact_phone VARCHAR(20), 
	open_time TIME NOT NULL COMMENT '营业开始时间' DEFAULT '08:00:00', 
	close_time TIME NOT NULL COMMENT '营业结束时间' DEFAULT '22:00:00', 
	status ENUM('OPEN','CLOSED') NOT NULL DEFAULT 'OPEN', 
	description VARCHAR(255), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_general_ci;
CREATE INDEX idx_points_city_status ON storage_points (city, status);
CREATE UNIQUE INDEX uk_points_code ON storage_points (code);

-- ---------- system_config ----------
CREATE TABLE system_config (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	config_key VARCHAR(64) NOT NULL, 
	config_value VARCHAR(128) NOT NULL, 
	description VARCHAR(255), 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_general_ci;
CREATE UNIQUE INDEX uk_config_key ON system_config (config_key);

-- ---------- users ----------
CREATE TABLE users (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	username VARCHAR(32) NOT NULL COMMENT '登录名', 
	password_hash VARCHAR(100) NOT NULL COMMENT 'bcrypt 哈希', 
	phone VARCHAR(20) COMMENT '手机号，可空', 
	`role` ENUM('USER','ADMIN') NOT NULL DEFAULT 'USER', 
	status ENUM('ACTIVE','DISABLED') NOT NULL DEFAULT 'ACTIVE', 
	token_version INTEGER UNSIGNED NOT NULL COMMENT 'JWT 版本号，登出时 +1，使旧 token 立即失效（BR-29）' DEFAULT '0', 
	last_login_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_general_ci;
CREATE INDEX idx_users_role ON users (`role`);
CREATE UNIQUE INDEX uk_users_phone ON users (phone);
CREATE UNIQUE INDEX uk_users_username ON users (username);

-- ---------- cabinet_groups ----------
CREATE TABLE cabinet_groups (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	point_id BIGINT UNSIGNED NOT NULL, 
	code VARCHAR(32) NOT NULL COMMENT '柜体编号，如 A', 
	name VARCHAR(64) NOT NULL COMMENT '如 A 号柜机', 
	status ENUM('NORMAL','MAINTENANCE','DISABLED') NOT NULL COMMENT '整机维护会禁用其下所有柜格（BR-10）' DEFAULT 'NORMAL', 
	remark VARCHAR(255), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(point_id) REFERENCES storage_points (id) ON DELETE RESTRICT ON UPDATE RESTRICT
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_general_ci;
CREATE INDEX idx_groups_point ON cabinet_groups (point_id);
CREATE UNIQUE INDEX uk_groups_point_code ON cabinet_groups (point_id, code);

-- ---------- cabinets ----------
CREATE TABLE cabinets (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	group_id BIGINT UNSIGNED NOT NULL COMMENT '所属柜体', 
	type_id BIGINT UNSIGNED NOT NULL COMMENT '柜格规格', 
	code VARCHAR(16) NOT NULL COMMENT '柜格编号，如 A-01', 
	physical_status ENUM('AVAILABLE','MAINTENANCE','DISABLED') NOT NULL DEFAULT 'AVAILABLE', 
	remark VARCHAR(255) COMMENT '维护原因等', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES cabinet_groups (id) ON DELETE RESTRICT ON UPDATE RESTRICT, 
	FOREIGN KEY(type_id) REFERENCES cabinet_types (id) ON DELETE RESTRICT ON UPDATE RESTRICT
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_general_ci;
CREATE INDEX idx_cabinets_physical_status ON cabinets (physical_status);
CREATE INDEX idx_cabinets_type ON cabinets (type_id);
CREATE UNIQUE INDEX uk_cabinets_group_code ON cabinets (group_id, code);

-- ---------- reservations ----------
CREATE TABLE reservations (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	order_no VARCHAR(32) NOT NULL COMMENT '对外订单号，如 LZ20261019A1B2C3D4', 
	user_id BIGINT UNSIGNED NOT NULL, 
	point_id BIGINT UNSIGNED NOT NULL COMMENT '快照：寄存点', 
	cabinet_id BIGINT UNSIGNED NOT NULL, 
	cabinet_type_id BIGINT UNSIGNED NOT NULL COMMENT '快照：柜格规格', 
	cabinet_code_snapshot VARCHAR(16) NOT NULL COMMENT '快照：下单时柜格编号', 
	point_name_snapshot VARCHAR(64) NOT NULL COMMENT '快照：下单时寄存点名称', 
	start_time DATETIME NOT NULL COMMENT '左闭', 
	end_time DATETIME NOT NULL COMMENT '右开', 
	slot_count INTEGER UNSIGNED NOT NULL COMMENT '时段数 = (end-start)/slot_minutes', 
	luggage_size ENUM('SMALL','MEDIUM','LARGE') NOT NULL, 
	luggage_count TINYINT UNSIGNED NOT NULL COMMENT '本期固定为 1（BR-07）' DEFAULT '1', 
	unit_price NUMERIC(10, 2) NOT NULL COMMENT '快照单价/时段', 
	amount NUMERIC(10, 2) NOT NULL DEFAULT '0.00', 
	pay_status ENUM('UNPAID','PAID','REFUNDED') NOT NULL COMMENT '模拟支付，本期不接入真实支付' DEFAULT 'UNPAID', 
	status ENUM('RESERVED','IN_USE','OVERDUE','COMPLETED','CANCELLED','EXPIRED','FORCE_CANCELLED') NOT NULL DEFAULT 'RESERVED', 
	idempotency_key VARCHAR(64) NOT NULL COMMENT '客户端幂等键，防重复提交', 
	checkin_deadline DATETIME NOT NULL COMMENT '= start_time + 存入宽限期，超时即释放（BR-22）', 
	checked_in_at DATETIME, 
	completed_at DATETIME, 
	cancelled_at DATETIME, 
	cancel_reason VARCHAR(128), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT ON UPDATE RESTRICT, 
	FOREIGN KEY(point_id) REFERENCES storage_points (id) ON DELETE RESTRICT ON UPDATE RESTRICT, 
	FOREIGN KEY(cabinet_id) REFERENCES cabinets (id) ON DELETE RESTRICT ON UPDATE RESTRICT, 
	FOREIGN KEY(cabinet_type_id) REFERENCES cabinet_types (id) ON DELETE RESTRICT ON UPDATE RESTRICT
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_general_ci;
CREATE INDEX idx_reservations_cabinet_time ON reservations (cabinet_id, start_time, end_time);
CREATE INDEX idx_reservations_point_status ON reservations (point_id, status);
CREATE INDEX idx_reservations_status_deadline ON reservations (status, checkin_deadline);
CREATE INDEX idx_reservations_status_end ON reservations (status, end_time);
CREATE INDEX idx_reservations_user_created ON reservations (user_id, created_at);
CREATE UNIQUE INDEX uk_reservations_order_no ON reservations (order_no);
CREATE UNIQUE INDEX uk_reservations_user_idem ON reservations (user_id, idempotency_key);

-- ---------- reservation_slots ----------
CREATE TABLE reservation_slots (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	reservation_id BIGINT UNSIGNED NOT NULL, 
	cabinet_id BIGINT UNSIGNED NOT NULL, 
	slot_start DATETIME NOT NULL COMMENT '该占用的时段起点（按粒度对齐）', 
	PRIMARY KEY (id), 
	FOREIGN KEY(reservation_id) REFERENCES reservations (id) ON DELETE CASCADE ON UPDATE RESTRICT, 
	FOREIGN KEY(cabinet_id) REFERENCES cabinets (id) ON DELETE RESTRICT ON UPDATE RESTRICT
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_general_ci;
CREATE INDEX idx_slots_reservation ON reservation_slots (reservation_id);
CREATE UNIQUE INDEX uk_slots_cabinet_slot ON reservation_slots (cabinet_id, slot_start);

-- ---------- reservation_status_logs ----------
CREATE TABLE reservation_status_logs (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	reservation_id BIGINT UNSIGNED NOT NULL, 
	from_status VARCHAR(20) COMMENT '创建订单时为 NULL', 
	to_status VARCHAR(20) NOT NULL, 
	operator_type ENUM('USER','ADMIN','SYSTEM') NOT NULL, 
	operator_id BIGINT UNSIGNED COMMENT '系统操作为 NULL', 
	remark VARCHAR(255), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reservation_id) REFERENCES reservations (id) ON DELETE RESTRICT ON UPDATE RESTRICT
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_general_ci;
CREATE INDEX idx_logs_reservation ON reservation_status_logs (reservation_id, created_at);

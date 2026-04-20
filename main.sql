/*
 Navicat Premium Data Transfer

 Source Server         : oa
 Source Server Type    : SQLite
 Source Server Version : 3035005
 Source Schema         : main

 Target Server Type    : SQLite
 Target Server Version : 3035005
 File Encoding         : 65001

 Date: 10/12/2025 20:14:36
*/

PRAGMA foreign_keys = false;


-- ----------------------------
-- Table structure for checkin
-- ----------------------------
DROP TABLE IF EXISTS "checkin";
CREATE TABLE "checkin" (
  "id" INTEGER NOT NULL,
  "user_id" INTEGER NOT NULL,
  "check_in_time" DATETIME NOT NULL,
  "status" VARCHAR(20) NOT NULL,
  PRIMARY KEY ("id"),
  FOREIGN KEY ("user_id") REFERENCES "user" ("id") ON DELETE CASCADE ON UPDATE NO ACTION
);

-- ----------------------------
-- Table structure for contract
-- ----------------------------
DROP TABLE IF EXISTS "contract";
CREATE TABLE "contract" (
  "id" INTEGER NOT NULL,
  "contract_name" VARCHAR(100) NOT NULL,
  "contract_no" VARCHAR(50) NOT NULL,
  "party_a" VARCHAR(100) NOT NULL,
  "party_b" VARCHAR(100) NOT NULL,
  "sign_time" DATE NOT NULL,
  "content" TEXT,
  "status" VARCHAR(20) NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE ("contract_no" ASC)
);

-- ----------------------------
-- Table structure for employee_info
-- ----------------------------
DROP TABLE IF EXISTS "employee_info";
CREATE TABLE "employee_info" (
  "id" INTEGER NOT NULL,
  "user_id" INTEGER NOT NULL,
  "age" INTEGER,
  "gender" VARCHAR(10),
  "phone" VARCHAR(20),
  "email" VARCHAR(50),
  "address" VARCHAR(200),
  "salary_base" FLOAT,
  "salary_bonus" FLOAT,
  "salary_deduction" FLOAT,
  "salary_total" FLOAT,
  PRIMARY KEY ("id"),
  FOREIGN KEY ("user_id") REFERENCES "user" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION
);

-- ----------------------------
-- Table structure for equipment
-- ----------------------------
DROP TABLE IF EXISTS "equipment";
CREATE TABLE "equipment" (
  "id" INTEGER NOT NULL,
  "name" VARCHAR(100) NOT NULL,
  "type" VARCHAR(50) NOT NULL,
  "status" VARCHAR(20) NOT NULL,
  "user_id" INTEGER,
  "borrow_time" DATETIME,
  "return_time" DATETIME,
  "is_active" integer NOT NULL DEFAULT 1,
  PRIMARY KEY ("id"),
  FOREIGN KEY ("user_id") REFERENCES "user" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION
);

-- ----------------------------
-- Table structure for leave
-- ----------------------------
DROP TABLE IF EXISTS "leave";
CREATE TABLE "leave" (
  "id" INTEGER NOT NULL,
  "user_id" INTEGER NOT NULL,
  "leave_type" VARCHAR(20) NOT NULL,
  "start_time" DATE NOT NULL,
  "end_time" DATE NOT NULL,
  "reason" VARCHAR(200) NOT NULL,
  "status" VARCHAR(20) NOT NULL,
  "approver_id" INTEGER,
  PRIMARY KEY ("id"),
  FOREIGN KEY ("user_id") REFERENCES "user" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION,
  FOREIGN KEY ("approver_id") REFERENCES "user" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION
);

-- ----------------------------
-- Table structure for meeting_apply
-- ----------------------------
-- 会议室申请表补充字段
DROP TABLE IF EXISTS "meeting_apply";
CREATE TABLE "meeting_apply" (
  "id" INTEGER NOT NULL,
  "user_id" INTEGER NOT NULL,
  "room_id" INTEGER NOT NULL,
  "start_time" DATETIME NOT NULL,
  "end_time" DATETIME NOT NULL,
  "reason" VARCHAR(500),
  "status" VARCHAR(20) NOT NULL DEFAULT '待审批',
  "approver_id" INTEGER,
  "apply_time" DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 新增
  "approve_remark" VARCHAR(500),  -- 新增
  "approve_time" DATETIME,  -- 新增
  "participants" INTEGER,  -- 新增
  PRIMARY KEY ("id"),
  FOREIGN KEY ("user_id") REFERENCES "user" ("id") ON DELETE CASCADE,
  FOREIGN KEY ("room_id") REFERENCES "meeting_room" ("id") ON DELETE CASCADE,
  FOREIGN KEY ("approver_id") REFERENCES "user" ("id") ON DELETE SET NULL
);

-- ----------------------------
-- Table structure for meeting_room
-- ----------------------------
DROP TABLE IF EXISTS "meeting_room";
CREATE TABLE "meeting_room" (
  "id" INTEGER NOT NULL,
  "room_no" VARCHAR(20) NOT NULL,
  "capacity" INTEGER NOT NULL,
  "status" VARCHAR(20) NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE ("room_no" ASC)
);

-- ----------------------------
-- Table structure for process
-- ----------------------------
DROP TABLE IF EXISTS "process";
CREATE TABLE "process" (
  "id" INTEGER NOT NULL,
  "process_name" VARCHAR(100) NOT NULL,
  "process_steps" VARCHAR(200) NOT NULL,
  "department" VARCHAR(50) NOT NULL,
  "status" VARCHAR(20) NOT NULL,
  PRIMARY KEY ("id")
);

-- ----------------------------
-- Table structure for user
-- ----------------------------
-- 修改main.sql中的user表结构
DROP TABLE IF EXISTS "user";
CREATE TABLE "user" (
  "id" INTEGER NOT NULL,
  "username" VARCHAR(50) NOT NULL,
  "password" VARCHAR(50) NOT NULL,
  "role" VARCHAR(20) NOT NULL,
  "department" VARCHAR(50) NOT NULL,
  "real_name" VARCHAR(50) NOT NULL,
  "status" VARCHAR NOT NULL DEFAULT '正在审批',  -- 注意添加引号
  "resignation_reason" VARCHAR,
  "resignation_status" VARCHAR DEFAULT '未申请',  -- 补充默认值
  "expected_resign_date" DATE,  -- 新增：预计离职日期
  "approval_comment" VARCHAR(500),  -- 新增：审批意见
  PRIMARY KEY ("id"),
  UNIQUE ("username" ASC)
);

PRAGMA foreign_keys = true;

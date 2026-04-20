# OA 办公自动化系统

基于 Flask + SQLite 的轻量级 OA 系统，覆盖员工日常办公中的签到、请假、会议室、设备、合同与流程审批等场景。

## 功能概览

- 用户与权限
	- 登录、注册
	- 角色权限：`admin`、`manager`、`employee`
- 员工管理
	- 员工信息维护
	- 新员工注册审批
	- 离职申请与审批
- 日常办公
	- 签到与签到记录
	- 请假申请、我的请假、请假审批
- 资源管理
	- 会议室申请、审批、冲突检查、取消申请
	- 设备新增、领用、归还、报废
	- 合同新增、编辑、列表
- 流程管理
	- 流程定义（增删改查）
	- 流程发起、实例跟踪、审批记录
- 定时任务
	- 使用 APScheduler 自动释放过期会议室

## 技术栈

- Python `>=3.8`
- Flask
- Flask-SQLAlchemy
- Flask-WTF（CSRF）
- Flask-Login
- APScheduler
- SQLite

## 快速开始

### 1. 克隆或进入项目目录

```bash
cd d:\code\python\oa
```

### 2. 创建并激活虚拟环境（推荐）

Windows（PowerShell）：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows（CMD）：

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

如果你使用 `pyproject.toml` 管理依赖，也可使用 `uv` 或 `pip` 按需安装。

### 4. 启动项目

```bash
python app.py
```

启动后访问：`http://127.0.0.1:5000`

首次运行会自动：

- 创建 SQLite 数据库（`instance/oa.db`）
- 初始化基础测试数据（用户、员工信息、会议室、设备、流程定义、合同）

## 默认测试账号

- 管理员：`admin / admin`
- 经理：`manager / 123456`
- 员工：`employee / 123456`

## 项目结构

```text
oa/
├─ app.py                   # 应用入口、模型与路由
├─ requirements.txt         # pip 依赖
├─ pyproject.toml           # 项目与依赖声明
├─ main.sql                 # 参考建表脚本（可选）
├─ instance/
│  └─ oa.db                 # 运行后自动生成的 SQLite 数据库
├─ static/                  # 静态资源（Bootstrap/JQuery）
└─ templates/               # 页面模板
	 ├─ login.html
	 ├─ dashboard.html
	 ├─ employee/
	 ├─ leave/
	 ├─ meeting/
	 ├─ equipment/
	 ├─ contract/
	 └─ workflow/
```

## 主要路由说明（节选）

- 认证与首页
	- `/`、`/login`：登录
	- `/register`：注册
	- `/dashboard`：仪表盘
	- `/logout`：退出登录
- 员工与审批
	- `/employee/info`：个人信息
	- `/employee/approve`：员工注册审批
	- `/resign_apply`：离职申请
	- `/resign_approve`：离职审批
- 签到
	- `/checkin`：签到
	- `/checkin/record`：签到记录
- 请假
	- `/leave/apply`：请假申请
	- `/leave/my_leave`：我的请假
	- `/leave/approve`：请假审批
- 会议室
	- `/meeting/apply`：会议室申请
	- `/meeting-approve`：会议审批
	- `/meeting/my_meeting`：我的会议
	- `/check-meeting-conflict`：会议冲突检查（JSON）
- 设备
	- `/equipment/list`：设备列表
	- `/equipment/add`：新增设备
	- `/equipment/borrow`：领用设备
	- `/equipment/return`：归还设备
- 合同
	- `/contract/list`：合同列表
	- `/contract/add`：新增合同
	- `/contract/edit/<contract_id>`：编辑合同
- 工作流
	- `/workflow/definitions`：流程定义列表
	- `/workflow/definition/add`：新增流程定义
	- `/workflow/start/<def_id>`：发起流程
	- `/my_workflow_instances`：我的流程实例

## 数据库说明

- 默认数据库：SQLite
- 连接配置：`app.py` 中 `SQLALCHEMY_DATABASE_URI = 'sqlite:///oa.db'`
- 建议使用方式：优先通过 `app.py` 自动初始化
- `main.sql` 用于参考或手动初始化（与代码迭代可能存在差异）

## 常见问题

### 1）端口被占用怎么办？

可在 `app.py` 中修改 `app.run(...)` 的端口，例如：

```python
app.run(debug=True, port=5001)
```

### 2）如何重置测试数据？

删除 `instance/oa.db` 后重新执行：

```bash
python app.py
```

### 3）为什么看不到某些菜单或页面？

该系统基于角色做权限控制，不同角色可访问的功能不同。

## 安全与生产建议

- 当前示例为学习/演示用途：
	- 用户密码为明文存储
	- `SECRET_KEY` 写在代码中
	- 默认以 `debug=True` 运行
- 生产环境建议：
	- 使用密码哈希（如 `werkzeug.security`）
	- 使用环境变量管理密钥和配置
	- 关闭 Debug，接入 WSGI 服务（gunicorn/uwsgi 等）
	- 增加日志、审计、限流与备份策略

## License

仅用于学习与课程设计演示。

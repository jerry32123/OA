from flask import Flask, render_template, request, redirect, url_for, flash, session,jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from functools import wraps
from flask_wtf.csrf import CSRFProtect
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import SQLAlchemyError
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user
from sqlalchemy import or_

import os

# ========== 初始化配置 ==========
app = Flask(__name__)
app.config['SECRET_KEY'] = 'oa_system_2025'  # 会话加密密钥
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///oa.db'  # SQLite数据库
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 关闭不必要的警告
db = SQLAlchemy(app)
CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # 指定登录页面的路由
# ========== 权限装饰器 ==========
def login_required(f):
    """登录验证装饰器"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录！', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """管理员权限装饰器"""

    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('无管理员权限！', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


def manager_required(f):
    """经理权限装饰器（管理员也可访问）"""

    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['admin', 'manager']:
            flash('无审批权限！', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function



# ========== 定时任务 ==========
scheduler = BackgroundScheduler()

def check_meeting_room_status():
    """检查并更新过期的会议室状态"""
    with app.app_context():
        expired_applies = MeetingApply.query.filter(
            MeetingApply.end_time < datetime.now(),
            MeetingApply.status == "已批准"
        ).all()

        for apply in expired_applies:
            room = MeetingRoom.query.get(apply.room_id)
            if room:
                room.status = "空闲"
                db.session.commit()
                print(f"会议室 {room.room_no} 已自动释放为空闲状态")

# 每分钟执行一次检查
scheduler.add_job(check_meeting_room_status, 'interval', minutes=1)
scheduler.start()

# 确保程序退出时正确关闭调度器
import atexit
atexit.register(lambda: scheduler.shutdown())

# ========== 数据库模型 ==========
class User(db.Model):
    """用户表（角色：admin/manager/employee）"""
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin/manager/employee
    department = db.Column(db.String(50), nullable=False)
    real_name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='正在审批')
    resignation_reason = db.Column(db.String(200))  # 离职原因
    resignation_status = db.Column(db.String(20), default='未申请')  # 未申请/待审批/已批准/已拒绝

    expected_resign_date = db.Column(db.Date)  # 预计离职日期
    approval_comment = db.Column(db.String(500))  # 审批意见
    # 关系定义
    employee_info = db.relationship('EmployeeInfo', backref='user', uselist=False, cascade="all, delete-orphan")
    checkins = db.relationship('CheckIn', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    # 请假记录关系
    leaves_as_applicant = db.relationship(
        'Leave',
        backref='applicant',
        lazy='dynamic',
        foreign_keys='Leave.user_id',
        cascade="all, delete-orphan"
    )

    leaves_as_approver = db.relationship(
        'Leave',
        backref='approver',
        lazy='dynamic',
        foreign_keys='Leave.approver_id'
    )

    # 设备借用关系
    equipments_borrowed = db.relationship('Equipment', backref='borrower', lazy='dynamic')

    # 会议室申请关系（申请人）
    meeting_applies_as_applicant = db.relationship(
        'MeetingApply',
        backref='meeting_applicant',
        lazy='dynamic',
        foreign_keys='MeetingApply.user_id',
        cascade="all, delete-orphan",
        overlaps="applicant,my_meeting_applies"  # 修正重叠参数
    )

    # 会议室申请关系（审批人）
    meeting_applies_as_approver = db.relationship(
        'MeetingApply',
        backref='meeting_approver',
        lazy='dynamic',
        foreign_keys='MeetingApply.approver_id',
        overlaps="approver,approved_meetings"  # 修正重叠参数
    )

@login_manager.user_loader
def load_user(user_id):
    """根据用户 ID 加载用户对象"""
    # 实际项目中，这里通常从数据库查询用户，例如：
    # return User.query.get(int(user_id))
    # 此处为示例，直接返回一个测试用户
    return User(user_id) if user_id.isdigit() else None

class EmployeeInfo(db.Model):
    """员工信息表（工资明细等）"""
    __tablename__ = 'employee_info'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, unique=True)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(50))
    address = db.Column(db.String(200))
    salary_base = db.Column(db.Float, default=0.0)
    salary_bonus = db.Column(db.Float, default=0.0)
    salary_deduction = db.Column(db.Float, default=0.0)
    salary_total = db.Column(db.Float, default=0.0)


class CheckIn(db.Model):
    """签到表"""
    __tablename__ = 'checkin'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    check_in_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    status = db.Column(db.String(20), nullable=False)  # 正常/迟到/早退


class Leave(db.Model):
    """请假表"""
    __tablename__ = 'leave'

    id = db.Column(db.Integer, primary_key=True)
    # 申请人ID（关联User.id）
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    # 审批人ID（关联User.id，可为空：未审批时）
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    leave_type = db.Column(db.String(20), nullable=False)  # 事假/病假/年假
    start_time = db.Column(db.Date, nullable=False)
    end_time = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='待审批')  # 待审批/已批准/已拒绝

    # 修复5：添加索引以提高查询性能
    __table_args__ = (
        db.Index('idx_leave_user_status', 'user_id', 'status'),
        db.Index('idx_leave_dates', 'start_time', 'end_time'),
    )


class Equipment(db.Model):
    """设备表"""
    __tablename__ = 'equipment'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 电脑/打印机/投影仪等
    status = db.Column(db.String(20), nullable=False, default='空闲')  # 空闲/已领用
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # 领用者，可为空
    borrow_time = db.Column(db.DateTime, nullable=True)
    return_time = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Integer, default=1)

    # 修复6：添加检查约束（借用和归还时间逻辑）
    __table_args__ = (
        db.CheckConstraint('(status = "已领用" AND user_id IS NOT NULL) OR (status = "空闲" AND user_id IS NULL)',
                           name='check_equipment_status'),
    )


class Contract(db.Model):
    """合同表"""
    __tablename__ = 'contract'

    id = db.Column(db.Integer, primary_key=True)
    contract_name = db.Column(db.String(100), nullable=False)
    contract_no = db.Column(db.String(50), unique=True, nullable=False)
    party_a = db.Column(db.String(100), nullable=False)
    party_b = db.Column(db.String(100), nullable=False)
    sign_time = db.Column(db.Date, nullable=False)
    content = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='有效')  # 有效/失效

    __table_args__ = (
        db.Index('idx_contract_no', 'contract_no'),
    )



class WorkflowDefinition(db.Model):
    __tablename__ = 'workflow_definitions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 流程名称
    description = db.Column(db.String(500))  # 流程描述
    trigger_event = db.Column(db.String(50), nullable=False)  # 触发事件：如"请假"、"设备领用"
    department = db.Column(db.String(50), nullable=False)  # 所属部门
    status = db.Column(db.String(20), default='启用')  # 启用/停用
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_time = db.Column(db.DateTime, default=datetime.now)

    # 关联步骤
    steps = db.relationship('WorkflowStep', backref='definition', cascade='all, delete-orphan')


class WorkflowStep(db.Model):
    __tablename__ = 'workflow_steps'
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflow_definitions.id'), nullable=False)
    step_order = db.Column(db.Integer, nullable=False)  # 步骤顺序（1,2,3...）
    required_role = db.Column(db.String(20), nullable=False)  # 所需角色：admin/manager/employee
    timeout_hours = db.Column(db.Integer, default=72)  # 超时时间（小时）
    description = db.Column(db.String(200))  # 步骤描述


class WorkflowInstance(db.Model):
    __tablename__ = 'workflow_instances'
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflow_definitions.id'), nullable=False)
    initiator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 发起人
    related_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # 关联用户（如请假人）
    status = db.Column(db.String(20), default='进行中')  # 进行中/已完成/已拒绝
    current_step_id = db.Column(db.Integer, db.ForeignKey('workflow_steps.id'))  # 当前步骤
    created_at = db.Column(db.DateTime, default=datetime.now)
    completed_at = db.Column(db.DateTime)

    # 关联审批记录
    approvals = db.relationship('ApprovalRecord', backref='instance', cascade='all, delete-orphan')



# 审批记录表
class ApprovalRecord(db.Model):
    __tablename__ = 'approval_records'
    id = db.Column(db.Integer, primary_key=True)
    instance_id = db.Column(db.Integer, db.ForeignKey('workflow_instances.id'), nullable=False)
    step_id = db.Column(db.Integer, db.ForeignKey('workflow_steps.id'), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 审批人
    approval_status = db.Column(db.String(20), default='待审批')  # 待审批/通过/拒绝
    comments = db.Column(db.String(500))  # 审批意见
    approved_at = db.Column(db.DateTime)
    deadline = db.Column(db.DateTime)  # 截止时间

class MeetingRoom(db.Model):
    """会议室表"""
    __tablename__ = 'meeting_room'

    id = db.Column(db.Integer, primary_key=True)
    room_no = db.Column(db.String(20), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='空闲')  # 空闲/已预约

    # 修复7：会议室申请关系
    applies = db.relationship(
        'MeetingApply',
        backref='meeting_room',
        lazy='dynamic',
        cascade="all, delete-orphan",
        overlaps="meeting_applies,room"  # 解决重叠警告
    )

class MeetingApply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('meeting_room.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(500))
    status = db.Column(db.String(20), default='待审批')
    apply_time = db.Column(db.DateTime, default=datetime.now)
    approve_remark = db.Column(db.String(500))
    approve_time = db.Column(db.DateTime)
    participants = db.Column(db.Integer)

    # 补充申请人和审批人关系（如果需要）
    applicant = db.relationship(
        'User',
        foreign_keys=[user_id],
        overlaps="meeting_applies_as_applicant,meeting_applicant"
    )
    approver = db.relationship(
        'User',
        foreign_keys=[approver_id],
        overlaps="meeting_applies_as_approver,meeting_approver"
    )

# ========== 初始化数据库和测试数据 ==========
def init_db():
    with app.app_context():
        db.create_all()  # 创建所有表
        # 初始化测试数据（仅首次运行）
        if not User.query.filter_by(username='admin').first():
            # 管理员：admin/admin
            admin = User(
                username='admin', password='admin', role='admin',
                department='行政部', real_name='系统管理员'
            )
            # 经理：manager/123456
            manager = User(
                username='manager', password='123456', role='manager',
                department='技术部', real_name='技术部经理'
            )
            # 普通员工：employee/123456
            employee = User(
                username='employee', password='123456', role='employee',
                department='技术部', real_name='普通员工'
            )
            db.session.add_all([admin, manager, employee])
            db.session.flush()  # 获取ID

            # 员工信息
            admin_info = EmployeeInfo(
                user_id=admin.id, age=30, gender='男', phone='13800138000',
                email='admin@company.com', address='北京市朝阳区',
                salary_base=10000, salary_bonus=2000, salary_deduction=500, salary_total=11500
            )
            manager_info = EmployeeInfo(
                user_id=manager.id, age=35, gender='男', phone='13900139000',
                email='manager@company.com', address='北京市海淀区',
                salary_base=15000, salary_bonus=3000, salary_deduction=800, salary_total=17200
            )
            employee_info = EmployeeInfo(
                user_id=employee.id, age=25, gender='女', phone='13700137000',
                email='employee@company.com', address='北京市西城区',
                salary_base=8000, salary_bonus=1000, salary_deduction=200, salary_total=8800
            )
            db.session.add_all([admin_info, manager_info, employee_info])

            # 会议室
            room1 = MeetingRoom(room_no='101', capacity=10)
            room2 = MeetingRoom(room_no='102', capacity=20)
            room3 = MeetingRoom(room_no='201', capacity=30)
            db.session.add_all([room1, room2, room3])

            # 设备
            equip1 = Equipment(name='联想笔记本1', type='电脑', status='空闲')
            equip2 = Equipment(name='惠普打印机1', type='打印机', status='空闲')
            equip3 = Equipment(name='明基投影仪1', type='投影仪', status='空闲')
            db.session.add_all([equip1, equip2, equip3])

            # 流程定义
            workflow1 = WorkflowDefinition(
                name='请假流程',
                description='员工请假审批流程',
                trigger_event='请假',  # 对应触发事件
                department='技术部',
                status='启用',
                created_by=admin.id  # 关联管理员创建
            )
            db.session.add(workflow1)
            db.session.flush()  # 获取流程ID

            # 补充流程步骤（与流程定义关联）
            step1 = WorkflowStep(
                workflow_id=workflow1.id,
                step_order=1,
                required_role='manager',  # 经理审批
                timeout_hours=24,
                description='部门经理审批'
            )
            step2 = WorkflowStep(
                workflow_id=workflow1.id,
                step_order=2,
                required_role='admin',  # 行政（管理员）备案
                timeout_hours=48,
                description='行政备案'
            )
            db.session.add_all([step1, step2])

            # 合同
            contract1 = Contract(
                contract_name='技术服务合同', contract_no='HT2025001',
                party_a='本公司', party_b='合作方A', sign_time=date(2025, 1, 1),
                content='技术服务相关条款', status='有效'
            )
            db.session.add(contract1)

            db.session.commit()

            definitions = WorkflowDefinition.query.all()
            print(f"初始化后共有 {len(definitions)} 条工作流定义")
            for defn in definitions:
                print(f"ID: {defn.id}, Name: {defn.name}, Department: {defn.department}, Status: {defn.status}")


# ========== 路由 ==========
# 登录
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            # 保存用户信息到会话
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['department'] = user.department
            session['real_name'] = user.real_name
            flash('登录成功！', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误！', 'danger')
    return render_template('login.html')

# 注册路由
@app.route('/register', methods=['GET', 'POST'])
def register():
    """极简注册功能，适配原有模型和模板风格"""
    if request.method == 'POST':
        # 1. 获取表单数据（对应注册页面的字段）
        username = request.form.get('username')
        password = request.form.get('password')
        real_name = request.form.get('real_name')
        department = request.form.get('department')
        role = request.form.get('role')  # 限制默认为employee，防止注册管理员

        # 2. 最简非空判断
        if not all([username, password, real_name, department, role]):
            flash('请填写所有必填字段！', 'danger')
            return render_template('register.html')

        # 3. 检查用户名是否重复
        if User.query.filter_by(username=username).first():
            flash('用户名已存在，请更换！', 'danger')
            return render_template('register.html')

        # 4. 创建用户（适配原有User模型，使用默认值）
        new_user = User(
            username=username,
            password=password,  # 原模型为明文，直接存储
            real_name=real_name,
            department=department,
            role=role  # 前端限制为employee，此处直接接收
            # 模型默认字段：status='正在审批'、resignation_status='未申请'，无需手动传参
        )

        # 5. 数据库存储（极简异常处理）
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('注册成功！请等待管理员审批', 'success')
            return redirect(url_for('login'))  # 跳转到原有登录页
        except Exception as e:
            db.session.rollback()
            flash(f'注册失败：{str(e)}', 'danger')

    # GET请求：展示注册页面
    return render_template('register.html')


# 员工注册审批路由
@app.route('/employee/approve', methods=['GET', 'POST'])
@manager_required  # 或 admin_required，根据你的权限设计
def employee_approve():
    # GET 请求：展示待审批列表
    if request.method == 'GET':
        pending_users = User.query.filter_by(status='正在审批').all()  # 待审批状态
        return render_template('employee/approve.html', users=pending_users)

    # POST 请求：处理审批操作
    else:
        user_id = request.form.get('user_id')  # 从表单获取用户ID
        status = request.form.get('status')  # 从表单获取审批状态（“已批准”或“已拒绝”）

        user = User.query.get_or_404(user_id)

        # 核心：根据前端提交的status正确更新数据库
        if status == '已批准':
            user.status = '在职'  # 批准时设置为“已批准”
        elif status == '已拒绝':
            user.status = '已拒绝'  # 拒绝时设置为“已拒绝”
        else:
            flash('无效的审批状态', 'danger')
            return redirect(url_for('employee_approve'))

        db.session.commit()
        flash(f'用户 {user.username} 审批已完成', 'success')
        return redirect(url_for('employee_approve'))


# 修改全员信息查询，排除已离职用户
@app.route('/employee/all')
@manager_required
def all_employee_info():
    # 只显示在职员工
    users = User.query.filter_by(status='在职').all()
    return render_template('employee/all_info.html', users=users)

# 登出
@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('已安全登出！', 'success')
    return redirect(url_for('login'))


@app.route('/resign_apply', methods=['GET', 'POST'])
@login_required
def resign_apply():
    if request.method == 'POST':
        # 获取表单数据
        resign_date_str = request.form.get('resign_date')  # 字符串格式的日期
        reason = request.form.get('reason', '').strip()

        # 验证数据
        if not resign_date_str:
            flash('请选择预计离职日期', 'danger')
            return redirect(url_for('resign_apply'))
        if not reason:
            flash('请填写填写离职原因', 'danger')
            return redirect(url_for('resign_apply'))

        # 关键修复：将字符串转换为date对象
        try:
            # 解析日期字符串（'%Y-%m-%d'对应'2025-12-16'格式）
            expected_resign_date = datetime.strptime(resign_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('日期格式错误，请使用YYYY-MM-DD格式', 'danger')
            return redirect(url_for('resign_apply'))

        # 更新用户信息
        user = User.query.get(session['user_id'])
        user.resignation_reason = reason
        user.resignation_status = '待审批'
        user.expected_resign_date = expected_resign_date  # 传入转换后的date对象

        try:
            db.session.commit()
            flash('离职申请已提交', 'success')
            return redirect(url_for('employee_info'))
        except Exception as e:
            db.session.rollback()
            flash(f'提交失败：{str(e)}', 'danger')
            return redirect(url_for('resign_apply'))

    # GET请求处理逻辑
    return render_template('employee/resign_apply.html')


# 离职审批处理
@app.route('/resign_approve', methods=['GET', 'POST'])
@admin_required  # 仅管理员有权限
def resign_approve():
    # 获取待审批列表
    pending_users = User.query.filter_by(resignation_status='待审批', status='在职').all()

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        status = request.form.get('status')  # 已批准/已拒绝
        comment = request.form.get('comment', '').strip()

        # 验证必要参数
        if not user_id or not status:
            flash('参数错误，无法处理请求', 'danger')
            return redirect(url_for('resign_approve'))

        # 查找用户
        user = User.query.get(user_id)
        if not user:
            flash('未找到指定用户', 'danger')
            return redirect(url_for('resign_approve'))

        # 验证用户状态（防止重复处理）
        if user.resignation_status != '待审批' or user.status != '在职':
            flash('该申请已处理或状态异常', 'warning')
            return redirect(url_for('resign_approve'))

        # 验证审批意见（可选，根据业务需求）
        if not comment:
            flash('请填写审批意见', 'warning')
            return redirect(url_for('resign_approve'))

        try:
            # 更新状态
            user.resignation_status = status
            user.approval_comment = comment  # 保存审批意见
            if status == '已批准':
                user.status = '已离职'  # 变更为离职状态

            db.session.commit()
            flash(f'已{status}用户 {user.real_name} 的离职申请', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'处理失败：{str(e)}', 'danger')

        return redirect(url_for('resign_approve'))

    return render_template('employee/resign_approve.html', users=pending_users)

# 仪表盘（主页面）
@app.route('/dashboard')
@login_required
def dashboard():
    # 生成当前时间字符串（后端处理，避免模板直接调用datetime）
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('dashboard.html',
                           role=session.get('role'),
                           real_name=session.get('real_name'),
                           department=session.get('department'),
                           current_time=current_time)  # 传递生成好的时间字符串



# ========== 员工信息管理 ==========
# 个人信息
@app.route('/employee/info', methods=['GET', 'POST'])
@login_required
def employee_info():
    user = User.query.get(session['user_id'])
    if not user:
        flash('用户不存在', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # 更新用户信息
        user.real_name = request.form.get('real_name', user.real_name)

        # 确保员工信息记录存在
        if not user.employee_info:
            user.employee_info = EmployeeInfo(user_id=user.id)

        # 更新员工详细信息
        user.employee_info.age = request.form.get('age')
        user.employee_info.gender = request.form.get('gender')
        user.employee_info.phone = request.form.get('phone')
        user.employee_info.email = request.form.get('email')
        user.employee_info.address = request.form.get('address')

        db.session.commit()
        flash('个人信息更新成功', 'success')
        return redirect(url_for('employee_info'))

    return render_template('employee/info.html', user=user)


# ========== 签到管理 ==========
# 今日签到
# 今日签到
@app.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    user_id = session.get('user_id')
    today = date.today()
    # 生成今日日期字符串（后端处理）
    today_str = today.strftime('%Y年%m月%d日')
    # 检查今日是否已签到
    has_checkin = CheckIn.query.filter(
        CheckIn.user_id == user_id,
        db.func.date(CheckIn.check_in_time) == today
    ).first()

    if request.method == 'POST' and not has_checkin:
        # 执行签到
        now = datetime.now()
        # 判断是否迟到（9:00前为正常）
        if now.hour > 9 or (now.hour == 9 and now.minute > 0):
            status = '迟到'
        else:
            status = '正常'
        new_checkin = CheckIn(
            user_id=user_id,
            check_in_time=now,
            status=status
        )
        db.session.add(new_checkin)
        db.session.commit()
        flash(f'签到成功！状态：{status}', 'success')
        return redirect(url_for('checkin'))

    # 传递today_str到模板，替代模板中的date.today()
    return render_template('checkin/checkin.html', has_checkin=has_checkin, today_str=today_str)



# 签到记录
@app.route('/checkin/record')
@login_required
def checkin_record():
    user_id = session.get('user_id')
    records = CheckIn.query.filter_by(user_id=user_id).order_by(CheckIn.check_in_time.desc()).all()
    return render_template('checkin/record.html', records=records)


# ========== 请假管理 ==========
# 提交请假申请
@app.route('/leave/apply', methods=['GET', 'POST'])
@login_required
def leave_apply():
    if request.method == 'POST':
        try:
            leave_type = request.form.get('leave_type')
            start_time = datetime.strptime(request.form.get('start_time'), '%Y-%m-%d').date()
            end_time = datetime.strptime(request.form.get('end_time'), '%Y-%m-%d').date()
            reason = request.form.get('reason')

            # 验证数据
            if not all([leave_type, start_time, end_time, reason]):
                flash('请填写完整信息', 'danger')
                return redirect(url_for('leave_apply'))

            if start_time > end_time:
                flash('开始日期不能晚于结束日期', 'danger')
                return redirect(url_for('leave_apply'))

            # 获取审批人（经理或管理员）
            approver = User.query.filter(User.role.in_(['admin', 'manager'])).first()
            if not approver:
                flash('未找到审批人，请联系系统管理员', 'danger')
                return redirect(url_for('leave_apply'))

            # 创建请假记录
            new_leave = Leave(
                user_id=session['user_id'],
                leave_type=leave_type,
                start_time=start_time,
                end_time=end_time,
                reason=reason,
                status='待审批',
                approver_id=approver.id
            )

            db.session.add(new_leave)
            db.session.commit()
            flash('请假申请提交成功，等待审批', 'success')
            return redirect(url_for('my_leave'))

        except Exception as e:
            db.session.rollback()
            flash(f'提交失败：{str(e)}', 'danger')
            return redirect(url_for('leave_apply'))

    return render_template('leave/apply.html')

# 我的请假记录
@app.route('/leave/my_leave')
@login_required
def my_leave():
    user_id = session.get('user_id')
    leaves = Leave.query.filter_by(user_id=user_id).order_by(Leave.start_time.desc()).all()
    # 获取审批人姓名 - 修复关系访问
    for leave in leaves:
        if leave.approver_id:
            approver = User.query.get(leave.approver_id)
            leave.approver_name = approver.real_name if approver else '未知'
        else:
            leave.approver_name = '未审批'
    return render_template('leave/my_leave.html', leaves=leaves)


# 审批请假申请（经理/管理员）
@app.route('/leave/approve', methods=['GET', 'POST'])
@manager_required
def leave_approve():
    department = session.get('department')

    # 修复查询：使用正确的连接方式
    leaves = db.session.query(Leave).join(
        User, Leave.user_id == User.id
    ).filter(
        Leave.status == '待审批',
        User.department == department
    ).order_by(Leave.start_time).all()

    if request.method == 'POST':
        leave_id = request.form.get('leave_id')
        status = request.form.get('status')
        approver_id = session.get('user_id')

        leave = Leave.query.get(leave_id)
        if leave:
            leave.status = status
            leave.approver_id = approver_id
            db.session.commit()
            flash(f'请假申请已{status}！', 'success')
            return redirect(url_for('leave_approve'))

    return render_template('leave/approve.html', leaves=leaves)


# ========== 设备管理 ==========
# 设备列表
@app.route('/equipment/list')
@login_required
def equipment_list():
    # 管理员可以查看所有设备，包括已报废的
    if session.get('role') == 'admin':
        equipments = Equipment.query.all()
    else:
        # 普通用户只能看到可使用的设备
        equipments = Equipment.query.filter_by(is_active=1).all()

    return render_template('equipment/list.html', equipments=equipments)


# 领用设备
# 领用设备（补充borrow_time）
@app.route('/equipment/borrow', methods=['GET', 'POST'])
@login_required
def equipment_borrow():
    user_id = session.get('user_id')
    free_equipments = Equipment.query.filter_by(status='空闲').all()

    if request.method == 'POST':
        try:
            equip_id = request.form.get('equip_id')
            equip = Equipment.query.get(equip_id)
            if equip and equip.status == '空闲':
                equip.status = '已领用'
                equip.user_id = user_id
                equip.borrow_time = datetime.now()  # 确保记录领用时间
                db.session.commit()
                flash('设备领用成功！', 'success')
                return redirect(url_for('equipment_list'))
            else:
                flash('设备已被领用！', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'领用失败：{str(e)}', 'danger')

    return render_template('equipment/borrow.html', equipments=free_equipments)


# 归还设备
@app.route('/equipment/return', methods=['GET', 'POST'])
@login_required
def equipment_return():
    user_id = session.get('user_id')
    # 修复查询逻辑：确保只查当前用户领用、状态为已领用的设备
    my_equipments = Equipment.query.filter_by(
        user_id=user_id,
        status='已领用'
    ).all()

    if request.method == 'POST':
        try:
            equip_id = request.form.get('equip_id')
            if not equip_id:
                flash('设备ID不能为空！', 'danger')
                return redirect(url_for('equipment_return'))

            equip = Equipment.query.get(equip_id)
            # 双重校验：确保设备存在、且归当前用户领用
            if not equip:
                flash('设备不存在！', 'danger')
                return redirect(url_for('equipment_return'))
            if equip.user_id != user_id or equip.status != '已领用':
                flash('无权归还该设备！', 'danger')
                return redirect(url_for('equipment_return'))

            # 更新设备状态（核心修复：补充return_time、提交事务）
            equip.status = '空闲'
            equip.user_id = None
            equip.return_time = datetime.now()  # 记录归还时间
            db.session.commit()  # 确保提交数据库
            flash('设备归还成功！', 'success')
            return redirect(url_for('equipment_list'))
        except Exception as e:
            db.session.rollback()  # 异常回滚
            flash(f'归还失败：{str(e)}', 'danger')
            return redirect(url_for('equipment_return'))

    return render_template('equipment/return.html', equipments=my_equipments)

# 新增设备（管理员）
@app.route('/equipment/add', methods=['GET', 'POST'])
@admin_required
def equipment_add():
    if request.method == 'POST':
        new_equip = Equipment(
            name=request.form.get('name'),
            type=request.form.get('type'),
            status='空闲'
        )
        db.session.add(new_equip)
        db.session.commit()
        flash('设备新增成功！', 'success')
        return redirect(url_for('equipment_list'))

    return render_template('equipment/add.html')

# 在app.py中添加设备编辑路由
@app.route('/equipment/edit/<int:equip_id>', methods=['GET', 'POST'])
@admin_required
def equipment_edit(equip_id):
    equip = Equipment.query.get_or_404(equip_id)
    if request.method == 'POST':
        # 处理设备编辑逻辑
        equip.name = request.form.get('name')
        equip.type = request.form.get('type')
        # 其他字段更新...
        db.session.commit()
        flash('设备信息更新成功', 'success')
        return redirect(url_for('equipment_list'))
    return render_template('equipment/edit.html', equip=equip)

# 设备报废
@app.route('/equipment/scrap/<int:equip_id>', methods=['POST'])
@admin_required
def equipment_scrap(equip_id):
    try:
        equipment = Equipment.query.get_or_404(equip_id)

        # 检查设备是否已被领用
        if equipment.status == '已领用':
            flash('该设备当前处于领用状态，无法报废', 'danger')
            return redirect(url_for('equipment_list'))

        # 标记为报废
        equipment.is_active = 0
        equipment.status = '已报废'
        db.session.commit()
        flash('设备已成功报废', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'操作失败：{str(e)}', 'danger')

    return redirect(url_for('equipment_list'))

# ========== 合同管理 ==========
# 合同列表
@app.route('/contract/list')
@login_required
def contract_list():
    contracts = Contract.query.all()
    return render_template('contract/list.html', contracts=contracts)


# 新增合同（管理员）
from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # 需导入完整性错误异常
from datetime import datetime

@app.route('/contract/add', methods=['GET', 'POST'])
@admin_required
def contract_add():
    if request.method == 'POST':
        # 1. 获取表单数据
        contract_name = request.form.get('contract_name')
        contract_no = request.form.get('contract_no')
        party_a = request.form.get('party_a')
        party_b = request.form.get('party_b')
        sign_time_str = request.form.get('sign_time')
        content = request.form.get('content', '')  # 允许为空
        status = request.form.get('status')

        # 2. 基础字段验证（防止空值）
        required_fields = {
            'contract_name': '合同名称',
            'contract_no': '合同编号',
            'party_a': '甲方',
            'party_b': '乙方',
            'sign_time_str': '签订日期',
            'status': '合同状态'
        }
        for field, name in required_fields.items():
            if not locals()[field]:  # 检查字段是否为空
                flash(f'请填写{name}', 'danger')
                return render_template('contract/add.html')

        try:
            # 3. 转换签订日期格式
            sign_time = datetime.strptime(sign_time_str, '%Y-%m-%d').date()

            # 4. 创建合同记录
            new_contract = Contract(
                contract_name=contract_name,
                contract_no=contract_no,
                party_a=party_a,
                party_b=party_b,
                sign_time=sign_time,
                content=content,
                status=status
            )
            db.session.add(new_contract)
            db.session.commit()
            flash('合同新增成功！', 'success')
            return redirect(url_for('contract_list'))

        # 5. 细化异常处理
        except ValueError:
            # 日期格式错误（如用户输入非YYYY-MM-DD格式）
            db.session.rollback()
            flash('签订日期格式错误，请使用YYYY-MM-DD格式', 'danger')
        except IntegrityError:
            # 合同编号重复（数据库唯一约束冲突）
            db.session.rollback()
            flash('新增失败：合同编号已存在', 'danger')
        except Exception as e:
            # 其他未知错误
            db.session.rollback()
            flash(f'新增失败：{str(e)}', 'danger')

    # GET请求返回表单页面
    return render_template('contract/add.html')


# 编辑合同（管理员）
@app.route('/contract/edit/<int:contract_id>', methods=['GET', 'POST'])
@admin_required
def contract_edit(contract_id):
    contract = Contract.query.get_or_404(contract_id)

    if request.method == 'POST':
        try:
            contract.contract_name = request.form.get('contract_name')
            contract.contract_no = request.form.get('contract_no')
            contract.party_a = request.form.get('party_a')
            contract.party_b = request.form.get('party_b')
            contract.sign_time = datetime.strptime(request.form.get('sign_time'), '%Y-%m-%d').date()
            contract.content = request.form.get('content')
            contract.status = request.form.get('status')

            db.session.commit()
            flash('合同更新成功', 'success')
            return redirect(url_for('contract_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'danger')

    return render_template('contract/edit.html', contract=contract)





# @app.route('/workflow/definitions')
# @login_required
# def workflow_definitions():
#     """流程定义列表"""
#     definitions = WorkflowDefinition.query.all()
#     return render_template('workflow/definition_list.html', definitions=definitions)


@app.route('/workflow/definition/add', methods=['GET', 'POST'])
@manager_required
def add_workflow_definition():
    """创建流程定义"""
    if request.method == 'POST':
        try:
            # 创建流程定义
            new_def = WorkflowDefinition(
                name=request.form['name'],
                description=request.form['description'],
                trigger_event=request.form['trigger_event'],
                department=request.form['department'],
                created_by=session['user_id']
            )
            db.session.add(new_def)
            db.session.flush()  # 获取ID

            # 添加流程步骤（最多5步）
            step_count = int(request.form['step_count'])
            for i in range(1, step_count + 1):
                step = WorkflowStep(
                    workflow_id=new_def.id,
                    step_order=i,
                    required_role=request.form[f'step_{i}_role'],
                    timeout_hours=int(request.form[f'step_{i}_timeout']),
                    description=request.form[f'step_{i}_desc']
                )
                db.session.add(step)

            db.session.commit()
            flash('流程定义创建成功', 'success')
            return redirect(url_for('workflow_definitions'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败：{str(e)}', 'danger')
    return render_template('workflow/definition_add.html')


# 流程实例管理
@app.route('/workflow/start/<int:def_id>', methods=['GET', 'POST'])
@login_required
def start_workflow(def_id):
    """发起流程实例"""
    definition = WorkflowDefinition.query.get_or_404(def_id)
    if request.method == 'POST':
        try:
            # 创建流程实例
            instance = WorkflowInstance(
                workflow_id=def_id,
                initiator_id=session['user_id'],
                related_user_id=request.form.get('related_user_id', session['user_id'])
            )
            db.session.add(instance)
            db.session.flush()

            # 获取第一步并创建审批记录
            first_step = WorkflowStep.query.filter_by(
                workflow_id=def_id,
                step_order=1
            ).first()

            if first_step:
                # 设置当前步骤
                instance.current_step_id = first_step.id

                # 创建审批记录
                deadline = datetime.now() + timedelta(hours=first_step.timeout_hours)
                approval = ApprovalRecord(
                    instance_id=instance.id,
                    step_id=first_step.id,
                    # 查找符合角色的审批人（此处简化为部门经理）
                    approver_id=get_department_manager_id(session['department']),
                    deadline=deadline
                )
                db.session.add(approval)

            db.session.commit()
            flash(f'流程 "{definition.name}" 已发起', 'success')
            return redirect(url_for('my_workflow_instances'))
        except Exception as e:
            db.session.rollback()
            flash(f'发起失败：{str(e)}', 'danger')
    return render_template('workflow/start.html', definition=definition)


@app.route('/workflow/definitions', methods=['GET'])
@login_required
def workflow_definitions():
    """流程定义列表（支持筛选、分页、部门权限过滤）"""
    try:
        # 1. 获取前端筛选参数
        keyword = request.args.get('keyword', '')  # 按名称/触发事件搜索
        department = request.args.get('department', '')  # 按部门筛选
        status = request.args.get('status', '')  # 按状态（启用/停用）筛选
        page = int(request.args.get('page', 1))  # 分页页码，默认第1页
        per_page = 10  # 每页显示10条

        # 2. 构建查询条件
        query = WorkflowDefinition.query

        # 部门筛选（普通员工仅看本部门，管理员/经理可看所有）
        if department:
            query = query.filter(WorkflowDefinition.department == department)
        elif session.get('role') not in ['admin', 'manager']:  # 普通员工默认看本部门
            query = query.filter(WorkflowDefinition.department == session.get('department'))

        # 状态筛选
        if status:
            query = query.filter(WorkflowDefinition.status == status)

        # 关键词筛选（名称、描述、触发事件）- 只有keyword不为空时才应用
        if keyword:
            query = query.filter(
                or_(
                    WorkflowDefinition.name.like(f'%{keyword}%'),
                    WorkflowDefinition.description.like(f'%{keyword}%'),
                    WorkflowDefinition.trigger_event.like(f'%{keyword}%')
                )
            )

        # 3. 执行查询（分页）
        pagination = query.order_by(WorkflowDefinition.created_time.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        definitions = pagination.items  # 当前页的流程定义列表

        # 4. 获取所有部门列表用于筛选
        all_departments = db.session.query(WorkflowDefinition.department).distinct().all()
        departments = [dept[0] for dept in all_departments] if all_departments else []

        # 5. 传递数据到模板
        return render_template(
            'workflow/definition_list.html',
            definitions=definitions,
            pagination=pagination,
            keyword=keyword,
            department=department,
            status=status,
            departments=departments
        )
    except Exception as e:
        app.logger.error(f"查询流程定义失败：{str(e)}")
        flash(f'查询流程定义失败：{str(e)}', 'danger')
        return render_template('workflow/definition_list.html',
                               definitions=[],
                               pagination=None,
                               keyword='',
                               department='',
                               status='',
                               departments=[])


# 编辑流程定义
@app.route('/workflow/definition/edit/<int:definition_id>', methods=['GET', 'POST'])
@manager_required
def edit_workflow_definition(definition_id):
    """编辑流程定义"""
    definition = WorkflowDefinition.query.get_or_404(definition_id)

    # 添加：获取部门列表用于下拉框
    departments = db.session.query(User.department).distinct().all()
    departments = [dept[0] for dept in departments if dept[0]]

    # 添加：获取该流程的步骤
    steps = WorkflowStep.query.filter_by(workflow_id=definition_id).order_by(WorkflowStep.step_order).all()

    if request.method == 'POST':
        try:
            definition.name = request.form['name']
            definition.description = request.form['description']
            definition.trigger_event = request.form['trigger_event']
            definition.department = request.form['department']
            definition.status = request.form.get('status', '启用')

            db.session.commit()
            flash('流程定义更新成功', 'success')
            return redirect(url_for('workflow_definitions'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'danger')

    # 添加：传递步骤和部门信息给模板
    return render_template('workflow/definition_edit.html',
                           definition=definition,
                           steps=steps,
                           departments=departments)


# 删除流程定义
@app.route('/workflow/definition/delete/<int:definition_id>')
@manager_required
def delete_workflow_definition(definition_id):
    """删除流程定义"""
    try:
        definition = WorkflowDefinition.query.get_or_404(definition_id)

        # 检查是否有相关的流程实例
        instances = WorkflowInstance.query.filter_by(workflow_id=definition_id).first()
        if instances:
            flash('该流程定义已被使用，无法删除', 'danger')
            return redirect(url_for('workflow_definitions'))

        db.session.delete(definition)
        db.session.commit()
        flash('流程定义删除成功', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败：{str(e)}', 'danger')

    return redirect(url_for('workflow_definitions'))


@app.route('/workflow/definition/<int:def_id>', methods=['GET'])
@login_required
def workflow_definition_detail(def_id):
    """流程定义详情（包含所有步骤）"""
    try:
        # 1. 查询流程定义（不存在则404）
        definition = WorkflowDefinition.query.get_or_404(def_id)
        # 2. 查询该流程的所有步骤（按顺序排序）
        steps = WorkflowStep.query.filter_by(workflow_id=def_id).order_by(WorkflowStep.step_order).all()

        # 3. 查询创建人信息
        creator_info = None
        if definition.created_by:
            creator = User.query.get(definition.created_by)
            if creator:
                creator_info = {
                    'id': creator.id,
                    'username': creator.username,
                    'real_name': creator.real_name,
                    'role': creator.role,
                    'department': creator.department
                }

        # 4. 传递数据到模板
        return render_template(
            'workflow/definition_detail.html',
            definition=definition,
            steps=steps,
            creator_info=creator_info
        )
    except Exception as e:
        flash(f'查询流程定义详情失败：{str(e)}', 'danger')
        return redirect(url_for('workflow_definitions'))

@app.route('/my_workflow_instances', methods=['GET'])
@login_required
def my_workflow_instances():
    """我的流程实例（支持按状态/流程名称筛选、分页）"""
    try:
        # 1. 获取筛选参数
        status = request.args.get('status', '')  # 进行中/已完成/已拒绝
        workflow_name = request.args.get('workflow_name', '')  # 按流程名称筛选
        page = int(request.args.get('page', 1))
        per_page = 10

        # 2. 构建查询条件（仅查当前用户发起的实例）
        query = WorkflowInstance.query.filter_by(initiator_id=session['user_id'])
        # 按流程状态筛选
        if status:
            query = query.filter(WorkflowInstance.status == status)
        # 按流程名称筛选（关联流程定义表）
        if workflow_name:
            query = query.join(WorkflowDefinition).filter(WorkflowDefinition.name.like(f'%{workflow_name}%'))

        # 3. 执行分页查询
        pagination = query.order_by(WorkflowInstance.created_at.desc()).paginate(page=page, per_page=per_page)
        instances = pagination.items

        # 4. 补充每个实例的流程定义名称和当前步骤名称
        for instance in instances:
            # 流程定义名称
            instance.workflow_name = WorkflowDefinition.query.get(instance.workflow_id).name
            # 当前步骤名称
            if instance.current_step_id:
                instance.current_step_name = WorkflowStep.query.get(instance.current_step_id).description
            else:
                instance.current_step_name = '无'

        return render_template(
            'workflow/my_instances.html',
            instances=instances,
            pagination=pagination,
            status=status,
            workflow_name=workflow_name
        )
    except Exception as e:
        flash(f'查询我的流程实例失败：{str(e)}', 'danger')
        return render_template('workflow/my_instances.html', instances=[], pagination=None)


@app.route('/workflow/instance/<int:instance_id>')
@login_required
def instance_detail(instance_id):
    """查看流程实例详情"""
    try:
        # 1. 获取流程实例
        instance = WorkflowInstance.query.get_or_404(instance_id)

        # 2. 权限检查：只能查看自己发起的实例或审批相关的实例
        user_id = session['user_id']
        if (instance.initiator_id != user_id and
                instance.current_step_id and
                not ApprovalRecord.query.filter_by(
                    instance_id=instance_id,
                    approver_id=user_id
                ).first()):
            flash('无权查看此流程实例', 'danger')
            return redirect(url_for('my_workflow_instances'))

        # 3. 获取相关数据
        definition = WorkflowDefinition.query.get(instance.workflow_id)

        # 获取所有步骤（按顺序排序）
        steps = WorkflowStep.query.filter_by(
            workflow_id=instance.workflow_id
        ).order_by(WorkflowStep.step_order).all()

        # 获取审批记录
        approvals = ApprovalRecord.query.filter_by(
            instance_id=instance_id
        ).order_by(ApprovalRecord.id).all()

        # 补充审批人姓名
        for approval in approvals:
            approver = User.query.get(approval.approver_id)
            approval.approver_name = approver.real_name if approver else '未知'

        # 4. 获取发起人信息
        initiator = User.query.get(instance.initiator_id)
        initiator_info = {
            'id': initiator.id,
            'username': initiator.username,
            'real_name': initiator.real_name,
            'department': initiator.department
        }

        # 5. 获取关联用户信息（如果有）
        related_user_info = None
        if instance.related_user_id:
            related_user = User.query.get(instance.related_user_id)
            if related_user:
                related_user_info = {
                    'id': related_user.id,
                    'username': related_user.username,
                    'real_name': related_user.real_name,
                    'department': related_user.department
                }

        # 6. 传递数据到模板
        return render_template(
            'workflow/instance_detail.html',
            instance=instance,
            definition=definition,
            steps=steps,
            approvals=approvals,
            initiator_info=initiator_info,
            related_user_info=related_user_info
        )

    except Exception as e:
        flash(f'查询流程实例详情失败：{str(e)}', 'danger')
        return redirect(url_for('my_workflow_instances'))

# 审批处理
@app.route('/workflow/approve/<int:record_id>', methods=['GET', 'POST'])
@login_required
def approve_workflow(record_id):
    """处理审批任务"""
    record = ApprovalRecord.query.get_or_404(record_id)
    # 验证权限（只能审批自己的任务）
    if record.approver_id != session['user_id']:
        flash('无权限处理此审批', 'danger')
        return redirect(url_for('pending_approvals'))

    if request.method == 'POST':
        try:
            status = request.form['status']
            record.approval_status = status
            record.comments = request.form['comments']
            record.approved_at = datetime.now()

            instance = record.instance
            current_step = record.step

            if status == '通过':
                # 查找下一步
                next_step = WorkflowStep.query.filter_by(
                    workflow_id=instance.workflow_id,
                    step_order=current_step.step_order + 1
                ).first()

                if next_step:
                    # 进入下一步
                    instance.current_step_id = next_step.id
                    # 创建新审批记录
                    deadline = datetime.now() + timedelta(hours=next_step.timeout_hours)
                    new_approval = ApprovalRecord(
                        instance_id=instance.id,
                        step_id=next_step.id,
                        approver_id=get_approver_by_role(next_step.required_role),
                        deadline=deadline
                    )
                    db.session.add(new_approval)
                else:
                    # 无下一步，流程完成
                    instance.status = '已完成'
                    instance.completed_at = datetime.now()

            else:  # 拒绝
                instance.status = '已拒绝'
                instance.completed_at = datetime.now()

            db.session.commit()
            flash('审批处理完成', 'success')
            return redirect(url_for('pending_approvals'))
        except Exception as e:
            db.session.rollback()
            flash(f'处理失败：{str(e)}', 'danger')
    return render_template('workflow/approve.html', record=record)

@app.route('/pending-approvals', methods=['GET', 'POST'])
@login_required
@manager_required
def pending_approvals():
    if request.method == 'POST':
        # 1. 获取表单数据
        approval_id = request.form.get('approval_id')
        action = request.form.get('action')  # 'approve' 或 'reject'
        comment = request.form.get('comment')
        # 2. 查询审批记录
        approval = Approval.query.get_or_404(approval_id)
        # 3. 校验：避免重复审批
        if approval.status != 'pending':
            flash('该申请已被审批，无法重复操作！', 'danger')
            return redirect(url_for('pending_approvals'))
        # 4. 更新审批状态
        if action == 'approve':
            approval.status = 'approved'
            # 同步更新业务模型状态（如会议审批通过）
            if approval.type == 'meeting':
                meeting = Meeting.query.filter_by(approval_id=approval.id).first()
                if meeting:
                    meeting.approval_status = 'approved'
        else:
            approval.status = 'rejected'
        # 5. 记录审批信息
        approval.approve_user_id = current_user.id
        approval.approve_time = datetime.utcnow
        approval.comment = comment
        db.session.commit()
        flash('审批操作成功！', 'success')
        return redirect(url_for('pending_approvals'))
    # GET方法：展示待审批列表

    pending_approvals = ApprovalRecord.query.filter_by(approval_status='待审批').all()
    return render_template('pending_approvals.html', items=pending_approvals)


# @app.route('/my_workflow_instances')
# @login_required
# def my_workflow_instances():
#     user_id = session['user_id']  # 使用session获取当前用户ID
#     instances = WorkflowInstance.query.filter_by(initiator_id=user_id).all()
#     return render_template('workflow/my_instances.html', instances=instances)


# 辅助函数：获取部门经理ID
def get_department_manager_id(department):
    manager = User.query.filter_by(
        department=department,
        role='manager'
    ).first()
    return manager.id if manager else 1  # 默认管理员


# 辅助函数：根据角色获取审批人
def get_approver_by_role(role):
    # 从user表中查询对应角色的用户（假设user表的role字段存储角色信息）
    approver = User.query.filter_by(role=role).first()
    return approver.id if approver else None

# ========== 会议室管理 ==========
# 申请会议室
@app.route('/meeting/apply', methods=['GET', 'POST'])
@login_required
def meeting_apply():
    # 获取所有可用会议室
    rooms = MeetingRoom.query.filter_by(status='空闲').all()

    if request.method == 'POST':
        room_id = request.form.get('room_id')
        start_time = datetime.fromisoformat(request.form.get('start_time'))
        end_time = datetime.fromisoformat(request.form.get('end_time'))
        reason = request.form.get('reason')
        participants = request.form.get('participants', 0)

        # 验证会议室容量
        room = MeetingRoom.query.get(room_id)
        if participants and int(participants) > room.capacity:
            flash('参与人数超过会议室容纳量', 'danger')
            return render_template('meeting/apply.html', rooms=rooms)

        # 检查时间冲突
        conflicts = MeetingApply.query.filter(
            MeetingApply.room_id == room_id,
            MeetingApply.status != '已拒绝',
            db.or_(
                db.and_(
                    MeetingApply.start_time <= start_time,
                    MeetingApply.end_time >= start_time
                ),
                db.and_(
                    MeetingApply.start_time <= end_time,
                    MeetingApply.end_time >= end_time
                ),
                db.and_(
                    MeetingApply.start_time >= start_time,
                    MeetingApply.end_time <= end_time
                )
            )
        ).first()

        if conflicts:
            flash(f'会议室{room.room_no}在该时间段已被占用', 'danger')
            return render_template('meeting/apply.html', rooms=rooms)

        # 创建申请记录
        new_apply = MeetingApply(
            room_id=room_id,
            user_id=session['user_id'],
            start_time=start_time,
            end_time=end_time,
            reason=reason,
            participants=participants,
            status='待审批'
        )

        db.session.add(new_apply)
        db.session.commit()
        flash('会议室申请已提交，等待审批', 'success')
        return redirect(url_for('my_meeting'))

    return render_template('meeting/apply.html', rooms=rooms)


@app.route('/meeting-approve', methods=['GET', 'POST'])
@manager_required
def meeting_approve():
    if request.method == 'POST':
        apply_id = request.form.get('apply_id')
        status = request.form.get('status')
        remark = request.form.get('remark', '')

        apply = MeetingApply.query.get(apply_id)
        if not apply:
            flash('申请记录不存在', 'danger')
            return redirect(url_for('meeting_approve'))

        # 更新审批信息
        apply.status = status
        apply.approver_id = session['user_id']
        apply.approve_remark = remark
        apply.approve_time = datetime.now()

        # 若批准，更新会议室状态
        if status == '已批准':
            room = MeetingRoom.query.get(apply.room_id)
            if room:
                room.status = '已预约'

        db.session.commit()
        flash(f'已{status}该申请', 'success')
        return redirect(url_for('meeting_approve'))

    #  GET请求：查询待审批申请
    applies = MeetingApply.query.filter_by(status='待审批').all()
    return render_template('meeting/approve.html', applies=applies)


# 我的会议室申请
@app.route('/meeting/my_meeting')
@login_required
def my_meeting():
    user_id = session.get('user_id')
    applies = MeetingApply.query.filter_by(user_id=user_id).order_by(MeetingApply.start_time.desc()).all()
    # 补充会议室名称和审批人名称 - 修复关系访问
    for apply in applies:
        apply.room_name = apply.meeting_room.room_no if apply.meeting_room else '未知'
        if apply.approver_id:
            approver = User.query.get(apply.approver_id)
            apply.approver_name = approver.real_name if approver else '未知'
        else:
            apply.approver_name = '未审批'
    return render_template('meeting/my_meeting.html', applies=applies)


# 会议室冲突检查接口
@app.route('/check-meeting-conflict')
@login_required
def check_meeting_conflict():
    room_id = request.args.get('room_id')
    start = request.args.get('start')
    end = request.args.get('end')

    if not all([room_id, start, end]):
        return jsonify({'conflict': False})

    try:
        start_time = datetime.fromisoformat(start)
        end_time = datetime.fromisoformat(end)
    except ValueError:
        return jsonify({'conflict': False})

    # 检查所选时间段内是否有已批准或待审批的申请
    conflict = MeetingApply.query.filter(
        MeetingApply.room_id == room_id,
        MeetingApply.status.in_(['待审批', '已批准']),
        # 时间重叠条件：(A开始 < B结束) 且 (A结束 > B开始)
        MeetingApply.start_time < end_time,
        MeetingApply.end_time > start_time
    ).first() is not None

    return jsonify({'conflict': conflict})


# 取消会议室申请
@app.route('/cancel-meeting', methods=['POST'])
@login_required
def cancel_meeting():
    apply_id = request.form.get('apply_id')
    apply = MeetingApply.query.filter_by(id=apply_id, user_id=session['user_id']).first()

    if not apply:
        flash('申请记录不存在', 'danger')
        return redirect(url_for('my_meeting'))

    if apply.status != '待审批':
        flash('只能取消待审批的申请', 'warning')
        return redirect(url_for('my_meeting'))

    apply.status = '已取消'
    db.session.commit()
    flash('申请已成功取消', 'success')
    return redirect(url_for('my_meeting'))



# ========== 启动应用 ==========
if __name__ == '__main__':
    init_db()  # 初始化数据库
    app.run(debug=True)

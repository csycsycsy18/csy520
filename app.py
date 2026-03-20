from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from functools import wraps 
import os

app = Flask(__name__)
app.secret_key = 'gym_mega_final_2026'

# --- 数据库配置 ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'gym_pro.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查 Session 中是否有管理员标记
        if not session.get('is_admin'):
            flash("越权访问：请先以管理员账号 (admin) 登录！", "danger")
            return redirect(url_for('user_main'))
        return f(*args, **kwargs)
    return decorated_function
# --- 数据库模型 ---
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), unique=True)
    level = db.Column(db.String(20), default="普通会员")
    expiry_date = db.Column(db.Date, nullable=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.now)
    amount = db.Column(db.Float)
    item_name = db.Column(db.String(50))
    member_name = db.Column(db.String(50)) # 需求：财务需记录购买人
    category = db.Column(db.String(20))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer)
    member_name = db.Column(db.String(50))
    in_time = db.Column(db.DateTime, default=datetime.now)
    out_time = db.Column(db.DateTime, nullable=True)

# 自动处理：高级会员过期检查
def auto_check_expiry():
    today = date.today()
    expired = Member.query.filter(Member.level == "高级会员", Member.expiry_date < today).all()
    for m in expired:
        m.level = "普通会员"
    db.session.commit()

# ================= 用户端 =================

@app.route('/')
def index():
    return redirect(url_for('user_main'))

@app.route('/user/main')
def user_main():
    auto_check_expiry()
    user = Member.query.get(session['member_id']) if 'member_id' in session else None
    return render_template('user_main.html', user=user)

@app.route('/user/login', methods=['POST'])
def user_login():
    phone = request.form.get('phone')
    # 【新增逻辑】：判定管理员登录
    if phone == 'admin':
        session['is_admin'] = True  # 赋予管理员权限
        session['member_id'] = None # 管理员不需要关联具体的会员ID
        flash("管理员登录成功！已开启管理权限。", "success")
        return redirect(url_for('admin_dashboard')) # 登录后直接跳转管理后台
    user = Member.query.filter_by(phone=phone).first()
    if user:
        session['member_id'] = user.id
        flash(f"欢迎回来，{user.name}！", "success")
    else:
        flash("未找到该手机号，请先注册。", "danger")
    return redirect(url_for('user_main'))

@app.route('/user/register', methods=['POST'])
def user_register():
    name, phone = request.form.get('name'), request.form.get('phone')
    if Member.query.filter_by(phone=phone).first():
        flash("手机号已注册，请直接登录。", "warning")
    else:
        new_m = Member(name=name, phone=phone, level="普通会员")
        db.session.add(new_m)
        db.session.commit()
        session['member_id'] = new_m.id
        flash("注册成功！", "success")
    return redirect(url_for('user_main'))

@app.route('/user/upgrade', methods=['POST'])
def user_upgrade():
    user = Member.query.get(session.get('member_id'))
    if user:
        today = date.today()
        
        # 【核心修复逻辑】：检查是否已有尚未过期的有效时长
        if user.expiry_date and user.expiry_date > today:
            # 如果还没过期，在原有效期基础上累加 365 天
            user.expiry_date = user.expiry_date + timedelta(days=365)
            action_name = "续费高级会员"
        else:
            # 如果是首次升级或已过期，从今天起算 365 天
            user.expiry_date = today + timedelta(days=365)
            action_name = "升级高级会员"
            
        user.level = "高级会员"
        
        # 记录财务流水时区分是升级还是续费
        db.session.add(Transaction(amount=1688.0, item_name=action_name, member_name=user.name, category="会员业务"))
        db.session.commit()
        
        # 友好的弹窗提示，展示具体的到期时间
        flash(f"{action_name}成功！您的会员权限已延期至 {user.expiry_date.strftime('%Y-%m-%d')}。", "warning")
        
    return redirect(url_for('user_main'))

@app.route('/user/action', methods=['POST'])
def user_action():
    user = Member.query.get(session.get('member_id'))
    if not user or user.level != "高级会员":
        flash("该功能仅限高级会员使用！", "danger")
        return redirect(url_for('user_main'))

    action = request.form.get('action')
    price = float(request.form.get('price', 0))

    if action == "签到":
        # 【新增逻辑】：检查是否已经在馆内（有入场没出场）
        already_in = Attendance.query.filter_by(member_id=user.id, out_time=None).first()
        if already_in:
            flash(f"您当前已在馆内，请勿重复签到！(入场时间: {already_in.in_time.strftime('%H:%M')})", "warning")
            return redirect(url_for('user_main'))
        
        db.session.add(Attendance(member_id=user.id, member_name=user.name))
        flash("签到成功，祝您健身愉快！", "success")

    elif action == "签出":
        # 【新增逻辑】：检查是否真的在馆内（找到那个没出场的记录）
        log = Attendance.query.filter_by(member_id=user.id, out_time=None).first()
        if log:
            log.out_time = datetime.now()
            flash("签出成功，期待下次再见！", "info")
        else:
            # 如果没找到没签出的记录，说明他根本没签到
            flash("您当前不在馆内或已签出，请先签到！", "danger")
            return redirect(url_for('user_main'))
            
    else:
        # 办理其他业务（私教、补剂等）
        db.session.add(Transaction(amount=price, item_name=action, member_name=user.name, category="增值业务"))
        flash(f"{action} 办理成功！", "success")
    
    db.session.commit()
    return redirect(url_for('user_main'))

@app.route('/user/logout')
def user_logout():
    session.clear()
    return redirect(url_for('user_main'))

# ================= 管理端 =================


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查 session 中是否有我们刚才设置的 is_admin 标记
        if not session.get('is_admin'):
            flash("越权访问：请先以管理员账号 (admin) 登录！", "danger")
            return redirect(url_for('user_main'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # 统计数据
    in_total = Attendance.query.count()
    out_total = Attendance.query.filter(Attendance.out_time != None).count()
    return render_template('admin_dashboard.html', in_total=in_total, out_total=out_total)

@app.route('/admin/clear_attendance')
@admin_required
def clear_attendance():
    Attendance.query.delete()
    db.session.commit()
    flash("签到记录已全部清除", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/members')
@admin_required
def admin_members():
    members = Member.query.all()
    n_count = Member.query.filter_by(level="普通会员").count()
    s_count = Member.query.filter_by(level="高级会员").count()
    return render_template('admin_members.html', members=members, n_count=n_count, s_count=s_count)

@app.route('/admin/add_member', methods=['POST'])
@admin_required
def admin_add_member():
    name, phone, level = request.form.get('name'), request.form.get('phone'), request.form.get('level')
    expiry = date.today() + timedelta(days=365) if level == "高级会员" else None
    db.session.add(Member(name=name, phone=phone, level=level, expiry_date=expiry))
    db.session.commit()
    return redirect(url_for('admin_members'))

@app.route('/admin/member/delete/<int:id>')
@admin_required
def delete_member(id):
    m = Member.query.get(id)
    if m: db.session.delete(m); db.session.commit()
    return redirect(url_for('admin_members'))

@app.route('/admin/member/delete_all')
@admin_required
def delete_all_members():
    Member.query.delete()
    db.session.commit()
    return redirect(url_for('admin_members'))

@app.route('/admin/finance')
@admin_required
def admin_finance():
    trans = Transaction.query.order_by(Transaction.date.desc()).all()
    total_income = db.session.query(db.func.sum(Transaction.amount)).scalar() or 0
    return render_template('admin_finance.html', trans=trans, total_income=total_income)

@app.route('/admin/finance/delete/<int:id>')
@admin_required
def delete_finance(id):
    t = Transaction.query.get(id)
    if t: db.session.delete(t); db.session.commit()
    return redirect(url_for('admin_finance'))

# 将这段代码添加到 app.py 的“管理员端路由”部分
@app.route('/admin/finance/clear_all')
@admin_required
def clear_all_finance():
    Transaction.query.delete()
    db.session.commit()
    flash("所有对账记录已清空", "info")
    return redirect(url_for('admin_finance'))

@app.route('/admin/finance/delete_all')
@admin_required
def delete_all_finance():
    Transaction.query.delete()
    db.session.commit()
    return redirect(url_for('admin_finance'))

if __name__ == '__main__':
    # 生产环境不要开启 debug=True
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))# 设置你的名字（可以是英文名或拼音）


from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import os

app = Flask(__name__)
app.secret_key = 'gym_mega_final_2026'

# --- 数据库配置 ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'gym_pro.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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
        user.level = "高级会员"
        user.expiry_date = date.today() + timedelta(days=365)
        db.session.add(Transaction(amount=1688.0, item_name="升级高级会员", member_name=user.name, category="会员业务"))
        db.session.commit()
        flash("升级成功！您已获得全部权限。", "warning")
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
        db.session.add(Attendance(member_id=user.id, member_name=user.name))
        flash("签到成功！", "success")
    elif action == "签出":
        log = Attendance.query.filter_by(member_id=user.id, out_time=None).first()
        if log: log.out_time = datetime.now()
        flash("签出成功！", "info")
    else:
        db.session.add(Transaction(amount=price, item_name=action, member_name=user.name, category="增值业务"))
        flash(f"{action} 办理成功！", "success")
    
    db.session.commit()
    return redirect(url_for('user_main'))

@app.route('/user/logout')
def user_logout():
    session.clear()
    return redirect(url_for('user_main'))

# ================= 管理端 =================

@app.route('/admin/dashboard')
def admin_dashboard():
    # 统计数据
    in_total = Attendance.query.count()
    out_total = Attendance.query.filter(Attendance.out_time != None).count()
    return render_template('admin_dashboard.html', in_total=in_total, out_total=out_total)

@app.route('/admin/clear_attendance')
def clear_attendance():
    Attendance.query.delete()
    db.session.commit()
    flash("签到记录已全部清除", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/members')
def admin_members():
    members = Member.query.all()
    n_count = Member.query.filter_by(level="普通会员").count()
    s_count = Member.query.filter_by(level="高级会员").count()
    return render_template('admin_members.html', members=members, n_count=n_count, s_count=s_count)

@app.route('/admin/add_member', methods=['POST'])
def admin_add_member():
    name, phone, level = request.form.get('name'), request.form.get('phone'), request.form.get('level')
    expiry = date.today() + timedelta(days=365) if level == "高级会员" else None
    db.session.add(Member(name=name, phone=phone, level=level, expiry_date=expiry))
    db.session.commit()
    return redirect(url_for('admin_members'))

@app.route('/admin/member/delete/<int:id>')
def delete_member(id):
    m = Member.query.get(id)
    if m: db.session.delete(m); db.session.commit()
    return redirect(url_for('admin_members'))

@app.route('/admin/member/delete_all')
def delete_all_members():
    Member.query.delete()
    db.session.commit()
    return redirect(url_for('admin_members'))

@app.route('/admin/finance')
def admin_finance():
    trans = Transaction.query.order_by(Transaction.date.desc()).all()
    total_income = db.session.query(db.func.sum(Transaction.amount)).scalar() or 0
    return render_template('admin_finance.html', trans=trans, total_income=total_income)

@app.route('/admin/finance/delete/<int:id>')
def delete_finance(id):
    t = Transaction.query.get(id)
    if t: db.session.delete(t); db.session.commit()
    return redirect(url_for('admin_finance'))

# 将这段代码添加到 app.py 的“管理员端路由”部分
@app.route('/admin/finance/clear_all')
def clear_all_finance():
    Transaction.query.delete()
    db.session.commit()
    flash("所有对账记录已清空", "info")
    return redirect(url_for('admin_finance'))

@app.route('/admin/finance/delete_all')
def delete_all_finance():
    Transaction.query.delete()
    db.session.commit()
    return redirect(url_for('admin_finance'))

if __name__ == '__main__':
    # 生产环境不要开启 debug=True
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))# 设置你的名字（可以是英文名或拼音）


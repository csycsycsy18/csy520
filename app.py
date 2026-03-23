from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'gym_mega_final_2026'

# --- 数据库配置 ---
basedir = os.path.abspath(os.path.dirname(__file__))
# 关键修改：优先读取环境变量中的 DATABASE_URL
# 如果读取不到（比如在本地开发），则使用原来的 SQLite
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    # 为了兼容 SQLAlchemy 2.0，需要将 postgres:// 替换为 postgresql://
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'gym_pro.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# ================= 通用装饰器 =================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('member_id'):
            flash("请先登录或注册会员！", "warning")
            return redirect(url_for('user_main'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash("越权访问：请先以管理员账号 (admin) 登录！", "danger")
            return redirect(url_for('user_main'))
        return f(*args, **kwargs)
    return decorated_function


# ================= 业务配置 =================
BUSINESS_PRICING = {
    "高级会员": {
        "日卡": {"price": 39, "days": 1},
        "月卡": {"price": 199, "days": 30},
        "季卡": {"price": 499, "days": 90},
        "年卡": {"price": 1688, "days": 365},
    },
    "私教课程": {
        "日卡": {"price": 199, "days": 1},
        "月卡": {"price": 1299, "days": 30},
        "季卡": {"price": 3299, "days": 90},
        "年卡": {"price": 9999, "days": 365},
    },
    "体操课": {
        "日卡": {"price": 59, "days": 1},
        "月卡": {"price": 399, "days": 30},
        "季卡": {"price": 999, "days": 90},
        "年卡": {"price": 3599, "days": 365},
    }
}

SUPPLEMENT_PRICING = {
    "乳清蛋白粉": 299,
    "肌酸": 129,
    "氮泵": 169,
    "支链氨基酸BCAA": 159,
    "左旋肉碱": 139,
    "维生素复合片": 89
}


# ================= 数据库模型 =================
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), unique=True)
    level = db.Column(db.String(20), default="普通会员")
    expiry_date = db.Column(db.Date, nullable=True)

    # 个人资料
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    height = db.Column(db.Float, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    birthday = db.Column(db.Date, nullable=True)
    profile_note = db.Column(db.String(200), nullable=True)

    # 课程有效期
    private_course_expiry = db.Column(db.Date, nullable=True)
    gymnastics_expiry = db.Column(db.Date, nullable=True)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.now)
    amount = db.Column(db.Float)
    item_name = db.Column(db.String(50))
    member_name = db.Column(db.String(50))
    category = db.Column(db.String(20))


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer)
    member_name = db.Column(db.String(50))
    in_time = db.Column(db.DateTime, default=datetime.now)
    out_time = db.Column(db.DateTime, nullable=True)


# ================= 工具函数 =================
def auto_check_expiry():
    today = date.today()
    expired = Member.query.filter(Member.level == "高级会员", Member.expiry_date < today).all()
    for m in expired:
        m.level = "普通会员"
    db.session.commit()


def is_active_vip(user):
    today = date.today()
    return user and user.level == "高级会员" and user.expiry_date and user.expiry_date >= today


# ================= 用户端 =================
@app.route('/')
def index():
    return redirect(url_for('user_main'))


@app.route('/user/main')
def user_main():
    auto_check_expiry()
    user = Member.query.get(session['member_id']) if session.get('member_id') else None
    vip_active = is_active_vip(user) if user else False
    return render_template('user_main.html', user=user, vip_active=vip_active)


@app.route('/user/login', methods=['POST'])
def user_login():
    phone = request.form.get('phone')

    if phone == 'admin':
        session['is_admin'] = True
        session['member_id'] = None
        flash("管理员登录成功！已开启管理权限。", "success")
        return redirect(url_for('user_main'))

    user = Member.query.filter_by(phone=phone).first()
    if user:
        session['member_id'] = user.id
        session.pop('is_admin', None)
        flash(f"欢迎回来，{user.name}！", "success")
    else:
        flash("未找到该手机号，请先注册。", "danger")
    return redirect(url_for('user_main'))


@app.route('/user/register', methods=['POST'])
def user_register():
    name = request.form.get('name')
    phone = request.form.get('phone')

    if Member.query.filter_by(phone=phone).first():
        flash("手机号已注册，请直接登录。", "warning")
    else:
        new_m = Member(name=name, phone=phone, level="普通会员")
        db.session.add(new_m)
        db.session.commit()
        session['member_id'] = new_m.id
        session.pop('is_admin', None)
        flash("注册成功！", "success")
    return redirect(url_for('user_main'))


@app.route('/user/profile/update', methods=['POST'])
@login_required
def update_profile():
    user = Member.query.get(session.get('member_id'))
    if not user:
        flash("请先登录！", "danger")
        return redirect(url_for('user_main'))

    user.name = request.form.get('name', user.name)
    user.age = int(request.form.get('age')) if request.form.get('age') else None
    user.gender = request.form.get('gender') or None
    user.height = float(request.form.get('height')) if request.form.get('height') else None
    user.weight = float(request.form.get('weight')) if request.form.get('weight') else None
    user.profile_note = request.form.get('profile_note') or None

    birthday_str = request.form.get('birthday')
    if birthday_str:
        try:
            user.birthday = datetime.strptime(birthday_str, '%Y-%m-%d').date()
        except:
            pass
    else:
        user.birthday = None

    db.session.commit()
    flash("个人资料已更新！", "success")
    return redirect(request.referrer or url_for('user_main'))


@app.route('/user/action', methods=['POST'])
@login_required
def user_action():
    auto_check_expiry()
    user = Member.query.get(session.get('member_id'))

    if not is_active_vip(user):
        flash("该功能仅限有效高级会员使用！", "danger")
        return redirect(url_for('user_main'))

    action = request.form.get('action')

    if action == "签到":
        already_in = Attendance.query.filter_by(member_id=user.id, out_time=None).first()
        if already_in:
            flash(f"您当前已在馆内，请勿重复签到！(入场时间: {already_in.in_time.strftime('%H:%M')})", "warning")
            return redirect(url_for('user_main'))

        db.session.add(Attendance(member_id=user.id, member_name=user.name))
        flash("签到成功，祝您健身愉快！", "success")

    elif action == "签出":
        log = Attendance.query.filter_by(member_id=user.id, out_time=None).first()
        if log:
            log.out_time = datetime.now()
            flash("签出成功，期待下次再见！", "info")
        else:
            flash("您当前不在馆内或已签出，请先签到！", "danger")
            return redirect(url_for('user_main'))

    db.session.commit()
    return redirect(url_for('user_main'))


# ======== 业务办理 ========
@app.route('/user/business')
@login_required
def user_business():
    auto_check_expiry()
    user = Member.query.get(session.get('member_id'))
    vip_active = is_active_vip(user)
    return render_template(
        'user_business.html',
        user=user,
        vip_active=vip_active,
        business_pricing=BUSINESS_PRICING
    )


@app.route('/user/business/submit', methods=['POST'])
@login_required
def user_business_submit():
    auto_check_expiry()
    user = Member.query.get(session.get('member_id'))

    biz_type = request.form.get('biz_type')
    plan = request.form.get('plan')

    if biz_type not in BUSINESS_PRICING or plan not in BUSINESS_PRICING[biz_type]:
        flash("办理参数错误，请重新选择。", "danger")
        return redirect(url_for('user_business'))

    config = BUSINESS_PRICING[biz_type][plan]
    price = config["price"]
    days = config["days"]

    # 高级会员
    if biz_type == "高级会员":
        today = date.today()

        if user.expiry_date and user.expiry_date >= today and user.level == "高级会员":
            user.expiry_date = user.expiry_date + timedelta(days=days)
            action_name = f"续费高级会员-{plan}"
        else:
            user.expiry_date = today + timedelta(days=days)
            action_name = f"开通高级会员-{plan}"

        user.level = "高级会员"

        db.session.add(Transaction(
            amount=price,
            item_name=action_name,
            member_name=user.name,
            category="会员业务"
        ))
        db.session.commit()
        flash(f"{action_name}成功！到期时间：{user.expiry_date.strftime('%Y-%m-%d')}", "success")
        return redirect(url_for('user_main'))

    # 私教课程：仅高级会员
    elif biz_type == "私教课程":
        if not is_active_vip(user):
            flash("私教课程仅限有效高级会员办理，请先开通高级会员！", "danger")
            return redirect(url_for('user_business'))

        today = date.today()
        if user.private_course_expiry and user.private_course_expiry >= today:
            user.private_course_expiry = user.private_course_expiry + timedelta(days=days)
        else:
            user.private_course_expiry = today + timedelta(days=days)

        db.session.add(Transaction(
            amount=price,
            item_name=f"私教课程-{plan}",
            member_name=user.name,
            category="课程业务"
        ))
        db.session.commit()
        flash(f"私教课程 {plan} 办理成功！课程有效期至 {user.private_course_expiry.strftime('%Y-%m-%d')}", "success")
        return redirect(url_for('user_business'))

    # 体操课：仅高级会员
    elif biz_type == "体操课":
        if not is_active_vip(user):
            flash("体操课程仅限有效高级会员办理，请先开通高级会员！", "danger")
            return redirect(url_for('user_business'))

        today = date.today()
        if user.gymnastics_expiry and user.gymnastics_expiry >= today:
            user.gymnastics_expiry = user.gymnastics_expiry + timedelta(days=days)
        else:
            user.gymnastics_expiry = today + timedelta(days=days)

        db.session.add(Transaction(
            amount=price,
            item_name=f"体操课-{plan}",
            member_name=user.name,
            category="课程业务"
        ))
        db.session.commit()
        flash(f"体操课 {plan} 办理成功！课程有效期至 {user.gymnastics_expiry.strftime('%Y-%m-%d')}", "success")
        return redirect(url_for('user_business'))

    flash("未知业务类型。", "danger")
    return redirect(url_for('user_business'))


# ======== 补品购买 ========
@app.route('/user/supplements')
@login_required
def user_supplements():
    user = Member.query.get(session.get('member_id'))
    vip_active = is_active_vip(user)
    return render_template(
        'user_supplements.html',
        user=user,
        vip_active=vip_active,
        supplement_pricing=SUPPLEMENT_PRICING
    )


@app.route('/user/supplements/buy', methods=['POST'])
@login_required
def buy_supplement():
    user = Member.query.get(session.get('member_id'))
    item_name = request.form.get('item_name')
    qty = int(request.form.get('qty', 1))

    if item_name not in SUPPLEMENT_PRICING:
        flash("商品不存在！", "danger")
        return redirect(url_for('user_supplements'))

    if qty < 1:
        flash("购买数量不能小于 1！", "danger")
        return redirect(url_for('user_supplements'))

    unit_price = SUPPLEMENT_PRICING[item_name]
    total_price = unit_price * qty

    db.session.add(Transaction(
        amount=total_price,
        item_name=f"{item_name} x{qty}",
        member_name=user.name,
        category="补品销售"
    ))
    db.session.commit()

    flash(f"购买成功：{item_name} × {qty}，合计 ¥{total_price}", "success")
    return redirect(url_for('user_supplements'))


@app.route('/user/logout')
def user_logout():
    session.clear()
    return redirect(url_for('user_main'))


# ================= 管理端 =================
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
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


@app.route('/admin/member/<int:id>/json')
@admin_required
def admin_member_json(id):
    m = Member.query.get_or_404(id)
    return jsonify({
        "id": m.id,
        "name": m.name,
        "phone": m.phone,
        "level": m.level,
        "expiry_date": m.expiry_date.strftime('%Y-%m-%d') if m.expiry_date else "--",
        "age": m.age or "",
        "gender": m.gender or "",
        "height": m.height or "",
        "weight": m.weight or "",
        "birthday": m.birthday.strftime('%Y-%m-%d') if m.birthday else "",
        "profile_note": m.profile_note or "",
        "private_course_expiry": m.private_course_expiry.strftime('%Y-%m-%d') if m.private_course_expiry else "--",
        "gymnastics_expiry": m.gymnastics_expiry.strftime('%Y-%m-%d') if m.gymnastics_expiry else "--"
    })


@app.route('/admin/add_member', methods=['POST'])
@admin_required
def admin_add_member():
    name = request.form.get('name')
    phone = request.form.get('phone')
    level = request.form.get('level')
    expiry = date.today() + timedelta(days=365) if level == "高级会员" else None

    db.session.add(Member(name=name, phone=phone, level=level, expiry_date=expiry))
    db.session.commit()
    return redirect(url_for('admin_members'))


@app.route('/admin/member/delete/<int:id>')
@admin_required
def delete_member(id):
    m = Member.query.get(id)
    if m:
        db.session.delete(m)
        db.session.commit()
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
    if t:
        db.session.delete(t)
        db.session.commit()
    return redirect(url_for('admin_finance'))


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
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

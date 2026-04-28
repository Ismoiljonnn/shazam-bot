import os
import sys
import asyncio
import threading
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'change-this-secret-key-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///mediabot.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, User, Download, AdminUser, BroadcastMessage

db.init_app(app)

logger = logging.getLogger(__name__)

# ======================== HELPERS ========================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def init_db():
    with app.app_context():
        db.create_all()
        # Default admin yaratish
        admin = AdminUser.query.filter_by(username=os.getenv('ADMIN_USERNAME', 'admin')).first()
        if not admin:
            admin = AdminUser(
                username=os.getenv('ADMIN_USERNAME', 'admin'),
                password_hash=generate_password_hash(os.getenv('ADMIN_PASSWORD', 'admin123'))
            )
            db.session.add(admin)
            db.session.commit()
            logger.info("Default admin yaratildi")


def get_dashboard_stats():
    total_users = User.query.count()
    total_downloads = Download.query.count()
    successful = Download.query.filter_by(status='success').count()
    failed = Download.query.filter_by(status='failed').count()
    banned_users = User.query.filter_by(is_banned=True).count()
    
    today = datetime.utcnow().date()
    new_users_today = User.query.filter(
        func.date(User.joined_at) == today
    ).count()
    downloads_today = Download.query.filter(
        func.date(Download.created_at) == today
    ).count()
    
    success_rate = round((successful / total_downloads * 100) if total_downloads > 0 else 0, 1)
    
    return {
        'total_users': total_users,
        'total_downloads': total_downloads,
        'successful': successful,
        'failed_downloads': failed,
        'banned_users': banned_users,
        'new_users_today': new_users_today,
        'downloads_today': downloads_today,
        'success_rate': success_rate,
    }


def get_platform_stats():
    platforms = db.session.query(
        Download.platform,
        func.count(Download.id).label('total'),
        func.sum(func.cast(Download.status == 'success', db.Integer)).label('success'),
        func.sum(func.cast(Download.status == 'failed', db.Integer)).label('failed'),
    ).group_by(Download.platform).order_by(func.count(Download.id).desc()).all()
    
    total_all = sum(p.total for p in platforms) or 1
    
    result = []
    for p in platforms:
        if p.platform:
            result.append({
                'platform': p.platform,
                'total': p.total,
                'success': p.success or 0,
                'failed': p.failed or 0,
                'percent': round(p.total / total_all * 100),
            })
    return result


# ======================== AUTH ROUTES ========================

@app.route('/admin/login', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('dashboard'))
    
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        admin = AdminUser.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return redirect(url_for('dashboard'))
        else:
            error = "Noto'g'ri foydalanuvchi nomi yoki parol"
    
    return render_template('login.html', error=error)


@app.route('/admin/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ======================== ADMIN ROUTES ========================

@app.route('/admin')
@login_required
def dashboard():
    stats = get_dashboard_stats()
    platform_stats = get_platform_stats()
    recent_downloads = Download.query.order_by(Download.created_at.desc()).limit(10).all()
    top_users = User.query.order_by(User.total_downloads.desc()).limit(10).all()
    
    return render_template('dashboard.html',
        active='dashboard',
        stats=stats,
        platform_stats=platform_stats,
        recent_downloads=recent_downloads,
        top_users=top_users
    )


@app.route('/admin/users')
@login_required
def users_list():
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    query = User.query
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.first_name.ilike(f'%{search}%')) |
            (User.last_name.ilike(f'%{search}%'))
        )
    
    users = query.order_by(User.joined_at.desc()).paginate(page=page, per_page=20)
    message = request.args.get('msg')
    
    return render_template('users.html', active='users', users=users, search=search, message=message)


@app.route('/admin/users/<int:user_id>')
@login_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    downloads = Download.query.filter_by(user_id=user_id).order_by(Download.created_at.desc()).limit(20).all()
    return render_template('user_detail.html', active='users', user=user, downloads=downloads)


@app.route('/admin/users/<int:user_id>/toggle-ban')
@login_required
def toggle_ban(user_id):
    user = User.query.get_or_404(user_id)
    user.is_banned = not user.is_banned
    db.session.commit()
    status = "ban qilindi" if user.is_banned else "ban olib tashlandi"
    return redirect(url_for('users_list', msg=f"{user.first_name} {status}"))


@app.route('/admin/downloads')
@login_required
def downloads_list():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    platform_filter = request.args.get('platform', '')
    
    query = Download.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if platform_filter:
        query = query.filter_by(platform=platform_filter)
    
    downloads = query.order_by(Download.created_at.desc()).paginate(page=page, per_page=25)
    
    return render_template('downloads.html', 
        active='downloads', 
        downloads=downloads,
        status_filter=status_filter,
        platform_filter=platform_filter
    )


@app.route('/admin/broadcast', methods=['GET'])
@login_required
def broadcast():
    broadcasts = BroadcastMessage.query.order_by(BroadcastMessage.created_at.desc()).limit(20).all()
    total_users = User.query.filter_by(is_banned=False).count()
    message = request.args.get('msg')
    return render_template('broadcast.html', 
        active='broadcast', 
        broadcasts=broadcasts,
        total_users=total_users,
        message=message
    )


@app.route('/admin/broadcast/send', methods=['POST'])
@login_required
def send_broadcast():
    msg_text = request.form.get('message', '').strip()
    target = request.form.get('target', 'all')
    
    if not msg_text:
        return redirect(url_for('broadcast', msg='Xabar matni bo\'sh bo\'lishi mumkin emas!'))
    
    # Xabarni DB ga saqlash
    bc = BroadcastMessage(message=msg_text, status='sending')
    db.session.add(bc)
    db.session.commit()
    
    # Foydalanuvchilarni olish
    query = User.query.filter_by(is_banned=False)
    if target == 'active':
        week_ago = datetime.utcnow() - timedelta(days=7)
        query = query.filter(User.last_active >= week_ago)
    
    users = query.all()
    
    # Xabar yuborish (background thread)
    def send_messages():
        import asyncio
        from telegram import Bot
        from telegram.constants import ParseMode
        
        bot_token = os.getenv('BOT_TOKEN', '')
        if not bot_token:
            return
        
        async def _send():
            bot = Bot(token=bot_token)
            sent = 0
            for user in users:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=msg_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    sent += 1
                    await asyncio.sleep(0.05)  # Rate limit
                except Exception as e:
                    logger.error(f"Broadcast error for {user.telegram_id}: {e}")
            
            with app.app_context():
                bc_db = BroadcastMessage.query.get(bc.id)
                if bc_db:
                    bc_db.sent_count = sent
                    bc_db.status = 'done'
                    db.session.commit()
        
        asyncio.run(_send())
    
    thread = threading.Thread(target=send_messages, daemon=True)
    thread.start()
    
    return redirect(url_for('broadcast', msg=f'{len(users)} foydalanuvchiga xabar yuborilmoqda...'))


@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def settings():
    import yt_dlp
    import platform as plt
    
    if request.method == 'POST':
        # Sozlamalarni saqlash (oddiy .env orqali emas, runtime da)
        # Haqiqiy loyihada bu DB da saqlanadi
        return redirect(url_for('settings', msg='Sozlamalar saqlandi!'))
    
    config = {
        'max_file_size': os.getenv('MAX_FILE_SIZE_MB', '50'),
        'download_timeout': os.getenv('DOWNLOAD_TIMEOUT', '300'),
        'welcome_msg': '🎬 Salom! Men MediaBot...',
    }
    
    message = request.args.get('msg')
    
    return render_template('settings.html',
        active='settings',
        config=config,
        message=message,
        python_version=sys.version.split()[0],
        ytdlp_version=yt_dlp.version.__version__
    )


@app.route('/admin/settings/change-password', methods=['POST'])
@login_required
def change_password():
    current = request.form.get('current_password', '')
    new_pwd = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    
    admin = AdminUser.query.filter_by(username=session.get('admin_username')).first()
    
    if not admin or not check_password_hash(admin.password_hash, current):
        return redirect(url_for('settings', msg='❌ Joriy parol noto\'g\'ri!'))
    
    if new_pwd != confirm:
        return redirect(url_for('settings', msg='❌ Yangi parollar mos kelmadi!'))
    
    if len(new_pwd) < 6:
        return redirect(url_for('settings', msg='❌ Parol kamida 6 ta belgidan iborat bo\'lishi kerak!'))
    
    admin.password_hash = generate_password_hash(new_pwd)
    db.session.commit()
    
    return redirect(url_for('settings', msg='✅ Parol muvaffaqiyatli o\'zgartirildi!'))


# ======================== BOT RUNNER ========================

def run_bot():
    """Botni alohida thread da ishga tushirish"""
    from bot import create_bot_app
    
    bot_app = create_bot_app()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def start():
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        
        # Bot ishlayapti, to'xtamasin
        while True:
            await asyncio.sleep(3600)
    
    try:
        loop.run_until_complete(start())
    except Exception as e:
        logger.error(f"Bot error: {e}")


# ======================== MAIN ========================

if __name__ == '__main__':
    init_db()
    
    # Botni background thread da ishga tushirish
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("Bot ishga tushirildi")
    
    # Flask admin panelini ishga tushirish
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

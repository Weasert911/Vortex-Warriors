from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import qrcode
import os
import uuid
import secrets
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'vw-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db = SQLAlchemy(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# CSRF Protection
def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(16)
    return session['_csrf_token']

@app.before_request
def before_request():
    if request.endpoint and 'static' not in request.endpoint:
        generate_csrf_token()

def csrf_protect(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'DELETE'):
            token = session.get('_csrf_token')
            form_token = request.form.get('_csrf_token')
            if not token or token != form_token:
                abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Make csrf_token available to all templates
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token)

# Database Models
class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game = db.Column(db.String(100), nullable=False)
    time = db.Column(db.DateTime, nullable=False)
    entry_fee = db.Column(db.Integer, nullable=False)
    total_slots = db.Column(db.Integer, nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='upcoming')  # upcoming, live, completed, cancelled
    room_id = db.Column(db.String(100))
    room_password = db.Column(db.String(100))
    discord_link = db.Column(db.String(500))
    stream_link = db.Column(db.String(500))
    prize = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    uid = db.Column(db.String(100), nullable=False)
    discord = db.Column(db.String(200), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, rejected
    utr = db.Column(db.String(100))  # UTR/Transaction ID
    screenshot_path = db.Column(db.String(500))  # Payment screenshot
    pass_id = db.Column(db.String(50), unique=True)
    slot_assigned = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    match = db.relationship('Match', backref=db.backref('players', lazy=True))

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    upi_id = db.Column(db.String(200))
    qr_path = db.Column(db.String(500))

# Routes
@app.route('/')
def index():
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())
    matches = Match.query.filter(
        Match.time >= start,
        Match.time <= end,
        Match.status.in_(['upcoming', 'live'])
    ).order_by(Match.time).all()
    pass_id = request.args.get('pass_id')
    return render_template('index.html', matches=matches, pass_id=pass_id)

@app.route('/join/<int:match_id>')
def join_form(match_id):
    match = Match.query.get_or_404(match_id)
    if match.available_slots <= 0 or match.status not in ['upcoming', 'live']:
        flash('Match not available!', 'error')
        return redirect(url_for('index'))
    return render_template('form.html', match=match)

@app.route('/register', methods=['POST'])
@csrf_protect
def register():
    name = request.form.get('name')
    uid = request.form.get('uid')
    discord = request.form.get('discord')
    match_id = request.form.get('match_id')
    
    if not all([name, uid, discord, match_id]):
        flash('All fields are required!', 'error')
        return redirect(url_for('index'))
    
    match = Match.query.get(match_id)
    if not match or match.status not in ['upcoming', 'live'] or match.available_slots <= 0:
        flash('Match not available!', 'error')
        return redirect(url_for('index'))
    
    existing = Player.query.filter_by(uid=uid, match_id=match_id).first()
    if existing:
        flash('This UID is already registered for this match!', 'error')
        return redirect(url_for('join_form', match_id=match_id))
    
    player = Player(
        name=name,
        uid=uid,
        discord=discord,
        match_id=match_id,
        payment_status='pending'
    )
    db.session.add(player)
    db.session.commit()
    
    return redirect(url_for('payment', player_id=player.id))

@app.route('/payment/<int:player_id>')
def payment(player_id):
    player = Player.query.get_or_404(player_id)
    match = Match.query.get(player.match_id)
    settings = Settings.query.first()
    return render_template('payment.html', player=player, match=match, settings=settings)

@app.route('/confirm-payment/<int:player_id>', methods=['POST'])
@csrf_protect
def confirm_payment(player_id):
    player = Player.query.get_or_404(player_id)
    
    if player.payment_status != 'pending':
        flash('Payment already processed!', 'error')
        return redirect(url_for('index'))
    
    match = Match.query.get(player.match_id)
    if not match or match.status not in ['upcoming', 'live'] or match.available_slots <= 0:
        flash('Match not available for registration!', 'error')
        return redirect(url_for('index'))
    
    # Get UTR/Transaction ID
    utr = request.form.get('utr', '').strip()
    if not utr:
        flash('Please provide Transaction/UTR ID!', 'error')
        return redirect(url_for('payment', player_id=player_id))
    
    # Basic UTR validation (minimum 6 characters)
    if len(utr) < 6:
        flash('Invalid Transaction ID. Please check and try again.', 'error')
        return redirect(url_for('payment', player_id=player_id))
    
    # Check if UTR already used (prevent duplicate payments)
    existing_utr = Player.query.filter_by(utr=utr).first()
    if existing_utr:
        flash('This Transaction ID has already been used!', 'error')
        return redirect(url_for('payment', player_id=player_id))
    
    # Handle screenshot upload
    if 'screenshot' in request.files:
        file = request.files['screenshot']
        if file and file.filename:
            # Check file extension
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
                filename = secure_filename(f"pay_{uuid.uuid4()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                player.screenshot_path = f"uploads/{filename}"
            else:
                flash('Invalid file type. Only images allowed (PNG, JPG, JPEG, GIF, WEBP).', 'error')
                return redirect(url_for('payment', player_id=player_id))
    
    # Generate unique pass ID immediately after payment proof submission
    if not player.pass_id:
        # Create unique pass ID: VW-XXXX-GAME
        pass_id = f"VW-{uuid.uuid4().hex[:4].upper()}-{match.game.replace(' ', '')[:4].upper()}"
        # Ensure uniqueness (though UUID makes collisions extremely unlikely)
        while Player.query.filter_by(pass_id=pass_id).first():
            pass_id = f"VW-{uuid.uuid4().hex[:4].upper()}-{match.game.replace(' ', '')[:4].upper()}"
        player.pass_id = pass_id
    
    # Save UTR but keep status as pending (admin must approve)
    player.utr = utr
    db.session.commit()
    
    flash('Payment details submitted! Your Pass ID is: ' + player.pass_id + '. Please wait for admin approval.', 'success')
    return redirect(url_for('index', pass_id=player.pass_id))

@app.route('/portal')
def portal():
    pass_id = request.args.get('pass')
    if not pass_id:
        return redirect(url_for('index'))
    
    player = Player.query.filter_by(pass_id=pass_id).first_or_404()
    match = Match.query.get(player.match_id)
    
    return render_template('portal.html', player=player, match=match)

@app.route('/hadunion-pass:121/W', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin'):
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        # Manual CSRF check
        token = session.get('_csrf_token')
        form_token = request.form.get('_csrf_token')
        if not token or token != form_token:
            abort(403)
            
        password = request.form.get('password')
        if password == '3ltillaug':
            session['admin'] = True
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid password!', 'error')
    
    return render_template('admin.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    matches = Match.query.order_by(Match.time.desc()).all()
    players = Player.query.order_by(Player.created_at.desc()).all()
    settings = Settings.query.first()
    
    # Calculate real metrics
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    today_matches = Match.query.filter(
        Match.time >= today_start,
        Match.time <= today_end
    ).all()
    
    pending_payments = Player.query.filter_by(payment_status='pending').all()
    approved_players = Player.query.filter_by(payment_status='paid').all()
    
    revenue_total = sum(p.match.entry_fee for p in approved_players if p.match)
    
    revenue_today = 0
    for p in approved_players:
        match = Match.query.get(p.match_id)
        if match and match.time.date() == today:
            revenue_today += match.entry_fee
    
    stats = {
        'total_matches': Match.query.count(),
        'active_matches': Match.query.filter(Match.status.in_(['upcoming', 'live'])).count(),
        'total_players': Player.query.count(),
        'pending_payments': len(pending_payments),
        'approved_players': len(approved_players),
        'revenue_total': revenue_total,
        'revenue_today': revenue_today,
        'today_matches': len(today_matches)
    }
    
    return render_template('dashboard.html', 
                         matches=matches, 
                         players=players, 
                         settings=settings,
                         stats=stats)

@app.route('/admin/create-match', methods=['POST'])
@csrf_protect
def create_match():
    game = request.form.get('game')
    time_str = request.form.get('time')
    entry_fee = request.form.get('entry_fee')
    total_slots = request.form.get('total_slots')
    prize = request.form.get('prize')
    discord_link = request.form.get('discord_link')
    stream_link = request.form.get('stream_link')
    
    if not all([game, time_str, entry_fee, total_slots]):
        flash('All required fields must be filled!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        entry_fee = int(entry_fee)
        total_slots = int(total_slots)
        match_time = datetime.strptime(time_str, '%Y-%m-%dT%H:%M')
    except (ValueError, TypeError):
        flash('Invalid date/time or number format!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if entry_fee <= 0 or total_slots <= 0:
        flash('Entry fee and slots must be positive!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    match = Match(
        game=game,
        time=match_time,
        entry_fee=entry_fee,
        total_slots=total_slots,
        available_slots=total_slots,
        prize=prize,
        discord_link=discord_link,
        stream_link=stream_link,
        status='upcoming'
    )
    db.session.add(match)
    db.session.commit()
    
    flash('Match created successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-match/<int:match_id>', methods=['POST'])
@csrf_protect
def update_match(match_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    match = Match.query.get_or_404(match_id)
    match.game = request.form.get('game', match.game)
    match.room_id = request.form.get('room_id')
    match.room_password = request.form.get('room_password')
    new_status = request.form.get('status')
    if new_status in ['upcoming', 'live', 'completed', 'cancelled']:
        match.status = new_status
    
    # Update other fields if provided
    if request.form.get('entry_fee'):
        try:
            match.entry_fee = int(request.form.get('entry_fee'))
        except:
            pass
    if request.form.get('total_slots'):
        try:
            total = int(request.form.get('total_slots'))
            if total > 0:
                # Adjust available slots proportionally
                filled = match.total_slots - match.available_slots
                match.total_slots = total
                match.available_slots = max(0, total - filled)
        except:
            pass
    if request.form.get('prize'):
        match.prize = request.form.get('prize')
    if request.form.get('discord_link'):
        match.discord_link = request.form.get('discord_link')
    if request.form.get('stream_link'):
        match.stream_link = request.form.get('stream_link')
    
    db.session.commit()
    flash('Match updated!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-match/<int:match_id>', methods=['POST'])
@csrf_protect
def delete_match(match_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    match = Match.query.get_or_404(match_id)
    
    # Check if match has players
    if match.players:
        flash('Cannot delete match with registered players!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    db.session.delete(match)
    db.session.commit()
    flash('Match deleted!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/approve-player/<int:player_id>/', methods=['POST'])
@csrf_protect
def approve_player(player_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    player = Player.query.get_or_404(player_id)
    match = Match.query.get(player.match_id)
    
    if player.payment_status == 'paid':
        flash('Player already approved!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if match.status not in ['upcoming', 'live']:
        flash('Cannot approve: Match is not active!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if match.available_slots <= 0:
        flash('Cannot approve: No slots remaining for this match!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    player.payment_status = 'paid'
    
    if not player.pass_id:
        pass_id = f"VW-{uuid.uuid4().hex[:4].upper()}-{match.game.replace(' ', '')[:4].upper()}"
        player.pass_id = pass_id
    
    match.available_slots -= 1
    db.session.commit()
    
    flash('Player approved!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject-player/<int:player_id>/', methods=['POST'])
@csrf_protect
def reject_player(player_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    player = Player.query.get_or_404(player_id)
    
    if player.payment_status != 'pending':
        flash('Only pending players can be rejected!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    player.payment_status = 'rejected'
    db.session.commit()
    flash('Player rejected!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/save-settings', methods=['POST'])
@csrf_protect
def save_settings():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    settings = Settings.query.first()
    if not settings:
        settings = Settings()
    
    upi_id = request.form.get('upi_id')
    if not upi_id:
        flash('UPI ID is required!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    settings.upi_id = upi_id
    
    if 'qr_image' in request.files:
        file = request.files['qr_image']
        if file and file.filename:
            filename = secure_filename(f"qr_{uuid.uuid4()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            settings.qr_path = f"uploads/{filename}"
    
    db.session.add(settings)
    db.session.commit()
    
    flash('Settings saved!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/generate-qr')
def generate_qr():
    upi_id = request.args.get('upi_id')
    amount = request.args.get('amount', '100')
    
    if not upi_id:
        return jsonify({'error': 'UPI ID required'}), 400
    
    upi_url = f"upi://pay?pa={upi_id}&pn=VortexWarriors&am={amount}&cu=INR"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    qr_path = os.path.join(app.config['UPLOAD_FOLDER'], f'qr_{uuid.uuid4()}.png')
    img.save(qr_path)
    
    return send_file(qr_path, mimetype='image/png')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

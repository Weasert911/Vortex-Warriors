# Vortex Warriors (VW) - Micro Tournament System

A production-ready Flask-based micro tournament management system for Free Fire and other mobile esports tournaments.

## Features

- **User-facing portal** with dark neon/glitch aesthetic
- **Complete tournament flow**: Browse matches → Register → Payment → Portal access
- **UPI payment integration** with QR code generation
- **Admin dashboard** for full control
- **Player management** with approval/rejection
- **Real-time slot tracking**

## Tech Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **Frontend**: HTML, CSS (dark neon/glitch style), Vanilla JavaScript
- **Payment**: UPI with QR code support

## Installation

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Setup Steps

1. **Clone or download the project**
   ```bash
   cd c:\Users\hp\OneDrive\Desktop\Busnessed\VW
   ```

2. **Create virtual environment (recommended)**
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install flask flask-sqlalchemy qrcode pillow werkzeug
   ```

4. **Initialize database**
   ```bash
   python app.py
   ```
   The database will be created automatically on first run.

5. **Access the application**
   - Frontend: http://localhost:5000
   - Admin Panel: http://localhost:5000/hadunion-pass:121/W
     - Password: `3ltillaug`

## Usage Guide

### For Players

1. **Browse Matches**: Visit homepage to see today's available matches
2. **Join a Match**: Click "Join Now" on any match card
3. **Fill Registration Form**: Enter name, game UID, Discord username
4. **Make Payment**: 
   - Scan QR code or use UPI ID
   - Pay exact entry fee
   - Upload payment screenshot
5. **Get Pass ID**: After admin approval, you'll receive a unique Pass ID
6. **Access Portal**: Use your Pass ID to view match details, room codes, and join Discord

### For Admins

1. **Login**: Visit `/hadunion-pass:121/W` and enter password `3ltillaug`
2. **Create Tournament**: Fill in match details (game, time, entry fee, slots, prize)
3. **Configure Payment**: Set UPI ID and optionally upload QR image
4. **Manage Players**: 
   - View all registrations with payment screenshots
   - Approve or reject players
   - Pass ID is auto-generated on approval
5. **Set Room Details**: When ready, update match with room ID and password
6. **Control Match Status**: Open → Live → Completed

## Database Schema

### Matches
- `id` (PK)
- `game` (Free Fire, BGMI, PUBG Mobile, etc.)
- `time` (match datetime)
- `entry_fee` (in INR)
- `total_slots` / `available_slots`
- `status` (open, live, completed)
- `room_id`, `room_password`
- `discord_link`, `stream_link`
- `prize`

### Players
- `id` (PK)
- `name`, `uid`, `discord`
- `match_id` (FK)
- `payment_status` (pending, paid, rejected)
- `payment_screenshot` (file path)
- `pass_id` (unique, format: VW-XXXX-GAME)
- `slot_assigned`

### Settings
- `id` (PK)
- `upi_id` (payment UPI ID)
- `qr_path` (optional uploaded QR image)

## Critical Flow

```
Landing Page → Match List → Join Form → /register → /payment/<player_id> → Upload Screenshot → /confirm-payment/<player_id> → Portal
```

**Important**: The form does NOT ask for payment screenshot. Screenshot is uploaded ONLY on the payment page after paying.

## File Structure

```
VW/
├── app.py                 # Main Flask application
├── database.db           # SQLite database (auto-created)
├── static/
│   └── uploads/          # Payment screenshots & QR codes
├── templates/
│   ├── index.html        # Landing page with matches
│   ├── form.html         # Registration form
│   ├── payment.html      # Payment page with QR/UPI
│   ├── portal.html       # Player portal
│   ├── admin.html        # Admin login
│   └── dashboard.html    # Admin dashboard
└── README.md
```

## Security Features

- CSRF protection on all forms
- Hidden admin route (`/hadunion-pass:121/W`)
- Session-based authentication
- File upload validation
- SQL injection prevention via SQLAlchemy

## Customization

### Styling
- Colors defined in CSS `:root` variables:
  - `--neon-purple`: #C026D3
  - `--toxic-green`: #39FF14
  - `--blood-red`: #FF0033
  - `--deep-black`: #000000

### Admin Password
Change in `app.py`:
```python
if password == '3ltillaug':  # Change this
```

### Secret Key
Change in `app.py`:
```python
app.config['SECRET_KEY'] = 'vw-secret-key-change-in-production'
```

## Production Deployment

1. **Set debug=False** in `app.run(debug=True, port=5000)`
2. **Use a production WSGI server** (Gunicorn, uWSGI)
3. **Configure a proper database** (PostgreSQL recommended)
4. **Set up HTTPS** with SSL certificate
5. **Change all default passwords and secrets**
6. **Configure file upload limits** and security headers
7. **Set up logging and monitoring**

## Troubleshooting

**Database errors**: Delete `instance/database.db` and restart app to recreate.

**Upload issues**: Ensure `static/uploads/` directory exists and is writable.

**QR not generating**: Check that `qrcode` package is installed.

**Admin login failing**: Verify route is `/hadunion-pass:121/W` (not `/admin`).

## License

Proprietary - All rights reserved to Vortex Warriors.

---

**Built with precision. No fake counters. Real tournaments only.**
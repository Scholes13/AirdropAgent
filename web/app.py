"""
Web application for AirdropAgent
"""
import sys
import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database
from config import SERVER_HOST, SERVER_PORT, ADMIN_USERNAME, ADMIN_PASSWORD

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for sessions
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=7)  # Session lifetime

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User model
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

# Single admin user
admin_user = User(1, ADMIN_USERNAME)

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID"""
    if int(user_id) == 1:
        return admin_user
    return None

@app.route('/')
def index():
    """Root route - redirect to login or dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            login_user(admin_user)
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid credentials'
    
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page"""
    # Get recent airdrops
    airdrops = database.get_recent_airdrops(limit=20)
    
    # Get stats
    stats = database.get_stats()
    
    return render_template('dashboard.html', 
                          airdrops=airdrops, 
                          stats=stats,
                          title="Airdrop Analyzer Dashboard")

@app.route('/airdrop/<int:airdrop_id>')
@login_required
def view_airdrop(airdrop_id):
    """View details for a specific airdrop"""
    airdrop = database.get_airdrop_by_id(airdrop_id)
    
    if not airdrop:
        flash('Airdrop not found', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('airdrop_detail.html', 
                          airdrop=airdrop,
                          title=f"Airdrop Details: {airdrop['project_name']}")

@app.route('/api/airdrops/recent')
@login_required
def api_recent_airdrops():
    """API endpoint for recent airdrops"""
    limit = request.args.get('limit', default=50, type=int)
    airdrops = database.get_recent_airdrops(limit=limit)
    return jsonify(airdrops)

@app.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for stats"""
    stats = database.get_stats()
    return jsonify(stats)

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('error.html', 
                          error_code=404,
                          error_message='Page not found'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('error.html',
                          error_code=500,
                          error_message='Server error'), 500

# New routes for sidebar pages
@app.route('/analytics')
@login_required
def analytics():
    """Analytics page"""
    stats = database.get_stats()
    return render_template('analytics.html',
                          stats=stats,
                          title="Analytics Dashboard")

@app.route('/verified')
@login_required
def verified_projects():
    """Verified projects page"""
    # Get projects with rating > 7.5
    verified_projects = database.get_airdrops_by_filter(is_legitimate=True)
    return render_template('verified.html',
                          verified_projects=verified_projects,
                          title="Verified Projects")

@app.route('/scam-alerts')
@login_required
def scam_alerts():
    """Scam alerts page"""
    # Get projects with rating < 4.0
    scam_projects = database.get_airdrops_by_filter(is_scam=True)
    return render_template('scam_alerts.html',
                          scam_projects=scam_projects,
                          title="Scam Alerts")

@app.route('/settings')
@login_required
def settings():
    """Settings page"""
    return render_template('settings.html',
                          title="Settings")

if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False) 
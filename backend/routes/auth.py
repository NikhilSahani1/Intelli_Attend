"""
Authentication routes for login, registration, and password management
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime

from backend.models.user import User
from backend.models.admin import Admin
from backend.utils.database import get_db
from backend.utils.security import is_locked_out, record_login_attempt, login_required
from backend.utils.validators import validate_email, validate_password, sanitize_input
from backend.utils.audit import log_audit

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route"""
    if request.method == 'POST':
        # Get form data
        name = sanitize_input(request.form.get('name', ''))
        moodle_id = sanitize_input(request.form.get('moodle_id', ''))
        email = sanitize_input(request.form.get('email', ''))
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        aadhaar_number = sanitize_input(request.form.get('aadhaar_number', ''))
        student_id = sanitize_input(request.form.get('student_id', ''))
        phone_number = sanitize_input(request.form.get('phone_number', ''))
        
        # Validate inputs
        if not all([name, moodle_id, email, password, confirm_password]):
            flash('All fields are required', 'error')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/register.html')
        
        if not validate_email(email):
            flash('Invalid email format', 'error')
            return render_template('auth/register.html')
        
        is_valid, msg = validate_password(password)
        if not is_valid:
            flash(msg, 'error')
            return render_template('auth/register.html')
        
        if aadhaar_number and len(aadhaar_number) != 12:
            flash('Aadhaar number must be 12 digits', 'error')
            return render_template('auth/register.html')
        
        try:
            # Create user
            user = User.create(
                name=name,
                moodle_id=moodle_id,
                email=email,
                password=password,
                aadhaar_number=aadhaar_number,
                student_id=student_id,
                phone_number=phone_number
            )
            
            log_audit('USER_REGISTERED', f'New user registered: {email}', user.id)
            flash('Registration successful! Please wait for admin verification.', 'success')
            return redirect(url_for('auth.user_login'))
            
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash('Registration failed. Please try again.', 'error')
            log_audit('REGISTRATION_ERROR', str(e))
    
    return render_template('auth/register.html')

@auth_bp.route('/user/login', methods=['GET', 'POST'])
def user_login():
    """User login route"""
    if request.method == 'POST':
        moodle_id = sanitize_input(request.form.get('moodle_id', ''))
        password = request.form.get('password', '')
        identifier = f"user_{moodle_id}_{request.remote_addr}"
        
        # Check if locked out
        if is_locked_out(identifier):
            flash('Too many failed attempts. Please try again later.', 'error')
            return render_template('auth/user_login.html')
        
        if not moodle_id or not password:
            flash('Both fields are required', 'error')
            return render_template('auth/user_login.html')
        
        # Get user
        user = User.get_by_moodle_id(moodle_id)
        
        if user and user.verify_password(password):
            # Check if user is verified
            if not user.is_verified():
                flash('Your account is pending verification by admin.', 'warning')
                log_audit('LOGIN_BLOCKED', f'Login blocked - not verified', user.id)
                return render_template('auth/user_login.html')
            
            # Check if user is active
            if not user.is_active:
                flash('Your account has been deactivated. Contact admin.', 'error')
                return render_template('auth/user_login.html')
            
            # Set session
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_type'] = 'user'
            session['login_time'] = datetime.now().isoformat()
            
            # Update last login
            user.update_last_login()
            
            # Reset login attempts
            record_login_attempt(identifier, success=True)
            
            log_audit('USER_LOGIN', f'User logged in: {user.email}', user.id)
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('user.dashboard'))
        
        else:
            # Record failed attempt
            record_login_attempt(identifier, success=False)
            
            if user:
                # Increment failed attempts in database
                db = get_db()
                db.execute('''
                    UPDATE users 
                    SET failed_login_attempts = COALESCE(failed_login_attempts, 0) + 1 
                    WHERE id = ?
                ''', (user.id,))
                db.commit()
            
            flash('Invalid Moodle ID or password', 'error')
            log_audit('LOGIN_FAILED', f'Failed login attempt for {moodle_id}')
    
    return render_template('auth/user_login.html')

@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login route"""
    if request.method == 'POST':
        username = sanitize_input(request.form.get('username', ''))
        password = request.form.get('password', '')
        identifier = f"admin_{username}_{request.remote_addr}"
        
        # Check if locked out
        if is_locked_out(identifier):
            flash('Too many failed attempts. Please try again later.', 'error')
            return render_template('auth/admin_login.html')
        
        if not username or not password:
            flash('Both fields are required', 'error')
            return render_template('auth/admin_login.html')
        
        # Get admin
        admin = Admin.get_by_username(username)
        
        if admin and admin.verify_password(password):
            # Set session
            session['admin_id'] = admin.id
            session['admin_name'] = admin.username
            session['user_type'] = 'admin'
            session['login_time'] = datetime.now().isoformat()
            
            # Update last login
            admin.update_last_login()
            
            # Reset login attempts
            record_login_attempt(identifier, success=True)
            
            log_audit('ADMIN_LOGIN', f'Admin logged in: {admin.username}', admin.id)
            flash('Admin login successful', 'success')
            return redirect(url_for('admin.dashboard'))
        
        else:
            # Record failed attempt
            record_login_attempt(identifier, success=False)
            flash('Invalid username or password', 'error')
            log_audit('ADMIN_LOGIN_FAILED', f'Failed admin login attempt for {username}')
    
    return render_template('auth/admin_login.html')

@auth_bp.route('/logout')
def logout():
    """Logout route"""
    user_type = session.get('user_type')
    user_id = session.get('user_id') or session.get('admin_id')
    
    if user_id:
        log_audit('LOGOUT', f'{user_type} logged out', user_id)
    
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Password reset route"""
    if request.method == 'POST':
        email = sanitize_input(request.form.get('email', ''))
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not email or not new_password or not confirm_password:
            flash('All fields are required', 'error')
            return render_template('auth/reset_password.html')
        
        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/reset_password.html')
        
        is_valid, msg = validate_password(new_password)
        if not is_valid:
            flash(msg, 'error')
            return render_template('auth/reset_password.html')
        
        # Get user
        user = User.get_by_email(email)
        
        if user:
            # Update password
            db = get_db()
            hashed = generate_password_hash(new_password)
            db.execute('UPDATE users SET password = ? WHERE id = ?', (hashed, user.id))
            db.commit()
            
            log_audit('PASSWORD_RESET', f'Password reset for {email}', user.id)
            flash('Password reset successful. Please login.', 'success')
            return redirect(url_for('auth.user_login'))
        else:
            flash('Email not found', 'error')
    
    return render_template('auth/reset_password.html')
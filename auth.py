from flask import Blueprint, request, jsonify, session, redirect, url_for
from db import get_db, hash_password, verify_password

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not username or len(username) < 2:
            return jsonify({'error': 'Username must be at least 2 characters'}), 400
        if len(username) > 30:
            return jsonify({'error': 'Username too long (max 30 chars)'}), 400
        if not password or len(password) < 4:
            return jsonify({'error': 'Password must be at least 4 characters'}), 400

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            return jsonify({'error': 'Username already taken'}), 409

        pw_hash = hash_password(password)
        db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email or '', pw_hash)
        )
        db.commit()
        db.close()

        return jsonify({'success': True, 'message': 'Registration successful'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return jsonify({'error': 'Please enter username and password'}), 400

        db = get_db()
        user = db.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        db.close()

        if not user or not verify_password(password, user['password_hash']):
            return jsonify({'error': 'Invalid username or password'}), 401

        session['user_id'] = user['id']
        session['username'] = user['username']
        session.permanent = True

        return jsonify({
            'success': True,
            'user': {'id': user['id'], 'username': user['username']}
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""股票价值分析网站 - 完整版（含用户系统+完整13章分析引擎+苹果风格UI）"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_cors import CORS
from datetime import datetime
import json
import sys
import os
import io

# 父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stock_analyzer_web import analyze_stock_full, get_kline_data
from db import get_db, init_db, DB_PATH
from auth import auth_bp

app = Flask(__name__)
app.secret_key = 'stock_analyzer_secret_key_2026'
CORS(app)

# 注册蓝图
app.register_blueprint(auth_bp)

# 全局股票列表
STOCK_LIST = []

def load_stock_list():
    global STOCK_LIST
    try:
        # 优先加载完整列表
        data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'stock_list_full.json')
        if not os.path.exists(data_path):
            data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'stock_list.json')
        with open(data_path, 'r', encoding='utf-8') as f:
            STOCK_LIST = json.load(f)
        print(f"Loaded {len(STOCK_LIST)} stocks")
    except Exception as e:
        print(f"Stock list load failed: {e}")
        STOCK_LIST = []

# 初始化数据库和股票列表
init_db()
load_stock_list()

# ============================================================
# 页面路由
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/history')
def history_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('history.html')

# ============================================================
# API路由
# ============================================================

@app.route('/api/search')
def search_stocks():
    query = request.args.get('q', '').strip().lower()
    if not query or len(query) < 1:
        return jsonify([])
    
    results = []
    query_lower = query.lower()
    
    # 优化搜索：优先代码精确匹配，然后名称前缀匹配，最后名称包含匹配
    for stock in STOCK_LIST:
        code = stock.get('code', '')
        name = stock.get('name', '')
        
        matched = False
        # 代码精确匹配（优先级最高）
        if code == query:
            matched = True
        # 代码前缀匹配
        elif code.startswith(query):
            matched = True
        # 名称精确匹配
        elif name == query:
            matched = True
        # 名称前缀匹配
        elif name.startswith(query.upper()) or name.lower().startswith(query_lower):
            matched = True
        # 名称包含匹配
        elif query_lower in name.lower():
            matched = True
        
        if matched:
            results.append({
                'code': code, 
                'name': name,
                'market': stock.get('market', ''),
                'display': f"{code} - {name}"
            })
            if len(results) >= 10:
                break
    
    return jsonify(results)

@app.route('/api/search_stock_code')
def search_stock_code_api():
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'code': None})
    name_lower = name.lower()
    for stock in STOCK_LIST:
        if stock.get('name', '').lower() == name_lower:
            return jsonify({'code': stock.get('code')})
    for stock in STOCK_LIST:
        if name_lower in stock.get('name', '').lower():
            return jsonify({'code': stock.get('code')})
    return jsonify({'code': None})

@app.route('/api/analyze', methods=['POST'])
def analyze_stock():
    try:
        data = request.get_json()
        code = data.get('code', '')
        name = data.get('name', '')
        if not code and not name:
            return jsonify({'error': 'please input stock code or name'}), 400
        if name and not code:
            code = search_stock_code(name)
            if not code:
                return jsonify({'error': f'stock not found: {name}'}), 404
        report = analyze_stock_full(code)
        if 'error' in report:
            return jsonify({'error': report['error']}), 500

        # 保存历史记录（若用户已登录）
        if 'user_id' in session:
            try:
                db = get_db()
                stock_name = report.get('ch1_overview', {}).get('stock_name', '')
                db.execute(
                    "INSERT INTO analysis_history (user_id, stock_code, stock_name, report_json, query_time) VALUES (?, ?, ?, ?, ?)",
                    (session['user_id'], code, stock_name, json.dumps(report, ensure_ascii=False), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                )
                db.commit()
            except Exception:
                pass

        return jsonify(report)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def get_history():
    if 'user_id' not in session:
        return jsonify({'error': 'not logged in'}), 401
    try:
        db = get_db()
        rows = db.execute(
            "SELECT id, stock_code, stock_name, query_time FROM analysis_history WHERE user_id = ? ORDER BY id DESC LIMIT 50",
            (session['user_id'],)
        ).fetchall()
        return jsonify([{
            'id': r['id'], 'stock_code': r['stock_code'],
            'stock_name': r['stock_name'], 'query_time': r['query_time']
        } for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history/<int:history_id>')
def get_history_detail(history_id):
    if 'user_id' not in session:
        return jsonify({'error': 'not logged in'}), 401
    try:
        db = get_db()
        row = db.execute(
            "SELECT report_json, query_time FROM analysis_history WHERE id = ? AND user_id = ?",
            (history_id, session['user_id'])
        ).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        report = json.loads(row['report_json'])
        report['__history_id'] = history_id
        report['__history_time'] = row['query_time']
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export_pdf', methods=['POST'])
def export_pdf():
    """导出PDF报告"""
    try:
        data = request.get_json()
        code = data.get('code', '')
        report_json = data.get('report', None)  # 可以传入已有报告

        if not code:
            return jsonify({'error': '请提供股票代码'}), 400

        # 获取报告
        if report_json:
            report = report_json
        else:
            report = analyze_stock_full(code)
            if 'error' in report:
                return jsonify({'error': report['error']}), 500

        # 获取K线数据
        klines = get_kline_data(code, 120)

        # 生成PDF
        try:
            from pdf_generator import generate_pdf
            pdf_buf = generate_pdf(report, klines)
        except ImportError as e:
            return jsonify({'error': f'PDF生成模块未安装：{str(e)}，请安装 reportlab 和 matplotlib'}), 500
        except Exception as e:
            return jsonify({'error': f'PDF生成失败：{str(e)}'}), 500

        name = report.get('ch1_overview', {}).get('stock_name', code)
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f'{code}_{name}_价值分析报告_{date_str}.pdf'

        # 如果用户已登录，保存PDF记录
        if 'user_id' in session:
            try:
                db = get_db()
                pdf_record = {
                    'filename': filename,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }
                db.execute(
                    "INSERT INTO analysis_history (user_id, stock_code, stock_name, report_json, query_time) VALUES (?, ?, ?, ?, ?)",
                    (session['user_id'], code, name + '[PDF]', json.dumps(pdf_record), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                )
                db.commit()
            except Exception:
                pass

        return send_file(
            io.BytesIO(pdf_buf.read()),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500



def auth_status():
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'username': session.get('username', ''),
            'user_id': session.get('user_id')
        })
    return jsonify({'logged_in': False})

def search_stock_code(name):
    name_lower = name.lower()
    for stock in STOCK_LIST:
        if stock.get('name', '').lower() == name_lower:
            return stock.get('code')
    for stock in STOCK_LIST:
        if name_lower in stock.get('name', '').lower():
            return stock.get('code')
    return None

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    # Render 需要绑定到 0.0.0.0，本地开发默认 127.0.0.1
    host = os.environ.get('HOST', '0.0.0.0')
    print('=' * 60)
    print('Stock Value Analysis Website - Starting...')
    print(f'URL: http://{host}:{port}')
    print('=' * 60)
    app.run(debug=False, host=host, port=port)

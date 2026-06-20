#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

print("Flask app created")

# 全局变量：股票列表
STOCK_LIST = []

def load_stock_list():
    """加载股票列表"""
    global STOCK_LIST
    try:
        data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'stock_list.json')
        print(f"Loading stock list from: {data_path}")
        with open(data_path, 'r', encoding='utf-8') as f:
            STOCK_LIST = json.load(f)
        print(f"成功加载 {len(STOCK_LIST)} 只股票")
    except Exception as e:
        print(f"加载股票列表失败：{e}")
        STOCK_LIST = []

print("About to load stock list...")
# 启动时加载股票列表
load_stock_list()
print("Stock list loaded")

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/api/search')
def search_stocks():
    """
    搜索股票API
    参数：q - 搜索关键词（可以是代码、名称、拼音缩写）
    返回：匹配的股票列表（最多10条）
    """
    query = request.args.get('q', '').strip().lower()
    
    if not query or len(query) < 1:
        return jsonify([])
    
    # 模糊匹配
    results = []
    for stock in STOCK_LIST:
        code = stock.get('code', '')
        name = stock.get('name', '')
        pinyin = stock.get('pinyin', '')
        
        # 匹配代码、名称、拼音
        if (query in code.lower() or 
            query in name.lower() or 
            query in pinyin.lower()):
            results.append({
                'code': code,
                'name': name,
                'market': stock.get('market', ''),
                'display': f"{code} - {name}"
            })
            
            # 最多返回10条
            if len(results) >= 10:
                break
    
    return jsonify(results)

@app.route('/api/analyze', methods=['POST'])
def analyze_stock():
    """分析股票API（简化版，返回模拟数据）"""
    try:
        data = request.get_json()
        code = data.get('code', '')
        name = data.get('name', '')
        
        if not code and not name:
            return jsonify({'error': '请输入股票代码或名称'}), 400
        
        # 如果输入的是名称，尝试转换为代码
        if name and not code:
            code = search_stock_code(name)
            if not code:
                return jsonify({'error': f'未找到股票：{name}'}), 404
        
        # 返回模拟数据（简化版）
        result = {
            'title': f"{name or code}（{code}）价值分析报告",
            'generated_at': '2026-06-20 08:50:00',
            'summary': {
                '股票名称': name or '未知',
                '股票代码': code,
                '当前股价': '176.58 元',
                '涨跌幅': '7.00%',
                '总市值': '52.05 亿元',
                '市盈率(PE-TTM)': '86.68',
                '估值水平': '高估'
            },
            'valuation': {
                'pe_analysis': '当前市盈率(PE-TTM)为 86.68。估值较高，建议谨慎。',
                'suggested_price_range': {
                    'low': '27.50 元',
                    'high': '33.61 元'
                }
            },
            'recommendation': {
                'rating': '减持',
                'target_price': '194.24 元',
                'suggestion': '估值较高，建议回避或减仓，注意风险控制。'
            },
            'risk_warning': [
                '股市有风险，投资需谨慎',
                '本报告仅供参考，不构成投资建议',
                '请结合自身风险承受能力做出投资决策',
                '建议分散投资，不要集中持有单一股票'
            ]
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def search_stock_code(name):
    """根据股票名称搜索代码"""
    name_lower = name.lower()
    
    # 精确匹配
    for stock in STOCK_LIST:
        if stock.get('name', '').lower() == name_lower:
            return stock.get('code')
    
    # 模糊匹配（包含关键词）
    for stock in STOCK_LIST:
        if name_lower in stock.get('name', '').lower():
            return stock.get('code')
    
    return None

if __name__ == '__main__':
    print('=' * 60)
    print('股票价值分析网站 - 启动中...')
    print('=' * 60)
    print('访问地址：http://127.0.0.1:5001')
    print('按 Ctrl+C 停止服务')
    print('=' * 60)
    app.run(debug=True, host='127.0.0.1', port=5001)

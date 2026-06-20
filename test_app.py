#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return 'Hello World!'

@app.route('/api/search')
def search():
    return jsonify([{'code': '603629', 'name': '利通电子'}])

@app.route('/api/test')
def test():
    return jsonify({'status': 'ok', 'message': '测试成功'})

if __name__ == '__main__':
    print('=' * 60)
    print('测试服务器启动中...')
    print('访问地址：http://127.0.0.1:5000')
    print('=' * 60)
    app.run(debug=True, host='127.0.0.1', port=5000)

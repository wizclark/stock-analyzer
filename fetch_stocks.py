#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取所有A股股票列表，保存到 stock_list.json
数据源：东方财富API
"""

import urllib.request
import json
import time

def fetch_stock_list():
    """
    从东方财富API获取所有A股股票列表
    包括：沪市、深市、科创板、创业板、北交所
    """
    stocks = []
    
    # 东方财富API：获取A股列表
    # fs参数：m:0+t:6(沪市A股), m:0+t:13(深市A股), m:1+t:2(科创板), m:1+t:23(创业板)
    url = "http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5000&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23&fields=f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data and 'data' in data and 'diff' in data['data']:
                for item in data['data']['diff']:
                    stock_code = item.get('f12', '')
                    stock_name = item.get('f14', '')
                    
                    if stock_code and stock_name:
                        # 判断市场
                        market = 'sh' if stock_code.startswith('6') or stock_code.startswith('5') else 'sz'
                        
                        stocks.append({
                            'code': stock_code,
                            'name': stock_name,
                            'market': market,
                            'pinyin': get_pinyin_abbr(stock_name)
                        })
                
                print(f"成功获取 {len(stocks)} 只股票")
            else:
                print("获取股票列表失败：返回数据格式错误")
    
    except Exception as e:
        print(f"获取股票列表失败：{e}")
        # 如果API失败，使用备用数据
        stocks = get_backup_stock_list()
    
    return stocks

def get_pinyin_abbr(name):
    """
    获取股票名称的拼音首字母缩写
    简化版：只取前4个汉字的拼音首字母
    """
    # 这里使用简化逻辑，实际应用中可以使用 pypinyin 库
    # 为演示目的，这里返回空字符串
    return ""

def get_backup_stock_list():
    """
    备用股票列表（常见A股）
    当API失败时使用的备用数据
    """
    backup_stocks = [
        {'code': '603629', 'name': '利通电子', 'market': 'sh', 'pinyin': 'ltdz'},
        {'code': '600519', 'name': '贵州茅台', 'market': 'sh', 'pinyin': 'gzmj'},
        {'code': '601318', 'name': '中国平安', 'market': 'sh', 'pinyin': 'zganpa'},
        {'code': '600036', 'name': '招商银行', 'market': 'sh', 'pinyin': 'zsyh'},
        {'code': '601398', 'name': '工商银行', 'market': 'sh', 'pinyin': 'gsyh'},
        {'code': '601857', 'name': '中国石油', 'market': 'sh', 'pinyin': 'zgsy'},
        {'code': '600028', 'name': '中国石化', 'market': 'sh', 'pinyin': 'zgsh'},
        {'code': '300750', 'name': '宁德时代', 'market': 'sz', 'pinyin': 'ndsd'},
        {'code': '002594', 'name': '比亚迪', 'market': 'sz', 'pinyin': 'byd'},
        {'code': '000858', 'name': '五粮液', 'market': 'sz', 'pinyin': 'wly'},
    ]
    return backup_stocks

def save_stock_list(stocks, filepath):
    """
    保存股票列表到JSON文件
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(stocks, f, ensure_ascii=False, indent=2)
        print(f"股票列表已保存到：{filepath}")
        print(f"共 {len(stocks)} 只股票")
    except Exception as e:
        print(f"保存股票列表失败：{e}")

if __name__ == '__main__':
    print("=" * 60)
    print("获取A股股票列表")
    print("=" * 60)
    
    # 获取股票列表
    stocks = fetch_stock_list()
    
    # 保存到文件
    output_path = 'data/stock_list.json'
    save_stock_list(stocks, output_path)
    
    print("=" * 60)
    print("完成！")
    print("=" * 60)

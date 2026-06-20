#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取完整A股股票列表
数据源：东方财富API（免费，无需认证）
"""

import urllib.request
import json
import time

def fetch_all_stocks():
    """从东方财富获取所有A股股票列表"""
    stocks = []
    
    # 东方财富API：获取沪深A股列表
    # pn: 页码，pz: 每页数量（最大5000）
    url = "http://80.push2.eastmoney.com/api/qt/clist/get?cb=&pn=1&pz=5000&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode('utf-8')
            
            # 去除JSONP回调
            if content.startswith('('):
                content = content[1:-1]
            
            data = json.loads(content)
            
            if 'data' in data and 'diff' in data['data']:
                for item in data['data']['diff']:
                    code = item.get('f12', '')
                    name = item.get('f14', '')
                    
                    if code and name:
                        # 判断市场
                        market = 'sh' if code.startswith('6') else 'sz'
                        
                        stocks.append({
                            'code': code,
                            'name': name,
                            'market': market
                        })
                
                print(f"成功获取 {len(stocks)} 只股票")
                return stocks
            else:
                print("API返回数据格式错误")
                return []
                
    except Exception as e:
        print(f"获取股票列表失败：{e}")
        return []

def save_stocks(stocks, filepath):
    """保存股票列表到JSON文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    print(f"股票列表已保存到：{filepath}")

if __name__ == '__main__':
    print("开始获取A股股票列表...")
    stocks = fetch_all_stocks()
    
    if stocks:
        save_path = "C:/Users/54324/WorkBuddy/2026-06-19-23-10-41/stock_website/data/stock_list_full.json"
        save_stocks(stocks, save_path)
        print(f"\n完成！共保存 {len(stocks)} 只股票")
    else:
        print("获取失败，请检查网络连接")

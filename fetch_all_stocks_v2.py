#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取完整A股股票列表（优化版）
数据源：腾讯行情API
"""

import urllib.request
import json
import time

def fetch_all_stocks():
    """从腾讯行情API获取所有A股股票列表"""
    stocks = []
    
    # 沪深A股代码前缀
    code_prefixes = {
        'sh6': '上海主板',
        'sz0': '深圳主板',
        'sz3': '创业板',
        'sh688': '科创板',
        'sz002': '中小板'
    }
    
    print("开始获取A股股票列表...")
    
    # 方法：通过腾讯行情API批量查询
    # 由于API限制，我们采用常见股票代码范围
    
    # 上海主板：600000-605999
    print("正在获取上海主板股票...")
    for prefix in ['600', '601', '602', '603', '604', '605']:
        batch = []
        for i in range(1000):
            code = f"{prefix}{i:03d}"
            batch.append(f"sh{code}")
        stocks.extend(batch)
    
    # 深圳主板：000000-001999
    print("正在获取深圳主板股票...")
    for prefix in ['000', '001']:
        batch = []
        for i in range(1000):
            code = f"{prefix}{i:03d}"
            batch.append(f"sz{code}")
        stocks.extend(batch)
    
    # 创业板：300000-301999
    print("正在获取创业板股票...")
    for prefix in ['300', '301']:
        batch = []
        for i in range(1000):
            code = f"{prefix}{i:03d}"
            batch.append(f"sz{code}")
        stocks.extend(batch)
    
    # 科创板：688000-688999
    print("正在获取科创板股票...")
    for i in range(1000):
        code = f"688{i:03d}"
        stocks.append(f"sh{code}")
    
    # 中小板：002000-002999
    print("正在获取中小板股票...")
    for i in range(1000):
        code = f"002{i:03d}"
        stocks.append(f"sz{code}")
    
    print(f"共生成 {len(stocks)} 个股票代码，正在验证...")
    
    # 批量验证股票是否存在
    valid_stocks = []
    batch_size = 50
    
    for i in range(0, len(stocks), batch_size):
        batch = stocks[i:i+batch_size]
        query = ','.join(batch)
        
        try:
            url = f"http://qt.gtimg.cn/q={query}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('gbk', errors='ignore')
                
                for line in content.strip().split('\n'):
                    if '="' in line and '~' in line:
                        try:
                            fields = line.split('"')[1].split('~')
                            if len(fields) > 2 and fields[1]:  # 有股票名称
                                code = fields[2] if len(fields) > 2 else ''
                                name = fields[1]
                                market = 'sh' if code.startswith('6') else 'sz'
                                
                                valid_stocks.append({
                                    'code': code,
                                    'name': name,
                                    'market': market
                                })
                        except:
                            pass
            
            if i % 500 == 0:
                print(f"已验证 {i}/{len(stocks)}，有效股票：{len(valid_stocks)}")
            
            time.sleep(0.5)  # 避免请求过快
            
        except Exception as e:
            print(f"批次 {i} 验证失败：{e}")
            continue
    
    print(f"\n完成！共获取 {len(valid_stocks)} 只有效A股股票")
    return valid_stocks

def save_stocks(stocks, filepath):
    """保存股票列表到JSON文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    print(f"股票列表已保存到：{filepath}")

if __name__ == '__main__':
    stocks = fetch_all_stocks()
    
    if stocks:
        save_path = "C:/Users/54324/WorkBuddy/2026-06-19-23-10-41/stock_website/data/stock_list_full.json"
        save_stocks(stocks, save_path)
    else:
        print("获取失败")

import urllib.request
import json
import time

def fetch_stocks_sina_paginated():
    """分页从新浪财经获取A股列表"""
    print("正在分页从新浪财经获取A股列表...")
    
    stocks = []
    
    # 获取沪市股票（多页）
    print("  获取沪市股票...")
    page = 1
    while True:
        url_sh = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={page}&num=100&sort=symbol&asc=1&node=hs_a&symbol=&_s_r_a=init"
        
        try:
            req = urllib.request.Request(url_sh)
            req.add_header('Referer', 'http://finance.sina.com.cn/')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('gbk')
                data = json.loads(content)
                
                if not data:  # 没有更多数据
                    break
                
                for item in data:
                    stock = {
                        'code': item['symbol'],
                        'name': item['name'],
                        'market': '上海'
                    }
                    stocks.append(stock)
                
                print(f"    第{page}页: {len(data)} 只，累计 {len(stocks)} 只")
                page += 1
                time.sleep(0.3)  # 避免请求过快
                
        except Exception as e:
            print(f"    第{page}页获取失败: {e}")
            break
    
    sh_count = len(stocks)
    
    # 获取深市股票（多页）
    print("  获取深市股票...")
    page = 1
    while True:
        url_sz = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={page}&num=100&sort=symbol&asc=1&node=sz_a&symbol=&_s_r_a=init"
        
        try:
            req = urllib.request.Request(url_sz)
            req.add_header('Referer', 'http://finance.sina.com.cn/')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('gbk')
                data = json.loads(content)
                
                if not data:  # 没有更多数据
                    break
                
                for item in data:
                    stock = {
                        'code': item['symbol'],
                        'name': item['name'],
                        'market': '深圳'
                    }
                    stocks.append(stock)
                
                print(f"    第{page}页: {len(data)} 只，累计 {len(stocks)} 只")
                page += 1
                time.sleep(0.3)
                
        except Exception as e:
            print(f"    第{page}页获取失败: {e}")
            break
    
    print(f"\n✅ 共获取 {len(stocks)} 只A股股票（沪市{sh_count}只，深市{len(stocks)-sh_count}只）")
    return stocks

def save_stock_list(stocks, filename='stock_list_full.json'):
    """保存股票列表到JSON文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    print(f"股票列表已保存到 {filename}")

if __name__ == '__main__':
    stocks = fetch_stocks_sina_paginated()
    if stocks and len(stocks) > 100:
        save_stock_list(stocks)
        print(f"\n✅ 完成！共保存 {len(stocks)} 只股票")
    else:
        print("\n⚠️ 获取失败或股票数量过少")

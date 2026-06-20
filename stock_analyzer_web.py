#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票全维度价值分析引擎 - Web版
移植 stock-value-analysis skill 的完整逻辑
基于：腾讯行情API + 新浪财经API + IMA知识库缓存
"""

import urllib.request
import urllib.parse
import json
import re
import time
import os
import math
from datetime import datetime, timedelta
from collections import OrderedDict

# ============================================================
# 数据源模块
# ============================================================

def fetch_url(url, encoding='utf-8', timeout=10, retries=2):
    """通用URL抓取，支持重试"""
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                # 尝试检测编码
                if encoding == 'gbk' or encoding == 'gb2312':
                    return raw.decode('gbk', errors='replace')
                return raw.decode(encoding, errors='replace')
        except Exception as e:
            if i == retries:
                raise
            time.sleep(0.5)
    return None


def get_realtime_quote(code):
    """获取实时行情（腾讯API）"""
    prefix = 'sh' if code.startswith(('6', '9')) else 'sz'
    url = f'http://qt.gtimg.cn/q={prefix}{code}'

    try:
        content = fetch_url(url, encoding='gbk')
        match = re.search(r'="([^"]+)"', content)
        if not match:
            return None

        fields = match.group(1).split('~')
        if len(fields) < 46:
            return None

        data = {
            'name': fields[1],
            'code': fields[2],
            'price': safe_float(fields[3]),
            'prev_close': safe_float(fields[4]),
            'open': safe_float(fields[5]),
            'volume': safe_float(fields[6]),
            'high': safe_float(fields[33]),
            'low': safe_float(fields[34]),
            'change_pct': safe_float(fields[32]),
            'change_amt': safe_float(fields[31]),
            'pe_ttm': safe_float(fields[39]),      # PE-TTM
            'pe_static': safe_float(fields[42]),    # 静态PE
            'pb': safe_float(fields[46]) if len(fields) > 46 else 0,
            # 市值：腾讯API字段45为总市值(亿)，直接使用不除10000
            'market_cap': safe_float(fields[45]) if fields[45] else 0,  # 亿元
            'circulation_cap': safe_float(fields[44]) if fields[44] else 0,
            'turnover_rate': safe_float(fields[38]),
            'high_52w': safe_float(fields[41]),
            'low_52w': safe_float(fields[40]),
        }
        return data
    except Exception as e:
        print(f"[ERROR] 获取行情失败 {code}: {e}")
        return None


def get_financial_data_sina(code):
    """获取财务报表（新浪财经API）"""
    prefix = 'sh' if code.startswith(('6', '9')) else 'sz'
    result = {'profit': [], 'balance': [], 'cashflow': []}

    # 利润表
    try:
        url = f'https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_BLOG_PROFIT?symbol={prefix}{code}&type=year'
        content = fetch_url(url, timeout=15)
        if content:
            json_match = re.search(r'\((.+)\)', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                result['profit'] = data if isinstance(data, list) else []
    except Exception as e:
        print(f"[WARN] 利润表获取失败: {e}")

    # 资产负债表
    try:
        url = f'https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_BLOG_BALANCE?symbol={prefix}{code}&type=year'
        content = fetch_url(url, timeout=15)
        if content:
            json_match = re.search(r'\((.+)\)', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                result['balance'] = data if isinstance(data, list) else []
    except Exception as e:
        print(f"[WARN] 资产负债表获取失败: {e}")

    # 现金流量表
    try:
        url = f'https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_BLOG_CASHFLOW?symbol={prefix}{code}&type=year'
        content = fetch_url(url, timeout=15)
        if content:
            json_match = re.search(r'\((.+)\)', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                result['cashflow'] = data if isinstance(data, list) else []
    except Exception as e:
        print(f"[WARN] 现金流量表获取失败: {e}")

    return result


def get_kline_data(code, days=120):
    """获取K线数据（腾讯API）"""
    prefix = 'sh' if code.startswith(('6', '9')) else 'sz'
    url = f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,{days},qfq'

    try:
        content = fetch_url(url, timeout=10)
        data = json.loads(content)
        klines = data.get('data', {}).get(f'{prefix}{code}', {}).get('day', []) or \
                 data.get('data', {}).get(f'{prefix}{code}', {}).get('qfqday', [])

        result = []
        for k in klines:
            result.append({
                'date': k[0],
                'open': float(k[1]),
                'close': float(k[2]),
                'high': float(k[3]),
                'low': float(k[4]),
                'volume': float(k[5]),
            })
        return result
    except Exception as e:
        print(f"[WARN] K线获取失败: {e}")
        return []


def safe_float(val):
    """安全的float转换"""
    try:
        if val is None or str(val).strip() == '':
            return 0.0
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# 技术指标计算模块（移植自 quant-stock-selector/stock_analyzer.py）
# ============================================================

def calc_sma(data, period):
    """简单移动平均"""
    if len(data) < period:
        return None
    return sum(data[-period:]) / period


def calc_rsi(closes, period=14):
    """RSI - Wilder平滑"""
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(diff if diff > 0 else 0)
        losses.append(abs(diff) if diff < 0 else 0)

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100
    return 100 - (100 / (1 + avg_gain / avg_loss))


def calc_macd(closes, fast=12, slow=26, signal=9):
    """MACD指标"""
    if len(closes) < slow + signal:
        return {'dif': 0, 'dea': 0, 'hist': 0}

    ema_fast = closes[0]
    ema_slow = closes[0]
    ema_fast_list = [ema_fast]
    ema_slow_list = [ema_slow]

    multiplier_fast = 2 / (fast + 1)
    multiplier_slow = 2 / (slow + 1)

    for price in closes[1:]:
        ema_fast = (price - ema_fast) * multiplier_fast + ema_fast
        ema_slow = (price - ema_slow) * multiplier_slow + ema_slow
        ema_fast_list.append(ema_fast)
        ema_slow_list.append(ema_slow)

    dif_list = [f - s for f, s in zip(ema_fast_list, ema_slow_list)]

    dea = dif_list[0]
    dea_list = [dea]
    multiplier_signal = 2 / (signal + 1)

    for dif in dif_list[1:]:
        dea = (dif - dea) * multiplier_signal + dea
        dea_list.append(dea)

    latest_dif = dif_list[-1]
    latest_dea = dea_list[-1]
    hist = 2 * (latest_dif - latest_dea)

    return {'dif': round(latest_dif, 4), 'dea': round(latest_dea, 4), 'hist': round(hist, 4)}


def calc_kdj(closes, highs, lows, n=9, m1=3, m2=3):
    """KDJ指标"""
    if len(closes) < n:
        return {'k': 50, 'd': 50, 'j': 50}

    low_list = []
    for i in range(n - 1, len(closes)):
        low_list.append(min(lows[i-n+1:i+1]))

    high_list = []
    for i in range(n - 1, len(closes)):
        high_list.append(max(highs[i-n+1:i+1]))

    rsv_list = []
    for i in range(len(low_list)):
        idx = i + n - 1
        if high_list[i] == low_list[i]:
            rsv_list.append(50)
        else:
            rsv_list.append((closes[idx] - low_list[i]) / (high_list[i] - low_list[i]) * 100)

    k_vals = [50]
    d_vals = [50]
    for rsv in rsv_list:
        k_vals.append((m1 - 1) / m1 * k_vals[-1] + 1 / m1 * rsv)
        d_vals.append((m2 - 1) / m2 * d_vals[-1] + 1 / m2 * k_vals[-1])

    k = k_vals[-1]
    d = d_vals[-1]
    j = 3 * k - 2 * d

    return {'k': round(k, 1), 'd': round(d, 1), 'j': round(j, 1)}


def calc_ma(closes, period):
    """计算MA均线"""
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def tech_analysis(code, klines):
    """完整技术分析"""
    if not klines or len(klines) < 30:
        return None

    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]

    result = {
        'ma5': calc_ma(closes, 5),
        'ma10': calc_ma(closes, 10),
        'ma20': calc_ma(closes, 20),
        'ma60': calc_ma(closes, 60) if len(closes) >= 60 else None,
        'rsi': round(calc_rsi(closes), 1),
        'macd': calc_macd(closes),
        'kdj': calc_kdj(closes, highs, lows),
    }

    # 技术面评分 (0-30分)
    score = 0
    details = []

    price = closes[-1]

    # 均线评分 (0-10分)
    ma_score = 0
    if result['ma5'] and result['ma10'] and result['ma20']:
        if price > result['ma5'] > result['ma10'] > result['ma20']:
            ma_score = 10
            details.append("均线多头排列（+10分）")
        elif price > result['ma5'] and price > result['ma20']:
            ma_score = 7
            details.append("均线偏多排列（+7分）")
        elif price < result['ma5'] and result['ma5'] < result['ma10']:
            ma_score = 3
            details.append("均线空头排列（+3分）")
        else:
            ma_score = 5
            details.append("均线交叉震荡（+5分）")
    score += ma_score

    # RSI评分 (0-8分)
    rsi = result['rsi']
    if 30 <= rsi <= 70:
        rsi_score = 6
        details.append(f"RSI={rsi}处于中性区间（+6分）")
    elif rsi < 30:
        rsi_score = 8
        details.append(f"RSI={rsi}超卖区，反弹概率大（+8分）")
    else:
        rsi_score = 3
        details.append(f"RSI={rsi}超买区，回调风险（+3分）")
    score += rsi_score

    # MACD评分 (0-7分)
    macd = result['macd']
    if macd['dif'] > macd['dea']:
        macd_score = 6
        details.append(f"MACD金叉，DIF={macd['dif']}>DEA={macd['dea']}（+6分）")
    else:
        macd_score = 3
        details.append(f"MACD死叉，DIF={macd['dif']}<DEA={macd['dea']}（+3分）")
    score += macd_score

    # KDJ评分 (0-5分)
    kdj = result['kdj']
    if kdj['k'] > kdj['d'] and kdj['j'] < 100:
        kdj_score = 4
        details.append(f"KDJ金叉K={kdj['k']}>D={kdj['d']},J={kdj['j']}（+4分）")
    elif kdj['j'] > 100:
        kdj_score = 2
        details.append(f"KDJ超买，J={kdj['j']}>100（+2分）")
    else:
        kdj_score = 3
        details.append(f"KDJ中性，K={kdj['k']},D={kdj['d']}（+3分）")
    score += kdj_score

    result['tech_score'] = min(score, 30)
    result['tech_details'] = details

    # 短线趋势判断
    if result['tech_score'] >= 24:
        trend = "强势上涨"
        hold_days = "1-2天"
    elif result['tech_score'] >= 18:
        trend = "震荡上行"
        hold_days = "2-4天"
    elif result['tech_score'] >= 12:
        trend = "横盘震荡"
        hold_days = "3-5天"
    else:
        trend = "弱势下跌"
        hold_days = "观望"

    result['short_trend'] = trend
    result['hold_days'] = hold_days

    # 参考价位
    avg_atr = sum(h - l for h, l in zip(highs[-14:], lows[-14:])) / 14 if len(highs) >= 14 else price * 0.03
    result['buy_price'] = round(price - 1.5 * avg_atr, 2)
    result['target_price'] = round(price + 2 * avg_atr, 2)
    result['stop_loss'] = round(price - 2.5 * avg_atr, 2)

    return result


# ============================================================
# 分析引擎主模块
# ============================================================

def get_valuation_level(pe):
    """估值水平判断"""
    if not pe or pe <= 0:
        return '无法判断（PE为负或零）'
    if pe < 15:
        return '低估（PE < 15x）'
    if pe < 25:
        return '合理偏低（15x ≤ PE < 25x）'
    if pe < 35:
        return '合理偏高（25x ≤ PE < 35x）'
    if pe < 50:
        return '高估（35x ≤ PE < 50x）'
    return '严重高估（PE ≥ 50x）'


def get_rating_simple(pe, growth=0):
    """综合评级"""
    if not pe or pe <= 0:
        return {'level': '中性', 'text': '无法判断估值水平，建议观望'}
    if pe < 20 and growth > 15:
        return {'level': '强烈买入', 'text': '估值合理且高增长'}
    if pe < 25 and growth > 10:
        return {'level': '买入', 'text': '估值合理，增长可期'}
    if pe < 30 and growth > 5:
        return {'level': '增持', 'text': '估值略高但仍有增长'}
    if pe < 40:
        return {'level': '中性', 'text': '估值偏高，需观察'}
    return {'level': '减持', 'text': '估值过高，注意风险'}


def load_knowledge_cache(code):
    """加载知识库缓存"""
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'knowledge_cache')
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f'{code}.json')

    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                age = time.time() - cache.get('cached_at', 0)
                if age < 86400:  # 24小时内有效
                    return cache
        except:
            pass
    return None


def save_knowledge_cache(code, data):
    """保存知识库缓存"""
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'knowledge_cache')
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f'{code}.json')
    data['cached_at'] = time.time()
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def search_web_news(query, max_results=5):
    """
    通过东方财富新闻搜索获取公司最新动态
    来源：eastmoney.com 财富号/新闻
    """
    results = []
    try:
        encoded = urllib.parse.quote(query)
        # 东方财富新闻搜索API
        url = f'https://search-api-web.eastmoney.com/search/jsonp?cb=callback&param={{"uid":"","keyword":"{query}","type":["cmsArticle"],"client":"web","clientType":"web","clientVersion":"curr","param":{{"cmsArticle":{{"field":["title","date","art_url"],"highlight":false,"pageSize":5,"pageIndex":1}}}}}}'
        req = urllib.request.Request(
            f'https://search-api-web.eastmoney.com/search/jsonp?cb=cb&param={urllib.parse.quote(json.dumps({"uid":"","keyword":query,"type":["cmsArticle"],"client":"web","clientType":"web","clientVersion":"curr","param":{"cmsArticle":{"field":["title","date","art_url"],"highlight":False,"pageSize":5,"pageIndex":1}}}))}',
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.eastmoney.com/'}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read().decode('utf-8', errors='replace')
            # 解析callback包装的JSON
            m = re.search(r'cb\((.*)\)', content, re.DOTALL)
            if m:
                data = json.loads(m.group(1))
                articles = data.get('result', {}).get('cmsArticle', {}).get('data', [])
                for a in articles[:max_results]:
                    results.append({
                        'title': a.get('title', ''),
                        'date': a.get('date', ''),
                        'url': a.get('art_url', ''),
                        'source': '东方财富网',
                    })
    except Exception:
        pass

    # 备用：东方财富个股新闻
    if not results:
        try:
            code_search = query.replace('股', '').replace('最新', '').strip()
            url = f'https://np-anotice-stock.eastmoney.com/api/security/ann?cb=jQuery&sr=-1&page_size=5&page_index=1&ann_type=A&client_source=web&f_node=0&s_node=0'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                content = resp.read().decode('utf-8', errors='replace')
        except Exception:
            pass

    return results


def fetch_eastmoney_news(code, name):
    """
    获取东方财富个股新闻列表
    来源：东方财富个股新闻API
    """
    results = []
    try:
        url = f'https://np-listapi.eastmoney.com/comm/web/getListInfo?cb=cb&client=web&type=1&mTypeAndCode=1%2C{code}&pageSize=8&pageIndex=1&callback=cb'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': f'https://quote.eastmoney.com/concept/{code}.html'
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read().decode('utf-8', errors='replace')
            m = re.search(r'cb\((.*)\)', content, re.DOTALL)
            if m:
                data = json.loads(m.group(1))
                items = data.get('data', {}).get('list', [])
                for item in items[:6]:
                    results.append({
                        'title': item.get('title', ''),
                        'date': item.get('showTime', '')[:10],
                        'url': item.get('articleUrl', ''),
                        'source': '东方财富网',
                    })
    except Exception:
        pass

    # 备用：新浪财经个股新闻
    if not results:
        try:
            prefix = 'sh' if code.startswith(('6', '9')) else 'sz'
            url = f'https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsInfoHidden.php?stockid={prefix}{code}&Pgoffset=0&num=6'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                content = resp.read().decode('gb2312', errors='replace')
                # 解析html中的新闻链接
                items = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>.*?(\d{4}-\d{2}-\d{2})', content, re.DOTALL)
                for href, title, date in items[:6]:
                    title = title.strip()
                    if len(title) > 5:
                        results.append({
                            'title': title,
                            'date': date,
                            'url': href if href.startswith('http') else 'https://finance.sina.com.cn' + href,
                            'source': '新浪财经',
                        })
        except Exception:
            pass

    return results


def fetch_business_segments(code, name, industry):
    """
    获取业务板块信息
    来源：东方财富公司概况
    """
    result = {
        'segments': [],
        'main_business': '',
        'source': '',
        'source_url': '',
    }
    try:
        # 东方财富F10公司介绍
        url = f'https://emweb.securities.eastmoney.com/PC_HSF10/CompanyIntroduction/Index?type=web&code={code}'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://emweb.securities.eastmoney.com/'
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='replace')
            # 提取主营业务
            m = re.search(r'主营业务[^<]*</[^>]+>.*?<[^>]+>([^<]{20,500})', html, re.DOTALL)
            if m:
                result['main_business'] = re.sub(r'\s+', ' ', m.group(1)).strip()[:300]
                result['source'] = '东方财富F10'
                result['source_url'] = url
    except Exception:
        pass

    # 备用：通过同花顺获取公司介绍
    if not result['main_business']:
        try:
            url = f'https://basic.10jqka.com.cn/{code}/'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode('gbk', errors='replace')
                # 提取公司简介
                m = re.search(r'主营业务.*?<p[^>]*>([^<]{30,500})', html, re.DOTALL)
                if m:
                    result['main_business'] = re.sub(r'\s+', ' ', m.group(1)).strip()[:300]
                    result['source'] = '同花顺F10'
                    result['source_url'] = url
        except Exception:
            pass

    return result


# 行业分类映射（申万行业部分映射）
INDUSTRY_MAP = {
    '600519': '白酒', '000858': '白酒', '000568': '白酒',
    '601318': '保险', '601628': '保险',
    '000002': '房地产开发', '001979': '房地产开发',
    '300750': '锂电池', '002594': '新能源汽车',
    '603629': '电子零部件/算力租赁',
    '688981': '半导体', '002371': '半导体设备',
    '601012': '光伏', '688599': '光伏组件',
    '300059': '互联网金融', '600570': '金融IT',
    '002415': '安防', '002230': 'AI语音',
}

# 行业同行映射
PEER_MAP = {
    '603629': ['002229', '300502', '000977'],
    '600519': ['000858', '000568', '002304'],
    '601318': ['601628', '601601', '601336'],
    '300750': ['002594', '300014', '688567'],
}


def get_industry(code, name):
    """获取行业分类"""
    if code in INDUSTRY_MAP:
        return INDUSTRY_MAP[code]
    # 简单规则推断
    if code.startswith('60'):
        if '银行' in name:
            return '银行'
        if '证券' in name:
            return '证券'
        if '保险' in name:
            return '保险'
        return '制造业'
    if code.startswith('00'):
        return '制造业'
    if code.startswith('30'):
        return '创业板'
    return '其他'


def get_peers(code):
    """获取同行公司列表"""
    return PEER_MAP.get(code, [])


def analyze_stock_full(code):
    """
    全维度股票分析 - 主入口
    返回完整的13章分析报告JSON
    """
    start_time = time.time()

    # 1. 获取实时行情
    quote = get_realtime_quote(code)
    if not quote:
        return {'error': f'获取股票 {code} 行情数据失败'}

    name = quote['name']
    price = quote['price']
    pe_ttm = quote['pe_ttm']
    market_cap = quote['market_cap']

    # 2. 获取财务数据
    financials = get_financial_data_sina(code)

    # 3. 获取K线数据
    klines = get_kline_data(code, 120)

    # 4. 技术分析
    tech = tech_analysis(code, klines)

    # 5. 获取知识库缓存
    knowledge = load_knowledge_cache(code)

    # 5b. 获取最新新闻（东方财富/新浪财经）
    news_list = fetch_eastmoney_news(code, name)

    # 5c. 获取业务板块信息（东方财富F10）
    biz_info = fetch_business_segments(code, name, get_industry(code, name))

    # 6. 行业分类
    industry = get_industry(code, name)

    # 7. 同行公司
    peers = get_peers(code)

    # 8. 估值分析
    valuation = analyze_valuation(price, pe_ttm, market_cap, financials)

    # 9. 构建报告
    report = build_report(code, name, quote, financials, tech, knowledge, industry, peers, valuation, news_list, biz_info)

    report['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    report['analysis_time'] = f'{time.time() - start_time:.1f}秒'
    report['data_sources'] = {
        '实时行情': '腾讯行情API (qt.gtimg.cn)',
        '财务报表': '新浪财经API (quotes.sina.cn)',
        'K线数据': '腾讯K线接口 (web.ifzq.gtimg.cn)',
        '知识库': 'IMA知识库缓存',
    }

    return report


def analyze_valuation(price, pe_ttm, market_cap, financials):
    """估值分析"""
    result = {
        'pe_ttm': pe_ttm,
        'pe_level': get_valuation_level(pe_ttm),
    }

    # PE法估值
    if pe_ttm and pe_ttm > 0:
        # 假设行业合理PE 15-25
        reasonable_pe_low = 15
        reasonable_pe_high = 25
        fair_low = price * (reasonable_pe_low / pe_ttm)
        fair_high = price * (reasonable_pe_high / pe_ttm)
        result['pe_method'] = {
            'reasonable_pe_range': f'{reasonable_pe_low}x - {reasonable_pe_high}x',
            'fair_price_low': round(fair_low, 2),
            'fair_price_high': round(fair_high, 2),
        }

    # DCF简化估值
    if market_cap and market_cap > 0:
        # 假设FCF = 净利润 * 0.7, WACC = 10%, g = 3%
        result['dcf_method'] = {
            'assumptions': {
                'wacc': '10%',
                'growth_rate': '3%',
                'fcf_ratio': '70%（净利润×0.7估算FCF）',
            },
            'note': 'DCF精确估值需要完整的现金流预测模型，此处仅作参考框架'
        }

    # PEG分析
    if pe_ttm and pe_ttm > 0:
        result['peg_method'] = {
            'formula': 'PE / 净利润增速(%)',
            'benchmark': 'PEG < 1 低估, PEG = 1-1.5 合理, PEG > 1.5 高估',
        }

    return result


def extract_financial_summary(financials):
    """提取关键财务指标"""
    summary = {
        'revenue': [],
        'net_profit': [],
        'total_assets': [],
        'total_equity': [],
        'operating_cf': [],
    }

    # 利润表
    for item in financials.get('profit', [])[:3]:
        report_date = item.get('report_date', '')[:4] if isinstance(item.get('report_date'), str) else str(item.get('report_date', ''))[:4]
        summary['revenue'].append({
            'year': report_date,
            'value': safe_float(item.get('operating_revenue', 0)) / 1e8
        })
        summary['net_profit'].append({
            'year': report_date,
            'value': safe_float(item.get('net_profit_attr_p', 0)) / 1e8
        })

    # 资产负债表
    for item in financials.get('balance', [])[:3]:
        report_date = item.get('report_date', '')[:4] if isinstance(item.get('report_date'), str) else str(item.get('report_date', ''))[:4]
        summary['total_assets'].append({
            'year': report_date,
            'value': safe_float(item.get('total_assets', 0)) / 1e8
        })
        summary['total_equity'].append({
            'year': report_date,
            'value': safe_float(item.get('total_equity_attr_p', 0)) / 1e8
        })

    # 现金流量表
    for item in financials.get('cashflow', [])[:3]:
        report_date = item.get('report_date', '')[:4] if isinstance(item.get('report_date'), str) else str(item.get('report_date', ''))[:4]
        summary['operating_cf'].append({
            'year': report_date,
            'value': safe_float(item.get('net_cf_operating', 0)) / 1e8
        })

    return summary


def calc_cagr(values):
    """计算复合增长率"""
    if len(values) < 2 or values[0] == 0:
        return 0
    years = len(values) - 1
    return round((pow(values[-1] / values[0], 1 / years) - 1) * 100, 1)


def build_report(code, name, quote, financials, tech, knowledge, industry, peers, valuation, news_list=None, biz_info=None):
    """构建完整13章报告"""

    fin_summary = extract_financial_summary(financials)
    price = quote['price']
    pe_ttm = quote['pe_ttm']
    market_cap = quote['market_cap']
    pb = quote['pb']

    # 计算增长率
    revenues = [item['value'] for item in fin_summary['revenue']]
    profits = [item['value'] for item in fin_summary['net_profit']]

    rev_cagr = calc_cagr(revenues) if len(revenues) >= 2 else 0
    profit_cagr = calc_cagr(profits) if len(profits) >= 2 else 0

    # 评级
    rating = get_rating_simple(pe_ttm, profit_cagr)

    report = {}

    # ==================== 第1章：概述 ====================
    report['ch1_overview'] = {
        'title': f'{name}（{code}）全维度价值分析报告',
        'stock_name': name,
        'stock_code': code,
        'industry': industry,
        'current_price': f'{price:.2f}元',
        'market_cap': f'{market_cap:.2f}亿元' if market_cap else 'N/A',
        'pe_ttm': f'{pe_ttm:.2f}x' if pe_ttm else 'N/A',
        'pb': f'{pb:.2f}x' if pb else 'N/A',
        'change_pct': f'{quote["change_pct"]:+.2f}%',
        'rating': rating,
        'summary': generate_overview_text(name, code, industry, price, pe_ttm, market_cap, rating),
    }

    # ==================== 第2章：公司最新动态 ====================
    # 数据来源优先级：IMA知识库缓存 > 东方财富新闻 > 新浪财经
    news_items = news_list or []
    knowledge_updates = knowledge.get('updates', []) if knowledge else []
    news_source_desc = '东方财富网/新浪财经（公开网络信息）' if news_items and not knowledge_updates else ('IMA知识库缓存' if knowledge_updates else '暂无数据')

    report['ch2_news'] = {
        'title': '公司最新动态',
        'source': news_source_desc,
        'source_note': '以下新闻来自公开互联网，数据已注明来源，如有时效性问题请以官方公告为准。',
        'knowledge_updates': knowledge_updates,  # IMA知识库（如有）
        'web_news': news_items,  # 东方财富/新浪财经
        'total_count': len(knowledge_updates) + len(news_items),
    }

    # ==================== 第3章：业务板块分析 ====================
    biz = biz_info or {}
    biz_main = biz.get('main_business', '')
    biz_source = biz.get('source', '')
    biz_url = biz.get('source_url', '')

    report['ch3_business'] = {
        'title': '业务板块分析',
        'main_business_desc': biz_main if biz_main else f'主营业务数据获取中，请参考{name}官方公告。',
        'main_business_source': biz_source,
        'main_business_source_url': biz_url,
        'revenue_structure': fin_summary['revenue'],
        'profit_structure': fin_summary['net_profit'],
        'revenue_cagr': f'{rev_cagr}%' if rev_cagr else 'N/A',
        'profit_cagr': f'{profit_cagr}%' if profit_cagr else 'N/A',
        'analysis': generate_business_analysis(name, industry, rev_cagr, profit_cagr),
        'data_source': '新浪财经API (quotes.sina.cn) — 财报数据',
    }

    # ==================== 第4章：行业深度分析 ====================
    report['ch4_industry'] = {
        'title': '行业深度分析',
        'industry': industry,
        'chain_analysis': generate_industry_chain(industry),
        'competition': get_industry_competition(industry),
        'outlook': get_industry_outlook(industry),
    }

    # ==================== 第5章：价值投资分析 ====================
    report['ch5_value_investing'] = {
        'title': '价值投资分析（基于《股市真规则》）',
        'ten_minute_test': perform_ten_minute_test(quote, fin_summary),
        'moat_analysis': analyze_moat(name, industry),
        'financial_health': check_financial_health(fin_summary),
        'dcf_valuation': valuation.get('dcf_method', {}),
    }

    # ==================== 第6章：综合分析 ====================
    report['ch6_comprehensive'] = {
        'title': '综合分析（基本面+新闻面+资金面+技术面）',
        'fundamental_score': calculate_fundamental_score(pe_ttm, pb, rev_cagr, profit_cagr),
        'news_sentiment': '待获取（需IMA知识库数据）',
        'capital_flow': '待获取（需资金流向接口）',
        'tech_reference': tech,
        'total_score': calculate_total_score(pe_ttm, pb, rev_cagr, profit_cagr),
    }

    # ==================== 第7章：同行对比分析 ====================
    report['ch7_peers'] = {
        'title': '同行对比分析',
        'peers': peers,
        'source': '统一数据源：腾讯行情API',
        'note': '同行实时数据需逐个获取，当前为简化版',
    }

    # ==================== 第8章：净利润预测依据 ====================
    report['ch8_profit_forecast'] = {
        'title': '净利润预测依据',
        'historical_revenue': fin_summary['revenue'],
        'historical_profit': fin_summary['net_profit'],
        'forecast_method': '基于历史增速趋势外推 + 行业增速参考',
        'prediction': predict_profit(fin_summary),
    }

    # ==================== 第9章：目标价来源依据 ====================
    report['ch9_target_price'] = {
        'title': '目标价来源依据',
        'pe_method': valuation.get('pe_method', {}),
        'dcf_method': valuation.get('dcf_method', {}),
        'peg_method': valuation.get('peg_method', {}),
        'comprehensive': calculate_target_price(price, pe_ttm, profit_cagr),
    }

    # ==================== 第10章：两种方法对比 ====================
    report['ch10_comparison'] = {
        'title': '两种方法的对比和整合结论',
        'value_investing_rating': rating['level'],
        'comprehensive_score': calculate_total_score(pe_ttm, pb, rev_cagr, profit_cagr),
        'conclusion': generate_integrated_conclusion(rating),
    }

    # ==================== 第11章：风险提示 ====================
    report['ch11_risks'] = {
        'title': '风险提示',
        'risks': generate_risk_warnings(industry, pe_ttm, market_cap),
    }

    # ==================== 第12章：信息来源和时效性 ====================
    report['ch12_sources'] = {
        'title': '信息来源和时效性',
        'sources': [
            {'name': '腾讯行情API', 'url': 'qt.gtimg.cn', 'data_type': '实时行情', 'time': datetime.now().strftime('%Y-%m-%d %H:%M')},
            {'name': '新浪财经API', 'url': 'quotes.sina.cn', 'data_type': '财务报表', 'time': datetime.now().strftime('%Y-%m-%d %H:%M')},
            {'name': '腾讯K线接口', 'url': 'web.ifzq.gtimg.cn', 'data_type': 'K线数据', 'time': datetime.now().strftime('%Y-%m-%d %H:%M')},
            {'name': 'IMA知识库缓存', 'url': '本地缓存', 'data_type': '研报/公告/问答', 'time': knowledge and knowledge.get('cached_at', 'N/A') or 'N/A'},
        ],
        'disclaimer': '本报告由AI自动生成，仅供参考，不构成投资建议。股市有风险，投资需谨慎。'
    }

    # ==================== 第13章：技术面最新分析 ====================
    report['ch13_technical'] = {
        'title': '技术面最新分析（量化短线意见）',
        'current_price': price,
        'kline_period': '最近120个交易日',
        'key_levels': {
            'ma5': tech['ma5'] if tech else None,
            'ma10': tech['ma10'] if tech else None,
            'ma20': tech['ma20'] if tech else None,
            'ma60': tech['ma60'] if tech else None,
        },
        'indicators': {
            'rsi': tech['rsi'] if tech else None,
            'macd': tech['macd'] if tech else None,
            'kdj': tech['kdj'] if tech else None,
        },
        'tech_score': tech['tech_score'] if tech else 0,
        'tech_details': tech['tech_details'] if tech else [],
        'short_trend': tech['short_trend'] if tech else '数据不足',
        'hold_days': tech['hold_days'] if tech else '数据不足',
        'buy_price': tech['buy_price'] if tech else None,
        'target_price_short': tech['target_price'] if tech else None,
        'stop_loss': tech['stop_loss'] if tech else None,
        'data_source': {
            'kline': '腾讯K线接口 (web.ifzq.gtimg.cn)',
            'indicators': 'MA(简单移动平均)、RSI(Wilder平滑)、MACD(EMA12/26)、KDJ(9/3/3)',
        }
    }

    return report


# ============================================================
# 报告各章节内容生成函数
# ============================================================

def generate_overview_text(name, code, industry, price, pe, mcap, rating):
    """生成概述文本"""
    return (
        f"{name}（{code}）是{industry}领域的上市公司。"
        f"当前股价{price:.2f}元，总市值{mcap:.2f}亿元，"
        f"市盈率(PE-TTM)为{pe:.2f}x。"
        f"综合评级：{rating['level']}。"
        f"{rating['text']}。"
    )


def generate_business_analysis(name, industry, rev_cagr, profit_cagr):
    """生成业务分析"""
    growth_desc = '高速增长' if profit_cagr > 20 else ('稳健增长' if profit_cagr > 5 else '增长放缓')
    return f"{name}近三年营收复合增速{rev_cagr}%，净利润复合增速{profit_cagr}%，属于{industry}行业{growth_desc}型公司。"


def generate_industry_chain(industry):
    """生成产业链分析"""
    chains = {
        '白酒': {'上游': '粮食种植、包装材料', '中游': '白酒酿造', '下游': '经销商、消费者'},
        '锂电池': {'上游': '锂矿、钴矿、石墨', '中游': '电池制造', '下游': '新能源车、储能'},
        '半导体': {'上游': '硅片、光刻胶、设备', '中游': '芯片设计/制造', '下游': '消费电子、汽车'},
        '保险': {'上游': None, '中游': '保险产品设计与销售', '下游': None},
    }
    return chains.get(industry, {'上游': '原材料供应商', '中游': industry, '下游': '终端客户'})


def get_industry_competition(industry):
    """获取行业竞争格局"""
    return {
        '状态': '分析中（需要更多行业数据）',
        'CR5': '待获取',
        'entry_barrier': '取决于具体细分领域',
    }


def get_industry_outlook(industry):
    """获取行业前景"""
    outlooks = {
        '白酒': {'trend': '消费升级驱动高端化', 'risk': '政策调控风险'},
        '锂电池': {'trend': '新能源转型持续推动需求', 'risk': '产能过剩风险'},
        '半导体': {'trend': '国产替代+AI需求双驱动', 'risk': '技术封锁和周期波动'},
        '保险': {'trend': '长期保障需求增长', 'risk': '利率下行压缩利差'},
    }
    return outlooks.get(industry, {'trend': '需进一步分析', 'risk': '需进一步分析'})


def perform_ten_minute_test(quote, fin_summary):
    """十分钟测试"""
    results = []
    pe = quote['pe_ttm']
    pb = quote['pb']

    # 测试1：PE是否合理
    if pe and 0 < pe < 50:
        results.append({'test': 'PE合理性', 'result': '通过', 'detail': f'PE-TTM={pe:.2f}x，在合理范围内'})
    elif pe and pe >= 50:
        results.append({'test': 'PE合理性', 'result': '注意', 'detail': f'PE-TTM={pe:.2f}x，估值偏高'})
    else:
        results.append({'test': 'PE合理性', 'result': '不适用', 'detail': 'PE为负或零'})

    # 测试2：PB是否合理
    if pb and 0 < pb < 10:
        results.append({'test': 'PB合理性', 'result': '通过', 'detail': f'PB={pb:.2f}x'})
    else:
        results.append({'test': 'PB合理性', 'result': '注意', 'detail': f'PB={pb:.2f}x' if pb else 'N/A'})

    # 测试3：盈利是否稳定
    profits = [item['value'] for item in fin_summary.get('net_profit', [])]
    if len(profits) >= 2 and all(p > 0 for p in profits):
        results.append({'test': '盈利稳定性', 'result': '通过', 'detail': '连续盈利'})
    else:
        results.append({'test': '盈利稳定性', 'result': '注意', 'detail': '存在亏损年份'})

    return results


def analyze_moat(name, industry):
    """护城河分析"""
    return {
        'brand': '需具体分析品牌价值',
        'switching_cost': '需具体分析客户粘性',
        'network_effect': '需具体分析网络效应',
        'cost_advantage': '需具体分析成本优势',
        'note': f'{name}作为{industry}企业，护城河深度需结合具体业务分析'
    }


def check_financial_health(fin_summary):
    """财务健康检查"""
    results = []

    # 检查1：自由现金流
    ocf_values = [item['value'] for item in fin_summary.get('operating_cf', [])]
    if ocf_values and any(v > 0 for v in ocf_values):
        results.append({'signal': '现金流健康', 'status': 'OK', 'detail': '经营现金流为正'})
    else:
        results.append({'signal': '现金流预警', 'status': 'WARN', 'detail': '经营现金流为负或未知'})

    # 检查2：应收账款
    results.append({'signal': '应收账款', 'status': 'CHECK', 'detail': '需查看原始报表'})

    # 检查3：负债率
    assets = [item['value'] for item in fin_summary.get('total_assets', [])]
    equity = [item['value'] for item in fin_summary.get('total_equity', [])]
    if assets and equity and assets[-1] > 0:
        debt_ratio = (assets[-1] - equity[-1]) / assets[-1] * 100
        status = 'OK' if debt_ratio < 70 else 'WARN'
        results.append({'signal': f'资产负债率{debt_ratio:.1f}%', 'status': status,
                        'detail': '低于70%为健康' if debt_ratio < 70 else '高于70%，需关注'})

    return results


def calculate_fundamental_score(pe, pb, rev_cagr, profit_cagr):
    """基本面评分（0-35分）"""
    score = 0
    details = []

    if pe and 0 < pe < 25:
        score += 15
        details.append('PE合理（+15分）')
    elif pe and 25 <= pe < 50:
        score += 10
        details.append('PE偏高（+10分）')
    else:
        score += 5
        details.append('PE异常（+5分）')

    if profit_cagr > 20:
        score += 10
        details.append('高增长（+10分）')
    elif profit_cagr > 10:
        score += 7
        details.append('中等增长（+7分）')
    else:
        score += 4
        details.append('增长一般（+4分）')

    if pb and 0 < pb < 5:
        score += 5
        details.append('PB合理（+5分）')
    else:
        score += 3
        details.append('PB偏高（+3分）')

    if rev_cagr > 10:
        score += 5
        details.append('营收稳健增长（+5分）')
    else:
        score += 2
        details.append('营收增速一般（+2分）')

    return {'score': min(score, 35), 'details': details}


def calculate_total_score(pe, pb, rev_cagr, profit_cagr):
    """综合评分（0-100分）"""
    fundamental = calculate_fundamental_score(pe, pb, rev_cagr, profit_cagr)
    # 简化：基本面40% + 估值20% + 增长20% + 技术面20%
    return {
        'fundamental': fundamental['score'],
        'max_fundamental': 35,
        'health_warning': '完整评分需资金面和新闻面数据',
    }


def predict_profit(fin_summary):
    """利润预测"""
    profits = [item['value'] for item in fin_summary['net_profit']]
    revenues = [item['value'] for item in fin_summary['revenue']]

    result = {'historical': []}
    for p, r in zip(profits, revenues):
        result['historical'].append({
            'year': '年份',
            'revenue': f'{r:.2f}亿',
            'net_profit': f'{p:.2f}亿',
        })

    if len(profits) >= 2:
        growth = (profits[-1] - profits[-2]) / abs(profits[-2]) * 100 if profits[-2] != 0 else 0
        next_year = profits[-1] * (1 + growth / 200)  # 增速减半保守估计
        result['forecast_2026e'] = {
            'value': f'{next_year:.2f}亿',
            'method': f'基于近两年增速{growth:.1f}%，给予50%折扣率保守估计',
        }

    return result


def calculate_target_price(price, pe, profit_cagr):
    """目标价计算"""
    result = {}
    if pe and pe > 0 and price > 0:
        # PE法
        fair_pe = min(max(15, profit_cagr * 0.8 if profit_cagr > 0 else 15), 30)
        target_pe = fair_pe
        target_low = price * (fair_pe / pe)
        target_high = price * ((fair_pe + 5) / pe)

        result['pe_method'] = {
            'fair_pe': f'{fair_pe:.0f}x',
            'target_range': f'{target_low:.2f} - {target_high:.2f}元',
            'upside': f'{((target_low+target_high)/2/price - 1)*100:.1f}%',
        }

    return result


def generate_integrated_conclusion(rating):
    """综合结论"""
    conclusions = {
        '强烈买入': '各项指标均表现优异，建议积极配置。',
        '买入': '整体估值合理，具有投资价值，建议逢低买入。',
        '增持': '基本面良好但估值略高，可在回调时适当增持。',
        '中性': '当前估值缺乏明显吸引力，建议观望。',
        '减持': '估值偏高且增长放缓，建议减持控制风险。',
    }
    return conclusions.get(rating['level'], '建议结合个人风险偏好综合判断。')


def generate_risk_warnings(industry, pe, mcap):
    """生成风险提示"""
    risks = [
        '宏观经济波动风险：经济下行可能影响公司业绩',
        '行业竞争风险：行业竞争加剧可能导致利润率下降',
        '估值风险：当前PE' + (f'{pe:.1f}x，估值偏高需关注回调风险' if pe > 30 else f'{pe:.1f}x，估值相对合理'),
        '市场风险：股市整体波动可能带来短期亏损',
        '流动性风险：市值' + (f'{mcap:.0f}亿，流通性' + ('较好' if mcap > 100 else '一般')),
        '⚠️ 本报告由AI自动生成，数据分析可能存在局限性，请务必结合自身判断。',
        '⚠️ 股市有风险，投资需谨慎。本报告不构成任何投资建议。',
    ]
    return risks


# ============================================================
# 测试入口
# ============================================================

if __name__ == '__main__':
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else '603629'
    print(f"分析 {code} ...")
    report = analyze_stock_full(code)
    print(json.dumps(report, ensure_ascii=False, indent=2))

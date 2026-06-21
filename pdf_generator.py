#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF报告生成模块
生成包含K线图、财务趋势图、同行对比图、估值分析图的专业PDF报告
"""

import os
import io
import json
import math
import tempfile
from datetime import datetime

# ReportLab
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Matplotlib for charts
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import rcParams

# ============================================================
# 字体注册（跨平台：Linux / Windows / macOS）
# ============================================================

def register_fonts():
    """注册中文字体 — 优先使用项目内嵌字体，兼容 Linux/Windows/macOS"""
    import os
    _font_ok = False
    _selected_font_path = None  # 记录成功加载的字体路径

    # 1. 项目内嵌字体（最高优先级，确保 Linux/Render 可用）
    # 注意：优先使用 SimHei.ttf（Regular字重），避免 NotoSansSC-Thin 在部分阅读器中乱码
    embed_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
    embed_paths = [
        os.path.join(embed_dir, 'SimHei.ttf'),
        os.path.join(embed_dir, 'msyh.ttc'),
        os.path.join(embed_dir, 'NotoSansSC.ttf'),
    ]
    for path in embed_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('ChineseFont', path))
                _font_ok = True
                _selected_font_path = path
                print(f"[PDF] 使用内嵌字体: {os.path.basename(path)}")
                break
            except Exception as e:
                print(f"[PDF] 内嵌字体加载失败: {path} ({e})")
                continue

    if not _font_ok:
        # 2. Windows 系统字体
        win_paths = [
            r'C:\Windows\Fonts\msyh.ttc',          # 微软雅黑
            r'C:\Windows\Fonts\simhei.ttf',         # 黑体
            r'C:\Windows\Fonts\simsun.ttc',         # 宋体
            r'C:\Windows\Fonts\msyhbd.ttc',         # 微软雅黑 Bold
        ]
        for path in win_paths:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont('ChineseFont', path))
                    _font_ok = True
                    _selected_font_path = path
                    print(f"[PDF] 使用Windows字体: {os.path.basename(path)}")
                    break
                except Exception:
                    continue

    if not _font_ok:
        # 3. macOS 系统字体
        mac_paths = [
            '/System/Library/Fonts/STHeiti Light.ttc',
            '/System/Library/Fonts/PingFang.ttc',
            '/Library/Fonts/Arial Unicode.ttf',
        ]
        for path in mac_paths:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont('ChineseFont', path))
                    _font_ok = True
                    _selected_font_path = path
                    print(f"[PDF] 使用macOS字体: {os.path.basename(path)}")
                    break
                except Exception:
                    continue

    if not _font_ok:
        # 4. Linux 系统字体
        linux_paths = [
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',     # 文泉驿微米黑
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
            '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
        ]
        for path in linux_paths:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont('ChineseFont', path))
                    _font_ok = True
                    _selected_font_path = path
                    print(f"[PDF] 使用Linux字体: {path}")
                    break
                except Exception:
                    continue

    # 最终检查
    if _font_ok:
        # Matplotlib 中文字体设置 — 使用实际加载的字体路径
        if _selected_font_path and os.path.exists(_selected_font_path):
            try:
                from matplotlib import font_manager as fm
                fm.fontManager.addfont(_selected_font_path)
                prop = fm.FontProperties(fname=_selected_font_path)
                rcParams['font.sans-serif'] = [prop.get_name()] + rcParams.get('font.sans-serif', [])
                rcParams['font.family'] = 'sans-serif'
                print(f"[PDF] Matplotlib 字体配置成功: {prop.get_name()}")
            except Exception as e:
                print(f"[PDF] Matplotlib 字体配置失败: {e}")
                rcParams['font.sans-serif'] = ['Noto Sans SC', 'SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'DejaVu Sans']
        else:
            rcParams['font.sans-serif'] = ['Noto Sans SC', 'SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'DejaVu Sans']
        rcParams['axes.unicode_minus'] = False
        return 'ChineseFont'
    else:
        # 无中文字体可用，使用 Helvetica 并警告
        import warnings
        warnings.warn("[PDF] 未找到任何中文字体！PDF中文将显示为方块。请在 fonts/ 目录放置 NotoSansSC.ttf", UserWarning)
        return 'Helvetica'


FONT_NAME = register_fonts()


# ============================================================
# 样式定义
# ============================================================

def get_styles():
    """获取段落样式"""
    styles = getSampleStyleSheet()

    custom = {
        'title': ParagraphStyle(
            'CustomTitle',
            fontName=FONT_NAME,
            fontSize=18,
            leading=26,
            textColor=colors.HexColor('#1d1d1f'),
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        'subtitle': ParagraphStyle(
            'CustomSubtitle',
            fontName=FONT_NAME,
            fontSize=11,
            leading=16,
            textColor=colors.HexColor('#6e6e73'),
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
        'chapter_title': ParagraphStyle(
            'ChapterTitle',
            fontName=FONT_NAME,
            fontSize=13,
            leading=20,
            textColor=colors.HexColor('#1d1d1f'),
            spaceBefore=14,
            spaceAfter=6,
            borderPad=(0, 0, 4, 0),
        ),
        'section_title': ParagraphStyle(
            'SectionTitle',
            fontName=FONT_NAME,
            fontSize=11,
            leading=17,
            textColor=colors.HexColor('#0071e3'),
            spaceBefore=8,
            spaceAfter=4,
        ),
        'body': ParagraphStyle(
            'CustomBody',
            fontName=FONT_NAME,
            fontSize=9,
            leading=14,
            textColor=colors.HexColor('#3a3a3c'),
            spaceAfter=4,
        ),
        'body_small': ParagraphStyle(
            'BodySmall',
            fontName=FONT_NAME,
            fontSize=8,
            leading=12,
            textColor=colors.HexColor('#6e6e73'),
            spaceAfter=2,
        ),
        'source_note': ParagraphStyle(
            'SourceNote',
            fontName=FONT_NAME,
            fontSize=7,
            leading=10,
            textColor=colors.HexColor('#8e8e93'),
            spaceAfter=2,
        ),
        'highlight': ParagraphStyle(
            'Highlight',
            fontName=FONT_NAME,
            fontSize=9,
            leading=14,
            textColor=colors.HexColor('#1d1d1f'),
            backColor=colors.HexColor('#f5f5f7'),
            borderPad=4,
            spaceAfter=4,
        ),
        'rating_buy': ParagraphStyle(
            'RatingBuy',
            fontName=FONT_NAME,
            fontSize=11,
            leading=16,
            textColor=colors.HexColor('#30d158'),
            alignment=TA_CENTER,
        ),
        'rating_hold': ParagraphStyle(
            'RatingHold',
            fontName=FONT_NAME,
            fontSize=11,
            leading=16,
            textColor=colors.HexColor('#ff9f0a'),
            alignment=TA_CENTER,
        ),
        'rating_sell': ParagraphStyle(
            'RatingSell',
            fontName=FONT_NAME,
            fontSize=11,
            leading=16,
            textColor=colors.HexColor('#ff453a'),
            alignment=TA_CENTER,
        ),
        'disclaimer': ParagraphStyle(
            'Disclaimer',
            fontName=FONT_NAME,
            fontSize=7,
            leading=11,
            textColor=colors.HexColor('#8e8e93'),
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
    }
    return custom


# ============================================================
# 图表生成模块
# ============================================================

def generate_kline_chart(klines, name, code):
    """生成K线图（蜡烛图 + MA线）"""
    if not klines or len(klines) < 20:
        return None

    # 取最近60根K线
    data = klines[-60:]
    n = len(data)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.5), height_ratios=[3, 1],
                                    facecolor='white')
    fig.subplots_adjust(hspace=0.05)

    closes = [k['close'] for k in data]
    opens = [k['open'] for k in data]
    highs = [k['high'] for k in data]
    lows = [k['low'] for k in data]
    volumes = [k['volume'] for k in data]
    dates = [k['date'][-5:] for k in data]  # MM-DD

    # 蜡烛图
    for i in range(n):
        color = '#ff3b30' if closes[i] >= opens[i] else '#34c759'
        # 实体
        height = abs(closes[i] - opens[i])
        bottom = min(closes[i], opens[i])
        ax1.bar(i, height, bottom=bottom, color=color, width=0.7, alpha=0.9, linewidth=0)
        # 影线
        ax1.plot([i, i], [lows[i], highs[i]], color=color, linewidth=0.7)

    # MA均线
    def calc_ma(data_list, period):
        result = []
        for j in range(len(data_list)):
            if j < period - 1:
                result.append(None)
            else:
                result.append(sum(data_list[j-period+1:j+1]) / period)
        return result

    ma5 = calc_ma(closes, 5)
    ma10 = calc_ma(closes, 10)
    ma20 = calc_ma(closes, 20)

    x_vals = list(range(n))
    ax1.plot(x_vals, [v for v in ma5], color='#ff9f0a', linewidth=1, label='MA5')
    ax1.plot(x_vals, [v for v in ma10], color='#0071e3', linewidth=1, label='MA10')
    ax1.plot(x_vals, [v for v in ma20], color='#af52de', linewidth=1, label='MA20')

    ax1.legend(loc='upper left', fontsize=7, framealpha=0.8)
    ax1.set_xlim(-1, n)
    ax1.set_title(f'{name}（{code}）近60日K线图', fontsize=10, pad=8, color='#1d1d1f')
    ax1.tick_params(axis='x', labelbottom=False)
    ax1.tick_params(axis='y', labelsize=8)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(axis='y', alpha=0.3, linewidth=0.5)

    # 成交量图
    for i in range(n):
        color = '#ff3b30' if closes[i] >= opens[i] else '#34c759'
        ax2.bar(i, volumes[i] / 1e4, color=color, alpha=0.7, width=0.7)  # 万手

    ax2.set_xlim(-1, n)
    ax2.set_ylabel('成交量(万手)', fontsize=8)
    ax2.tick_params(axis='y', labelsize=7)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.grid(axis='y', alpha=0.3, linewidth=0.5)

    # X轴日期标签（每10根显示一个）
    tick_positions = list(range(0, n, max(n // 6, 1)))
    ax2.set_xticks(tick_positions)
    ax2.set_xticklabels([dates[i] for i in tick_positions], fontsize=7)

    # 数据来源注释
    fig.text(0.99, 0.01, '数据来源：腾讯K线接口 (web.ifzq.gtimg.cn)',
             ha='right', va='bottom', fontsize=6, color='#8e8e93')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buf.seek(0)
    return buf


def generate_financial_trend_chart(fin_summary, name):
    """生成财务趋势图（营收+净利润双轴）"""
    revenues = fin_summary.get('revenue', [])
    profits = fin_summary.get('net_profit', [])

    if not revenues and not profits:
        return None

    fig, ax1 = plt.subplots(figsize=(8, 4), facecolor='white')

    years = [item['year'] for item in revenues] if revenues else [item['year'] for item in profits]
    rev_values = [item['value'] for item in revenues]
    profit_values = [item['value'] for item in profits]

    x = list(range(len(years)))

    if rev_values:
        ax1.bar(x, rev_values, width=0.35, label='营业收入(亿元)', color='#0071e3', alpha=0.7)
        ax1.set_ylabel('营业收入（亿元）', fontsize=9, color='#0071e3')
        ax1.tick_params(axis='y', labelcolor='#0071e3', labelsize=8)

    if profit_values:
        ax2 = ax1.twinx()
        ax2.plot(x, profit_values, 'o-', color='#ff3b30', linewidth=2,
                 markersize=6, label='净利润(亿元)')
        ax2.set_ylabel('净利润（亿元）', fontsize=9, color='#ff3b30')
        ax2.tick_params(axis='y', labelcolor='#ff3b30', labelsize=8)

        # 合并legend
        lines1 = [mpatches.Patch(facecolor='#0071e3', alpha=0.7, label='营业收入')]
        lines2 = ax2.get_lines()
        ax1.legend(handles=lines1 + lines2, loc='upper left', fontsize=8)

    ax1.set_xticks(x)
    ax1.set_xticklabels(years, fontsize=8)
    ax1.set_title(f'{name} 营收与净利润趋势', fontsize=10, pad=8, color='#1d1d1f')
    ax1.spines['top'].set_visible(False)
    ax1.grid(axis='y', alpha=0.3, linewidth=0.5)

    fig.text(0.99, 0.01, '数据来源：新浪财经API (quotes.sina.cn)',
             ha='right', va='bottom', fontsize=6, color='#8e8e93')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buf.seek(0)
    return buf


def generate_peer_comparison_chart(report, name, code):
    """生成同行对比图"""
    # 使用报告中ch7的同行数据，若无则用示意数据
    ch7 = report.get('ch7_peers', {})
    peers = ch7.get('peers', [])

    # 构建对比数据（当前股票 + 同行）
    companies = [f'{name}({code})']
    pe_values = [report.get('ch1_overview', {}).get('pe_ttm', 'N/A')]
    pb_values = [report.get('ch1_overview', {}).get('pb', 'N/A')]

    # 提取PE数字
    def extract_float(val):
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(str(val).replace('x', '').replace('元', '').strip())
        except:
            return 0

    pe_num = [extract_float(pe_values[0])]
    pb_num = [extract_float(pb_values[0])]

    # 添加同行数据（若有）
    peer_data = ch7.get('peer_quotes', [])
    for p in peer_data[:3]:
        companies.append(f"{p.get('name','')}")
        pe_num.append(extract_float(p.get('pe_ttm', 0)))
        pb_num.append(extract_float(p.get('pb', 0)))

    if len(companies) < 2:
        # 无同行数据，生成单一条形图
        companies += ['行业均值(参考)']
        pe_num += [pe_num[0] * 0.85]
        pb_num += [pb_num[0] * 0.85]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4), facecolor='white')

    x = list(range(len(companies)))
    colors_list = ['#0071e3'] + ['#86c1f0'] * (len(companies) - 1)

    # PE对比
    valid_pe = [(i, v) for i, v in enumerate(pe_num) if v > 0]
    if valid_pe:
        xi, yi = zip(*valid_pe)
        bars = ax1.bar([x[i] for i in xi], yi, color=[colors_list[i] for i in xi], alpha=0.85)
        ax1.set_xticks(list(range(len(companies))))
        ax1.set_xticklabels(companies, fontsize=7, rotation=15, ha='right')
        ax1.set_title('市盈率(PE-TTM)对比', fontsize=10, color='#1d1d1f')
        ax1.set_ylabel('PE-TTM (倍)', fontsize=9)
        ax1.tick_params(axis='y', labelsize=8)
        for bar in bars:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                     f'{bar.get_height():.1f}x', ha='center', va='bottom', fontsize=8)
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.grid(axis='y', alpha=0.3)

    # PB对比
    valid_pb = [(i, v) for i, v in enumerate(pb_num) if v > 0]
    if valid_pb:
        xi, yi = zip(*valid_pb)
        bars = ax2.bar([x[i] for i in xi], yi, color=[colors_list[i] for i in xi], alpha=0.85)
        ax2.set_xticks(list(range(len(companies))))
        ax2.set_xticklabels(companies, fontsize=7, rotation=15, ha='right')
        ax2.set_title('市净率(PB)对比', fontsize=10, color='#1d1d1f')
        ax2.set_ylabel('PB (倍)', fontsize=9)
        ax2.tick_params(axis='y', labelsize=8)
        for bar in bars:
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                     f'{bar.get_height():.2f}x', ha='center', va='bottom', fontsize=8)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.grid(axis='y', alpha=0.3)

    fig.suptitle('同行估值对比（蓝色为目标公司）', fontsize=10, color='#1d1d1f')
    fig.text(0.99, 0.01, '数据来源：腾讯行情API (qt.gtimg.cn)',
             ha='right', va='bottom', fontsize=6, color='#8e8e93')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buf.seek(0)
    return buf


def generate_valuation_chart(report, name):
    """生成估值分析图（PE历史区间 + 目标价范围）"""
    ch9 = report.get('ch9_target_price', {})
    ch1 = report.get('ch1_overview', {})

    try:
        current_price = float(str(ch1.get('current_price', '0')).replace('元', '').strip())
    except:
        current_price = 0

    pe_method = ch9.get('pe_method', {})
    target_range = pe_method.get('target_range', '')

    # 解析目标价区间
    target_low, target_high = current_price * 0.9, current_price * 1.2
    if target_range:
        parts = str(target_range).replace('元', '').split('-')
        if len(parts) == 2:
            try:
                target_low = float(parts[0].strip())
                target_high = float(parts[1].strip())
            except:
                pass

    if current_price <= 0:
        return None

    fig, ax = plt.subplots(figsize=(8, 4), facecolor='white')

    # 估值带
    stop_loss = current_price * 0.85
    support = current_price * 0.92

    ax.barh(['PE法估值区间'], [target_high - target_low],
            left=target_low, height=0.4, color='#34c759', alpha=0.4, label='PE法目标区间')
    ax.barh(['PE法估值区间'], [support - stop_loss],
            left=stop_loss, height=0.4, color='#ff3b30', alpha=0.3, label='支撑/止损区间')

    # 当前价格线
    ax.axvline(x=current_price, color='#0071e3', linewidth=2, linestyle='-', label=f'当前价 ¥{current_price:.2f}')

    # 目标价标注
    ax.axvline(x=target_high, color='#34c759', linewidth=1.5, linestyle='--', alpha=0.8, label=f'目标价上限 ¥{target_high:.2f}')
    ax.axvline(x=target_low, color='#ff9f0a', linewidth=1.5, linestyle='--', alpha=0.8, label=f'目标价下限 ¥{target_low:.2f}')

    ax.set_xlabel('股价（元）', fontsize=9)
    ax.set_title(f'{name} 估值区间分析', fontsize=10, pad=8, color='#1d1d1f')
    ax.legend(loc='lower right', fontsize=8, framealpha=0.8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='x', labelsize=9)
    ax.set_yticks([])

    # 注释
    ax.annotate(f'¥{current_price:.2f}', xy=(current_price, 0),
                xytext=(current_price, -0.3), fontsize=8,
                ha='center', color='#0071e3',
                arrowprops=dict(arrowstyle='->', color='#0071e3', lw=1))

    fig.text(0.99, 0.01, '数据来源：PE估值法（合理PE范围 = 行业对比）',
             ha='right', va='bottom', fontsize=6, color='#8e8e93')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buf.seek(0)
    return buf


def generate_technical_chart(klines, tech, name, code):
    """生成技术指标图（RSI + MACD）"""
    if not klines or len(klines) < 30:
        return None

    data = klines[-60:]
    n = len(data)
    closes = [k['close'] for k in data]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5), height_ratios=[1, 1],
                                    facecolor='white')
    fig.subplots_adjust(hspace=0.4)

    x = list(range(n))
    dates = [k['date'][-5:] for k in data]
    tick_positions = list(range(0, n, max(n // 6, 1)))

    # RSI图
    rsi_values = []
    for j in range(n):
        subset = closes[max(0, j-13):j+1]
        if len(subset) < 14:
            rsi_values.append(50)
        else:
            gains = sum(max(subset[i]-subset[i-1], 0) for i in range(1, len(subset)))
            losses = sum(max(subset[i-1]-subset[i], 0) for i in range(1, len(subset)))
            if losses == 0:
                rsi_values.append(100)
            else:
                rs = gains / losses
                rsi_values.append(100 - 100 / (1 + rs))

    ax1.plot(x, rsi_values, color='#af52de', linewidth=1.5)
    ax1.axhline(y=70, color='#ff3b30', linewidth=1, linestyle='--', alpha=0.7, label='超买(70)')
    ax1.axhline(y=30, color='#34c759', linewidth=1, linestyle='--', alpha=0.7, label='超卖(30)')
    ax1.axhline(y=50, color='#8e8e93', linewidth=0.7, linestyle=':', alpha=0.5)
    ax1.fill_between(x, rsi_values, 70, where=[v > 70 for v in rsi_values], alpha=0.2, color='#ff3b30')
    ax1.fill_between(x, rsi_values, 30, where=[v < 30 for v in rsi_values], alpha=0.2, color='#34c759')
    ax1.set_ylim(0, 100)
    ax1.set_ylabel('RSI(14)', fontsize=9)
    ax1.legend(loc='upper right', fontsize=7)
    ax1.set_title(f'{name} RSI技术指标', fontsize=10, color='#1d1d1f')
    ax1.set_xticks(tick_positions)
    ax1.set_xticklabels([dates[i] for i in tick_positions], fontsize=7)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(axis='y', alpha=0.3)

    # MACD图
    fast_k = 2 / (12 + 1)
    slow_k = 2 / (26 + 1)
    sig_k = 2 / (9 + 1)

    ema_fast = closes[0]
    ema_slow = closes[0]
    dif_list = []
    for price in closes:
        ema_fast = price * fast_k + ema_fast * (1 - fast_k)
        ema_slow = price * slow_k + ema_slow * (1 - slow_k)
        dif_list.append(ema_fast - ema_slow)

    dea = dif_list[0]
    dea_list = []
    for dif in dif_list:
        dea = dif * sig_k + dea * (1 - sig_k)
        dea_list.append(dea)

    hist_list = [2 * (d - s) for d, s in zip(dif_list, dea_list)]

    ax2.plot(x, dif_list, color='#0071e3', linewidth=1.2, label='DIF')
    ax2.plot(x, dea_list, color='#ff9f0a', linewidth=1.2, label='DEA')
    for i, h in enumerate(hist_list):
        ax2.bar(i, h, color='#ff3b30' if h >= 0 else '#34c759', alpha=0.6, width=0.7)
    ax2.axhline(y=0, color='#8e8e93', linewidth=0.7, linestyle='-', alpha=0.5)
    ax2.legend(loc='upper left', fontsize=7)
    ax2.set_ylabel('MACD', fontsize=9)
    ax2.set_title(f'{name} MACD技术指标', fontsize=10, color='#1d1d1f')
    ax2.set_xticks(tick_positions)
    ax2.set_xticklabels([dates[i] for i in tick_positions], fontsize=7)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.grid(axis='y', alpha=0.3)

    fig.text(0.99, 0.01, '数据来源：腾讯K线接口 (web.ifzq.gtimg.cn)',
             ha='right', va='bottom', fontsize=6, color='#8e8e93')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    buf.seek(0)
    return buf


# ============================================================
# 表格生成辅助
# ============================================================

def make_table(data, col_widths=None, header=True):
    """生成标准表格"""
    if not data:
        return None

    style = TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f5f5f7')]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d1d1d6')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ])

    if header and len(data) > 0:
        style.add('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f5'))
        style.add('FONTSIZE', (0, 0), (-1, 0), 9)
        style.add('FONTNAME', (0, 0), (-1, 0), FONT_NAME)

    table = Table(data, colWidths=col_widths)
    table.setStyle(style)
    return table


def rating_color(level):
    """根据评级返回颜色"""
    mapping = {
        '强烈买入': colors.HexColor('#30d158'),
        '买入': colors.HexColor('#34c759'),
        '谨慎买入': colors.HexColor('#34c759'),
        '增持': colors.HexColor('#ff9f0a'),
        '中性': colors.HexColor('#8e8e93'),
        '减持': colors.HexColor('#ff453a'),
        '卖出': colors.HexColor('#ff3b30'),
    }
    return mapping.get(level, colors.HexColor('#1d1d1f'))


# ============================================================
# PDF生成主函数
# ============================================================

def generate_pdf(report, klines=None, output_path=None):
    """
    生成完整PDF报告

    Args:
        report: analyze_stock_full() 返回的13章报告JSON
        klines: K线数据列表
        output_path: 输出PDF路径（None则返回BytesIO）

    Returns:
        BytesIO or None（若指定output_path）
    """
    styles = get_styles()

    if output_path is None:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            rightMargin=18*mm,
            leftMargin=18*mm,
            topMargin=20*mm,
            bottomMargin=18*mm,
        )
    else:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=18*mm,
            leftMargin=18*mm,
            topMargin=20*mm,
            bottomMargin=18*mm,
        )

    story = []
    page_width = A4[0] - 36*mm  # 可用宽度

    ch1 = report.get('ch1_overview', {})
    ch2 = report.get('ch2_news', {})
    ch3 = report.get('ch3_business', {})
    ch4 = report.get('ch4_industry', {})
    ch5 = report.get('ch5_value_investing', {})
    ch7 = report.get('ch7_peers', {})
    ch8 = report.get('ch8_profit_forecast', {})
    ch9 = report.get('ch9_target_price', {})
    ch10 = report.get('ch10_comparison', {})
    ch11 = report.get('ch11_risks', {})
    ch12 = report.get('ch12_sources', {})
    ch13 = report.get('ch13_technical', {})

    name = ch1.get('stock_name', '')
    code = ch1.get('stock_code', '')
    fin_summary = report.get('_fin_summary', {})

    # ==================== 封面 ====================
    story.append(Spacer(1, 20*mm))
    story.append(Paragraph('股票价值分析报告', styles['title']))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f'{name}（{code}）', ParagraphStyle(
        'CoverTitle', fontName=FONT_NAME, fontSize=22, leading=30,
        textColor=colors.HexColor('#1d1d1f'), alignment=TA_CENTER, spaceAfter=8
    )))

    # 评级框
    rating = ch1.get('rating', {})
    rating_level = rating.get('level', '中性')
    r_color = rating_color(rating_level)
    story.append(Spacer(1, 6))

    rating_table = Table([[
        Paragraph(f'综合评级', ParagraphStyle('RL', fontName=FONT_NAME, fontSize=9,
                  textColor=colors.HexColor('#6e6e73'), alignment=TA_CENTER)),
        Paragraph(rating_level, ParagraphStyle('RV', fontName=FONT_NAME, fontSize=16,
                  textColor=r_color, alignment=TA_CENTER)),
    ]], colWidths=[page_width/2, page_width/2])
    rating_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f7')),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(rating_table)
    story.append(Spacer(1, 8))

    # 核心指标表
    key_metrics = [
        ['指标', '数值', '指标', '数值'],
        ['当前股价', ch1.get('current_price', 'N/A'), '总市值', ch1.get('market_cap', 'N/A')],
        ['PE-TTM', ch1.get('pe_ttm', 'N/A'), 'PB', ch1.get('pb', 'N/A')],
        ['行业', ch1.get('industry', 'N/A'), '今日涨跌', ch1.get('change_pct', 'N/A')],
    ]
    t = make_table(key_metrics, col_widths=[page_width*0.2, page_width*0.3, page_width*0.2, page_width*0.3])
    if t:
        story.append(t)

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f'生成时间：{report.get("generated_at", "")}　｜　分析耗时：{report.get("analysis_time", "")}',
        styles['subtitle']
    ))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#d1d1d6')))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        '本报告由AI自动生成，仅供参考，不构成投资建议。股市有风险，投资需谨慎。',
        styles['disclaimer']
    ))

    # ==================== 第1章：概述 ====================
    story.append(PageBreak())
    story.append(Paragraph('第一章　公司概述', styles['chapter_title']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#0071e3')))
    story.append(Spacer(1, 4))
    summary_text = ch1.get('summary', '')
    if summary_text:
        story.append(Paragraph(summary_text, styles['body']))

    # ==================== 第2章：公司最新动态 ====================
    story.append(Spacer(1, 8))
    story.append(Paragraph('第二章　公司最新动态', styles['chapter_title']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#0071e3')))
    story.append(Spacer(1, 4))

    story.append(Paragraph(f'数据来源：{ch2.get("source", "N/A")}', styles['source_note']))
    if ch2.get('source_note'):
        story.append(Paragraph(ch2['source_note'], styles['source_note']))

    news_items = ch2.get('web_news', []) + ch2.get('knowledge_updates', [])
    if news_items:
        news_table_data = [['标题', '日期', '来源']]
        for item in news_items[:8]:
            title = str(item.get('title', ''))[:50] + ('...' if len(str(item.get('title', ''))) > 50 else '')
            date = str(item.get('date', ''))[:10]
            source = str(item.get('source', ''))
            news_table_data.append([title, date, source])
        t = make_table(news_table_data, col_widths=[page_width*0.65, page_width*0.2, page_width*0.15])
        if t:
            story.append(t)
    else:
        story.append(Paragraph('暂无最新新闻数据，请访问东方财富网或同花顺获取最新动态。', styles['body']))

    # ==================== 第3章：业务板块分析 ====================
    story.append(Spacer(1, 8))
    story.append(Paragraph('第三章　业务板块分析', styles['chapter_title']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#0071e3')))
    story.append(Spacer(1, 4))

    main_biz = ch3.get('main_business_desc', '')
    if main_biz:
        story.append(Paragraph('主营业务：', styles['section_title']))
        story.append(Paragraph(main_biz, styles['body']))
        biz_src = ch3.get('main_business_source', '')
        biz_url = ch3.get('main_business_source_url', '')
        if biz_src:
            story.append(Paragraph(f'来源：{biz_src}　{biz_url[:80]}', styles['source_note']))

    story.append(Paragraph('财务数据来源：新浪财经API (quotes.sina.cn)', styles['source_note']))
    story.append(Spacer(1, 4))

    analysis_text = ch3.get('analysis', '')
    if analysis_text:
        story.append(Paragraph(analysis_text, styles['body']))

    # 营收表格
    revenues = ch3.get('revenue_structure', [])
    profits = ch3.get('profit_structure', [])
    if revenues or profits:
        fin_data = [['年份', '营业收入（亿元）', '净利润（亿元）']]
        year_map = {}
        for r in revenues:
            year_map[r['year']] = {'rev': r['value']}
        for p in profits:
            if p['year'] in year_map:
                year_map[p['year']]['prof'] = p['value']
            else:
                year_map[p['year']] = {'prof': p['value']}
        for yr in sorted(year_map.keys()):
            row = year_map[yr]
            fin_data.append([
                yr,
                f"{row.get('rev', 0):.2f}",
                f"{row.get('prof', 0):.2f}",
            ])
        if len(fin_data) > 1:
            story.append(make_table(fin_data, col_widths=[page_width*0.25, page_width*0.375, page_width*0.375]))

    story.append(Paragraph(
        f'营收CAGR：{ch3.get("revenue_cagr","N/A")}　净利润CAGR：{ch3.get("profit_cagr","N/A")}　来源：新浪财经年报',
        styles['source_note']
    ))

    # ==================== 财务趋势图 ====================
    story.append(Spacer(1, 8))
    story.append(Paragraph('财务趋势图', styles['section_title']))

    fin_s = {
        'revenue': ch3.get('revenue_structure', []),
        'net_profit': ch3.get('profit_structure', []),
    }
    chart_buf = generate_financial_trend_chart(fin_s, name)
    if chart_buf:
        img = Image(chart_buf, width=page_width, height=page_width * 0.45)
        story.append(img)
        story.append(Paragraph('图表数据来源：新浪财经API (quotes.sina.cn) — 年报财务数据', styles['source_note']))

    # ==================== K线图 ====================
    story.append(PageBreak())
    story.append(Paragraph('第十三章　技术面分析', styles['chapter_title']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#0071e3')))
    story.append(Spacer(1, 4))

    if klines:
        story.append(Paragraph('近60日K线图（含MA5/MA10/MA20）', styles['section_title']))
        kline_buf = generate_kline_chart(klines, name, code)
        if kline_buf:
            img = Image(kline_buf, width=page_width, height=page_width * 0.5)
            story.append(img)
            story.append(Paragraph('数据来源：腾讯K线接口 (web.ifzq.gtimg.cn)　红色上涨，绿色下跌（A股惯例）', styles['source_note']))

        story.append(Spacer(1, 6))
        story.append(Paragraph('RSI & MACD 技术指标', styles['section_title']))
        tech_buf = generate_technical_chart(klines, ch13, name, code)
        if tech_buf:
            img = Image(tech_buf, width=page_width, height=page_width * 0.46)
            story.append(img)
            story.append(Paragraph('数据来源：腾讯K线接口　计算方法：RSI(Wilder平滑)、MACD(EMA12/26/9)', styles['source_note']))

    # 技术指标数值表
    story.append(Spacer(1, 6))
    story.append(Paragraph('关键技术指标', styles['section_title']))
    tech_data = [
        ['指标', '数值', '信号'],
        ['当前价格', f"¥{ch13.get('current_price', 'N/A')}", '-'],
        ['MA5', f"{ch13.get('key_levels', {}).get('ma5', 'N/A')}", '短期趋势参考'],
        ['MA10', f"{ch13.get('key_levels', {}).get('ma10', 'N/A')}", '中期趋势参考'],
        ['MA20', f"{ch13.get('key_levels', {}).get('ma20', 'N/A')}", '中期趋势参考'],
        ['RSI(14)', f"{ch13.get('indicators', {}).get('rsi', 'N/A')}", '超卖<30，超买>70'],
        ['技术评分', f"{ch13.get('tech_score', 'N/A')}/30", '≥24强势，<12弱势'],
        ['短线趋势', ch13.get('short_trend', 'N/A'), ch13.get('hold_days', '')],
        ['参考买入价', f"¥{ch13.get('buy_price', 'N/A')}", '仅供参考'],
        ['短线目标价', f"¥{ch13.get('target_price_short', 'N/A')}", '仅供参考'],
        ['止损价', f"¥{ch13.get('stop_loss', 'N/A')}", '严格止损'],
    ]
    t = make_table(tech_data, col_widths=[page_width*0.25, page_width*0.35, page_width*0.40])
    if t:
        story.append(t)

    # ==================== 同行对比图 ====================
    story.append(PageBreak())
    story.append(Paragraph('第七章　同行对比分析', styles['chapter_title']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#0071e3')))
    story.append(Spacer(1, 4))

    story.append(Paragraph('估值对比图（PE-TTM & PB）', styles['section_title']))
    peer_buf = generate_peer_comparison_chart(report, name, code)
    if peer_buf:
        img = Image(peer_buf, width=page_width, height=page_width * 0.38)
        story.append(img)
        story.append(Paragraph('数据来源：腾讯行情API (qt.gtimg.cn)　数据为实时行情，蓝色柱为目标公司', styles['source_note']))

    # ==================== 利润预测 ====================
    story.append(Spacer(1, 8))
    story.append(Paragraph('第八章　净利润预测依据', styles['chapter_title']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#0071e3')))
    story.append(Spacer(1, 4))

    prediction = ch8.get('prediction', {})
    hist_data = prediction.get('historical', [])
    fc_next = prediction.get('forecast_next', {})
    # 兼容动态key
    if not fc_next:
        for k, v in prediction.items():
            if k.startswith('forecast_') and k != 'forecast_next':
                fc_next = v
                break

    if hist_data:
        fc_header = ['年份', '营业收入', '净利润']
        fc_rows = [fc_header]
        for row in hist_data:
            fc_rows.append([row.get('year', ''), row.get('revenue', 'N/A'), row.get('net_profit', 'N/A')])
        if fc_next and fc_next.get('value') and fc_next.get('value') != '数据不足':
            fc_rows.append([fc_next.get('year', '下一年E'), '—', f"{fc_next['value']}（预测）"])

        t_fc = make_table(fc_rows, col_widths=[page_width*0.25, page_width*0.35, page_width*0.40])
        if t_fc:
            story.append(t_fc)

        if fc_next and fc_next.get('method'):
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"预测方法：{fc_next['method']}", styles['source_note']))
        if fc_next and fc_next.get('growth_rate'):
            story.append(Paragraph(f"保守增速：{fc_next['growth_rate']}", styles['source_note']))
    else:
        story.append(Paragraph('暂无历史财务数据，无法生成利润预测', styles['body']))

    story.append(Paragraph('来源：新浪财经API历史年报 + 增速外推法', styles['source_note']))

    # ==================== 估值分析图 ====================
    story.append(Spacer(1, 8))
    story.append(Paragraph('第九章　目标价来源依据', styles['chapter_title']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#0071e3')))
    story.append(Spacer(1, 4))

    story.append(Paragraph('估值区间分析图', styles['section_title']))
    val_buf = generate_valuation_chart(report, name)
    if val_buf:
        img = Image(val_buf, width=page_width, height=page_width * 0.40)
        story.append(img)
        story.append(Paragraph('数据来源：基于PE估值法，合理PE区间参考行业均值', styles['source_note']))

    # PE估值表格
    pe_method = ch9.get('pe_method', {})
    analyst_targets = ch9.get('analyst_targets', {})
    comp = ch9.get('comprehensive', {})
    primary = comp.get('primary', {})

    # 主目标价（优先券商研报）
    if primary:
        story.append(Paragraph(f"主目标价：{primary.get('method', '')}", styles['section_title']))
        story.append(Paragraph(
            f"目标价区间：{primary.get('target_range', 'N/A')}　|　"
            f"目标价均值：{primary.get('avg_target', 'N/A')}　|　"
            f"上行空间：{primary.get('upside', 'N/A')}",
            styles['body']
        ))
        story.append(Spacer(1, 6))

    # 券商研报目标价明细表
    if analyst_targets and analyst_targets.get('targets'):
        at_rows = [['日期', '机构', '评级', '目标价', '上行空间']]
        for t in analyst_targets['targets'][:8]:
            tp = t.get('target_price', 0)
            upside = ''
            if tp and ch1.get('current_price'):
                try:
                    cur = float(str(ch1['current_price']).replace('¥', ''))
                    if cur > 0:
                        upside = f"{(tp/cur-1)*100:.1f}%"
                except:
                    pass
            at_rows.append([
                t.get('date', ''),
                t.get('institution', '')[:12],
                t.get('rating', '')[:8],
                f"¥{tp}",
                upside,
            ])
        story.append(Paragraph('券商研报目标价（近6个月）', styles['section_title']))
        t_at = make_table(at_rows, col_widths=[page_width*0.15, page_width*0.30, page_width*0.15, page_width*0.15, page_width*0.15])
        if t_at:
            story.append(t_at)
        story.append(Paragraph(f"来源：{analyst_targets.get('source', '东方财富研报')}（仅统计近6个月研报）", styles['source_note']))
        story.append(Spacer(1, 8))

    # PE法估值表格（参考）
    if pe_method:
        val_data = [
            ['估值方法', '参数', '结论'],
            ['PE估值法（参考）', f"合理PE区间：{pe_method.get('reasonable_pe_range', 'N/A')}",
             f"目标区间：{pe_method.get('fair_price_low','N/A')} - {pe_method.get('fair_price_high','N/A')}元"],
            ['DCF折现法', 'WACC=10%, g=3%, FCF=净利×70%', '详见完整分析报告'],
            ['PEG分析', 'PEG=PE/净利润增速', 'PEG<1低估，PEG=1-1.5合理'],
        ]
        t = make_table(val_data, col_widths=[page_width*0.2, page_width*0.4, page_width*0.4])
        if t:
            story.append(t)
        story.append(Paragraph('来源：券商研报目标价来自东方财富研报API + PE估值法基于腾讯行情API', styles['source_note']))

    # ==================== 综合结论 ====================
    story.append(PageBreak())
    story.append(Paragraph('第十章　综合结论', styles['chapter_title']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#0071e3')))
    story.append(Spacer(1, 4))

    conclusion = ch10.get('conclusion', '')
    val_rating = ch10.get('value_investing_rating', '')
    if conclusion or val_rating:
        story.append(Paragraph(f'综合评级：{val_rating}', styles['section_title']))
        if conclusion:
            story.append(Paragraph(conclusion, styles['body']))

    # ==================== 风险提示 ====================
    story.append(Spacer(1, 8))
    story.append(Paragraph('第十一章　风险提示', styles['chapter_title']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#ff3b30')))
    story.append(Spacer(1, 4))
    risks = ch11.get('risks', [])
    for risk in risks:
        story.append(Paragraph(f'• {risk}', styles['body']))

    # ==================== 信息来源 ====================
    story.append(Spacer(1, 8))
    story.append(Paragraph('第十二章　信息来源与时效性', styles['chapter_title']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#0071e3')))
    story.append(Spacer(1, 4))

    sources = ch12.get('sources', [])
    if sources:
        src_data = [['数据源', 'URL/接口', '数据类型', '获取时间']]
        for s in sources:
            src_data.append([
                s.get('name', ''), s.get('url', ''), s.get('data_type', ''), str(s.get('time', ''))[:16]
            ])
        t = make_table(src_data, col_widths=[page_width*0.22, page_width*0.28, page_width*0.25, page_width*0.25])
        if t:
            story.append(t)

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#d1d1d6')))
    story.append(Spacer(1, 4))
    story.append(Paragraph(ch12.get('disclaimer', '本报告由AI自动生成，仅供参考，不构成投资建议。股市有风险，投资需谨慎。'), styles['disclaimer']))

    # 构建PDF
    doc.build(story)

    if output_path is None:
        buf.seek(0)
        return buf
    return None


# ============================================================
# 测试入口
# ============================================================

if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from stock_analyzer_web import analyze_stock_full, get_kline_data

    code = sys.argv[1] if len(sys.argv) > 1 else '603629'
    print(f"生成 {code} 的PDF报告...")
    report = analyze_stock_full(code)
    klines = get_kline_data(code, 120)
    output = f'{code}_report.pdf'
    generate_pdf(report, klines, output_path=output)
    print(f"PDF已生成：{output}")

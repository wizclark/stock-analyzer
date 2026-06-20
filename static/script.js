/* ============================================================
   StockAnalyzer — Main Script (Google-style Search)
   ============================================================ */

let currentReport = null;
let currentCode = null;
let searchDebounceTimer = null;
let selectedSugIndex = -1;

/* ============================================================
   Init
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
    checkAuthStatus();
    setupSearch();

    const input = document.getElementById('stockInput');
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            const sug = document.getElementById('suggestions');
            const items = sug.querySelectorAll('.google-sug-item');
            if (selectedSugIndex >= 0 && items[selectedSugIndex]) {
                items[selectedSugIndex].click();
            } else {
                analyzeStock();
            }
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            moveSuggestion(1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            moveSuggestion(-1);
        } else if (e.key === 'Escape') {
            hideSuggestions();
        }
    });

    document.addEventListener('click', e => {
        if (!e.target.closest('#searchWrap')) hideSuggestions();
    });
});

/* ============================================================
   Auth
   ============================================================ */
async function checkAuthStatus() {
    try {
        const resp = await fetch('/api/auth/status');
        const data = await resp.json();
        const navLogin = document.getElementById('navLogin');
        const navRegister = document.getElementById('navRegister');
        const navUser = document.getElementById('navUser');
        const navHistory = document.getElementById('navHistory');
        if (data.logged_in) {
            navLogin && navLogin.classList.add('hidden');
            navRegister && navRegister.classList.add('hidden');
            navUser && navUser.classList.remove('hidden');
            navHistory && navHistory.classList.remove('hidden');
            const navUsername = document.getElementById('navUsername');
            if (navUsername) navUsername.textContent = data.username;
        }
    } catch (e) {}
}

async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.reload();
}

/* ============================================================
   Search Autocomplete (Google-style)
   ============================================================ */
function setupSearch() {
    const input = document.getElementById('stockInput');
    input.addEventListener('input', () => {
        clearTimeout(searchDebounceTimer);
        const q = input.value.trim();
        if (!q) { hideSuggestions(); return; }
        searchDebounceTimer = setTimeout(() => fetchSuggestions(q), 180);
    });
}

async function fetchSuggestions(q) {
    const searchBox = document.querySelector('.google-search-box');
    searchBox.classList.add('loading');
    
    try {
        const resp = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
        const items = await resp.json();
        renderSuggestions(items);
    } catch (e) {
        hideSuggestions();
    } finally {
        searchBox.classList.remove('loading');
    }
}

function renderSuggestions(items) {
    const sug = document.getElementById('suggestions');
    if (!items || items.length === 0) { sug.innerHTML = ''; return; }
    sug.innerHTML = items.map((item, i) => `
        <button class="google-sug-item" data-code="${item.code}" data-name="${item.name}" onclick="selectSuggestion('${item.code}','${item.name}')">
            <svg class="google-sug-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="10.5" cy="10.5" r="7" stroke="#9aa0a6" stroke-width="2"/>
                <path d="M15.5 15.5L21 21" stroke="#9aa0a6" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span class="google-sug-name">${highlightMatch(item.name, document.getElementById('stockInput').value.trim())}</span>
            <span class="google-sug-code">${item.code}</span>
            <span class="google-sug-market">${item.market || ''}</span>
        </button>
    `).join('');
    selectedSugIndex = -1;
}

function highlightMatch(text, query) {
    if (!query) return text;
    const idx = text.toLowerCase().indexOf(query.toLowerCase());
    if (idx === -1) return text;
    return text.substring(0, idx) + '<strong>' + text.substring(idx, idx + query.length) + '</strong>' + text.substring(idx + query.length);
}

function hideSuggestions() {
    const sug = document.getElementById('suggestions');
    if (sug) sug.innerHTML = '';
    selectedSugIndex = -1;
}

function moveSuggestion(dir) {
    const items = document.querySelectorAll('.google-sug-item');
    if (!items.length) return;
    items.forEach(i => i.classList.remove('selected'));
    selectedSugIndex = Math.max(-1, Math.min(items.length - 1, selectedSugIndex + dir));
    if (selectedSugIndex >= 0) {
        items[selectedSugIndex].classList.add('selected');
        items[selectedSugIndex].scrollIntoView({ block: 'nearest' });
        document.getElementById('stockInput').value = items[selectedSugIndex].dataset.code;
    }
}

function selectSuggestion(code, name) {
    document.getElementById('stockInput').value = code;
    hideSuggestions();
    analyzeStock();
}

/* ============================================================
   Lucky Analyze (手气不错)
   ============================================================ */
const LUCKY_STOCKS = ['603629','600519','000858','300750','688981','601318','000333','601012','300059','600036'];

function luckyAnalyze() {
    const randomCode = LUCKY_STOCKS[Math.floor(Math.random() * LUCKY_STOCKS.length)];
    document.getElementById('stockInput').value = randomCode;
    showToast(`手气不错！正在分析 ${randomCode}...`);
    setTimeout(() => analyzeStock(), 300);
}

/* ============================================================
   Analysis
   ============================================================ */
function quickAnalyze(code) {
    document.getElementById('stockInput').value = code;
    analyzeStock();
}

async function analyzeStock() {
    const input = document.getElementById('stockInput').value.trim();
    if (!input) { showToast('请输入股票代码或名称'); return; }
    hideSuggestions();

    showLoading(true);
    const loadingText = document.getElementById('loadingText');

    const messages = [
        '正在获取实时行情数据...',
        '正在读取财务报表...',
        '正在分析业务板块...',
        '正在计算技术指标...',
        '正在生成分析报告...',
    ];
    let msgIdx = 0;
    const msgTimer = setInterval(() => {
        msgIdx = (msgIdx + 1) % messages.length;
        if (loadingText) loadingText.textContent = messages[msgIdx];
    }, 3500);

    try {
        const payload = input.match(/^\d+$/) ? { code: input } : { name: input };
        const resp = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const report = await resp.json();
        clearInterval(msgTimer);

        if (report.error) {
            showLoading(false);
            showToast(`分析失败：${report.error}`);
            return;
        }

        currentReport = report;
        currentCode = report.ch1_overview?.stock_code || input;
        renderReport(report);
    } catch (e) {
        clearInterval(msgTimer);
        showToast('网络错误，请重试');
    } finally {
        clearInterval(msgTimer);
        showLoading(false);
    }
}

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (show) overlay.classList.remove('hidden');
    else overlay.classList.add('hidden');
}

/* ============================================================
   Report Rendering
   ============================================================ */
function renderReport(report) {
    const container = document.getElementById('reportContainer');
    container.classList.remove('hidden');

    const ch1 = report.ch1_overview || {};
    const ch2 = report.ch2_news || {};
    const ch3 = report.ch3_business || {};
    const ch4 = report.ch4_industry || {};
    const ch5 = report.ch5_value_investing || {};
    const ch7 = report.ch7_peers || {};
    const ch8 = report.ch8_profit_forecast || {};
    const ch9 = report.ch9_target_price || {};
    const ch10 = report.ch10_comparison || {};
    const ch11 = report.ch11_risks || {};
    const ch12 = report.ch12_sources || {};
    const ch13 = report.ch13_technical || {};

    // Header
    document.getElementById('reportName').textContent = `${ch1.stock_name || ''}（${ch1.stock_code || ''}）`;

    const rating = ch1.rating || {};
    const ratingLevel = rating.level || '中性';
    const ratingClass = getRatingClass(ratingLevel);
    const changePct = ch1.change_pct || '0%';
    const changeNum = parseFloat(changePct) || 0;
    const changeClass = changeNum > 0 ? 'tag-rating-buy' : changeNum < 0 ? 'tag-rating-sell' : 'tag-neutral';

    document.getElementById('reportTags').innerHTML = `
        <span class="tag tag-industry">${ch1.industry || ''}</span>
        <span class="tag ${ratingClass}">${ratingLevel}</span>
        <span class="tag tag-price">¥${ch1.current_price || 'N/A'}</span>
        <span class="tag ${changeClass}">${changePct}</span>
    `;

    // Summary Bar
    document.getElementById('summaryBar').innerHTML = `
        <div class="stat-cell">
            <div class="stat-label">当前股价</div>
            <div class="stat-value">¥${ch1.current_price || 'N/A'}</div>
        </div>
        <div class="stat-cell">
            <div class="stat-label">PE-TTM</div>
            <div class="stat-value">${ch1.pe_ttm || 'N/A'}</div>
        </div>
        <div class="stat-cell">
            <div class="stat-label">市净率PB</div>
            <div class="stat-value">${ch1.pb || 'N/A'}</div>
        </div>
        <div class="stat-cell">
            <div class="stat-label">总市值</div>
            <div class="stat-value">${ch1.market_cap || 'N/A'}</div>
        </div>
        <div class="stat-cell">
            <div class="stat-label">今日涨跌</div>
            <div class="stat-value ${changeNum > 0 ? 'up' : changeNum < 0 ? 'down' : 'neutral'}">${changePct}</div>
        </div>
        <div class="stat-cell">
            <div class="stat-label">技术评分</div>
            <div class="stat-value">${ch13.tech_score || 0}/30</div>
        </div>
    `;

    // Build chapter panels
    const panels = {
        overview:  renderOverview(ch1, report),
        news:      renderNews(ch2),
        business:  renderBusiness(ch3),
        industry:  renderIndustry(ch4),
        value:     renderValue(ch5),
        peers:     renderPeers(ch7),
        forecast:  renderForecast(ch8),
        target:    renderTarget(ch9, ch1),
        tech:      renderTech(ch13),
        risks:     renderRisks(ch11, ch12),
    };

    const panelsEl = document.getElementById('chapterPanels');
    panelsEl.innerHTML = Object.entries(panels).map(([key, html]) =>
        `<div class="ch-panel${key === 'overview' ? ' active' : ''}" id="panel-${key}">${html}</div>`
    ).join('');

    // Scroll to report
    container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function getRatingClass(level) {
    if (['强烈买入','买入','谨慎买入'].includes(level)) return 'tag-rating-buy';
    if (['增持'].includes(level)) return 'tag-rating-hold';
    if (['减持','卖出'].includes(level)) return 'tag-rating-sell';
    return 'tag-neutral';
}

/* ---- Chapter Renderers ---- */

function renderOverview(ch1, report) {
    const ch10 = report.ch10_comparison || {};
    const ch13 = report.ch13_technical || {};
    const rating = ch1.rating || {};

    const techScore = ch13.tech_score || 0;
    const techPct = Math.round(techScore / 30 * 100);

    return `
    <div class="section-card">
        <div class="section-card-header">
            <span class="section-card-title">综合概述</span>
            <span class="section-card-badge">生成时间：${report.generated_at || ''}</span>
        </div>
        <div class="section-card-body">
            <p class="text-body">${ch1.summary || ''}</p>
            <div class="val-box">
                <div class="val-cell"><div class="val-cell-label">综合评级</div><div class="val-cell-value" style="color:${ratingColorHex(rating.level)}">${rating.level || 'N/A'}</div></div>
                <div class="val-cell"><div class="val-cell-label">PE估值水平</div><div class="val-cell-value" style="font-size:12px">${report.ch5_value_investing?.ten_minute_test?.[0]?.detail || ch1.pe_ttm || 'N/A'}</div></div>
                <div class="val-cell"><div class="val-cell-label">综合结论</div><div class="val-cell-value" style="font-size:11px;color:#6e6e73">${ch10.conclusion || rating.text || ''}</div></div>
            </div>
            <div class="score-bar-wrap">
                <div class="score-bar-label"><span>技术面评分</span><span>${techScore}/30分</span></div>
                <div class="score-bar-bg"><div class="score-bar-fill" style="width:${techPct}%;background:${techScore>=18?'#34c759':techScore>=12?'#ff9f0a':'#ff3b30'}"></div></div>
            </div>
        </div>
    </div>
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title">核心数据</span></div>
        <div class="section-card-body">
            <table class="data-table">
                <tr><th>指标</th><th>数值</th><th>指标</th><th>数值</th></tr>
                <tr><td>股票代码</td><td class="text-mono">${ch1.stock_code}</td><td>所属行业</td><td>${ch1.industry}</td></tr>
                <tr><td>当前股价</td><td class="text-mono text-${parseFloat(ch1.change_pct)>0?'up':'down'}">¥${ch1.current_price}</td><td>今日涨跌</td><td class="${parseFloat(ch1.change_pct)>0?'text-up':'text-down'}">${ch1.change_pct}</td></tr>
                <tr><td>PE-TTM</td><td>${ch1.pe_ttm}</td><td>市净率PB</td><td>${ch1.pb}</td></tr>
                <tr><td>总市值</td><td>${ch1.market_cap}</td><td>分析耗时</td><td>${report.analysis_time || 'N/A'}</td></tr>
            </table>
            <div class="source-note">数据来源：腾讯行情API (qt.gtimg.cn) — 实时数据</div>
        </div>
    </div>
    `;
}

function renderNews(ch2) {
    const knowledgeItems = ch2.knowledge_updates || [];
    const webItems = ch2.web_news || [];
    const allItems = [...knowledgeItems, ...webItems];

    const newsHtml = allItems.length > 0
        ? allItems.map(item => `
            <div class="news-item">
                <div class="news-date">${item.date || ''}</div>
                <div>
                    <div class="news-title">
                        ${item.url ? `<a href="${item.url}" target="_blank" rel="noopener">${item.title || ''}</a>` : (item.title || '')}
                    </div>
                    <div class="news-source">来源：${item.source || 'N/A'}</div>
                </div>
            </div>
        `).join('')
        : '<p class="text-body" style="color:#8e8e93">暂无新闻数据，请访问 <a href="https://www.eastmoney.com" target="_blank">东方财富网</a> 或 <a href="https://finance.sina.com.cn" target="_blank">新浪财经</a> 获取最新动态。</p>';

    return `
    <div class="section-card">
        <div class="section-card-header">
            <span class="section-card-title">公司最新动态</span>
            <span class="section-card-badge">${allItems.length}条新闻</span>
        </div>
        <div class="section-card-body">
            <p class="text-sm" style="margin-bottom:10px">数据来源：${ch2.source || 'N/A'}。${ch2.source_note || ''}</p>
            ${newsHtml}
        </div>
    </div>
    `;
}

function renderBusiness(ch3) {
    const revenues = ch3.revenue_structure || [];
    const profits = ch3.profit_structure || [];

    // Merge years
    const yearMap = {};
    revenues.forEach(r => { yearMap[r.year] = { rev: r.value }; });
    profits.forEach(p => {
        if (yearMap[p.year]) yearMap[p.year].prof = p.value;
        else yearMap[p.year] = { prof: p.value };
    });

    const tableRows = Object.entries(yearMap).sort((a, b) => a[0] < b[0] ? -1 : 1).map(([year, vals]) => `
        <tr>
            <td>${year}</td>
            <td>${vals.rev != null ? vals.rev.toFixed(2) + ' 亿元' : 'N/A'}</td>
            <td>${vals.prof != null ? vals.prof.toFixed(2) + ' 亿元' : 'N/A'}</td>
        </tr>
    `).join('');

    const mainBiz = ch3.main_business_desc || '';
    const bizSrc = ch3.main_business_source || '';
    const bizUrl = ch3.main_business_source_url || '';

    return `
    ${mainBiz ? `
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title">主营业务</span></div>
        <div class="section-card-body">
            <p class="text-body">${mainBiz}</p>
            ${bizSrc ? `<div class="source-note">数据来源：${bizSrc}${bizUrl ? ' — <a href="${bizUrl}" target="_blank">查看原始数据</a>' : ''}</div>` : ''}
        </div>
    </div>` : ''}
    <div class="section-card">
        <div class="section-card-header">
            <span class="section-card-title">财务数据趋势</span>
            <span class="section-card-badge">营收CAGR：${ch3.revenue_cagr || 'N/A'} ｜ 净利润CAGR：${ch3.profit_cagr || 'N/A'}</span>
        </div>
        <div class="section-card-body">
            <p class="text-body" style="margin-bottom:10px">${ch3.analysis || ''}</p>
            ${tableRows ? `
            <table class="data-table">
                <tr><th>年份</th><th>营业收入</th><th>净利润</th></tr>
                ${tableRows}
            </table>
            <div class="source-note">数据来源：${ch3.data_source || '新浪财经API (quotes.sina.cn)'}</div>
            ` : '<p class="text-sm">财务数据获取中...</p>'}
        </div>
    </div>
    `;
}

function renderIndustry(ch4) {
    const chain = ch4.chain_analysis || {};
    const outlook = ch4.outlook || {};

    return `
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title">行业：${ch4.industry || 'N/A'}</span></div>
        <div class="section-card-body">
            <table class="data-table">
                <tr><th>产业链环节</th><th>主要内容</th></tr>
                ${Object.entries(chain).filter(([k]) => k !== null).map(([k, v]) => `<tr><td>${k}</td><td>${v || 'N/A'}</td></tr>`).join('')}
            </table>
        </div>
    </div>
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title">行业前景</span></div>
        <div class="section-card-body">
            <table class="data-table">
                <tr><th>维度</th><th>内容</th></tr>
                <tr><td>发展趋势</td><td>${outlook.trend || 'N/A'}</td></tr>
                <tr><td>主要风险</td><td>${outlook.risk || 'N/A'}</td></tr>
            </table>
        </div>
    </div>
    `;
}

function renderValue(ch5) {
    const tests = ch5.ten_minute_test || [];
    const health = ch5.financial_health || [];
    const moat = ch5.moat_analysis || {};

    const testRows = tests.map(t => `
        <div class="test-item">
            <span class="test-badge ${t.result === '通过' ? 'ok' : t.result === '注意' ? 'warn' : 'na'}">${t.result}</span>
            <span style="color:#6e6e73;min-width:80px;font-size:12px">${t.test}</span>
            <span class="text-sm">${t.detail}</span>
        </div>
    `).join('');

    const healthRows = health.map(h => `
        <div class="test-item">
            <span class="test-badge ${h.status === 'OK' ? 'ok' : h.status === 'WARN' ? 'warn' : 'na'}">${h.status}</span>
            <span style="color:#6e6e73;min-width:80px;font-size:12px">${h.signal}</span>
            <span class="text-sm">${h.detail}</span>
        </div>
    `).join('');

    return `
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title">十分钟测试（基于《股市真规则》）</span></div>
        <div class="section-card-body">${testRows || '<p class="text-sm">数据不足</p>'}</div>
    </div>
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title">财务健康检查</span></div>
        <div class="section-card-body">${healthRows || '<p class="text-sm">数据不足</p>'}</div>
    </div>
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title">护城河分析</span></div>
        <div class="section-card-body">
            <table class="data-table">
                <tr><th>维度</th><th>分析</th></tr>
                ${Object.entries(moat).filter(([k]) => k !== 'note').map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('')}
            </table>
            ${moat.note ? `<p class="text-sm" style="margin-top:8px">${moat.note}</p>` : ''}
        </div>
    </div>
    `;
}

function renderPeers(ch7) {
    return `
    <div class="section-card">
        <div class="section-card-header">
            <span class="section-card-title">同行对比</span>
            <span class="section-card-badge">数据来源：${ch7.source || '腾讯行情API'}</span>
        </div>
        <div class="section-card-body">
            <p class="text-sm" style="margin-bottom:10px">${ch7.note || ''}</p>
            ${ch7.peers && ch7.peers.length > 0 ? `
            <table class="data-table">
                <tr><th>股票代码</th><th>数据</th></tr>
                ${ch7.peers.map(p => `<tr><td class="text-mono">${p}</td><td>—</td></tr>`).join('')}
            </table>
            ` : '<p class="text-sm">同行对比数据将在后续版本完善，敬请期待。</p>'}
        </div>
    </div>
    `;
}

function renderForecast(ch8) {
    const hist = ch8.historical_profit || [];
    const forecast = ch8.prediction || {};
    const fc26 = forecast.forecast_2026e || {};

    const histRows = (forecast.historical || []).map((row, i) => {
        const rev = hist[i] ? hist[i] : {};
        return `<tr><td>${row.year || ''}</td><td>${row.revenue || 'N/A'}</td><td>${row.net_profit || 'N/A'}</td></tr>`;
    }).join('');

    return `
    <div class="section-card">
        <div class="section-card-header">
            <span class="section-card-title">净利润预测</span>
            <span class="section-card-badge">${ch8.forecast_method || ''}</span>
        </div>
        <div class="section-card-body">
            <table class="data-table">
                <tr><th>年份</th><th>营业收入</th><th>净利润</th></tr>
                ${histRows || '<tr><td colspan="3" style="text-align:center;color:#8e8e93">历史数据获取中</td></tr>'}
                ${fc26.value ? `<tr style="background:#e8f2ff"><td>2026E（预测）</td><td>—</td><td><strong>${fc26.value}</strong></td></tr>` : ''}
            </table>
            ${fc26.method ? `<p class="text-sm" style="margin-top:8px">预测方法：${fc26.method}</p>` : ''}
            <div class="source-note">来源：新浪财经API历史年报 + 增速外推法</div>
        </div>
    </div>
    `;
}

function renderTarget(ch9, ch1) {
    const pem = ch9.pe_method || {};
    const dcf = ch9.dcf_method || {};
    const peg = ch9.peg_method || {};
    const comp = ch9.comprehensive || {};
    const peComp = comp.pe_method || {};

    return `
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title">目标价来源依据</span></div>
        <div class="section-card-body">
            <div class="val-box">
                <div class="val-cell"><div class="val-cell-label">当前股价</div><div class="val-cell-value">¥${ch1.current_price || 'N/A'}</div></div>
                <div class="val-cell"><div class="val-cell-label">PE估值目标区间</div><div class="val-cell-value" style="font-size:12px">${peComp.target_range || (pem.fair_price_low ? (pem.fair_price_low + ' - ' + pem.fair_price_high + '元') : 'N/A')}</div></div>
                <div class="val-cell"><div class="val-cell-label">上行空间</div><div class="val-cell-value text-up">${peComp.upside || 'N/A'}</div></div>
            </div>
            <table class="data-table">
                <tr><th>估值方法</th><th>核心参数</th><th>目标价结论</th></tr>
                <tr><td>PE估值法</td><td>合理PE区间 ${pem.reasonable_pe_range || peComp.fair_pe || 'N/A'}</td><td>${pem.fair_price_low ? pem.fair_price_low + ' - ' + pem.fair_price_high + '元' : (peComp.target_range || 'N/A')}</td></tr>
                <tr><td>DCF折现法</td><td>${dcf.assumptions ? Object.entries(dcf.assumptions).map(([k,v]) => k+'='+v).join(', ') : 'N/A'}</td><td>${dcf.note || '参见完整模型'}</td></tr>
                <tr><td>PEG分析</td><td>${peg.formula || 'N/A'}</td><td>${peg.benchmark || 'N/A'}</td></tr>
            </table>
            <div class="source-note">来源：PE估值法基于腾讯行情API实时PE + 行业合理PE区间参考值</div>
        </div>
    </div>
    `;
}

function renderTech(ch13) {
    const kl = ch13.key_levels || {};
    const ind = ch13.indicators || {};
    const macd = ind.macd || {};
    const kdj = ind.kdj || {};
    const score = ch13.tech_score || 0;
    const trend = ch13.short_trend || 'N/A';
    const trendClass = trend.includes('上') ? 'trend-up' : trend.includes('下') ? 'trend-down' : 'trend-neutral';
    const details = ch13.tech_details || [];

    return `
    <div class="section-card">
        <div class="section-card-header">
            <span class="section-card-title">技术面量化分析</span>
            <span class="section-card-badge">数据：腾讯K线接口 (web.ifzq.gtimg.cn)</span>
        </div>
        <div class="section-card-body">
            <div style="display:flex;align-items:center;gap:16px;margin-bottom:12px">
                <div>
                    <div class="stat-label">短线趋势</div>
                    <span class="trend-badge ${trendClass}">${trend}</span>
                </div>
                <div>
                    <div class="stat-label">持股参考</div>
                    <span style="font-size:13px;font-weight:600">${ch13.hold_days || 'N/A'}</span>
                </div>
                <div>
                    <div class="stat-label">技术评分</div>
                    <span style="font-size:18px;font-weight:700;font-family:var(--font-mono)">${score}<span style="font-size:12px;font-weight:400;color:#8e8e93">/30</span></span>
                </div>
            </div>
            <div class="score-bar-wrap">
                <div class="score-bar-bg" style="height:8px">
                    <div class="score-bar-fill" style="width:${Math.round(score/30*100)}%;background:${score>=18?'#34c759':score>=12?'#ff9f0a':'#ff3b30'}"></div>
                </div>
            </div>
        </div>
    </div>
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title">关键技术指标</span></div>
        <div class="section-card-body">
            <table class="data-table">
                <tr><th>指标</th><th>数值</th><th>参考基准</th></tr>
                <tr><td>当前价格</td><td class="text-mono">¥${ch13.current_price || 'N/A'}</td><td>—</td></tr>
                <tr><td>MA5</td><td class="text-mono">${kl.ma5 || 'N/A'}</td><td>短期趋势参考</td></tr>
                <tr><td>MA10</td><td class="text-mono">${kl.ma10 || 'N/A'}</td><td>中期趋势参考</td></tr>
                <tr><td>MA20</td><td class="text-mono">${kl.ma20 || 'N/A'}</td><td>中期趋势参考</td></tr>
                <tr><td>MA60</td><td class="text-mono">${kl.ma60 || 'N/A'}</td><td>长期趋势参考</td></tr>
                <tr><td>RSI(14)</td><td class="text-mono">${ind.rsi || 'N/A'}</td><td>&lt;30超卖 / &gt;70超买</td></tr>
                <tr><td>MACD DIF</td><td class="text-mono">${macd.dif || 'N/A'}</td><td>DIF&gt;DEA金叉</td></tr>
                <tr><td>MACD DEA</td><td class="text-mono">${macd.dea || 'N/A'}</td><td>EMA信号线</td></tr>
                <tr><td>MACD 柱</td><td class="text-mono">${macd.hist || 'N/A'}</td><td>&gt;0多头，&lt;0空头</td></tr>
                <tr><td>KDJ K</td><td class="text-mono">${kdj.k || 'N/A'}</td><td>K&gt;D金叉</td></tr>
                <tr><td>KDJ D</td><td class="text-mono">${kdj.d || 'N/A'}</td><td>信号线</td></tr>
                <tr><td>KDJ J</td><td class="text-mono">${kdj.j || 'N/A'}</td><td>&gt;100超买，&lt;0超卖</td></tr>
            </table>
            <div class="source-note">计算方法：MA(简单移动平均)、RSI(Wilder平滑)、MACD(EMA12/26/9)、KDJ(9/3/3)</div>
        </div>
    </div>
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title">参考价位（短线，仅供参考）</span></div>
        <div class="section-card-body">
            <table class="data-table">
                <tr><th>价位</th><th>数值</th><th>说明</th></tr>
                <tr><td>参考买入价</td><td class="text-mono text-blue">¥${ch13.buy_price || 'N/A'}</td><td>低于此价可考虑介入</td></tr>
                <tr><td>短线目标价</td><td class="text-mono text-up">¥${ch13.target_price_short || 'N/A'}</td><td>2-4天参考目标</td></tr>
                <tr><td>止损价</td><td class="text-mono text-down">¥${ch13.stop_loss || 'N/A'}</td><td>跌破则严格止损</td></tr>
            </table>
            <div class="source-note">⚠️ 以上价位仅基于技术指标计算，不构成投资建议，请结合基本面综合判断。</div>
            ${details.length ? `<div style="margin-top:8px">${details.map(d => `<p class="text-sm">• ${d}</p>`).join('')}</div>` : ''}
        </div>
    </div>
    `;
}

function renderRisks(ch11, ch12) {
    const risks = ch11.risks || [];
    const sources = ch12.sources || [];

    const riskHtml = risks.map((r, i) => `
        <div class="risk-item">
            <div class="risk-dot ${i >= risks.length - 2 ? 'critical' : ''}"></div>
            <span>${r}</span>
        </div>
    `).join('');

    const sourceHtml = sources.length ? `
        <table class="data-table" style="margin-top:10px">
            <tr><th>数据源</th><th>接口/URL</th><th>数据类型</th><th>获取时间</th></tr>
            ${sources.map(s => `<tr><td>${s.name}</td><td class="text-mono" style="font-size:10px">${s.url}</td><td>${s.data_type}</td><td class="text-sm">${String(s.time || '').substring(0,16)}</td></tr>`).join('')}
        </table>
    ` : '';

    return `
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title" style="color:#ff3b30">风险提示</span></div>
        <div class="section-card-body">
            ${riskHtml || '<p class="text-sm">暂无风险数据</p>'}
        </div>
    </div>
    <div class="section-card">
        <div class="section-card-header"><span class="section-card-title">信息来源与时效性</span></div>
        <div class="section-card-body">
            ${sourceHtml}
            <p class="text-sm" style="margin-top:10px">${ch12.disclaimer || '本报告由AI自动生成，仅供参考，不构成投资建议。股市有风险，投资需谨慎。'}</p>
        </div>
    </div>
    `;
}

/* ============================================================
   Chapter Navigation
   ============================================================ */
function showChapter(btn, ch) {
    document.querySelectorAll('.ch-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.ch-panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById(`panel-${ch}`);
    if (panel) panel.classList.add('active');
}

/* ============================================================
   PDF Export
   ============================================================ */
async function exportPDF() {
    if (!currentReport || !currentCode) { showToast('请先进行股票分析'); return; }

    const btn = document.getElementById('pdfBtn');
    btn.textContent = '生成中...';
    btn.disabled = true;

    try {
        const resp = await fetch('/api/export_pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: currentCode, report: currentReport })
        });

        if (!resp.ok) {
            const err = await resp.json();
            showToast(`PDF生成失败：${err.error}`);
            return;
        }

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const name = currentReport.ch1_overview?.stock_name || currentCode;
        a.href = url;
        a.download = `${currentCode}_${name}_价值分析报告.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('PDF已下载！');
    } catch (e) {
        showToast('PDF下载失败，请重试');
    } finally {
        btn.innerHTML = `<svg viewBox="0 0 20 20" fill="none" width="14" height="14"><rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" stroke-width="1.4"/><path d="M7 7h6M7 10h6M7 13h4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg> 导出PDF`;
        btn.disabled = false;
    }
}

/* ============================================================
   Helpers
   ============================================================ */
function closeReport() {
    document.getElementById('reportContainer').classList.add('hidden');
    currentReport = null;
    currentCode = null;
}

function ratingColorHex(level) {
    if (['强烈买入','买入','谨慎买入'].includes(level)) return '#34c759';
    if (['增持'].includes(level)) return '#ff9f0a';
    if (['减持','卖出'].includes(level)) return '#ff3b30';
    return '#8e8e93';
}

function showToast(msg, duration = 3000) {
    let toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.classList.remove('hidden');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.add('hidden'), duration);
}

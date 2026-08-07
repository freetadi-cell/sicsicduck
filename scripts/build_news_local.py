#!/usr/bin/env python3
"""
從 news.json + articles_cache/ 生成 news-local.html（測試版新聞頁）。
卡片點擊 → 站內 modal 顯示「改寫摘要」+ 原文按鈕。
版權：只顯示自撰摘要(rewritten)，不改寫嘅文章退回純標題卡片（外連原文）。
"""
import json, re, html
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "articles_cache"

CSS_BLOCK = open(ROOT / "scripts" / "_news_local_css.html", encoding="utf-8").read()


def esc(s):
    return html.escape(str(s or ""), quote=True)


def load_news():
    with open(DATA_DIR / "news.json", encoding="utf-8") as f:
        return json.load(f).get("articles", [])


def load_summary(aid):
    p = CACHE_DIR / f"{aid}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("status") == "done" and d.get("rewritten"):
            return d["rewritten"]
    except json.JSONDecodeError:
        pass
    return None


def card(a):
    aid = a.get("id", "")
    title = esc(a.get("title", ""))
    desc = esc(a.get("description", ""))
    src = esc(a.get("source_name", ""))
    pub = esc((a.get("pubDate", "") or "")[:10])
    cats = esc(",".join(a.get("category", [])))
    region = esc(a.get("region", ""))
    image = a.get("image_url") or "/default-news.jpg"
    image = esc(image)
    link = esc(a.get("link", "#"))

    summary = load_summary(aid)
    if summary:
        summary_esc = esc(summary)
        # 有本地改寫 → 卡片點擊開 modal, 用 data-modal-id
        inner = f'''<div class="article-image"><img src="{image}" alt="" onerror="this.src='/default-news.jpg'"></div>
            <div class="article-content">
                <h3 class="article-title">{title}</h3>
                <p class="article-description">{summary_esc}</p>
                <div class="article-meta">
                    <span class="article-source">{src}</span>
                    <span class="article-date">📅 {pub}</span>
                </div>
            </div>'''
        card_html = f'''<a href="javascript:void(0)" class="article-card" data-modal-id="{esc(aid)}" data-category="{cats}" data-region="{region}">
        {inner}
    </a>'''
        # 同時產生 modal
        modal = f'''<div class="news-modal" id="modal-{esc(aid)}" data-modal>
        <div class="news-modal-backdrop" onclick="closeModal('{esc(aid)}')"></div>
        <div class="news-modal-dialog">
            <button class="news-modal-close" onclick="closeModal('{esc(aid)}')">✕</button>
            <h2 class="news-modal-title">{title}</h2>
            <div class="news-modal-meta">
                <span class="article-source">{src}</span>
                <span class="article-date">📅 {pub}</span>
            </div>
            <div class="news-modal-body">
                <p class="news-modal-rewritten">{summary_esc}</p>
                <p class="news-modal-copy">* 以上內容為本站以人工智能改寫之摘要，版權屬原媒體所有。</p>
            </div>
            <div class="news-modal-footer">
                <a class="news-modal-link" href="{link}" target="_blank" rel="noopener">📄 閱讀原文 →</a>
            </div>
        </div>
    </div>'''
        return card_html, modal
    else:
        # 冇改寫 → 直接外連（現況）
        inner = f'''<div class="article-image"><img src="{image}" alt="" onerror="this.src='/default-news.jpg'"></div>
            <div class="article-content">
                <h3 class="article-title">{title}</h3>
                <p class="article-description">{desc}</p>
                <div class="article-meta">
                    <span class="article-source">{src}</span>
                    <span class="article-date">📅 {pub}</span>
                </div>
            </div>'''
        return f'''<a href="{link}" target="_blank" class="article-card" data-category="{cats}" data-region="{region}">
        {inner}
    </a>''', None


def build():
    import sys
    # --summary-only 模式：只顯示已改寫嘅文章（測試用，避免幾千張外連圖拖垮頁面）
    summary_only = "--summary-only" in sys.argv

    articles = load_news()
    cards_html = []
    modals_html = []
    shown = 0
    for a in articles:
        c, m = card(a)
        if summary_only and m is None:
            continue  # 只揀有站內摘要嘅
        cards_html.append(c)
        if m:
            modals_html.append(m)
        shown += 1

    grid = "\n".join(cards_html)
    modals = "\n".join(modals_html)

    # 由現有 news.html 複製 header/footer/script 結構
    base = ROOT / "news.html"
    src = base.read_text(encoding="utf-8")

    # 抽 header（到 hero 前）— 用簡單 string 定位
    header_start = src.index('<header class="header">')
    hero_start = src.index('<!-- Hero -->')

    # 抽 footer + script（最後完整 block）
    footer_start = src.index('<!-- Footer -->')

    header_html = src[header_start:hero_start]

    # script：抽取 <script>...</script> 最後一段（剔除原始 articles grid 更新邏輯唔需要，保留 search/category/modal 兼容）
    script_html = '''<script>
function toggleNav() {
    document.getElementById('navDropdown').classList.toggle('open');
}
document.addEventListener('click', function(e) {
    const wrap = document.querySelector('.nav-dropdown-wrap');
    if (!wrap.contains(e.target)) {
        document.getElementById('navDropdown').classList.remove('open');
    }
});

function classifyArticle(article) {
    const title = (article.querySelector('.article-title')?.textContent || '').toLowerCase();
    const desc = (article.querySelector('.article-description')?.textContent || '').toLowerCase();
    const text = title + ' ' + desc;
    const stockKeywords = ['股票','港股','美股','股市','恒指','納指','道指','上證','深證','a股','ipo','股份','股價','升市','跌市','牛市','熊市','成交','恆生','證券','基金'];
    const propertyKeywords = ['地產','樓市','樓價','屋苑','物業','住宅','新盤','樓花','租金','買樓','賣樓','地皮','發展商','地產商','樓宇','房地產','置業','按揭'];
    const interestKeywords = ['利率','利息','息口','加息','減息','聯儲局','央行','基準利率','存款利率','貸款利率','按揭利率','孳息','債息','國債','息率'];
    let categories = [];
    if (stockKeywords.some(kw => text.includes(kw))) categories.push('stock');
    if (propertyKeywords.some(kw => text.includes(kw))) categories.push('property');
    if (interestKeywords.some(kw => text.includes(kw))) categories.push('interest');
    if (categories.length > 0) {
        const existing = article.dataset.category || '';
        article.dataset.category = existing + ',' + categories.join(',');
    }
}
document.querySelectorAll('.article-card').forEach(classifyArticle);

let currentSearch = '';
let currentCategory = 'all';
function applyFilters() {
    const articles = document.querySelectorAll('.article-card');
    let shown = 0;
    articles.forEach(article => {
        const title = (article.querySelector('.article-title')?.textContent || '').toLowerCase();
        const desc = (article.querySelector('.article-description')?.textContent || '').toLowerCase();
        const cats = (article.dataset.category || '').split(',').map(c => c.trim().toLowerCase());
        const matchCat = currentCategory === 'all' || cats.includes(currentCategory.toLowerCase());
        const matchSearch = !currentSearch || title.includes(currentSearch) || desc.includes(currentSearch);
        if (matchCat && matchSearch) { article.style.display = ''; shown++; }
        else { article.style.display = 'none'; }
    });
    const countEl = document.getElementById('searchResultCount');
    if (currentSearch) {
        countEl.textContent = '顯示 ' + shown + ' / ' + articles.length + ' 篇新聞';
        countEl.classList.add('show');
    } else { countEl.classList.remove('show'); }
}
function filterBySearch() {
    currentSearch = document.getElementById('searchInput').value.trim().toLowerCase();
    document.getElementById('searchClear').classList.toggle('show', currentSearch.length > 0);
    applyFilters();
}
function clearSearch() {
    document.getElementById('searchInput').value = '';
    currentSearch = '';
    document.getElementById('searchClear').classList.remove('show');
    applyFilters();
}
document.querySelectorAll('.category-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.category-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        currentCategory = tab.dataset.category;
        applyFilters();
    });
});

// Modal 開關
function openModal(id) {
    const m = document.getElementById('modal-' + id);
    if (m) { m.classList.add('open'); document.body.style.overflow = 'hidden'; }
}
function closeModal(id) {
    const m = document.getElementById('modal-' + id);
    if (m) { m.classList.remove('open'); document.body.style.overflow = ''; }
}
document.querySelectorAll('.article-card[data-modal-id]').forEach(card => {
    card.addEventListener('click', (e) => {
        e.preventDefault();
        openModal(card.dataset.modalId);
    });
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.news-modal.open').forEach(m => closeModal(m.id.replace('modal-','')));
    }
});
</script>'''

    footer_html = f'''<!-- Footer -->
<div class="footer">
    <div class="disclaimer">
        <strong>⚠️ 免責聲明</strong><br>
        本網站所載之一切資訊僅供參考，不構成任何投資、財務或稅務建議。投資者應根據自身情況作出獨立判斷，並在有需要時諮詢專業財務顧問。<br>
        新聞內容為本站以人工智能改寫之摘要，版權屬原媒體所有，完整內容請前往來源網站閱讀。<br>
        聯絡我們：<a href="mailto:hello@sicsicduck.com" style="color:var(--gold-700)">hello@sicsicduck.com</a>
    </div>
</div>
{script_html}
</body>
</html>'''

    out = f'''<!DOCTYPE html>
<html lang="zh-HK">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>新聞（站內版測試）| 食息鴨</title>
    <meta name="description" content="最新新聞資訊、投資理財、財經動態">
    <meta name="keywords" content="新聞,財經,投資理財,香港新聞">
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+TC:wght@300;400;500;700&display=swap" rel="stylesheet">
    {CSS_BLOCK}

    <style>
        /* ==== 站內版新聞 Modal CSS ==== */
        .news-modal {{
            display: none;
            position: fixed;
            inset: 0;
            z-index: 300;
        }}
        .news-modal.open {{ display: block; }}
        .news-modal-backdrop {{
            position: absolute; inset: 0;
            background: rgba(0,0,0,0.55);
            backdrop-filter: blur(2px);
        }}
        .news-modal-dialog {{
            position: relative;
            z-index: 2;
            max-width: 640px;
            margin: 6vh auto 0;
            background: var(--white);
            border-radius: 16px;
            box-shadow: var(--shadow-xl);
            padding: 28px 28px 24px;
            max-height: 82vh;
            overflow-y: auto;
            border: 1px solid var(--gold-200);
        }}
        .news-modal-close {{
            position: absolute; top: 14px; right: 14px;
            width: 32px; height: 32px;
            border: none; border-radius: 50%;
            background: var(--gray-100);
            color: var(--gray-600);
            font-size: 16px; cursor: pointer;
        }}
        .news-modal-close:hover {{ background: var(--gold-200); color: var(--gold-800); }}
        .news-modal-title {{
            font-size: 20px; font-weight: 800;
            color: var(--gray-900); margin: 4px 40px 10px 0;
            line-height: 1.4;
        }}
        .news-modal-meta {{
            display: flex; gap: 14px; align-items: center;
            font-size: 13px; color: var(--gold-700);
            margin-bottom: 16px;
        }}
        .news-modal-body {{ border-top: 1px solid var(--gray-200); padding-top: 16px; }}
        .news-modal-rewritten {{
            font-size: 15px; line-height: 1.75;
            color: var(--gray-800);
        }}
        .news-modal-copy {{
            margin-top: 16px; font-size: 12px;
            color: var(--gray-500);
            background: var(--gold-100);
            border-left: 3px solid var(--gold-400);
            padding: 8px 12px; border-radius: 6px;
        }}
        .news-modal-footer {{ margin-top: 20px; text-align: right; }}
        .news-modal-link {{
            display: inline-block;
            padding: 10px 20px;
            background: linear-gradient(135deg, var(--gold-500), var(--gold-600));
            color: var(--white);
            border-radius: 10px;
            text-decoration: none;
            font-weight: 700; font-size: 14px;
        }}
        .news-modal-link:hover {{ filter: brightness(1.05); }}
        .test-banner {{
            background: linear-gradient(90deg, var(--gold-500), var(--gold-600));
            color: var(--white);
            text-align: center;
            padding: 10px 16px;
            font-size: 13px; font-weight: 600;
        }}
    </style>
</head>
<body>

<div class="test-banner">🧪 測試頁：站內新聞摘要版本（尚未上線）</div>

{header_html}
<!-- Hero -->
<section class="hero">
    <h1>📰 新聞</h1>
    <p>站內摘要版測試 — 點擊卡片即睇改寫內容，唔使跳走</p>
</section>

<!-- Search Box -->
<div class="search-wrap">
    <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" placeholder="搜尋新聞關鍵字..." oninput="filterBySearch()">
        <button class="search-clear" id="searchClear" onclick="clearSearch()">✕</button>
    </div>
</div>
<div class="search-result-count" id="searchResultCount"></div>

<!-- Category Tabs -->
<div class="category-tabs">
    <button class="category-tab active" data-category="all">全部</button>
    <button class="category-tab" data-category="business">財經</button>
    <button class="category-tab" data-category="stock">股市</button>
    <button class="category-tab" data-category="property">地產</button>
    <button class="category-tab" data-category="interest">利率</button>
    <button class="category-tab" data-category="technology">科技</button>
    <button class="category-tab" data-category="entertainment">娛樂</button>
    <button class="category-tab" data-category="sports">體育</button>
    <button class="category-tab" data-category="science">科學</button>
    <button class="category-tab" data-category="health">健康</button>
    <button class="category-tab" data-category="politics">政治</button>
</div>

<!-- Articles Section -->
<section class="articles-section">
    <div class="articles-grid" id="articlesGrid">
{grid}
    </div>
</section>

{modals}

{footer_html}
'''

    out_path = ROOT / "news-local.html"
    out_path.write_text(out, encoding="utf-8")
    print(f"✅ 生成 {out_path.name}（{len(articles)} 篇，{modals.count('news-modal') if modals else 0} 個 modal）")

    # 檢查大細
    size_kb = out_path.stat().st_size / 1024
    print(f"   檔案大小: {size_kb:.0f} KB")


if __name__ == "__main__":
    build()

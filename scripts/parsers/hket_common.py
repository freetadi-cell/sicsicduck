"""通用 HKET 定期存款利率解析器

設計目標：
1. 不依賴固定的新聞 ID 或標題格式
2. 基於銀行名稱識別數據
3. 支援多種利率格式（% 和 厘）
4. 靈活解析不同表格結構

適用銀行：
- 中信銀行（國際）
- 富融銀行
- 平安數字銀行
- 螞蟻銀行
- 其他虛擬銀行

使用方法：
    from parsers.hket_common import parse_hket_article
    
    rates = parse_hket_article(text, bank_name='中信銀行（國際）')
"""
import re


# 銀行名稱識別映射
BANK_NAME_MAPPING = {
    '中信銀行（國際）': ['中信銀行（國際）', '中信銀行國際', '信銀國際', 'CNCBI'],
    '富融銀行': ['富融銀行', 'Fusion Bank', 'Fusion'],
    '平安數字銀行': ['平安數字銀行', '平安銀行', 'PAObank', 'PAO bank'],
    '螞蟻銀行': ['螞蟻銀行', 'Ant Bank', 'Ant'],
    '中信銀行': ['中信銀行', 'CITIC'],
}


def parse_hket_article(text, bank_name=None):
    """從 HKET 文章中提取定期存款利率
    
    Args:
        text: HKET 文章全文
        bank_name: 銀行名稱（可選，會自動識別）
    
    Returns:
        dict: 利率數據
    """
    if not text:
        return None
    
    # 自動識別銀行
    if not bank_name:
        bank_name = detect_bank_name(text)
    
    if not bank_name:
        return None
    
    # 截斷文章尾部嘅推薦/焦點區塊（「今日焦點」「最新專欄文章」等），
    # 防止誤食其他銀行嘅利率（例如「建設銀行7.88厘」）。
    text = _truncate_article(text)
    
    rates = {
        'bank': bank_name,
        'source': 'hket',
        'hkd': {},
        'usd': {},
        'cny': {}
    }
    
    lines = text.split('\n')
    
    # 追蹤當前區塊（新客戶/新資金/現有資金）
    current_section = 'general'
    current_currency = 'hkd'

    # 表格模式狀態：期數行同利率行分開（例：「3個月\n2.7厘\n6個月\n3.0厘」）
    table_mode = False
    pending_period = None  # 等待配對利率嘅期數
    pending_section = None  # 該期數所屬嘅 section
    pending_currency = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 識別區塊標題（完整標題行，如「信銀國際現有客戶新資金2.95厘港元定存」）
        section = detect_section(line)
        if section:
            current_section = section
            # 從標題行提取貨幣（如果有）
            currency_in_title = detect_currency(line)
            if currency_in_title:
                current_currency = currency_in_title
            continue
        
        # 識別貨幣
        currency = detect_currency(line)
        if currency:
            current_currency = currency
        
        # 提取利率
        rate_data = extract_rate_from_line(line)

        # ---- 表格模式：期數同利率分開行 ----
        # 純期數行（如「3個月」「6個月」，唔帶利率）——記低等候配對
        period_only = _extract_period_only(line) if not rate_data else None
        if period_only and not rate_data:
            pending_period = period_only
            pending_section = current_section
            pending_currency = current_currency
            table_mode = True
            continue
        
        # 純利率行（如「2.7厘」「3.0厘」，唔帶期數）——同之前嘅期數配對
        if rate_data is None and pending_period and not _extract_period_only(line):
            rate_only = _extract_rate_only(line)
            if rate_only is not None:
                period_key = pending_period
                period_section = pending_section or current_section
                period_currency = pending_currency or current_currency
                _store_rate(rates, period_currency, period_key, rate_only, 0, period_section)
                pending_period = None  # 已配對
                pending_section = None
                pending_currency = None
                continue
            # 遇到其他非利率內容（如「不設最低存款額」），保留 pending 但唔清空

        if rate_data:
            period = rate_data['period']
            rate = rate_data['rate']
            min_deposit = rate_data.get('min_deposit', 0)
            
            # 特殊處理：過濾明顯錯誤嘅利率
            if period == '1w' and rate > 10.0 and current_section not in ('flash_promotion', 'new_funds'):
                continue
            
            _store_rate(rates, current_currency, period, rate, min_deposit, current_section)
    
    # 清理空的幣種
    for currency in ['hkd', 'usd', 'cny']:
        if not rates.get(currency):
            del rates[currency]
    
    return rates if rates.get('hkd') or rates.get('usd') else None


def _store_rate(rates, currency, period, rate, min_deposit, section):
    """將一筆利率存入 rates 結構，根據 section 分類。"""
    if currency not in rates:
        rates[currency] = {}
    if period not in rates[currency]:
        rates[currency][period] = {}
    
    # 根據區塊類型決定 note 和 source
    if section == 'new_funds':
        note = '新資金定期存款優惠'
    elif section == 'existing_funds':
        note = '定期存款牌價利率'
    elif section == 'new_customer':
        note = '新客戶定期存款優惠'
    elif section == 'flash_promotion':
        note = '快閃定期存款優惠'
    else:
        note = '定期存款'
    
    source = 'hket'
    rates[currency][period][section] = {
        'rate': rate,
        'min_deposit': min_deposit,
        'note': note,
        'source': source
    }


def _extract_period_only(line):
    """只提取期數（唔帶利率），如「3個月」「6個月」「1星期」。返回 period key；唔係期數行就 None。"""
    m = re.match(r'^(\d+)\s*(個月|月|星期|周)$', line)
    if not m:
        return None
    num, unit = m.group(1), m.group(2)
    return f"{num}w" if unit in ('星期', '周') else f"{num}m"


def _extract_rate_only(line):
    """只提取利率（唔帶期數），如「2.7厘」「3.0厘」「2.80%」。返回 float；唔係利率行就 None。"""
    m_li = re.search(r'(\d+\.?\d*)厘', line)
    m_pct = re.search(r'(\d+\.?\d*)%', line)
    if m_li:
        return float(m_li.group(1))
    elif m_pct:
        return float(m_pct.group(1))
    return None


ARTICLE_END_MARKERS = ['資料來源', '更多資訊請看', '今日焦點', '最新專欄文章', '訂閱《香港經濟日報》']


def _truncate_article(text):
    """截斷 HKET 文章尾部嘅推薦/焦點區塊。"""
    if not text:
        return text
    end_positions = [text.find(m) for m in ARTICLE_END_MARKERS if text.find(m) >= 0]
    if end_positions:
        return text[:min(end_positions)]
    return text


def detect_bank_name(text):
    """從文章中識別銀行名稱"""
    for standard_name, aliases in BANK_NAME_MAPPING.items():
        for alias in aliases:
            if alias in text:
                return standard_name
    return None


def detect_section(line):
    """識別區塊類型（新客戶/新資金/現有資金）"""
    line_lower = line.lower()
    
    # 快閃活動要優先識別，因為佢有特殊利率
    if '快閃' in line or '閃購' in line or '快搶' in line:
        return 'flash_promotion'
    
    # 特殊識別「（新客戶專有）」格式（富融銀行）
    if '（新客戶專有）' in line or '新客戶專有' in line:
        return 'new_customer'
    
    if '全新客戶' in line:
        return 'new_customer'
    elif '現有客戶新資金' in line:
        return 'new_funds'
    elif '新資金' in line and '現有' not in line:
        return 'new_funds'
    elif '現有資金' in line:
        return 'existing_funds'
    elif '零元起存' in line or '最低存款' in line or '不論新舊資金' in line:
        # 「零元起存」「不論新舊資金」= 不限資金來源嘅牌價（general）
        return 'general'
    
    return None


def detect_currency(line):
    """識別貨幣類型"""
    if '美元' in line or 'USD' in line.upper():
        return 'usd'
    elif '人民幣' in line or 'CNY' in line or 'RMB' in line.upper():
        return 'cny'
    elif '港元' in line or '港幣' in line or 'HKD' in line.upper():
        return 'hkd'
    return None


def extract_rate_from_line(line):
    """從一行文字中提取利率
    
    支援格式：
    - 3個月 2.80%
    - 12個月 2.95厘
    - 1星期 6.88%
    - 100萬元至200萬元 3.30%
    - 10萬元 1.5厘（螞蟻銀行格式）
    """
    # 過濾標題行（包含「最高」「每日更新」等）
    title_indicators = ['最高', '每日更新', '定期存款年利率', '存款期年利率', '總年利率']
    for indicator in title_indicators:
        if indicator in line and '存款期' not in line:
            return None
    
    # 提取存款期
    period_match = re.search(r'(\d+)\s*(個月|月|星期|周)', line)
    if not period_match:
        return None
    
    period_num = period_match.group(1)
    period_unit = period_match.group(2)
    
    # 轉換存款期
    if period_unit in ['星期', '周']:
        period = f"{period_num}w"
    elif period_unit == '月':
        period = f"{period_num}m"
    else:
        period = f"{period_num}m"
    
    # 提取利率（支援 % 和 厘）
    # 統一輸出為百分比格式：2.95厘 = 2.95%，2.80% = 2.80
    # 注意：要先匹配「厘」再匹配「%」，因為「25厘」唔係「25%厘」
    rate_match_li = re.search(r'(\d+\.?\d*)厘', line)
    rate_match_percent = re.search(r'(\d+\.?\d*)%', line)
    
    if rate_match_li:
        # 「厘」= 百分比：2.95厘 = 2.95%
        rate = float(rate_match_li.group(1))
    elif rate_match_percent:
        # 「%」直接取數字：2.80% = 2.80
        rate = float(rate_match_percent.group(1))
    else:
        return None
    
    # 提取最低存款額
    min_deposit = 0
    
    # 優先匹配「10萬元」格式（螞蟻銀行：10萬元新資金）
    amount_match_wan = re.search(r'(\d+)萬元', line)
    if amount_match_wan:
        min_deposit = int(amount_match_wan.group(1)) * 10000
    else:
        # 嘗試匹配「100萬元至200萬元」格式
        amount_match_range = re.search(r'(\d+)萬元至', line)
        if amount_match_range:
            min_deposit = int(amount_match_range.group(1)) * 10000
        else:
            # 嘗試匹配「港元定期」前面嘅金額
            amount_match_prefix = re.search(r'(\d+)萬港元', line)
            if amount_match_prefix:
                min_deposit = int(amount_match_prefix.group(1)) * 10000
            else:
                # 嘗試提取「100元」「1元」等
                amount_match_yuan = re.search(r'(\d+)元', line)
                if amount_match_yuan:
                    min_deposit = int(amount_match_yuan.group(1))
    
    return {
        'period': period,
        'rate': rate,
        'min_deposit': min_deposit
    }


def parse(text, tables=None, html=None):
    """通用 HKET 文章解析入口
    
    這個函數會自動識別銀行名稱並提取利率。
    適用於所有從 HKET 抓取的虛擬銀行利率。
    """
    return parse_hket_article(text)
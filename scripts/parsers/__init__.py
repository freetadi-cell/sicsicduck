# Bank rate parsers - each file handles one bank
# Filename format: <bank_key>.py
# Each must export: parse(page_text: str, tables: list) -> dict or None
#
# Return format:
# {
#     'hkd': {'1m': rate, '3m': rate, '6m': rate, '12m': rate},
#     'usd': {'1m': rate, '3m': rate, '6m': rate, '12m': rate},
#     'note': 'optional note',  # optional
# }
# Or None if parsing fails
#
# ⚠️ 利率單位規範：
# 所有 parser 輸出嘅 rate 必須係百分比格式（e.g. 2.95 表示 2.95%）
# 唔可以用小數格式（e.g. 0.0295 表示 2.95%）
# 使用 normalize_rate() 確保單位一致

from .hsbc import parse as parse_hsbc
from .bochk import parse as parse_bochk
from .hangseng import parse as parse_hangseng
from .sc import parse as parse_sc
from .dbs import parse as parse_dbs
from .bea import parse as parse_bea
from .cncbi import parse as parse_cncbi
from .icbc import parse as parse_icbc
from .fubon import parse as parse_fubon
from .bocomm import parse as parse_bocomm
from .shacom import parse as parse_shacom
from .publicbank import parse as parse_publicbank
from .winglung import parse as parse_winglung
from .chbank import parse as parse_chbank
from .fusion import parse as parse_fusion
from .airstar import parse as parse_airstar
from .za import parse as parse_za
from .pao import parse as parse_pao
from .welab import parse as parse_welab
from .livi import parse as parse_livi
from .ant import parse as parse_ant
from .chiyu import parse as parse_chiyu
from .pingan import parse as parse_pingan
from .ncb import parse as parse_ncb


# ============================================================
# 利率正規化工具
# ============================================================

# 2026年香港定期存款利率合理範圍
RATE_BOUNDS = {
    'hkd': (0.001, 10.0),
    'usd': (0.001, 6.0),
    'cny': (0.001, 5.0),
}


def _count_decimal_places(value):
    """計算一個浮點數嘅小數位數（有效位，唔計尾零）。"""
    s = f"{value:.10f}".rstrip('0').rstrip('.')
    if '.' in s:
        return len(s.split('.')[1])
    return 0


def _is_likely_decimal_format(rate, currency, tenor, source):
    """判斷一個 rate 值係咪「小數格式」（即需要乘以 100 先係百分比）。

    核心啟發式：
    ─────────────────────────────────────────────
    小數格式嘅特徵（需要 ×100）：
    - 值喺 0.001 - 0.5 之間
    - 乘以 100 後落入合理利率範圍（0.1% - 10%）
    - 通常有 3-4 位小數（因為係百分比 ÷ 100）
    - 例子：0.0295→2.95%, 0.038→3.8%, 0.013→1.3%, 0.05→5%

    百分比格式嘅特徵（唔使轉）：
    - 值 >= 0.5（0.5% 以上嘅利率好常見）
    - 乘以 100 後超出合理範圍（e.g. 0.1×100=10% 好罕見）
    - 通常只有 1-2 位小數
    - 例子：0.1%=0.1, 0.5%=0.5, 2.95%=2.95, 0.01%=0.01
    ─────────────────────────────────────────────

    判斷流程：
    1. rate >= 1.0 → 唔係小數格式（1% 以上唔可能係小數格式）
    2. rate >= 0.5 → 唔係小數格式（0.5% 常見，50% 唔合理）
    3. 0.01 < rate < 0.5：
       a. 小數位數 >= 3 → 係小數格式（0.0295, 0.038 等）
       b. 小數位數 == 2：
          - rate*100 喺合理範圍 → 係小數格式（0.05→5%, 0.25→25%?）
          - 但要排除 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50 呢啲
            睇落似「整齊百分比」嘅值（0.10%=0.10, 0.25%=0.25）
          - 判斷：如果 rate*100 係整數或 .5 結尾，且 rate 本身
            只有 1-2 位小數，更可能係百分比格式
       c. 小數位數 == 1：
          - rate*100 喺合理範圍 → 可能係小數格式
          - 但 0.1, 0.2, 0.3, 0.4, 0.5 呢啲更可能係百分比格式
          - 保守策略：唔轉換
    4. rate <= 0.01：
       a. rate == 0.01 → 睇 source 同 tenor
          - hket source → 1%（HKET 報優惠利率）
          - bank source + 短年期 → 0.01%（牌價）
          - bank source + 長年期 → 1%
       b. rate < 0.01 → 唔轉換（極低利率，0.001% 等）
    """
    lo, hi = RATE_BOUNDS.get(currency, (0.001, 10.0))
    decimal_places = _count_decimal_places(rate)
    converted = rate * 100

    # 1. rate >= 1.0 → 百分比格式
    if rate >= 1.0:
        return False

    # 2. rate >= 0.5 → 百分比格式
    # 0.5% 常見，50% 唔合理
    if rate >= 0.5:
        return False

    # 3. 0.01 < rate < 0.5
    if rate > 0.01:
        # 小數位數 >= 3 → 大概率係小數格式
        # e.g. 0.0295(4位)→2.95%, 0.038(3位)→3.8%, 0.013(3位)→1.3%
        # e.g. 0.0135(4位)→1.35%, 0.0285(4位)→2.85%
        if decimal_places >= 3:
            if lo <= converted <= hi:
                return True
            return False

        # 小數位數 == 2
        # e.g. 0.05→5%, 0.25→25%, 0.15→15%, 0.35→3.5%?
        # 呢度最棘手：0.05 可以係 5% 或 0.05%
        # 關鍵判斷：0.05 如果係小數格式，5% 好合理
        #          0.05 如果係百分比格式，0.05% 極低但可能
        # 啟發式：如果 rate*100 係整數且喺 1-10 範圍，更可能係小數格式
        #         如果 rate 本身似「整齊百分比」（0.05, 0.10, 0.15, 0.20, 0.25），
        #         要睇 source
        if decimal_places == 2:
            if lo <= converted <= hi:
                # converted 喺合理範圍
                # 如果 converted 係整數（5, 3, 2 等），更可能係小數格式
                # 如果 converted 有小數（3.5, 2.5 等），都可能
                # 但要排除 0.05%=0.05 呢種情況
                # 關鍵：0.05% 嘅定期存款極罕見，5% 更常見
                # 所以如果 converted 喺 1-10 範範圍，傾向小數格式
                if 1.0 <= converted <= hi:
                    return True
                # converted < 1.0（e.g. 0.5%），更可能係百分比格式
                return False
            return False

        # 小數位數 == 1
        # e.g. 0.1→10%, 0.2→20%, 0.3→30%, 0.4→40%
        # 呢啲乘以 100 後都超出合理範圍（>10%），所以唔係小數格式
        # 例外：0.1→10% 喺 HKD 上限邊界，但 10% 定期極罕見
        return False

    # 4. rate <= 0.01
    if rate == 0.01:
        # 0.01 可以係 0.01% 或 1%
        # 睇 source：hket 報優惠利率 → 1% 更合理
        # bank 官網：0.01% 可能係牌價
        if source == 'hket':
            return True  # 0.01 → 1%
        # bank source：睇 tenor
        if tenor in ('1w', '2w', '1m', '2m'):
            return False  # 短年期牌價，0.01% 更可能
        return True  # 長年期，1% 更合理

    # rate < 0.01
    # e.g. 0.001, 0.002, 0.005, 0.0105
    # 呢啲極小值通常唔係百分比格式（0.001% 極罕見）
    # 但如果 source 係 hket，更可能係小數格式
    # 因為 HKET 報嘅係優惠利率，唔會報 0.001% 呢種極低利率
    if source == 'hket':
        converted = rate * 100
        if lo <= converted <= hi:
            return True  # hket source + 極小值 → 小數格式

    # bank/uhk source：極小值更可能係真實嘅極低利率
    # e.g. 0.001% = 0.001（牌價）
    # 但 0.0105, 0.0115 呢啲有 3+ 位小數嘅，更可能係小數格式
    if decimal_places >= 4:
        converted = rate * 100
        if lo <= converted <= hi:
            return True

    return False


def normalize_rate(rate, currency='hkd', tenor=None, source=None):
    """正規化利率為百分比格式。

    統一規範：輸出永遠係百分比格式
    - 2.95 表示 2.95%
    - 唔接受 0.0295 呢種小數格式

    Args:
        rate: 原始利率值
        currency: 貨幣類型 ('hkd', 'usd', 'cny')
        tenor: 存款期（可選），用於上下文判斷
        source: 數據來源（可選），用於上下文判斷

    Returns:
        float: 正規化後嘅百分比格式利率，或 None 如果無效
    """
    if rate is None:
        return None

    try:
        rate = float(rate)
    except (ValueError, TypeError):
        return None

    # 無效利率
    if rate <= 0:
        return None

    lo, hi = RATE_BOUNDS.get(currency, (0.001, 10.0))

    # 判斷係咪小數格式
    if _is_likely_decimal_format(rate, currency, tenor, source):
        converted = round(rate * 100, 4)
        if lo <= converted <= hi:
            return converted
        # converted 超出範圍，保持原值
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"normalize_rate: rate={rate} 判斷為小數格式但 ×100={converted}% 超出 {currency.upper()} 範圍，保持原值")
        return rate

    # 百分比格式，直接返回
    if rate > hi:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"normalize_rate: rate={rate}% 超出 {currency.upper()} 合理上限 {hi}%，可能係異常數據 (tenor={tenor}, source={source})")

    return rate


def normalize_rates(parsed_rates):
    """對整個 parser 輸出做利率正規化。

    遍歷所有幣種、年期、資金類型嘅 rate，用 normalize_rate() 統一格式。

    Args:
        parsed_rates: parser 返回嘅完整利率字典

    Returns:
        dict: 正規化後嘅利率字典（原地修改）
    """
    if not parsed_rates:
        return parsed_rates

    for currency in ['hkd', 'usd', 'cny']:
        if currency not in parsed_rates:
            continue

        curr_data = parsed_rates[currency]
        if not isinstance(curr_data, dict):
            continue

        for tenor, tenor_data in curr_data.items():
            if not isinstance(tenor_data, dict):
                continue

            # 處理嵌套結構（new_funds/existing_funds/exchange/new_customer/general）
            for fund_type, fund_data in tenor_data.items():
                if not isinstance(fund_data, dict):
                    continue

                if 'rate' in fund_data and fund_data['rate'] is not None:
                    original = fund_data['rate']
                    src = fund_data.get('source', None)
                    normalized = normalize_rate(original, currency=currency, tenor=tenor, source=src)
                    if normalized is None:
                        fund_data['rate'] = None
                    elif normalized != original:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"normalize_rates: {currency.upper()} {tenor} {fund_type}: {original} → {normalized}")
                        fund_data['rate'] = normalized

            # 處理扁平結構（直接有 rate key 喺 tenor 層級）
            if 'rate' in tenor_data and tenor_data['rate'] is not None:
                original = tenor_data['rate']
                src = tenor_data.get('source', None)
                normalized = normalize_rate(original, currency=currency, tenor=tenor, source=src)
                if normalized is None:
                    tenor_data['rate'] = None
                elif normalized != original:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"normalize_rates: {currency.upper()} {tenor}: {original} → {normalized}")
                    tenor_data['rate'] = normalized

    return parsed_rates

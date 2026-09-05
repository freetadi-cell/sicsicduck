#!/usr/bin/env python3
"""
LLM 全量驗證 + Fallback — 用 kimi-k3 驗證所有銀行利率

策略：
1. Parser 先跑（免費、快）
2. 每間銀行嘅 raw text 送 kimi-k3 做獨立抽取
3. 比對 Parser 結果同 LLM 結果
4. 不一致 → 以 LLM 為準 + 標記異常
5. Parser 完全失敗 → LLM 直接接管
"""
import json
import re
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# LLM config — environment variables take precedence; otherwise use the
# provider configured in OpenClaw's private config.
def _load_openclaw_provider():
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    try:
        config = json.loads(config_path.read_text())
        provider = config.get("models", {}).get("providers", {}).get("yuanyuai", {})
        return provider.get("apiKey", ""), provider.get("baseUrl") or provider.get("api", "")
    except (OSError, json.JSONDecodeError, TypeError):
        return "", ""


_CONFIG_API_KEY, _CONFIG_BASE_URL = _load_openclaw_provider()
LLM_BASE_URL = os.environ.get("LLM_BASE_URL") or _CONFIG_BASE_URL or "https://api.moonshot.cn/v1"
LLM_API_KEY = os.environ.get("LLM_API_KEY") or _CONFIG_API_KEY
LLM_MODEL = os.environ.get("LLM_MODEL", "kimi-k3")
LLM_TIMEOUT = 60

# Rate comparison tolerance (percentage points)
RATE_DIFF_TOLERANCE = 0.05  # 0.05% 以內視為一致


EXTRACTION_PROMPT_TEMPLATE = """你係一個香港銀行定期存款利率提取助手。我會畀你一段從銀行官網抓到嘅文字，請提取所有定期存款利率。

要求：
1. 輸出 JSON，格式如下：
{{
  "hkd": {{
    "3m": {{"new_funds": 2.65, "existing_funds": 2.55}},
    "6m": {{"new_funds": 2.65, "existing_funds": 2.55}},
    "12m": {{"new_funds": 2.65, "existing_funds": 2.55}}
  }},
  "usd": {{ ... }},
  "cny": {{ ... }}
}}

2. 利率必須係百分比格式（例如 2.65 表示 2.65%），唔好用小數格式
3. 如果只有「新資金」冇「現有資金」嘅區分，將新資金利率放入 new_funds，existing_funds 設為 null
4. 如果只見到一個利率（冇分新資金/現有資金），放入 new_funds
5. 如果某幣種冇定期存款資料，唔好放該幣種
6. 只輸出 JSON，唔好加解釋

銀行名稱：{bank_name}
文字內容：
---
{text}
---"""


def _call_llm(prompt):
    """呼叫 LLM API"""
    try:
        import httpx
    except ImportError:
        os.system("pip install httpx -q")
        import httpx

    if not LLM_API_KEY:
        logger.warning("LLM: 未設定 LLM_API_KEY")
        return None

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "你係一個精確嘅數據提取助手。只輸出 JSON，唔好加任何解釋。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0,
        "max_tokens": 50000
    }

    try:
        with httpx.Client(timeout=LLM_TIMEOUT) as client:
            resp = client.post(f"{LLM_BASE_URL}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"LLM API error: {e}")
        return None


def _parse_llm_response(text):
    """解析 LLM 返回嘅 JSON，標準化為完整格式"""
    if not text:
        return None

    # 清理 markdown code block
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                data = json.loads(m.group())
            except:
                return None
        else:
            return None

    if not isinstance(data, dict):
        return None

    result = {}
    for currency in ['hkd', 'usd', 'cny']:
        if currency not in data or not isinstance(data[currency], dict):
            continue

        curr_result = {}
        for tenor, rates in data[currency].items():
            if not isinstance(rates, dict):
                continue

            # 簡寫格式（直接有 rate key）
            if 'rate' in rates:
                try:
                    rate_val = float(rates['rate'])
                    if 0 < rate_val < 15:
                        curr_result[tenor] = {
                            'new_funds': {'rate': rate_val, 'min_deposit': 10000, 'note': '新資金定期存款', 'source': 'llm'},
                            'existing_funds': None
                        }
                except (ValueError, TypeError):
                    pass
                continue

            # 完整格式
            period_data = {}
            for fund_type in ['new_funds', 'existing_funds']:
                if fund_type in rates and rates[fund_type] is not None:
                    try:
                        rate_val = float(rates[fund_type])
                        if 0 < rate_val < 15:
                            period_data[fund_type] = {
                                'rate': rate_val,
                                'min_deposit': 10000,
                                'note': f'{"新資金" if fund_type == "new_funds" else "現有資金"}定期存款',
                                'source': 'llm'
                            }
                    except (ValueError, TypeError):
                        continue

            if period_data:
                curr_result[tenor] = period_data

        if curr_result:
            result[currency] = curr_result

    return result if result else None


def _get_rates_flat(rates_dict):
    """將嵌套利率結構攤平成 {(currency, tenor, fund_type): rate}"""
    flat = {}
    if not rates_dict:
        return flat
    for currency in ['hkd', 'usd', 'cny']:
        if currency not in rates_dict:
            continue
        for tenor, tenor_data in rates_dict[currency].items():
            if not isinstance(tenor_data, dict):
                continue
            for fund_type in ['new_funds', 'existing_funds']:
                if fund_type in tenor_data and isinstance(tenor_data[fund_type], dict):
                    rate = tenor_data[fund_type].get('rate')
                    if rate is not None:
                        flat[(currency, tenor, fund_type)] = rate
    return flat


def _compare_rates(parser_flat, llm_flat):
    """比對 Parser 同 LLM 結果，返回差異列表"""
    discrepancies = []
    all_keys = set(parser_flat.keys()) | set(llm_flat.keys())

    for key in all_keys:
        p_rate = parser_flat.get(key)
        l_rate = llm_flat.get(key)
        currency, tenor, fund_type = key

        if p_rate is None and l_rate is not None:
            discrepancies.append({
                'currency': currency, 'tenor': tenor, 'fund_type': fund_type,
                'parser': None, 'llm': l_rate, 'diff': None,
                'type': 'llm_only'
            })
        elif p_rate is not None and l_rate is None:
            # LLM 搵唔到，唔算大問題（可能 text 截斷）
            pass
        elif p_rate is not None and l_rate is not None:
            diff = abs(p_rate - l_rate)
            if diff > RATE_DIFF_TOLERANCE:
                discrepancies.append({
                    'currency': currency, 'tenor': tenor, 'fund_type': fund_type,
                    'parser': p_rate, 'llm': l_rate, 'diff': round(diff, 4),
                    'type': 'mismatch'
                })

    return discrepancies


def llm_verify_all(banks_data):
    """
    全量 LLM 驗證：對每間銀行做獨立抽取，同 Parser 結果比對。

    Args:
        banks_data: list of dicts, 每個包含:
            - name: 銀行名稱
            - key: 銀行 key
            - text: raw text（爬蟲抓到嘅）
            - parsed: parser 返回嘅利率（可能為 None）

    Returns:
        dict with:
            - verified: {key: rates_dict} — LLM 驗證後嘅利率
            - discrepancies: [{bank, ...}] — Parser 同 LLM 不一致嘅記錄
            - stats: {total, parser_ok, llm_fixed, llm_failed}
    """
    if not LLM_API_KEY:
        logger.warning("LLM 全量驗證: 未設定 LLM_API_KEY，跳過")
        return {'verified': {}, 'discrepancies': [], 'stats': {'total': len(banks_data), 'skipped': len(banks_data)}}

    verified = {}
    discrepancies = []
    stats = {'total': len(banks_data), 'parser_ok': 0, 'llm_fixed': 0, 'llm_only': 0, 'llm_failed': 0}

    for bank in banks_data:
        name = bank['name']
        key = bank['key']
        text = bank.get('text', '')
        parsed = bank.get('parsed')

        if not text or len(text) < 50:
            logger.info(f"  LLM 驗證 [{key}]: text 太短，跳過")
            if parsed:
                verified[key] = parsed
            else:
                stats['llm_failed'] += 1
            continue

        # 呼叫 LLM
        logger.info(f"  LLM 驗證 [{name}]...")
        prompt = EXTRACTION_PROMPT_TEMPLATE.format(bank_name=name, text=text[:8000])
        response = _call_llm(prompt)
        llm_rates = _parse_llm_response(response)

        if not llm_rates:
            logger.warning(f"  LLM 驗證 [{key}]: LLM 抽取失敗")
            if parsed:
                verified[key] = parsed  # fallback 到 parser 結果
            else:
                stats['llm_failed'] += 1
            continue

        if not parsed:
            # Parser 完全失敗，LLM 直接接管
            verified[key] = llm_rates
            stats['llm_only'] += 1
            logger.info(f"  🤖 [{name}] Parser 失敗，LLM 直接接管")
            continue

        # 比對 Parser 同 LLM
        parser_flat = _get_rates_flat(parsed)
        llm_flat = _get_rates_flat(llm_rates)
        diffs = _compare_rates(parser_flat, llm_flat)

        if not diffs:
            # 一致，用 parser 結果（結構已知）
            verified[key] = parsed
            stats['parser_ok'] += 1
            logger.info(f"  ✅ [{name}] Parser 同 LLM 一致")
        else:
            # 不一致，以 LLM 為準
            verified[key] = llm_rates
            stats['llm_fixed'] += 1
            for d in diffs:
                d['bank'] = name
                d['key'] = key
                discrepancies.append(d)
            logger.warning(f"  ⚠️ [{name}] Parser 同 LLM 有 {len(diffs)} 處差異，以 LLM 為準")
            for d in diffs:
                logger.warning(f"    {d['currency'].upper()} {d['tenor']} {d['fund_type']}: parser={d['parser']}, llm={d['llm']}, diff={d['diff']}")

    return {'verified': verified, 'discrepancies': discrepancies, 'stats': stats}


def should_use_llm(existing_rates, expected_currencies=None):
    """向舊版 update_rates.py 提供相容判斷。"""
    if not existing_rates:
        return True
    currencies = expected_currencies or ['hkd', 'usd', 'cny']
    return any(not existing_rates.get(currency) for currency in currencies)


def llm_extract_rates(raw_text, bank_name="", existing_rates=None):
    """
    Fallback 模式：Parser 失敗時用 LLM 抽取。
    """
    if not raw_text or len(raw_text) < 50:
        return None

    logger.info(f"LLM fallback: 正在用 LLM 抽取 {bank_name} 嘅利率...")
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(bank_name=bank_name, text=raw_text[:8000])
    response = _call_llm(prompt)
    parsed = _parse_llm_response(response)

    if parsed:
        logger.info(f"LLM fallback: {bank_name} — 成功抽取 {list(parsed.keys())}")
        return parsed

    logger.warning(f"LLM fallback: {bank_name} — 失敗")
    return None

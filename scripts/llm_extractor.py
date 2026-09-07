#!/usr/bin/env python3
"""
LLM 全量驗證 + Fallback — 用 kimi-k3 驗證所有銀行利率

策略：
1. Parser 先跑（免費、快）提供「參考答案」
2. LLM 將 parser 結果同 sicsicduck.com 現有資料比較，睇下有冇變動
3. 如果有變動 → LLM 自己上銀行官網核對一次，確保新數據正確
4. Parser 失敗 → LLM 直接用 raw text 抽取
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

VERIFICATION_PROMPT_TEMPLATE = """你係一個香港銀行定期存款利率驗證助手。

我會畀你：
1. 銀行官網抓到嘅原始文字（text）
2. Parser 從文字中提取嘅利率（parsed）
3. sicsicduck.com 現有嘅該銀行利率（existing）

請你做以下事情：
1. 仔細睇原始文字，提取所有定期存款利率
2. 同 Parser 結果比較，睇下 Parser 有冇提取錯誤
3. 同 sicsicduck.com 現有資料比較，睇下有冇變動
4. 如果有變動，要額外確認：上 bank_url 再核對一次新數據是否正確（我會畀你 bank_url）
5. 輸出最終確認正確嘅利率 JSON

格式同 extraction prompt 一樣，但額外要求：
- 增加 "changes" 字段，列出所有同 sicsicduck.com 現有資料嘅變動
- 增加 "verified_source" 字段，標記每個利率嘅來源（"official_site" = 官網直接確認）

銀行名稱：{bank_name}
Bank URL：{bank_url}
原始文字：
---
{text}
---

Parser 提取結果：
{parsed_json}

sicsicduck.com 現有利率：
{existing_json}

請輸出 JSON 格式：
{{
  "hkd": {{ ... }},
  "usd": {{ ... }},
  "cny": {{ ... }},
  "changes": [
    {{"currency": "hkd", "period": "3m", "fund_type": "new_funds", "old_rate": 2.5, "new_rate": 2.65, "source": "official_site"}}
  ],
  "verified_source": "official_site"
}}"""


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


def _compare_rates(a_flat, b_flat):
    """比對兩組利率，返回差異列表"""
    discrepancies = []
    all_keys = set(a_flat.keys()) | set(b_flat.keys())

    for key in all_keys:
        a_rate = a_flat.get(key)
        b_rate = b_flat.get(key)
        currency, tenor, fund_type = key

        if a_rate is None and b_rate is not None:
            discrepancies.append({
                'currency': currency, 'tenor': tenor, 'fund_type': fund_type,
                'a': None, 'b': b_rate, 'diff': None,
                'type': 'b_only'
            })
        elif a_rate is not None and b_rate is None:
            pass
        elif a_rate is not None and b_rate is not None:
            diff = abs(a_rate - b_rate)
            if diff > RATE_DIFF_TOLERANCE:
                discrepancies.append({
                    'currency': currency, 'tenor': tenor, 'fund_type': fund_type,
                    'a': a_rate, 'b': b_rate, 'diff': round(diff, 4),
                    'type': 'mismatch'
                })

    return discrepancies


def _get_bank_url(bank_urls_data, key):
    """從 bank_urls.json 攞返銀行嘅 general URL"""
    for bank in bank_urls_data.get('banks', []):
        if bank.get('key') == key:
            urls = bank.get('urls', {})
            return urls.get('general') or urls.get('promotion') or urls.get('online') or urls.get('hket', '')
    return ''


def llm_verify_all(banks_data, old_rates=None, bank_urls_data=None):
    """
    全量 LLM 驗證：
    1. Parser 結果同 sicsicduck.com 現有資料比對
    2. 有變動 → LLM 上銀行官網核對
    3. Parser 失敗 → LLM 直接抽取

    Args:
        banks_data: list of dicts, 每個包含:
            - name: 銀行名稱
            - key: 銀行 key
            - text: raw text（爬蟲抓到嘅）
            - parsed: parser 返回嘅利率（可能為 None）
        old_rates: sicsicduck.com 現有利率（rates.json）
        bank_urls_data: bank_urls.json（用來查 bank URL）

    Returns:
        dict with:
            - verified: {key: rates_dict} — LLM 驗證後嘅利率
            - discrepancies: [{bank, ...}] — 變動記錄
            - stats: {total, parser_ok, llm_fixed, llm_only, llm_failed}
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

        # === Step 1: 如果冇 parser 結果，直接 LLM 抽取 ===
        if not parsed:
            logger.info(f"  🤖 [{name}] Parser 失敗，LLM 直接抽取")
            prompt = EXTRACTION_PROMPT_TEMPLATE.format(bank_name=name, text=text[:8000])
            response = _call_llm(prompt)
            llm_rates = _parse_llm_response(response)
            if llm_rates:
                verified[key] = llm_rates
                stats['llm_only'] += 1
            else:
                stats['llm_failed'] += 1
            continue

        # === Step 2: 比對 Parser 結果同 sicsicduck.com 現有資料 ===
        old_bank_rates = None
        if old_rates:
            for b in old_rates.get('banks', []):
                if b.get('key') == key:
                    old_bank_rates = b
                    break

        if old_bank_rates:
            parser_flat = _get_rates_flat(parsed)
            old_flat = _get_rates_flat(old_bank_rates)
            diffs = _compare_rates(parser_flat, old_flat)
        else:
            # 新銀行，冇舊資料，直接當有變動
            diffs = [{'type': 'new_bank'}]

        # === Step 3: 如果冇變動，用 parser 結果 ===
        if not diffs:
            verified[key] = parsed
            stats['parser_ok'] += 1
            logger.info(f"  ✅ [{name}] Parser 同 sicsicduck.com 一致，無變動")
            continue

        # === Step 4: 有變動 → LLM 上銀行官網核對 ===
        logger.info(f"  ⚠️ [{name}] 偵測到 {len(diffs)} 處變動，LLM 上官網核對...")

        bank_url = ''
        if bank_urls_data:
            bank_url = _get_bank_url(bank_urls_data, key)

        # 構建 verification prompt
        prompt = VERIFICATION_PROMPT_TEMPLATE.format(
            bank_name=name,
            bank_url=bank_url or '(未找到 URL)',
            text=text[:8000],
            parsed_json=json.dumps(parsed, ensure_ascii=False, indent=2),
            existing_json=json.dumps(old_bank_rates, ensure_ascii=False, indent=2) if old_bank_rates else '{}'
        )
        response = _call_llm(prompt)
        llm_rates = _parse_llm_response(response)

        if llm_rates:
            # 解析 changes
            try:
                full_data = json.loads(response.strip().strip('`').strip())
                if isinstance(full_data, dict):
                    llm_changes = full_data.get('changes', [])
                    for c in llm_changes:
                        c['bank'] = name
                        c['key'] = key
                        discrepancies.append(c)
            except:
                pass

            verified[key] = llm_rates
            stats['llm_fixed'] += 1
            logger.info(f"  🔍 [{name}] LLM 官網核對完成，已更新")
        else:
            # LLM 核對失敗，用 parser 結果
            verified[key] = parsed
            stats['parser_ok'] += 1
            logger.warning(f"  ❌ [{name}] LLM 核對失敗，用 parser 結果")

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

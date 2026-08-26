#!/usr/bin/env python3
"""
LLM 輔助利率抽取 — 當 Parser 失敗時嘅 Fallback

策略：
1. 爬蟲抓到 raw text / table 後，先用現有 parser 嘗試
2. 如果 parser 返回空或只覆蓋部分幣種，觸發 LLM fallback
3. LLM 讀 raw text 直接抽利率（唔依賴 HTML 結構）

支援嘅 LLM：
- OpenAI-compatible API（自己嘅 endpoint）
"""
import json
import re
import os
import logging

logger = logging.getLogger(__name__)

# LLM config — 優先用環境變量，fallback 到 yuanyuai endpoint
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://yuanyuaicloud.cn/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-5.2")
LLM_TIMEOUT = 30


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
5. 只輸出 JSON，唔好加解釋

銀行名稱：{bank_name}
文字內容：
---
{text}
---"""


def _call_llm(prompt):
    """呼叫 LLM API 抽取利率"""
    try:
        import httpx
    except ImportError:
        logger.warning("LLM fallback: httpx 未安裝，嘗試 pip install httpx")
        try:
            os.system("pip install httpx -q")
            import httpx
        except:
            return None

    if not LLM_API_KEY:
        logger.warning("LLM fallback: 未設定 LLM_API_KEY，請設定環境變量 LLM_API_KEY")
        return None

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你係一個精確嘅數據提取助手。只輸出 JSON，唔好加任何解釋。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0,
        "max_tokens": 2000
    }

    try:
        with httpx.Client(timeout=LLM_TIMEOUT) as client:
            resp = client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()
    except Exception as e:
        logger.error(f"LLM fallback API error: {e}")
        return None


def _parse_llm_response(response_text):
    """解析 LLM 返回嘅 JSON"""
    if not response_text:
        return None

    # 清理 markdown code block
    text = response_text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 嘗試搵 JSON 嘅部分
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
        if currency in data and isinstance(data[currency], dict):
            curr_result = {}
            for tenor, rates in data[currency].items():
                if not isinstance(rates, dict):
                    continue

                # 處理簡寫格式（直接有 rate）
                if 'rate' in rates:
                    curr_result[tenor] = {
                        'new_funds': {'rate': rates['rate'], 'min_deposit': 10000, 'note': '新資金定期存款', 'source': 'llm'},
                        'existing_funds': None
                    }
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


def llm_extract_rates(raw_text, bank_name="", existing_rates=None):
    """
    用 LLM 從 raw text 抽取利率。

    Args:
        raw_text: 爬蟲抓到嘅文字
        bank_name: 銀行名稱（用於 prompt）
        existing_rates: 現有 parser 已抽到嘅利率（用於判斷覆蓋率）

    Returns:
        dict: 利率數據，格式同 parser 一樣；或者 None 如果 LLM 都失敗
    """
    if not raw_text or len(raw_text) < 50:
        logger.info("LLM fallback: text 太短，跳過")
        return None

    text = raw_text[:8000]

    logger.info(f"LLM fallback: 正在用 LLM 抽取 {bank_name} 嘅利率...")
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(bank_name=bank_name, text=text)
    response = _call_llm(prompt)

    if not response:
        logger.warning(f"LLM fallback: {bank_name} — LLM 無回應")
        return None

    parsed = _parse_llm_response(response)
    if parsed:
        currencies_found = list(parsed.keys())
        logger.info(f"LLM fallback: {bank_name} — 成功抽取 {currencies_found}")

        if existing_rates:
            for c in currencies_found:
                if c not in existing_rates:
                    logger.info(f"  → LLM 補充咗 {c.upper()} 利率")

        return parsed
    else:
        logger.warning(f"LLM fallback: {bank_name} — LLM 返回嘅 JSON 解析失敗")
        return None


def should_use_llm(existing_rates, expected_currencies=None):
    """
    判斷需唔需要用 LLM fallback。

    Args:
        existing_rates: 現有 parser 返回嘅利率
        expected_currencies: 預期嘅幣種（例如 ['hkd', 'usd', 'cny']）

    Returns:
        bool: True = 需要 LLM fallback
    """
    if expected_currencies is None:
        expected_currencies = ['hkd', 'usd', 'cny']

    if not existing_rates:
        return True

    missing = [c for c in expected_currencies if c not in existing_rates or not existing_rates[c]]
    if len(missing) >= 2:
        return True

    for c in expected_currencies:
        if c in existing_rates:
            for tenor, data in existing_rates[c].items():
                if isinstance(data, dict):
                    for fund_type in ['new_funds', 'existing_funds']:
                        if fund_type in data and isinstance(data[fund_type], dict):
                            if data[fund_type].get('rate') is None:
                                return True

    return False

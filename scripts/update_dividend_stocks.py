#!/usr/bin/env python3
"""
香港藍籌股息率數據更新腳本
使用 etnet.com.hk 獲取上一財政年度派息 + yfinance 獲取股價

息率計算方法：
- 從 etnet 派息紀錄提取「上一個已完成財政年度」嘅總派息（港元）
- 從 yfinance 獲取現價
- 息率 = 上一財政年度總派息 / 現價 × 100%

etnet URL format: https://www.etnet.com.hk/www/tc/stocks/realtime/quote_dividend.php?code={code}
code = ticker number without .HK (e.g. 00005, 0941)

每日 8:30 由 cron 執行
"""
import yfinance as yf
import json, os, re, logging, subprocess, time
from datetime import datetime, timezone, timedelta

HKT = timezone(timedelta(hours=8))
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'dividend_stocks.json')

hsi_stocks = {
    "0005.HK":"滙豐控股","0002.HK":"中電控股","0003.HK":"香港中華煤氣",
    "0006.HK":"電能實業","0011.HK":"恒生銀行","0012.HK":"恒基兆業地產",
    "0016.HK":"新鴻基地產","0017.HK":"新世界發展","0027.HK":"銀河娛樂",
    "0066.HK":"港鐵公司","0101.HK":"恒隆地產","0175.HK":"吉利汽車",
    "0267.HK":"中信股份","0288.HK":"萬洲國際","0291.HK":"華潤啤酒",
    "0388.HK":"香港交易所","0669.HK":"創科實業","0700.HK":"騰訊控股",
    "0762.HK":"中國聯通","0823.HK":"領展房產基金","0857.HK":"中國石油",
    "0868.HK":"信義玻璃","0939.HK":"建設銀行","0941.HK":"中國移動",
    "1038.HK":"長江基建","1044.HK":"恒安國際","1093.HK":"石藥集團",
    "1109.HK":"華潤置地","1113.HK":"長實集團","1177.HK":"中國生物製藥",
    "1211.HK":"比亞迪","1288.HK":"農業銀行","1299.HK":"友邦保險",
    "1398.HK":"工商銀行","1810.HK":"小米集團","1876.HK":"百威亞太",
    "1928.HK":"金沙中國","1997.HK":"九龍倉置業","2018.HK":"瑞聲科技",
    "2313.HK":"申洲國際","2318.HK":"中國平安","2382.HK":"舜宇光學",
    "2388.HK":"中銀香港","2628.HK":"中國人壽","3328.HK":"交通銀行",
    "3690.HK":"美團","3968.HK":"招商銀行","3988.HK":"中國銀行",
    "6862.HK":"海底撈","9618.HK":"京東集團","9633.HK":"農夫山泉",
    "9961.HK":"攜程集團","9988.HK":"阿里巴巴","9999.HK":"網易",
}

sectors = {
    "0005.HK":"銀行","0002.HK":"公用事業","0003.HK":"公用事業",
    "0006.HK":"公用事業","0011.HK":"銀行","0012.HK":"地產",
    "0016.HK":"地產","0017.HK":"地產","0027.HK":"博彩",
    "0066.HK":"運輸","0101.HK":"地產","0175.HK":"汽車",
    "0267.HK":"綜合企業","0288.HK":"食品","0291.HK":"食品",
    "0388.HK":"金融","0669.HK":"工業","0700.HK":"科技",
    "0762.HK":"電訊","0823.HK":"房地產信託","0857.HK":"能源",
    "0868.HK":"工業","0939.HK":"建設銀行","0941.HK":"電訊",
    "1038.HK":"公用事業","1044.HK":"消費品","1093.HK":"醫藥",
    "1109.HK":"地產","1113.HK":"地產","1177.HK":"醫藥",
    "1211.HK":"汽車","1288.HK":"銀行","1299.HK":"保險",
    "1398.HK":"銀行","1810.HK":"科技","1876.HK":"食品",
    "1928.HK":"博彩","1997.HK":"地產","2018.HK":"科技",
    "2313.HK":"紡織","2318.HK":"保險","2382.HK":"科技",
    "2388.HK":"銀行","2628.HK":"保險","3328.HK":"銀行",
    "3690.HK":"科技","3968.HK":"銀行","3988.HK":"銀行",
    "6862.HK":"餐飲","9618.HK":"科技","9633.HK":"食品",
    "9961.HK":"科技","9988.HK":"科技","9999.HK":"科技",
}

ETNET_URL = 'https://www.etnet.com.hk/www/tc/stocks/realtime/quote_dividend.php?code={code}'
RMB_HKD_RATE = 1.08  # 人民幣兌港元 (approx, etnet 用接近即時匯率轉換)


def _run_browser(cmd, timeout=20):
    """Run agent-browser command, return cleaned output or None."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            out = re.sub(r'\x1b\[[0-9;]*m', '', r.stdout).strip()
            return out if out else None
        return None
    except Exception as e:
        logger.warning(f"agent-browser error: {e}")
        return None


def get_last_fy_dividend_etnet(stock_code):
    """
    Scrape etnet dividend page to get total dividends for the last completed fiscal year.
    
    Args:
        stock_code: e.g. "00005", "0941" (without .HK)
    
    Returns:
        (total_hkd_div, fy_label) or (None, None)
        fy_label e.g. "2025/12" meaning FY2025
    """
    try:
        url = ETNET_URL.format(code=stock_code)
        
        # Open page
        _run_browser('agent-browser close', timeout=5)
        time.sleep(1)
        result = _run_browser(f'agent-browser open "{url}" --timeout 30000', timeout=35)
        if not result:
            return None, None
        time.sleep(5)
        
        # Get page text
        raw = _run_browser('agent-browser eval "document.body.innerText.substring(0, 15000)"', timeout=10)
        if not raw:
            return None, None
        
        try:
            text = json.loads(raw)
        except:
            text = raw.strip('"')
        
        if not text or '派息記錄' not in text:
            return None, None
        
        # Extract dividend rows: each row has 財政年度 and 港元 amount
        # Format: "22/04/2026\t2026/12\t第一次中期息美元 0.1\t14/05/2026\t..."
        # Or: "07/08/2025\t2025/12\t中期息人民幣 2.508 或港元 2.75\t..."
        
        # Find all fiscal years and their HKD dividends
        fy_divs = {}  # fy_label -> [hkd_amounts]
        
        lines = text.split('\n')
        for line in lines:
            # Match fiscal year: YYYY/MM (e.g. 2025/12)
            fy_match = re.search(r'(\d{4}/\d{2})\t', line)
            if not fy_match:
                continue
            
            fy = fy_match.group(1)
            
            # Extract HKD amount
            # Pattern: 港元 X.XXX (or 港元X.XXX)
            # Could be: "港元 3.522942" or "港元 2.75" or "港元 2.52"
            hkd_match = re.search(r'港元\s*(\d+\.?\d*)', line)
            if hkd_match:
                amount = float(hkd_match.group(1))
                if fy not in fy_divs:
                    fy_divs[fy] = []
                fy_divs[fy].append(amount)
            else:
                # Fallback: if no HKD amount, try RMB/CNY and convert
                # Pattern: "人民幣 0.1169" or "人民幣0.1169"
                rmb_match = re.search(r'人民幣\s*(\d+\.?\d*)', line)
                if rmb_match:
                    rmb_amount = float(rmb_match.group(1))
                    # Convert RMB to HKD (approx 1.07-1.08)
                    hkd_amount = rmb_amount * RMB_HKD_RATE
                    if fy not in fy_divs:
                        fy_divs[fy] = []
                    fy_divs[fy].append(hkd_amount)
        
        if not fy_divs:
            return None, None
        
        # Determine last completed FY
        # FY format "2025/12" means fiscal year ending Dec 2025
        # Now is 2026-06, so last completed FY is 2025/12
        # Sort FY labels and find the most recent completed one
        sorted_fys = sorted(fy_divs.keys(), reverse=True)
        
        # Parse FY: "2025/12" -> year=2025, month=12
        now = datetime.now(HKT)
        best_fy = None
        for fy in sorted_fys:
            parts = fy.split('/')
            if len(parts) != 2:
                continue
            fy_year, fy_month = int(parts[0]), int(parts[1])
            
            # A FY is "completed" if its end date is in the past
            # FY 2025/12 ends Dec 2025 (which is in the past for June 2026)
            fy_end = datetime(fy_year, fy_month, 1, tzinfo=HKT) + timedelta(days=31)
            if fy_end < now:
                best_fy = fy
                break
        
        if best_fy is None:
            # Fallback: just use the second most recent (first might be current FY)
            if len(sorted_fys) >= 2:
                best_fy = sorted_fys[1]
            else:
                best_fy = sorted_fys[0]
        
        total = round(sum(fy_divs[best_fy]), 4)
        if total <= 0:
            return None, None
        
        return total, best_fy
    
    except Exception as e:
        logger.warning(f"etnet scrape error for {stock_code}: {e}")
        return None, None


def get_price_yfinance(ticker):
    """Get current price from yfinance."""
    try:
        s = yf.Ticker(ticker)
        info = s.info
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        return round(float(price), 2) if price else None
    except:
        return None


def main():
    logger.info("Updating dividend stocks data (etnet FY method)...")
    results = []
    failed = []
    
    for ticker, name in sorted(hsi_stocks.items()):
        code = ticker.replace('.HK', '')
        
        try:
            # Get dividend from etnet
            div, fy_label = get_last_fy_dividend_etnet(code)
            price = get_price_yfinance(ticker)
            
            if div and div > 0 and price:
                yld = (div / price) * 100
                results.append({
                    'ticker': code,
                    'name': name,
                    'price': price,
                    'dividend': div,
                    'yield': round(yld, 2),
                    'fy': fy_label,
                    'sector': sectors.get(ticker, '其他'),
                    'div_source': 'etnet',
                })
                logger.info(f"  ✓ {code} {name}: FY{fy_label} div={div} HKD, price={price}, yield={yld:.2f}%")
            elif price and (div is None or div == 0):
                logger.warning(f"  ⚠ {code} {name}: no dividend data from etnet (price={price})")
                failed.append(name)
            else:
                logger.warning(f"  ⚠ {code} {name}: no price (div={div})")
                failed.append(name)
        
        except Exception as e:
            logger.warning(f"  ✗ {code} {name}: {e}")
            failed.append(name)
    
    # Close browser
    _run_browser('agent-browser close', timeout=5)
    
    results.sort(key=lambda x: x['yield'], reverse=True)
    
    data = {
        'last_updated': datetime.now(HKT).strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        'source': 'etnet (派息) + Yahoo Finance (股價)',
        'method': '上一財政年度總派息 / 現價',
        'disclaimer': '息率 = 上一財政年度總派息（港元）/ 現價 × 100%。派息數據來自經濟通 etnet，股價來自 Yahoo Finance。數據僅供參考，不構成投資建議。',
        'stocks': results,
    }
    
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Updated {len(results)} stocks, {len(failed)} skipped")
    if failed:
        logger.info(f"Skipped: {', '.join(failed)}")


if __name__ == '__main__':
    main()

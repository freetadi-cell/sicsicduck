#!/usr/bin/env python3
import yfinance as yf
import json, os, sys, logging
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

def get_last_fy_dividend(stock):
    """
    Get total dividends from the last completed fiscal year.
    Most HK stocks have FY ending Dec 31, but some (banks, insurers) differ.
    Uses yfinance dividends history to find the last FY and sum all dividends in it.
    """
    try:
        divs = stock.dividends
        if divs is None or divs.empty:
            return None
        # Get fiscal year end from info
        info = stock.info
        fy_end_month = info.get('lastFiscalYearEnd')
        
        # Find dividend dates and group by fiscal year
        # Most HK stocks: FY ends Dec 31. We determine the last completed FY
        # by looking at the latest dividend and working backwards.
        last_div_date = divs.index[-1]
        now = datetime.now()
        
        # Try to determine FY end month
        # Common HK FY end months: 12 (Dec) for most, 3 (Mar) for some Japanese/banks
        fy_month = 12  # Default for HK stocks
        
        # Calculate last completed fiscal year end date
        if now.month > fy_month:
            last_fy_end = datetime(now.year, fy_month, 31)
        else:
            last_fy_end = datetime(now.year - 1, fy_month, 31)
        
        # Previous FY end
        prev_fy_end = datetime(last_fy_end.year - 1, fy_month, 31)
        
        # Sum dividends in (prev_fy_end, last_fy_end]
        mask = (divs.index > prev_fy_end.strftime('%Y-%m-%d')) & (divs.index <= last_fy_end.strftime('%Y-%m-%d'))
        fy_divs = divs[mask]
        
        if fy_divs.empty:
            return None
        
        return round(float(fy_divs.sum()), 4)
    except Exception:
        return None


def main():
    logger.info("Updating dividend stocks data...")
    results = []
    for ticker, name in hsi_stocks.items():
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            dr = get_last_fy_dividend(stock)
            if price and dr and dr > 0:
                yld = (dr / price) * 100
                results.append({
                    'ticker': ticker.replace('.HK',''), 'name': name,
                    'price': round(price, 2), 'dividend': round(dr, 4),
                    'yield': round(yld, 2), 'sector': sectors.get(ticker, '其他'),
                })
        except Exception as e:
            logger.warning(f"{ticker} {name}: {e}")

    results.sort(key=lambda x: x['yield'], reverse=True)
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    data = {
        'last_updated': datetime.now(HKT).strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        'source': 'Yahoo Finance (yfinance)',
        'disclaimer': '息率 = 上一財政年度總派息（年終+中期+季息）/ 上一日收市價 × 100%。數據僅供參考，不構成投資建議。',
        'stocks': results,
    }
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ Updated {len(results)} stocks")

if __name__ == '__main__':
    main()

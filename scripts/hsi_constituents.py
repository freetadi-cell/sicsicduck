#!/usr/bin/env python3
"""
恒指成份股分析框架 + Yahoo Finance 示范分析
基於大戶動能策略模型
"""
import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 1. 恒指成份股列表（2026年8月）
# ============================================================
HSI_CONSTITUENTS = {
    # 金融
    "0005.HK": "汇丰控股",
    "0011.HK": "恒生银行",
    "0388.HK": "港交所",
    "1398.HK": "工商银行",
    "0939.HK": "建设银行",
    "3988.HK": "中国银行",
    "3968.HK": "招商银行",
    "1988.HK": "民生银行",
    "0023.HK": "东亚银行",
    "2388.HK": "中银香港",
    "1288.HK": "农业银行",
    "6818.HK": "中国光大银行",
    "6030.HK": "中信证券",
    "6066.HK": "中信建投证券",
    "6886.HK": "华泰证券",
    "0386.HK": "中国石化",
    "1211.HK": "比亚迪股份",
    "0002.HK": "中电控股",
    "0003.HK": "中华煤气",
    "0006.HK": "电能实业",
    "0012.HK": "恒基地产",
    "0016.HK": "新鸿基地产",
    "0017.HK": "新世界发展",
    "0066.HK": "港铁公司",
    "0101.HK": "恒隆集团",
    "0688.HK": "中国海外发展",
    "1109.HK": "华润置地",
    "0823.HK": "领展房产基金",
    "0027.HK": "银河娱乐",
    "1928.HK": "金沙中国",
    "0066.HK": "港铁公司",
    "0700.HK": "腾讯控股",
    "9988.HK": "阿里巴巴-W",
    "9618.HK": "京东集团-SW",
    "3690.HK": "美团-W",
    "9888.HK": "百度集团-SW",
    "1024.HK": "快手-W",
    "9999.HK": "网易-S",
    "0241.HK": "阿里健康",
    "9961.HK": "携程集团-S",
    "6060.HK": "众安在线",
    "0941.HK": "中国移动",
    "0728.HK": "中国电信",
    "0992.HK": "联想集团",
    "0267.HK": "中信股份",
    "0019.HK": "太古A",
    "0023.HK": "东亚银行",
    "2313.HK": "申洲国际",
    "2318.HK": "中国平安",
    "2628.HK": "中国人寿",
    "0386.HK": "中国石化",
    "0883.HK": "中国海洋石油",
    "2899.HK": "紫金矿业",
    "0857.HK": "中国石油股份",
    "0288.HK": "万洲国际",
    "1093.HK": "石药集团",
    "2269.HK": "药明生物",
    "0001.HK": "长和",
    "0002.HK": "中电控股",
    "0003.HK": "中华煤气",
    "0005.HK": "汇丰控股",
    "0006.HK": "电能实业",
    "0011.HK": "恒生银行",
    "0012.HK": "恒基地产",
    "0016.HK": "新鸿基地产",
    "0017.HK": "新世界发展",
    "0019.HK": "太古A",
    "0027.HK": "银河娱乐",
    "0066.HK": "港铁公司",
    "0101.HK": "恒隆集团",
    "0241.HK": "阿里健康",
    "0267.HK": "中信股份",
    "0288.HK": "万洲国际",
    "0386.HK": "中国石化",
    "0388.HK": "港交所",
    "0688.HK": "中国海外发展",
    "0700.HK": "腾讯控股",
    "0728.HK": "中国电信",
    "0823.HK": "领展房产基金",
    "0857.HK": "中国石油股份",
    "0883.HK": "中国海洋石油",
    "0939.HK": "建设银行",
    "0941.HK": "中国移动",
    "0992.HK": "联想集团",
    "1024.HK": "快手-W",
    "1093.HK": "石药集团",
    "1109.HK": "华润置地",
    "1211.HK": "比亚迪股份",
    "1288.HK": "农业银行",
    "1398.HK": "工商银行",
    "1928.HK": "金沙中国",
    "1988.HK": "民生银行",
    "2269.HK": "药明生物",
    "2313.HK": "申洲国际",
    "2318.HK": "中国平安",
    "2388.HK": "中银香港",
    "2628.HK": "中国人寿",
    "2899.HK": "紫金矿业",
    "3690.HK": "美团-W",
    "3968.HK": "招商银行",
    "3988.HK": "中国银行",
    "6030.HK": "中信证券",
    "6060.HK": "众安在线",
    "6066.HK": "中信建投证券",
    "6818.HK": "中国光大银行",
    "6886.HK": "华泰证券",
    "9618.HK": "京东集团-SW",
    "9888.HK": "百度集团-SW",
    "9961.HK": "携程集团-S",
    "9988.HK": "阿里巴巴-W",
    "9999.HK": "网易-S",
    "9999.HK": "网易-S",
}

# 去重
HSI_CONSTITUENTS = dict(list(dict.fromkeys(HSI_CONSTITUENTS.items())))

# ============================================================
# 2. 技術指標計算
# ============================================================
def calculate_technical_indicators(df, period=20):
    """計算技術指標"""
    # 移動平均線
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # 成交量均線
    df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
    
    # OBV (On-Balance Volume)
    df['OBV'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
    
    # MFI (Money Flow Index) - 14日
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    money_flow = typical_price * df['Volume']
    positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(14).sum()
    negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(14).sum()
    mfi_ratio = positive_flow / negative_flow
    df['MFI'] = 100 - (100 / (1 + mfi_ratio))
    
    # CMF (Chaikin Money Flow) - 20日
    clv = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'])
    clv = clv.fillna(0)
    df['CMF'] = (clv * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
    
    # AD Oscillator
    ad = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low']) * df['Volume']
    df['AD'] = ad.cumsum()
    df['AD_OSC'] = df['AD'].rolling(3).mean() - df['AD'].rolling(10).mean()
    
    # RSI (14日)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df

# ============================================================
# 3. 大戶動能評分模型
# ============================================================
def score_smart_money(stock_data, hsi_data=None):
    """計算個股大戶動能評分"""
    scores = {}
    
    # A. 趨勢結構 (30分)
    trend_score = 0
    if stock_data['Close'].iloc[-1] > stock_data['MA20'].iloc[-1]:
        trend_score += 10
    if stock_data['MA20'].iloc[-1] > stock_data['MA50'].iloc[-1]:
        trend_score += 10
    if stock_data['MA50'].iloc[-1] > stock_data['MA200'].iloc[-1]:
        trend_score += 10
    scores['趨勢結構'] = trend_score
    
    # B. 量價動能 (25分)
    vol_score = 0
    vol_ratio = stock_data['Volume'].iloc[-1] / stock_data['Vol_MA20'].iloc[-1] if stock_data['Vol_MA20'].iloc[-1] > 0 else 0
    if vol_ratio > 1.2:
        vol_score += 15
    elif vol_ratio > 1.0:
        vol_score += 10
    
    # 價升量增
    if stock_data['Close'].iloc[-1] > stock_data['Close'].iloc[-2] and vol_ratio > 1.0:
        vol_score += 10
    scores['量價動能'] = min(vol_score, 25)
    
    # C. 大戶行為 (30分)
    smart_score = 0
    # MFI > 50 = 買方主導
    if stock_data['MFI'].iloc[-1] > 50:
        smart_score += 10
    if stock_data['MFI'].iloc[-1] > 60:
        smart_score += 5
    
    # CMF > 0 = 資金流入
    if stock_data['CMF'].iloc[-1] > 0:
        smart_score += 10
    if stock_data['CMF'].iloc[-1] > 0.1:
        smart_score += 5
    
    scores['大戶行為'] = min(smart_score, 30)
    
    # D. 流動性 (15分)
    liq_score = 0
    avg_vol = stock_data['Volume'].mean()
    if avg_vol > 10_000_000:  # 日均成交量 > 1000萬股
        liq_score += 15
    elif avg_vol > 5_000_000:
        liq_score += 10
    elif avg_vol > 1_000_000:
        liq_score += 5
    scores['流動性'] = liq_score
    
    # E. 動能持續性 (加分項)
    # 近5日RSI趨勢
    rsi_5d = stock_data['RSI'].iloc[-5:].mean()
    if 50 < rsi_5d < 70:
        scores['動能持續性'] = 5
    
    total = sum(scores.values())
    return total, scores

# ============================================================
# 4. 主分析函数
# ============================================================
def analyze_hsi_constituents():
    """分析所有恒指成份股"""
    results = []
    total = len(HSI_CONSTITUENTS)
    
    print(f"開始分析 {total} 隻恒指成份股...")
    print("=" * 60)
    
    for i, (ticker, name) in enumerate(HSI_CONSTITUENTS.items(), 1):
        try:
            print(f"[{i}/{total}] 分析 {name} ({ticker})...")
            
            # 獲取數據（250日用於計算MA200）
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            
            if hist.empty or len(hist) < 200:
                print(f"  ⚠️  {name} 數據不足，跳過")
                continue
            
            # 計算技術指標
            hist = calculate_technical_indicators(hist)
            
            # 計算評分
            total_score, scores = score_smart_money(hist)
            
            # 獲取基本面
            info = stock.info
            market_cap = info.get('marketCap', 0)
            
            # 判斷建議
            if total_score >= 80:
                advice = "🟢 強勢 - 可考慮買入"
            elif total_score >= 60:
                advice = "🟡 中性 - 觀察"
            elif total_score >= 40:
                advice = "🟠 弱勢 - 觀望"
            else:
                advice = "🔴 弱勢 - 回避"
            
            results.append({
                '股票代碼': ticker,
                '股票名稱': name,
                '收盤價': round(hist['Close'].iloc[-1], 2),
                '20MA': round(hist['MA20'].iloc[-1], 2),
                '50MA': round(hist['MA50'].iloc[-1], 2),
                '200MA': round(hist['MA200'].iloc[-1], 2),
                'RSI': round(hist['RSI'].iloc[-1], 1),
                'MFI': round(hist['MFI'].iloc[-1], 1),
                'CMF': round(hist['CMF'].iloc[-1], 3),
                '成交量比': round(hist['Volume'].iloc[-1] / hist['Vol_MA20'].iloc[-1], 2) if hist['Vol_MA20'].iloc[-1] > 0 else 0,
                '市值(億港元)': round(market_cap / 1e8, 1) if market_cap else 'N/A',
                '總分': total_score,
                '建議': advice,
                '評分明細': scores
            })
            
        except Exception as e:
            print(f"  ❌ {name} 分析失敗: {e}")
            continue
    
    return results

# ============================================================
# 5. 生成報告
# ============================================================
def generate_report(results):
    """生成分析報告"""
    # 按總分排序
    results_sorted = sorted(results, key=lambda x: x['總分'], reverse=True)
    
    report = []
    report.append("# 恒指成份股大戶動能分析報告")
    report.append(f"\n分析日期：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"數據來源：Yahoo Finance")
    report.append(f"分析模型：大戶動能策略")
    report.append(f"\n---")
    
    # 總覽
    strong = [r for r in results_sorted if r['總分'] >= 80]
    neutral = [r for r in results_sorted if 60 <= r['總分'] < 80]
    weak = [r for r in results_sorted if r['總分'] < 60]
    
    report.append(f"\n## 📊 總覽")
    report.append(f"- 🟢 強勢（≥80分）：{len(strong)} 隻")
    report.append(f"- 🟡 中性（60-79分）：{len(neutral)} 隻")
    report.append(f"- 🔴 弱勢（<60分）：{len(weak)} 隻")
    
    # 前10名
    report.append(f"\n## 🏆 前10名（大戶動能最強）")
    report.append("| 排名 | 股票 | 收盤價 | 20MA | RSI | MFI | CMF | 成交量比 | 總分 | 建議 |")
    report.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---|")
    
    for i, r in enumerate(results_sorted[:10], 1):
        report.append(f"| {i} | {r['股票名稱']} ({r['股票代碼']}) | {r['收盤價']} | {r['20MA']} | {r['RSI']} | {r['MFI']} | {r['CMF']} | {r['成交量比']} | {r['總分']} | {r['建議']} |")
    
    # 後10名
    report.append(f"\n## ⚠️ 後10名（最弱勢）")
    report.append("| 排名 | 股票 | 收盤價 | 20MA | RSI | MFI | CMF | 成交量比 | 總分 | 建議 |")
    report.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---|")
    
    for i, r in enumerate(results_sorted[-10:], 1):
        report.append(f"| {i} | {r['股票名稱']} ({r['股票代碼']}) | {r['收盤價']} | {r['20MA']} | {r['RSI']} | {r['MFI']} | {r['CMF']} | {r['成交量比']} | {r['總分']} | {r['建議']} |")
    
    # 評分細則說明
    report.append(f"\n## 📈 評分細則（滿分100）")
    report.append("| 指標 | 權重 | 滿分條件 |")
    report.append("|---|---:|---|")
    report.append("| 趨勢結構 | 30分 | 收盤>20MA>50MA>200MA |")
    report.append("| 量價動能 | 25分 | 成交量比>1.2 + 價升量增 |")
    report.append("| 大戶行為 | 30分 | MFI>60 + CMF>0.1 |")
    report.append("| 流動性 | 15分 | 日均成交量>1000萬股 |")
    
    # 建議
    report.append(f"\n## 💡 操作建議")
    report.append("1. 強勢股（≥80分）：可考慮分批買入，止賺+15-30%，止蝕-7%")
    report.append("2. 中性股（60-79分）：觀察為主，等待突破確認")
    report.append("3. 弱勢股（<60分）：暫時迴避，等待轉強信號")
    report.append("4. 注意：本分析基於技術指標，請結合基本面及市場環境判斷")
    
    return "\n".join(report)

# ============================================================
# 6. 主程式
# ============================================================
if __name__ == "__main__":
    print("恒指成份股大戶動能分析")
    print("=" * 60)
    
    # 分析
    results = analyze_hsi_constituents()
    
    if results:
        # 生成報告
        report = generate_report(results)
        
        # 保存報告
        report_path = "/home/freet/.openclaw/workspace/sicsicduck/research/hsi_analysis_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        
        # 保存JSON數據
        data_path = "/home/freet/.openclaw/workspace/sicsicduck/data/hsi_analysis.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print("\n" + "=" * 60)
        print("分析完成！")
        print(f"報告已保存至：{report_path}")
        print(f"數據已保存至：{data_path}")
        print(f"共分析 {len(results)} 隻股票")
        
        # 簡報
        print("\n📊 簡報：")
        strong = [r for r in results if r['總分'] >= 80]
        neutral = [r for r in results if 60 <= r['總分'] < 80]
        weak = [r for r in results if r['總分'] < 60]
        print(f"  🟢 強勢：{len(strong)} 隻")
        print(f"  🟡 中性：{len(neutral)} 隻")
        print(f"  🔴 弱勢：{len(weak)} 隻")
    else:
        print("分析失敗，無法獲取數據")

#!/usr/bin/env python3
"""
恒指成份股大戶動能分析
基於 Yahoo Finance 數據，應用我們設計嘅大戶動能策略模型
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 恒指成份股列表（2026年8月，約50只）
# ============================================================
HSI_CONSTITUENTS = [
    # 金融
    ("0005.HK", "汇丰控股"),
    ("0011.HK", "恒生银行"),
    ("0388.HK", "港交所"),
    ("1398.HK", "工商银行"),
    ("0939.HK", "建设银行"),
    ("3988.HK", "中国银行"),
    ("3968.HK", "招商银行"),
    ("1288.HK", "农业银行"),
    ("2388.HK", "中银香港"),
    ("6818.HK", "中国光大银行"),
    ("6030.HK", "中信证券"),
    ("6066.HK", "中信建投证券"),
    ("6886.HK", "华泰证券"),
    ("2318.HK", "中国平安"),
    ("2628.HK", "中国人寿"),
    # 地产/公用
    ("0002.HK", "中电控股"),
    ("0003.HK", "中华煤气"),
    ("0006.HK", "电能实业"),
    ("0012.HK", "恒基地产"),
    ("0016.HK", "新鸿基地产"),
    ("0017.HK", "新世界发展"),
    ("0066.HK", "港铁公司"),
    ("0101.HK", "恒隆集团"),
    ("0688.HK", "中国海外发展"),
    ("1109.HK", "华润置地"),
    ("0823.HK", "领展房产基金"),
    # 科技
    ("0700.HK", "腾讯控股"),
    ("9988.HK", "阿里巴巴"),
    ("9618.HK", "京东集团"),
    ("3690.HK", "美团"),
    ("9888.HK", "百度集团"),
    ("1024.HK", "快手"),
    ("9999.HK", "网易"),
    ("0241.HK", "阿里健康"),
    ("9961.HK", "携程集团"),
    # 消费/博彩
    ("0027.HK", "银河娱乐"),
    ("1928.HK", "金沙中国"),
    ("0288.HK", "万洲国际"),
    # 电讯
    ("0941.HK", "中国移动"),
    ("0728.HK", "中国电信"),
    # 综合/工业
    ("0267.HK", "中信股份"),
    ("0019.HK", "太古A"),
    ("0992.HK", "联想集团"),
    ("2313.HK", "申洲国际"),
    # 能源/资源
    ("0386.HK", "中国石化"),
    ("0857.HK", "中国石油股份"),
    ("0883.HK", "中国海洋石油"),
    ("2899.HK", "紫金矿业"),
    # 医药
    ("1093.HK", "石药集团"),
    ("2269.HK", "药明生物"),
    ("6060.HK", "众安在线"),
    # 综合企业
    ("0001.HK", "长和"),
    ("1211.HK", "比亚迪股份"),
    ("1988.HK", "民生银行"),
    ("0023.HK", "东亚银行"),
]

# 去重
seen = set()
HSI_LIST = []
for code, name in HSI_CONSTITUENTS:
    if code not in seen:
        seen.add(code)
        HSI_LIST.append((code, name))

print(f"共 {len(HSI_LIST)} 只恒指成份股")

# ============================================================
# 技術指標計算
# ============================================================
def calc_indicators(df):
    """計算所有技術指標"""
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']
    
    # 移動平均線
    df['MA5'] = close.rolling(5).mean()
    df['MA10'] = close.rolling(10).mean()
    df['MA20'] = close.rolling(20).mean()
    df['MA50'] = close.rolling(50).mean()
    df['MA200'] = close.rolling(200).mean()
    
    # 成交量均線
    df['Vol_MA5'] = volume.rolling(5).mean()
    df['Vol_MA20'] = volume.rolling(20).mean()
    
    # RSI (14日)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MFI (Money Flow Index, 14日)
    typical = (high + low + close) / 3
    mf = typical * volume
    pos_mf = mf.where(typical > typical.shift(1), 0).rolling(14).sum()
    neg_mf = mf.where(typical < typical.shift(1), 0).rolling(14).sum()
    df['MFI'] = 100 - (100 / (1 + pos_mf / neg_mf))
    
    # CMF (Chaikin Money Flow, 20日)
    clv = ((close - low) - (high - close)) / (high - low)
    clv = clv.fillna(0)
    df['CMF'] = (clv * volume).rolling(20).sum() / volume.rolling(20).sum()
    
    # OBV
    df['OBV'] = (np.sign(close.diff()) * volume).fillna(0).cumsum()
    
    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # 波動率 (20日)
    df['Volatility'] = close.pct_change().rolling(20).std() * np.sqrt(252)
    
    return df

# ============================================================
# 大戶動能評分
# ============================================================
def score_stock(df):
    """計算大戶動能評分（滿分100）"""
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    score = 0
    details = {}
    
    # 1. 趨勢結構 (30分)
    trend = 0
    if latest['Close'] > latest['MA5']:
        trend += 5
    if latest['Close'] > latest['MA10']:
        trend += 5
    if latest['Close'] > latest['MA20']:
        trend += 5
    if latest['MA20'] > latest['MA50']:
        trend += 8
    if latest['MA50'] > latest['MA200']:
        trend += 7
    details['趨勢結構'] = trend
    score += trend
    
    # 2. 量價動能 (25分)
    vol_score = 0
    vol_ratio = latest['Volume'] / latest['Vol_MA20'] if latest['Vol_MA20'] > 0 else 0
    
    if vol_ratio > 1.5:
        vol_score += 15
    elif vol_ratio > 1.2:
        vol_score += 12
    elif vol_ratio > 1.0:
        vol_score += 8
    
    # 價升量增
    price_up = latest['Close'] > prev['Close']
    vol_up = latest['Volume'] > prev['Volume']
    if price_up and vol_up and vol_ratio > 1.0:
        vol_score += 10
    details['量價動能'] = min(vol_score, 25)
    score += min(vol_score, 25)
    
    # 3. 大戶行為 (30分)
    smart = 0
    # MFI > 50 = 買方主導
    if latest['MFI'] > 50:
        smart += 10
    if latest['MFI'] > 60:
        smart += 8
    if latest['MFI'] > 70:
        smart += 7
    
    # CMF > 0 = 資金流入
    if latest['CMF'] > 0:
        smart += 5
    if latest['CMF'] > 0.1:
        smart += 5
    if latest['CMF'] > 0.2:
        smart += 5
    details['大戶行為'] = min(smart, 30)
    score += min(smart, 30)
    
    # 4. 流動性 (15分)
    liq = 0
    avg_vol = df['Volume'].tail(20).mean()
    if avg_vol > 50_000_000:
        liq = 15
    elif avg_vol > 20_000_000:
        liq = 12
    elif avg_vol > 10_000_000:
        liq = 9
    elif avg_vol > 5_000_000:
        liq = 6
    elif avg_vol > 1_000_000:
        liq = 3
    details['流動性'] = liq
    score += liq
    
    return score, details

# ============================================================
# 建議生成
# ============================================================
def get_advice(score):
    """根據評分生成建議"""
    if score >= 80:
        return "🟢 強勢", "可考慮買入", "止賺+15-30%，止蝕-7%"
    elif score >= 70:
        return "🟢 偏強", "觀察，等待突破確認", "若突破可小注試探"
    elif score >= 60:
        return "🟡 中性", "觀望", "等待更明確信號"
    elif score >= 50:
        return "🟠 偏弱", "觀望，避免追入", "若持有可考慮減持"
    else:
        return "🔴 弱勢", "迴避", "若持有建議止蝕"

# ============================================================
# 主程式
# ============================================================
def main():
    print("=" * 60)
    print("恒指成份股大戶動能分析")
    print(f"分析日期：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    results = []
    
    for i, (ticker, name) in enumerate(HSI_LIST, 1):
        try:
            print(f"\n[{i}/{len(HSI_LIST)}] {name} ({ticker})...")
            
            # 抓取數據（1年用於MA200）
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y", interval="1d")
            
            if df.empty or len(df) < 50:
                print(f"  ⚠️ 數據不足，跳過")
                continue
            
            # 計算指標
            df = calc_indicators(df)
            
            # 評分
            score, details = score_stock(df)
            
            # 建議
            level, action, risk = get_advice(score)
            
            # 記錄結果
            results.append({
                'rank': 0,
                'code': ticker,
                'name': name,
                'price': round(df['Close'].iloc[-1], 2),
                'ma5': round(df['MA5'].iloc[-1], 2),
                'ma20': round(df['MA20'].iloc[-1], 2),
                'ma50': round(df['MA50'].iloc[-1], 2),
                'ma200': round(df['MA200'].iloc[-1], 2),
                'rsi': round(df['RSI'].iloc[-1], 1),
                'mfi': round(df['MFI'].iloc[-1], 1),
                'cmf': round(df['CMF'].iloc[-1], 3),
                'vol_ratio': round(df['Volume'].iloc[-1] / df['Vol_MA20'].iloc[-1], 2) if df['Vol_MA20'].iloc[-1] > 0 else 0,
                'macd_hist': round(df['MACD_Hist'].iloc[-1], 4),
                'score': score,
                'details': details,
                'level': level,
                'action': action,
                'risk': risk,
            })
            
            print(f"  📊 價格: {df['Close'].iloc[-1]:.2f} | RSI: {df['RSI'].iloc[-1]:.1f} | MFI: {df['MFI'].iloc[-1]:.1f} | CMF: {df['CMF'].iloc[-1]:.3f} | 評分: {score}")
            
            # 避免過快請求
            time.sleep(0.3)
            
        except Exception as e:
            print(f"  ❌ 分析失敗: {e}")
            continue
    
    # 排序
    results.sort(key=lambda x: x['score'], reverse=True)
    for i, r in enumerate(results, 1):
        r['rank'] = i
    
    return results

# ============================================================
# 生成報告
# ============================================================
def generate_report(results):
    """生成 Markdown 報告"""
    lines = []
    lines.append("# 恒指成份股大戶動能分析報告")
    lines.append(f"\n分析日期：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("數據來源：Yahoo Finance")
    lines.append("分析模型：大戶動能策略（Momentum + Money Flow）")
    lines.append("\n---\n")
    
    # 總覽
    strong = [r for r in results if r['score'] >= 70]
    neutral = [r for r in results if 50 <= r['score'] < 70]
    weak = [r for r in results if r['score'] < 50]
    
    lines.append("## 📊 總覽")
    lines.append(f"- 🟢 強勢/偏強（≥70分）：**{len(strong)}** 隻")
    lines.append(f"- 🟡 中性（50-69分）：**{len(neutral)}** 隻")
    lines.append(f"- 🔴 弱勢（<50分）：**{len(weak)}** 隻")
    lines.append(f"- 總計分析：**{len(results)}** 隻")
    
    # 前15名
    lines.append("\n## 🏆 前15名（大戶動能最強）")
    lines.append("| # | 股票 | 代碼 | 收盤價 | 20MA | RSI | MFI | CMF | 成交量比 | 總分 | 建議 |")
    lines.append("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    
    for r in results[:15]:
        lines.append(f"| {r['rank']} | {r['name']} | {r['code']} | {r['price']} | {r['ma20']} | {r['rsi']} | {r['mfi']} | {r['cmf']} | {r['vol_ratio']} | **{r['score']}** | {r['level']} |")
    
    # 後10名
    lines.append("\n## ⚠️ 後10名（最弱勢）")
    lines.append("| # | 股票 | 代碼 | 收盤價 | 20MA | RSI | MFI | CMF | 總分 | 建議 |")
    lines.append("|---:|---|---|---:|---:|---:|---:|---:|---:|---|")
    
    for r in results[-10:]:
        lines.append(f"| {r['rank']} | {r['name']} | {r['code']} | {r['price']} | {r['ma20']} | {r['rsi']} | {r['mfi']} | {r['cmf']} | **{r['score']}** | {r['level']} |")
    
    # 評分細則
    lines.append("\n## 📈 評分細則（滿分100）")
    lines.append("| 指標 | 權重 | 滿分條件 |")
    lines.append("|---|---:|---|")
    lines.append("| 趨勢結構 | 30分 | 收盤 > MA5 > MA10 > MA20，且 MA20 > MA50 > MA200 |")
    lines.append("| 量價動能 | 25分 | 成交量比 > 1.2，且價升量增 |")
    lines.append("| 大戶行為 | 30分 | MFI > 60 且 CMF > 0.1 |")
    lines.append("| 流動性 | 15分 | 日均成交量 > 5000萬股 |")
    
    # 入市建議
    lines.append("\n## 💡 入市建議")
    lines.append("1. **強勢股（≥70分）**：可考慮分批買入，止賺 +15-30%，止蝕 -7%")
    lines.append("2. **中性股（50-69分）**：觀望為主，等待突破確認")
    lines.append("3. **弱勢股（<50分）**：暫時迴避，等待轉強信號")
    lines.append("")
    lines.append("### 注意事項")
    lines.append("- 本分析基於技術指標，請結合基本面及市場環境判斷")
    lines.append("- 大戶動能策略最怕：假突破、末段追高、流動性陷阱")
    lines.append("- 建議配合「交易清單」使用，確認所有條件符合後再操作")
    
    # 持倉建議
    lines.append("\n## 📋 持倉建議")
    lines.append("| 股票 | 代碼 | 評分 | 建議動作 | 風險控制 |")
    lines.append("|---|---|---:|---|---|")
    for r in results:
        lines.append(f"| {r['name']} | {r['code']} | {r['score']} | {r['action']} | {r['risk']} |")
    
    return "\n".join(lines)

# ============================================================
# 執行
# ============================================================
if __name__ == "__main__":
    results = main()
    
    if results:
        # 保存報告
        report = generate_report(results)
        report_path = "/home/freet/.openclaw/workspace/sicsicduck/research/hsi_analysis_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n✅ 報告已保存至：{report_path}")
        
        # 顯示摘要
        print("\n" + "=" * 60)
        print("📊 分析摘要")
        print("=" * 60)
        strong = [r for r in results if r['score'] >= 70]
        neutral = [r for r in results if 50 <= r['score'] < 70]
        weak = [r for r in results if r['score'] < 50]
        print(f"🟢 強勢/偏強：{len(strong)} 隻")
        print(f"🟡 中性：{len(neutral)} 隻")
        print(f"🔴 弱勢：{len(weak)} 隻")
        print(f"\n🏆 前5名：")
        for r in results[:5]:
            print(f"  {r['rank']}. {r['name']} ({r['code']}) - {r['score']}分 - {r['level']}")
        print(f"\n⚠️ 後5名：")
        for r in results[-5:]:
            print(f"  {r['rank']}. {r['name']} ({r['code']}) - {r['score']}分 - {r['level']}")
    else:
        print("❌ 分析失敗")

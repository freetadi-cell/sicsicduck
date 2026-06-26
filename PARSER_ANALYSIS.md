# 銀行 Parser 分析 - 兌換及新資金優惠

## 已支援兌換優惠（exchange conditions）

| 銀行 | Parser | 兌換優惠 | 幣種 | 存款期 | 備註 |
|------|--------|---------|------|--------|------|
| 滙豐 HSBC | `hsbc.py` | ✅ | HKD/USD/CNY | 1w | Currency exchange section |
| 中銀香港 BOCHK | `bochk.py` | ✅ | CNY | 1w, 1m | 特優人民幣及外幣定期存款優惠 |
| 平安 PAO | `pao.py` | ❌ | - | - | 只有新資金優惠，無兌換優惠 |

## 已支援新資金優惠（new_funds fund_type）

| 銀行 | Parser | 新資金優惠 | 幣種 | 存款期 | 備註 |
|------|--------|-----------|------|--------|------|
| 滙豐 HSBC | `hsbc.py` | ✅ | HKD/USD/CNY | 3m, 6m, 12m | RewardCash + Preferential |
| 中銀香港 BOCHK | `bochk.py` | ✅ | HKD/USD/CNY | 3m, 6m, 12m | 新資金特優定期存款 |
| 恒生 Hang Seng | `hangseng.py` | ✅ | HKD/USD | 3m, 6m | 新資金定期存款優惠 |
| 渣打 SC | `sc.py` | ❌ | - | - | 只有網上定存，無條件標記 |
| 星展 DBS | `dbs.py` | ✅ | HKD/USD | 4m, 6m | 新資金定期存款優惠（100萬+） |
| 富邦 Fubon | `fubon.py` | ✅ | HKD/USD | 3m, 6m, 12m | 新資金定期存款優惠 |
| 工銀亞洲 ICBC | `icbc.py` | ✅ | HKD/USD/CNY | 3m, 6m | 全新資金定期存款推廣 |
| 中信 CNCBI | `cncbi.py` | ✅ | HKD/USD | 3m | inMotion新資金定期存款特惠 |
| 平安 PAO | `pao.py` | ✅ | HKD | 1m, 3m, 6m, 12m | 新資金定期存款優惠 |
| 螞蟻 Ant | `ant.py` | ✅ | HKD/USD | 1w-12m | 總年利率（含新資金加息） |
| 集友 Chiyu | `chiyu.py` | ✅ | HKD/USD/CNY | 1m-12m | 新資金定期存款推廣（分行） |

## 未支援兌換/新資金優惠（需要更新）

| 銀行 | Parser | 現狀 | 建議更新 |
|------|--------|------|---------|
| 渣打 SC | `sc.py` | 只有基本定存利率 | 加入新資金優惠條件標記 |
| 東亞 BEA | `bea.py` | 未分析 | 檢查是否有新資金/兌換優惠 |
| 交通銀行 BOCOM | `bocomm.py` | 未分析 | 檢查 PDF 內容 |
| 上海商業 SHACOM | `shacom.py` | 未分析 | 檢查官網 |
| 大眾銀行 Public Bank | `publicbank.py` | 未分析 | 檢查官網 |
| 招商永隆 Wing Lung | `winglung.py` | 未分析 | 檢查官網 |
| 創興 CH Bank | `chbank.py` | 未分析 | 檢查官網 |
| 富融 Fusion | `fusion.py` | 未分析 | 虛擬銀行，可能有新資金優惠 |
| 象象 Airstar | `airstar.py` | 未分析 | 虛擬銀行，可能有新資金優惠 |
| 眾安 ZA | `za.py` | 未分析 | 虛擬銀行，可能有新資金優惠 |
| 匯立 WeLab | `welab.py` | 未分析 | 虛擬銀行，可能有新資金優惠 |
| 理慧 livi | `livi.py` | 未分析 | 虛擬銀行，可能有新資金優惠 |

---

## 數據結構說明

### fund_type 欄位
- `new_funds`: 新資金優惠
- `existing_funds`: 現有資金優惠

### conditions 欄位（陣列）
- `exchange`: 兌換資金優惠
- `new_account`: 開立新戶口
- `upgrade_wealth`: 提升至理財戶口

### 範例
```json
{
  "hkd": {
    "3m": {
      "rate": 2.8,
      "min_deposit": 10000,
      "fund_type": "new_funds",
      "conditions": [],
      "note": "新資金定期存款優惠"
    },
    "1w": {
      "rate": 12.0,
      "min_deposit": 10000,
      "fund_type": null,
      "conditions": ["exchange"],
      "note": "兌換資金優惠"
    }
  }
}
```

---

## 下一步行動

1. **檢查未分析嘅 parser** - 睇下佢哋嘅官網有冇兌換/新資金優惠
2. **更新現有 parser** - 如果有優惠但冇標記，加入 `fund_type` 同 `conditions`
3. **更新 `update_rates.py`** - 確保所有條件正確傳遞到 `rates.json`

生成時間：2026-06-26

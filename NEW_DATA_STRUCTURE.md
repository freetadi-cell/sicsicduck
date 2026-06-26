# 新數據結構設計 - 分開記錄所有條件利率

## 舊結構（現有）
```json
{
  "hkd": {
    "3m": {
      "rate": 3.0,
      "fund_type": "new_funds",
      "conditions": [],
      "min_deposit": 1000000,
      "note": "新資金定期存款優惠"
    }
  }
}
```
**問題：** 只記錄一個利率，無法同時顯示新資金、現有資金、兌換資金嘅利率

---

## 新結構（建議）
```json
{
  "hkd": {
    "3m": {
      "new_funds": {
        "rate": 3.0,
        "min_deposit": 1000000,
        "conditions": [],
        "note": "新資金定期存款優惠（100萬港元以上）",
        "source": "bank"
      },
      "existing_funds": {
        "rate": 2.5,
        "min_deposit": 50000,
        "conditions": [],
        "note": "網上定存特惠年利率",
        "source": "bank"
      },
      "exchange": {
        "rate": null,
        "min_deposit": null,
        "conditions": ["exchange"],
        "note": null,
        "source": null
      }
    }
  }
}
```

---

## 實施步驟

### 1. 更新數據結構
- 修改 `rates.json` 結構
- 每個年期分為 `new_funds` / `existing_funds` / `exchange` 三個子項

### 2. 更新 Parser
每個 parser 需要提取所有條件嘅利率：

**星展銀行 (dbs.py) 範例：**
```python
result = {
  'hkd': {
    '3m': {
      'existing_funds': {'rate': 2.5, 'min_deposit': 50000},
      # new_funds 沒有 3m
      # exchange 沒有 3m
    },
    '4m': {
      'new_funds': {'rate': 3.0, 'min_deposit': 1000000},
      'existing_funds': {'rate': 2.45, 'min_deposit': 50000},
    },
    '6m': {
      'new_funds': {'rate': 3.0, 'min_deposit': 1000000},
      'existing_funds': {'rate': 2.3, 'min_deposit': 50000},
    }
  }
}
```

**滙豐銀行 (hsbc.py) 範例：**
```python
result = {
  'hkd': {
    '1w': {
      'exchange': {'rate': 7.0, 'conditions': ['exchange', 'new_account']},
    },
    '3m': {
      'new_funds': {'rate': 2.395, 'min_deposit': 10000},
    }
  }
}
```

### 3. 更新 update_rates.py
- 新增 `_apply_result_rates_new_structure()` 函數
- 將 parser 返回嘅數據正確分類到 new_funds / existing_funds / exchange
- 保持向後兼容（如果 parser 未更新，仍然可以用舊格式）

### 4. 更新網站前端
- 修改篩選邏輯，根據選擇顯示對應條件嘅利率
- 例如：選「新資金」→ 顯示 `period.new_funds.rate`
- 選「兌換」→ 顯示 `period.exchange.rate`

### 5. 遷移現有數據
- 寫腳本將現有 rates.json 轉換為新結構
- 備份舊檔案

---

## 條件類型定義

### fund_type（資金類型）
- `new_funds`: 新資金優惠
- `existing_funds`: 現有資金優惠
- `any_funds`: 不限資金來源（一般利率）

### conditions（額外條件，陣列）
- `exchange`: 兌換資金（通常係短期高息）
- `new_account`: 開立新戶口
- `upgrade_wealth`: 提升至理財戶口

---

## 優點
1. **完整數據**：同時顯示所有條件嘅利率，方便比較
2. **靈活篩選**：用戶可按條件篩選，看到該條件下嘅最佳利率
3. **數據完整**：唔會因為只保留最高利率而遺失資訊
4. **向後兼容**：舊 parser 仍可運作，逐步遷移

---

## 修改範圍

### Parser（需要更新）
- ✅ dbs.py（星展）- 已有新資金/現有資金邏輯
- ✅ hsbc.py（滙豐）- 已有兌換/新資金邏輯
- ✅ bochk.py（中銀）- 已有兌換/新資金邏輯
- ⏳ 其他 22 個 parser - 需要逐步更新

### 核心腳本
- ⏳ update_rates.py - 更新應用邏輯
- ⏳ rates.json - 數據結構遷移

### 前端
- ⏳ index.html - 更新篩選邏輯

---

生成時間：2026-06-26

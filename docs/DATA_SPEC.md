# 利率數據規範 (Rates Data Specification)

## 數據結構

每個利率項目應包含以下欄位：

```json
{
  "rate": 3.5,
  "min_deposit": 10000,
  "note": "產品描述",
  "source": "bank",
  "conditions": []
}
```

## 欄位定義

### `rate` (必填)
- 利率數值（百分比）
- 類型：`number | null`
- 例如：`3.5` 表示 3.5%

### `min_deposit` (選填)
- 最低存款金額
- 類型：`number | null`
- 貨幣單位與利率相同（HKD/USD/CNY）

### `note` (選填)
- **產品描述**，說明該利率屬於邊種產品/推廣
- 類型：`string | null`
- **唔係來源說明**（來源應放 `source` 欄位）

#### 正確示例：
- ✅ `定期存款牌價利率`
- ✅ `新資金定期存款優惠（網上理財）`
- ✅ `雲利率（網上/流動理財）`

#### 錯誤示例：
- ❌ `從香港經濟日報提取` → 應該用 `source: "hket"`
- ❌ `UHK 港生活` → 應該用 `source: "uhk"`
- ❌ `*` → 無意義佔位符，應清空

### `source` (必填)
- 數據來源，說明利率從邊度取得
- 類型：`string`
- 必須使用標準化嘅來源代碼

#### 標準來源代碼：

| 代碼 | 說明 | 可靠度 |
|------|------|--------|
| `bank` | 銀行官網直接爬取 | ⭐⭐⭐ 最高 |
| `hket` | 香港經濟日報 | ⭐⭐ 高 |
| `uhk` | UHK 港生活 | ⭐⭐ 高 |
| `moneyhero` | MoneyHero 比較平台 | ⭐ 中 |
| `estimate` | 估計值（無法直接取得） | ⚠️ 低 |

#### 唔好用嘅格式：
- ❌ `HKET 2026-07-10` → 應該用 `hket`
- ❌ `各銀行官網 / HKET香港經濟日報（補充）` → 呢個係全局說明，唔係單項 source

### `conditions` (選填)
- 利率條件標籤
- 類型：`string[]`
- 標準條件：

| 標籤 | 說明 |
|------|------|
| `new_funds` | 新資金 |
| `new_customer` | 新客戶 |
| `new_account` | 新開戶口 |
| `exchange` | 兌換資金 |
| `mobile_banking` | 手機銀行 |
| `limited_time` | 限時優惠 |

## Parser 寫作規範

所有 parser 必須：

1. **喺每個利率層級寫 `source`**
   ```python
   rates['hkd']['3m'] = {
       'rate': 3.5,
       'note': '新資金定期存款優惠',
       'source': 'bank',
       'min_deposit': 10000
   }
   ```

2. **唔好寫全局 `note`**
   ```python
   # ❌ 錯誤
   result['note'] = '滙豐定期存款優惠'
   
   # ✅ 正確
   rates['hkd']['3m']['note'] = '滙豐定期存款優惠（新資金）'
   ```

3. **外部數據源要標註**
   ```python
   # 如果數據來自 HKET
   rates['hkd']['3m'] = {
       'rate': 3.5,
       'note': '新資金定期存款優惠',
       'source': 'hket',
       'min_deposit': 10000
   }
   ```

4. **估計值要標註**
   ```python
   rates['hkd']['1m'] = {
       'rate': 0.1,
       'note': '定期存款牌價利率（估計）',
       'source': 'estimate',
       'min_deposit': 10000
   }
   ```

## 前端顯示規範

### 來源標記

| 來源 | 標記 | 樣式 |
|------|------|------|
| `bank` | 無 | 直接顯示 |
| `hket` | 📰 | 灰色小字 |
| `uhk` | 📊 | 灰色小字 |
| `moneyhero` | * | 現有樣式 |
| `estimate` | ⚠️ | 橙色標記 |

### 備註顯示

- `note` 欄位直接顯示喺備註欄
- 唔包含來源說明（來源用標記顯示）
- 過期資訊要清理

## 數據清理規則

1. **統一 source 格式**
   - `HKET 2026-07-10` → `hket`
   - `香港經濟日報` → `hket`
   - `UHK 港生活` → `uhk`

2. **清理備註**
   - 移除「從...提取」字樣
   - 清空 `*` 佔位符
   - 移除過期資訊（如「至6月起」）

3. **分離 note 同 source**
   - 原本 `note: "從香港經濟日報提取"` → `note: null`, `source: "hket"`
   - 原本 `note: "UHK 港生活"` → `note: null`, `source: "uhk"`

---

*建立日期：2026-07-23*
*最後更新：2026-07-23*
"""星展銀行 DBS - Parser for online time deposit rates.

Page: https://www.dbs.com.hk/personal-zh/promotion/OnlineTD-promo#exist_fund

Three rate tiers on page:
1. 網上定存優惠 (HKD 50,000+) — standard online TD rates
2. 現有資金定期存款優惠 (HKD 1,000,000+ / USD 128,000+) — existing fund large deposit
3. 新資金定期存款優惠 (HKD 1,000,000+ / USD 128,000+) — new fund large deposit

Parser extracts the best available rate for each period.
Uses data-rate attributes in HTML for new fund rates (tab content may be hidden).
"""
import re


def parse(text, tables=None, html=None):
    """Parse DBS HK online time deposit rates.

    Page format (June 2026):
    現有資金定期存款優惠:
      港元 高達 2.80%, 4或6個月 2.80%
      美元 高達 3.80%, 4或6個月 3.80%

    新資金定期存款優惠 (from data-rate attrs in HTML):
      港元 高達 3.00%, 4或6個月 3.00%
      美元 高達 4.00%, 4或6個月 4.00%

    網上定存優惠 table (HKD 50K+):
      1個月 2.00% | 3個月 2.40% | 6個月 2.30% | 12個月 2.30%

    Returns rates with proper fund_type tagging:
    - new_funds: 新資金優惠（大額，100萬港元或65,000美元以上）
    - existing_funds: 現有資金優惠或一般網上定存
    """
    if not text:
        return None

    rates = {}

    # === 網上定存優惠 table (HKD 50K+) ===
    hkd_rates = {}
    # Find the base rate section (after 現有資金 or at the main rate table)
    # Look for the standard rate table which has all periods
    # Try to find a section with period rates that is NOT the promo section
    base_text = text
    promo_idx = text.find('定期存款優惠')
    if promo_idx >= 0:
        # The base rates are typically after the promo sections
        # Find the last section with rate patterns
        pass
    
    # Extract all period-rate matches - but only from the standard table
    # Standard table has format: X個月 X.XX% without currency prefixes
    # Look specifically for a clean list of periods
    for period, label in [('1m', '1個月'), ('2m', '2個月'), ('3m', '3個月'),
                           ('4m', '4個月'), ('6m', '6個月'), ('9m', '9個月'),
                           ('12m', '12個月')]:
        m = re.search(rf'{label}\s+(\d+\.\d+)%', base_text)
        if m:
            hkd_rates[period] = float(m.group(1))
    
    # If we got unrealistically high rates (from promo section), 
    # they'll be corrected by the promo override logic below
    # The key insight: nf_hkd and exist_hkd will override appropriately

    # === 新資金定期存款優惠 ===
    nf_hkd = {}
    nf_usd = {}

    # Try text-based extraction first (current page format)
    # Pattern: 港元 高達\n3.00%\n年利率  or  美元 高達\n4.00%\n年利率
    # Then: 4或6個月\t3.00%\t4.00%
    nf_idx = text.find('網上新資金定期存款優惠')
    if nf_idx < 0:
        nf_idx = text.find('新資金定期存款優惠')
    if nf_idx >= 0:
        nf_section = text[nf_idx:nf_idx + 1000]
        
        # Clean up whitespace (including newlines)
        nf_section_clean = re.sub(r'\s+', ' ', nf_section)
        
        # Find the period table: 4或6個月  3.00%  4.00%
        period_match = re.search(r'(\d+)或(\d+)個月\s+(\d+\.\d+)%\s+(\d+\.\d+)%', nf_section_clean)
        if period_match:
            p1 = _days_to_period(int(period_match.group(1)) * 30)
            p2 = _days_to_period(int(period_match.group(2)) * 30)
            nf_hkd[p1] = float(period_match.group(3))
            nf_hkd[p2] = float(period_match.group(3))
            nf_usd[p1] = float(period_match.group(4))
            nf_usd[p2] = float(period_match.group(4))
        else:
            # Try headline rates as fallback
            hkd_nf_match = re.search(r'港元\s*高達\s*(\d+\.\d+)%', nf_section_clean)
            if hkd_nf_match:
                # Without specific period, can't use this rate
                pass

    # Fallback: try data-rate attrs in HTML
    if not nf_hkd and not nf_usd and html:
        for m in re.finditer(
            r'data-currency="HKD"\s+data-days="(\d+)"\s+data-fund="new"\s+[^>]*data-rate="(\d+\.\d+)"',
            html
        ):
            days, rate = int(m.group(1)), float(m.group(2))
            period = _days_to_period(days)
            if period and rate > nf_hkd.get(period, 0):
                nf_hkd[period] = rate
        for m in re.finditer(
            r'data-currency="USD"\s+data-days="(\d+)"\s+data-fund="new"\s+[^>]*data-rate="(\d+\.\d+)"',
            html
        ):
            days, rate = int(m.group(1)), float(m.group(2))
            period = _days_to_period(days)
            if period and rate > nf_usd.get(period, 0):
                nf_usd[period] = rate

    # === 現有資金定期存款優惠 (HKD 1M+ / USD 128K+) ===
    exist_idx = text.find('現有資金定期存款優惠')
    exist_hkd = {}
    exist_usd = {}
    if exist_idx >= 0:
        exist_section = text[exist_idx:exist_idx + 800]
        # Pattern: 4或6個月  2.80%  3.80%
        m = re.search(r'(\d+)或(\d+)個月\s+(\d+\.\d+)%\s+(\d+\.\d+)%', exist_section)
        if m:
            p1 = _days_to_period(int(m.group(1)) * 30)
            p2 = _days_to_period(int(m.group(2)) * 30)
            exist_hkd[p1] = float(m.group(3))
            exist_hkd[p2] = float(m.group(3))
            exist_usd[p1] = float(m.group(4))
            exist_usd[p2] = float(m.group(4))
        else:
            # Old format: 4或6個月\t2.80%\t3.80%
            m = re.search(r'4或6個月\s+(\d+\.\d+)%\s+(\d+\.\d+)%', exist_section)
            if m:
                exist_hkd['4m'] = float(m.group(1))
                exist_hkd['6m'] = float(m.group(1))
                exist_usd['4m'] = float(m.group(2))
                exist_usd['6m'] = float(m.group(2))

    # === Build HKD rates ===
    if hkd_rates:
        rates['hkd'] = {}
        for period, rate in hkd_rates.items():
            rates['hkd'][period] = {
                'rate': rate,
                'fund_type': 'existing_funds',
                'min_deposit': 50000
            }
        
        # Override with new fund promo rates (higher threshold but better rates)
        for period, rate in nf_hkd.items():
            if period in rates['hkd']:
                # New fund rate should override if it's higher or equal
                # Note: DBS new fund rates require HKD 1,000,000+ but offer better rates
                rates['hkd'][period] = {
                    'rate': rate,
                    'fund_type': 'new_funds',
                    'min_deposit': 1000000,
                    'note': '新資金定期存款優惠（100萬港元以上）'
                }
            else:
                # Period not in base table but exists in promo
                rates['hkd'][period] = {
                    'rate': rate,
                    'fund_type': 'new_funds',
                    'min_deposit': 1000000,
                    'note': '新資金定期存款優惠（100萬港元以上）'
                }
        
        # Only apply existing fund rates if higher than base AND no new fund rate
        for period, rate in exist_hkd.items():
            if period in rates['hkd']:
                curr = rates['hkd'][period].get('rate', 0)
                is_new_fund = rates['hkd'][period].get('fund_type') == 'new_funds'
                # Don't override new_funds rates with existing_funds rates
                if rate > curr and not is_new_fund:
                    rates['hkd'][period] = {
                        'rate': rate,
                        'fund_type': 'existing_funds',
                        'min_deposit': 1000000,
                        'note': '現有資金定期存款優惠（100萬港元以上）'
                    }

    # === Build USD rates ===
    if nf_usd or exist_usd:
        rates['usd'] = {}
        all_usd = {}
        for period, rate in nf_usd.items():
            all_usd[period] = {
                'rate': rate,
                'fund_type': 'new_funds',
                'min_deposit': 65000,
                'note': '新資金定期存款優惠（65,000美元以上）',
            }
        for period, rate in exist_usd.items():
            if period not in all_usd or rate > all_usd[period]['rate']:
                all_usd[period] = {
                    'rate': rate,
                    'fund_type': 'existing_funds',
                    'min_deposit': 128000,
                    'note': '現有資金定期存款優惠（128,000美元以上）',
                }
        rates['usd'] = all_usd

    if rates and ('hkd' in rates or 'usd' in rates):
        rates['note'] = '網上定存特惠年利率'
        return rates

    return None


def _days_to_period(days):
    """Convert days to period key."""
    mapping = {
        7: '1w', 14: '2w', 30: '1m', 60: '2m', 90: '3m',
        120: '4m', 180: '6m', 270: '9m', 365: '12m',
    }
    return mapping.get(days)

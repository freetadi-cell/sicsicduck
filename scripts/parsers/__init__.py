# Bank rate parsers - each file handles one bank
# Filename format: <bank_key>.py
# Each must export: parse(page_text: str, tables: list) -> dict or None
#
# Return format:
# {
#     'hkd': {'1m': rate, '3m': rate, '6m': rate, '12m': rate},
#     'usd': {'1m': rate, '3m': rate, '6m': rate, '12m': rate},
#     'note': 'optional note',  # optional
# }
# Or None if parsing fails

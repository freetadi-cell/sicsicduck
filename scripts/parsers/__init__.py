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

from .hsbc import parse as parse_hsbc
from .bochk import parse as parse_bochk
from .hangseng import parse as parse_hangseng
from .sc import parse as parse_sc
from .dbs import parse as parse_dbs
from .bea import parse as parse_bea
from .cncbi import parse as parse_cncbi
from .icbc import parse as parse_icbc
from .fubon import parse as parse_fubon
from .bocomm import parse as parse_bocomm
from .shacom import parse as parse_shacom
from .publicbank import parse as parse_publicbank
from .winglung import parse as parse_winglung
from .chbank import parse as parse_chbank
from .fusion import parse as parse_fusion
from .airstar import parse as parse_airstar
from .za import parse as parse_za
from .pao import parse as parse_pao
from .welab import parse as parse_welab
from .livi import parse as parse_livi
from .ant import parse as parse_ant
from .chiyu import parse as parse_chiyu
from .ncb import parse as parse_ncb
from .pingan import parse as parse_pingan

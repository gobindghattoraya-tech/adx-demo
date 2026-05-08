"""
ADX primary market seed data constants.
Source: ADX Issuers Directory (adx.ae) — as of May 2026.

Each Symbol defines:
  - ticker:      Official ADX ticker symbol
  - full_name:   Company full registered name
  - sector_name: Must match a Sector.name in SECTORS list
  - tick_size:   Minimum price increment (Decimal for precision)
  - lot_size:    Minimum trade quantity
  - currency:    ISO 4217 currency code (default: AED)
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Sector:
    name: str
    description: str


@dataclass(frozen=True)
class Symbol:
    ticker: str
    full_name: str
    sector_name: str
    tick_size: Decimal
    lot_size: int
    currency: str = "AED"


SECTORS: list[Sector] = [
    Sector("Banking",     "Financial services and banking institutions"),
    Sector("Diversified", "Conglomerates and holding companies"),
    Sector("Energy",      "Oil, gas, and energy sector companies"),
    Sector("Telecom",     "Telecommunications service providers"),
    Sector("Real Estate", "Property development and investment"),
    Sector("Chemicals",   "Petrochemical and industrial companies"),
]

SYMBOLS: list[Symbol] = [
    # ── Banking ────────────────────────────────────────────────────────────────
    Symbol("FAB",        "First Abu Dhabi Bank P.J.S.C.",           "Banking",     Decimal("0.01"), 100),
    Symbol("ADCB",       "Abu Dhabi Commercial Bank PJSC",           "Banking",     Decimal("0.01"), 100),
    Symbol("ADIB",       "Abu Dhabi Islamic Bank PJSC",              "Banking",     Decimal("0.01"), 100),
    # ── Diversified ────────────────────────────────────────────────────────────
    Symbol("IHC",        "International Holding Company PJSC",       "Diversified", Decimal("0.50"), 10),
    Symbol("ALPHADHABI", "Alpha Dhabi Holding PJSC",                 "Diversified", Decimal("0.05"), 50),
    # ── Energy ─────────────────────────────────────────────────────────────────
    Symbol("TAQA",       "Abu Dhabi National Energy Company PJSC",   "Energy",      Decimal("0.01"), 200),
    Symbol("ADNOCGAS",   "ADNOC Gas PLC",                            "Energy",      Decimal("0.01"), 100),
    Symbol("ADNOCDRILL", "ADNOC Drilling Company P.J.S.C.",          "Energy",      Decimal("0.01"), 100),
    Symbol("ADNOCDIST",  "ADNOC Distribution PJSC",                  "Energy",      Decimal("0.01"), 100),
    Symbol("ADNOCLS",    "ADNOC Logistics & Services plc",           "Energy",      Decimal("0.01"), 100),
    # ── Telecom ────────────────────────────────────────────────────────────────
    Symbol("EAND",       "Emirates Telecommunications Group (e&)",   "Telecom",     Decimal("0.01"), 100),
    Symbol("ETISALAT",   "Abu Dhabi National Telecom Co.",           "Telecom",     Decimal("0.01"), 100),
    # ── Real Estate ────────────────────────────────────────────────────────────
    Symbol("ALDAR",      "Aldar Properties PJSC",                    "Real Estate", Decimal("0.01"), 200),
    Symbol("MODON",      "Modon Holding PSC",                        "Real Estate", Decimal("0.01"), 100),
    # ── Chemicals ──────────────────────────────────────────────────────────────
    Symbol("BOROUGE",    "Borouge plc",                              "Chemicals",   Decimal("0.01"), 100),
]

# Quick-access sets for validation
SECTOR_NAMES: frozenset[str] = frozenset(s.name for s in SECTORS)
TICKER_SYMBOLS: frozenset[str] = frozenset(s.ticker for s in SYMBOLS)

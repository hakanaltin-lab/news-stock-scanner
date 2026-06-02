#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  GLOBAL HABER -> SEKTOR -> HISSE FIRSAT TARAYICI  -  v2.0  (FREE STACK)
================================================================================

AMAÇ
  Dünyadaki ücretsiz haber akışlarını okuyup, haberlerin hangi sektör/temalara ve
  hangi ABD hisselerine pozitif/negatif etki edebileceğini çıkarmak; ardından bu
  hisseleri ücretsiz fiyat/temel veriyle teknik + temel + değerleme + risk
  skorlarından geçirip fırsat/risk listesi üretmek.

ÜCRETSİZ KAYNAKLAR
  - RSS / Google News RSS / BBC RSS
  - GDELT DOC 2.0 API (ücretsiz, API key gerektirmez)
  - yfinance / Yahoo Finance public data (araştırma/öğrenme amaçlı)

DÜRÜST UYARILAR
  - Bu sistem Bloomberg/RavenPack/Dataminr gibi saniyelik kurumsal feed değildir.
  - Ücretsiz haber ve fiyat kaynakları gecikmeli/eksik/hatalı olabilir.
  - Çıktılar yatırım tavsiyesi değildir; araştırma başlangıç noktasıdır.
  - “Ucuz” görünen hisse değer tuzağı olabilir; skor final karar değildir.
================================================================================
"""

from __future__ import annotations

import argparse
import csv
import email.utils
import html
import json
import math
import os
import random
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


# =============================================================================
# AYARLAR
# =============================================================================

APP_NAME = "Global News-to-Stock Opportunity Scanner v2.0"

TOP_N = 20
DEFAULT_HOURS = 8

OUTPUT_CSV = "news_stock_opportunities_v20.csv"
OUTPUT_HTML = "news_stock_report_v20.html"

# Skor ağırlıkları: toplam 1.0
WEIGHTS = {
    "catalyst": 0.25,
    "sector_momentum": 0.15,
    "technical": 0.20,
    "quality": 0.20,
    "value": 0.10,
    "risk": 0.10,
}

# Haber skoru zaman çürümesi: age_seconds büyüdükçe haber etkisi azalır
NEWS_DECAY_LAMBDA = 0.000045

# yfinance çağrıları arası bekleme: ücretsiz kaynaklara nazik davranmak için
TICKER_SLEEP_SECONDS = 0.25

# Fiyat verisi
PRICE_PERIOD = "1y"
MIN_PRICE_ROWS = 80

# Çok düşük likidite / penny stock filtresi
MIN_MARKET_CAP = 300_000_000
MIN_AVG_VOLUME = 200_000
MIN_PRICE = 2.0


# =============================================================================
# HABER KAYNAKLARI
# =============================================================================

RSS_FEEDS = {
    "macro": [
        "https://news.google.com/rss/search?q=Fed+OR+inflation+OR+CPI+OR+rates+OR+recession&hl=en-US&gl=US&ceid=US:en",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ],
    "geopolitics": [
        "https://news.google.com/rss/search?q=war+OR+sanctions+OR+missile+OR+NATO+OR+Iran+OR+China+Taiwan&hl=en-US&gl=US&ceid=US:en",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ],
    "technology": [
        "https://news.google.com/rss/search?q=AI+OR+semiconductor+OR+chip+OR+datacenter+OR+GPU+OR+cloud&hl=en-US&gl=US&ceid=US:en",
    ],
    "energy": [
        "https://news.google.com/rss/search?q=oil+OR+OPEC+OR+LNG+OR+uranium+OR+nuclear+OR+energy+prices&hl=en-US&gl=US&ceid=US:en",
    ],
    "cyber": [
        "https://news.google.com/rss/search?q=cyberattack+OR+ransomware+OR+data+breach+OR+cybersecurity&hl=en-US&gl=US&ceid=US:en",
    ],
    "market": [
        "https://news.google.com/rss/search?q=earnings+beat+OR+guidance+raised+OR+upgrade+OR+downgrade+stocks&hl=en-US&gl=US&ceid=US:en",
    ],
}

GDELT_QUERIES = [
    "AI semiconductor GPU datacenter",
    "chip export restrictions China Taiwan semiconductor",
    "Fed inflation CPI rate cut rate hike",
    "war sanctions missile NATO defense spending",
    "oil OPEC crude LNG energy prices",
    "uranium nuclear reactor energy policy",
    "cyberattack ransomware cybersecurity data breach",
    "robotics humanoid robot automation factory",
    "crypto bitcoin ETF regulation",
    "cloud capex hyperscaler datacenter power grid",
]

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"


# =============================================================================
# TEMA / SEKTÖR / HİSSE EVRENİ
# =============================================================================

@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    etf: Optional[str]
    tickers: Tuple[str, ...]
    match_keywords: Tuple[str, ...]
    positive_keywords: Tuple[str, ...]
    negative_keywords: Tuple[str, ...]


THEMES: Dict[str, Theme] = {
    "ai_infra": Theme(
        key="ai_infra",
        label="AI Infrastructure / Data Center",
        etf="XLK",
        tickers=("NVDA", "AVGO", "AMD", "ANET", "VRT", "ETN", "DELL", "HPE", "SMCI", "PSTG", "MU", "MRVL", "ORCL", "MSFT", "GOOGL", "AMZN"),
        match_keywords=("ai", "artificial intelligence", "gpu", "datacenter", "data center", "cloud capex", "hyperscaler", "accelerator", "sovereign ai"),
        positive_keywords=("strong demand", "capex", "buildout", "record", "surge", "approval", "partnership", "orders", "upgrade", "raised guidance", "accelerates", "expansion"),
        negative_keywords=("export restriction", "ban", "delay", "capacity shortage", "downgrade", "cuts guidance", "investigation", "antitrust", "weaker demand"),
    ),
    "semiconductor": Theme(
        key="semiconductor",
        label="Semiconductor / Equipment",
        etf="SMH",
        tickers=("NVDA", "AMD", "AVGO", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "MU", "MRVL", "ARM", "ON", "NXPI", "QCOM", "ADI", "TXN", "COHR"),
        match_keywords=("semiconductor", "chip", "foundry", "wafer", "memory", "hbm", "lithography", "chipmaking", "export controls"),
        positive_keywords=("demand", "shortage", "orders", "upgrade", "investment", "subsidy", "capacity expansion", "earnings beat", "hbm", "advanced packaging"),
        negative_keywords=("export restriction", "inventory correction", "weak demand", "ban", "sanction", "delay", "downgrade", "miss", "cuts forecast"),
    ),
    "power_grid": Theme(
        key="power_grid",
        label="Power / Electrification / Grid",
        etf="XLI",
        tickers=("ETN", "GEV", "PWR", "HUBB", "EMR", "ROK", "ABB", "NVT", "VRT", "GNRC"),
        match_keywords=("power grid", "electricity demand", "transformer", "electrification", "grid", "datacenter power", "power equipment"),
        positive_keywords=("demand", "shortage", "orders", "backlog", "upgrade", "investment", "capacity", "grid expansion", "infrastructure"),
        negative_keywords=("delay", "shortfall", "downgrade", "margin pressure", "supply chain", "cost overrun"),
    ),
    "cybersecurity": Theme(
        key="cybersecurity",
        label="Cybersecurity",
        etf="HACK",
        tickers=("CRWD", "PANW", "FTNT", "ZS", "S", "OKTA", "NET", "DDOG", "CYBR", "TENB"),
        match_keywords=("cyber", "cyberattack", "ransomware", "data breach", "hack", "zero day", "malware", "security software"),
        positive_keywords=("cyberattack", "ransomware", "breach", "demand", "mandate", "contract", "upgrade", "platform", "federal", "security spending"),
        negative_keywords=("downgrade", "breach at", "outage", "guidance cut", "competition", "miss"),
    ),
    "defense": Theme(
        key="defense",
        label="Defense / Aerospace",
        etf="ITA",
        tickers=("LMT", "RTX", "NOC", "GD", "LHX", "HII", "TXT", "BA", "KTOS", "AVAV", "PLTR"),
        match_keywords=("war", "missile", "military", "defense", "defence", "nato", "weapons", "drone", "rearmament", "army", "air force"),
        positive_keywords=("defense spending", "contract", "order", "budget", "aid package", "missile", "drone", "nato", "rearm", "procurement"),
        negative_keywords=("budget cut", "delay", "cost overrun", "accident", "investigation", "contract cancelled"),
    ),
    "energy_oil_gas": Theme(
        key="energy_oil_gas",
        label="Oil / Gas / LNG",
        etf="XLE",
        tickers=("XOM", "CVX", "COP", "SLB", "HAL", "EOG", "OXY", "LNG", "WMB", "KMI"),
        match_keywords=("oil", "opec", "crude", "lng", "gas prices", "energy prices", "supply cut", "middle east"),
        positive_keywords=("supply cut", "prices rise", "sanctions", "disruption", "demand growth", "lng contract", "opec cut", "inventory draw"),
        negative_keywords=("oil falls", "oversupply", "demand weak", "inventory build", "recession", "price cap", "production surge"),
    ),
    "uranium_nuclear": Theme(
        key="uranium_nuclear",
        label="Uranium / Nuclear / SMR",
        etf="URA",
        tickers=("CCJ", "CEG", "UEC", "UUUU", "NXE", "DNN", "BWXT", "SMR"),
        match_keywords=("uranium", "nuclear", "reactor", "smr", "small modular reactor", "nuclear power"),
        positive_keywords=("approval", "reactor", "restart", "supply deficit", "contract", "nuclear policy", "clean energy", "uranium price"),
        negative_keywords=("delay", "accident", "shutdown", "regulatory setback", "cost overrun", "project cancelled"),
    ),
    "robotics_physical_ai": Theme(
        key="robotics_physical_ai",
        label="Robotics / Physical AI / Automation",
        etf="BOTZ",
        tickers=("ISRG", "TER", "ROK", "SYM", "PATH", "ZBRA", "ABB", "HON", "DE", "TSLA", "NVDA"),
        match_keywords=("robot", "robotics", "humanoid", "automation", "factory automation", "physical ai", "warehouse automation"),
        positive_keywords=("orders", "deployment", "partnership", "factory", "launch", "upgrade", "autonomous", "scale", "productivity"),
        negative_keywords=("delay", "safety issue", "recall", "downgrade", "miss", "cuts guidance"),
    ),
    "crypto_equities": Theme(
        key="crypto_equities",
        label="Crypto-linked Equities",
        etf="BITQ",
        tickers=("COIN", "MSTR", "MARA", "RIOT", "CLSK", "HOOD", "SQ", "PYPL", "IBIT"),
        match_keywords=("bitcoin", "crypto", "ethereum", "stablecoin", "etf", "sec", "blockchain"),
        positive_keywords=("bitcoin rises", "surge", "approval", "inflows", "record high", "regulation clarity", "adoption", "rally"),
        negative_keywords=("bitcoin falls", "crackdown", "lawsuit", "outflows", "ban", "hack", "liquidation", "selloff"),
    ),
    "fintech_banks": Theme(
        key="fintech_banks",
        label="Banks / Fintech / Rates",
        etf="XLF",
        tickers=("JPM", "BAC", "GS", "MS", "C", "WFC", "V", "MA", "AXP", "HOOD", "SQ", "PYPL", "SOFI"),
        match_keywords=("bank", "rates", "yield", "credit", "fintech", "consumer finance", "loan", "net interest margin"),
        positive_keywords=("higher rates", "soft landing", "loan growth", "trading revenue", "upgrade", "capital return", "buyback"),
        negative_keywords=("credit losses", "recession", "rate cut", "defaults", "regulatory", "deposit outflows", "downgrade"),
    ),
    "software_cloud": Theme(
        key="software_cloud",
        label="Cloud / Software / SaaS",
        etf="IGV",
        tickers=("MSFT", "ORCL", "CRM", "SNOW", "DDOG", "NET", "NOW", "MDB", "ADBE", "PLTR", "TEAM", "WDAY"),
        match_keywords=("cloud", "software", "saas", "enterprise ai", "database", "ai agent", "subscription", "guidance"),
        positive_keywords=("earnings beat", "raised guidance", "ai demand", "contract", "partnership", "accelerating growth", "upgrade"),
        negative_keywords=("slowing growth", "cuts guidance", "downgrade", "competition", "margin pressure", "security incident"),
    ),
    "healthcare_biotech": Theme(
        key="healthcare_biotech",
        label="Healthcare / Biotech / GLP-1",
        etf="XLV",
        tickers=("LLY", "NVO", "MRK", "ABBV", "PFE", "AMGN", "REGN", "VRTX", "ISRG", "TMO", "DHR", "UNH"),
        match_keywords=("fda", "drug", "trial", "glp-1", "obesity", "biotech", "pharma", "approval", "clinical"),
        positive_keywords=("approval", "positive trial", "beats endpoint", "fast track", "strong sales", "upgrade", "label expansion"),
        negative_keywords=("trial failure", "rejected", "safety", "side effect", "lawsuit", "cuts guidance", "downgrade"),
    ),
    "consumer": Theme(
        key="consumer",
        label="Consumer / Retail",
        etf="XLY",
        tickers=("AMZN", "WMT", "COST", "TGT", "HD", "NKE", "SBUX", "MCD", "DIS", "TSLA"),
        match_keywords=("consumer", "retail sales", "spending", "holiday sales", "wages", "tariffs", "inflation"),
        positive_keywords=("retail sales rise", "strong demand", "consumer spending", "upgrade", "margin expansion", "earnings beat"),
        negative_keywords=("weak demand", "recession", "tariff", "inflation", "downgrade", "miss", "guidance cut"),
    ),
    "real_estate_reits": Theme(
        key="real_estate_reits",
        label="REITs / Real Estate",
        etf="XLRE",
        tickers=("PLD", "SPG", "O", "AMT", "EQIX", "DLR", "WELL", "PSA", "VICI"),
        match_keywords=("real estate", "reit", "property", "rent", "mortgage", "rates", "datacenter reit"),
        positive_keywords=("rate cut", "lower yields", "occupancy", "rent growth", "upgrade", "data center demand"),
        negative_keywords=("higher rates", "vacancy", "default", "downgrade", "office weakness", "refinancing risk"),
    ),
}

# Temel izleme listesi: her taramada yer alır
CORE_WATCHLIST = (
    "AAPL", "MSFT", "NVDA", "AVGO", "AMD", "GOOGL", "AMZN", "META", "TSLA", "PLTR",
    "VRT", "ANET", "ETN", "DELL", "SMCI", "CRWD", "PANW", "JPM", "XOM", "LLY",
)

# Şirket entity eşleştirme: haber başlığı şirketi doğrudan içerirse ticker'a ekstra skor verir
COMPANY_ALIASES: Dict[str, Tuple[str, ...]] = {
    "NVDA": ("nvidia", "nvda"),
    "AMD": ("advanced micro devices", "amd"),
    "AVGO": ("broadcom", "avgo"),
    "TSM": ("taiwan semiconductor", "tsmc", "tsm"),
    "ASML": ("asml",),
    "AMAT": ("applied materials", "amat"),
    "LRCX": ("lam research", "lrcx"),
    "KLAC": ("kla", "klac"),
    "MU": ("micron", "mu"),
    "MRVL": ("marvell", "mrvl"),
    "ARM": ("arm holdings", "arm"),
    "ANET": ("arista", "anet"),
    "VRT": ("vertiv", "vrt"),
    "ETN": ("eaton", "etn"),
    "DELL": ("dell", "dell technologies"),
    "SMCI": ("super micro", "supermicro", "smci"),
    "MSFT": ("microsoft", "msft", "azure"),
    "GOOGL": ("alphabet", "google", "googl", "gemini"),
    "AMZN": ("amazon", "aws", "amzn"),
    "META": ("meta", "facebook"),
    "AAPL": ("apple", "aapl"),
    "ORCL": ("oracle", "orcl"),
    "CRWD": ("crowdstrike", "crwd"),
    "PANW": ("palo alto", "palo alto networks", "panw"),
    "FTNT": ("fortinet", "ftnt"),
    "ZS": ("zscaler", "zs"),
    "NET": ("cloudflare", "net"),
    "DDOG": ("datadog", "ddog"),
    "LMT": ("lockheed", "lockheed martin", "lmt"),
    "RTX": ("rtx", "raytheon"),
    "NOC": ("northrop", "northrop grumman", "noc"),
    "GD": ("general dynamics", "gd"),
    "BA": ("boeing", "ba"),
    "PLTR": ("palantir", "pltr"),
    "XOM": ("exxon", "exxon mobil", "xom"),
    "CVX": ("chevron", "cvx"),
    "COP": ("conocophillips", "cop"),
    "CCJ": ("cameco", "ccj"),
    "CEG": ("constellation energy", "ceg"),
    "COIN": ("coinbase", "coin"),
    "MSTR": ("microstrategy", "strategy", "mstr"),
    "MARA": ("marathon digital", "mara"),
    "RIOT": ("riot platforms", "riot"),
    "LLY": ("eli lilly", "lilly", "lly"),
    "NVO": ("novo nordisk", "nvo", "wegovy", "ozempic"),
    "ISRG": ("intuitive surgical", "isrg"),
    "TSLA": ("tesla", "tsla", "optimus"),
}

# Bazı haberler genel olarak sektörler için ters yönde etkili olabilir
GLOBAL_MACRO_RULES = [
    {
        "name": "rate_cut_growth_positive",
        "triggers": ("rate cut", "dovish", "lower rates", "easing", "yields fall"),
        "theme_impacts": {"software_cloud": 0.7, "ai_infra": 0.5, "real_estate_reits": 0.9, "consumer": 0.3, "fintech_banks": -0.3},
    },
    {
        "name": "hot_inflation_growth_negative",
        "triggers": ("hot inflation", "higher inflation", "rate hike", "hawkish", "yields rise", "tightening"),
        "theme_impacts": {"software_cloud": -0.6, "ai_infra": -0.4, "real_estate_reits": -0.8, "consumer": -0.4, "fintech_banks": 0.3},
    },
    {
        "name": "geopolitical_risk",
        "triggers": ("war", "missile", "sanctions", "conflict", "attack", "nato", "middle east"),
        "theme_impacts": {"defense": 0.9, "energy_oil_gas": 0.5, "cybersecurity": 0.3, "consumer": -0.2},
    },
    {
        "name": "recession_risk",
        "triggers": ("recession", "layoffs", "weak demand", "slowdown", "consumer confidence falls"),
        "theme_impacts": {"consumer": -0.8, "fintech_banks": -0.5, "software_cloud": -0.3, "energy_oil_gas": -0.4, "defense": 0.2},
    },
]


# =============================================================================
# YARDIMCI FONKSİYONLAR
# =============================================================================

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def safe_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if x is None:
            return default
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9%+\-\. ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def contains_any(text_norm: str, keywords: Sequence[str]) -> bool:
    return any(normalize(k) in text_norm for k in keywords)


def count_hits(text_norm: str, keywords: Sequence[str]) -> int:
    return sum(1 for k in keywords if normalize(k) in text_norm)


def parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    value = value.strip()
    # RSS pubDate
    try:
        dt = email.utils.parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    # GDELT seendate: 20260528T123000Z, bazen 20260528123000
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    # ISO fallback
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def age_seconds(date_value: str) -> float:
    dt = parse_date(date_value)
    if dt is None:
        return float("inf")
    return max(0.0, (now_utc() - dt).total_seconds())


def recency_weight(seconds: float) -> float:
    if not math.isfinite(seconds):
        return 0.0
    return float(math.exp(-NEWS_DECAY_LAMBDA * seconds))


def short(text: str, n: int = 90) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 3] + "..."


def unique_preserve(seq: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for x in seq:
        x = x.upper().strip()
        if x and x not in seen:
            out.append(x)
            seen.add(x)
    return out


# =============================================================================
# HABER MODELİ
# =============================================================================

@dataclass
class NewsItem:
    title: str
    summary: str = ""
    url: str = ""
    published: str = ""
    source: str = ""
    category: str = ""

    @property
    def text(self) -> str:
        return f"{self.title} {self.summary} {self.source}"

    @property
    def key(self) -> str:
        return self.url or self.title


class NewsCollector:
    def __init__(self, source: str = "both", hours: int = DEFAULT_HOURS):
        self.source = source
        self.hours = hours
        try:
            import requests
            self.requests = requests
            self.s = requests.Session()
            self.s.headers.update({"User-Agent": "free-news-stock-scanner/2.0"})
        except Exception:
            self.requests = None
            self.s = None

    def rss_items(self) -> List[NewsItem]:
        if self.s is None:
            return []
        items: List[NewsItem] = []
        for category, urls in RSS_FEEDS.items():
            for url in urls:
                try:
                    r = self.s.get(url, timeout=12)
                    r.raise_for_status()
                    items.extend(self._parse_rss(r.text, category))
                except Exception:
                    continue
        return items

    @staticmethod
    def _parse_rss(xml_text: str, category: str) -> List[NewsItem]:
        out: List[NewsItem] = []
        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return out
        for node in root.iter():
            tag = node.tag.split("}")[-1].lower()
            if tag not in ("item", "entry"):
                continue
            title = summary = link = pub = source = ""
            for ch in node:
                ct = ch.tag.split("}")[-1].lower()
                if ct == "title":
                    title = ch.text or ""
                elif ct in ("description", "summary", "content"):
                    summary = ch.text or summary
                elif ct == "link":
                    link = ch.get("href") or ch.text or link
                elif ct in ("pubdate", "published", "updated") and not pub:
                    pub = ch.text or ""
                elif ct == "source":
                    source = ch.text or ""
            if title:
                out.append(NewsItem(title=title, summary=summary, url=link, published=pub, source=source, category=category))
        return out

    def gdelt_items(self) -> List[NewsItem]:
        if self.s is None:
            return []
        out: List[NewsItem] = []
        seen = set()
        for q in GDELT_QUERIES:
            params = {
                "query": q,
                "mode": "ArtList",
                "format": "json",
                "maxrecords": "50",
                "sort": "HybridRel",
            }
            try:
                r = self.s.get(GDELT_ENDPOINT, params=params, timeout=15)
                r.raise_for_status()
                data = r.json()
                for art in data.get("articles", []) or []:
                    title = art.get("title") or ""
                    url = art.get("url") or ""
                    if not title or (url and url in seen):
                        continue
                    if url:
                        seen.add(url)
                    out.append(
                        NewsItem(
                            title=title,
                            summary=art.get("seendate", ""),
                            url=url,
                            published=art.get("seendate", ""),
                            source=art.get("sourceCountry") or art.get("domain") or "GDELT",
                            category="gdelt",
                        )
                    )
            except Exception:
                continue
        return out

    def collect(self) -> List[NewsItem]:
        raw: List[NewsItem] = []
        if self.source in ("rss", "both"):
            raw.extend(self.rss_items())
        if self.source in ("gdelt", "both"):
            raw.extend(self.gdelt_items())

        max_age = self.hours * 3600
        filtered: List[NewsItem] = []
        seen = set()
        for item in raw:
            key = item.key
            if key in seen:
                continue
            seen.add(key)
            if age_seconds(item.published) <= max_age:
                filtered.append(item)
        return filtered


# =============================================================================
# HABER ETKİ MOTORU
# =============================================================================

@dataclass
class Trigger:
    title: str
    url: str
    score: float
    source: str
    theme: str = ""
    ticker: str = ""


@dataclass
class NewsImpact:
    theme_scores: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    ticker_scores: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    theme_triggers: Dict[str, List[Trigger]] = field(default_factory=lambda: defaultdict(list))
    ticker_triggers: Dict[str, List[Trigger]] = field(default_factory=lambda: defaultdict(list))
    negative_tickers: Dict[str, float] = field(default_factory=lambda: defaultdict(float))


class ImpactEngine:
    def score(self, news: Sequence[NewsItem]) -> NewsImpact:
        impact = NewsImpact()
        for item in news:
            text_norm = normalize(item.text)
            age = age_seconds(item.published)
            w_time = recency_weight(age)
            if w_time <= 0:
                continue

            # Tema bazlı scoring
            for key, theme in THEMES.items():
                if not contains_any(text_norm, theme.match_keywords):
                    continue

                pos = count_hits(text_norm, theme.positive_keywords)
                neg = count_hits(text_norm, theme.negative_keywords)

                # Yön yoksa, tema eşleşmesini hafif pozitif değil nötre yakın alıyoruz
                raw = 0.25 + 0.65 * pos - 0.75 * neg
                if pos == 0 and neg == 0:
                    raw = 0.15
                score = raw * w_time
                if abs(score) < 0.05:
                    continue

                impact.theme_scores[key] += score
                impact.theme_triggers[key].append(Trigger(title=item.title, url=item.url, source=item.source, score=score, theme=key))

                # Tema skoru tickers'a dağıtılır, ama düşük ağırlıkla
                for t in theme.tickers:
                    impact.ticker_scores[t] += score * 0.35
                    if score < 0:
                        impact.negative_tickers[t] += abs(score) * 0.35

            # Makro/global rules
            for rule in GLOBAL_MACRO_RULES:
                if not contains_any(text_norm, rule["triggers"]):
                    continue
                for theme_key, theme_impact in rule["theme_impacts"].items():
                    score = float(theme_impact) * w_time
                    impact.theme_scores[theme_key] += score
                    impact.theme_triggers[theme_key].append(Trigger(title=item.title, url=item.url, source=item.source, score=score, theme=theme_key))
                    for t in THEMES[theme_key].tickers:
                        impact.ticker_scores[t] += score * 0.25
                        if score < 0:
                            impact.negative_tickers[t] += abs(score) * 0.25

            # Direkt şirket/entity hit
            for ticker, aliases in COMPANY_ALIASES.items():
                if not contains_any(text_norm, aliases):
                    continue
                # Alias varsa haberde direkt şirket etkisi daha güçlüdür.
                # Pozitif/negatif yönü genel kelime setiyle belirlenir.
                positive_words = (
                    "beat", "beats", "raised guidance", "upgrade", "surge", "record", "contract", "partnership",
                    "approval", "strong demand", "orders", "buyback", "investment", "expansion", "wins"
                )
                negative_words = (
                    "miss", "misses", "cut guidance", "cuts guidance", "downgrade", "investigation", "lawsuit",
                    "ban", "restriction", "recall", "delay", "weak demand", "falls", "plunges", "outage"
                )
                pos = count_hits(text_norm, positive_words)
                neg = count_hits(text_norm, negative_words)
                if pos == 0 and neg == 0:
                    direct = 0.25 * w_time
                else:
                    direct = (0.85 * pos - 0.95 * neg) * w_time
                impact.ticker_scores[ticker] += direct
                if direct < 0:
                    impact.negative_tickers[ticker] += abs(direct)
                impact.ticker_triggers[ticker].append(Trigger(title=item.title, url=item.url, source=item.source, score=direct, ticker=ticker))

        return impact


# =============================================================================
# HİSSE EVRENİ
# =============================================================================

def universe_from_themes(mode: str = "full", custom: Optional[str] = None) -> List[str]:
    tickers: List[str] = []
    if mode == "core":
        tickers.extend(CORE_WATCHLIST)
    elif mode == "full":
        tickers.extend(CORE_WATCHLIST)
        for theme in THEMES.values():
            tickers.extend(theme.tickers)
    elif mode == "custom":
        tickers.extend((custom or "").replace(" ", "").split(","))
    else:
        tickers.extend(CORE_WATCHLIST)
    return unique_preserve(tickers)


def themes_for_ticker(ticker: str) -> List[str]:
    return [k for k, theme in THEMES.items() if ticker.upper() in theme.tickers]


def main_theme_for_ticker(ticker: str) -> str:
    keys = themes_for_ticker(ticker)
    if not keys:
        return "general"
    # En yüksek odaklı temayı ilk döndürür
    return keys[0]


# =============================================================================
# FİYAT / TEMEL VERİ
# =============================================================================

class MarketData:
    def __init__(self, demo: bool = False):
        self.demo = demo
        self._history_cache: Dict[str, pd.DataFrame] = {}
        self._info_cache: Dict[str, Dict[str, Any]] = {}
        if not demo:
            try:
                import yfinance as yf
                self.yf = yf
            except Exception as e:
                raise RuntimeError(
                    "yfinance kurulu değil. Kurulum: pip install yfinance pandas numpy requests\n"
                    "Veya test için: --demo\n"
                    f"Detay: {e}"
                )
        else:
            self.yf = None

    def history(self, ticker: str) -> Optional[pd.DataFrame]:
        ticker = ticker.upper()
        if ticker in self._history_cache:
            return self._history_cache[ticker]
        if self.demo:
            df = self._demo_history(ticker)
        else:
            try:
                df = self.yf.Ticker(ticker).history(period=PRICE_PERIOD, auto_adjust=True)
            except Exception:
                df = None
        if df is not None and len(df) >= MIN_PRICE_ROWS:
            self._history_cache[ticker] = df.copy()
            return df.copy()
        return None

    def info(self, ticker: str) -> Dict[str, Any]:
        ticker = ticker.upper()
        if ticker in self._info_cache:
            return self._info_cache[ticker]
        if self.demo:
            info = self._demo_info(ticker)
        else:
            try:
                info = dict(self.yf.Ticker(ticker).info or {})
            except Exception:
                info = {}
        self._info_cache[ticker] = info
        return info

    @staticmethod
    def _demo_history(ticker: str) -> pd.DataFrame:
        rng = np.random.default_rng(abs(hash(ticker)) % (2**32))
        n = 260
        drift = rng.normal(0.00035, 0.00025)
        vol = rng.uniform(0.012, 0.030)
        ret = rng.normal(drift, vol, n)
        close = 100 * np.exp(np.cumsum(ret))
        high = close * (1 + rng.uniform(0.001, 0.025, n))
        low = close * (1 - rng.uniform(0.001, 0.025, n))
        open_ = close * (1 + rng.normal(0, 0.006, n))
        volume = rng.integers(500_000, 20_000_000, n)
        idx = pd.date_range(end=datetime.now(), periods=n, freq="B")
        return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=idx)

    @staticmethod
    def _demo_info(ticker: str) -> Dict[str, Any]:
        rng = np.random.default_rng((abs(hash(ticker)) + 777) % (2**32))
        return {
            "shortName": f"{ticker} Demo Corp",
            "sector": random.choice(["Technology", "Industrials", "Energy", "Healthcare", "Financial Services"]),
            "marketCap": int(rng.uniform(2e9, 2e12)),
            "averageVolume": int(rng.uniform(500_000, 30_000_000)),
            "trailingPE": float(rng.uniform(8, 70)),
            "forwardPE": float(rng.uniform(8, 50)),
            "priceToBook": float(rng.uniform(0.7, 15)),
            "pegRatio": float(rng.uniform(0.5, 4.0)),
            "priceToSalesTrailing12Months": float(rng.uniform(0.7, 25)),
            "returnOnEquity": float(rng.uniform(-0.05, 0.45)),
            "grossMargins": float(rng.uniform(0.15, 0.85)),
            "operatingMargins": float(rng.uniform(-0.05, 0.40)),
            "profitMargins": float(rng.uniform(-0.10, 0.35)),
            "revenueGrowth": float(rng.uniform(-0.15, 0.45)),
            "debtToEquity": float(rng.uniform(0, 250)),
            "beta": float(rng.uniform(0.5, 2.5)),
            "freeCashflow": float(rng.uniform(-1e9, 20e9)),
            "totalRevenue": float(rng.uniform(1e9, 250e9)),
        }


# =============================================================================
# ANALİZ / SKORLAMA
# =============================================================================

def rsi(close: pd.Series, period: int = 14) -> Optional[float]:
    delta = close.diff()
    up = delta.clip(lower=0).rolling(period).mean()
    down = (-delta.clip(upper=0)).rolling(period).mean()
    rs = up / down.replace(0, np.nan)
    val = 100 - 100 / (1 + rs)
    x = safe_float(val.iloc[-1])
    return x


def technicals(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    close = df["Close"].astype(float)
    price = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else price
    vol = df["Volume"].astype(float) if "Volume" in df else pd.Series([np.nan] * len(df))
    avg_vol20 = safe_float(vol.rolling(20).mean().iloc[-1], None)
    volume_ratio = safe_float(vol.iloc[-1] / avg_vol20, None) if avg_vol20 and avg_vol20 > 0 else None

    sma20 = safe_float(close.rolling(20).mean().iloc[-1])
    sma50 = safe_float(close.rolling(50).mean().iloc[-1])
    sma200 = safe_float(close.rolling(200).mean().iloc[-1])

    high52 = safe_float(close.rolling(min(len(close), 252)).max().iloc[-1])
    low52 = safe_float(close.rolling(min(len(close), 252)).min().iloc[-1])
    band = ((price - low52) / (high52 - low52)) if high52 and low52 and high52 > low52 else None

    ret1 = price / prev - 1 if prev else None
    ret5 = price / float(close.iloc[-6]) - 1 if len(close) >= 6 else None
    ret20 = price / float(close.iloc[-21]) - 1 if len(close) >= 21 else None
    ret63 = price / float(close.iloc[-64]) - 1 if len(close) >= 64 else None

    return {
        "price": price,
        "ret1": ret1,
        "ret5": ret5,
        "ret20": ret20,
        "ret63": ret63,
        "rsi": rsi(close),
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "high52": high52,
        "low52": low52,
        "band52": band,
        "volume_ratio": volume_ratio,
    }


def sector_momentum_score(theme_key: str, data: MarketData) -> float:
    theme = THEMES.get(theme_key)
    if not theme or not theme.etf:
        return 0.50
    df = data.history(theme.etf)
    if df is None:
        return 0.50
    t = technicals(df)
    ret5 = t.get("ret5") or 0.0
    ret20 = t.get("ret20") or 0.0
    price = t.get("price")
    sma50 = t.get("sma50")
    trend_bonus = 0.08 if price and sma50 and price > sma50 else -0.05
    return clamp(0.50 + ret5 * 3.2 + ret20 * 1.4 + trend_bonus)


def catalyst_score(ticker: str, impact: NewsImpact) -> float:
    theme_keys = themes_for_ticker(ticker)
    sector_component = sum(impact.theme_scores.get(k, 0.0) * 0.65 for k in theme_keys)
    direct_component = impact.ticker_scores.get(ticker, 0.0)
    raw = sector_component + direct_component
    return clamp(0.48 + 0.16 * raw)


def value_score(info: Dict[str, Any], theme_key: str) -> float:
    forward_pe = safe_float(info.get("forwardPE"))
    trailing_pe = safe_float(info.get("trailingPE"))
    peg = safe_float(info.get("pegRatio") or info.get("trailingPegRatio"))
    ps = safe_float(info.get("priceToSalesTrailing12Months"))
    pb = safe_float(info.get("priceToBook"))

    pe = forward_pe or trailing_pe
    parts: List[float] = []

    # Growth/AI hisselerinde P/E doğal olarak yüksek olabilir; değerleme tamamen cezalandırılmasın
    growth_theme = theme_key in {"ai_infra", "semiconductor", "software_cloud", "cybersecurity", "robotics_physical_ai"}
    pe_cut = 45 if growth_theme else 25
    ps_cut = 18 if growth_theme else 8

    if pe and pe > 0:
        parts.append(clamp((pe_cut - pe) / pe_cut))
    if peg and peg > 0:
        parts.append(clamp((2.2 - peg) / 2.2))
    if ps and ps > 0:
        parts.append(clamp((ps_cut - ps) / ps_cut))
    if pb and pb > 0 and not growth_theme:
        parts.append(clamp((4.5 - pb) / 4.5))

    return mean(parts) if parts else 0.45


def quality_score(info: Dict[str, Any]) -> float:
    parts: List[float] = []
    roe = safe_float(info.get("returnOnEquity"))
    gross = safe_float(info.get("grossMargins"))
    opm = safe_float(info.get("operatingMargins"))
    pm = safe_float(info.get("profitMargins"))
    growth = safe_float(info.get("revenueGrowth"))
    debt = safe_float(info.get("debtToEquity"))
    fcf = safe_float(info.get("freeCashflow"))
    revenue = safe_float(info.get("totalRevenue"))

    if roe is not None:
        parts.append(clamp(roe / 0.28))
    if gross is not None:
        parts.append(clamp(gross / 0.55))
    if opm is not None:
        parts.append(clamp((opm + 0.05) / 0.35))
    elif pm is not None:
        parts.append(clamp((pm + 0.05) / 0.30))
    if growth is not None:
        parts.append(clamp((growth + 0.05) / 0.35))
    if debt is not None:
        parts.append(clamp((180 - debt) / 180))
    if fcf is not None and revenue and revenue > 0:
        parts.append(clamp((fcf / revenue + 0.03) / 0.18))

    return mean(parts) if parts else 0.45


def technical_score(t: Dict[str, Optional[float]]) -> float:
    parts: List[float] = []
    price = t.get("price")
    sma20 = t.get("sma20")
    sma50 = t.get("sma50")
    sma200 = t.get("sma200")
    r = t.get("rsi")
    band = t.get("band52")
    ret5 = t.get("ret5") or 0.0
    ret20 = t.get("ret20") or 0.0
    volr = t.get("volume_ratio")

    if price and sma20:
        parts.append(0.62 if price > sma20 else 0.42)
    if price and sma50:
        parts.append(0.70 if price > sma50 else 0.38)
    if price and sma200:
        parts.append(0.78 if price > sma200 else 0.32)
    if r is not None:
        # En iyi bölge: 42-63; aşırı alım/çöküş cezalı
        if 42 <= r <= 63:
            parts.append(0.78)
        elif 35 <= r < 42 or 63 < r <= 70:
            parts.append(0.60)
        elif r < 35:
            parts.append(0.48)  # ucuz olabilir ama momentum kırık olabilir
        else:
            parts.append(0.35)
    if band is not None:
        # 52w bandının %35-80 arası genelde iyi risk/ödül; zirvede FOMO cezası
        if 0.35 <= band <= 0.80:
            parts.append(0.75)
        elif band < 0.35:
            parts.append(0.55)
        else:
            parts.append(0.45)
    if ret5 is not None and ret20 is not None:
        mom = 0.50 + ret5 * 3.0 + ret20 * 1.2
        parts.append(clamp(mom))
    if volr is not None:
        parts.append(clamp(0.45 + min(volr, 3.0) * 0.15))

    return mean(parts) if parts else 0.50


def risk_score(info: Dict[str, Any], t: Dict[str, Optional[float]]) -> float:
    parts: List[float] = []
    mcap = safe_float(info.get("marketCap"))
    avg_vol = safe_float(info.get("averageVolume") or info.get("averageDailyVolume10Day"))
    beta = safe_float(info.get("beta"))
    price = t.get("price")

    if mcap is not None:
        # Büyük ve likit şirketlere daha yüksek skor
        parts.append(clamp(math.log10(max(mcap, 1)) / 12.0))
    if avg_vol is not None:
        parts.append(clamp(math.log10(max(avg_vol, 1)) / 8.0))
    if beta is not None:
        parts.append(clamp(1.0 - max(0.0, beta - 1.2) / 1.8))
    if price is not None:
        parts.append(0.75 if price >= MIN_PRICE else 0.20)
    return mean(parts) if parts else 0.50


def passes_basic_filters(info: Dict[str, Any], t: Dict[str, Optional[float]]) -> Tuple[bool, str]:
    mcap = safe_float(info.get("marketCap"), 0.0) or 0.0
    avg_vol = safe_float(info.get("averageVolume") or info.get("averageDailyVolume10Day"), 0.0) or 0.0
    price = t.get("price") or 0.0
    if price < MIN_PRICE:
        return False, f"price<{MIN_PRICE}"
    if mcap and mcap < MIN_MARKET_CAP:
        return False, "small_mcap"
    if avg_vol and avg_vol < MIN_AVG_VOLUME:
        return False, "low_volume"
    return True, ""


def top_triggers(triggers: Sequence[Trigger], n: int = 2) -> str:
    if not triggers:
        return ""
    sorted_t = sorted(triggers, key=lambda x: abs(x.score), reverse=True)[:n]
    return " || ".join(short(t.title, 95) for t in sorted_t)


def build_reason(row: Dict[str, Any]) -> str:
    chunks = []
    if row.get("news"):
        chunks.append(f"Katalizör: {row['news']}")
    chunks.append(f"Teknik: RSI {row.get('rsi','-')}, 20g {row.get('ret20_pct','-')}%")
    if row.get("forwardPE") not in (None, ""):
        chunks.append(f"Fwd P/E {row['forwardPE']}")
    elif row.get("trailingPE") not in (None, ""):
        chunks.append(f"P/E {row['trailingPE']}")
    if row.get("revenueGrowth") not in (None, ""):
        chunks.append(f"Gelir büy. {row['revenueGrowth']}%")
    if row.get("band52_pct") not in (None, ""):
        chunks.append(f"52h band {row['band52_pct']}%")
    return " | ".join(str(x) for x in chunks if x)


# =============================================================================
# TARAYICI
# =============================================================================

def make_demo_news() -> List[NewsItem]:
    ts = email.utils.format_datetime(now_utc())
    samples = [
        NewsItem("AI chip demand accelerates as hyperscalers raise datacenter capex", published=ts, source="DEMO", category="technology"),
        NewsItem("NATO members boost defense spending after new missile attacks", published=ts, source="DEMO", category="geopolitics"),
        NewsItem("Fed signals possible rate cut as inflation cools", published=ts, source="DEMO", category="macro"),
        NewsItem("Cyberattack wave drives new cybersecurity mandates for public companies", published=ts, source="DEMO", category="cyber"),
        NewsItem("Oil prices rise after OPEC supply cut and Middle East disruption", published=ts, source="DEMO", category="energy"),
    ]
    return samples


def scan(
    demo: bool = False,
    source: str = "both",
    hours: int = DEFAULT_HOURS,
    universe_mode: str = "full",
    custom_tickers: Optional[str] = None,
    min_score: float = 0.0,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], NewsImpact, List[NewsItem]]:
    if demo:
        news = make_demo_news()
    else:
        collector = NewsCollector(source=source, hours=hours)
        news = collector.collect()

    engine = ImpactEngine()
    impact = engine.score(news)

    base_universe = universe_from_themes(universe_mode, custom_tickers)

    # Haber skoru alan ama evrende olmayan ticker'ları da ekle
    event_tickers = [t for t, s in impact.ticker_scores.items() if abs(s) > 0.05]
    tickers = unique_preserve(list(base_universe) + event_tickers)

    data = MarketData(demo=demo)
    sector_cache: Dict[str, float] = {}

    rows: List[Dict[str, Any]] = []
    risks: List[Dict[str, Any]] = []

    for i, ticker in enumerate(tickers, 1):
        df = data.history(ticker)
        if df is None:
            continue
        info = data.info(ticker)
        t = technicals(df)
        ok, filter_reason = passes_basic_filters(info, t)
        if not ok:
            # Çok küçük/likitsizleri rapora almıyoruz
            continue

        theme_key = main_theme_for_ticker(ticker)
        if theme_key not in sector_cache:
            sector_cache[theme_key] = sector_momentum_score(theme_key, data)
        sec_score = sector_cache[theme_key]

        cat = catalyst_score(ticker, impact)
        val = value_score(info, theme_key)
        qual = quality_score(info)
        tech = technical_score(t)
        risk = risk_score(info, t)

        total = 100.0 * (
            WEIGHTS["catalyst"] * cat
            + WEIGHTS["sector_momentum"] * sec_score
            + WEIGHTS["technical"] * tech
            + WEIGHTS["quality"] * qual
            + WEIGHTS["value"] * val
            + WEIGHTS["risk"] * risk
        )

        direct_trig = impact.ticker_triggers.get(ticker, [])
        theme_trig: List[Trigger] = []
        for k in themes_for_ticker(ticker):
            theme_trig.extend(impact.theme_triggers.get(k, []))
        news_txt = top_triggers(direct_trig + theme_trig, n=2)

        price = t.get("price")
        row = {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "theme": THEMES.get(theme_key).label if theme_key in THEMES else "General",
            "theme_key": theme_key,
            "sector": info.get("sector") or "-",
            "price": round(price, 2) if price is not None else "",
            "score": round(total, 1),
            "catalyst": round(cat * 100),
            "sector_momentum": round(sec_score * 100),
            "technical": round(tech * 100),
            "quality": round(qual * 100),
            "value": round(val * 100),
            "risk": round(risk * 100),
            "ret1_pct": round((t.get("ret1") or 0) * 100, 2),
            "ret5_pct": round((t.get("ret5") or 0) * 100, 2),
            "ret20_pct": round((t.get("ret20") or 0) * 100, 2),
            "rsi": round(t.get("rsi"), 1) if t.get("rsi") is not None else "",
            "band52_pct": round((t.get("band52") or 0) * 100, 1) if t.get("band52") is not None else "",
            "volume_ratio": round(t.get("volume_ratio"), 2) if t.get("volume_ratio") is not None else "",
            "marketCap_B": round((safe_float(info.get("marketCap"), 0.0) or 0.0) / 1e9, 1),
            "forwardPE": round(safe_float(info.get("forwardPE"), np.nan), 1) if safe_float(info.get("forwardPE")) is not None else "",
            "trailingPE": round(safe_float(info.get("trailingPE"), np.nan), 1) if safe_float(info.get("trailingPE")) is not None else "",
            "ps": round(safe_float(info.get("priceToSalesTrailing12Months"), np.nan), 1) if safe_float(info.get("priceToSalesTrailing12Months")) is not None else "",
            "revenueGrowth": round((safe_float(info.get("revenueGrowth"), 0.0) or 0.0) * 100, 1) if safe_float(info.get("revenueGrowth")) is not None else "",
            "news_score_raw": round(impact.ticker_scores.get(ticker, 0.0), 2),
            "negative_news_raw": round(impact.negative_tickers.get(ticker, 0.0), 2),
            "news": news_txt,
        }
        row["reason"] = build_reason(row)

        if total >= min_score:
            rows.append(row)

        if impact.negative_tickers.get(ticker, 0.0) > 0.25:
            risk_row = row.copy()
            risk_row["risk_alert_score"] = round(impact.negative_tickers.get(ticker, 0.0), 2)
            risks.append(risk_row)

        if not demo:
            time.sleep(TICKER_SLEEP_SECONDS)

    rows.sort(key=lambda r: (-r["score"], -r["catalyst"], -r["technical"]))
    risks.sort(key=lambda r: (-r.get("risk_alert_score", 0), r["score"]))
    return rows, risks, impact, news


# =============================================================================
# RAPORLAMA
# =============================================================================

def write_csv(rows: List[Dict[str, Any]], path: str = OUTPUT_CSV) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def print_console(rows: List[Dict[str, Any]], risks: List[Dict[str, Any]], top_n: int = TOP_N) -> None:
    print("\n" + "=" * 124)
    print(f"{'#':>2} {'TICKER':<7} {'THEME':<28} {'PRICE':>8} {'SCORE':>7} {'CAT':>5} {'SEC':>5} {'TECH':>6} {'QUAL':>6} {'VAL':>5}  REASON")
    print("-" * 124)
    for i, r in enumerate(rows[:top_n], 1):
        print(
            f"{i:>2} {r['ticker']:<7} {short(r['theme'], 28):<28} {str(r['price']):>8} "
            f"{r['score']:>7.1f} {r['catalyst']:>5} {r['sector_momentum']:>5} {r['technical']:>6} "
            f"{r['quality']:>6} {r['value']:>5}  {short(r['reason'], 52)}"
        )
    print("=" * 124)

    if risks:
        print("\n⚠️  NEGATİF HABER / RİSK RADARI")
        print("-" * 100)
        for i, r in enumerate(risks[:10], 1):
            print(f"{i:>2} {r['ticker']:<7} risk={r['risk_alert_score']:<5} score={r['score']:<5} {short(r['news'], 80)}")
        print("-" * 100)


def write_html(rows: List[Dict[str, Any]], risks: List[Dict[str, Any]], impact: NewsImpact, news: List[NewsItem], top_n: int = TOP_N, path: str = OUTPUT_HTML) -> None:
    def score_color(score: float) -> str:
        if score >= 75:
            return "#16a34a"
        if score >= 65:
            return "#65a30d"
        if score >= 55:
            return "#ca8a04"
        return "#dc2626"

    opp_rows = ""
    for i, r in enumerate(rows[:top_n], 1):
        color = score_color(float(r["score"]))
        opp_rows += f"""
        <tr>
          <td>{i}</td>
          <td><b>{html.escape(str(r['ticker']))}</b><br><span class="dim">{html.escape(short(str(r['name']), 28))}</span></td>
          <td>{html.escape(short(str(r['theme']), 24))}</td>
          <td>{r['price']}</td>
          <td style="color:{color};font-weight:800">{r['score']}</td>
          <td>{r['catalyst']}</td><td>{r['sector_momentum']}</td><td>{r['technical']}</td>
          <td>{r['quality']}</td><td>{r['value']}</td><td>{r['risk']}</td>
          <td class="reason">{html.escape(short(str(r['reason']), 220))}</td>
        </tr>"""

    risk_rows = ""
    for i, r in enumerate(risks[:10], 1):
        risk_rows += f"""
        <tr>
          <td>{i}</td><td><b>{html.escape(str(r['ticker']))}</b></td>
          <td>{r.get('risk_alert_score','')}</td><td>{r['score']}</td>
          <td class="reason">{html.escape(short(str(r['news']), 220))}</td>
        </tr>"""

    theme_rows = ""
    for theme_key, score in sorted(impact.theme_scores.items(), key=lambda kv: -abs(kv[1]))[:20]:
        label = THEMES.get(theme_key).label if theme_key in THEMES else theme_key
        trig = top_triggers(impact.theme_triggers.get(theme_key, []), 1)
        theme_rows += f"""
        <tr><td>{html.escape(label)}</td><td>{score:+.2f}</td><td class="reason">{html.escape(short(trig, 180))}</td></tr>"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    doc = f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Global Haber → Hisse Fırsat Raporu v2.0</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background:#0b0f17;color:#e5e7eb;margin:0;padding:24px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin-top:26px;color:#f8fafc}}
.dim{{color:#94a3b8;font-size:12px}} .warn{{background:#1f2937;border-left:4px solid #f59e0b;padding:12px 14px;border-radius:8px;margin:14px 0;font-size:13px}}
table{{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px}} th,td{{padding:8px 10px;border-bottom:1px solid #1f2937;text-align:center;vertical-align:top}}
th{{font-size:11px;text-transform:uppercase;color:#94a3b8}} tr:hover{{background:#111827}} .reason{{text-align:left;color:#cbd5e1;line-height:1.35}}
.badge{{display:inline-block;background:#111827;border:1px solid #334155;border-radius:999px;padding:4px 8px;margin-right:6px;color:#cbd5e1;font-size:12px}}
</style></head><body>
<h1>Global Haber → Sektör → Hisse Fırsat Raporu v2.0</h1>
<div class="dim">Oluşturma: {now} · Haber: {len(news)} · Aday: {len(rows)} · Gösterilen: {min(top_n, len(rows))}</div>
<div class="warn">⚠️ Ücretsiz RSS/GDELT/yfinance kaynakları kullanılır. Gerçek zamanlı terminal değildir. Yatırım tavsiyesi değildir; araştırma başlangıç noktasıdır.</div>
<div><span class="badge">Catalyst</span><span class="badge">Sector Momentum</span><span class="badge">Technical</span><span class="badge">Quality</span><span class="badge">Value</span><span class="badge">Risk/Liquidity</span></div>

<h2>En Yüksek Skorlu Fırsat Adayları</h2>
<table><tr><th>#</th><th>Hisse</th><th>Tema</th><th>Fiyat</th><th>Skor</th><th>Kat</th><th>Sektör</th><th>Teknik</th><th>Kalite</th><th>Değer</th><th>Risk</th><th>Gerekçe</th></tr>
{opp_rows}
</table>

<h2>Negatif Haber / Risk Radarı</h2>
<table><tr><th>#</th><th>Hisse</th><th>Risk Haber Skoru</th><th>Toplam Skor</th><th>Tetikleyici Haber</th></tr>
{risk_rows or '<tr><td colspan="5" class="dim">Belirgin negatif haber riski bulunmadı.</td></tr>'}
</table>

<h2>Tema Bazlı Haber Skorları</h2>
<table><tr><th>Tema</th><th>Haber Skoru</th><th>Örnek Tetikleyici</th></tr>
{theme_rows}
</table>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Global haber -> sektör -> hisse fırsat tarayıcı v2.0 / free stack")
    parser.add_argument("--demo", action="store_true", help="İnternetsiz demo haber ve sentetik fiyat/veriyle çalıştır.")
    parser.add_argument("--source", choices=["rss", "gdelt", "both"], default="both", help="Haber kaynağı. Varsayılan: both")
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS, help="Kaç saat içindeki haberler dikkate alınsın? Varsayılan: 8")
    parser.add_argument("--universe", choices=["core", "full", "custom"], default="full", help="Hisse evreni. core daha hızlı, full daha geniş.")
    parser.add_argument("--tickers", default="", help="--universe custom için virgüllü ticker listesi: NVDA,AMD,VRT")
    parser.add_argument("--top", type=int, default=TOP_N, help="Raporda kaç aday gösterilsin?")
    parser.add_argument("--min-score", type=float, default=0.0, help="Minimum toplam skor filtresi.")
    args = parser.parse_args()

    print("=" * 80)
    print(f"  {APP_NAME}")
    print(f"  Mode: {'DEMO' if args.demo else 'LIVE FREE'} | Source: {args.source} | Universe: {args.universe}")
    print("  Not: Yatırım tavsiyesi değildir; ücretsiz kaynaklarla araştırma asistanıdır.")
    print("=" * 80)

    try:
        rows, risks, impact, news = scan(
            demo=args.demo,
            source=args.source,
            hours=args.hours,
            universe_mode=args.universe,
            custom_tickers=args.tickers,
            min_score=args.min_score,
        )
    except Exception as e:
        print(f"\nHata: {e}")
        return

    if not rows:
        print("Sonuç üretilemedi. --demo ile test edebilir veya --universe core deneyebilirsin.")
        return

    print(f"\nToplanan haber: {len(news)}")
    print("Öne çıkan tema skorları:")
    for k, v in sorted(impact.theme_scores.items(), key=lambda kv: -abs(kv[1]))[:10]:
        label = THEMES[k].label if k in THEMES else k
        print(f"  {label:<34} {v:+.2f}")

    print_console(rows, risks, top_n=args.top)
    write_csv(rows, OUTPUT_CSV)
    write_html(rows, risks, impact, news, top_n=args.top, path=OUTPUT_HTML)

    print(f"\nCSV : {OUTPUT_CSV}")
    print(f"HTML: {OUTPUT_HTML}")
    print("\nÇalıştırma önerisi: python news_stock_scanner_v2.py --source both --hours 8 --universe full --top 20")


if __name__ == "__main__":
    main()

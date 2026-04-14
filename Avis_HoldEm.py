from __future__ import annotations

import itertools
import math
import random
from collections import Counter
from textwrap import dedent
from typing import Final

import streamlit as st

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Texas Hold'em",
    page_icon="🂡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================================================
# CONSTANTS
# =========================================================
SUITS: Final[tuple[str, ...]] = ("♠", "♥", "♦", "♣")
RANKS: Final[tuple[str, ...]] = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
RED_SUITS: Final[set[str]] = {"♥", "♦"}
RANK_VALUE: Final[dict[str, int]] = {rank: i for i, rank in enumerate(RANKS, start=2)}

STARTING_STACK: Final[int] = 2000
SMALL_BLIND: Final[int] = 10
BIG_BLIND: Final[int] = 20
DEFAULT_RAISE: Final[int] = 40
MAX_SEATS: Final[int] = 8
MIN_SEATS: Final[int] = 2
LOG_LIMIT: Final[int] = 24
MIN_DECK_REFRESH: Final[int] = 20

NPC_NAME_POOL: Final[tuple[str, ...]] = (
    "Coach Kev",
    "Tej",
    "Caleb",
    "Ryan",
    "Chris",
    "Cousin Alex",
    "Avinash",
    "George",
)

NPC_STYLE_POOL: Final[tuple[str, ...]] = (
    "tight",
    "balanced",
    "loose",
    "aggressive",
    "balanced",
    "balanced",
    "loose",
    "aggressive",
)

HAND_NAMES: Final[dict[int, str]] = {
    8: "Straight Flush",
    7: "Four of a Kind",
    6: "Full House",
    5: "Flush",
    4: "Straight",
    3: "Three of a Kind",
    2: "Two Pair",
    1: "One Pair",
    0: "High Card",
}

CHIP_DENOMS: Final[tuple[tuple[float, str, int, str], ...]] = (
    (1000.0, "1000", 2000, "platinum"),
    (500.0, "500", 1000, "orange"),
    (100.0, "100", 200, "black"),
    (50.0, "50", 100, "green"),
    (25.0, "25", 50, "purple"),
    (10.0, "10", 20, "blue"),
    (5.0, "5", 10, "red"),
    (1.0, "1", 2, "white"),
)

Card = dict[str, str]
Seat = dict[str, object]

# =========================================================
# UTILITIES
# =========================================================
def html(s: str) -> str:
    return dedent(s).strip()


def join_html(*parts: str) -> str:
    return "".join(part for part in parts if part)


def money(amount: int | float) -> str:
    value = float(amount)
    return f"${value:,.0f}" if value.is_integer() else f"${value:,.2f}"


def safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def make_card(rank: str, suit: str) -> Card:
    return {"rank": rank, "suit": suit}


def normalize_card(raw: object) -> Card | None:
    if isinstance(raw, dict):
        rank = raw.get("rank")
        suit = raw.get("suit")
        if isinstance(rank, str) and isinstance(suit, str) and rank in RANKS and suit in SUITS:
            return make_card(rank, suit)

    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        rank, suit = raw[0], raw[1]
        if isinstance(rank, str) and isinstance(suit, str) and rank in RANKS and suit in SUITS:
            return make_card(rank, suit)

    if isinstance(raw, str):
        raw = raw.strip()
        if len(raw) >= 2 and raw[-1] in SUITS:
            rank = raw[:-1]
            suit = raw[-1]
            if rank in RANKS:
                return make_card(rank, suit)

    return None


def normalize_cards(raw: object) -> list[Card]:
    if not isinstance(raw, (list, tuple)):
        return []
    cards: list[Card] = []
    for item in raw:
        card = normalize_card(item)
        if card is not None:
            cards.append(card)
    return cards


def card_key(card: Card) -> tuple[str, str]:
    return card["rank"], card["suit"]


def fresh_deck(exclude: list[Card] | None = None) -> list[Card]:
    excluded = {card_key(card) for card in (exclude or [])}
    deck = [
        make_card(rank, suit)
        for suit in SUITS
        for rank in RANKS
        if (rank, suit) not in excluded
    ]
    random.shuffle(deck)
    return deck


def suit_color(suit: str) -> str:
    return "red" if suit in RED_SUITS else "black"


def card_center(rank: str, suit: str) -> str:
    if rank == "A":
        return suit
    if rank in {"J", "Q", "K"}:
        return rank
    return suit


def push_log(text: str) -> None:
    log = list(st.session_state.action_log)
    log.insert(0, text)
    st.session_state.action_log = log[:LOG_LIMIT]


def set_status(message: str, kind: str = "info") -> None:
    st.session_state.message = message
    st.session_state.message_type = kind


def funded_seat_indices() -> list[int]:
    return [i for i, seat in enumerate(st.session_state.seats) if safe_int(seat["stack"], 0) > 0]


def tournament_chip_total() -> int:
    seat_stacks = sum(max(0, safe_int(seat.get("stack", 0), 0)) for seat in st.session_state.seats)
    street_bets = sum(max(0, safe_int(seat.get("street_bet", 0), 0)) for seat in st.session_state.seats)
    pot = max(0, safe_int(st.session_state.get("pot", 0), 0))
    return seat_stacks + street_bets + pot


def tournament_champion_index() -> int | None:
    funded = funded_seat_indices()
    if len(funded) != 1:
        return None
    return funded[0]


# =========================================================
# STYLES
# =========================================================
def inject_styles() -> None:
    st.markdown(
        html(
            """
            <style>
            html, body, [data-testid="stAppViewContainer"], .stApp {
                background: #07120d;
            }

            header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {
                display: none !important;
            }

            [data-testid="stAppViewContainer"] > .main {
                background:
                    radial-gradient(circle at top, rgba(36, 102, 75, 0.20) 0%, rgba(7, 18, 13, 0) 38%),
                    linear-gradient(180deg, #07120d 0%, #091711 100%);
            }

            .block-container {
                max-width: 1560px;
                padding-top: 0.45rem;
                padding-bottom: 0.8rem;
                padding-left: 0.8rem;
                padding-right: 0.8rem;
            }

            div[data-testid="stVerticalBlock"] {
                gap: 0.55rem;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] {
                background: linear-gradient(180deg, rgba(12, 26, 21, 0.96) 0%, rgba(10, 22, 18, 0.96) 100%);
                border: 1px solid rgba(197, 164, 92, 0.14) !important;
                border-radius: 20px;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
                padding: 0.1rem 0.2rem;
            }

            .shell {
                background: linear-gradient(180deg, rgba(10, 23, 18, 0.96) 0%, rgba(8, 19, 15, 0.96) 100%);
                border: 1px solid rgba(197, 164, 92, 0.18);
                border-radius: 24px;
                padding: 0.7rem;
                box-shadow:
                    0 20px 60px rgba(0, 0, 0, 0.35),
                    inset 0 1px 0 rgba(255, 255, 255, 0.04);
            }

            .hero-eyebrow {
                font-size: 0.72rem;
                font-weight: 800;
                letter-spacing: 0.14em;
                text-transform: uppercase;
                color: #d2b46c;
                margin-bottom: 0.15rem;
            }

            .hero-title {
                font-size: 2rem;
                font-weight: 900;
                line-height: 0.95;
                letter-spacing: -0.03em;
                color: #f5efd8;
                margin-bottom: 0.18rem;
            }

            .hero-subtitle {
                color: #9fb3a6;
                font-size: 0.92rem;
                margin-bottom: 0.4rem;
            }

            .panel-title {
                color: #f5efd8;
                font-size: 1rem;
                font-weight: 850;
                margin-bottom: 0.12rem;
            }

            .panel-subtitle {
                color: #8ea397;
                font-size: 0.84rem;
                margin-bottom: 0.55rem;
            }

            .metric-grid {
                display: grid;
                grid-template-columns: repeat(7, minmax(0, 1fr));
                gap: 0.55rem;
            }

            .metric-card {
                background: linear-gradient(180deg, rgba(16, 34, 27, 0.96) 0%, rgba(12, 28, 22, 0.96) 100%);
                border: 1px solid rgba(197, 164, 92, 0.16);
                border-radius: 18px;
                padding: 0.7rem 0.85rem;
                min-height: 78px;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
            }

            .metric-label {
                color: #8da395;
                font-size: 0.74rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-weight: 700;
                margin-bottom: 0.22rem;
            }

            .metric-value {
                color: #f8f2df;
                font-size: 1.06rem;
                font-weight: 900;
                line-height: 1.05;
            }

            .status {
                border-radius: 16px;
                padding: 0.72rem 0.82rem;
                font-size: 0.92rem;
                font-weight: 700;
                border: 1px solid transparent;
            }

            .status.info {
                background: rgba(33, 85, 70, 0.22);
                color: #d7f3e7;
                border-color: rgba(71, 156, 126, 0.28);
            }

            .status.success {
                background: rgba(34, 92, 44, 0.24);
                color: #dcf8d8;
                border-color: rgba(93, 186, 109, 0.28);
            }

            .status.warning {
                background: rgba(126, 93, 25, 0.22);
                color: #ffefbf;
                border-color: rgba(214, 175, 77, 0.26);
            }

            .status.error {
                background: rgba(109, 34, 34, 0.24);
                color: #ffd7d7;
                border-color: rgba(196, 86, 86, 0.26);
            }

            .tiny-meta {
                color: #7f9789;
                font-size: 0.78rem;
                margin-top: 0.45rem;
                line-height: 1.35;
            }

            .action-log {
                display: flex;
                flex-direction: column;
                gap: 0.45rem;
            }

            .log-item {
                background: rgba(255,255,255,0.045);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
                padding: 0.55rem 0.62rem;
                color: #d7e2db;
                font-size: 0.82rem;
                line-height: 1.25;
            }

            .chip-board {
                display: flex;
                flex-direction: column;
                gap: 0.45rem;
                margin-top: 0.5rem;
            }

            .chip-card {
                background: rgba(255,255,255,0.035);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                padding: 0.55rem 0.65rem 0.6rem 0.65rem;
            }

            .chip-card-top {
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                gap: 0.75rem;
                margin-bottom: 0.35rem;
            }

            .chip-card-title {
                color: #dbe5df;
                font-size: 0.8rem;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }

            .chip-card-value {
                color: #f8f2df;
                font-size: 0.95rem;
                font-weight: 900;
            }

            .chip-card-subtitle {
                color: #80998a;
                font-size: 0.75rem;
                margin-bottom: 0.3rem;
            }

            .chip-towers {
                display: flex;
                align-items: flex-end;
                gap: 0.42rem;
                min-height: 74px;
                flex-wrap: nowrap;
                overflow: hidden;
            }

            .chip-tower {
                display: flex;
                flex-direction: column-reverse;
                align-items: center;
                min-width: 38px;
            }

            .chip {
                width: 38px;
                height: 38px;
                border-radius: 50%;
                margin-top: -16px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 0.64rem;
                font-weight: 900;
                letter-spacing: -0.02em;
                box-shadow:
                    0 5px 12px rgba(0,0,0,0.22),
                    inset 0 1px 0 rgba(255,255,255,0.38);
                border: 3px dashed rgba(255,255,255,0.58);
            }

            .chip.black {
                background: radial-gradient(circle at 30% 25%, #606060 0%, #1f1f1f 58%, #0e0e0e 100%);
                color: #f8f8f8;
            }

            .chip.green {
                background: radial-gradient(circle at 30% 25%, #43b274 0%, #16804a 58%, #0f5c36 100%);
                color: #f7fff9;
            }

            .chip.purple {
                background: radial-gradient(circle at 30% 25%, #a574ff 0%, #7240d5 58%, #5426a9 100%);
                color: #fcf8ff;
            }

            .chip.blue {
                background: radial-gradient(circle at 30% 25%, #59a8ff 0%, #2d74d9 58%, #1e57a8 100%);
                color: #f8fbff;
            }

            .chip.red {
                background: radial-gradient(circle at 30% 25%, #ff8078 0%, #cf4944 58%, #9d312d 100%);
                color: #fff9f8;
            }

            .chip.white {
                background: radial-gradient(circle at 30% 25%, #ffffff 0%, #ece7db 58%, #c7beaf 100%);
                color: #131313;
                border-color: rgba(40,40,40,0.38);
            }

            .chip.orange {
                background: radial-gradient(circle at 30% 25%, #ffbe72 0%, #f08e28 58%, #b75d08 100%);
                color: #fff8f1;
            }

            .chip.platinum {
                background: radial-gradient(circle at 30% 25%, #edf8ff 0%, #b5d2e2 58%, #6f8ea1 100%);
                color: #10202a;
                border-color: rgba(255,255,255,0.76);
            }

            .chip-count {
                color: #90a79a;
                font-size: 0.7rem;
                font-weight: 800;
                margin-top: 0.18rem;
            }

            .pill {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: 999px;
                padding: 0.28rem 0.58rem;
                font-size: 0.72rem;
                font-weight: 900;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                white-space: nowrap;
                background: rgba(255,255,255,0.12);
                color: #f3ead4;
            }

            .pill.live {
                background: rgba(231, 198, 112, 0.24);
                color: #fff1c5;
            }

            .pill.win {
                background: rgba(34, 92, 44, 0.24);
                color: #dcf8d8;
            }

            .pill.loss {
                background: rgba(109, 34, 34, 0.24);
                color: #ffd7d7;
            }

            .card {
                width: 82px;
                min-width: 82px;
                height: 116px;
                border-radius: 14px;
                position: relative;
                overflow: hidden;
                padding: 0.45rem;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                box-shadow:
                    0 8px 18px rgba(0, 0, 0, 0.22),
                    inset 0 1px 0 rgba(255,255,255,0.92);
            }

            .card.face {
                background: linear-gradient(180deg, #fffdf8 0%, #f5f0e5 100%);
                border: 1px solid #d9ccbb;
            }

            .card.back {
                background:
                    radial-gradient(circle at center, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0) 55%),
                    repeating-linear-gradient(
                        45deg,
                        #d2b46c 0px,
                        #d2b46c 8px,
                        #b78e47 8px,
                        #b78e47 16px
                    );
                border: 1px solid #caa55c;
                justify-content: center;
                align-items: center;
                color: rgba(255,255,255,0.96);
                font-size: 1.45rem;
                font-weight: 900;
                text-shadow: 0 1px 3px rgba(0,0,0,0.25);
            }

            .card.empty {
                background: rgba(255,255,255,0.07);
                border: 1px dashed rgba(255,255,255,0.26);
                justify-content: center;
                align-items: center;
                color: rgba(255,255,255,0.56);
                font-size: 0.76rem;
                font-weight: 700;
            }

            .card.red { color: #b73b3b; }
            .card.black { color: #171717; }

            .card-top, .card-bottom {
                display: flex;
                flex-direction: column;
                line-height: 0.92;
            }

            .card-bottom {
                align-items: flex-end;
                transform: rotate(180deg);
            }

            .card-rank {
                font-size: 0.95rem;
                font-weight: 900;
            }

            .card-suit {
                font-size: 0.82rem;
                margin-top: 1px;
            }

            .card-center {
                flex: 1;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 2rem;
                font-weight: 900;
                line-height: 1;
            }

            .cards-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.42rem;
                min-height: 118px;
                align-items: flex-start;
                justify-content: center;
            }

            .round-table-wrap {
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0) 28%),
                    linear-gradient(180deg, #14553f 0%, #0f4634 100%);
                border: 1px solid rgba(197, 164, 92, 0.20);
                border-radius: 24px;
                padding: 0.8rem;
                box-shadow:
                    inset 0 1px 0 rgba(255,255,255,0.08),
                    inset 0 -16px 50px rgba(0,0,0,0.14);
                min-height: 940px;
                position: relative;
            }

            .table-title {
                color: #f9f4e3;
                font-size: 1.05rem;
                font-weight: 850;
                margin-bottom: 0.12rem;
            }

            .table-subtitle {
                color: rgba(249, 244, 227, 0.74);
                font-size: 0.82rem;
                margin-bottom: 0.65rem;
            }

            .round-table-shell {
                position: relative;
                width: 100%;
                height: 820px;
                border-radius: 50%;
                background:
                    radial-gradient(circle at center, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.01) 45%, rgba(0,0,0,0.10) 100%),
                    linear-gradient(180deg, #14553f 0%, #0f4634 100%);
                border: 3px solid rgba(210, 180, 108, 0.55);
                box-shadow:
                    inset 0 8px 40px rgba(0,0,0,0.18),
                    0 18px 60px rgba(0,0,0,0.20);
                overflow: hidden;
            }

            .round-table-center {
                position: absolute;
                left: 50%;
                top: 50%;
                width: 54%;
                transform: translate(-50%, -50%);
                text-align: center;
            }

            .street-chip {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: 999px;
                padding: 0.35rem 0.7rem;
                background: rgba(231, 198, 112, 0.24);
                color: #fff1c5;
                font-size: 0.78rem;
                font-weight: 900;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 0.45rem;
            }

            .center-pot {
                color: #f9f4e3;
                font-size: 1.36rem;
                font-weight: 900;
                margin-bottom: 0.12rem;
            }

            .center-bet {
                color: rgba(249, 244, 227, 0.78);
                font-size: 0.9rem;
                font-weight: 700;
                margin-bottom: 0.6rem;
            }

            .board-row .card {
                width: 78px;
                min-width: 78px;
                height: 110px;
            }

            .seat-node {
                position: absolute;
                width: 252px;
                background: rgba(9, 21, 17, 0.88);
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 18px;
                padding: 0.55rem 0.6rem 0.6rem 0.6rem;
                box-shadow: 0 14px 28px rgba(0,0,0,0.26);
                backdrop-filter: blur(3px);
            }

            .seat-head {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 0.5rem;
                margin-bottom: 0.18rem;
            }

            .seat-name {
                color: #f7f1dc;
                font-size: 0.94rem;
                font-weight: 900;
            }

            .seat-meta {
                color: #b9cabf;
                font-size: 0.74rem;
                font-weight: 700;
                margin-bottom: 0.1rem;
            }

            .seat-submeta {
                color: #8ea397;
                margin-bottom: 0.35rem;
                min-height: 1rem;
            }

            .seat-node .cards-row {
                justify-content: center;
                min-height: 0;
                gap: 0.32rem;
            }

            .seat-node .card {
                width: 50px;
                min-width: 50px;
                height: 74px;
                border-radius: 10px;
                padding: 0.22rem;
            }

            .seat-node .card-rank {
                font-size: 0.66rem;
            }

            .seat-node .card-suit {
                font-size: 0.56rem;
            }

            .seat-node .card-center {
                font-size: 1.15rem;
            }

            .seat-node .card.back {
                font-size: 1rem;
            }

            .seat-chips {
                display: flex;
                justify-content: center;
                align-items: flex-end;
                gap: 0.2rem;
                min-height: 44px;
                margin-top: 0.25rem;
            }

            .seat-chips .chip-tower {
                min-width: 20px;
            }

            .seat-chips .chip {
                width: 20px;
                height: 20px;
                margin-top: -8px;
                font-size: 0.42rem;
                border-width: 2px;
            }

            .seat-chips .chip-count {
                font-size: 0.52rem;
                margin-top: 0.08rem;
            }

            .seat-chip-empty {
                color: rgba(255,255,255,0.40);
                font-size: 0.72rem;
                font-weight: 800;
            }

            div.stButton > button {
                width: 100%;
                min-height: 2.35rem;
                border-radius: 999px;
                border: 1px solid rgba(197, 164, 92, 0.18);
                background: linear-gradient(180deg, #162b23 0%, #12241d 100%);
                color: #f7f1dc;
                font-weight: 800;
                box-shadow: 0 6px 16px rgba(0,0,0,0.16);
            }

            div.stButton > button:hover {
                border-color: rgba(218, 184, 106, 0.38);
                color: #fff8e5;
            }

            div.stButton > button[kind="primary"] {
                background: linear-gradient(180deg, #dfc079 0%, #caa04c 100%);
                color: #1d1508;
                border: 1px solid rgba(221, 189, 113, 0.70);
            }

            div[data-testid="stNumberInput"] input {
                background: #f8f4e8 !important;
                color: #1a1712 !important;
                border-radius: 12px !important;
                font-weight: 800 !important;
            }

            label[data-testid="stWidgetLabel"] p {
                color: #dbe5df !important;
                font-weight: 700 !important;
            }

            @media (max-width: 1300px) {
                .metric-grid {
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                }
            }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


# =========================================================
# CHIP HTML
# =========================================================
def chip_breakdown(amount: float) -> list[tuple[str, str, int]]:
    remaining_units = int(round(max(0.0, amount) * 2))
    parts: list[tuple[str, str, int]] = []
    for _, label, units, chip_class in CHIP_DENOMS:
        count = remaining_units // units
        remaining_units %= units
        if count > 0:
            parts.append((chip_class, label, count))
    return parts


def chip_tower_html(chip_class: str, label: str, count: int) -> str:
    visible = min(count, 6)
    chips = "".join(f'<div class="chip {chip_class}"><span>{label}</span></div>' for _ in range(visible))
    return html(
        f"""
        <div class="chip-tower">
            {chips}
            <div class="chip-count">×{count}</div>
        </div>
        """
    )


def mini_chip_stack_html(amount: int) -> str:
    towers = chip_breakdown(float(amount))
    if not towers:
        return "<div class='seat-chip-empty'>—</div>"
    return "".join(chip_tower_html(chip_class, label, min(count, 3)) for chip_class, label, count in towers[:3])


def chip_card_html(title: str, amount: float, subtitle: str) -> str:
    towers = chip_breakdown(amount)
    towers_html = "".join(
        chip_tower_html(chip_class, label, count)
        for chip_class, label, count in towers
    ) if towers else ""

    return join_html(
        '<div class="chip-card">',
        '<div class="chip-card-top">',
        f'<div class="chip-card-title">{title}</div>',
        f'<div class="chip-card-value">{money(amount)}</div>',
        "</div>",
        f'<div class="chip-card-subtitle">{subtitle}</div>',
        f'<div class="chip-towers">{towers_html}</div>',
        "</div>",
    )


# =========================================================
# CARD HTML
# =========================================================
def face_card_html(card: Card) -> str:
    rank = card["rank"]
    suit = card["suit"]
    color = suit_color(suit)
    return html(
        f"""
        <div class="card face {color}">
            <div class="card-top">
                <div class="card-rank">{rank}</div>
                <div class="card-suit">{suit}</div>
            </div>
            <div class="card-center">{card_center(rank, suit)}</div>
            <div class="card-bottom">
                <div class="card-rank">{rank}</div>
                <div class="card-suit">{suit}</div>
            </div>
        </div>
        """
    )


def back_card_html() -> str:
    return '<div class="card back">♠</div>'


def cards_row_html(cards: list[Card], reveal: bool) -> str:
    if not cards:
        return "<div class='cards-row'></div>"
    items: list[str] = []
    for card in cards:
        items.append(face_card_html(card) if reveal else back_card_html())
    return f"<div class='cards-row'>{''.join(items)}</div>"


def board_cards_html(cards: list[Card]) -> str:
    items: list[str] = []
    for i in range(5):
        if i < len(cards):
            items.append(face_card_html(cards[i]))
        else:
            items.append('<div class="card empty">WAIT</div>')
    return f"<div class='cards-row board-row'>{''.join(items)}</div>"


# =========================================================
# HAND EVALUATION
# =========================================================
def is_straight(values: list[int]) -> tuple[bool, int | None]:
    uniq = sorted(set(values), reverse=True)
    if len(uniq) < 5:
        return False, None
    for i in range(len(uniq) - 4):
        window = uniq[i:i + 5]
        if window[0] - window[4] == 4:
            return True, window[0]
    if {14, 5, 4, 3, 2}.issubset(set(values)):
        return True, 5
    return False, None


def evaluate_5(cards: list[Card]) -> tuple:
    values = sorted([RANK_VALUE[c["rank"]] for c in cards], reverse=True)
    suits = [c["suit"] for c in cards]
    counts = Counter(values)

    flush = len(set(suits)) == 1
    straight, straight_high = is_straight(values)

    if straight and flush:
        return (8, straight_high)

    if 4 in counts.values():
        four = max(v for v, c in counts.items() if c == 4)
        kicker = max(v for v, c in counts.items() if c == 1)
        return (7, four, kicker)

    if sorted(counts.values()) == [2, 3]:
        trips = max(v for v, c in counts.items() if c == 3)
        pair = max(v for v, c in counts.items() if c == 2)
        return (6, trips, pair)

    if flush:
        return (5, *values)

    if straight:
        return (4, straight_high)

    if 3 in counts.values():
        trips = max(v for v, c in counts.items() if c == 3)
        kickers = sorted((v for v, c in counts.items() if c == 1), reverse=True)
        return (3, trips, *kickers)

    pairs = sorted((v for v, c in counts.items() if c == 2), reverse=True)
    if len(pairs) == 2:
        kicker = max(v for v, c in counts.items() if c == 1)
        return (2, pairs[0], pairs[1], kicker)

    if len(pairs) == 1:
        pair = pairs[0]
        kickers = sorted((v for v, c in counts.items() if c == 1), reverse=True)
        return (1, pair, *kickers)

    return (0, *values)


def best_hand_7(cards: list[Card]) -> tuple:
    return max(evaluate_5(list(combo)) for combo in itertools.combinations(cards, 5))


def hand_name(rank_tuple: tuple) -> str:
    return HAND_NAMES[safe_int(rank_tuple[0], 0)]


# =========================================================
# SEATS
# =========================================================
def make_seat(name: str, is_human: bool, style: str = "balanced") -> Seat:
    return {
        "name": name,
        "is_human": is_human,
        "style": style,
        "stack": STARTING_STACK,
        "cards": [],
        "in_hand": True,
        "folded": False,
        "all_in": False,
        "street_bet": 0,
        "total_bet": 0,
        "acted": False,
        "last_action": "",
        "result": "",
        "best_hand_name": "",
    }


def default_seats(player_count: int) -> list[Seat]:
    seats: list[Seat] = [make_seat("You", True, "human")]
    for i in range(player_count - 1):
        seats.append(make_seat(NPC_NAME_POOL[i % len(NPC_NAME_POOL)], False, NPC_STYLE_POOL[i % len(NPC_STYLE_POOL)]))
    return seats


def normalize_seat(raw: object) -> Seat | None:
    if not isinstance(raw, dict):
        return None
    return {
        "name": str(raw.get("name", "Seat")),
        "is_human": bool(raw.get("is_human", False)),
        "style": str(raw.get("style", "balanced")),
        "stack": max(0, safe_int(raw.get("stack", STARTING_STACK), STARTING_STACK)),
        "cards": normalize_cards(raw.get("cards", [])),
        "in_hand": bool(raw.get("in_hand", True)),
        "folded": bool(raw.get("folded", False)),
        "all_in": bool(raw.get("all_in", False)),
        "street_bet": max(0, safe_int(raw.get("street_bet", 0), 0)),
        "total_bet": max(0, safe_int(raw.get("total_bet", 0), 0)),
        "acted": bool(raw.get("acted", False)),
        "last_action": str(raw.get("last_action", "")),
        "result": str(raw.get("result", "")),
        "best_hand_name": str(raw.get("best_hand_name", "")),
    }


def player_index() -> int:
    for i, seat in enumerate(st.session_state.seats):
        if bool(seat["is_human"]):
            return i
    return 0


def live_seat_indices() -> list[int]:
    return [
        i for i, seat in enumerate(st.session_state.seats)
        if bool(seat["in_hand"]) and not bool(seat["folded"])
    ]


def seat_can_act(index: int) -> bool:
    seat = st.session_state.seats[index]
    return bool(seat["in_hand"]) and not bool(seat["folded"]) and not bool(seat["all_in"])


def next_active_index(start_idx: int) -> int:
    total = len(st.session_state.seats)
    for offset in range(1, total + 1):
        idx = (start_idx + offset) % total
        if seat_can_act(idx):
            return idx
    return start_idx


def draw_card() -> Card:
    if not st.session_state.deck:
        exclude = list(st.session_state.community_cards)
        for seat in st.session_state.seats:
            exclude.extend(normalize_cards(seat["cards"]))
        st.session_state.deck = fresh_deck(exclude=exclude)
    card = st.session_state.deck[-1]
    st.session_state.deck = st.session_state.deck[:-1]
    return card


def seats_needing_action() -> list[int]:
    need: list[int] = []
    for i, seat in enumerate(st.session_state.seats):
        if not seat_can_act(i):
            continue
        if not bool(seat["acted"]):
            need.append(i)
            continue
        if safe_int(seat["street_bet"], 0) != safe_int(st.session_state.current_bet, 0):
            need.append(i)
    return need


# =========================================================
# STATE
# =========================================================
def default_state() -> dict[str, object]:
    seats = default_seats(4)
    return {
        "seats": seats,
        "player_count": 4,
        "deck": fresh_deck(),
        "community_cards": [],
        "pot": 0,
        "street": "preflop",
        "phase": "setup",
        "message": "Choose seat count and deal a hand.",
        "message_type": "info",
        "hand_result": "",
        "action_log": [],
        "round_counter": 0,
        "dealer_button": 0,
        "small_blind_index": 1,
        "big_blind_index": 2,
        "current_bet": 0,
        "current_actor": 0,
        "raise_amount": DEFAULT_RAISE,
        "showdown_revealed": False,
    }


def ensure_state() -> None:
    defaults = default_state()
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    raw_seats = st.session_state.get("seats", [])
    seats: list[Seat] = []
    if isinstance(raw_seats, list):
        for item in raw_seats:
            seat = normalize_seat(item)
            if seat is not None:
                seats.append(seat)

    desired_count = min(MAX_SEATS, max(MIN_SEATS, safe_int(st.session_state.get("player_count", len(seats) or 4), 4)))
    if not seats:
        seats = default_seats(desired_count)

    if len(seats) != desired_count:
        old_player_stack = STARTING_STACK
        for seat in seats:
            if bool(seat["is_human"]):
                old_player_stack = safe_int(seat["stack"], STARTING_STACK)
                break
        seats = default_seats(desired_count)
        seats[0]["stack"] = old_player_stack

    st.session_state.player_count = desired_count
    st.session_state.seats = seats
    st.session_state.deck = normalize_cards(st.session_state.get("deck", []))
    st.session_state.community_cards = normalize_cards(st.session_state.get("community_cards", []))
    st.session_state.pot = max(0, safe_int(st.session_state.get("pot", 0), 0))
    st.session_state.street = str(st.session_state.get("street", "preflop"))
    st.session_state.phase = str(st.session_state.get("phase", "setup"))
    st.session_state.message = str(st.session_state.get("message", ""))
    st.session_state.message_type = str(st.session_state.get("message_type", "info"))
    st.session_state.hand_result = str(st.session_state.get("hand_result", ""))
    st.session_state.action_log = list(st.session_state.get("action_log", []))[:LOG_LIMIT]
    st.session_state.round_counter = max(0, safe_int(st.session_state.get("round_counter", 0), 0))
    st.session_state.dealer_button = safe_int(st.session_state.get("dealer_button", 0), 0) % len(st.session_state.seats)
    st.session_state.small_blind_index = safe_int(st.session_state.get("small_blind_index", 1), 1) % len(st.session_state.seats)
    st.session_state.big_blind_index = safe_int(st.session_state.get("big_blind_index", 2), 2) % len(st.session_state.seats)
    st.session_state.current_bet = max(0, safe_int(st.session_state.get("current_bet", 0), 0))
    st.session_state.current_actor = safe_int(st.session_state.get("current_actor", 0), 0) % len(st.session_state.seats)
    st.session_state.raise_amount = max(BIG_BLIND, safe_int(st.session_state.get("raise_amount", DEFAULT_RAISE), DEFAULT_RAISE))
    st.session_state.showdown_revealed = bool(st.session_state.get("showdown_revealed", False))

    in_play = list(st.session_state.community_cards)
    for seat in st.session_state.seats:
        in_play.extend(normalize_cards(seat["cards"]))
    in_play_keys = {card_key(card) for card in in_play}
    st.session_state.deck = [card for card in st.session_state.deck if card_key(card) not in in_play_keys]

    if not st.session_state.deck and not in_play:
        st.session_state.deck = fresh_deck()


# =========================================================
# ROUND FLOW
# =========================================================
def clear_for_new_hand() -> None:
    for seat in st.session_state.seats:
        seat["cards"] = []
        seat["in_hand"] = safe_int(seat["stack"], 0) > 0
        seat["folded"] = False
        seat["all_in"] = False
        seat["street_bet"] = 0
        seat["total_bet"] = 0
        seat["acted"] = False
        seat["last_action"] = ""
        seat["result"] = ""
        seat["best_hand_name"] = ""

    st.session_state.community_cards = []
    st.session_state.pot = 0
    st.session_state.street = "preflop"
    st.session_state.current_bet = 0
    st.session_state.hand_result = ""
    st.session_state.showdown_revealed = False


def reset_for_next_hand() -> None:
    clear_for_new_hand()
    st.session_state.phase = "setup"
    set_status("Ready for the next hand.", "info")


def reset_game() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def post_blind(index: int, amount: int, label: str) -> None:
    seat = st.session_state.seats[index]
    if not bool(seat["in_hand"]):
        return

    post = min(amount, safe_int(seat["stack"], 0))
    seat["stack"] = safe_int(seat["stack"], 0) - post
    seat["street_bet"] = safe_int(seat["street_bet"], 0) + post
    seat["total_bet"] = safe_int(seat["total_bet"], 0) + post
    st.session_state.pot += post

    if safe_int(seat["stack"], 0) == 0:
        seat["all_in"] = True

    seat["last_action"] = f"{label} {money(post)}"
    push_log(f"{seat['name']} posts {label.lower()} of {money(post)}.")


def deal_new_hand() -> None:
    ensure_state()
    clear_for_new_hand()

    funded = funded_seat_indices()
    if len(funded) < 2:
        set_status("Need at least two funded seats to deal a hand.", "warning")
        return

    if len(st.session_state.deck) < MIN_DECK_REFRESH:
        st.session_state.deck = fresh_deck()

    st.session_state.round_counter += 1
    st.session_state.dealer_button = next_active_index(st.session_state.dealer_button)

    if len(funded) == 2:
        st.session_state.small_blind_index = st.session_state.dealer_button
        st.session_state.big_blind_index = next_active_index(st.session_state.dealer_button)
    else:
        st.session_state.small_blind_index = next_active_index(st.session_state.dealer_button)
        st.session_state.big_blind_index = next_active_index(st.session_state.small_blind_index)

    post_blind(st.session_state.small_blind_index, SMALL_BLIND, "SB")
    post_blind(st.session_state.big_blind_index, BIG_BLIND, "BB")
    st.session_state.current_bet = BIG_BLIND

    for _ in range(2):
        for seat in st.session_state.seats:
            if bool(seat["in_hand"]):
                seat["cards"].append(draw_card())

    st.session_state.current_actor = next_active_index(st.session_state.big_blind_index)
    st.session_state.phase = "action"
    set_status("Cards are out. Your move.", "info")
    push_log(f"Hand #{st.session_state.round_counter} begins.")


def reset_street_state() -> None:
    for seat in st.session_state.seats:
        seat["street_bet"] = 0
        seat["acted"] = False
        seat["last_action"] = ""
    st.session_state.current_bet = 0


def showdown() -> None:
    live = live_seat_indices()
    rankings: list[tuple[int, tuple]] = []

    for idx in live:
        seat = st.session_state.seats[idx]
        rank = best_hand_7(normalize_cards(seat["cards"]) + list(st.session_state.community_cards))
        seat["best_hand_name"] = hand_name(rank)
        rankings.append((idx, rank))

    best_rank = max(rank for _, rank in rankings)
    winners = [idx for idx, rank in rankings if rank == best_rank]
    pot = safe_int(st.session_state.pot, 0)
    share, remainder = divmod(pot, len(winners))

    for seat in st.session_state.seats:
        seat["result"] = ""

    ordered_winners = sorted(winners)
    for offset, idx in enumerate(ordered_winners):
        odd_chip = 1 if offset < remainder else 0
        st.session_state.seats[idx]["stack"] = safe_int(st.session_state.seats[idx]["stack"], 0) + share + odd_chip
        st.session_state.seats[idx]["result"] = "WIN"

    for idx, _ in rankings:
        if idx not in winners:
            st.session_state.seats[idx]["result"] = "LOSS"

    winner_names = ", ".join(st.session_state.seats[idx]["name"] for idx in winners)
    best_name = hand_name(best_rank)
    st.session_state.hand_result = f"{winner_names} win with {best_name}."
    st.session_state.pot = 0
    st.session_state.phase = "settled"
    st.session_state.showdown_revealed = True

    if any(bool(st.session_state.seats[idx]["is_human"]) for idx in winners):
        set_status("Showdown shipped your way." if len(winners) == 1 else "You got a piece of the pot.", "success")
    else:
        set_status(f"{winner_names} take the showdown.", "error")

    push_log(f"Showdown: {winner_names} with {best_name}.")


def advance_street() -> None:
    if st.session_state.street == "preflop":
        st.session_state.community_cards.extend([draw_card(), draw_card(), draw_card()])
        st.session_state.street = "flop"
        push_log("Flop hits the felt.")
    elif st.session_state.street == "flop":
        st.session_state.community_cards.append(draw_card())
        st.session_state.street = "turn"
        push_log("Turn card dealt.")
    elif st.session_state.street == "turn":
        st.session_state.community_cards.append(draw_card())
        st.session_state.street = "river"
        push_log("River card dealt.")
    elif st.session_state.street == "river":
        showdown()
        return

    reset_street_state()
    st.session_state.current_actor = next_active_index(st.session_state.dealer_button)
    set_status(f"{st.session_state.street.title()} action live.", "info")


def maybe_finish_betting_round() -> bool:
    live = live_seat_indices()

    if len(live) == 0:
        st.session_state.pot = 0
        st.session_state.phase = "settled"
        st.session_state.showdown_revealed = True
        st.session_state.hand_result = "Hand ended."
        set_status("Hand ended.", "info")
        return True

    if len(live) == 1:
        idx = live[0]
        seat = st.session_state.seats[idx]
        seat["stack"] = safe_int(seat["stack"], 0) + st.session_state.pot
        seat["result"] = "WIN"
        st.session_state.hand_result = f"{seat['name']} wins the pot uncontested."
        st.session_state.pot = 0
        st.session_state.phase = "settled"
        st.session_state.showdown_revealed = True

        if bool(seat["is_human"]):
            set_status("Everybody folded. Pot is yours.", "success")
        else:
            set_status(f"{seat['name']} takes it uncontested.", "error")

        push_log(f"{seat['name']} wins uncontested.")
        return True

    if not seats_needing_action():
        advance_street()
        return True

    return False


# =========================================================
# ACTIONS
# =========================================================
def apply_bet(index: int, amount: int) -> int:
    seat = st.session_state.seats[index]
    commit = min(amount, safe_int(seat["stack"], 0))
    seat["stack"] = safe_int(seat["stack"], 0) - commit
    seat["street_bet"] = safe_int(seat["street_bet"], 0) + commit
    seat["total_bet"] = safe_int(seat["total_bet"], 0) + commit
    st.session_state.pot += commit
    if safe_int(seat["stack"], 0) == 0:
        seat["all_in"] = True
    return commit


def move_to_next_actor() -> None:
    if st.session_state.phase != "action":
        return
    if maybe_finish_betting_round():
        return
    st.session_state.current_actor = next_active_index(st.session_state.current_actor)


def player_to_call() -> int:
    seat = st.session_state.seats[player_index()]
    return max(0, safe_int(st.session_state.current_bet, 0) - safe_int(seat["street_bet"], 0))


def can_check() -> bool:
    return (
        st.session_state.phase == "action"
        and st.session_state.current_actor == player_index()
        and player_to_call() == 0
    )


def can_call() -> bool:
    return (
        st.session_state.phase == "action"
        and st.session_state.current_actor == player_index()
        and player_to_call() > 0
    )


def can_fold() -> bool:
    return st.session_state.phase == "action" and st.session_state.current_actor == player_index()


def can_raise() -> bool:
    if st.session_state.phase != "action" or st.session_state.current_actor != player_index():
        return False
    seat = st.session_state.seats[player_index()]
    return safe_int(seat["stack"], 0) > player_to_call()


def player_check() -> None:
    if not can_check():
        return
    seat = st.session_state.seats[player_index()]
    seat["acted"] = True
    seat["last_action"] = "Check"
    push_log("You check.")
    move_to_next_actor()
    run_npc_actions()

def effective_raise_amount() -> int:
    seat = st.session_state.seats[player_index()]
    remaining = max(0, safe_int(seat["stack"], 0))
    raw_value = safe_int(st.session_state.get("raise_amount", DEFAULT_RAISE), DEFAULT_RAISE)

    if remaining <= 0:
        return 0

    return min(max(BIG_BLIND, raw_value), remaining)
    
def player_call() -> None:
    if not can_call():
        return
    seat = st.session_state.seats[player_index()]
    commit = apply_bet(player_index(), player_to_call())
    seat["acted"] = True
    seat["last_action"] = f"Call {money(commit)}"
    push_log(f"You call {money(commit)}.")
    move_to_next_actor()
    run_npc_actions()


def player_raise() -> None:
    if not can_raise():
        return

    idx = player_index()
    seat = st.session_state.seats[idx]
    to_call = player_to_call()
    raise_size = effective_raise_amount()

    if raise_size <= 0:
        set_status("No chips available for that raise.", "warning")
        return

    apply_bet(idx, to_call + raise_size)

    st.session_state.current_bet = max(
        safe_int(st.session_state.current_bet, 0),
        safe_int(seat["street_bet"], 0),
    )

    for i, other in enumerate(st.session_state.seats):
        if i != idx and seat_can_act(i):
            other["acted"] = False

    seat["acted"] = True
    seat["last_action"] = f"Raise to {money(seat['street_bet'])}"
    push_log(f"You raise to {money(seat['street_bet'])}.")

    if maybe_finish_betting_round():
        return

    st.session_state.current_actor = next_active_index(idx)
    run_npc_actions()



def player_fold() -> None:
    if not can_fold():
        return

    idx = player_index()
    seat = st.session_state.seats[idx]
    seat["folded"] = True
    seat["acted"] = True
    seat["last_action"] = "Fold"
    push_log("You fold.")

    if maybe_finish_betting_round():
        return

    st.session_state.current_actor = next_active_index(idx)
    run_npc_actions()


# =========================================================
# NPC AI
# =========================================================
def preflop_strength(cards: list[Card]) -> int:
    if len(cards) != 2:
        return 0
    values = sorted([RANK_VALUE[c["rank"]] for c in cards], reverse=True)
    pair = values[0] == values[1]
    suited = cards[0]["suit"] == cards[1]["suit"]
    connected = abs(values[0] - values[1]) == 1

    score = 0
    if pair:
        score += 5
    if suited:
        score += 2
    if connected:
        score += 1
    if values[0] >= 14:
        score += 2
    if values[0] >= 13 and values[1] >= 10:
        score += 2
    return score


def npc_fold_decision(seat: Seat, to_call: int) -> bool:
    cards = normalize_cards(seat["cards"])
    board = normalize_cards(st.session_state.community_cards)
    score = preflop_strength(cards)

    if len(board) >= 3:
        best = best_hand_7(cards + board)
        score += safe_int(best[0], 0) * 2

    style = str(seat["style"])
    pressure = 0
    if to_call >= BIG_BLIND * 2:
        pressure += 2
    if to_call >= max(1, safe_int(seat["stack"], 0) // 3):
        pressure += 2
    if style == "tight":
        pressure += 1
    if style == "loose":
        pressure -= 1

    return pressure > score + random.randint(0, 2)


def npc_raise_decision(seat: Seat, to_call: int) -> int:
    cards = normalize_cards(seat["cards"])
    board = normalize_cards(st.session_state.community_cards)
    style = str(seat["style"])
    score = preflop_strength(cards)

    if len(board) >= 3:
        best = best_hand_7(cards + board)
        score += safe_int(best[0], 0) * 2

    if style == "aggressive" and score >= 4 and safe_int(seat["stack"], 0) > to_call + BIG_BLIND:
        return min(safe_int(seat["stack"], 0), BIG_BLIND * random.choice([2, 3]))
    if style == "balanced" and score >= 6 and safe_int(seat["stack"], 0) > to_call + BIG_BLIND:
        return min(safe_int(seat["stack"], 0), BIG_BLIND * 2)
    return 0


def run_npc_actions() -> None:
    while st.session_state.phase == "action" and st.session_state.current_actor != player_index():
        idx = st.session_state.current_actor
        seat = st.session_state.seats[idx]

        if not seat_can_act(idx):
            move_to_next_actor()
            continue

        to_call = max(0, safe_int(st.session_state.current_bet, 0) - safe_int(seat["street_bet"], 0))

        if to_call > 0 and npc_fold_decision(seat, to_call):
            seat["folded"] = True
            seat["acted"] = True
            seat["last_action"] = "Fold"
            push_log(f"{seat['name']} folds.")
            if maybe_finish_betting_round():
                break
            st.session_state.current_actor = next_active_index(idx)
            continue

        raise_amt = npc_raise_decision(seat, to_call)
        if raise_amt > 0:
            apply_bet(idx, to_call + raise_amt)
            st.session_state.current_bet = max(st.session_state.current_bet, safe_int(seat["street_bet"], 0))
            for j, other in enumerate(st.session_state.seats):
                if j != idx and seat_can_act(j):
                    other["acted"] = False
            seat["acted"] = True
            seat["last_action"] = f"Raise to {money(seat['street_bet'])}"
            push_log(f"{seat['name']} raises to {money(seat['street_bet'])}.")
            st.session_state.current_actor = next_active_index(idx)
            continue

        if to_call > 0:
            commit = apply_bet(idx, to_call)
            seat["acted"] = True
            seat["last_action"] = f"Call {money(commit)}"
            push_log(f"{seat['name']} calls {money(commit)}.")
        else:
            seat["acted"] = True
            seat["last_action"] = "Check"
            push_log(f"{seat['name']} checks.")

        move_to_next_actor()


# =========================================================
# ROUND TABLE HTML
# =========================================================
def seat_badge(index: int, seat: Seat) -> tuple[str, str]:
    base = []
    if index == st.session_state.dealer_button:
        base.append("D")
    if index == st.session_state.small_blind_index:
        base.append("SB")
    if index == st.session_state.big_blind_index:
        base.append("BB")

    if st.session_state.phase == "settled":
        if seat["result"] == "WIN":
            base.append("WIN")
            return " ".join(base), "pill win"
        if seat["result"] == "LOSS":
            base.append("LOSS")
            return " ".join(base), "pill loss"

    if bool(seat["folded"]):
        base.append("FOLD")
        return " ".join(base), "pill loss"

    if index == st.session_state.current_actor and st.session_state.phase == "action":
        base.append("ACT")
        return " ".join(base), "pill live"

    if bool(seat["all_in"]):
        base.append("ALL-IN")
        return " ".join(base), "pill"

    if not base:
        base.append("LIVE")
    return " ".join(base), "pill"


def seat_position_style(index: int, total: int) -> str:
    angle_deg = (360 / total) * index - 90
    angle = math.radians(angle_deg)
    radius_x = 39
    radius_y = 34
    x = 50 + radius_x * math.cos(angle)
    y = 50 + radius_y * math.sin(angle)
    return f"left:{x:.2f}%; top:{y:.2f}%; transform: translate(-50%, -50%);"


def render_round_table() -> None:
    seat_blocks: list[str] = []

    for i, seat in enumerate(st.session_state.seats):
        badge_text, badge_class = seat_badge(i, seat)
        reveal = bool(seat["is_human"]) or bool(st.session_state.showdown_revealed)
        if bool(seat["folded"]):
            reveal = False

        submeta = str(seat["best_hand_name"]) if st.session_state.phase == "settled" else str(seat["last_action"])
        chips_html = mini_chip_stack_html(safe_int(seat["stack"], 0))

        seat_blocks.append(
            join_html(
                f"<div class='seat-node' style='{seat_position_style(i, len(st.session_state.seats))}'>",
                "<div class='seat-head'>",
                f"<div class='seat-name'>{seat['name']}</div>",
                f"<div class='{badge_class}'>{badge_text}</div>",
                "</div>",
                f"<div class='seat-meta'>Stack {money(seat['stack'])} • Street Bet {money(seat['street_bet'])}</div>",
                f"<div class='seat-meta seat-submeta'>{submeta or 'Ready'}</div>",
                cards_row_html(normalize_cards(seat["cards"]), reveal),
                f"<div class='seat-chips'>{chips_html}</div>",
                "</div>",
            )
        )

    st.markdown(
        join_html(
            "<div class='round-table-wrap'>",
            "<div class='table-title'>Texas Hold’em Table</div>",
            "<div class='table-subtitle'>Round table, real blinds, live seat stacks, and proper street action.</div>",
            "<div class='round-table-shell'>",
            "<div class='round-table-center'>",
            f"<div class='street-chip'>{st.session_state.street.upper()}</div>",
            f"<div class='center-pot'>POT {money(st.session_state.pot)}</div>",
            f"<div class='center-bet'>TO CALL {money(st.session_state.current_bet)}</div>",
            board_cards_html(st.session_state.community_cards),
            "</div>",
            "".join(seat_blocks),
            "</div>",
            "</div>",
        ),
        unsafe_allow_html=True,
    )


# =========================================================
# PANELS
# =========================================================
def render_status() -> None:
    st.markdown(
        f"<div class='status {st.session_state.message_type}'>{st.session_state.message}</div>",
        unsafe_allow_html=True,
    )


def render_tournament_banner() -> None:
    champ_idx = tournament_champion_index()
    if champ_idx is None:
        st.session_state["champ_celebrated"] = False
        return

    champion = st.session_state.seats[champ_idx]
    chips = safe_int(champion["stack"], 0)
    total = tournament_chip_total()
    complete = chips == total
    tone = "success" if bool(champion["is_human"]) and complete else "warning"
    status = "TOURNAMENT CHAMPION" if complete else "CHIP LEADER"
    subtitle = "clean sweep, every chip on the table." if complete else "closeout pending — chips are missing from earlier split pots."

    st.markdown(
        join_html(
            "<div class='status ", tone, "'>",
            f"🏆 {champion['name']} — {status} ({money(chips)} / {money(total)})",
            "</div>",
            f"<div class='tiny-meta'>{subtitle}</div>",
        ),
        unsafe_allow_html=True,
    )

    if bool(champion["is_human"]) and complete and not bool(st.session_state.get("champ_celebrated", False)):
        st.balloons()
        st.session_state["champ_celebrated"] = True


def render_header_metrics() -> None:
    player = st.session_state.seats[player_index()]
    st.markdown(
        join_html(
            '<div class="metric-grid">',
            '<div class="metric-card"><div class="metric-label">Your Stack</div>'
            f'<div class="metric-value">{money(player["stack"])}</div></div>',
            '<div class="metric-card"><div class="metric-label">Pot</div>'
            f'<div class="metric-value">{money(st.session_state.pot)}</div></div>',
            '<div class="metric-card"><div class="metric-label">Street</div>'
            f'<div class="metric-value">{st.session_state.street.title()}</div></div>',
            '<div class="metric-card"><div class="metric-label">Players</div>'
            f'<div class="metric-value">{len(st.session_state.seats)}</div></div>',
            '<div class="metric-card"><div class="metric-label">Dealer</div>'
            f'<div class="metric-value">{st.session_state.seats[st.session_state.dealer_button]["name"]}</div></div>',
            '<div class="metric-card"><div class="metric-label">SB / BB</div>'
            f'<div class="metric-value">{money(SMALL_BLIND)} / {money(BIG_BLIND)}</div></div>',
            '<div class="metric-card"><div class="metric-label">Hand</div>'
            f'<div class="metric-value">H{st.session_state.round_counter}</div></div>',
            '</div>',
        ),
        unsafe_allow_html=True,
    )


def render_setup_controls() -> None:
    st.markdown("<div class='panel-title'>Table setup</div>", unsafe_allow_html=True)
    st.markdown("<div class='panel-subtitle'>Choose seats, then deal a real hand with rotating blinds.</div>", unsafe_allow_html=True)

    st.number_input(
        "Total players",
        min_value=MIN_SEATS,
        max_value=MAX_SEATS,
        step=1,
        key="player_count",
        disabled=st.session_state.phase != "setup",
    )

    st.number_input(
        "Raise size",
        min_value=BIG_BLIND,
        max_value=max(BIG_BLIND, safe_int(st.session_state.seats[player_index()]["stack"], STARTING_STACK)),
        step=10,
        key="raise_amount",
        disabled=st.session_state.phase != "setup",
    )

    if st.button("Apply Seat Count", use_container_width=True, disabled=st.session_state.phase != "setup"):
        old_player_stack = safe_int(st.session_state.seats[player_index()]["stack"], STARTING_STACK)
        st.session_state.seats = default_seats(st.session_state.player_count)
        st.session_state.seats[0]["stack"] = old_player_stack
        st.session_state.dealer_button = 0
        st.session_state.small_blind_index = 1 % len(st.session_state.seats)
        st.session_state.big_blind_index = 2 % len(st.session_state.seats)
        set_status(f"Table rebuilt for {st.session_state.player_count} seats.", "info")

    st.button(
        "Deal Hand",
        key="deal_hand_btn",
        type="primary",
        use_container_width=True,
        on_click=deal_new_hand,
        disabled=st.session_state.phase != "setup",
    )


def render_action_controls() -> None:
    to_call = player_to_call()

    st.markdown("<div class='panel-title'>Action</div>", unsafe_allow_html=True)
    st.markdown("<div class='panel-subtitle'>Real street betting. Act only when the button reaches you.</div>", unsafe_allow_html=True)

    st.number_input(
        "Raise size",
        min_value=BIG_BLIND,
        max_value=max(BIG_BLIND, safe_int(st.session_state.seats[player_index()]["stack"], 0)),
        step=10,
        key="raise_amount",
        disabled=st.session_state.current_actor != player_index() or st.session_state.phase != "action",
    )

    row1 = st.columns(2, gap="small")
    with row1[0]:
        st.button("Check", use_container_width=True, disabled=not can_check(), on_click=player_check)
    with row1[1]:
        st.button(f"Call {money(to_call)}", use_container_width=True, disabled=not can_call(), on_click=player_call)

    row2 = st.columns(2, gap="small")
    with row2[0]:
        st.button("Raise", use_container_width=True, disabled=not can_raise(), on_click=player_raise)
    with row2[1]:
        st.button("Fold", use_container_width=True, disabled=not can_fold(), on_click=player_fold)

    if st.session_state.phase == "settled":
        st.button("Next Hand", type="primary", use_container_width=True, on_click=reset_for_next_hand)


def render_chip_visuals() -> None:
    player = st.session_state.seats[player_index()]
    st.markdown(
        join_html(
            '<div class="chip-board">',
            chip_card_html("Your Stack", float(player["stack"]), "Your live chips"),
            chip_card_html("Pot", float(st.session_state.pot), "Middle of the felt"),
            chip_card_html("Your Street Bet", float(player["street_bet"]), "This betting round"),
            '</div>',
        ),
        unsafe_allow_html=True,
    )


def render_results_panel() -> None:
    with st.container(border=True):
        st.markdown("<div class='panel-title'>Results</div>", unsafe_allow_html=True)
        st.markdown("<div class='panel-subtitle'>Who won the hand and why.</div>", unsafe_allow_html=True)

        if st.session_state.hand_result:
            kind = "success" if "You" in st.session_state.hand_result and "win" in st.session_state.hand_result.lower() else "info"
            if "You fold" in st.session_state.hand_result or ("win" in st.session_state.hand_result.lower() and "You" not in st.session_state.hand_result):
                kind = "error"
            st.markdown(f"<div class='status {kind}'>{st.session_state.hand_result}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='status info'>No result yet. Hand is live.</div>", unsafe_allow_html=True)

        st.markdown(
            html(
                """
                <div class='tiny-meta'>
                    Real small blind and big blind posting<br>
                    Dealer button rotates each hand<br>
                    Action moves clockwise from UTG preflop and left of button postflop<br>
                    Bets reset by street while the full pot carries forward<br>
                    Best 5-card hand wins at showdown
                </div>
                """
            ),
            unsafe_allow_html=True,
        )


def render_log_panel() -> None:
    with st.container(border=True):
        st.markdown("<div class='panel-title'>Action log</div>", unsafe_allow_html=True)
        st.markdown("<div class='panel-subtitle'>Blinds, bets, checks, folds, and showdown flow.</div>", unsafe_allow_html=True)

        if not st.session_state.action_log:
            st.markdown("<div class='log-item'>No action yet.</div>", unsafe_allow_html=True)
            return

        items = "".join(f"<div class='log-item'>{item}</div>" for item in st.session_state.action_log[:10])
        st.markdown(f"<div class='action-log'>{items}</div>", unsafe_allow_html=True)


# =========================================================
# APP
# =========================================================
ensure_state()
inject_styles()

st.markdown("<div class='shell'>", unsafe_allow_html=True)

top_left, top_right = st.columns([1.32, 2.68], gap="small")

with top_left:
    st.markdown("<div class='hero-eyebrow'>Compliance Casino</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero-title'>AVI'S TEXAS HOLD’EM</div>", unsafe_allow_html=True)
    st.image("avi.png", width=120)  # ✅ Dealer avatar added (perfect header position)
    st.markdown(
        "<div class='hero-subtitle'>Round-table poker with real blinds, live stacks, per-seat chips, and proper turn order.</div>",
        unsafe_allow_html=True,
    )
    render_tournament_banner()
    render_status()

with top_right:
    render_header_metrics()

main_left, main_right = st.columns([1.02, 2.58], gap="small")

with main_left:
    with st.container(border=True):
        if st.session_state.phase == "setup":
            render_setup_controls()
        else:
            render_action_controls()

        render_chip_visuals()

        st.markdown(
            html(
                """
                <div class='tiny-meta'>
                    Dealer button rotates every hand<br>
                    Small blind and big blind post automatically<br>
                    Seats act in order around the table<br>
                    Street betting resets after flop / turn / river<br>
                    NPCs follow real turn progression
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        reset_cols = st.columns(2, gap="small")
        with reset_cols[0]:
            st.button("Reset Hand", use_container_width=True, on_click=reset_for_next_hand)
        with reset_cols[1]:
            st.button("Reset Game", use_container_width=True, on_click=reset_game)

    render_results_panel()
    render_log_panel()

with main_right:
    render_round_table()

st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.phase == "action" and st.session_state.current_actor != player_index():
    run_npc_actions()
    st.rerun()

from __future__ import annotations

import random
from html import escape
from textwrap import dedent
from typing import Final

import streamlit as st

st.set_page_config(
    page_title="Blackjack",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.audio("BlackJack.mp3", format="audio/mpeg", loop=False)

# =========================================================
# Constants
# =========================================================
SUITS: Final[tuple[str, ...]] = ("♠", "♥", "♦", "♣")
RANKS: Final[tuple[str, ...]] = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
RED_SUITS: Final[set[str]] = {"♥", "♦"}

CARD_VALUES: Final[dict[str, int]] = {
    "A": 11,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
}

STARTING_BANKROLL: Final[float] = 500.0
DEFAULT_BET: Final[int] = 25
DEALER_STANDS_ON: Final[int] = 17
CHIP_OPTIONS: Final[tuple[int, ...]] = (5, 10, 25, 50, 100, 500, 1000)
MIN_CARDS_FOR_NEW_DECK: Final[int] = 15
MAX_SPLIT_HANDS: Final[int] = 4
HISTORY_LIMIT: Final[int] = 16

CHIP_DENOMS: Final[tuple[tuple[float, str, int, str], ...]] = (
    (1000.0, "1000", 2000, "platinum"),
    (500.0, "500", 1000, "orange"),
    (100.0, "100", 200, "black"),
    (50.0, "50", 100, "green"),
    (25.0, "25", 50, "purple"),
    (10.0, "10", 20, "blue"),
    (5.0, "5", 10, "red"),
    (1.0, "1", 2, "white"),
    (0.5, "½", 1, "gold"),
)

CHIP_BUTTON_CLASS: Final[dict[int, str]] = {
    5: "red",
    10: "blue",
    25: "purple",
    50: "green",
    100: "black",
    500: "orange",
    1000: "platinum",
}

Card = dict[str, str]
HandState = dict[str, object]
HistoryEntry = dict[str, object]


# =========================================================
# Utilities
# =========================================================
def html(s: str) -> str:
    return dedent(s).strip()


def join_html(*parts: str) -> str:
    return "".join(part for part in parts if part)


def money(amount: float) -> str:
    return f"${amount:,.0f}" if float(amount).is_integer() else f"${amount:,.2f}"


def signed_money(amount: float) -> str:
    if amount > 0:
        return f"+{money(amount)}"
    if amount < 0:
        return f"-{money(abs(amount))}"
    return money(0)


def safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def message_kind_for_delta(delta: float) -> str:
    if delta > 0:
        return "success"
    if delta < 0:
        return "error"
    return "info"


def dealer_rule_text() -> str:
    return "H17" if bool(st.session_state.get("dealer_hits_soft_17", False)) else "S17"


def streak_text() -> str:
    streak_type = str(st.session_state.get("streak_type", ""))
    streak_count = max(0, safe_int(st.session_state.get("streak_count", 0), 0))

    if streak_type not in {"win", "loss", "push"} or streak_count <= 0:
        return "—"

    prefix = {"win": "W", "loss": "L", "push": "P"}[streak_type]
    return f"{prefix}{streak_count}"


def player_ref(index: int, total_hands: int) -> str:
    return "You" if total_hands == 1 else f"Hand {index + 1}"


def history_player_ref(index: int, total_hands: int) -> str:
    return "Player" if total_hands == 1 else f"Hand {index + 1}"


# =========================================================
# Styling
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
                    radial-gradient(circle at top, rgba(36, 102, 75, 0.22) 0%, rgba(7, 18, 13, 0) 38%),
                    linear-gradient(180deg, #07120d 0%, #091711 100%);
            }

            .block-container {
                max-width: 1500px;
                padding-top: 0.45rem;
                padding-bottom: 0.75rem;
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
                margin-bottom: 0.2rem;
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

            .input-label {
                color: #c8d2cb;
                font-size: 0.84rem;
                font-weight: 700;
                margin-bottom: 0.22rem;
                margin-top: 0.25rem;
            }

            .tiny-meta {
                color: #7f9789;
                font-size: 0.78rem;
                margin-top: 0.45rem;
                line-height: 1.35;
            }

            .metric-grid {
                display: grid;
                grid-template-columns: repeat(6, minmax(0, 1fr));
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
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-weight: 700;
                margin-bottom: 0.25rem;
            }

            .metric-value {
                color: #f8f2df;
                font-size: 1.18rem;
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

            .chip.gold {
                background: radial-gradient(circle at 30% 25%, #ffe59b 0%, #d5b15f 58%, #a67d2f 100%);
                color: #1d1508;
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

            .chip-empty {
                min-height: 52px;
                display: flex;
                align-items: center;
                color: rgba(255,255,255,0.52);
                font-size: 0.78rem;
                font-weight: 700;
            }

            .chip-row-gap {
                margin-top: 0.18rem;
            }

            .history-root {
                display: block;
            }

            .history-summary-row {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.42rem;
                margin-bottom: 0.55rem;
            }

            .mini-stat {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
                padding: 0.45rem 0.5rem;
            }

            .mini-stat-label {
                color: #8ea397;
                font-size: 0.72rem;
                font-weight: 800;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 0.18rem;
            }

            .mini-stat-value {
                color: #f7f1dc;
                font-size: 0.96rem;
                font-weight: 900;
            }

            .history-list {
                display: flex;
                flex-direction: column;
                gap: 0.45rem;
            }

            .history-item {
                background: rgba(255,255,255,0.045);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                padding: 0.58rem 0.65rem;
            }

            .history-item.win {
                border-color: rgba(88, 182, 113, 0.22);
            }

            .history-item.loss {
                border-color: rgba(196, 86, 86, 0.22);
            }

            .history-item.push {
                border-color: rgba(214, 175, 77, 0.22);
            }

            .history-top {
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                gap: 0.7rem;
                margin-bottom: 0.22rem;
            }

            .history-tag {
                display: inline-flex;
                align-items: center;
                gap: 0.3rem;
                border-radius: 999px;
                padding: 0.22rem 0.48rem;
                font-size: 0.72rem;
                font-weight: 900;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }

            .history-tag.win {
                background: rgba(34, 92, 44, 0.24);
                color: #dcf8d8;
            }

            .history-tag.loss {
                background: rgba(109, 34, 34, 0.24);
                color: #ffd7d7;
            }

            .history-tag.push {
                background: rgba(126, 93, 25, 0.22);
                color: #ffefbf;
            }

            .history-delta {
                font-size: 0.86rem;
                font-weight: 900;
            }

            .history-delta.plus {
                color: #95efab;
            }

            .history-delta.minus {
                color: #ffb1b1;
            }

            .history-delta.flat {
                color: #eedb9c;
            }

            .history-summary {
                color: #d7e2db;
                font-size: 0.82rem;
                line-height: 1.28;
                margin-bottom: 0.18rem;
            }

            .history-foot {
                color: #86a092;
                font-size: 0.74rem;
                font-weight: 700;
            }

            .history-empty {
                color: rgba(255,255,255,0.56);
                font-size: 0.82rem;
                font-weight: 700;
                padding: 0.25rem 0;
            }

            .table-wrap {
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0) 28%),
                    linear-gradient(180deg, #14553f 0%, #0f4634 100%);
                border: 1px solid rgba(197, 164, 92, 0.20);
                border-radius: 24px;
                padding: 0.8rem;
                box-shadow:
                    inset 0 1px 0 rgba(255,255,255,0.08),
                    inset 0 -16px 50px rgba(0,0,0,0.14);
                min-height: 560px;
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

            .hand-block {
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 18px;
                padding: 0.72rem;
                margin-bottom: 0.6rem;
                transition: all 0.18s ease;
            }

            .hand-block.active {
                background: rgba(255,255,255,0.11);
                border-color: rgba(231, 198, 112, 0.42);
                box-shadow:
                    0 0 0 1px rgba(231, 198, 112, 0.18),
                    inset 0 1px 0 rgba(255,255,255,0.08);
            }

            .hand-head {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 0.8rem;
                margin-bottom: 0.55rem;
            }

            .hand-title {
                color: #fbf7ea;
                font-size: 0.98rem;
                font-weight: 800;
                margin-bottom: 0.04rem;
            }

            .hand-meta {
                color: rgba(251, 247, 234, 0.82);
                font-size: 0.82rem;
                font-weight: 700;
                line-height: 1.25;
            }

            .hand-badge {
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
            }

            .hand-badge.active {
                background: rgba(231, 198, 112, 0.24);
                color: #fff1c5;
            }

            .hand-badge.win {
                background: rgba(34, 92, 44, 0.24);
                color: #dcf8d8;
            }

            .hand-badge.loss {
                background: rgba(109, 34, 34, 0.24);
                color: #ffd7d7;
            }

            .hand-badge.push {
                background: rgba(126, 93, 25, 0.22);
                color: #ffefbf;
            }

            .hand-badge.pending {
                background: rgba(255,255,255,0.12);
                color: #f3ead4;
            }

            .cards-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.42rem;
                min-height: 118px;
                align-items: flex-start;
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

            .card.red {
                color: #b73b3b;
            }

            .card.black {
                color: #171717;
            }

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

            .table-footer {
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                align-items: center;
                margin-top: 0.2rem;
                color: rgba(249, 244, 227, 0.86);
                font-size: 0.82rem;
                font-weight: 700;
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
                font-size: 1.1rem !important;
            }

            label[data-testid="stWidgetLabel"] p {
                color: #dbe5df !important;
                font-weight: 700 !important;
            }

            [data-testid="stToggle"] label p {
                color: #e0e8e2 !important;
                font-weight: 700 !important;
            }

            @media (max-width: 1300px) {
                .metric-grid {
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                }
            }

            @media (max-width: 900px) {
                .history-summary-row {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


def inject_chip_button_styles(selected_bet: int) -> None:
    styles: list[str] = []

    for chip, chip_class in CHIP_BUTTON_CLASS.items():
        styles.append(
            f"""
            .st-key-chip_{chip} button {{
                min-height: 82px !important;
                height: 82px !important;
                width: 82px !important;
                border-radius: 50% !important;
                padding: 0 !important;
                font-size: {"0.98rem" if chip < 100 else "0.92rem"} !important;
                font-weight: 900 !important;
                letter-spacing: -0.02em !important;
                line-height: 1 !important;
                border-width: 4px !important;
                border-style: dashed !important;
                box-shadow:
                    0 8px 18px rgba(0,0,0,0.30),
                    inset 0 2px 0 rgba(255,255,255,0.34) !important;
            }}
            """
        )

        if chip_class == "red":
            styles.append(
                f"""
                .st-key-chip_{chip} button {{
                    background: radial-gradient(circle at 30% 25%, #ff8078 0%, #cf4944 58%, #9d312d 100%) !important;
                    color: #fff9f8 !important;
                    border-color: rgba(255,255,255,0.62) !important;
                }}
                """
            )
        elif chip_class == "blue":
            styles.append(
                f"""
                .st-key-chip_{chip} button {{
                    background: radial-gradient(circle at 30% 25%, #59a8ff 0%, #2d74d9 58%, #1e57a8 100%) !important;
                    color: #f8fbff !important;
                    border-color: rgba(255,255,255,0.62) !important;
                }}
                """
            )
        elif chip_class == "purple":
            styles.append(
                f"""
                .st-key-chip_{chip} button {{
                    background: radial-gradient(circle at 30% 25%, #a574ff 0%, #7240d5 58%, #5426a9 100%) !important;
                    color: #fcf8ff !important;
                    border-color: rgba(255,255,255,0.62) !important;
                }}
                """
            )
        elif chip_class == "green":
            styles.append(
                f"""
                .st-key-chip_{chip} button {{
                    background: radial-gradient(circle at 30% 25%, #43b274 0%, #16804a 58%, #0f5c36 100%) !important;
                    color: #f7fff9 !important;
                    border-color: rgba(255,255,255,0.62) !important;
                }}
                """
            )
        elif chip_class == "black":
            styles.append(
                f"""
                .st-key-chip_{chip} button {{
                    background: radial-gradient(circle at 30% 25%, #606060 0%, #1f1f1f 58%, #0e0e0e 100%) !important;
                    color: #f8f8f8 !important;
                    border-color: rgba(255,255,255,0.62) !important;
                }}
                """
            )
        elif chip_class == "orange":
            styles.append(
                f"""
                .st-key-chip_{chip} button {{
                    background: radial-gradient(circle at 30% 25%, #ffbe72 0%, #f08e28 58%, #b75d08 100%) !important;
                    color: #fff8f1 !important;
                    border-color: rgba(255,255,255,0.68) !important;
                }}
                """
            )
        elif chip_class == "platinum":
            styles.append(
                f"""
                .st-key-chip_{chip} button {{
                    background: radial-gradient(circle at 30% 25%, #edf8ff 0%, #b5d2e2 58%, #6f8ea1 100%) !important;
                    color: #10202a !important;
                    border-color: rgba(255,255,255,0.78) !important;
                }}
                """
            )

        styles.append(
            f"""
            .st-key-chip_{chip} button:hover {{
                transform: translateY(-1px);
                filter: brightness(1.05);
            }}

            .st-key-chip_{chip} button:disabled {{
                opacity: 0.42 !important;
                filter: grayscale(0.18);
            }}
            """
        )

    if selected_bet in CHIP_BUTTON_CLASS:
        styles.append(
            f"""
            .st-key-chip_{selected_bet} button {{
                box-shadow:
                    0 0 0 4px rgba(236, 205, 125, 0.20),
                    0 0 0 2px rgba(247, 227, 170, 0.55) inset,
                    0 12px 22px rgba(0,0,0,0.34),
                    inset 0 2px 0 rgba(255,255,255,0.36) !important;
                transform: translateY(-1px);
            }}
            """
        )

    st.markdown(f"<style>{''.join(styles)}</style>", unsafe_allow_html=True)


# =========================================================
# Cards / State normalization
# =========================================================
def make_card(rank: str, suit: str) -> Card:
    return {"rank": rank, "suit": suit}


def card_key(card: Card) -> tuple[str, str]:
    return card["rank"], card["suit"]


def normalize_card(raw: object) -> Card | None:
    rank: str | None = None
    suit: str | None = None

    if isinstance(raw, dict):
        maybe_rank = raw.get("rank")
        maybe_suit = raw.get("suit")
        if maybe_rank is not None and maybe_suit is not None:
            rank = str(maybe_rank)
            suit = str(maybe_suit)
        elif 0 in raw and 1 in raw:
            rank = str(raw[0])
            suit = str(raw[1])
    elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
        rank = str(raw[0])
        suit = str(raw[1])
    elif isinstance(raw, str):
        raw = raw.strip()
        if len(raw) >= 2 and raw[-1] in SUITS:
            suit = raw[-1]
            rank = raw[:-1]

    if rank not in RANKS or suit not in SUITS:
        return None

    return make_card(rank, suit)


def normalize_cards(raw: object) -> list[Card]:
    if not isinstance(raw, (list, tuple)):
        return []

    cards: list[Card] = []
    for item in raw:
        card = normalize_card(item)
        if card is not None:
            cards.append(card)
    return cards


def looks_like_card_sequence(raw: object) -> bool:
    if not isinstance(raw, (list, tuple)) or not raw:
        return False
    return all(normalize_card(item) is not None for item in raw)


def make_hand(
    cards: list[Card] | None = None,
    bet: int = DEFAULT_BET,
    *,
    finished: bool = False,
    doubled: bool = False,
    result: str = "pending",
) -> HandState:
    return {
        "cards": list(cards or []),
        "bet": max(1, int(bet)),
        "finished": bool(finished),
        "doubled": bool(doubled),
        "result": str(result),
    }


def normalize_hand(raw: object, fallback_bet: int) -> HandState | None:
    if isinstance(raw, dict) and "cards" in raw:
        cards = normalize_cards(raw.get("cards", []))
        return make_hand(
            cards=cards,
            bet=safe_int(raw.get("bet", fallback_bet), fallback_bet),
            finished=bool(raw.get("finished", False)),
            doubled=bool(raw.get("doubled", False)),
            result=str(raw.get("result", "pending")),
        )

    if looks_like_card_sequence(raw):
        return make_hand(cards=normalize_cards(raw), bet=fallback_bet)

    return None


def normalize_hands(raw: object, fallback_bet: int, fallback_player_hand: list[Card]) -> list[HandState]:
    hands: list[HandState] = []

    if looks_like_card_sequence(raw):
        return [make_hand(cards=normalize_cards(raw), bet=fallback_bet)]

    if isinstance(raw, (list, tuple)):
        for item in raw:
            hand = normalize_hand(item, fallback_bet)
            if hand is not None and normalize_cards(hand.get("cards", [])):
                hands.append(hand)

    if not hands and fallback_player_hand:
        hands = [make_hand(cards=fallback_player_hand, bet=fallback_bet)]

    return hands


def normalize_history_entry(raw: object) -> HistoryEntry | None:
    if not isinstance(raw, dict):
        return None

    outcome = str(raw.get("outcome", "push"))
    if outcome not in {"win", "loss", "push"}:
        outcome = "push"

    rule = str(raw.get("rule", "S17"))
    if rule not in {"S17", "H17"}:
        rule = "S17"

    return {
        "seq": max(1, safe_int(raw.get("seq", 1), 1)),
        "outcome": outcome,
        "summary": str(raw.get("summary", "")),
        "delta": safe_float(raw.get("delta", 0.0), 0.0),
        "bankroll_after": max(0.0, safe_float(raw.get("bankroll_after", STARTING_BANKROLL), STARTING_BANKROLL)),
        "hands": max(1, safe_int(raw.get("hands", 1), 1)),
        "rule": rule,
    }


def normalize_history(raw: object) -> list[HistoryEntry]:
    if not isinstance(raw, (list, tuple)):
        return []

    history: list[HistoryEntry] = []
    for item in raw:
        entry = normalize_history_entry(item)
        if entry is not None:
            history.append(entry)

    return history[:HISTORY_LIMIT]


# =========================================================
# Game logic
# =========================================================
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


def hand_value_and_soft(hand: list[Card]) -> tuple[int, bool]:
    total = sum(CARD_VALUES[card["rank"]] for card in hand)
    aces_as_eleven = sum(1 for card in hand if card["rank"] == "A")

    while total > 21 and aces_as_eleven > 0:
        total -= 10
        aces_as_eleven -= 1

    return total, aces_as_eleven > 0


def hand_value(hand: list[Card]) -> int:
    return hand_value_and_soft(hand)[0]


def is_blackjack(hand: list[Card]) -> bool:
    return len(hand) == 2 and hand_value(hand) == 21


def dealer_should_hit(hand: list[Card]) -> bool:
    total, soft = hand_value_and_soft(hand)

    if total < DEALER_STANDS_ON:
        return True

    if total > DEALER_STANDS_ON:
        return False

    return soft and bool(st.session_state.get("dealer_hits_soft_17", False))


def history_record_counts(history: list[HistoryEntry] | None = None) -> tuple[int, int, int]:
    items = history if history is not None else normalize_history(st.session_state.get("round_history", []))
    wins = sum(1 for item in items if str(item.get("outcome")) == "win")
    losses = sum(1 for item in items if str(item.get("outcome")) == "loss")
    pushes = sum(1 for item in items if str(item.get("outcome")) == "push")
    return wins, losses, pushes


def max_bet_allowed() -> int:
    return max(0, int(float(st.session_state.get("bankroll", STARTING_BANKROLL))))


def clamp_bet_to_bankroll() -> None:
    bankroll_max = max_bet_allowed()
    current_bet = safe_int(st.session_state.get("bet_input", DEFAULT_BET), DEFAULT_BET)

    if bankroll_max < 1:
        st.session_state.bet_input = 1
        return

    st.session_state.bet_input = max(1, min(current_bet, bankroll_max))


def total_exposure() -> int:
    hands = st.session_state.get("hands", [])
    if not bool(st.session_state.get("round_active", False)) or not isinstance(hands, list):
        return 0

    exposure = 0
    for hand in hands:
        if isinstance(hand, dict):
            exposure += max(1, safe_int(hand.get("bet", DEFAULT_BET), DEFAULT_BET))
    return exposure


def additional_exposure_allowed(extra_amount: int) -> bool:
    bankroll = float(st.session_state.get("bankroll", STARTING_BANKROLL))
    return total_exposure() + max(0, int(extra_amount)) <= bankroll + 1e-9


def split_value(rank: str) -> int:
    if rank in {"10", "J", "Q", "K"}:
        return 10
    return CARD_VALUES[rank]


def current_hand() -> HandState | None:
    if not bool(st.session_state.get("round_active", False)):
        return None

    hands = st.session_state.get("hands", [])
    active_index = safe_int(st.session_state.get("active_hand_index", 0), 0)

    if not isinstance(hands, list):
        return None

    if 0 <= active_index < len(hands) and isinstance(hands[active_index], dict):
        return hands[active_index]

    return None


def can_play_active_hand() -> bool:
    hand = current_hand()
    if hand is None:
        return False
    return not bool(hand.get("finished", False))


def can_hit_active_hand() -> bool:
    if not can_play_active_hand():
        return False

    hand = current_hand()
    if hand is None:
        return False

    return hand_value(normalize_cards(hand.get("cards", []))) < 21


def can_stand_active_hand() -> bool:
    return can_play_active_hand()


def can_double_active_hand() -> bool:
    if not can_play_active_hand():
        return False

    hand = current_hand()
    if hand is None:
        return False

    cards = normalize_cards(hand.get("cards", []))
    bet = max(1, safe_int(hand.get("bet", DEFAULT_BET), DEFAULT_BET))

    return (
        len(cards) == 2
        and not bool(hand.get("doubled", False))
        and hand_value(cards) < 21
        and additional_exposure_allowed(bet)
    )


def can_split_active_hand() -> bool:
    if not can_play_active_hand():
        return False

    hands = st.session_state.get("hands", [])
    if not isinstance(hands, list) or len(hands) >= MAX_SPLIT_HANDS:
        return False

    hand = current_hand()
    if hand is None:
        return False

    cards = normalize_cards(hand.get("cards", []))
    if len(cards) != 2:
        return False

    rank_1 = cards[0]["rank"]
    rank_2 = cards[1]["rank"]
    bet = max(1, safe_int(hand.get("bet", DEFAULT_BET), DEFAULT_BET))

    return split_value(rank_1) == split_value(rank_2) and additional_exposure_allowed(bet)


def ensure_state() -> None:
    legacy_player_hand = normalize_cards(st.session_state.get("player_hand", []))
    fallback_bet = safe_int(
        st.session_state.get("current_bet", st.session_state.get("bet_input", DEFAULT_BET)),
        DEFAULT_BET,
    )

    hands = normalize_hands(st.session_state.get("hands", []), fallback_bet, legacy_player_hand)
    dealer_hand = normalize_cards(st.session_state.get("dealer_hand", []))

    bankroll = max(0.0, safe_float(st.session_state.get("bankroll", STARTING_BANKROLL), STARTING_BANKROLL))
    bet_input = safe_int(st.session_state.get("bet_input", DEFAULT_BET), DEFAULT_BET)
    current_bet = safe_int(st.session_state.get("current_bet", DEFAULT_BET), DEFAULT_BET)
    active_hand_index = safe_int(st.session_state.get("active_hand_index", 0), 0)
    round_active = bool(st.session_state.get("round_active", False))
    hide_dealer_hole = bool(st.session_state.get("hide_dealer_hole", True))
    dealer_hits_soft_17 = bool(st.session_state.get("dealer_hits_soft_17", False))
    round_result = str(st.session_state.get("round_result", ""))
    message = str(st.session_state.get("message", "Pick a bet and deal."))
    message_type = str(st.session_state.get("message_type", "info"))
    if message_type not in {"info", "success", "warning", "error"}:
        message_type = "info"

    round_history = normalize_history(st.session_state.get("round_history", []))
    round_counter = max(len(round_history), safe_int(st.session_state.get("round_counter", len(round_history)), len(round_history)))
    streak_type = str(st.session_state.get("streak_type", ""))
    if streak_type not in {"", "win", "loss", "push"}:
        streak_type = ""
    streak_count = max(0, safe_int(st.session_state.get("streak_count", 0), 0))

    in_play_cards = dealer_hand + [card for hand in hands for card in normalize_cards(hand.get("cards", []))]
    if len({card_key(card) for card in in_play_cards}) != len(in_play_cards):
        hands = []
        dealer_hand = []
        round_active = False
        hide_dealer_hole = True
        round_result = ""
        message = "Table refreshed after stale session data was repaired."
        message_type = "warning"
        in_play_cards = []

    in_play_keys = {card_key(card) for card in in_play_cards}
    deck = [card for card in normalize_cards(st.session_state.get("deck", [])) if card_key(card) not in in_play_keys]
    if not deck:
        deck = fresh_deck(exclude=in_play_cards)

    unfinished_indices = [i for i, hand in enumerate(hands) if not bool(hand.get("finished", False))]
    if round_active and (not hands or not dealer_hand):
        round_active = False
        hide_dealer_hole = True

    if round_active and not unfinished_indices:
        round_active = False

    if round_active:
        if active_hand_index not in unfinished_indices and unfinished_indices:
            active_hand_index = unfinished_indices[0]
    else:
        active_hand_index = 0
        if dealer_hand:
            hide_dealer_hole = False

    st.session_state.bankroll = bankroll
    st.session_state.bet_input = bet_input
    st.session_state.current_bet = current_bet
    st.session_state.active_hand_index = active_hand_index
    st.session_state.round_active = round_active
    st.session_state.hide_dealer_hole = hide_dealer_hole
    st.session_state.dealer_hits_soft_17 = dealer_hits_soft_17
    st.session_state.round_result = round_result
    st.session_state.message = message
    st.session_state.message_type = message_type
    st.session_state.round_history = round_history
    st.session_state.round_counter = round_counter
    st.session_state.streak_type = streak_type
    st.session_state.streak_count = streak_count
    st.session_state.hands = hands
    st.session_state.dealer_hand = dealer_hand
    st.session_state.deck = deck

    clamp_bet_to_bankroll()


def rebuild_deck_excluding_in_play() -> None:
    in_play = normalize_cards(st.session_state.get("dealer_hand", []))
    for hand in st.session_state.get("hands", []):
        if isinstance(hand, dict):
            in_play.extend(normalize_cards(hand.get("cards", [])))

    st.session_state.deck = fresh_deck(exclude=in_play)


def draw_card() -> Card:
    if not st.session_state.deck:
        rebuild_deck_excluding_in_play()

    card = st.session_state.deck[-1]
    st.session_state.deck = st.session_state.deck[:-1]
    return card


def prepare_deck_for_new_round() -> None:
    ensure_state()
    if len(st.session_state.deck) < MIN_CARDS_FOR_NEW_DECK:
        st.session_state.deck = fresh_deck()


def update_streak(outcome: str) -> None:
    current_type = str(st.session_state.get("streak_type", ""))
    current_count = max(0, safe_int(st.session_state.get("streak_count", 0), 0))

    if outcome not in {"win", "loss", "push"}:
        st.session_state.streak_type = ""
        st.session_state.streak_count = 0
        return

    if current_type == outcome:
        st.session_state.streak_count = current_count + 1
        return

    st.session_state.streak_type = outcome
    st.session_state.streak_count = 1


def record_round(summary: str, delta: float) -> None:
    outcome = "win" if delta > 0 else "loss" if delta < 0 else "push"
    st.session_state.round_counter = safe_int(st.session_state.get("round_counter", 0), 0) + 1

    entry: HistoryEntry = {
        "seq": st.session_state.round_counter,
        "outcome": outcome,
        "summary": summary,
        "delta": float(delta),
        "bankroll_after": float(st.session_state.bankroll),
        "hands": max(1, len(st.session_state.get("hands", []))),
        "rule": dealer_rule_text(),
    }

    history = normalize_history(st.session_state.get("round_history", []))
    history.insert(0, entry)
    st.session_state.round_history = history[:HISTORY_LIMIT]
    update_streak(outcome)
    st.session_state.round_result = outcome


def reset_table(full_reset: bool = False) -> None:
    ensure_state()

    bankroll = STARTING_BANKROLL if full_reset else float(st.session_state.bankroll)
    bankroll = max(0.0, bankroll)

    st.session_state.bankroll = bankroll
    st.session_state.deck = fresh_deck()
    st.session_state.hands = []
    st.session_state.dealer_hand = []
    st.session_state.current_bet = safe_int(st.session_state.get("bet_input", DEFAULT_BET), DEFAULT_BET)
    st.session_state.active_hand_index = 0
    st.session_state.round_active = False
    st.session_state.hide_dealer_hole = True
    st.session_state.round_result = ""
    st.session_state.message = "Pick a bet and deal."
    st.session_state.message_type = "info"

    if full_reset:
        st.session_state.round_history = []
        st.session_state.round_counter = 0
        st.session_state.streak_type = ""
        st.session_state.streak_count = 0

    clamp_bet_to_bankroll()


def settle_naturals() -> None:
    hands = list(st.session_state.hands)
    if not hands:
        return

    hand = dict(hands[0])
    cards = normalize_cards(hand.get("cards", []))
    bet = max(1, safe_int(hand.get("bet", DEFAULT_BET), DEFAULT_BET))
    dealer_total = hand_value(st.session_state.dealer_hand)

    player_bj = is_blackjack(cards)
    dealer_bj = is_blackjack(st.session_state.dealer_hand)

    delta = 0.0
    summary = ""

    if player_bj and dealer_bj:
        hand["finished"] = True
        hand["result"] = "push"
        st.session_state.message = "Both sides catch blackjack. Push."
        st.session_state.message_type = "info"
        summary = "Player blackjack • Dealer blackjack"
    elif player_bj:
        hand["finished"] = True
        hand["result"] = "blackjack"
        delta = bet * 1.5
        st.session_state.bankroll += delta
        st.session_state.message = "Blackjack. Clean win."
        st.session_state.message_type = "success"
        summary = f"Player blackjack • Dealer {dealer_total}"
    elif dealer_bj:
        hand["finished"] = True
        hand["result"] = "loss"
        delta = -bet
        st.session_state.bankroll += delta
        st.session_state.message = "Dealer flips blackjack. Tough beat."
        st.session_state.message_type = "error"
        summary = f"Dealer blackjack • Player {hand_value(cards)}"

    hands[0] = hand
    st.session_state.hands = hands
    st.session_state.round_active = False
    st.session_state.active_hand_index = 0
    st.session_state.hide_dealer_hole = False
    record_round(summary, delta)
    clamp_bet_to_bankroll()


def dealer_status_line(dealer_total: int, dealer_soft: bool, dealer_busted: bool) -> str:
    if dealer_busted:
        return f"Dealer burns out at {dealer_total}."
    soft_text = " soft" if dealer_soft and dealer_total <= 21 else ""
    return f"Dealer lands on {dealer_total}{soft_text}."


def dealer_history_line(dealer_total: int, dealer_soft: bool, dealer_busted: bool) -> str:
    if dealer_busted:
        return f"Dealer busts at {dealer_total}"
    soft_text = " soft" if dealer_soft and dealer_total <= 21 else ""
    return f"Dealer {dealer_total}{soft_text}"


def status_result_phrase(result: str, index: int, hand_count: int) -> str:
    who = player_ref(index, hand_count)

    if hand_count == 1:
        if result == "win":
            return "You take the hand."
        if result == "loss":
            return "House takes this one."
        if result == "push":
            return "It's a push."
        if result == "bust":
            return "You bust out."
        if result == "blackjack":
            return "Blackjack."
        return "Round settled."

    if result == "win":
        return f"{who} wins."
    if result == "loss":
        return f"{who} loses."
    if result == "push":
        return f"{who} pushes."
    if result == "bust":
        return f"{who} busts."
    if result == "blackjack":
        return f"{who} hits blackjack."
    return f"{who} settles."


def history_result_phrase(result: str, index: int, hand_count: int) -> str:
    who = history_player_ref(index, hand_count)

    if result == "win":
        return f"{who} wins"
    if result == "loss":
        return f"{who} loses"
    if result == "push":
        return f"{who} pushes"
    if result == "bust":
        return f"{who} busts"
    if result == "blackjack":
        return f"{who} blackjack"
    return f"{who} settles"


def resolve_round() -> None:
    hands = [dict(hand) for hand in st.session_state.hands]
    dealer_hand = list(st.session_state.dealer_hand)
    hand_count = len(hands)

    live_hands = [hand for hand in hands if str(hand.get("result", "pending")) != "bust"]

    if not live_hands:
        total_delta = 0.0
        for idx, hand in enumerate(hands):
            bet = max(1, safe_int(hand.get("bet", DEFAULT_BET), DEFAULT_BET))
            hand["finished"] = True
            hand["result"] = "loss"
            hands[idx] = hand
            total_delta -= float(bet)

        st.session_state.hands = hands
        st.session_state.bankroll = max(0.0, float(st.session_state.bankroll) + total_delta)
        st.session_state.round_active = False
        st.session_state.active_hand_index = 0
        st.session_state.hide_dealer_hole = False

        if hand_count == 1:
            st.session_state.message = "Too much heat. You bust out."
            summary = "Player busts"
        else:
            st.session_state.message = "All split hands bust. Rough round."
            summary = "All player hands bust"

        st.session_state.message_type = "error"
        record_round(summary, total_delta)
        clamp_bet_to_bankroll()
        return

    while dealer_should_hit(dealer_hand):
        dealer_hand.append(draw_card())

    st.session_state.dealer_hand = dealer_hand
    dealer_total, dealer_soft = hand_value_and_soft(dealer_hand)
    dealer_busted = dealer_total > 21

    total_delta = 0.0
    history_parts: list[str] = [dealer_history_line(dealer_total, dealer_soft, dealer_busted)]
    status_parts: list[str] = [dealer_status_line(dealer_total, dealer_soft, dealer_busted)]

    for idx, hand in enumerate(hands):
        cards = normalize_cards(hand.get("cards", []))
        bet = max(1, safe_int(hand.get("bet", DEFAULT_BET), DEFAULT_BET))
        current_result = str(hand.get("result", "pending"))

        if current_result == "bust":
            final_result = "loss"
            delta = -float(bet)
            history_parts.append(history_result_phrase("bust", idx, hand_count))
            status_parts.append(status_result_phrase("bust", idx, hand_count))
        else:
            total = hand_value(cards)
            if dealer_busted:
                final_result = "win"
                delta = float(bet)
            elif total > dealer_total:
                final_result = "win"
                delta = float(bet)
            elif total < dealer_total:
                final_result = "loss"
                delta = -float(bet)
            else:
                final_result = "push"
                delta = 0.0

            history_parts.append(history_result_phrase(final_result, idx, hand_count))
            status_parts.append(status_result_phrase(final_result, idx, hand_count))

        hand["finished"] = True
        hand["result"] = final_result
        hands[idx] = hand
        total_delta += delta

    st.session_state.hands = hands
    st.session_state.bankroll = max(0.0, float(st.session_state.bankroll) + total_delta)
    st.session_state.round_active = False
    st.session_state.active_hand_index = 0
    st.session_state.hide_dealer_hole = False

    st.session_state.message = " ".join(status_parts)
    st.session_state.message_type = message_kind_for_delta(total_delta)

    summary = " • ".join(history_parts)
    record_round(summary, total_delta)
    clamp_bet_to_bankroll()


def advance_after_finished_hand(prefix: str = "") -> None:
    hands = st.session_state.hands
    current_index = safe_int(st.session_state.get("active_hand_index", 0), 0)

    for next_index in range(current_index + 1, len(hands)):
        if not bool(hands[next_index].get("finished", False)):
            st.session_state.active_hand_index = next_index
            if prefix:
                st.session_state.message = f"{prefix} {player_ref(next_index, len(hands))} is up."
            else:
                st.session_state.message = f"{player_ref(next_index, len(hands))} is up."
            st.session_state.message_type = "info"
            return

    resolve_round()


def start_round() -> None:
    ensure_state()

    if st.session_state.round_active:
        return

    bankroll = float(st.session_state.bankroll)
    bet = safe_int(st.session_state.bet_input, DEFAULT_BET)

    if bankroll < 1:
        st.session_state.message = "Bankroll is below the $1 minimum. Reset bankroll."
        st.session_state.message_type = "warning"
        return

    if bet < 1:
        st.session_state.message = "Bet must be at least $1."
        st.session_state.message_type = "warning"
        return

    if bet > bankroll:
        st.session_state.message = "Bet can’t exceed bankroll."
        st.session_state.message_type = "warning"
        return

    prepare_deck_for_new_round()

    player_hand = [draw_card(), draw_card()]
    dealer_hand = [draw_card(), draw_card()]

    st.session_state.current_bet = bet
    st.session_state.hands = [make_hand(cards=player_hand, bet=bet)]
    st.session_state.dealer_hand = dealer_hand
    st.session_state.active_hand_index = 0
    st.session_state.round_active = True
    st.session_state.hide_dealer_hole = True
    st.session_state.round_result = ""
    st.session_state.message = "Cards are out. Your move."
    st.session_state.message_type = "info"

    if is_blackjack(player_hand) or is_blackjack(dealer_hand):
        settle_naturals()


def player_hit() -> None:
    ensure_state()

    if not can_hit_active_hand():
        return

    hands = [dict(hand) for hand in st.session_state.hands]
    index = safe_int(st.session_state.active_hand_index, 0)
    hand = dict(hands[index])
    cards = normalize_cards(hand.get("cards", []))

    cards.append(draw_card())
    total = hand_value(cards)

    hand["cards"] = cards
    if total > 21:
        hand["finished"] = True
        hand["result"] = "bust"
        hands[index] = hand
        st.session_state.hands = hands
        advance_after_finished_hand(f"{player_ref(index, len(hands))} burns out.")
        clamp_bet_to_bankroll()
        return

    hand["result"] = "pending"
    hands[index] = hand
    st.session_state.hands = hands

    if total == 21:
        st.session_state.message = f"{player_ref(index, len(hands))} hits 21."
    else:
        st.session_state.message = f"Nice pull. {player_ref(index, len(hands))} is on {total}."
    st.session_state.message_type = "info"


def player_stand() -> None:
    ensure_state()

    if not can_stand_active_hand():
        return

    hands = [dict(hand) for hand in st.session_state.hands]
    index = safe_int(st.session_state.active_hand_index, 0)
    hand = dict(hands[index])

    hand["finished"] = True
    hand["result"] = "stand"
    hands[index] = hand
    st.session_state.hands = hands

    advance_after_finished_hand(f"{player_ref(index, len(hands))} stands tall.")


def player_double() -> None:
    ensure_state()

    if not can_double_active_hand():
        return

    hands = [dict(hand) for hand in st.session_state.hands]
    index = safe_int(st.session_state.active_hand_index, 0)
    hand = dict(hands[index])
    cards = normalize_cards(hand.get("cards", []))
    current_bet = max(1, safe_int(hand.get("bet", DEFAULT_BET), DEFAULT_BET))

    hand["bet"] = current_bet * 2
    hand["doubled"] = True
    cards.append(draw_card())
    hand["cards"] = cards

    total = hand_value(cards)
    if total > 21:
        hand["finished"] = True
        hand["result"] = "bust"
        hands[index] = hand
        st.session_state.hands = hands
        advance_after_finished_hand(f"Big swing. {player_ref(index, len(hands))} busts.")
        clamp_bet_to_bankroll()
        return

    hand["finished"] = True
    hand["result"] = "stand"
    hands[index] = hand
    st.session_state.hands = hands

    advance_after_finished_hand(f"Double down lands on {total}.")


def player_split() -> None:
    ensure_state()

    if not can_split_active_hand():
        return

    hands = [dict(hand) for hand in st.session_state.hands]
    index = safe_int(st.session_state.active_hand_index, 0)
    hand = dict(hands[index])
    cards = normalize_cards(hand.get("cards", []))
    bet = max(1, safe_int(hand.get("bet", DEFAULT_BET), DEFAULT_BET))

    first_hand = make_hand(cards=[cards[0], draw_card()], bet=bet)
    second_hand = make_hand(cards=[cards[1], draw_card()], bet=bet)

    hands = hands[:index] + [first_hand, second_hand] + hands[index + 1 :]
    st.session_state.hands = hands
    st.session_state.active_hand_index = index
    st.session_state.message = "Pair split. Left hand first."
    st.session_state.message_type = "info"


def set_bet_amount(amount: int) -> None:
    ensure_state()

    if st.session_state.round_active:
        return

    allowed = max_bet_allowed()
    if allowed < 1:
        st.session_state.bet_input = 1
        return

    st.session_state.bet_input = max(1, min(int(amount), allowed))


# =========================================================
# Rendering helpers
# =========================================================
def suit_color(suit: str) -> str:
    return "red" if suit in RED_SUITS else "black"


def card_center(rank: str, suit: str) -> str:
    if rank == "A":
        return suit
    if rank in {"J", "Q", "K"}:
        return rank
    return suit


def face_card_html(card: Card) -> str:
    rank = card["rank"]
    suit = card["suit"]

    return html(
        f"""
        <div class="card face {suit_color(suit)}">
            <div class="card-top">
                <div class="card-rank">{escape(rank)}</div>
                <div class="card-suit">{escape(suit)}</div>
            </div>
            <div class="card-center">{escape(card_center(rank, suit))}</div>
            <div class="card-bottom">
                <div class="card-rank">{escape(rank)}</div>
                <div class="card-suit">{escape(suit)}</div>
            </div>
        </div>
        """
    )


def back_card_html() -> str:
    return '<div class="card back">♠</div>'


def empty_card_html() -> str:
    return '<div class="card empty">WAITING</div>'


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
    chips = "".join(f'<div class="chip {escape(chip_class)}"><span>{escape(label)}</span></div>' for _ in range(visible))
    return html(
        f"""
        <div class="chip-tower">
            {chips}
            <div class="chip-count">×{count}</div>
        </div>
        """
    )


def chip_card_html(title: str, amount: float, subtitle: str) -> str:
    towers = chip_breakdown(amount)
    towers_html = (
        '<div class="chip-empty">No chips on the felt.</div>'
        if not towers
        else "".join(chip_tower_html(chip_class, label, count) for chip_class, label, count in towers)
    )

    return join_html(
        '<div class="chip-card">',
        '<div class="chip-card-top">',
        f'<div class="chip-card-title">{escape(title)}</div>',
        f'<div class="chip-card-value">{escape(money(amount))}</div>',
        "</div>",
        f'<div class="chip-card-subtitle">{escape(subtitle)}</div>',
        f'<div class="chip-towers">{towers_html}</div>',
        "</div>",
    )


def render_chip_visuals() -> None:
    selected_bet = safe_int(
        st.session_state.current_bet if st.session_state.round_active else st.session_state.bet_input,
        DEFAULT_BET,
    )
    exposure = total_exposure() if st.session_state.round_active else selected_bet

    st.markdown(
        join_html(
            '<div class="chip-board">',
            chip_card_html("Bankroll", float(st.session_state.bankroll), "Total chips in front of you"),
            chip_card_html("Bet", float(selected_bet), "Base bet for the current or next deal"),
            chip_card_html("Exposure", float(exposure), "Live amount riding on the table"),
            "</div>",
        ),
        unsafe_allow_html=True,
    )


def dealer_meta_text(hand: list[Card], hide_hole: bool) -> str:
    if not hand:
        return f"Value 0 • {dealer_rule_text()}"

    if hide_hole:
        return f"Showing {CARD_VALUES[hand[0]['rank']]} • {dealer_rule_text()}"

    total, soft = hand_value_and_soft(hand)
    return f"Value {total}{' soft' if soft and total <= 21 else ''} • {dealer_rule_text()}"


def hand_badge(result: str, active: bool, finished: bool) -> tuple[str, str]:
    if active and not finished and st.session_state.round_active:
        return "ACTIVE", "active"

    if result == "blackjack":
        return "BLACKJACK", "win"
    if result == "win":
        return "WIN", "win"
    if result == "loss":
        return "LOSS", "loss"
    if result == "bust":
        return "BUST", "loss"
    if result == "push":
        return "PUSH", "push"
    if result == "stand" and st.session_state.round_active:
        return "LOCKED", "pending"

    return "READY", "pending"


def player_hand_meta_text(hand: HandState, active: bool) -> str:
    cards = normalize_cards(hand.get("cards", []))
    total = hand_value(cards) if cards else 0
    bet = max(1, safe_int(hand.get("bet", DEFAULT_BET), DEFAULT_BET))
    doubled = bool(hand.get("doubled", False))
    finished = bool(hand.get("finished", False))

    parts = [f"Value {total}", f"Bet {money(bet)}"]
    if doubled:
        parts.append("Doubled")
    if active and st.session_state.round_active and not finished:
        parts.append("Your move")
    elif finished and st.session_state.round_active:
        parts.append("Waiting")

    return " • ".join(parts)


def hand_html(
    title: str,
    meta_text: str,
    cards: list[Card],
    badge_text: str,
    badge_class: str,
    *,
    active: bool = False,
    hide_hole: bool = False,
) -> str:
    slots = max(2, len(cards))
    card_html_list: list[str] = []

    if not cards:
        card_html_list = [empty_card_html(), empty_card_html()]
    else:
        for idx in range(slots):
            if idx >= len(cards):
                card_html_list.append(empty_card_html())
            elif hide_hole and idx == 1:
                card_html_list.append(back_card_html())
            else:
                card_html_list.append(face_card_html(cards[idx]))

    active_class = " active" if active else ""

    return join_html(
        f'<div class="hand-block{active_class}">',
        '<div class="hand-head">',
        "<div>",
        f'<div class="hand-title">{escape(title)}</div>',
        f'<div class="hand-meta">{escape(meta_text)}</div>',
        "</div>",
        f'<div class="hand-badge {escape(badge_class)}">{escape(badge_text)}</div>',
        "</div>",
        f'<div class="cards-row">{"".join(card_html_list)}</div>',
        "</div>",
    )


# =========================================================
# UI renderers
# =========================================================
def render_status() -> None:
    st.markdown(
        f"<div class='status {escape(st.session_state.message_type)}'>{escape(st.session_state.message)}</div>",
        unsafe_allow_html=True,
    )


def render_header_metrics() -> None:
    wins, losses, pushes = history_record_counts()
    record = f"{wins}-{losses}-{pushes}"
    selected_bet = safe_int(
        st.session_state.current_bet if st.session_state.round_active else st.session_state.bet_input,
        DEFAULT_BET,
    )
    exposure = total_exposure() if st.session_state.round_active else selected_bet

    st.markdown(
        join_html(
            '<div class="metric-grid">',
            '<div class="metric-card"><div class="metric-label">Bankroll</div>'
            f'<div class="metric-value">{escape(money(float(st.session_state.bankroll)))}</div></div>',
            '<div class="metric-card"><div class="metric-label">Bet</div>'
            f'<div class="metric-value">{escape(money(float(selected_bet)))}</div></div>',
            '<div class="metric-card"><div class="metric-label">Exposure</div>'
            f'<div class="metric-value">{escape(money(float(exposure)))}</div></div>',
            '<div class="metric-card"><div class="metric-label">Record</div>'
            f'<div class="metric-value">{escape(record)}</div></div>',
            '<div class="metric-card"><div class="metric-label">Streak</div>'
            f'<div class="metric-value">{escape(streak_text())}</div></div>',
            '<div class="metric-card"><div class="metric-label">Deck / Rule</div>'
            f'<div class="metric-value">{escape(f"{len(st.session_state.deck)} • {dealer_rule_text()}")}</div></div>',
            "</div>",
        ),
        unsafe_allow_html=True,
    )


def chip_button_label(chip: int) -> str:
    return f"${chip}"


def render_chip_row(chips: tuple[int, ...], selected: int, allowed: int) -> None:
    cols = st.columns(len(chips), gap="small")

    for idx, chip in enumerate(chips):
        disabled = st.session_state.round_active or chip > allowed
        with cols[idx]:
            st.button(
                chip_button_label(chip),
                key=f"chip_{chip}",
                use_container_width=True,
                disabled=disabled,
                on_click=set_bet_amount,
                args=(chip,),
            )


def render_chip_controls() -> None:
    selected = safe_int(st.session_state.bet_input, DEFAULT_BET)
    allowed = max_bet_allowed()

    inject_chip_button_styles(selected)

    render_chip_row((5, 10, 25, 50), selected, allowed)
    st.markdown("<div class='chip-row-gap'></div>", unsafe_allow_html=True)
    render_chip_row((100, 500, 1000), selected, allowed)


def render_controls() -> None:
    with st.container(border=True):
        st.markdown("<div class='panel-title'>Controls</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='panel-subtitle'>Double down. Split matching values. Dealer rule toggle. Built to play clean.</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<div class='input-label'>Quick chips</div>", unsafe_allow_html=True)
        render_chip_controls()

        st.markdown("<div class='input-label'>Custom bet</div>", unsafe_allow_html=True)
        st.number_input(
            "Custom bet",
            min_value=1,
            max_value=max(1, max_bet_allowed()),
            step=5,
            format="%d",
            key="bet_input",
            disabled=st.session_state.round_active,
            label_visibility="collapsed",
        )

        row_one = st.columns(3, gap="small")
        with row_one[0]:
            st.button(
                "Deal",
                key="deal_btn",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.round_active or max_bet_allowed() < 1,
                on_click=start_round,
            )
        with row_one[1]:
            st.button(
                "Hit",
                key="hit_btn",
                use_container_width=True,
                disabled=not can_hit_active_hand(),
                on_click=player_hit,
            )
        with row_one[2]:
            st.button(
                "Stand",
                key="stand_btn",
                use_container_width=True,
                disabled=not can_stand_active_hand(),
                on_click=player_stand,
            )

        row_two = st.columns(2, gap="small")
        with row_two[0]:
            st.button(
                "Double",
                key="double_btn",
                use_container_width=True,
                disabled=not can_double_active_hand(),
                on_click=player_double,
            )
        with row_two[1]:
            st.button(
                "Split",
                key="split_btn",
                use_container_width=True,
                disabled=not can_split_active_hand(),
                on_click=player_split,
            )

        st.toggle(
            "Dealer hits soft 17",
            key="dealer_hits_soft_17",
            disabled=st.session_state.round_active,
            help="When enabled, dealer draws on soft 17. Rule locks while a round is live.",
        )

        render_chip_visuals()

        reset_cols = st.columns(2, gap="small")
        with reset_cols[0]:
            st.button(
                "Reset table",
                key="reset_table_btn",
                use_container_width=True,
                on_click=reset_table,
                kwargs={"full_reset": False},
            )
        with reset_cols[1]:
            st.button(
                "Reset bankroll",
                key="reset_bankroll_btn",
                use_container_width=True,
                on_click=reset_table,
                kwargs={"full_reset": True},
            )

        st.markdown(
            html(
                """
                <div class='tiny-meta'>
                    Dealer stands on hard 17<br>
                    Toggle switches between S17 and H17<br>
                    Blackjack pays 3:2<br>
                    Split matching values up to 4 hands<br>
                    Double down after split is allowed<br>
                    Self-heals stale session state<br>
                    Auto-shuffles when the deck gets low
                </div>
                """
            ),
            unsafe_allow_html=True,
        )


def build_history_html() -> str:
    history = normalize_history(st.session_state.get("round_history", []))
    wins, losses, pushes = history_record_counts(history)
    total_rounds = len(history)
    streak = streak_text()

    if history:
        items_html = ""
        for entry in history[:6]:
            outcome = str(entry.get("outcome", "push"))
            delta = safe_float(entry.get("delta", 0.0), 0.0)
            delta_class = "plus" if delta > 0 else "minus" if delta < 0 else "flat"

            items_html += join_html(
                f'<div class="history-item {escape(outcome)}">',
                '<div class="history-top">',
                f'<div class="history-tag {escape(outcome)}">#{safe_int(entry.get("seq", 1), 1)} {escape(outcome)}</div>',
                f'<div class="history-delta {delta_class}">{escape(signed_money(delta))}</div>',
                "</div>",
                f'<div class="history-summary">{escape(str(entry.get("summary", "")))}</div>',
                '<div class="history-foot">',
                f'Bank {escape(money(safe_float(entry.get("bankroll_after", STARTING_BANKROLL), STARTING_BANKROLL)))} • ',
                f'{safe_int(entry.get("hands", 1), 1)} hand(s) • ',
                f'{escape(str(entry.get("rule", "S17")))}',
                "</div>",
                "</div>",
            )
    else:
        items_html = '<div class="history-empty">No rounds yet. Deal one and start stacking history.</div>'

    return join_html(
        '<div class="history-root">',
        '<div class="panel-title">History &amp; streaks</div>',
        '<div class="panel-subtitle">Recent rounds, live streaks, and bankroll track record.</div>',
        '<div class="history-summary-row">',
        '<div class="mini-stat"><div class="mini-stat-label">Rounds</div>'
        f'<div class="mini-stat-value">{total_rounds}</div></div>',
        '<div class="mini-stat"><div class="mini-stat-label">Record</div>'
        f'<div class="mini-stat-value">{wins}-{losses}-{pushes}</div></div>',
        '<div class="mini-stat"><div class="mini-stat-label">Streak</div>'
        f'<div class="mini-stat-value">{escape(streak)}</div></div>',
        "</div>",
        f'<div class="history-list">{items_html}</div>',
        "</div>",
    )


def render_history_panel() -> None:
    with st.container(border=True):
        st.markdown(build_history_html(), unsafe_allow_html=True)


def render_table() -> None:
    dealer_hide = bool(st.session_state.round_active and st.session_state.hide_dealer_hole)
    hands = st.session_state.get("hands", [])
    active_index = safe_int(st.session_state.get("active_hand_index", 0), 0)

    dealer_badge_text = "LIVE" if st.session_state.round_active else "HOUSE"
    dealer_badge_class = "active" if st.session_state.round_active else "pending"

    table_parts = [
        '<div class="table-wrap">',
        '<div class="table-title">Blackjack Table</div>',
        f'<div class="table-subtitle">Double, split, streak tracking, and live {escape(dealer_rule_text())} dealer behavior.</div>',
        hand_html(
            "Dealer",
            dealer_meta_text(st.session_state.dealer_hand, dealer_hide),
            st.session_state.dealer_hand,
            dealer_badge_text,
            dealer_badge_class,
            active=False,
            hide_hole=dealer_hide,
        ),
    ]

    if hands:
        for idx, raw_hand in enumerate(hands):
            hand = dict(raw_hand)
            cards = normalize_cards(hand.get("cards", []))
            finished = bool(hand.get("finished", False))
            result = str(hand.get("result", "pending"))
            active = bool(st.session_state.round_active and idx == active_index and not finished)
            badge_text, badge_class = hand_badge(result, active, finished)
            title = "Player" if len(hands) == 1 else f"Hand {idx + 1}"

            table_parts.append(
                hand_html(
                    title,
                    player_hand_meta_text(hand, active),
                    cards,
                    badge_text,
                    badge_class,
                    active=active,
                    hide_hole=False,
                )
            )
    else:
        table_parts.append(
            hand_html(
                "Player",
                "Value 0 • Bet $0",
                [],
                "READY",
                "pending",
                active=False,
                hide_hole=False,
            )
        )

    footer_left = f"Exposure: {money(float(total_exposure() if st.session_state.round_active else safe_int(st.session_state.bet_input, DEFAULT_BET)))}"
    if st.session_state.round_active and hands:
        footer_right = f"Playing hand {active_index + 1} of {len(hands)}"
    else:
        footer_right = f"Waiting on next deal • {len(st.session_state.deck)} cards left"

    table_parts.append(
        join_html(
            '<div class="table-footer">',
            f"<div>{escape(footer_left)}</div>",
            f"<div>{escape(footer_right)}</div>",
            "</div>",
        )
    )
    table_parts.append("</div>")

    st.markdown("".join(table_parts), unsafe_allow_html=True)


# =========================================================
# App
# =========================================================
ensure_state()
inject_styles()

st.markdown("<div class='shell'>", unsafe_allow_html=True)

top_left, top_right = st.columns([1.45, 2.75], gap="small")

with top_left:
    st.markdown("<div class='hero-eyebrow'>Compliance Casino</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero-title'>AVI'S BLACKJACK</div>", unsafe_allow_html=True)
    st.image("avi.png", width=120)  # ✅ Dealer avatar added (perfect header position)
    st.markdown(
        "<div class='hero-subtitle'>No fluff. Sharp table. Split, double, streak, and stack chips like you mean it.</div>",
        unsafe_allow_html=True,
    )
    render_status()

with top_right:
    render_header_metrics()

main_left, main_right = st.columns([1.1, 2.45], gap="small")

with main_left:
    render_controls()
    render_history_panel()

with main_right:
    render_table()

st.markdown("</div>", unsafe_allow_html=True)

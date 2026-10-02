"""Componenti di interfaccia condivisi dalle pagine della dashboard:
stile globale, intestazioni, schede con spiegazione, tabelle con tooltip,
classifica con forma recente, card dei leader.

Ogni grafico vive in una `card`: titolo + una riga di spiegazione + (se
serve) un popover "Come leggere" — così chi apre la dashboard non deve
indovinare cosa sta guardando.
"""

from __future__ import annotations

import html
from contextlib import contextmanager

import pandas as pd
import streamlit as st

from src.glossary import PLAYER_METRICS, TEAM_METRICS, MetricInfo

_CSS = """
<style>
.block-container {padding-top: 1.8rem; padding-bottom: 3rem; max-width: 1440px;}
h1, h2, h3 {letter-spacing: -0.01em;}

/* --- intestazione di pagina --- */
.page-eyebrow {text-transform: uppercase; letter-spacing: .09em; font-size: .72rem; font-weight: 650; color: #2a78d6; margin-bottom: .15rem;}
.page-title {font-size: 2.05rem; font-weight: 700; color: #1a1d23; line-height: 1.15; margin: 0 0 .35rem 0;}
.page-sub {color: #5c6470; font-size: .98rem; max-width: 60rem; margin-bottom: 1.2rem; line-height: 1.5;}
.section-title {font-size: 1.12rem; font-weight: 650; color: #1a1d23; margin: 1.5rem 0 .1rem 0;}
.section-sub {color: #5c6470; font-size: .9rem; margin-bottom: .7rem;}

/* --- card --- */
[class*="st-key-card_"] {background: #ffffff; border: 1px solid #e3e6ea; border-radius: 14px;
  padding: 16px 18px 8px 18px; box-shadow: 0 1px 2px rgba(16, 24, 40, .04);}
/* Streamlit forza lo sfondo della figura Plotly sul colore della pagina:
   lo rendiamo trasparente così i grafici prendono il bianco della card */
.js-plotly-plot .main-svg {background: transparent !important;}
.js-plotly-plot .legend .bg {fill: transparent !important;}
.card-title {font-size: 1rem; font-weight: 650; color: #1a1d23; margin: 0; line-height: 1.3;}
.card-desc {font-size: .84rem; color: #5c6470; margin: .2rem 0 .3rem 0; line-height: 1.45;}

/* --- metriche (st.metric con border=True) --- */
[data-testid="stMetric"] {background: #ffffff; border-radius: 12px;}
[data-testid="stMetricLabel"] p {font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; color: #6b7380; font-weight: 600;}
[data-testid="stMetricValue"] {font-size: 1.65rem;}

/* --- tabs e controlli --- */
.stTabs [data-baseweb="tab-list"] {gap: 1.4rem; border-bottom: 1px solid #e3e6ea;}
.stTabs [data-baseweb="tab"] {padding: .55rem 0 .6rem 0;}
.stTabs [data-baseweb="tab"] p {font-size: .95rem; font-weight: 600;}

/* --- callout --- */
.callout {border-left: 3px solid #2a78d6; background: #eef4fc; padding: .7rem 1rem; border-radius: 8px;
  color: #1a1d23; font-size: .88rem; line-height: 1.5; margin: .2rem 0 .8rem 0;}
.callout.warn {border-left-color: #c98500; background: #fdf6e4;}
.callout b {font-weight: 650;}

/* --- forma recente --- */
.fb {display: inline-block; width: 21px; height: 21px; border-radius: 5px; font-size: 11px; font-weight: 700;
  color: #fff; text-align: center; line-height: 21px; margin-right: 3px;}
.fb.W {background: #0ca30c;} .fb.D {background: #8b929c;} .fb.L {background: #d03b3b;}

/* --- classifica --- */
table.standings {width: 100%; border-collapse: collapse; font-size: .86rem; font-variant-numeric: tabular-nums;}
table.standings th {text-align: right; color: #6b7380; font-weight: 600; font-size: .72rem; text-transform: uppercase;
  letter-spacing: .05em; padding: 6px 6px; border-bottom: 1px solid #e3e6ea;}
table.standings th.l, table.standings td.l {text-align: left;}
table.standings td {text-align: right; padding: 6px 6px; border-bottom: 1px solid #f0f1f4; color: #1a1d23;}
table.standings tr.hl td {background: #eef4fc; font-weight: 650;}
table.standings td.pos {width: 34px; font-weight: 650; color: #52514e; border-left: 3px solid transparent;}
table.standings td.pos.ucl {border-left-color: #2a78d6;}
table.standings td.pos.uel {border-left-color: #1baf7a;}
table.standings td.pos.rel {border-left-color: #d03b3b;}
table.standings td.pts {font-weight: 700;}
table.standings td.form {white-space: nowrap;}
.legend-dot {display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin: 0 4px 0 10px; vertical-align: -1px;}

/* --- leader card --- */
.leader {background: #ffffff; border: 1px solid #e3e6ea; border-radius: 14px; padding: 14px 16px; height: 100%;}
.leader .k {font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: #6b7380; font-weight: 600;}
.leader .v {font-size: 1.7rem; font-weight: 700; color: #1a1d23; line-height: 1.2; margin-top: .25rem;}
.leader .n {font-size: .95rem; font-weight: 650; color: #1a1d23; margin-top: .1rem;}
.leader .t {font-size: .8rem; color: #6b7380;}

/* --- tabellone partita --- */
.scoreboard {display: flex; align-items: center; justify-content: center; gap: 1.6rem; background: #0f1b2d; color: #fff;
  border-radius: 14px; padding: 18px 12px; margin-bottom: .8rem;}
.scoreboard .team {font-size: 1.25rem; font-weight: 650; min-width: 9rem;}
.scoreboard .team.h {text-align: right;}
.scoreboard .score {font-size: 2.2rem; font-weight: 700; letter-spacing: .05em; font-variant-numeric: tabular-nums;}
.scoreboard .meta {font-size: .78rem; color: #9fb0c8; text-align: center;}
.result-chip {background: #ffffff; border: 1px solid #e3e6ea; border-radius: 10px; padding: 8px 12px; font-size: .86rem;
  margin-bottom: 8px; display: flex; justify-content: space-between; font-variant-numeric: tabular-nums;}
.result-chip b {font-weight: 700;}

/* --- sidebar --- */
.brand {font-weight: 700; font-size: 1.05rem; color: #ffffff; margin: .2rem 0 0 0;}
.brand-sub {font-size: .78rem; color: #9fb0c8; margin-bottom: .6rem;}
.nav-section {font-size: .68rem; text-transform: uppercase; letter-spacing: .09em; color: #7f93b0; font-weight: 650;
  margin: .9rem 0 .15rem .2rem;}
[data-testid="stSidebar"] [data-testid="stPageLink"] a {padding-top: .15rem; padding-bottom: .15rem;}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {padding-top: .2rem; padding-bottom: .2rem;}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def reset_keys() -> None:
    """Da chiamare una volta per esecuzione: i contenitori-card hanno una key
    progressiva (serve alla classe CSS st-key-card_N)."""
    st.session_state["_card_n"] = 0


def _next_key(prefix: str) -> str:
    n = st.session_state.get("_card_n", 0) + 1
    st.session_state["_card_n"] = n
    return f"{prefix}_{n}"


# --------------------------------------------------------------------------- #
# Testo
# --------------------------------------------------------------------------- #

def page_header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="page-eyebrow">{html.escape(eyebrow)}</div>'
        f'<div class="page-title">{html.escape(title)}</div>'
        f'<div class="page-sub">{subtitle}</div>',
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str | None = None) -> None:
    sub = f'<div class="section-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="section-title">{html.escape(title)}</div>{sub}', unsafe_allow_html=True)


def callout(text: str, warn: bool = False) -> None:
    st.markdown(f'<div class="callout{" warn" if warn else ""}">{text}</div>', unsafe_allow_html=True)


@contextmanager
def card(title: str, description: str | None = None, how_to: str | None = None):
    """Contenitore bianco con titolo, spiegazione e popover 'Come leggere'."""
    with st.container(key=_next_key("card")):
        st.markdown(
            f'<div class="card-title">{html.escape(title)}</div>'
            + (f'<div class="card-desc">{description}</div>' if description else ""),
            unsafe_allow_html=True,
        )
        if how_to:
            with st.popover("How to read", icon=":material/help:", type="tertiary", width="content"):
                st.markdown(how_to)
        yield


def chart(fig) -> None:
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False},
                    key=_next_key("chart"))


# --------------------------------------------------------------------------- #
# Tabelle
# --------------------------------------------------------------------------- #

def _column_config(df: pd.DataFrame, columns: list[str], infos: dict[str, MetricInfo]) -> dict:
    cfg = {}
    for col in columns:
        info = infos.get(col)
        if info is None:
            continue
        help_text = info.description or None
        if info.kind == "text":
            cfg[col] = st.column_config.TextColumn(info.label, help=help_text)
        elif info.kind in ("pct", "share"):
            top = pd.to_numeric(df[col], errors="coerce").max()
            max_value = 100.0 if info.kind == "pct" else float(max(top if pd.notna(top) else 1, 1))
            cfg[col] = st.column_config.ProgressColumn(
                info.label, help=help_text, format="%.1f%%", min_value=0.0, max_value=max_value,
            )
        elif info.kind == "count":
            cfg[col] = st.column_config.NumberColumn(info.label, help=help_text, format="%d")
        else:
            cfg[col] = st.column_config.NumberColumn(info.label, help=help_text, format="%.2f")
    return cfg


def data_table(
    df: pd.DataFrame, columns: list[str], *, scope: str = "player",
    extra: dict[str, MetricInfo] | None = None, height: int | str = "auto",
) -> None:
    """st.dataframe con etichette leggibili, formato per tipo di metrica,
    barre di progresso per le percentuali e definizione della metrica nel
    tooltip dell'intestazione (passa il mouse sul nome della colonna)."""
    base = PLAYER_METRICS if scope == "player" else TEAM_METRICS
    infos = {**base, **(extra or {})}
    columns = [c for c in columns if c in df.columns]
    st.dataframe(
        df[columns], column_config=_column_config(df, columns, infos),
        hide_index=True, width="stretch", height=height,
    )


# --------------------------------------------------------------------------- #
# Blocchi HTML
# --------------------------------------------------------------------------- #

def form_badges(form: list[dict]) -> str:
    return "".join(
        f'<span class="fb {f["code"]}" title="{html.escape(f["detail"])}">{f["result"]}</span>' for f in form
    )


def standings_table(summary: pd.DataFrame, form: dict[str, list[dict]], highlight: str | None = None) -> None:
    """Classifica in HTML: zone europee/retrocessione, forma recente come
    badge colorati CON lettera (V/N/P), riga della squadra in evidenza."""
    n = len(summary)
    rows = []
    for _, r in summary.iterrows():
        pos = int(r["rank"])
        zone = "ucl" if pos <= 4 else "uel" if pos <= 6 else "rel" if pos > n - 3 else ""
        cls = ' class="hl"' if highlight and r["team"] == highlight else ""
        rows.append(
            f"<tr{cls}><td class='pos {zone}'>{pos}</td><td class='l'>{html.escape(r['team'].title())}</td>"
            f"<td>{int(r['matches'])}</td><td>{int(r['wins'])}</td><td>{int(r['draws'])}</td><td>{int(r['losses'])}</td>"
            f"<td>{int(r['goals_for'])}:{int(r['goals_against'])}</td><td>{int(r['goal_difference']):+d}</td>"
            f"<td class='pts'>{int(r['points'])}</td><td class='l form'>{form_badges(form.get(r['team'], []))}</td></tr>"
        )
    st.markdown(
        "<table class='standings'><thead><tr><th>#</th><th class='l'>Team</th><th>MP</th><th>W</th><th>D</th>"
        "<th>L</th><th>Goals</th><th>GD</th><th>Pts</th><th class='l'>Form</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table>"
        "<div class='card-desc' style='margin-top:.5rem'>"
        "<span class='legend-dot' style='background:#2a78d6;margin-left:0'></span>Champions League"
        "<span class='legend-dot' style='background:#1baf7a'></span>Europa/Conference League"
        "<span class='legend-dot' style='background:#d03b3b'></span>Relegation"
        " · Form: last 5 matches, most recent on the right (hover a badge for details)</div>",
        unsafe_allow_html=True,
    )


def leader_card(kicker: str, value: str, name: str, team: str) -> None:
    st.markdown(
        f"<div class='leader'><div class='k'>{html.escape(kicker)}</div><div class='v'>{html.escape(value)}</div>"
        f"<div class='n'>{html.escape(name)}</div><div class='t'>{html.escape(team)}</div></div>",
        unsafe_allow_html=True,
    )


def scoreboard(home: str, away: str, home_score: int, away_score: int, meta: str) -> None:
    st.markdown(
        f"<div class='scoreboard'><div class='team h'>{html.escape(home.title())}</div>"
        f"<div><div class='score'>{home_score} – {away_score}</div><div class='meta'>{html.escape(meta)}</div></div>"
        f"<div class='team'>{html.escape(away.title())}</div></div>",
        unsafe_allow_html=True,
    )


def result_chip(home: str, away: str, hs: int, as_: int) -> str:
    h = f"<b>{html.escape(home.title())}</b>" if hs > as_ else html.escape(home.title())
    a = f"<b>{html.escape(away.title())}</b>" if as_ > hs else html.escape(away.title())
    return f"<div class='result-chip'><span>{h}</span><span><b>{hs} – {as_}</b></span><span>{a}</span></div>"


def ordinal(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', 11 -> '11th' (posizioni in classifica)."""
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

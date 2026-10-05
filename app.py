"""Serie A Match Report Observatory — dashboard Streamlit (multipagina).

Lancio: streamlit run app.py

Questo file carica il dataset in data/processed/ (in cache, invalidata quando
cambiano i CSV), disegna i filtri globali nella barra laterale e instrada
verso le pagine in views/. Ogni pagina riceve lo stesso Context
(src/context.py). I PDF non vengono letti qui: il dataset è prodotto e
aggiornato da update_dataset.py (a mano o dal workflow settimanale).

Nota: src/data_quality.py (riconciliazione giocatori-vs-squadra) NON va mai
importato qui — è un controllo del parser a uso esclusivo del notebook.
"""

from __future__ import annotations

from functools import partial

import pandas as pd
import streamlit as st

from src import ui
from src.context import Context, build_context
from src.dataset import dataset_available, dataset_signature, load_dataset
from src.player_aggregation import default_thresholds
from views import (
    matches,
    methodology,
    overview,
    player_compare,
    player_profile,
    player_rankings,
    keepers,
    scouting,
    team_compare,
    team_profile,
    team_rankings,
    team_styles,
)

st.set_page_config(
    page_title="Serie A Observatory",
    page_icon=":material/sports_soccer:",
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.inject_css()
ui.reset_keys()


# --------------------------------------------------------------------------- #
# Caricamento dati
# --------------------------------------------------------------------------- #

@st.cache_data(show_spinner="Loading the dataset…")
def load_data(signature: tuple) -> tuple[pd.DataFrame, pd.DataFrame]:
    return load_dataset()


@st.cache_data(show_spinner=False)
def load_context(
    signature: tuple, giornata: int, single_round: bool, min_minutes: int, min_passes: int,
) -> Context:
    match_stats_df, player_stats_df = load_data(signature)
    return build_context(match_stats_df, player_stats_df, giornata, single_round, min_minutes, min_passes)


if not dataset_available():
    st.error("No dataset in 'data/processed/'. Run `python update_dataset.py` to build it.")
    st.stop()

signature = dataset_signature()
match_stats_df, player_stats_df = load_data(signature)

if match_stats_df.empty:
    st.error("No data available.")
    st.stop()

giornate_disponibili = sorted(match_stats_df["giornata"].dropna().unique().astype(int))
all_teams = sorted(set(match_stats_df["home"]) | set(match_stats_df["away"]))


# --------------------------------------------------------------------------- #
# Barra laterale: filtri globali
# --------------------------------------------------------------------------- #

with st.sidebar:
    st.markdown(
        "<div class='brand'>⚽ Serie A Observatory</div>"
        f"<div class='brand-sub'>Official Match Reports · {len(match_stats_df)} matches · "
        f"{len(giornate_disponibili)} matchdays</div>",
        unsafe_allow_html=True,
    )
    nav_slot = st.container()  # riempito più sotto, quando le pagine sono definite
    st.markdown("<div class='nav-section'>Filters</div>", unsafe_allow_html=True)
    giornata = st.selectbox(
        "Matchday", giornate_disponibili, index=len(giornate_disponibili) - 1, key="giornata",
        help="Last matchday included. The table is always computed up to this matchday.",
    )
    vista = st.segmented_control(
        "Period", ["Season", "Single matchday"], default="Season", required=True, key="vista",
        help="Season: every match up to the selected matchday. Single matchday: the 10 matches of that round.",
    )
    single_round = vista == "Single matchday"
    highlight = st.selectbox(
        "Highlighted team", ["—", *all_teams], format_func=lambda t: t if t == "—" else t.title(),
        key="highlight",
        help="Highlights this team (and its players) in every chart and preselects it in the profile pages.",
    )

    n_giornate_vista = 1 if single_round else len([g for g in giornate_disponibili if g <= giornata])
    default_min, default_passes = default_thresholds(n_giornate_vista, single_round)
    with st.expander("Player thresholds", icon=":material/tune:"):
        st.caption(
            "Minimum to enter per-90 rankings and percentage rankings: "
            "below these thresholds rates are dominated by chance."
        )
        min_minutes = st.slider(
            "Minimum minutes", 0, 90 * n_giornate_vista, default_min, step=9,
            key=f"min_minutes_{n_giornate_vista}_{single_round}",
        )
        min_passes = st.slider(
            "Minimum completed passes", 0, 60 * n_giornate_vista, default_passes, step=5,
            key=f"min_passes_{n_giornate_vista}_{single_round}",
        )

ctx = load_context(signature, int(giornata), single_round, int(min_minutes), int(min_passes))
ctx.highlight_team = None if highlight == "—" else highlight

quality_all = pd.concat([ctx.quality_df, ctx.players.quality_df], ignore_index=True)
if not quality_all["passed"].all():
    ui.callout(
        "<b>Warning:</b> some quality checks fail on this view — "
        "details on the <i>Methodology</i> page.", warn=True,
    )


# --------------------------------------------------------------------------- #
# Navigazione
# --------------------------------------------------------------------------- #

def page(module, title: str, icon: str, url: str, default: bool = False) -> st.Page:
    return st.Page(partial(module.render, ctx), title=title, icon=icon, url_path=url, default=default)


pages = {
    "League": [
        page(overview, "Overview", ":material/dashboard:", "overview", default=True),
        page(matches, "Matches", ":material/scoreboard:", "matches"),
    ],
    "Teams": [
        page(team_rankings, "Team rankings", ":material/leaderboard:", "team-rankings"),
        page(team_styles, "Styles & efficiency", ":material/insights:", "styles"),
        page(team_profile, "Team profile", ":material/shield:", "team-profile"),
        page(team_compare, "Team comparison", ":material/compare_arrows:", "team-comparison"),
    ],
    "Players": [
        page(player_rankings, "Player rankings", ":material/military_tech:", "player-rankings"),
        page(scouting, "Scouting", ":material/person_search:", "scouting"),
        page(player_profile, "Player profile", ":material/person:", "player-profile"),
        page(player_compare, "Player comparison", ":material/group:", "player-comparison"),
        page(keepers, "Goalkeepers", ":material/sports_handball:", "goalkeepers"),
    ],
    "Info": [
        page(methodology, "Methodology & glossary", ":material/menu_book:", "methodology"),
    ],
}

# Menu disegnato a mano (invece di quello automatico) per avere il marchio in
# cima alla barra laterale e i filtri subito sotto le voci.
current = st.navigation(pages, position="hidden")
with nav_slot:
    for section_name, section_pages in pages.items():
        st.markdown(f"<div class='nav-section'>{section_name}</div>", unsafe_allow_html=True)
        for p in section_pages:
            st.page_link(p)
current.run()

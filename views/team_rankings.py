"""Classifiche di squadra metrica per metrica (registro METRIC_PANELS)."""

from __future__ import annotations

import streamlit as st

from src import ui
from src.context import Context
from src.metrics import CATEGORIES, LOWER_IS_BETTER, METRIC_PANELS
from src.plotting import team_ranking_fig

CATEGORY_INTRO = {
    "Attack": "How much, and how, teams get to shoot.",
    "Passing": "How teams build up: volume, accuracy, verticality and creativity.",
    "Defence": "How much teams concede, how much they win back and how many fouls they commit.",
}


def render(ctx: Context) -> None:
    ui.page_header(
        ctx.eyebrow, "Team rankings",
        "All 20 teams ranked on every Match Report statistic, as an average per match. "
        "The dotted line is the league average: bars reaching past it are above average. "
        "Pick a highlighted team in the sidebar to follow it across every chart.",
    )
    category = st.segmented_control("Area of play", CATEGORIES, default=CATEGORIES[0], required=True, key="team_rank_cat")
    st.caption(CATEGORY_INTRO[category])

    panels = [p for p in METRIC_PANELS if p.category == category]
    for i in range(0, len(panels), 2):
        cols = st.columns(2, gap="medium")
        for col, panel in zip(cols, panels[i : i + 2]):
            with col:
                note = " Lower is better here: the best team is at the top." if panel.avg_col in LOWER_IS_BETTER else ""
                with ui.card(panel.title, panel.description + note):
                    ui.chart(team_ranking_fig(ctx.team_summary_df, panel, ctx.highlight_team))

    ui.section("Full table", "Every team average in one sortable table (click a header).")
    cols = ["rank", "team", "matches", "points", "goals_for", "goals_against", "style_score", *[p.avg_col for p in METRIC_PANELS]]
    ui.data_table(ctx.team_summary_df, cols, scope="team")

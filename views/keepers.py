"""Portieri: scheda separata (per loro PA = Parate)."""

from __future__ import annotations

import streamlit as st

from src import ui
from src.context import Context
from src.glossary import PLAYER_METRICS
from src.plotting import player_ranking_fig, player_scatter_fig


def render(ctx: Context) -> None:
    ui.page_header(
        ctx.eyebrow, "Goalkeepers",
        "Goalkeepers have their own statistics in the Match Report (goals conceded, saves, parries, long balls) and "
        "are analysed separately. Note: for them the code PA means <b>saves</b>, not forward passes.",
    )
    gk = ctx.players.keepers
    if gk.empty:
        st.info("No goalkeeper data for this view.")
        return
    eligible = gk[gk["eligible_rates"]]
    ui.callout(f"<b>{len(eligible)}</b> of {len(gk)} goalkeepers pass the <b>{ctx.players.min_minutes}'</b> threshold.")

    specs = [
        ("save_pct", {"pct": True, "decimals": 1}),
        ("saves_per90", {"decimals": 2}),
        ("goals_conceded_per90", {"decimals": 2, "lowest": True}),
        ("clean_sheets", {"decimals": 0}),
    ]
    for i in range(0, len(specs), 2):
        cols = st.columns(2, gap="medium")
        for col, (metric, kw) in zip(cols, specs[i : i + 2]):
            info = PLAYER_METRICS[metric]
            note = " Ranked from the lowest value." if kw.get("lowest") else ""
            with col:
                with ui.card(info.label, info.description + note):
                    ui.chart(player_ranking_fig(eligible, metric, info.label, highlight_team=ctx.highlight_team, **kw))

    with ui.card(
        "Workload vs performance",
        "Saves per 90 (how busy the keeper is) against save % (how effective). Colour = team league position.",
        how_to="Top right: busy keepers who hold up — often the most valuable for teams at the bottom of the table. "
               "Top left: keepers rarely called upon but effective when needed. Save % does not account for shot "
               "difficulty: read it carefully when the number of shots is small.",
    ):
        ui.chart(player_scatter_fig(eligible, "saves_per90", "save_pct", "Saves/90", "Save %",
                                    ctx.highlight_team, label_n=6, height=480))

    ui.section("All goalkeepers")
    ui.data_table(gk, ["player", "team", "team_rank", "matches", "minutes", "goals_conceded", "saves", "save_pct",
                       "goals_conceded_per90", "saves_per90", "respinte", "long_balls", "clean_sheets", "amm"])

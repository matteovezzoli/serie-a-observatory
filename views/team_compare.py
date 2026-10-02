"""Confronto squadre: 2-3 squadre sugli stessi percentili, più gli scontri diretti."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import ui
from src.analysis import team_percentiles
from src.context import Context
from src.metrics import METRIC_PANELS
from src.plotting import comparison_dots_fig


def render(ctx: Context) -> None:
    ui.page_header(
        ctx.eyebrow, "Team comparison",
        "Two or three teams on the same scale: for each statistic, the league percentile, so very different "
        "metrics (400 passes, 12 shots) become comparable at a glance.",
    )
    teams = list(ctx.standings_df["team"])
    default = [ctx.highlight_team] if ctx.highlight_team else []
    default += [t for t in teams[:2] if t not in default]
    chosen = st.multiselect("Teams to compare (max 3)", teams, default=default[:2], max_selections=3,
                            format_func=str.title, key="team_compare_sel")
    chosen = [t for t in chosen if t in set(ctx.team_summary_df["team"])]
    if len(chosen) < 2:
        st.info("Select at least two teams with matches in the current view.")
        return

    pct = team_percentiles(ctx.team_summary_df).set_index("team")
    raw = ctx.team_summary_df.set_index("team")
    labels = {p.avg_col: p.title.replace(" per match", "") for p in METRIC_PANELS}
    long = pd.DataFrame([
        {"entity": t.title(), "metric": p.avg_col, "value": raw.loc[t, p.avg_col], "percentile": pct.loc[t, p.avg_col]}
        for t in chosen for p in METRIC_PANELS
    ])

    c = st.columns(len(chosen))
    for col, t in zip(c, chosen):
        r = ctx.standings_df.set_index("team").loc[t]
        col.metric(t.title(), f"{ui.ordinal(r['rank'])} · {int(r['points'])} pts", border=True,
                   help=f"Goals {int(r['goals_for'])}–{int(r['goals_against'])}")

    with ui.card(
        "Profiles compared",
        "One dot per team on each statistic; the grey segment shows the gap between the highest and the lowest.",
        how_to="Percentile 100 = highest value in the league on that statistic, 0 = the lowest. Long segments show "
               "where the teams really differ; overlapping dots, where they are alike. For shots conceded and fouls "
               "a high value is not a strength.",
    ):
        ui.chart(comparison_dots_fig(long, labels, [p.avg_col for p in METRIC_PANELS]))

    with ui.card("Actual values", "The per-match averages behind the percentiles."):
        table = raw.loc[chosen, [p.avg_col for p in METRIC_PANELS]].T
        table.index = [labels[i] for i in table.index]
        table.columns = [t.title() for t in chosen]
        st.dataframe(table.style.format("{:.1f}"), width="stretch")

    h2h = ctx.dati_vista[ctx.dati_vista["home"].isin(chosen) & ctx.dati_vista["away"].isin(chosen)]
    if not h2h.empty:
        with ui.card("Head-to-head matches in the view"):
            st.markdown("".join(ui.result_chip(r["home"], r["away"], int(r["home_score"]), int(r["away_score"]))
                                for _, r in h2h.iterrows()), unsafe_allow_html=True)

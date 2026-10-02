"""Confronto giocatori: 2-3 giocatori sugli stessi percentili."""

from __future__ import annotations

import streamlit as st

from src import ui
from src.analysis import PROFILE_METRICS, player_percentiles
from src.context import Context
from src.glossary import PLAYER_METRICS
from src.plotting import comparison_dots_fig

COMPARE_METRICS = PROFILE_METRICS + ["key_pass_share_pct", "shot_share_pct", "recovery_share_pct"]


def render(ctx: Context) -> None:
    ui.page_header(
        ctx.eyebrow, "Player comparison",
        "Up to three players on the same percentile scale: useful to choose between transfer alternatives or to "
        "see how two seemingly similar profiles actually differ.",
    )
    out = ctx.players.outfield
    eligible = out[out["eligible_rates"]].sort_values("minutes", ascending=False) if not out.empty else out
    if eligible.empty:
        st.info("No players above the minutes threshold in this view.")
        return
    keys = [f"{r.player} · {r.team.title()}" for r in eligible.itertuples()]
    lookup = dict(zip(keys, zip(eligible["player"], eligible["team"])))
    default = keys[:2]
    if ctx.highlight_team:
        own = [k for k, (_, t) in lookup.items() if t == ctx.highlight_team][:1]
        default = own + [k for k in keys if k not in own][:1]
    chosen = st.multiselect("Players (max 3, only above the minutes threshold)", keys, default=default, max_selections=3, key="pc_players")
    if not chosen:
        st.info("Select at least one player.")
        return
    targets = [lookup[k] for k in chosen]

    cols = st.columns(len(targets))
    for col, (player, team) in zip(cols, targets):
        r = eligible[(eligible["player"] == player) & (eligible["team"] == team)].iloc[0]
        col.metric(f"{player} · {team.title()}", f"{r['minutes']:.0f}'", border=True,
                   help=f"{int(r['matches'])} apps · {int(r['goals'])} goals · {int(r['assists'])} assists · "
                        f"team {ui.ordinal(r['team_rank'])} in the table")

    long = player_percentiles(out, targets, COMPARE_METRICS)
    labels = {k: v.label for k, v in PLAYER_METRICS.items()}
    with ui.card(
        "Profiles compared",
        "One dot per player on each statistic (percentile among all eligible players). The grey segment is the gap "
        "between the best and the worst of the group.",
        how_to="Look at the long segments first: they are the statistics that really set the chosen players apart. "
               "Hover a dot for the actual value.",
    ):
        ui.chart(comparison_dots_fig(long, labels, COMPARE_METRICS))

    with ui.card("Actual values"):
        table = long.pivot_table(index="metric", columns="entity", values="value").reindex(COMPARE_METRICS).dropna(how="all")
        table.index = [labels[m] for m in table.index]
        st.dataframe(table[[f"{p} · {t.title()}" for p, t in targets if f"{p} · {t.title()}" in table.columns]]
                     .style.format("{:.2f}"), width="stretch")

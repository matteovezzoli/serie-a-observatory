"""Classifiche giocatori: per 90', totali, efficienza, disciplina."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import ui
from src.context import Context
from src.glossary import PLAYER_METRICS
from src.plotting import player_ranking_fig, player_scatter_fig

PER90 = [
    "goals_per90", "assists_per90", "goal_contributions_per90", "shots_per90", "shots_on_target_per90",
    "big_chances_per90", "key_passes_per90", "recoveries_per90", "passes_completed_per90",
    "forward_passes_per90", "touches_per90", "fouls_suffered_per90",
]
TOTALS = ["goals", "assists", "goal_contributions", "shots", "shots_on_target", "key_passes",
          "recoveries", "woodwork", "passes_completed", "minutes"]
EFFICIENCY = ["pass_accuracy_pct", "shot_accuracy_pct", "conversion_pct", "forward_play_incidence_pct"]


def _grid(ctx: Context, df: pd.DataFrame, metrics: list[str], n: int) -> None:
    for i in range(0, len(metrics), 2):
        cols = st.columns(2, gap="medium")
        for col, metric in zip(cols, metrics[i : i + 2]):
            info = PLAYER_METRICS[metric]
            decimals = 0 if info.kind == "count" else 1 if info.kind in ("pct", "share") else 2
            with col:
                with ui.card(info.label, info.description):
                    ui.chart(player_ranking_fig(df, metric, info.label, n=n, pct=info.kind in ("pct", "share"),
                                                decimals=decimals, highlight_team=ctx.highlight_team))


def render(ctx: Context) -> None:
    ui.page_header(
        ctx.eyebrow, "Player rankings",
        "Who leads the league, statistic by statistic. <b>Per-90</b> rankings compare players with different "
        "minutes and only include those who have played enough; <b>totals</b> also reward regular playing time.",
    )
    out = ctx.players.outfield
    if out.empty:
        st.info("No player data for this view.")
        return
    eligible = out[out["eligible_rates"]]
    ui.callout(
        f"<b>{len(eligible)}</b> of {len(out)} outfield players pass the threshold of "
        f"<b>{ctx.players.min_minutes}'</b> played (adjustable under <i>Player thresholds</i> in the sidebar). "
        + ("With a highlighted team, its players are coloured and everyone else is grey." if ctx.highlight_team else "")
    )

    c1, c2 = st.columns([3, 1])
    with c1:
        group = st.segmented_control("Category", ["Per 90", "Totals", "Efficiency", "Discipline", "Custom ranking"],
                                     default="Per 90", required=True, key="player_rank_group")
    with c2:
        n = st.slider("Players per ranking", 5, 25, 10, key="player_rank_n")

    if group == "Per 90":
        _grid(ctx, eligible, PER90, n)
    elif group == "Totals":
        st.caption("Absolute volumes in the view, with no minutes threshold.")
        _grid(ctx, out, TOTALS, n)
    elif group == "Efficiency":
        st.caption(f"Pass accuracy: at least {ctx.players.min_passes} completed passes. Shot accuracy and conversion: at least 5 shots.")
        pools = {"pass_accuracy_pct": out[out["eligible_pct"]]}
        for i in range(0, len(EFFICIENCY), 2):
            cols = st.columns(2, gap="medium")
            for col, metric in zip(cols, EFFICIENCY[i : i + 2]):
                info = PLAYER_METRICS[metric]
                with col:
                    with ui.card(info.label, info.description):
                        ui.chart(player_ranking_fig(pools.get(metric, eligible), metric, info.label, n=n, pct=True,
                                                    decimals=1, highlight_team=ctx.highlight_team))
        with ui.card(
            "Passing volume vs verticality",
            "Verticality alone depends on role (forwards play almost only forward): read together with volume it "
            "separates vertical playmakers, top right, from target forwards, top left.",
        ):
            ui.chart(player_scatter_fig(out[out["eligible_pct"]], "passes_completed_per90", "forward_play_incidence_pct",
                                        "Completed passes/90", "Verticality (%)", ctx.highlight_team))
    elif group == "Discipline":
        left, right = st.columns([1, 1], gap="medium")
        with left:
            with ui.card(PLAYER_METRICS["yellow_equivalent"].label, PLAYER_METRICS["yellow_equivalent"].description):
                ui.chart(player_ranking_fig(out[out["yellow_equivalent"] > 0], "yellow_equivalent", "Yellow equivalent",
                                            n=n, decimals=0, highlight_team=ctx.highlight_team))
        with right:
            with ui.card("Sendings-off", "Every red card in the view, with the type of dismissal."):
                log = ctx.players.match_log
                reds = log[log[["DAM", "ESP"]].notna().any(axis=1)].copy()
                if reds.empty:
                    st.write("No sendings-off in the current view.")
                else:
                    reds["tipo"] = reds["DAM"].notna().map({True: "Second yellow", False: "Straight red"})
                    reds["match"] = reds["match_id"].str.replace(r"^G\d+_", "", regex=True).str.replace("_", " – ").str.title()
                    st.dataframe(reds[["giornata", "match", "team", "player", "tipo"]].rename(columns={
                        "giornata": "MD", "match": "Match", "team": "Team", "player": "Player", "tipo": "Type"}),
                        hide_index=True, width="stretch")
            with ui.card("Fouls won", PLAYER_METRICS["fouls_suffered"].description):
                ui.chart(player_ranking_fig(out, "fouls_suffered", "Fouls won", n=min(n, 10), decimals=0,
                                            highlight_team=ctx.highlight_team))
        ui.data_table(out[out["yellow_equivalent"] > 0].sort_values(["yellow_equivalent", "esp"], ascending=False),
                      ["player", "team", "matches", "minutes", "amm", "dam", "direct_reds", "yellow_equivalent"])
    else:
        numeric = [k for k, v in PLAYER_METRICS.items() if v.kind in ("count", "rate", "pct", "share")
                   and k in out.columns and v.group not in ("Profile", "Goalkeepers")]
        left, right = st.columns([2, 1])
        with left:
            metric = st.selectbox("Statistic", numeric, format_func=lambda k: f"{PLAYER_METRICS[k].group} · {PLAYER_METRICS[k].label}",
                                  index=numeric.index("key_passes_per90"), key="free_metric")
        with right:
            only_eligible = st.toggle("Only players above the threshold", value=True, key="free_eligible")
        info = PLAYER_METRICS[metric]
        pool = eligible if only_eligible else out
        with ui.card(info.label, info.description):
            ui.chart(player_ranking_fig(pool, metric, info.label, n=n, pct=info.kind in ("pct", "share"),
                                        decimals=0 if info.kind == "count" else 2, highlight_team=ctx.highlight_team))

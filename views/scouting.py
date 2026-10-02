"""Scouting: isolare il talento individuale dal contesto squadra."""

from __future__ import annotations

import streamlit as st

from src import ui
from src.analysis import PROFILE_METRICS
from src.context import Context
from src.glossary import PLAYER_METRICS
from src.plotting import player_ranking_fig, player_scatter_fig

SHARES = ["key_pass_share_pct", "shot_share_pct", "recovery_share_pct", "pass_share_pct", "goal_share_pct"]
AXIS_OPTIONS = PROFILE_METRICS + SHARES


def render(ctx: Context) -> None:
    ui.page_header(
        ctx.eyebrow, "Scouting",
        "Finding players who perform above the context they play in. In a weak team absolute volumes are low for "
        "everyone, so this page looks at per-90 rates, <b>shares of their own team's output</b> and percentiles, "
        "filtered by league position.",
    )
    out = ctx.players.outfield
    if out.empty:
        st.info("No player data for this view.")
        return
    eligible = out[out["eligible_rates"]]
    n_teams = int(ctx.standings_df["team"].nunique())

    with ui.card("Search scope", "Which teams to search. The default is the bottom half of the table."):
        c1, c2 = st.columns([2, 1])
        with c1:
            lo, hi = st.slider(
                f"Team league position (after matchday {ctx.giornata})", 1, n_teams,
                (n_teams // 2 + 1, n_teams), key="scout_range",
                help="1–20 = all teams. The 'bottom half' cut-off is a choice, not a truth: adjust it.",
            )
        with c2:
            st.metric("Players in scope", int(eligible["team_rank"].between(lo, hi).sum()), border=True,
                      help=f"Outfield players with at least {ctx.players.min_minutes}' in the selected teams.")
    pool = eligible[eligible["team_rank"].between(lo, hi)]
    teams_in = ctx.standings_df[ctx.standings_df["rank"].between(lo, hi)]["team"].str.title()
    st.caption("Teams: " + ", ".join(teams_in))

    tab_share, tab_map, tab_search = st.tabs(["Weight in the team", "Profile map", "Profile search"])

    with tab_share:
        ui.callout(
            "The <b>share</b> tells how much of the team's output goes through a player, only in the matches they "
            "played. It is already normalised: 25% of the key passes weighs the same in a team making 8 per match "
            "or 4. It is the most direct measure of 'the player carrying the team'."
        )
        for i in range(0, len(SHARES), 2):
            cols = st.columns(2, gap="medium")
            for col, metric in zip(cols, SHARES[i : i + 2]):
                info = PLAYER_METRICS[metric]
                with col:
                    with ui.card(info.label, info.description):
                        ui.chart(player_ranking_fig(pool, metric, info.label, pct=True, decimals=1,
                                                    highlight_team=ctx.highlight_team))

    with tab_map:
        c1, c2 = st.columns(2)
        fmt = lambda k: PLAYER_METRICS[k].label
        with c1:
            x = st.selectbox("Horizontal axis", AXIS_OPTIONS, index=AXIS_OPTIONS.index("key_passes_per90"), format_func=fmt, key="scout_x")
        with c2:
            y = st.selectbox("Vertical axis", AXIS_OPTIONS, index=AXIS_OPTIONS.index("recoveries_per90"), format_func=fmt, key="scout_y")
        with ui.card(
            f"{fmt(x)} vs {fmt(y)}",
            "Each dot is a player in scope. Size = minutes played; colour = their team's league position "
            "(darker = lower in the table). The most extreme profiles are labelled, the rest on hover.",
            how_to="The dotted lines are the medians of the scope: top right are players above the median on both "
                   "statistics. With the defaults (key passes and recoveries) these are players who contribute in "
                   "both phases — the profile a single score would hide.",
        ):
            ui.chart(player_scatter_fig(pool, x, y, fmt(x), fmt(y), ctx.highlight_team, height=600))

    with tab_search:
        st.markdown(
            "Pick the statistics that matter for the profile you are looking for and a minimum percentile: the table shows "
            "who clears **all** of them. Percentiles are computed on every eligible player in the league, not only the scope."
        )
        c1, c2 = st.columns([3, 1])
        with c1:
            metrics = st.multiselect("Required statistics", AXIS_OPTIONS, default=["key_passes_per90", "recoveries_per90"],
                                     format_func=lambda k: PLAYER_METRICS[k].label, key="scout_metrics")
        with c2:
            threshold = st.slider("Minimum percentile", 0, 95, 70, step=5, key="scout_threshold")
        ranked = eligible.copy()
        for m in metrics:
            ranked[f"{m}__pct"] = ranked[m].rank(pct=True) * 100
        hits = pool.merge(ranked[["player", "team", *[f"{m}__pct" for m in metrics]]], on=["player", "team"])
        if metrics:
            hits = hits[(hits[[f"{m}__pct" for m in metrics]] >= threshold).all(axis=1)]
            hits = hits.assign(score=hits[[f"{m}__pct" for m in metrics]].mean(axis=1)).sort_values("score", ascending=False)
        st.metric("Players found", len(hits), border=True)
        ui.data_table(hits, ["player", "team", "team_rank", "minutes", *metrics, "goals", "assists",
                             "key_pass_share_pct", "recovery_share_pct"], height=min(40 + 35 * max(len(hits), 1), 560))
        st.download_button(
            "Download results (CSV)", hits.drop(columns=[c for c in hits.columns if c.endswith("__pct")]).to_csv(index=False).encode("utf-8"),
            file_name=f"scouting_MD{ctx.giornata}.csv", mime="text/csv", icon=":material/download:",
        )

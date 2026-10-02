"""Scheda squadra: profilo, andamento, partite e giocatori chiave."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import ui
from src.analysis import home_away_split, team_percentiles
from src.context import Context
from src.glossary import CORE_METRIC_LABELS, MetricInfo
from src.metrics import METRIC_PANELS
from src.parsing import CORE_METRICS
from src.plotting import percentile_bars_fig, team_trend_fig

MATCH_COLS = {
    "giornata": MetricInfo("MD", "Matchday.", "count"),
    "opponent": MetricInfo("Opponent", "", "text"),
    "venue": MetricInfo("Venue", "Home or away.", "text"),
    "score": MetricInfo("Score", "Goals scored – goals conceded.", "text"),
    "result": MetricInfo("Result", "W/D/L.", "text"),
    **{m: MetricInfo(CORE_METRIC_LABELS[m], "", "pct" if "%" in m else "count") for m in CORE_METRICS},
}


def render(ctx: Context) -> None:
    teams = list(ctx.standings_df["team"])
    default = teams.index(ctx.highlight_team) if ctx.highlight_team in teams else 0
    ui.page_header(
        ctx.eyebrow, "Team profile",
        "A team's full profile: where it stands against the rest of the league, how it has changed match after "
        "match and which players carry its output.",
    )
    team = st.selectbox("Team", teams, index=default, format_func=str.title, key="team_profile_sel")
    if team not in set(ctx.team_summary_df["team"]):
        st.info(f"{team.title()} has no matches in the current view.")
        return
    row = ctx.team_summary_df.set_index("team").loc[team]
    stand = ctx.standings_df.set_index("team").loc[team]

    c = st.columns(6)
    c[0].metric("Position", ui.ordinal(stand["rank"]), border=True, help="Real league position at the selected matchday.")
    c[1].metric("Points", int(stand["points"]), border=True, help="League points at the selected matchday.")
    c[2].metric("W · D · L", f"{int(row['wins'])} · {int(row['draws'])} · {int(row['losses'])}", border=True)
    c[3].metric("Goals F · A", f"{int(row['goals_for'])} · {int(row['goals_against'])}", border=True,
                help="Goals scored and conceded in the current view.")
    c[4].metric("Shots/match", f"{row['shots_avg']:.1f}", border=True,
                help=f"League average: {ctx.team_summary_df['shots_avg'].mean():.1f}")
    c[5].metric("Style", f"{row['style_score']:.0f}/100", border=True,
                help="Average percentile of pass accuracy, final-third penetration and verticality.")
    st.markdown(f"**Recent form** &nbsp; {ui.form_badges(ctx.form.get(team, []))}", unsafe_allow_html=True)

    st.write("")
    left, right = st.columns([1, 1.25], gap="medium")
    with left:
        pct = team_percentiles(ctx.team_summary_df).set_index("team").loc[team]
        profile = pd.DataFrame({
            "metric": [p.avg_col for p in METRIC_PANELS],
            "value": [row[p.avg_col] for p in METRIC_PANELS],
            "percentile": [pct[p.avg_col] for p in METRIC_PANELS],
        })
        with ui.card(
            "League profile",
            "Percentile on each statistic against the other teams (100 = highest value in the league).",
            how_to="A bar past the 'median' line means a value higher than half of the teams. Careful with defensive "
                   "metrics: a high percentile on shots conceded or fouls is a high value, not a strength.",
        ):
            ui.chart(percentile_bars_fig(profile, {p.avg_col: p.title.replace(" per match", "") for p in METRIC_PANELS},
                                          x_title="Percentile among teams"))
    with right:
        panel_by_title = {p.title: p for p in METRIC_PANELS}
        with ui.card("Match by match", "A statistic of your choice over time, against the league average on that matchday."):
            chosen = st.selectbox("Statistic", list(panel_by_title), key="team_trend_metric", label_visibility="collapsed")
            panel = panel_by_title[chosen]
            ui.chart(team_trend_fig(ctx.team_match_df, team, panel.column, panel.x_title, pct=panel.pct))
        split = home_away_split(ctx.team_match_df)
        if not ctx.single_round and not split.empty and {"ppg_home", "ppg_away"} <= set(split.columns):
            s = split.set_index("team").loc[team]
            with ui.card("Home and away", "Average output per match at each venue."):
                h, a = st.columns(2)
                h.metric("Home · points/match", f"{s['ppg_home']:.2f}", border=True,
                         help=f"{int(s['matches_home'])} matches · goals {s['gf_home']:.1f}–{s['ga_home']:.1f} per match")
                a.metric("Away · points/match", f"{s['ppg_away']:.2f}", border=True,
                         help=f"{int(s['matches_away'])} matches · goals {s['gf_away']:.1f}–{s['ga_away']:.1f} per match")

    ui.section("Matches played", "Every team statistic for each match in the view.")
    games = ctx.team_match_df[ctx.team_match_df["team"] == team].sort_values("giornata").copy()
    games["opponent"] = games["opponent"].str.title()
    games["venue"] = games["venue"].map({"home": "Home", "away": "Away"})
    games["score"] = games["goals_for"].astype(int).astype(str) + "–" + games["goals_against"].astype(int).astype(str)
    ui.data_table(games, list(MATCH_COLS), extra=MATCH_COLS)

    ui.section("Key players", "Who produces the most, and how much of the team's output goes through them.")
    out = ctx.players.outfield[ctx.players.outfield["team"] == team].sort_values("minutes", ascending=False)
    if out.empty:
        st.info("No player data for this team.")
        return
    c = st.columns(4)
    for col, (kicker, metric, fmt) in zip(c, [
        ("Top scorer", "goals", "{:.0f} goals"), ("Most assists", "assists", "{:.0f} assists"),
        ("Most key passes", "key_passes", "{:.0f}"), ("Most recoveries", "recoveries", "{:.0f}"),
    ]):
        best = out.sort_values([metric, "minutes"], ascending=[False, True]).iloc[0]
        with col:
            ui.leader_card(kicker, fmt.format(best[metric]), best["player"], f"{best['minutes']:.0f}' played")
    st.write("")
    ui.data_table(out, [
        "player", "matches", "minutes", "goals", "assists", "shots", "key_passes", "recoveries", "pass_accuracy_pct",
        "shot_share_pct", "key_pass_share_pct", "recovery_share_pct", "yellow_equivalent",
    ])
    gk = ctx.players.keepers[ctx.players.keepers["team"] == team]
    if not gk.empty:
        ui.data_table(gk, ["player", "matches", "minutes", "goals_conceded", "saves", "save_pct", "clean_sheets"])

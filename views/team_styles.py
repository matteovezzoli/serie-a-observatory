"""Stili ed efficienza: mappa percentili, identità di gioco, efficienza
offensiva/difensiva, rendimento casa/trasferta."""

from __future__ import annotations

import streamlit as st

from src import ui
from src.analysis import home_away_split, team_percentiles
from src.context import Context
from src.metrics import METRIC_PANELS, MetricPanel
from src.plotting import dumbbell_fig, percentile_heatmap_fig, team_ranking_fig, team_scatter_fig


def render(ctx: Context) -> None:
    ui.page_header(
        ctx.eyebrow, "Styles & efficiency",
        "Not just how much teams produce, but <b>how</b> they play and how much they get out of it: playing identity, "
        "efficiency in front of goal and in defence, home vs away differences.",
    )
    summary = ctx.team_summary_df.copy()
    summary["gf_pg"] = summary["goals_for"] / summary["matches"]
    summary["ga_pg"] = summary["goals_against"] / summary["matches"]

    # --- Mappa del campionato
    cols = [p.avg_col for p in METRIC_PANELS]
    labels = {p.avg_col: p.title.replace(" per match", "") for p in METRIC_PANELS}
    with ui.card(
        "League map",
        "Each cell is a team's average on one statistic; the colour is its percentile against the other 19 teams "
        "(dark blue = among the highest values in the league). Teams in table order.",
        how_to="Read a <b>row</b> for a team's profile (where it excels, where it is weak), a <b>column</b> to see "
               "who dominates a statistic. Colour means a high value, not necessarily a good one: for shots "
               "conceded and fouls, dark blue means 'concedes/commits a lot'.",
    ):
        ui.chart(percentile_heatmap_fig(team_percentiles(summary, cols), summary, cols, labels))

    # --- Identità di gioco
    ui.section("Playing identity", "How teams build up, regardless of results.")
    left, right = st.columns([1.3, 1], gap="medium")
    with left:
        with ui.card(
            "Style map",
            "Verticality (share of passes played forward) against pass accuracy. Dot size = league points.",
            how_to="The dotted lines are the league medians and split four styles. Top left: patient ball "
                   "circulation; bottom right: teams that go forward immediately and accept more errors. No quadrant "
                   "is 'right': it is a snapshot of playing identity.",
        ):
            ui.chart(team_scatter_fig(
                summary, "forward_incidence_avg", "pass_accuracy_avg",
                "Verticality (% of passes forward)", "Pass accuracy (%)", ctx.highlight_team,
                quadrants={"tl": "Patient possession", "tr": "Vertical and accurate",
                           "bl": "Struggling build-up", "br": "Direct play"},
                x_pct=True, y_pct=True,
            ))
    with right:
        with ui.card(
            "Style index",
            "Average percentile of pass accuracy, final-third penetration and verticality (0–100): high = a team that "
            "builds up cleanly and gets forward.",
        ):
            panel = MetricPanel("style_score", "style_score", "Style index", "Style index (0–100)")
            ui.chart(team_ranking_fig(summary, panel, ctx.highlight_team))

    # --- Efficienza
    ui.section("Efficiency", "What the volumes are worth: shots turned into goals, shots conceded turned into goals against.")
    left, right = st.columns(2, gap="medium")
    with left:
        with ui.card(
            "Attacking efficiency",
            "Shots per match against goals scored per match.",
            how_to="Top left: clinical teams (few shots, many goals). Bottom right: teams that shoot a lot but score "
                   "little — often a sign of low-quality shooting positions or bad luck, which tends to even out over time.",
        ):
            ui.chart(team_scatter_fig(
                summary, "shots_avg", "gf_pg", "Shots per match", "Goals scored per match", ctx.highlight_team,
                quadrants={"tl": "Clinical", "tr": "Many shots, many goals", "bl": "Struggling attack", "br": "Shooting but not scoring"},
            ))
    with right:
        with ui.card(
            "Defensive solidity",
            "Shots conceded per match against goals conceded per match. The best defences sit bottom left.",
            how_to="Bottom left: concede few shots and few goals. Top left: concede few shots but those few go in "
                   "(high-quality chances allowed or a struggling keeper). Bottom right: under siege, but the goal holds.",
        ):
            ui.chart(team_scatter_fig(
                summary, "shots_conceded_avg", "ga_pg", "Shots conceded per match", "Goals conceded per match", ctx.highlight_team,
                quadrants={"bl": "Solid defence", "br": "Under pressure but holding",
                           "tl": "Conceding more than allowed", "tr": "Defence in trouble"},
            ))

    # --- Casa e trasferta
    ui.section("Home and away", "Home advantage, team by team.")
    split = home_away_split(ctx.team_match_df)
    if ctx.single_round or split.empty or {"ppg_home", "ppg_away"} - set(split.columns):
        st.info("The home/away comparison needs the Season view with at least two matchdays.")
        return
    with ui.card(
        "Points per match: home vs away",
        "Each row links home (blue) and away (orange) performance. The longer the segment, the more the team relies on "
        "home advantage. Teams sorted by gap.",
    ):
        ui.chart(dumbbell_fig(split, "team", "ppg_home", "ppg_away", "Home", "Away", "Points per match", ctx.highlight_team))
    st.caption("With few matchdays each team has played only 2–3 matches per venue: gaps are still heavily shaped by the fixture list.")

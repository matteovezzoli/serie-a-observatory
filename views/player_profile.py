"""Scheda giocatore: profilo percentile, peso in squadra, partita per partita
e giocatori con profilo simile."""

from __future__ import annotations

import streamlit as st

from src import ui
from src.analysis import PROFILE_METRICS, player_match_series, player_percentiles, similar_players
from src.context import Context
from src.glossary import PLAYER_METRICS, MetricInfo
from src.plotting import percentile_bars_fig, player_match_bars_fig
from views.matches import OUTFIELD_LOG

MATCH_METRICS = {"G": "Goals", "AS": "Assists", "T": "Shots", "TP": "On target", "PC": "Key passes",
                 "P": "Passes", "PA": "Forward passes", "R": "Recoveries", "PG": "Touches",
                 "FS": "Fouls won", "MIN": "Minutes"}


def render(ctx: Context) -> None:
    ui.page_header(
        ctx.eyebrow, "Player profile",
        "An outfield player's full profile: where they rank in the league, how much they weigh in their team, "
        "how they played match by match and who resembles them statistically.",
    )
    out = ctx.players.outfield
    if out.empty:
        st.info("No player data for this view.")
        return

    teams = sorted(out["team"].unique())
    c1, c2 = st.columns(2)
    with c1:
        team = st.selectbox("Team", teams, format_func=str.title, key="pp_team",
                            index=teams.index(ctx.highlight_team) if ctx.highlight_team in teams else 0)
    roster = out[out["team"] == team].sort_values("minutes", ascending=False)
    with c2:
        player = st.selectbox("Player", list(roster["player"]), key="pp_player",
                              format_func=lambda p: f"{p} · {roster.set_index('player').loc[p, 'minutes']:.0f}'")
    p = roster[roster["player"] == player].iloc[0]

    c = st.columns(6)
    c[0].metric("Apps · min", f"{int(p['matches'])} · {p['minutes']:.0f}'", border=True, help="Appearances and minutes played.")
    c[1].metric("Goals · assists", f"{int(p['goals'])} · {int(p['assists'])}", border=True)
    c[2].metric("Shots (OT)", f"{int(p['shots'])} ({int(p['shots_on_target'])})", border=True, help="Total shots and, in brackets, shots on target.")
    c[3].metric("Key passes", int(p["key_passes"]), border=True, help=PLAYER_METRICS["key_passes"].description)
    c[4].metric("Recoveries", int(p["recoveries"]), border=True)
    c[5].metric("Accuracy", "—" if p["passes_completed"] == 0 else f"{p['pass_accuracy_pct']:.0f}%", border=True,
                help=PLAYER_METRICS["pass_accuracy_pct"].description)

    eligible = bool(p["eligible_rates"])
    if not eligible:
        ui.callout(
            f"{player} has played {p['minutes']:.0f}' in this view, below the {ctx.players.min_minutes}' threshold: "
            "percentiles and similar players are hidden because over so few minutes they would be dominated by chance. "
            "You can lower the threshold under <i>Player thresholds</i>.", warn=True,
        )

    st.write("")
    left, right = st.columns([1.1, 1], gap="medium")
    with left:
        if eligible:
            profile = player_percentiles(out, [(player, team)], PROFILE_METRICS)
            n_pool = int(out["eligible_rates"].sum())
            with ui.card(
                "Percentile profile",
                f"Rank on each statistic against the league's {n_pool} eligible outfield players.",
                how_to="Percentile 90 = better than 90% of eligible players on that statistic. The pool includes "
                       "every role (the PDF does not report positions): a defender will have low percentiles on "
                       "shooting by definition — what matters is the comparison with similar players, on the right.",
            ):
                ui.chart(percentile_bars_fig(profile, {k: v.label for k, v in PLAYER_METRICS.items()}))
    with right:
        with ui.card("Weight in the team", "Share of the team's output going through the player, in matches played."):
            shares = [("key_pass_share_pct", "Key passes"), ("shot_share_pct", "Shots"),
                      ("recovery_share_pct", "Recoveries"), ("pass_share_pct", "Passes"), ("goal_share_pct", "Goals")]
            for metric, name in shares:
                v = p[metric]
                st.progress(min(float(v) / 40, 1.0) if v == v else 0.0,
                            text=f"{name}: **{'—' if v != v else f'{v:.1f}%'}**")
            st.caption("Full bar = 40% or more of the team's output.")
        if eligible:
            sim = similar_players(out, player, team)
            with ui.card(
                "Similar profiles",
                "Players with the most similar combination of per-90 statistics, across the whole league.",
                how_to="Cosine similarity on standardised per-90 values: 100 = the same profile in proportion. It "
                       "ignores role and opponent quality: it is a starting point for scouting (alternatives with "
                       "similar traits), not an assessment.",
            ):
                ui.data_table(sim, ["player", "team", "minutes", "similarity"])

    ui.section("Match by match")
    series = player_match_series(ctx.players.match_log, player, team)
    with ui.card("Trend", "A statistic of your choice, match by match."):
        metric = st.segmented_control("Statistic", list(MATCH_METRICS), default="PC", required=True,
                                      format_func=MATCH_METRICS.get, key="pp_series_metric", label_visibility="collapsed")
        ui.chart(player_match_bars_fig(series, metric, MATCH_METRICS[metric]))
    series = series.assign(match=series["match_id"].str.replace(r"^G\d+_", "", regex=True).str.replace("_", " – ").str.title())
    ui.data_table(series, ["giornata", "match", *[c for c in OUTFIELD_LOG if c not in ("jersey", "player")]],
                  extra={**OUTFIELD_LOG, "giornata": MetricInfo("MD", "Matchday.", "count"),
                         "match": MetricInfo("Match", "", "text")})

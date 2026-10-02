"""Panoramica: stato del campionato alla giornata selezionata."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import ui
from src.context import Context
from src.plotting import standings_bump_fig


def _insights(summary: pd.DataFrame, matches: pd.DataFrame) -> list[str]:
    """Frasi generate dai dati della vista (non scritte a mano)."""
    top = lambda col: summary.loc[summary[col].idxmax()]
    low = lambda col: summary.loc[summary[col].idxmin()]
    t = lambda r: r["team"].title()
    lines = [
        f"<b>{t(top('shots_avg'))}</b> has the highest attacking volume: {top('shots_avg')['shots_avg']:.1f} shots per match.",
        f"<b>{t(top('shots_on_target_avg'))}</b> is the most dangerous on target: {top('shots_on_target_avg')['shots_on_target_avg']:.1f} shots on target per match.",
        f"<b>{t(low('shots_conceded_avg'))}</b> concedes the fewest shots: {low('shots_conceded_avg')['shots_conceded_avg']:.1f} per match.",
        f"<b>{t(top('pass_accuracy_avg'))}</b> has the best pass accuracy ({top('pass_accuracy_avg')['pass_accuracy_avg']:.1f}%), "
        f"<b>{t(top('forward_incidence_avg'))}</b> the most vertical style ({top('forward_incidence_avg')['forward_incidence_avg']:.1f}% of passes played forward).",
    ]
    losses = matches[matches["result"] == "L"]
    if not losses.empty:
        r = losses.loc[losses["Tiri"].idxmax()]
        lines.append(
            f"<b>{t(r)}</b> lost to {r['opponent'].title()} (MD{int(r['giornata'])}) despite "
            f"{r['Tiri']:.0f} shots: the highest volume in a defeat."
        )
    # squadra che raccoglie più (o meno) di quanto produce: punti vs tiri
    ranked = summary.assign(shot_rank=summary["shots_avg"].rank(ascending=False))
    ranked["gap"] = ranked["shot_rank"] - ranked["rank"]
    over = ranked.loc[ranked["gap"].idxmax()]
    under = ranked.loc[ranked["gap"].idxmin()]
    if over["gap"] >= 5:
        lines.append(f"<b>{t(over)}</b> is {ui.ordinal(over['rank'])} in the table but only {ui.ordinal(over['shot_rank'])} for shots: "
                     "collecting more than it produces.")
    if under["gap"] <= -5:
        lines.append(f"<b>{t(under)}</b> is {ui.ordinal(under['shot_rank'])} for shots but only {ui.ordinal(under['rank'])} in the table: "
                     "producing more than it collects.")
    return lines


def render(ctx: Context) -> None:
    ui.page_header(
        ctx.eyebrow, "League overview",
        "Serie A at a glance: key numbers, the table with recent form, how positions have changed and the "
        "players who are standing out. All data is extracted automatically from the League's official Match Reports.",
    )

    matches = ctx.dati_vista
    goals = matches["home_score"] + matches["away_score"]
    tm = ctx.team_match_df
    c = st.columns(6)
    c[0].metric("Matches", len(matches), border=True, help="Matches in the current view.")
    c[1].metric("Goals/match", f"{goals.mean():.2f}", border=True, help="Average goals (both teams) per match.")
    c[2].metric("Home wins", f"{(matches['home_score'] > matches['away_score']).mean() * 100:.0f}%", border=True,
                help="Share of matches won by the home team.")
    c[3].metric("Draws", f"{(matches['home_score'] == matches['away_score']).mean() * 100:.0f}%", border=True)
    c[4].metric("Shots/team", f"{tm['Tiri'].mean():.1f}", border=True,
                help="Average shots by one team in a match.")
    c[5].metric("Accuracy", f"{tm['Passaggi riusciti/tentati (%)'].mean():.1f}%", border=True,
                help="Average team pass accuracy.")

    st.write("")
    left, right = st.columns([1.15, 1], gap="medium")
    with left:
        with ui.card(
            f"Table after matchday {ctx.giornata}",
            "Points, goal difference and form over the last 5 matches. The table is always the real one up to the "
            "selected matchday, even in the single-matchday view.",
        ):
            ui.standings_table(ctx.standings_df, ctx.form, ctx.highlight_team)
    with right:
        default = [ctx.highlight_team] if ctx.highlight_team else list(ctx.standings_df["team"].head(3))
        with ui.card(
            "Standings over time",
            "Position matchday by matchday. Pick up to 3 teams to follow; the others stay grey for reference.",
            how_to="Each line is a team. Higher = better position. A line climbing steeply means a run of good "
                   "results; a flat line means stability.",
        ):
            chosen = st.multiselect(
                "Teams", list(ctx.standings_df["team"]), default=default, max_selections=3,
                format_func=str.title, label_visibility="collapsed", key="bump_teams",
            )
            ui.chart(standings_bump_fig(ctx.progression, chosen))
        with ui.card("Matchday results", f"Matches of matchday {ctx.giornata}."):
            rnd = ctx.match_stats_df[ctx.match_stats_df["giornata"] == ctx.giornata]
            st.markdown(
                "".join(ui.result_chip(r["home"], r["away"], int(r["home_score"]), int(r["away_score"]))
                        for _, r in rnd.iterrows()),
                unsafe_allow_html=True,
            )

    ui.section("Who is standing out", f"Leaders of the current view among players with at least {ctx.players.min_minutes}' played.")
    out = ctx.players.outfield
    if out.empty:
        st.info("No player data available.")
    else:
        eligible = out[out["eligible_rates"]]
        gk = ctx.players.keepers[ctx.players.keepers["eligible_rates"]]
        cards = [
            ("Top scorer", out, "goals", "{:.0f} goals"),
            ("Most assists", out, "assists", "{:.0f} assists"),
            ("Key passes /90", eligible, "key_passes_per90", "{:.2f}"),
            ("Recoveries /90", eligible, "recoveries_per90", "{:.2f}"),
            ("Save % (goalkeepers)", gk, "save_pct", "{:.1f}%"),
        ]
        cols = st.columns(len(cards))
        for col, (kicker, pool, metric, fmt) in zip(cols, cards):
            with col:
                pool = pool.dropna(subset=[metric])
                if pool.empty:
                    ui.leader_card(kicker, "—", "No eligible players", "")
                    continue
                best = pool.sort_values([metric, "minutes"], ascending=[False, True]).iloc[0]
                ties = int((pool[metric] == best[metric]).sum()) - 1
                team_line = best["team"].title() + (f" · tied with {ties} other{'s' if ties > 1 else ''}" if ties > 0 else "")
                ui.leader_card(kicker, fmt.format(best[metric]), best["player"], team_line)

    st.write("")
    with ui.card("What the numbers say", "Observations computed automatically on the current view."):
        st.markdown("".join(f"<p style='margin:.35rem 0'>• {line}</p>" for line in _insights(ctx.team_summary_df, ctx.team_match_df)),
                    unsafe_allow_html=True)

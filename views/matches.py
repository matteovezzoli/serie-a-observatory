"""Partite: dettaglio di una singola gara (statistiche e tabellini)."""

from __future__ import annotations

import streamlit as st

from src import ui
from src.context import Context
from src.glossary import CORE_METRIC_LABELS, MetricInfo
from src.parsing import CORE_METRICS
from src.plotting import match_comparison_fig

# colonne grezze del tabellino (sigle della Legenda del PDF)
OUTFIELD_LOG = {
    "jersey": MetricInfo("No.", "Shirt number.", "count"),
    "player": MetricInfo("Player", "", "text"),
    "MIN": MetricInfo("Min", "Minutes played (MIN).", "count"),
    "G": MetricInfo("Goals", "Goals (G).", "count"),
    "AS": MetricInfo("Assists", "Assists (AS).", "count"),
    "T": MetricInfo("Shots", "Total shots (T).", "count"),
    "TP": MetricInfo("On target", "Shots on target (TP).", "count"),
    "OG": MetricInfo("Chances", "Goal chances (OG).", "count"),
    "PC": MetricInfo("Key passes", "Key passes (PC).", "count"),
    "P": MetricInfo("Passes", "Completed passes (P).", "count"),
    "P(%)": MetricInfo("Pass %", "Completed/attempted passes (P%).", "pct"),
    "PA": MetricInfo("Forward", "Completed forward passes (PA).", "count"),
    "R": MetricInfo("Recoveries", "Recoveries (R).", "count"),
    "PG": MetricInfo("Touches", "Balls played (PG).", "count"),
    "FS": MetricInfo("Fouls won", "Fouls suffered (FS).", "count"),
    "AMM": MetricInfo("YC", "Yellow card (AMM).", "count"),
    "ESP": MetricInfo("RC", "Red card (ESP).", "count"),
}
GK_LOG = {
    "jersey": OUTFIELD_LOG["jersey"], "player": MetricInfo("Goalkeeper", "", "text"), "MIN": OUTFIELD_LOG["MIN"],
    "GS": MetricInfo("Conceded", "Goals conceded (GS).", "count"),
    "PA": MetricInfo("Saves", "Saves (PA: for goalkeepers this code means saves).", "count"),
    "RE": MetricInfo("Parries", "Parried shots (RE).", "count"),
    "LU": MetricInfo("Long balls", "Long balls (LU).", "count"),
    "AMM": OUTFIELD_LOG["AMM"],
}


def render(ctx: Context) -> None:
    ui.page_header(
        ctx.eyebrow, "Matches",
        "Every match in detail: which team dominated each phase of play, and the individual match sheet "
        "of both teams as reported in the Match Report.",
    )
    view = ctx.dati_vista.sort_values(["giornata", "match_id"], ascending=[False, True])
    labels = {
        r["match_id"]: f"MD{int(r['giornata'])} · {r['home'].title()} {int(r['home_score'])}–{int(r['away_score'])} {r['away'].title()}"
        for _, r in view.iterrows()
    }
    ids = list(labels)
    default = 0
    if ctx.highlight_team:
        hits = [i for i, mid in enumerate(ids) if ctx.highlight_team in (view.set_index("match_id").loc[mid, ["home", "away"]].tolist())]
        default = hits[0] if hits else 0
    match_id = st.selectbox("Match", ids, index=default, format_func=labels.get)
    m = view[view["match_id"] == match_id].iloc[0]

    ui.scoreboard(m["home"], m["away"], int(m["home_score"]), int(m["away_score"]),
                  f"Matchday {int(m['giornata'])} · {m.get('match_date') or ''}")

    with ui.card(
        "Who dominated what",
        "For each statistic the bar is split in proportion between the two teams; the actual value is written inside each segment.",
        how_to="A fully blue bar means the statistic was produced only by the home team. The white line in the "
               "middle is parity (50/50). Example: 16 shots vs 11 → blue bar at 59%.",
    ):
        ui.chart(match_comparison_fig(m, CORE_METRICS))
        recovered = [CORE_METRIC_LABELS[x] for x in CORE_METRICS if m.get(f"{x}_status") == "recovered_zero"]
        review = [CORE_METRIC_LABELS[x] for x in CORE_METRICS if m.get(f"{x}_status") == "review"]
        if recovered:
            st.caption(f"In the PDF these rows show a single value; the other team's 0 is rebuilt from its position: {', '.join(recovered)}.")
        if review:
            ui.callout(f"Statistics not read with certainty in this match: {', '.join(review)}.", warn=True)

    rows = ctx.player_stats_df[ctx.player_stats_df["match_id"] == match_id] if not ctx.player_stats_df.empty else None
    if rows is None or rows.empty:
        st.info("Player match sheet not available for this match.")
        return
    cols = st.columns(2, gap="medium")
    for col, side in zip(cols, ("home", "away")):
        team = m[side]
        team_rows = rows[rows["team"] == team]
        with col:
            with ui.card(f"Match sheet — {team.title()}", "Hover the column headers for the definition of each code."):
                out = team_rows[team_rows["role"] == "OUT"].sort_values("MIN", ascending=False)
                ui.data_table(out, list(OUTFIELD_LOG), extra=OUTFIELD_LOG)
                ui.data_table(team_rows[team_rows["role"] == "GK"], list(GK_LOG), extra=GK_LOG)

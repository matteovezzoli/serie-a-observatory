"""Metodologia e glossario: fonte dati, pipeline, soglie, definizioni,
limiti noti e controlli di qualità."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import ui
from src.context import Context
from src.glossary import PLAYER_METRICS
from src.metrics import METRIC_PANELS

QUALITY_LABELS = {
    "team_rows": "Two team rows for every match",
    "no_suspicious_missing": "No missing values on never-zero metrics (passes, accuracy, recoveries)",
    "player_rows_for_every_match": "Player match sheet available for every match",
    "no_unassigned_values": "Every match-sheet value assigned to a column",
    "two_teams_per_match": "Two teams in every match sheet",
    "player_rows_present": "Player rows present",
}


def render(ctx: Context) -> None:
    ui.page_header(
        "Info", "Methodology & glossary",
        "Where the numbers come from, how they are computed and what their limits are. A dashboard is only "
        "credible if it is clear what it measures.",
    )

    c = st.columns(4)
    c[0].metric("Matches read", len(ctx.match_stats_df), border=True)
    c[1].metric("Matchdays", int(ctx.match_stats_df["giornata"].nunique()), border=True)
    c[2].metric("Player rows", len(ctx.player_stats_df), border=True)
    c[3].metric("Distinct players", int(ctx.player_stats_df[["player", "team"]].drop_duplicates().shape[0])
                if not ctx.player_stats_df.empty else 0, border=True)

    tab_src, tab_team, tab_player, tab_limits, tab_quality = st.tabs(
        ["Source & method", "Team metrics", "Player metrics", "Known limitations", "Quality checks"])

    with tab_src:
        st.markdown(f"""
#### Source
The **official Lega Serie A Match Reports** (PDF), one per match. From each report the dashboard reads:
- **Team statistics** — 16 statistics for both teams (shots, passes, recoveries, saves…);
- **Player statistics** — the individual match sheet of every player who took the field.

#### How the PDFs are read
The PDF text is not a table: a zero statistic for a player is **not printed at all**, so a number's position in
the row does not tell which column it belongs to. The parser reads the **coordinates** of every number and assigns
it to the nearest header column, recalibrating the columns on every single page. Cards (yellow, second yellow,
red) are told apart by their position within the dedicated header zone. Across all matches read, no value was
left unassigned.

#### Views and thresholds
- **Season**: every match up to the selected matchday. **Single matchday**: only that round's matches.
- The **table** is always the real one up to the selected matchday.
- **Per 90**: total ÷ minutes × 90, using only matches whose minutes are reported in the PDF.
- Current **minutes threshold**: **{ctx.players.min_minutes}'** (default: 40% of available minutes, at least 180'
  in the season view) — below it, per-90 rates are too driven by chance.
- **Passes threshold** for accuracy: **{ctx.players.min_passes}** completed passes. Shot accuracy and
  conversion: at least 5 shots.
- **Percentiles**: where a value sits within the reference group (eligible players or the teams in the view).
""")

    with tab_team:
        st.markdown("Per-match averages, computed over every match in the view.")
        st.dataframe(pd.DataFrame([
            {"Area": p.category, "Metric": p.title, "Definition": p.description} for p in METRIC_PANELS
        ] + [{"Area": "Summary", "Metric": "Style index",
              "Definition": "Average percentile of pass accuracy, final-third penetration and verticality (0-100)."}]),
            hide_index=True, width="stretch", height=720)

    with tab_player:
        groups = [g for g in dict.fromkeys(v.group for v in PLAYER_METRICS.values()) if g and g != "Profile"]
        group = st.segmented_control("Group", groups, default=groups[0], required=True, key="glossary_group")
        st.dataframe(pd.DataFrame([
            {"Metric": v.label, "Definition": v.description} for v in PLAYER_METRICS.values() if v.group == group
        ]), hide_index=True, width="stretch")

    with tab_limits:
        st.markdown("""
- **No positions in the match sheet.** The PDF does not report where a player plays: rankings mix defenders,
  midfielders and forwards. That is why the dashboard avoids a single overall score and favours multi-dimensional
  comparisons, shares of team output and similar players.
- **Missing minutes.** In some reports the minutes field is empty: those appearances count in totals but are
  excluded from per-90 rates (both numerator and denominator).
- **Estimated attempted passes.** Rebuilt from completed passes and percentage, which the PDF rounds to an integer.
- **Team-only statistics.** Dribbles, final-third passes and corners do not exist per player.
- **Small samples.** Early in the season each team has played few matches: percentages and shares (especially
  goal share) can change a lot from one matchday to the next.
- **Second yellows.** In the report a second yellow also appears as a red card: straight reds are computed as
  red cards minus second yellows.
- **No shot quality.** The report has no expected goals or shot locations: efficiency (goals/shots) cannot tell
  easy chances from hard ones.
""")

    with tab_quality:
        st.markdown("Automatic checks run on the current view at every load.")
        quality = pd.concat([ctx.quality_df, ctx.players.quality_df], ignore_index=True)
        quality["Check"] = quality["check"].map(QUALITY_LABELS).fillna(quality["check"])
        quality["Result"] = quality["passed"].map({True: "✅ passed", False: "❌ failed"})
        st.dataframe(quality[["Check", "Result"]], hide_index=True, width="stretch")
        if not ctx.suspicious_nan_rows.empty:
            st.markdown("Matches with missing values on never-zero metrics:")
            st.dataframe(ctx.suspicious_nan_rows[["match_id", "team", "opponent"]], hide_index=True)
        no_min = ctx.players.match_log[ctx.players.match_log["MIN"].isna()] if not ctx.players.match_log.empty else pd.DataFrame()
        if not no_min.empty:
            st.markdown(f"Appearances without minutes in the source PDF: **{len(no_min)}**")
            st.dataframe(no_min.groupby(["match_id", "team"]).size().rename("rows").reset_index(), hide_index=True)

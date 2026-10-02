"""Glossario delle metriche: fonte unica per etichette, spiegazioni (tooltip
delle tabelle, didascalie dei grafici, pagina Metodologia) e formato di
visualizzazione. Le sigle tra parentesi sono quelle della Legenda del PDF.
I testi mostrati in dashboard sono in inglese; le chiavi interne dei dati
restano quelle del parser.

`kind` guida la formattazione:
- "count"   intero (totali)
- "rate"    decimale (per 90', medie)
- "pct"     percentuale 0-100
- "share"   quota % sulla squadra (0-100, valori tipici bassi)
- "text"    testo
"""

from __future__ import annotations

from dataclasses import dataclass

from src.metrics import METRIC_PANELS


@dataclass(frozen=True)
class MetricInfo:
    label: str
    description: str
    kind: str = "rate"
    group: str = ""


# Etichette inglesi delle 16 statistiche di squadra (le chiavi sono i nomi del PDF)
CORE_METRIC_LABELS = {
    "Tiri": "Shots",
    "Tiri in porta": "Shots on target",
    "Tiri fuori": "Shots off target",
    "Tiri respinti": "Blocked shots",
    "Passaggi chiave": "Key passes",
    "Falli fatti": "Fouls committed",
    "Corner": "Corners",
    "Fuorigioco": "Offsides",
    "Dribbling": "Successful dribbles",
    "Passaggi riusciti": "Completed passes",
    "Passaggi riusciti/tentati (%)": "Pass accuracy (%)",
    "Passaggi riusciti in ultimo terzo": "Completed passes in final third",
    "Palloni giocati in avanti riusciti": "Completed forward passes",
    "Passaggi lunghi": "Long passes",
    "Parate": "Saves",
    "Recuperi": "Recoveries",
}

_P90 = "Normalised per 90 minutes played, using only matches whose minutes are reported in the PDF."

PLAYER_METRICS: dict[str, MetricInfo] = {
    # --- anagrafica / contesto
    "player": MetricInfo("Player", "Name as printed in the Match Report.", "text", "Profile"),
    "team": MetricInfo("Team", "Team in the match sheet.", "text", "Profile"),
    "team_rank": MetricInfo("Team pos.", "League position of the player's team at the selected matchday.", "count", "Profile"),
    "matches": MetricInfo("Apps", "Matches in which the player appears in the match sheet (starter or substitute).", "count", "Profile"),
    "minutes": MetricInfo("Minutes", "Minutes played (MIN). Matches without minutes in the PDF are not counted.", "count", "Profile"),
    "matches_no_minutes": MetricInfo("Apps without minutes", "Appearances whose minutes are missing in the source PDF: excluded from per-90 rates.", "count", "Profile"),

    # --- totali
    "goals": MetricInfo("Goals", "Goals scored (G).", "count", "Totals"),
    "assists": MetricInfo("Assists", "Final pass before a goal (AS).", "count", "Totals"),
    "goal_contributions": MetricInfo("Goals + assists", "Direct goal involvement: goals plus assists.", "count", "Totals"),
    "own_goals": MetricInfo("Own goals", "Own goals (AUT).", "count", "Totals"),
    "shots": MetricInfo("Shots", "Total shots (T).", "count", "Totals"),
    "shots_on_target": MetricInfo("Shots on target", "Shots on target (TP).", "count", "Totals"),
    "woodwork": MetricInfo("Woodwork", "Shots hitting the post or bar (PT).", "count", "Totals"),
    "big_chances": MetricInfo("Goal chances", "Goal chances (OG) as defined by the data provider.", "count", "Totals"),
    "fouls_suffered": MetricInfo("Fouls won", "Fouls suffered (FS): players who draw contact, often ball carriers.", "count", "Totals"),
    "touches": MetricInfo("Touches", "Balls played (PG): a measure of involvement in the game.", "count", "Totals"),
    "key_passes": MetricInfo("Key passes", "Passes that set up a teammate's shot (PC).", "count", "Totals"),
    "passes_completed": MetricInfo("Completed passes", "Passes that reach a teammate (P).", "count", "Totals"),
    "passes_attempted": MetricInfo("Attempted passes (est.)", "Rebuilt from P and P(%): the PDF rounds the percentage, so this is an approximation.", "count", "Totals"),
    "forward_passes": MetricInfo("Forward passes", "Completed forward passes (PA, outfield players only).", "count", "Totals"),
    "recoveries": MetricInfo("Recoveries", "Balls won back (R).", "count", "Totals"),

    # --- per 90
    "goals_per90": MetricInfo("Goals/90", f"Goals per 90 minutes. {_P90}", "rate", "Per 90"),
    "assists_per90": MetricInfo("Assists/90", f"Assists per 90 minutes. {_P90}", "rate", "Per 90"),
    "goal_contributions_per90": MetricInfo("G+A/90", f"Goals plus assists per 90 minutes. {_P90}", "rate", "Per 90"),
    "shots_per90": MetricInfo("Shots/90", f"Shots per 90 minutes. {_P90}", "rate", "Per 90"),
    "shots_on_target_per90": MetricInfo("Shots on target/90", f"Shots on target per 90 minutes. {_P90}", "rate", "Per 90"),
    "big_chances_per90": MetricInfo("Chances/90", f"Goal chances per 90 minutes. {_P90}", "rate", "Per 90"),
    "key_passes_per90": MetricInfo("Key passes/90", f"Key passes per 90 minutes: creativity. {_P90}", "rate", "Per 90"),
    "passes_completed_per90": MetricInfo("Passes/90", f"Completed passes per 90 minutes: involvement in build-up. {_P90}", "rate", "Per 90"),
    "forward_passes_per90": MetricInfo("Forward passes/90", f"Completed forward passes per 90 minutes: progression. {_P90}", "rate", "Per 90"),
    "recoveries_per90": MetricInfo("Recoveries/90", f"Balls recovered per 90 minutes: off-the-ball work. {_P90}", "rate", "Per 90"),
    "touches_per90": MetricInfo("Touches/90", f"Balls played per 90 minutes. {_P90}", "rate", "Per 90"),
    "fouls_suffered_per90": MetricInfo("Fouls won/90", f"Fouls suffered per 90 minutes. {_P90}", "rate", "Per 90"),

    # --- efficienza
    "pass_accuracy_pct": MetricInfo("Pass accuracy", "Completed / attempted passes, weighted by volume (not an average of match percentages).", "pct", "Efficiency"),
    "forward_play_incidence_pct": MetricInfo("Verticality", "Share of completed passes played forward. Strongly role-dependent.", "pct", "Efficiency"),
    "shot_accuracy_pct": MetricInfo("Shot accuracy", "Shots on target / total shots. Only with at least 5 shots.", "pct", "Efficiency"),
    "conversion_pct": MetricInfo("Conversion", "Goals / total shots. Only with at least 5 shots.", "pct", "Efficiency"),

    # --- contesto squadra
    "goal_share_pct": MetricInfo("% of team goals", "Share of the team's goals scored by the player, only in matches the player played. Noisy when the team scores little.", "share", "Team context"),
    "shot_share_pct": MetricInfo("% of team shots", "Share of the team's shots taken by the player, only in matches the player played.", "share", "Team context"),
    "key_pass_share_pct": MetricInfo("% of team key passes", "Share of the team's key passes made by the player, only in matches the player played.", "share", "Team context"),
    "recovery_share_pct": MetricInfo("% of team recoveries", "Share of the team's recoveries made by the player, only in matches the player played.", "share", "Team context"),
    "pass_share_pct": MetricInfo("% of team passes", "Share of the team's completed passes made by the player, only in matches the player played.", "share", "Team context"),

    # --- disciplina
    "amm": MetricInfo("Yellow cards", "Single yellow cards (AMM).", "count", "Discipline"),
    "dam": MetricInfo("Second yellows", "Sendings-off for a second yellow (DAM).", "count", "Discipline"),
    "esp": MetricInfo("Red cards", "Rows with a red card (ESP), second yellows included.", "count", "Discipline"),
    "direct_reds": MetricInfo("Straight reds", "Straight red cards, second yellows excluded.", "count", "Discipline"),
    "yellow_equivalent": MetricInfo("Yellow equivalent", "Yellow cards + 2 × second yellows: a second yellow counts as two yellows.", "count", "Discipline"),

    # --- portieri
    "goals_conceded": MetricInfo("Goals conceded", "Goals conceded with the keeper on the pitch (GS).", "count", "Goalkeepers"),
    "saves": MetricInfo("Saves", "Saves (PA: for goalkeepers this code means saves).", "count", "Goalkeepers"),
    "respinte": MetricInfo("Parries", "Parried shots (RE).", "count", "Goalkeepers"),
    "long_balls": MetricInfo("Long balls", "Goal kicks and long balls by the keeper (LU).", "count", "Goalkeepers"),
    "save_pct": MetricInfo("Save %", "Saves / (saves + goals conceded): share of shots on target stopped.", "pct", "Goalkeepers"),
    "saves_per90": MetricInfo("Saves/90", f"Saves per 90 minutes: how busy the keeper is. {_P90}", "rate", "Goalkeepers"),
    "goals_conceded_per90": MetricInfo("Goals conceded/90", f"Goals conceded per 90 minutes: lower is better. {_P90}", "rate", "Goalkeepers"),
    "clean_sheets": MetricInfo("Clean sheets", "Full matches (90') without conceding.", "count", "Goalkeepers"),

    # --- analisi derivate
    "similarity": MetricInfo("Similarity", "Cosine similarity between standardised per-90 profiles (100 = identical profile).", "pct", "Analysis"),
}

TEAM_METRICS: dict[str, MetricInfo] = {
    "rank": MetricInfo("Pos", "League position (points, then goal difference, then goals scored).", "count"),
    "team": MetricInfo("Team", "", "text"),
    "matches": MetricInfo("MP", "Matches played in the current view.", "count"),
    "points": MetricInfo("Pts", "3 per win, 1 per draw.", "count"),
    "wins": MetricInfo("W", "Wins.", "count"),
    "draws": MetricInfo("D", "Draws.", "count"),
    "losses": MetricInfo("L", "Losses.", "count"),
    "goals_for": MetricInfo("GF", "Goals scored.", "count"),
    "goals_against": MetricInfo("GA", "Goals conceded.", "count"),
    "goal_difference": MetricInfo("GD", "Goal difference.", "count"),
    "style_score": MetricInfo("Style index", "Average percentile of pass accuracy, final-third penetration and verticality (0-100). Describes how a team plays, not how good it is.", "rate"),
    **{p.avg_col: MetricInfo(p.x_title if not p.pct else p.title, p.description, "pct" if p.pct else "rate", p.category) for p in METRIC_PANELS},
}

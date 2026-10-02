"""Registro delle metriche di squadra derivabili dai Match Report.

Fonte di verità unica usata sia da aggregation.py (per calcolare le medie
di squadra) sia dalla dashboard (pannelli grafici, tooltip, glossario):
aggiungere una metrica alla dashboard richiede una riga sola qui, non
modifiche sparse in più file.

`column` è il nome della colonna in team_match_df — o una delle 16
CORE_METRICS del parser, o una delle metriche derivate già calcolate in
aggregation.py (final_third_share_pct, forward_play_incidence_pct,
shots_conceded, shots_on_target_conceded).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricPanel:
    column: str        # colonna sorgente in team_match_df
    avg_col: str        # nome della media aggregata in team_summary_df
    title: str           # titolo del grafico
    x_title: str         # etichetta asse
    pct: bool = False     # True se il valore è già una percentuale
    category: str = "Attack"
    description: str = ""  # spiegazione per tooltip e glossario


METRIC_PANELS: list[MetricPanel] = [
    # --- Attacco ----------------------------------------------------------
    MetricPanel("Tiri", "shots_avg", "Shots per match", "Shots/match", category="Attack",
                description="Every attempt at goal: on target, off target and blocked. Measures attacking volume."),
    MetricPanel("Tiri in porta", "shots_on_target_avg", "Shots on target per match", "Shots on target/match", category="Attack",
                description="Shots on target (saved or scored). Measures how much of the volume turns into real danger."),
    MetricPanel("Tiri fuori", "shots_off_target_avg", "Shots off target per match", "Shots off target/match", category="Attack",
                description="Shots that miss the target without being deflected."),
    MetricPanel("Tiri respinti", "shots_blocked_avg", "Blocked shots per match", "Blocked shots/match", category="Attack",
                description="Shots blocked by a defender: many blocks often mean shooting from crowded positions."),
    MetricPanel("Corner", "corners_avg", "Corners per match", "Corners/match", category="Attack",
                description="Corners won: an indirect sign of pressure in the opponent's half."),
    MetricPanel("Fuorigioco", "offsides_avg", "Offsides per match", "Offsides/match", category="Attack",
                description="Offsides called against the team: often linked to balls played in behind the defence."),

    # --- Passaggi e costruzione -------------------------------------------
    MetricPanel("Passaggi riusciti", "passes_completed_avg", "Completed passes per match", "Completed passes/match", category="Passing",
                description="Passes reaching a teammate: a proxy for possession and build-up volume."),
    MetricPanel("Passaggi riusciti/tentati (%)", "pass_accuracy_avg", "Pass accuracy", "Pass accuracy (%)", pct=True, category="Passing",
                description="Completed passes over attempted passes. High with patient build-up, lower with direct play."),
    MetricPanel("Passaggi chiave", "key_passes_avg", "Key passes per match", "Key passes/match", category="Passing",
                description="Passes that directly set up a teammate's shot: measures chance creation."),
    MetricPanel("Passaggi lunghi", "long_passes_avg", "Long passes per match", "Long passes/match", category="Passing",
                description="Long balls: many of them suggest direct play or build-up under pressure."),
    MetricPanel("Dribbling", "dribbles_avg", "Successful dribbles per match", "Dribbles/match", category="Passing",
                description="One-on-ones won with the ball: the ability to beat a man."),
    MetricPanel("final_third_share_pct", "final_third_share_avg", "Final-third penetration", "% of completed passes in final third", pct=True, category="Passing",
                description="Share of completed passes played in the final third: how close to goal possession gets."),
    MetricPanel("forward_play_incidence_pct", "forward_incidence_avg", "Verticality index", "% of completed passes played forward", pct=True, category="Passing",
                description="Share of completed passes played forward: high = vertical play, low = sideways circulation."),

    # --- Difesa e disciplina ------------------------------------------------
    MetricPanel("shots_conceded", "shots_conceded_avg", "Shots conceded per match", "Opponent shots/match", category="Defence",
                description="Opponent shots: lower is better. Measures how much the team lets opponents shoot."),
    MetricPanel("shots_on_target_conceded", "shots_on_target_conceded_avg", "Shots on target conceded per match", "Opponent shots on target/match", category="Defence",
                description="Opponent shots on target: lower is better. Shows how much work reaches the goalkeeper."),
    MetricPanel("Falli fatti", "fouls_avg", "Fouls committed per match", "Fouls/match", category="Defence",
                description="Fouls called against the team: aggression, but also difficulty winning the ball cleanly."),
    MetricPanel("Parate", "saves_avg", "Saves per match", "Saves/match", category="Defence",
                description="Goalkeeper saves on shots on target: many saves = a very busy keeper."),
    MetricPanel("Recuperi", "recoveries_avg", "Recoveries per match", "Recoveries/match", category="Defence",
                description="Balls won back: intensity and ability to regain possession."),
]

CATEGORIES = ["Attack", "Passing", "Defence"]

# Metriche in cui un valore BASSO è il risultato desiderabile (serve ai grafici
# per dire "lower is better" in modo esplicito)
LOWER_IS_BETTER = {"shots_conceded_avg", "shots_on_target_conceded_avg"}

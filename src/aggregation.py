"""Aggregazione season-level: legge tutte le giornate disponibili in
`data/` e costruisce i tre dataset usati a valle (match, squadra-partita,
riepilogo di squadra).

NOTA rispetto alla Cella 3 del notebook: lì un quality check fallito
solleva un'eccezione (`raise ValueError(...)`), corretto per un notebook
dove vuoi fermarti e investigare subito. Qui invece `build_team_tables`
non solleva mai: ritorna sempre i dati disponibili + un `quality_df` e
un `suspicious_nan_rows`, così l'app Streamlit può mostrare un avviso
invece di andare in crash per una singola partita problematica.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.metrics import METRIC_PANELS
from src.parsing import CORE_METRICS, parse_full_report

# Metriche per cui uno 0 reale è plausibile nel calcio (il PDF le rende blank)
PLAUSIBLE_ZERO_METRICS = {
    "Tiri", "Tiri in porta", "Tiri fuori", "Tiri respinti", "Corner",
    "Fuorigioco", "Dribbling", "Passaggi chiave", "Falli fatti", "Parate",
}

# Metriche che in una partita professionistica non sono mai 0
NEVER_ZERO_METRICS = {"Passaggi riusciti", "Passaggi riusciti/tentati (%)", "Recuperi"}


def discover_round_dirs(base_data_dir: Path) -> list[Path]:
    """Sottocartelle di base_data_dir che contengono almeno un PDF
    (es. data/prima, data/seconda, ...). L'ordine cronologico reale è
    letto dal campo 'giornata' dentro ogni PDF, non dal nome cartella."""
    return sorted(
        d for d in base_data_dir.iterdir()
        if d.is_dir() and any(d.glob("*.pdf"))
    )


def data_signature(round_dirs: list[Path]) -> tuple:
    """Firma (nome file, mtime) di tutti i PDF trovati: usata come cache key
    per invalidare automaticamente la cache Streamlit quando aggiungi una
    nuova giornata o sostituisci un PDF, senza doverla svuotare a mano."""
    return tuple(
        (p.name, p.stat().st_mtime_ns)
        for d in round_dirs
        for p in sorted(d.glob("*.pdf"))
    )


def build_match_stats_df(round_dirs: list[Path]) -> tuple[pd.DataFrame, list[dict]]:
    """Parsa tutti i PDF in round_dirs. Ritorna (match_stats_df, parse_errors):
    un PDF che fallisce il parsing finisce in parse_errors invece di far
    crashare l'intero batch."""
    records: list[dict] = []
    parse_errors: list[dict] = []

    for round_dir in round_dirs:
        for pdf_path in sorted(round_dir.glob("*.pdf")):
            try:
                records.append(parse_full_report(pdf_path))
            except Exception as exc:
                parse_errors.append({
                    "folder": round_dir.name,
                    "file": pdf_path.name,
                    "error": str(exc),
                })

    match_stats_df = (
        pd.DataFrame(records)
        .sort_values(["giornata", "match_id"])
        .reset_index(drop=True)
    ) if records else pd.DataFrame()

    return match_stats_df, parse_errors


def build_team_tables(
    match_stats_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Da match_stats_df (già eventualmente filtrato per giornata) costruisce:
    - team_match_df: una riga per squadra per partita
    - team_summary_df: classifica + medie di squadra, ordinata per punti
    - quality_df: esito dei controlli di qualità
    - suspicious_nan_rows: righe con NaN su metriche 'mai zero' (vuoto se tutto ok)
    """
    team_rows = []
    for _, match in match_stats_df.iterrows():
        for side, team in (("home", match["home"]), ("away", match["away"])):
            row = {
                "match_id": match["match_id"],
                "giornata": match["giornata"],
                "team": team,
                "opponent": match["away"] if side == "home" else match["home"],
                "venue": side,
                "goals_for": match[f"{side}_score"],
                "goals_against": match["away_score"] if side == "home" else match["home_score"],
            }
            for metric in CORE_METRICS:
                row[metric] = match[f"{metric}_{side}"]
            team_rows.append(row)

    team_match_df = pd.DataFrame(team_rows)

    team_match_df["result"] = np.select(
        [
            team_match_df["goals_for"] > team_match_df["goals_against"],
            team_match_df["goals_for"] < team_match_df["goals_against"],
        ],
        ["W", "L"],
        default="D",
    )
    team_match_df["points"] = team_match_df["result"].map({"W": 3, "D": 1, "L": 0})

    # Imputazione controllata dei valori 0 plausibili rimasti NaN
    for m in PLAUSIBLE_ZERO_METRICS:
        if m in team_match_df.columns:
            team_match_df[m] = team_match_df[m].fillna(0.0)

    # Metriche derivate
    team_match_df["final_third_share_pct"] = (
        team_match_df["Passaggi riusciti in ultimo terzo"] / team_match_df["Passaggi riusciti"] * 100
    )
    team_match_df["forward_play_incidence_pct"] = (
        team_match_df["Palloni giocati in avanti riusciti"] / team_match_df["Passaggi riusciti"] * 100
    )

    # Metriche "concesse": le stesse righe dell'avversario nella stessa partita
    opponent_view = team_match_df[["match_id", "team", "Tiri", "Tiri in porta"]].rename(
        columns={"team": "opponent", "Tiri": "shots_conceded", "Tiri in porta": "shots_on_target_conceded"}
    )
    team_match_df = team_match_df.merge(opponent_view, on=["match_id", "opponent"], how="left")

    # Quality checks (non bloccanti qui: l'app decide cosa mostrare)
    suspicious_nan_rows = team_match_df[team_match_df[list(NEVER_ZERO_METRICS)].isna().any(axis=1)]
    quality_checks = {
        "team_rows": len(team_match_df) == len(match_stats_df) * 2,
        "no_suspicious_missing": suspicious_nan_rows.empty,
    }
    quality_df = pd.DataFrame({"check": list(quality_checks.keys()), "passed": list(quality_checks.values())})

    # Aggregazione classifica e medie di squadra — le medie per-metrica sono
    # generate dal registro METRIC_PANELS (src/metrics.py), non hardcodate
    # qui: aggiungere un pannello alla dashboard non richiede toccare questa
    # funzione.
    metric_aggs = {panel.avg_col: (panel.column, "mean") for panel in METRIC_PANELS}

    team_summary_df = (
        team_match_df.groupby("team", as_index=False)
        .agg(
            matches=("match_id", "size"),
            points=("points", "sum"),
            wins=("result", lambda v: (v == "W").sum()),
            draws=("result", lambda v: (v == "D").sum()),
            losses=("result", lambda v: (v == "L").sum()),
            goals_for=("goals_for", "sum"),
            goals_against=("goals_against", "sum"),
            **metric_aggs,
        )
        .assign(goal_difference=lambda f: f["goals_for"] - f["goals_against"])
    )

    team_summary_df = team_summary_df.sort_values(
        ["points", "goal_difference", "goals_for"], ascending=False
    ).reset_index(drop=True)
    team_summary_df.insert(0, "rank", team_summary_df.index + 1)

    # Indice sintetico di stile (Cella 7): media dei percentili di precisione,
    # penetrazione nell'ultimo terzo e verticalità — descrive COME gioca una
    # squadra, non quanto è forte.
    team_summary_df["style_score"] = (
        team_summary_df["pass_accuracy_avg"].rank(pct=True)
        + team_summary_df["final_third_share_avg"].rank(pct=True)
        + team_summary_df["forward_incidence_avg"].rank(pct=True)
    ) / 3 * 100

    return team_match_df, team_summary_df, quality_df, suspicious_nan_rows

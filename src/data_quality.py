"""Controlli di qualità automatici: confronta le statistiche di squadra (da
STATISTICHE SQUADRE) con la somma delle statistiche individuali (da
STATISTICHE GIOCATORE) per la stessa partita.

Le due tabelle vivono nello stesso PDF ma sono compilate/riportate
separatamente dal fornitore. Validato con coordinate reali su 3 partite
(Udinese-Lazio, Monza-Udinese, Atalanta-Sassuolo — settembre 2026): quando
emerge uno scostamento, il valore individuale è sempre centrato esattamente
(0.0pt) sulla colonna giusta — quindi la causa non è mai un errore di
mappatura del parser, è un'incongruenza che esiste già tra le due pagine del
PDF sorgente.

Questo modulo non "corregge" nulla: segnala soltanto. Con 10+ partite
aggiunte a settimana, l'obiettivo è che le incongruenze restino visibili e
tracciabili invece di sparire in silenzio — non richiedere un'indagine
manuale ogni volta che ne emerge una nuova. Uno scostamento piccolo (1-2
unità) è rumore di fondo atteso della fonte dati, non un'emergenza da
fermare-tutto: la soglia di attenzione reale è quando gli scostamenti
crescono in numero o dimensione rispetto alla baseline, non la singola
occorrenza.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# (etichetta, colonna aggregata giocatori, colonna in team_match_df) — attesa: uguaglianza esatta
_EXACT_CHECKS = [
    ("Tiri", "T", "Tiri"),
    ("Tiri in porta", "TP", "Tiri in porta"),
    ("Passaggi chiave", "PC", "Passaggi chiave"),
    ("Palloni giocati in avanti", "PA", "Palloni giocati in avanti riusciti"),
]

# attesa: squadra >= somma giocatori (il portiere non è incluso nella tabella giocatori per queste metriche)
_AT_LEAST_CHECKS = [
    ("Passaggi riusciti", "P", "Passaggi riusciti"),
    ("Recuperi", "R", "Recuperi"),
]


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Garantisce che le colonne esistano anche se assenti nel sottoinsieme
    (es. AUT-autogol, raro) — altrimenti .agg() con nome fisso va in KeyError."""
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = np.nan
    return df


def build_team_player_totals(player_stats_df: pd.DataFrame) -> pd.DataFrame:
    """Aggrega le statistiche individuali (giocatori di movimento + portiere)
    a livello team-partita, con gli stessi nomi di colonna delle metriche
    grezze del parser (T, TP, PC, P, PA, R, FS, saves) per poterle confrontare
    riga per riga con team_match_df."""
    outfield = _ensure_columns(
        player_stats_df[player_stats_df["role"] == "OUT"],
        ["T", "TP", "PC", "P", "PA", "R", "FS"],
    )
    gk = _ensure_columns(player_stats_df[player_stats_df["role"] == "GK"], ["PA"])

    out_totals = outfield.groupby(["match_id", "team"], as_index=False).agg(
        T=("T", "sum"), TP=("TP", "sum"), PC=("PC", "sum"), P=("P", "sum"),
        PA=("PA", "sum"), R=("R", "sum"), FS=("FS", "sum"),
    )
    gk_totals = gk.groupby(["match_id", "team"], as_index=False).agg(saves=("PA", "sum"))
    return out_totals.merge(gk_totals, on=["match_id", "team"], how="left")


def check_team_vs_player_consistency(
    team_match_df: pd.DataFrame, player_stats_df: pd.DataFrame
) -> pd.DataFrame:
    """Una riga per OGNI scostamento trovato (dataframe vuoto se tutto torna).
    Colonne: match_id, team, metrica, valore_giocatori, valore_squadra, scostamento.
    Non distingue "bug nostro" da "incongruenza nel PDF sorgente" — quella
    distinzione richiede sempre una verifica manuale sul PDF specifico (vedi
    docstring del modulo); il compito di questa funzione è solo non far
    perdere traccia dello scostamento quando succede."""
    totals = build_team_player_totals(player_stats_df)
    merged = team_match_df.merge(totals, on=["match_id", "team"], how="left")

    opp_fouls = team_match_df[["match_id", "team", "Falli fatti"]].rename(
        columns={"team": "opponent", "Falli fatti": "opp_fouls"}
    )
    merged = merged.merge(opp_fouls, on=["match_id", "opponent"], how="left")

    issues: list[dict] = []

    for label, player_col, team_col in _EXACT_CHECKS:
        diff = merged[player_col].fillna(0) - merged[team_col].fillna(0)
        for _, row in merged.loc[diff != 0, ["match_id", "team", player_col, team_col]].iterrows():
            issues.append({
                "match_id": row["match_id"], "team": row["team"], "metrica": label,
                "valore_giocatori": row[player_col], "valore_squadra": row[team_col],
                "scostamento": row[player_col] - row[team_col],
            })

    for label, player_col, team_col in _AT_LEAST_CHECKS:
        diff = merged[team_col].fillna(0) - merged[player_col].fillna(0)
        for _, row in merged.loc[diff < 0, ["match_id", "team", player_col, team_col]].iterrows():
            issues.append({
                "match_id": row["match_id"], "team": row["team"], "metrica": label,
                "valore_giocatori": row[player_col], "valore_squadra": row[team_col],
                "scostamento": row[team_col] - row[player_col],
            })

    diff_saves = merged["saves"].fillna(0) - merged["Parate"].fillna(0)
    for _, row in merged.loc[diff_saves != 0, ["match_id", "team", "saves", "Parate"]].iterrows():
        issues.append({
            "match_id": row["match_id"], "team": row["team"], "metrica": "Parate (portiere)",
            "valore_giocatori": row["saves"], "valore_squadra": row["Parate"],
            "scostamento": row["saves"] - row["Parate"],
        })

    diff_fouls = merged["opp_fouls"].fillna(0) - merged["FS"].fillna(0)
    for _, row in merged.loc[diff_fouls < 0, ["match_id", "team", "FS", "opp_fouls"]].iterrows():
        issues.append({
            "match_id": row["match_id"], "team": row["team"], "metrica": "Falli subiti",
            "valore_giocatori": row["FS"], "valore_squadra": row["opp_fouls"],
            "scostamento": row["opp_fouls"] - row["FS"],
        })

    return pd.DataFrame(issues)

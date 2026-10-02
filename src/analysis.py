"""Analisi derivate per la dashboard, costruite sopra le tabelle di
aggregation.py e player_aggregation.py. Nessuna funzione solleva per dati
mancanti: ritornano un DataFrame vuoto e l'app mostra un messaggio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.metrics import METRIC_PANELS

# Metriche usate per descrivere il profilo di un giocatore di movimento
# (percentili, confronti, giocatori simili): volumi per 90' + efficienza.
PROFILE_METRICS = [
    "goals_per90", "assists_per90", "shots_per90", "shots_on_target_per90", "big_chances_per90",
    "key_passes_per90", "passes_completed_per90", "forward_passes_per90", "pass_accuracy_pct",
    "forward_play_incidence_pct", "recoveries_per90", "touches_per90", "fouls_suffered_per90",
]
SIMILARITY_FEATURES = [
    "goals_per90", "shots_per90", "shots_on_target_per90", "big_chances_per90", "assists_per90",
    "key_passes_per90", "passes_completed_per90", "forward_passes_per90", "recoveries_per90",
    "touches_per90", "fouls_suffered_per90", "pass_accuracy_pct", "forward_play_incidence_pct",
]


# --------------------------------------------------------------------------- #
# Squadre
# --------------------------------------------------------------------------- #

def standings_progression(team_match_all: pd.DataFrame) -> pd.DataFrame:
    """Classifica ricalcolata dopo ogni giornata: una riga per (giornata, squadra)
    con punti cumulati e posizione. Stessi criteri di ordinamento della
    classifica principale (punti, differenza reti, gol fatti)."""
    if team_match_all.empty:
        return pd.DataFrame()
    frames = []
    for giornata in sorted(team_match_all["giornata"].dropna().unique()):
        upto = team_match_all[team_match_all["giornata"] <= giornata]
        table = upto.groupby("team", as_index=False).agg(
            points=("points", "sum"), goals_for=("goals_for", "sum"), goals_against=("goals_against", "sum"),
        )
        table["goal_difference"] = table["goals_for"] - table["goals_against"]
        table = table.sort_values(["points", "goal_difference", "goals_for"], ascending=False).reset_index(drop=True)
        table["position"] = table.index + 1
        table["giornata"] = int(giornata)
        frames.append(table)
    return pd.concat(frames, ignore_index=True)


def team_form(team_match_all: pd.DataFrame, n: int = 5) -> dict[str, list[dict]]:
    """Ultimi n risultati per squadra (dal più vecchio al più recente), con
    avversario e punteggio per il tooltip."""
    form: dict[str, list[dict]] = {}
    for team, games in team_match_all.sort_values("giornata").groupby("team"):
        form[team] = [
            {
                "result": r["result"], "code": r["result"],
                "detail": f"MD{int(r['giornata'])} {'vs' if r['venue'] == 'home' else '@'} {r['opponent'].title()} "
                          f"{int(r['goals_for'])}-{int(r['goals_against'])}",
            }
            for _, r in games.tail(n).iterrows()
        ]
    return form


def home_away_split(team_match_df: pd.DataFrame) -> pd.DataFrame:
    """Rendimento in casa e in trasferta per squadra: punti a partita, gol
    fatti/subiti a partita e tiri a partita, una colonna per sede."""
    if team_match_df.empty:
        return pd.DataFrame()
    agg = team_match_df.groupby(["team", "venue"]).agg(
        matches=("match_id", "size"), ppg=("points", "mean"),
        gf=("goals_for", "mean"), ga=("goals_against", "mean"), shots=("Tiri", "mean"),
    ).unstack("venue")
    agg.columns = [f"{metric}_{venue}" for metric, venue in agg.columns]
    return agg.reset_index()


def team_percentiles(team_summary_df: pd.DataFrame, avg_cols: list[str] | None = None) -> pd.DataFrame:
    """Percentile (0-100) di ogni squadra su ogni media di METRIC_PANELS,
    rispetto alle altre squadre della vista. Formato largo: una riga per squadra."""
    cols = avg_cols or [p.avg_col for p in METRIC_PANELS]
    out = team_summary_df[["team"]].copy()
    for col in cols:
        out[col] = team_summary_df[col].rank(pct=True, method="average") * 100
    return out


# --------------------------------------------------------------------------- #
# Giocatori
# --------------------------------------------------------------------------- #

def player_percentiles(outfield: pd.DataFrame, targets: list[tuple[str, str]], metrics: list[str]) -> pd.DataFrame:
    """Percentili di uno o più giocatori rispetto al pool idoneo per minuti.
    Formato lungo: entity, metric, value, percentile. I giocatori sotto
    soglia sono esclusi (percentile troppo rumoroso)."""
    pool = outfield[outfield["eligible_rates"]]
    rows = []
    for player, team in targets:
        target = pool[(pool["player"] == player) & (pool["team"] == team)]
        if target.empty:
            continue
        for metric in metrics:
            values = pool[metric].dropna()
            value = target[metric].iloc[0]
            if values.empty or pd.isna(value):
                continue
            pct = (values < value).mean() * 100 + (values == value).mean() * 50
            rows.append({"entity": f"{player} · {team.title()}", "player": player, "team": team,
                         "metric": metric, "value": value, "percentile": pct})
    return pd.DataFrame(rows)


def similar_players(
    outfield: pd.DataFrame, player: str, team: str, features: list[str] | None = None, n: int = 8,
) -> pd.DataFrame:
    """Giocatori con il profilo statistico più simile: similarità del coseno
    sui valori per 90' standardizzati (z-score) del pool idoneo. Non conosce
    il ruolo, ma giocatori con profili simili tendono a occupare zone e
    compiti simili — utile per trovare alternative in squadre diverse."""
    features = features or SIMILARITY_FEATURES
    pool = outfield[outfield["eligible_rates"]].reset_index(drop=True)
    mask = (pool["player"] == player) & (pool["team"] == team)
    if not mask.any() or len(pool) < 3:
        return pd.DataFrame()
    X = pool[features].astype(float)
    X = (X - X.mean()) / X.std(ddof=0).replace(0, np.nan)
    X = X.fillna(0.0).to_numpy()
    norms = np.linalg.norm(X, axis=1)
    norms[norms == 0] = np.nan
    target = X[mask.to_numpy()][0]
    sims = X @ target / (norms * np.linalg.norm(target))
    result = pool.assign(similarity=sims * 100)
    result = result[~mask].dropna(subset=["similarity"])
    return result.sort_values("similarity", ascending=False).head(n)


def player_match_series(match_log: pd.DataFrame, player: str, team: str) -> pd.DataFrame:
    """Serie partita per partita di un giocatore di movimento, con avversario."""
    log = match_log[(match_log["player"] == player) & (match_log["team"] == team) & (match_log["role"] == "OUT")]
    return log.sort_values("giornata")

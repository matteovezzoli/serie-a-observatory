"""Aggregazione season-level per giocatore: porta in funzioni riutilizzabili
la logica delle Celle 16-18 di exploration.ipynb.

Stesso contratto di aggregation.build_team_tables: nessuna funzione qui
solleva per un problema nei dati — ritornano sempre le tabelle disponibili
più un `quality_df`, e l'app decide cosa mostrare.

Note sul modello dati (dalla Cella 16):
- La colonna "PA" ha significati DIVERSI a seconda del ruolo: per un
  portiere è "Parate", per un giocatore di movimento "Palloni giocati in
  avanti riusciti". Portieri (role == "GK") e movimento (role == "OUT")
  vengono quindi aggregati SEPARATAMENTE.
- In alcuni PDF il campo MIN non contiene cifre (dato assente nel file
  sorgente). Per i tassi per-90 quelle righe sono escluse SIA dai minuti SIA
  dalle statistiche (colonne "_timed"), altrimenti il numeratore include
  partite di cui manca il denominatore. I totali grezzi restano su tutte le
  partite.
- Precisione passaggi: media PESATA (completati totali / tentati totali). I
  tentati sono ricostruiti da P e P(%) (arrotondato a intero nel PDF):
  approssimazione.
- DAM include entrambi i gialli dell'espulsione per doppia ammonizione, e
  la stessa riga ha anche ESP: gialli_equivalenti = AMM + 2*DAM, rossi
  diretti = ESP - DAM.
- STATISTICHE GIOCATORE non contiene ruolo/posizione né Dribbling/Passaggi
  in ultimo terzo per singolo giocatore.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

OUTFIELD_RAW_COLUMNS = ["G", "AUT", "T", "TP", "PT", "OG", "FS", "PG", "AS", "PC", "P", "P(%)", "PA", "R", "AMM", "DAM", "ESP"]
GK_RAW_COLUMNS = ["GS", "AUT", "PA", "AS", "RE", "LU", "AMM", "DAM", "ESP"]

# nome aggregato -> colonna sorgente (giocatori di movimento)
OUTFIELD_TOTALS = {
    "goals": "G",
    "own_goals": "AUT",
    "shots": "T",
    "shots_on_target": "TP",
    "woodwork": "PT",
    "big_chances": "OG",
    "fouls_suffered": "FS",
    "touches": "PG",
    "assists": "AS",
    "key_passes": "PC",
    "passes_completed": "P",
    "forward_passes": "PA",
    "recoveries": "R",
    "amm": "AMM",
    "dam": "DAM",
    "esp": "ESP",
}

# Metriche con tasso per-90 (sottoinsieme di OUTFIELD_TOTALS)
PER90_METRICS = [
    "goals", "assists", "shots", "shots_on_target", "key_passes", "recoveries",
    "touches", "fouls_suffered", "big_chances", "passes_completed", "forward_passes",
]

# Quote sulla produzione di squadra: nome -> (colonna giocatore aggregata, colonna in team_match_df)
SHARE_SOURCES = {
    "goal_share_pct": ("goals", "goals_for"),
    "shot_share_pct": ("shots", "Tiri"),
    "key_pass_share_pct": ("key_passes", "Passaggi chiave"),
    "recovery_share_pct": ("recoveries", "Recuperi"),
    "pass_share_pct": ("passes_completed", "Passaggi riusciti"),
}

MIN_SHOTS_FOR_PCT = 5  # sotto questo volume la % di tiri in porta / conversione è solo rumore


@dataclass
class PlayerTables:
    outfield: pd.DataFrame      # una riga per (giocatore, squadra), giocatori di movimento
    keepers: pd.DataFrame       # una riga per (portiere, squadra)
    match_log: pd.DataFrame     # una riga per giocatore per partita, colonne numeriche pulite
    quality_df: pd.DataFrame
    min_minutes: int
    min_passes: int


def default_thresholds(n_matchdays: int, single_round: bool) -> tuple[int, int]:
    """Soglie di default (minuti per i tassi, passaggi per le %).
    Multi-giornata: minuti = 40% dei minuti disponibili, minimo 180' (Cella 16);
    passaggi = 50. Singola giornata: il minimo 180' escluderebbe tutti, quindi
    solo il 40% (36') e un volume passaggi proporzionato (20)."""
    if single_round:
        return round(0.4 * 90), 20
    return max(180, round(0.4 * 90 * n_matchdays)), 50


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Garantisce che le colonne esistano anche se assenti in questo sottoinsieme
    (es. AUT-autogol, raro) — altrimenti .agg() con nome fisso va in KeyError."""
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = np.nan
    return df


def _team_totals_on_played_matches(match_log: pd.DataFrame, team_match_df: pd.DataFrame) -> pd.DataFrame:
    """Totali di squadra sommati SOLO sulle partite in cui il giocatore è
    presente nel tabellino: la quota misura quanto passa da lui quando è in
    campo, senza penalizzare chi ha saltato partite (infortunio, arrivo a
    stagione in corso)."""
    team_cols = sorted({team_col for _, team_col in SHARE_SOURCES.values()})
    appearances = match_log[["player", "team", "match_id"]].drop_duplicates()
    merged = appearances.merge(team_match_df[["match_id", "team", *team_cols]], on=["match_id", "team"], how="left")
    return merged.groupby(["player", "team"], as_index=False)[team_cols].sum().rename(
        columns={c: f"team_{c}" for c in team_cols}
    )


def build_player_tables(
    player_stats_df: pd.DataFrame,
    team_match_df: pd.DataFrame,
    standings_df: pd.DataFrame,
    min_minutes: int | None = None,
    min_passes: int | None = None,
) -> PlayerTables:
    """Da player_stats_df (già filtrato sulla vista corrente) costruisce le
    tabelle giocatore. team_match_df deve coprire la stessa vista (serve per
    le quote di squadra); standings_df dà la posizione in classifica usata
    per il contesto squadra (tipicamente la classifica fino alla giornata
    selezionata, anche nella vista a giornata singola)."""
    if player_stats_df.empty:
        empty = pd.DataFrame()
        quality = pd.DataFrame({"check": ["player_rows_present"], "passed": [False]})
        return PlayerTables(empty, empty, empty, quality, min_minutes or 0, min_passes or 0)

    n_matchdays = int(player_stats_df["giornata"].nunique())
    default_min, default_passes = default_thresholds(n_matchdays, single_round=n_matchdays == 1)
    min_minutes = default_min if min_minutes is None else min_minutes
    min_passes = default_passes if min_passes is None else min_passes

    log = _ensure_columns(player_stats_df, sorted(set(OUTFIELD_RAW_COLUMNS) | set(GK_RAW_COLUMNS)))
    log["MIN"] = pd.to_numeric(log["MIN"], errors="coerce")
    rank_map = standings_df.set_index("team")["rank"]

    # --- Giocatori di movimento ------------------------------------------------
    out = log[log["role"] == "OUT"].copy()
    for name in PER90_METRICS:
        out[f"{name}_timed"] = out[OUTFIELD_TOTALS[name]].where(out["MIN"].notna())
    out["passes_attempted"] = np.where(out["P(%)"] > 0, out["P"] / (out["P(%)"] / 100), np.nan)

    outfield = out.groupby(["player", "team"], as_index=False).agg(
        matches=("match_id", "size"),
        matches_no_minutes=("MIN", lambda s: int(s.isna().sum())),
        minutes=("MIN", "sum"),
        passes_attempted=("passes_attempted", "sum"),
        **{name: (src, "sum") for name, src in OUTFIELD_TOTALS.items()},
        **{f"{name}_timed": (f"{name}_timed", "sum") for name in PER90_METRICS},
    )

    outfield["goal_contributions"] = outfield["goals"] + outfield["assists"]
    outfield["pass_accuracy_pct"] = outfield["passes_completed"] / outfield["passes_attempted"].replace(0, np.nan) * 100
    outfield["forward_play_incidence_pct"] = outfield["forward_passes"] / outfield["passes_completed"].replace(0, np.nan) * 100
    enough_shots = outfield["shots"] >= MIN_SHOTS_FOR_PCT
    outfield["shot_accuracy_pct"] = np.where(enough_shots, outfield["shots_on_target"] / outfield["shots"] * 100, np.nan)
    outfield["conversion_pct"] = np.where(enough_shots, outfield["goals"] / outfield["shots"] * 100, np.nan)
    outfield["yellow_equivalent"] = outfield["amm"] + 2 * outfield["dam"]
    outfield["direct_reds"] = (outfield["esp"] - outfield["dam"]).clip(lower=0)

    outfield["eligible_rates"] = outfield["minutes"] >= min_minutes
    outfield["eligible_pct"] = outfield["eligible_rates"] & (outfield["passes_completed"] >= min_passes)
    for name in PER90_METRICS:
        outfield[f"{name}_per90"] = np.where(
            outfield["eligible_rates"], outfield[f"{name}_timed"] / outfield["minutes"] * 90, np.nan
        )
    outfield["goal_contributions_per90"] = outfield["goals_per90"] + outfield["assists_per90"]

    # Quote sulla produzione di squadra (Cella 18), per tutte le squadre:
    # il filtro "squadre deboli" lo applica l'app sulla colonna team_rank.
    outfield = outfield.merge(_team_totals_on_played_matches(out, team_match_df), on=["player", "team"], how="left")
    for share, (player_col, team_col) in SHARE_SOURCES.items():
        outfield[share] = outfield[player_col] / outfield[f"team_{team_col}"].replace(0, np.nan) * 100

    outfield["team_rank"] = outfield["team"].map(rank_map)
    outfield = (
        outfield.drop(columns=[f"{n}_timed" for n in PER90_METRICS])
        .sort_values("minutes", ascending=False)
        .reset_index(drop=True)
    )

    # --- Portieri ------------------------------------------------------------
    gk = log[log["role"] == "GK"].copy()
    gk["goals_conceded_timed"] = gk["GS"].where(gk["MIN"].notna())
    gk["saves_timed"] = gk["PA"].where(gk["MIN"].notna())
    keepers = gk.groupby(["player", "team"], as_index=False).agg(
        matches=("match_id", "size"),
        matches_no_minutes=("MIN", lambda s: int(s.isna().sum())),
        minutes=("MIN", "sum"),
        goals_conceded=("GS", "sum"),
        goals_conceded_timed=("goals_conceded_timed", "sum"),
        saves=("PA", "sum"),  # per il portiere, PA = Parate
        saves_timed=("saves_timed", "sum"),
        respinte=("RE", "sum"),
        long_balls=("LU", "sum"),
        own_goals=("AUT", "sum"),
        assists=("AS", "sum"),
        amm=("AMM", "sum"),
        dam=("DAM", "sum"),
        esp=("ESP", "sum"),
    )
    faced = keepers["saves"] + keepers["goals_conceded"]
    keepers["save_pct"] = keepers["saves"] / faced.replace(0, np.nan) * 100
    keepers["eligible_rates"] = keepers["minutes"] >= min_minutes
    keepers["goals_conceded_per90"] = np.where(
        keepers["eligible_rates"], keepers["goals_conceded_timed"] / keepers["minutes"] * 90, np.nan
    )
    keepers["saves_per90"] = np.where(keepers["eligible_rates"], keepers["saves_timed"] / keepers["minutes"] * 90, np.nan)
    # Porta inviolata: partita intera (90'+) senza gol subiti
    clean_sheets = (
        gk[gk["MIN"] >= 90].assign(clean_sheets=lambda f: f["GS"].fillna(0) == 0)
        .groupby(["player", "team"], as_index=False)["clean_sheets"].sum()
    )
    keepers = keepers.merge(clean_sheets, on=["player", "team"], how="left")
    keepers["clean_sheets"] = keepers["clean_sheets"].fillna(0).astype(int)
    keepers["team_rank"] = keepers["team"].map(rank_map)
    keepers = (
        keepers.drop(columns=["goals_conceded_timed", "saves_timed"])
        .sort_values("minutes", ascending=False)
        .reset_index(drop=True)
    )

    # --- Match log pulito (scheda giocatore / scheda partita) ------------------
    match_log = log.drop(columns=["unassigned_values"], errors="ignore")

    # --- Quality check (non bloccanti) ----------------------------------------
    unassigned = player_stats_df.get("unassigned_values")
    n_unassigned = int(unassigned.str.len().gt(0).sum()) if unassigned is not None else 0
    quality_checks = {
        "player_rows_for_every_match": set(team_match_df["match_id"]) <= set(player_stats_df["match_id"]),
        "no_unassigned_values": n_unassigned == 0,
        "two_teams_per_match": bool((player_stats_df.groupby("match_id")["team"].nunique() == 2).all()),
    }
    quality_df = pd.DataFrame({"check": list(quality_checks), "passed": list(quality_checks.values())})

    return PlayerTables(outfield, keepers, match_log, quality_df, int(min_minutes), int(min_passes))


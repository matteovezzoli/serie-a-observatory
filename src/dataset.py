"""Dataset estratto dai Match Report, salvato in CSV leggibili.

I PDF ufficiali restano la fonte, ma non vanno nel repository (peso e
diritti della Lega). Dopo ogni lettura dei PDF la dashboard salva qui le
due tabelle grezze; senza PDF (es. dopo un clone da GitHub) le rilegge da
qui. Tutto il resto (classifiche, per 90', percentili...) è ricalcolato a
partire da queste due tabelle.

- matches.csv: una riga per partita (metadati + 16 statistiche squadra
  casa/ospite + stato di lettura di ogni metrica)
- players.csv: una riga per giocatore per partita (tabellino individuale)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path("data/processed")
MATCHES_CSV = PROCESSED_DIR / "matches.csv"
PLAYERS_CSV = PROCESSED_DIR / "players.csv"


def export_dataset(match_stats_df: pd.DataFrame, player_stats_df: pd.DataFrame) -> None:
    """Scrive le due tabelle. La colonna diagnostica unassigned_values (liste)
    non va nel CSV: serve solo durante la validazione del parser."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    match_stats_df.to_csv(MATCHES_CSV, index=False)
    player_stats_df.drop(columns=["unassigned_values"], errors="ignore").to_csv(PLAYERS_CSV, index=False)


def dataset_available() -> bool:
    return MATCHES_CSV.exists() and PLAYERS_CSV.exists()


def dataset_signature() -> tuple:
    """Firma (nome, mtime) dei CSV: invalida la cache quando vengono rigenerati."""
    return tuple((p.name, p.stat().st_mtime_ns) for p in (MATCHES_CSV, PLAYERS_CSV) if p.exists())


def load_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    match_stats_df = pd.read_csv(MATCHES_CSV, dtype={"match_date": str})
    player_stats_df = pd.read_csv(PLAYERS_CSV)
    return match_stats_df, player_stats_df

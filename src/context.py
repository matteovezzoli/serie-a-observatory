"""Contesto condiviso da tutte le pagine della dashboard: i dati della
vista corrente (giornata + modalità) già aggregati una volta sola."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.aggregation import build_team_tables
from src.analysis import standings_progression, team_form
from src.player_aggregation import PlayerTables, build_player_tables


@dataclass
class Context:
    match_stats_df: pd.DataFrame      # tutte le partite parsate
    player_stats_df: pd.DataFrame     # tutte le righe giocatore parsate
    dati_vista: pd.DataFrame          # partite nella vista corrente
    giornata: int
    single_round: bool
    n_giornate: int
    # squadre — vista corrente
    team_match_df: pd.DataFrame
    team_summary_df: pd.DataFrame
    quality_df: pd.DataFrame
    suspicious_nan_rows: pd.DataFrame
    # squadre — classifica reale fino alla giornata (indipendente dalla vista)
    team_match_all: pd.DataFrame
    standings_df: pd.DataFrame
    progression: pd.DataFrame
    form: dict
    # giocatori
    players: PlayerTables
    highlight_team: str | None = None

    @property
    def view_label(self) -> str:
        return f"Matchday {self.giornata}" if self.single_round else f"Matchdays 1–{self.giornata}"

    @property
    def eyebrow(self) -> str:
        return f"Serie A · {self.view_label} · {len(self.dati_vista)} matches"


def build_context(
    match_stats_df: pd.DataFrame, player_stats_df: pd.DataFrame, giornata: int, single_round: bool,
    min_minutes: int | None, min_passes: int | None,
) -> Context:
    if single_round:
        dati_vista = match_stats_df[match_stats_df["giornata"] == giornata]
    else:
        dati_vista = match_stats_df[match_stats_df["giornata"] <= giornata]

    team_match_df, team_summary_df, quality_df, suspicious = build_team_tables(dati_vista)

    # Classifica "reale" fino alla giornata selezionata: usata per il contesto
    # squadra dei giocatori e per classifica/forma anche nella vista a singola
    # giornata (dove la classifica di una sola partita non direbbe nulla).
    upto = match_stats_df[match_stats_df["giornata"] <= giornata]
    team_match_all, standings_df, _, _ = build_team_tables(upto)

    player_view = (
        player_stats_df[player_stats_df["match_id"].isin(dati_vista["match_id"])]
        if not player_stats_df.empty else player_stats_df
    )
    players = build_player_tables(player_view, team_match_df, standings_df, min_minutes, min_passes)

    return Context(
        match_stats_df=match_stats_df, player_stats_df=player_stats_df, dati_vista=dati_vista,
        giornata=giornata, single_round=single_round, n_giornate=int(dati_vista["giornata"].nunique()),
        team_match_df=team_match_df, team_summary_df=team_summary_df, quality_df=quality_df,
        suspicious_nan_rows=suspicious, team_match_all=team_match_all, standings_df=standings_df,
        progression=standings_progression(team_match_all), form=team_form(team_match_all), players=players,
    )

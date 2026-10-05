"""Parsing della tabella STATISTICHE GIOCATORE dei Match Report.

Stato allineato alla Cella 9 di exploration.ipynb (validato a scala piena:
zero valori non assegnati su 50 partite).

A differenza di STATISTICHE SQUADRE (2 colonne fisse, casa/ospite), qui
ogni riga giocatore ha un NUMERO VARIABILE di valori: una metrica a 0/vuota
per quel giocatore non viene stampata affatto, non stampata come "0". Quindi
non si può mappare per posizione sequenziale ("il 5° valore = 5° colonna") —
serve calibrare i centri X delle colonne dall'header e assegnare ogni valore
alla colonna più vicina, riga per riga. Verificato con coordinate reali su
7 PDF diversi.

Nota sul legenda: la sidebar "Legenda" (a destra della pagina) sta in un
range Y che si sovrappone alle righe giocatore — il raggruppamento per
tolleranza-Y da solo la fonderebbe con la tabella. Va filtrata via X PRIMA
di raggruppare in righe. Verificato su 5 PDF diversi: il Legenda parte
sempre a x0≈391.76, mai prima — usiamo 390 come soglia sicura.

AMM/DAM/ESP: nell'header questi tre si fondono in un unico token
("AMMDAMESP"), ma il token mantiene lo span (x0, x1) dell'intera zona
fusa — largo 43pt sia per riga portiere che di movimento, solo posizionato
più a sinistra o a destra secondo quante colonne reali lo precedono.
Dividendo quello span in 3 terzi uguali si classifica il cartellino:
verificato su 3 casi reali (AMM su ~160 casi, DAM e ESP su 1 caso
ciascuno — J. VÁSQUEZ doppio giallo, GAETANO rosso diretto), il centro
osservato cade entro 1.3pt dal centro predetto in tutti e 3 i casi, e la
stessa formula spiega anche la posizione del portiere (zona spostata a
sinistra, larghezza identica). DAM/ESP restano da confermare su più
partite man mano che se ne accumulano — l'evidenza è solida ma il
campione resta piccolo.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.parsing import (
    NUMERIC_TOKEN,
    extract_match_metadata,
    extract_page_texts,
    extract_stats_page_words,
    find_page,
    group_words_into_lines,
    parse_number,
)

LEGEND_X_THRESHOLD = 390.0
MAX_COLUMN_MATCH_DISTANCE = 8.0  # metà circa del passo tra colonne (~15pt): oltre, la riga va revisionata

GK_COLUMNS = ["MIN", "GS", "AUT", "PA", "AS", "RE", "LU"]
OUTFIELD_COLUMNS = ["MIN", "G", "AUT", "T", "TP", "PT", "OG", "FS", "PG", "AS", "PC", "P", "P(%)", "PA", "R"]

MIN_VALUE_PATTERN = re.compile(r"^\d*'$")  # un '' vuoto (dato mancante nel PDF sorgente) va comunque
# riconosciuto come "qui iniziano i valori", altrimenti scivola dentro il nome del giocatore


# --------------------------------------------------------------------------- #
# Riconoscimento delle righe header (portiere vs movimento)
# --------------------------------------------------------------------------- #

def _is_gk_header(texts: list[str]) -> bool:
    """GS, RE, LU compaiono SOLO nell'header portiere."""
    return "GS" in texts and "RE" in texts and "LU" in texts


def _is_outfield_header(texts: list[str]) -> bool:
    """TP, PT, P(%) insieme compaiono SOLO nell'header di movimento."""
    return "TP" in texts and "PT" in texts and "P(%)" in texts


def _extract_team_name(line: list[dict]) -> str:
    """Nella riga header portiere il nome squadra sono i token prima di 'MIN'
    (uniti: gestisce anche nomi di più parole, es. 'HELLAS VERONA')."""
    tokens = []
    for word in line:
        if word["text"] == "MIN":
            break
        tokens.append(word["text"])
    return " ".join(tokens)


def _column_centers(line: list[dict], expected_cols: list[str]) -> dict[str, float]:
    """Centro X di ogni colonna attesa, letto dall'header di QUESTA pagina
    (mai hardcodato): se il template cambia leggermente da un report
    all'altro, la calibrazione si adatta da sola."""
    return {
        word["text"]: (word["x0"] + word["x1"]) / 2.0
        for word in line
        if word["text"] in expected_cols
    }


# --------------------------------------------------------------------------- #
# Cartellini (zona fusa AMM/DAM/ESP)
# --------------------------------------------------------------------------- #

def _card_zone_bounds(line: list[dict]) -> tuple[float, float] | None:
    """Trova il token header fuso 'AMMDAMESP' e ritorna il suo span (x0, x1)."""
    for word in line:
        if word["text"] == "AMMDAMESP":
            return word["x0"], word["x1"]
    return None


def _classify_card(word: dict, zone_bounds: tuple[float, float] | None) -> str | None:
    """Divide la zona AMM/DAM/ESP fusa in tre terzi uguali e classifica il
    valore in base a dove cade il suo centro. None se il valore è fuori
    da quella zona (davvero non classificabile)."""
    if zone_bounds is None:
        return None
    x0, x1 = zone_bounds
    third = (x1 - x0) / 3
    center = (word["x0"] + word["x1"]) / 2.0
    if not (x0 - 2 <= center <= x1 + 2):  # piccolo margine di tolleranza
        return None
    if center < x0 + third:
        return "AMM"
    elif center < x0 + 2 * third:
        return "DAM"
    else:
        return "ESP"


# --------------------------------------------------------------------------- #
# Parsing di una riga giocatore
# --------------------------------------------------------------------------- #

def _split_name_and_values(line: list[dict]) -> tuple[str, str, list[dict]]:
    """Numero di maglia (1° token) + nome (token fino al primo valore) + token
    di valore (minutaggio 'XX'' o numerico puro). Gestisce nomi multi-parola
    (es. 'J. RODRÍGUEZ', 'UNAI GÓMEZ') perché non si ferma al primo spazio ma
    al primo token che SEMBRA un valore."""
    jersey = line[0]["text"]
    value_start = None
    for i, word in enumerate(line[1:], start=1):
        if MIN_VALUE_PATTERN.match(word["text"]) or NUMERIC_TOKEN.match(word["text"]):
            value_start = i
            break
    if value_start is None:
        return jersey, " ".join(w["text"] for w in line[1:]), []
    name = " ".join(w["text"] for w in line[1:value_start])
    return jersey, name, line[value_start:]


def _nearest_column(word: dict, header_centers: dict[str, float]) -> tuple[str, float]:
    center = (word["x0"] + word["x1"]) / 2.0
    col = min(header_centers, key=lambda c: abs(header_centers[c] - center))
    return col, abs(header_centers[col] - center)


def _parse_player_row(
    line: list[dict], header_centers: dict[str, float], role: str, team: str,
    card_zone: tuple[float, float] | None,
) -> dict[str, object]:
    """Ogni valore va alla colonna più vicina SOLO se entro tolleranza. Un
    valore fuori tolleranza viene prima provato come cartellino (AMM/DAM/ESP,
    vedi _classify_card) — solo se non classificabile nemmeno lì finisce in
    'unassigned_values'. Non sovrascrive MAI una colonna già assegnata
    correttamente (bug reale trovato e corretto in fase di validazione)."""
    jersey, name, value_words = _split_name_and_values(line)
    row: dict[str, object] = {"team": team, "role": role, "jersey": int(jersey), "player": name}
    unassigned_values: list[dict] = []

    for word in value_words:
        col, distance = _nearest_column(word, header_centers)
        if distance <= MAX_COLUMN_MATCH_DISTANCE:
            if col == "MIN":
                stripped = word["text"].rstrip("'")
                row["MIN"] = int(stripped) if stripped else None
            else:
                row[col] = parse_number(word["text"])
            continue

        card = _classify_card(word, card_zone)
        if card is not None:
            row[card] = 1
            continue

        unassigned_values.append({"x0": word["x0"], "text": word["text"], "nearest_col": col})

    row["unassigned_values"] = unassigned_values  # lista vuota = allineamento pulito
    return row


def _looks_like_player_row(line: list[dict]) -> bool:
    return line[0]["text"].isdigit()


# --------------------------------------------------------------------------- #
# Entry point: singolo report -> lista di righe giocatore
# --------------------------------------------------------------------------- #

def parse_player_stats(report_path: Path) -> list[dict]:
    """Estrae la tabella STATISTICHE GIOCATORE (entrambe le squadre, un
    dizionario per giocatore) da un singolo Match Report PDF."""
    pages = extract_page_texts(report_path)
    match_meta = extract_match_metadata(pages)
    page_number, _ = find_page(pages, "STATISTICHE GIOCATORE")

    words = extract_stats_page_words(report_path, page_number)
    table_words = [w for w in words if w["x0"] < LEGEND_X_THRESHOLD]
    lines = group_words_into_lines(table_words)

    records: list[dict] = []
    current_team: str | None = None
    current_header: dict[str, float] | None = None
    current_role: str | None = None
    current_card_zone: tuple[float, float] | None = None

    for line in lines:
        texts = [w["text"] for w in line]

        if "RANKING" in texts:
            break

        if _is_gk_header(texts):
            current_team = _extract_team_name(line)
            current_header = _column_centers(line, GK_COLUMNS)
            current_card_zone = _card_zone_bounds(line)
            current_role = "GK"
            continue

        if _is_outfield_header(texts):
            current_header = _column_centers(line, OUTFIELD_COLUMNS)
            current_card_zone = _card_zone_bounds(line)
            current_role = "OUT"
            continue

        if current_header is None or not _looks_like_player_row(line):
            continue

        row = _parse_player_row(line, current_header, current_role, current_team, current_card_zone)
        row["match_id"] = match_meta["match_id"]
        row["giornata"] = match_meta["giornata"]
        records.append(row)

    return records

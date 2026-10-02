"""Parsing dei Match Report PDF ufficiali della Lega Serie A.

Contiene tutta la logica per estrarre metadati e statistiche di squadra
da un singolo PDF. Nessuna aggregazione multi-partita qui: quella vive
in `aggregation.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pdfplumber

import logging

logging.getLogger("pdfminer").setLevel(logging.ERROR)


# --------------------------------------------------------------------------- #
# Costanti
# --------------------------------------------------------------------------- #

CORE_METRICS = [
    "Tiri", "Tiri in porta", "Tiri fuori", "Tiri respinti",
    "Passaggi chiave", "Falli fatti", "Corner", "Fuorigioco", "Dribbling",
    "Passaggi riusciti", "Passaggi riusciti/tentati (%)",
    "Passaggi riusciti in ultimo terzo", "Palloni giocati in avanti riusciti",
    "Passaggi lunghi", "Parate", "Recuperi",
]

TEAM_NAME_PATTERN = r"[A-ZÀ-ÖØ-Ý]+(?:\s+[A-ZÀ-ÖØ-Ý]+)*"
MATCH_LINE_PATTERN = re.compile(rf"({TEAM_NAME_PATTERN})\s+(\d+)-(\d+)\s+({TEAM_NAME_PATTERN})")
NUMERIC_TOKEN = re.compile(r"^\d+(?:[.,]\d+)?%?$")


# --------------------------------------------------------------------------- #
# Utility di basso livello
# --------------------------------------------------------------------------- #

def parse_number(value: str) -> float:
    """Converte una stringa numerica (virgola decimale o %) in float."""
    return float(value.replace(",", ".").replace("%", "").strip())


def extract_page_texts(report_path: Path, max_pages: int | None = None) -> list[str]:
    """Estrae il testo di ogni pagina. max_pages limita l'estrazione per i pass leggeri."""
    with pdfplumber.open(report_path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        return [page.extract_text() or "" for page in pages]


def extract_match_metadata(pages: list[str]) -> dict[str, object]:
    """Legge giornata, data e risultato dalle prime pagine.
    Il pattern TEAM punteggio-punteggio TEAM viene cercato riga per riga
    con fullmatch: SOLO una riga che coincide per intero può fare match.
    Necessario perché \\s+ include il newline — un .search() sull'intero
    blocco di testo di pagina "scivolerebbe" su più righe reali,
    agganciando testo spurio (es. l'anno del campionato) invece della
    riga di risultato vera."""
    match = None
    for text in pages[:3]:
        for line in text.splitlines():
            candidate = MATCH_LINE_PATTERN.fullmatch(line.strip())
            if candidate:
                match = candidate
                break
        if match:
            break
    if match is None:
        raise ValueError("Risultato non riconosciuto nelle prime pagine.")

    home, home_score, away_score, away = match.groups()
    home_score, away_score = int(home_score), int(away_score)
    winner = home if home_score > away_score else away if away_score > home_score else "Pareggio"

    giornata_match = re.search(r"Giornata\s+(\d+)", pages[0])
    date_match = re.search(r"(\d{2}/\d{2}/\d{4})", pages[0])
    giornata = int(giornata_match.group(1)) if giornata_match else None
    match_date = date_match.group(1) if date_match else None

    match_id = (
        f"G{giornata:02d}_{home}_{away}" if giornata is not None
        else f"{home}_{away}_{match_date or 'UNK'}"
    )

    return {
        "match_id": match_id, "giornata": giornata, "match_date": match_date,
        "home": home, "away": away,
        "home_score": home_score, "away_score": away_score, "winner": winner,
    }


def find_page(pages: list[str], marker: str) -> tuple[int, str]:
    for page_number, text in enumerate(pages, start=1):
        if marker in text:
            return page_number, text
    raise ValueError(f"Sezione non trovata: {marker}")


def parse_team_metric_line(section: str, metric: str) -> list[str]:
    pattern = re.compile(rf"(?<!\w){re.escape(metric)}(?!\w)\s+([\d.,%\s/]+)$")
    for line in section.splitlines():
        m = pattern.search(line.strip())
        if m:
            return re.findall(r"\d+(?:[.,]\d+)?", m.group(1))
    return []


def extract_stats_page_words(report_path: Path, page_number: int) -> list[dict]:
    """Estrae le words con bounding box (x0, x1, top) della pagina indicata,
    necessarie per la disambiguazione posizionale casa/ospite."""
    with pdfplumber.open(report_path) as pdf:
        return pdf.pages[page_number - 1].extract_words()


def group_words_into_lines(words: list[dict], y_tolerance: float = 2.0) -> list[list[dict]]:
    """Raggruppa le words in righe visive per coordinata Y ('top'), ordinate
    dall'alto in basso. Tolleranza stretta apposta: la stessa pagina che ha
    fuso 'GENOA NAPOLI' e 'Tiri 16 9' in extract_text() potrebbe farlo anche
    qui se il gap verticale reale è piccolo — con tolleranza 2pt separiamo
    correttamente anche righe molto ravvicinate."""
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        for line in lines:
            if abs(line[0]["top"] - word["top"]) <= y_tolerance:
                line.append(word)
                break
        else:
            lines.append([word])
    for line in lines:
        line.sort(key=lambda w: w["x0"])
    return sorted(lines, key=lambda line: line[0]["top"])


def filter_lines_after_marker(lines: list[list[dict]], marker_tokens: list[str]) -> list[list[dict]]:
    """Tiene solo le righe dopo quella che contiene tutti i marker_tokens
    (es. ['STATISTICHE','SQUADRE']), per non far contaminare la calibrazione
    da sezioni sopra come POSSESSO PALLA."""
    for index, line in enumerate(lines):
        texts = [w["text"] for w in line]
        if all(token in texts for token in marker_tokens):
            return lines[index + 1:]
    return lines  # marker non trovato: fallback, meglio di niente


def split_label_and_values(line: list[dict]) -> tuple[str, list[dict]]:
    """Separa una riga in (etichetta, token numerici finali), prendendo i
    numeri dalla coda finché matchano NUMERIC_TOKEN — indipendente da quante
    parole compongono l'etichetta o da testo fuso davanti (es. nomi squadra)."""
    value_tokens: list[dict] = []
    for word in reversed(line):
        if NUMERIC_TOKEN.match(word["text"]):
            value_tokens.insert(0, word)
        else:
            break
    label = " ".join(w["text"] for w in line[: len(line) - len(value_tokens)])
    return label, value_tokens


def label_matches_metric(label: str, metric: str) -> bool:
    """Confronta gli ultimi N token dell'etichetta con quelli della metrica
    (suffix match), non l'uguaglianza esatta — robusto a testo fuso davanti."""
    label_tokens, metric_tokens = label.split(), metric.split()
    return len(label_tokens) >= len(metric_tokens) and label_tokens[-len(metric_tokens):] == metric_tokens


def build_column_reference(lines: list[list[dict]]) -> tuple[float, float] | None:
    """Calibra il CENTRO ORIZZONTALE (x_center) delle colonne casa/ospite usando
    tutte le righe NON ambigue (esattamente 2 valori). Rispetto a x1, il centro
    è molto più stabile sia con cifre singole che doppie."""
    home_centers, away_centers = [], []
    for line in lines:
        _, values = split_label_and_values(line)
        if len(values) == 2:
            home_centers.append((values[0]["x0"] + values[0]["x1"]) / 2.0)
            away_centers.append((values[1]["x0"] + values[1]["x1"]) / 2.0)
    if not home_centers:
        return None
    return float(np.median(home_centers)), float(np.median(away_centers))


def recover_ambiguous_metric(
    lines: list[list[dict]], metric: str, column_ref: tuple[float, float], min_margin: float = 2.0
) -> tuple[float, float] | None:
    """Per la riga di 'metric' con UN SOLO valore, decide casa/ospite confrontando
    il centro orizzontale del valore con le colonne calibrate. Se il margine è
    sotto min_margin (troppo ambiguo), ritorna None lasciando il fallback a fillna."""
    home_ref, away_ref = column_ref
    for line in lines:
        label, values = split_label_and_values(line)
        if len(values) != 1 or not label_matches_metric(label, metric):
            continue

        val_center = (values[0]["x0"] + values[0]["x1"]) / 2.0
        value = parse_number(values[0]["text"])

        dist_home = abs(val_center - home_ref)
        dist_away = abs(val_center - away_ref)

        if abs(dist_home - dist_away) < min_margin:
            return None
        return (value, 0.0) if dist_home < dist_away else (0.0, value)
    return None


# --------------------------------------------------------------------------- #
# Entry point: parsing di un intero report
# --------------------------------------------------------------------------- #

def parse_full_report(report_path: Path) -> dict[str, object]:
    pages = extract_page_texts(report_path)
    parsed = extract_match_metadata(pages)
    parsed["pdf_name"] = report_path.name
    parsed["pages"] = len(pages)

    stats_page, stats_text = find_page(pages, "STATISTICHE SQUADRE")
    section = stats_text[stats_text.index("STATISTICHE SQUADRE"):]
    parsed["stats_page"] = stats_page

    raw_lines = group_words_into_lines(extract_stats_page_words(report_path, stats_page))
    stats_lines = filter_lines_after_marker(raw_lines, ["STATISTICHE", "SQUADRE"])
    column_ref = build_column_reference(stats_lines)

    for metric in CORE_METRICS:
        values = parse_team_metric_line(section, metric)
        if len(values) >= 2:
            parsed[f"{metric}_home"] = parse_number(values[0])
            parsed[f"{metric}_away"] = parse_number(values[-1])
            parsed[f"{metric}_status"] = "parsed"
            continue

        recovered = recover_ambiguous_metric(stats_lines, metric, column_ref) if column_ref else None
        if recovered is not None:
            parsed[f"{metric}_home"], parsed[f"{metric}_away"] = recovered
            parsed[f"{metric}_status"] = "recovered_zero"
        else:
            parsed[f"{metric}_home"] = np.nan
            parsed[f"{metric}_away"] = np.nan
            parsed[f"{metric}_status"] = "review"

    return parsed

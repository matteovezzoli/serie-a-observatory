"""Aggiornamento incrementale del dataset dai Match Report ufficiali.

Interroga l'API dei contenuti della Lega Serie A (la stessa usata dal sito
legaseriea.it) e confronta l'elenco dei Match Report con il registro
data/processed/reports.csv:

- report nuovi: scaricati, letti con lo stesso parser della dashboard e
  aggiunti ai CSV;
- report corretti: la Lega ricarica spesso il PDF da 0 a 12 giorni dopo la
  partita (minutaggi, tiri...). Se la data di ultimo aggiornamento è più
  recente di quella registrata, la partita viene riletta e le sue righe
  sostituite;
- report di altre competizioni (Coppa Italia): riconosciuti dall'intestazione
  del PDF, registrati come 'other' e non più riscaricati.

Se un controllo fallisce non scrive nulla ed esce con codice 1: il workflow
GitHub Actions diventa rosso e la dashboard continua a mostrare i dati
precedenti, mai dati parziali.

Uso:
    python update_dataset.py             # aggiorna (partite nuove + report corretti)
    python update_dataset.py --dry-run   # mostra cosa farebbe, senza scaricare né scrivere
    python update_dataset.py --rebuild   # rilegge tutti i report della stagione (es. dopo una modifica al parser)

I PDF scaricati restano in locale (data/giornata_NN/, esclusi da git) per il
notebook; un report corretto sovrascrive la copia locale con lo stesso nome.
A inizio di una nuova stagione vanno aggiornati SEASON e SEASON_START.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pandas as pd

from src.dataset import PROCESSED_DIR, dataset_available, export_dataset, load_dataset
from src.parsing import extract_page_texts, parse_full_report
from src.player_parsing import parse_player_stats

API_URL = "https://dapi.legaseriea.it/v2/content/it-it/documents"
SEASON = "2026-2027"
SEASON_START = "2026-07-01"  # i report pubblicati prima appartengono a stagioni precedenti
COMPETITION = "SERIE A"

DATA_DIR = Path("data")
REPORTS_CSV = PROCESSED_DIR / "reports.csv"
REPORT_COLUMNS = ["pdf_name", "status", "match_id", "published", "updated", "header"]
USER_AGENT = "serie-a-observatory/1.0 (+https://github.com/matteovezzoli/serie-a-observatory)"


# --------------------------------------------------------------------------- #
# Rete
# --------------------------------------------------------------------------- #

def http_get(url: str, attempts: int = 3) -> bytes:
    """GET con qualche tentativo: un errore di rete temporaneo non deve far
    fallire l'aggiornamento della settimana."""
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except OSError:
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def list_match_reports(since: str) -> list[dict]:
    """Tutti i Match Report pubblicati da `since` in poi. L'API li restituisce
    dal più recente: ci si ferma alla prima pagina che scende sotto `since`."""
    url = f"{API_URL}?$limit=100&tags.slug=match-report"
    reports: list[dict] = []
    while url:
        page = json.loads(http_get(url))
        items = page.get("items", [])
        for item in items:
            file = item.get("file") or {}
            if item.get("contentDate", "") >= since and file.get("downloadUrl"):
                reports.append({
                    "pdf_name": file["originalFileName"],
                    "url": file["downloadUrl"],
                    "published": item["contentDate"][:19],
                    "updated": (item.get("lastUpdatedDate") or item["contentDate"])[:19],
                })
        if not items or min(i.get("contentDate", "") for i in items) < since:
            break
        url = (page.get("pagination") or {}).get("nextUrl")
    # a volte un report corretto è caricato come documento nuovo senza togliere
    # il vecchio (stesso nome file): vale la versione aggiornata più di recente
    latest: dict[str, dict] = {}
    for r in reports:
        if r["pdf_name"] not in latest or r["updated"] > latest[r["pdf_name"]]["updated"]:
            latest[r["pdf_name"]] = r
    return list(latest.values())


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #

def competition_line(pdf_path: Path) -> str:
    """Riga di intestazione con competizione e stagione, es. 'SERIE A ENILIVE 2026-2027'
    oppure 'COPPA ITALIA FRECCIAROSSA 2026-2027'."""
    lines = [l.strip() for l in extract_page_texts(pdf_path, max_pages=1)[0].splitlines()[:6]]
    return next((l for l in lines if l.upper().startswith(COMPETITION)), " / ".join(lines[1:3]))


def classify(header: str) -> str:
    """'serie_a' = Serie A della stagione configurata; 'other' = altra competizione;
    'wrong_season' = Serie A di un'altra stagione (SEASON da aggiornare)."""
    if not header.upper().startswith(COMPETITION):
        return "other"
    return "serie_a" if SEASON in header else "wrong_season"


def local_destination(pdf_name: str, giornata: int) -> Path:
    """Copia locale da sovrascrivere se esiste già (anche in cartelle create a
    mano, es. data/quinta/), altrimenti data/giornata_NN/."""
    existing = next((p for p in DATA_DIR.glob(f"*/{pdf_name}") if p.is_file()), None)
    return existing or DATA_DIR / f"giornata_{giornata:02d}" / pdf_name


# --------------------------------------------------------------------------- #
# Validazione
# --------------------------------------------------------------------------- #

def validate(new_matches: pd.DataFrame, new_players: pd.DataFrame, kept_matches: pd.DataFrame) -> list[str]:
    """Controlli bloccanti sulle partite lette in questo run. Indipendenti da
    src/data_quality.py, che resta a uso esclusivo del notebook."""
    problems: list[str] = []
    dup = new_matches["match_id"].duplicated()
    if dup.any():
        problems.append(f"Duplicate matches in the batch: {sorted(new_matches.loc[dup, 'match_id'])}")
    clash = set(new_matches["match_id"]) & set(kept_matches.get("match_id", []))
    if clash:
        problems.append(f"Matches already in the dataset under another file name: {sorted(clash)}")
    if new_matches["giornata"].isna().any():
        problems.append("Matchday not recognised in some reports.")

    for match_id in new_matches["match_id"]:
        rows = new_players[new_players["match_id"] == match_id] if not new_players.empty else new_players
        if rows.empty:
            problems.append(f"{match_id}: no player rows.")
            continue
        if rows["team"].nunique() != 2:
            problems.append(f"{match_id}: {rows['team'].nunique()} teams in the player table (expected 2).")
        unassigned = int(rows["unassigned_values"].map(len).sum()) if "unassigned_values" in rows else 0
        if unassigned:
            problems.append(f"{match_id}: {unassigned} values not assigned to a column.")
    return problems


def review_warnings(new_matches: pd.DataFrame) -> list[str]:
    """Statistiche squadra non lette (stato 'review'): non bloccano, la
    dashboard le gestisce già come valori mancanti."""
    status_cols = [c for c in new_matches.columns if c.endswith("_status")]
    flagged = new_matches.melt(id_vars="match_id", value_vars=status_cols)
    flagged = flagged[flagged["value"] == "review"]
    return [f"{r.match_id}: '{r.variable.removesuffix('_status')}' not read (left empty)" for r in flagged.itertuples()]


# --------------------------------------------------------------------------- #
# Registro e output
# --------------------------------------------------------------------------- #

def load_registry() -> pd.DataFrame:
    if REPORTS_CSV.exists():
        return pd.read_csv(REPORTS_CSV, dtype=str).fillna("")
    return pd.DataFrame(columns=REPORT_COLUMNS)


def pending_reports(reports: list[dict], registry: pd.DataFrame) -> list[dict]:
    """Report da (ri)scaricare: mai visti, oppure di Serie A e aggiornati dalla
    Lega dopo l'ultima lettura. Gli 'other' non vengono più toccati."""
    seen = registry.set_index("pdf_name")
    todo = []
    for r in reports:
        if r["pdf_name"] not in seen.index:
            todo.append({**r, "reason": "new"})
        elif seen.at[r["pdf_name"], "status"] == "serie_a" and r["updated"] > seen.at[r["pdf_name"], "updated"]:
            todo.append({**r, "reason": "corrected"})
    return todo


def report(lines: list[str]) -> None:
    """Stampa il riepilogo e, dentro GitHub Actions, lo mostra nella pagina del run."""
    text = "\n".join(lines)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="show what would be updated, without downloading")
    parser.add_argument("--rebuild", action="store_true", help="re-read every Serie A report of the season")
    args = parser.parse_args()

    old_matches, old_players = load_dataset() if dataset_available() else (pd.DataFrame(), pd.DataFrame())
    registry = load_registry()
    if args.rebuild:
        registry = registry[registry["status"] == "other"]

    reports = list_match_reports(SEASON_START)
    todo = pending_reports(reports, registry)
    in_dataset = set(old_matches.get("pdf_name", []))
    for r in todo:  # già nel dataset ma senza data di lettura registrata (primo run o --rebuild)
        if r["reason"] == "new" and r["pdf_name"] in in_dataset:
            r["reason"] = "refresh"
    if not todo:
        report(["## Dataset update", f"Nothing to do: {len(reports)} Match Reports published since "
                f"{SEASON_START}, none new or corrected."])
        return 0
    if args.dry_run:
        report([f"{len(todo)} reports to download:"] + [f"- {r['reason']:9}  {r['published'][:10]}  {r['pdf_name']}" for r in todo])
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        serie_a: list[dict] = []
        entries: list[dict] = []
        errors: list[str] = []
        for r in todo:
            path = staging / r["pdf_name"]
            path.write_bytes(http_get(r["url"]))
            header = competition_line(path)
            kind = classify(header)
            if kind == "serie_a":
                serie_a.append({**r, "path": path, "header": header})
            elif kind == "other":
                entries.append({"pdf_name": r["pdf_name"], "status": "other", "match_id": "",
                                "published": r["published"], "updated": r["updated"], "header": header})
            else:
                errors.append(f"{r['pdf_name']}: '{header}' is not season {SEASON}. "
                              "Update SEASON and SEASON_START in update_dataset.py.")

        match_records, player_records = [], []
        for r in serie_a:
            try:
                match_records.append(parse_full_report(r["path"]))
                player_records.extend(parse_player_stats(r["path"]))
            except Exception as exc:  # un PDF illeggibile blocca l'aggiornamento, non lo salta
                errors.append(f"{r['pdf_name']}: {exc}")

        new_matches = pd.DataFrame(match_records)
        new_players = pd.DataFrame(player_records)

        # partite da sostituire: stesso file già presente nel dataset (report corretto o rebuild)
        refreshed_names = {r["pdf_name"] for r in serie_a}
        if args.rebuild:
            replaced = set(old_matches.get("match_id", []))
        else:
            replaced = set(old_matches.loc[old_matches["pdf_name"].isin(refreshed_names), "match_id"]) if not old_matches.empty else set()
        kept_matches = old_matches[~old_matches["match_id"].isin(replaced)] if not old_matches.empty else old_matches
        kept_players = old_players[~old_players["match_id"].isin(replaced)] if not old_players.empty else old_players

        problems = errors + (validate(new_matches, new_players, kept_matches) if match_records else [])
        if problems:
            report(["## Dataset update FAILED", "Nothing was written. Problems:"] + [f"- {p}" for p in problems])
            return 1

        for r in serie_a:
            m = new_matches.loc[new_matches["pdf_name"] == r["pdf_name"]].iloc[0]
            entries.append({"pdf_name": r["pdf_name"], "status": "serie_a", "match_id": m["match_id"],
                            "published": r["published"], "updated": r["updated"], "header": r["header"]})
            dest = local_destination(r["pdf_name"], int(m["giornata"]))
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(r["path"], dest)

    if match_records:
        new_players = new_players.drop(columns=["unassigned_values"], errors="ignore")
        if not kept_players.empty:
            new_players = new_players.reindex(columns=kept_players.columns)  # stesso ordine di colonne del CSV
        matches = pd.concat([kept_matches, new_matches], ignore_index=True).sort_values(["giornata", "match_id"], kind="stable")
        players = pd.concat([kept_players, new_players], ignore_index=True).sort_values(["giornata", "match_id"], kind="stable")
        export_dataset(matches, players)

    entries_df = pd.DataFrame(entries, columns=REPORT_COLUMNS)
    registry = pd.concat([registry[~registry["pdf_name"].isin(entries_df["pdf_name"])], entries_df], ignore_index=True)
    registry.sort_values(["status", "published", "pdf_name"]).to_csv(REPORTS_CSV, index=False)

    n_new = sum(r["reason"] == "new" for r in serie_a)
    n_corrected = sum(r["reason"] == "corrected" for r in serie_a)
    n_refreshed = sum(r["reason"] == "refresh" for r in serie_a)
    lines = ["## Dataset update", f"- New matches: **{n_new}**",
             f"- Matches re-read from a corrected report: **{n_corrected}**"]
    if n_refreshed:
        lines.append(f"- Matches re-read to record their publication date: **{n_refreshed}**")
    if match_records:
        for g, n in sorted(new_matches.groupby("giornata").size().items()):
            lines.append(f"  - matchday {int(g)}: {n}")
    skipped = sum(e["status"] == "other" for e in entries)
    if skipped:
        lines.append(f"- Reports of other competitions skipped: {skipped}")
    warnings = review_warnings(new_matches) if match_records else []
    if warnings:
        lines += ["", "Warnings (not blocking):"] + [f"- {w}" for w in warnings]
    if match_records:
        lines.append(f"\nDataset now: {len(matches)} matches, matchdays {int(matches['giornata'].min())}–"
                     f"{int(matches['giornata'].max())}, {len(players)} player rows.")
    report(lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())

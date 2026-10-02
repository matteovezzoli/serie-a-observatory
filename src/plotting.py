"""Grafici interattivi per la dashboard Streamlit (Plotly): zoom, pan e
hover-tooltip nativi, resi con st.plotly_chart().

Tutti i grafici condividono il template "observatory" registrato qui sotto
(tipografia, griglie leggere, tooltip) e la stessa palette:
- serie singola -> un solo colore (la lunghezza della barra porta il valore);
- "squadra in evidenza" -> quella squadra a colori, tutte le altre in grigio;
- confronti tra 2-3 entità -> i primi tre colori categoriali, in ordine fisso
  (validati anche per daltonismo);
- intensità (heatmap, posizione in classifica) -> rampa di un solo blu.

Il titolo del grafico sta nella scheda che lo contiene (src/ui.py), non
dentro la figura: così titolo, spiegazione e "come leggere" hanno la stessa
tipografia in tutta la dashboard.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from src.glossary import CORE_METRIC_LABELS
from src.metrics import LOWER_IS_BETTER, MetricPanel

FONT = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"
INK = "#1a1d23"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#eceae4"
AXIS = "#c3c2b7"
DIM = "#d3d7de"          # barre/punti non in evidenza
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SERIES_1, SERIES_2, SERIES_3 = SERIES[:3]
BLUE_RAMP = [[0.0, "#eef4fc"], [0.25, "#cde2fb"], [0.5, "#86b6ef"], [0.75, "#3987e5"], [1.0, "#1c5cab"]]
RANK_RAMP = [[0.0, "#b7d3f6"], [0.5, "#3987e5"], [1.0, "#104281"]]

pio.templates["observatory"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, size=12, color=INK_2),
    paper_bgcolor="#ffffff",
    plot_bgcolor="#ffffff",
    colorway=SERIES,
    margin=dict(l=8, r=24, t=16, b=8),
    xaxis=dict(gridcolor=GRID, zeroline=False, linecolor=AXIS, ticks="", tickfont=dict(color=MUTED), automargin=True,
               title=dict(font=dict(color=INK_2, size=12), standoff=8)),
    yaxis=dict(gridcolor=GRID, zeroline=False, linecolor=AXIS, ticks="", tickfont=dict(color=INK_2), automargin=True,
               title=dict(font=dict(color=INK_2, size=12), standoff=8)),
    hoverlabel=dict(bgcolor="white", bordercolor=AXIS, font=dict(family=FONT, color=INK, size=12)),
    legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, xanchor="left", font=dict(color=INK_2), title=None,
                bgcolor="rgba(0,0,0,0)"),
    bargap=0.28,
))
TEMPLATE = "observatory"


def _empty(message: str, height: int = 240) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(color=MUTED, size=13))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(template=TEMPLATE, height=height)
    return fig


def _fmt(value: float, decimals: int, pct: bool) -> str:
    return f"{value:.{decimals}f}{'%' if pct else ''}"


def _bar_colors(keys: pd.Series, highlight: str | None) -> list[str]:
    if not highlight:
        return [SERIES_1] * len(keys)
    return [SERIES_1 if k == highlight else DIM for k in keys]


def _short(team: str) -> str:
    return team.title()


# --------------------------------------------------------------------------- #
# Squadre
# --------------------------------------------------------------------------- #

def team_ranking_fig(team_summary_df: pd.DataFrame, panel: MetricPanel, highlight: str | None = None) -> go.Figure:
    """Classifica di tutte le squadre su una metrica, con la media del
    campionato come riferimento. Per le metriche "meno è meglio" la squadra
    migliore resta comunque in cima."""
    lower_better = panel.avg_col in LOWER_IS_BETTER
    # l'ordine delle categorie va dal basso verso l'alto: la migliore è l'ultima
    df = team_summary_df.sort_values(panel.avg_col, ascending=not lower_better)
    league_avg = team_summary_df[panel.avg_col].mean()
    fig = go.Figure(go.Bar(
        x=df[panel.avg_col], y=df["team"].map(_short), orientation="h",
        marker=dict(color=_bar_colors(df["team"], highlight), cornerradius=4),
        text=[_fmt(v, 1, panel.pct) for v in df[panel.avg_col]], textposition="outside",
        textfont=dict(color=INK_2, size=11), cliponaxis=False,
        customdata=df[["rank"]],
        hovertemplate=f"<b>%{{y}}</b> (#%{{customdata[0]}} in the table)<br>{panel.x_title}: %{{x:.2f}}"
                      f"{'%' if panel.pct else ''}<extra></extra>",
    ))
    fig.add_vline(x=league_avg, line=dict(color=MUTED, width=1, dash="dot"),
                  annotation=dict(text=f"league avg {_fmt(league_avg, 1, panel.pct)}", font=dict(color=MUTED, size=11),
                                  yanchor="bottom", y=1.0))
    fig.update_layout(
        template=TEMPLATE, height=560,
        xaxis=dict(title=panel.x_title + (" · lower is better" if lower_better else ""), range=[0, df[panel.avg_col].max() * 1.15]),
        yaxis=dict(categoryorder="array", categoryarray=df["team"].map(_short), gridcolor="rgba(0,0,0,0)"),
    )
    return fig


def team_scatter_fig(
    team_summary_df: pd.DataFrame, x: str, y: str, x_title: str, y_title: str,
    highlight: str | None = None, quadrants: dict[str, str] | None = None, size_col: str = "points",
    x_pct: bool = False, y_pct: bool = False,
) -> go.Figure:
    """Dispersione delle squadre su due metriche, con le mediane del
    campionato come assi dei quadranti. Dimensione = punti in classifica
    (min-max sulla vista). quadrants: etichette per 'tr', 'tl', 'br', 'bl'."""
    df = team_summary_df.copy()
    size = df[size_col]
    df["_size"] = 14 + (size - size.min()) / max(size.max() - size.min(), 1) * 22
    colors = _bar_colors(df["team"], highlight) if highlight else [SERIES_1] * len(df)
    sx, sy = ("%" if x_pct else ""), ("%" if y_pct else "")
    fig = go.Figure(go.Scatter(
        x=df[x], y=df[y], mode="markers+text", text=df["team"].map(_short),
        textposition="top center", textfont=dict(size=10, color=INK_2),
        marker=dict(size=df["_size"], color=colors, opacity=0.9, line=dict(width=1.5, color="white")),
        customdata=df[["rank", "points"]],
        hovertemplate=(f"<b>%{{text}}</b> · #%{{customdata[0]}} (%{{customdata[1]}} pts)<br>"
                       f"{x_title}: %{{x:.1f}}{sx}<br>{y_title}: %{{y:.1f}}{sy}<extra></extra>"),
    ))
    mx, my = df[x].median(), df[y].median()
    fig.add_vline(x=mx, line=dict(color=AXIS, width=1, dash="dot"))
    fig.add_hline(y=my, line=dict(color=AXIS, width=1, dash="dot"))
    if quadrants:
        pos = {"tr": (1, 1, "right", "top"), "tl": (0, 1, "left", "top"),
               "br": (1, 0, "right", "bottom"), "bl": (0, 0, "left", "bottom")}
        for key, text in quadrants.items():
            px, py, xa, ya = pos[key]
            fig.add_annotation(text=text, xref="paper", yref="paper", x=px, y=py, xanchor=xa, yanchor=ya,
                               showarrow=False, font=dict(size=11, color=MUTED))
    fig.update_layout(template=TEMPLATE, height=520, xaxis_title=x_title, yaxis_title=y_title)
    return fig


def percentile_heatmap_fig(pct_df: pd.DataFrame, raw_df: pd.DataFrame, cols: list[str], labels: dict[str, str]) -> go.Figure:
    """Mappa del campionato: squadre (righe, in ordine di classifica) x
    metriche (colonne), colore = percentile 0-100 sulla metrica, testo =
    valore reale. Un'occhiata sola per vedere punti di forza e debolezza."""
    order = raw_df.sort_values("rank")["team"]
    pct = pct_df.set_index("team").loc[order, cols]
    raw = raw_df.set_index("team").loc[order, cols]
    text = [[f"{v:.1f}" for v in row] for row in raw.to_numpy()]
    fig = go.Figure(go.Heatmap(
        z=pct.to_numpy(), x=[labels[c] for c in cols], y=[_short(t) for t in order],
        text=text, texttemplate="%{text}", textfont=dict(size=10, color=INK),
        colorscale=BLUE_RAMP, zmin=0, zmax=100, xgap=2, ygap=2,
        colorbar=dict(title=dict(text="Percentile", font=dict(size=11)), thickness=10, len=0.6, tickfont=dict(size=10)),
        hovertemplate="<b>%{y}</b><br>%{x}: %{text}<br>Percentile: %{z:.0f}<extra></extra>",
    ))
    fig.update_layout(
        template=TEMPLATE, height=90 + 26 * len(order),
        xaxis=dict(side="top", tickangle=-35, gridcolor="rgba(0,0,0,0)", tickfont=dict(color=INK_2, size=11)),
        yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"),
    )
    return fig


def standings_bump_fig(progression: pd.DataFrame, highlight: list[str]) -> go.Figure:
    """Posizione in classifica giornata per giornata. Tutte le squadre in
    grigio per contesto; quelle scelte a colori, con etichetta a fine linea."""
    if progression.empty or progression["giornata"].nunique() < 2:
        return _empty("At least two matchdays are needed to show the standings trend.")
    fig = go.Figure()
    last = progression["giornata"].max()
    for team, g in progression.groupby("team"):
        if team in highlight:
            continue
        fig.add_trace(go.Scatter(
            x=g["giornata"], y=g["position"], mode="lines", line=dict(color=DIM, width=1.2),
            name=_short(team), showlegend=False,
            hovertemplate=f"<b>{_short(team)}</b><br>MD%{{x}}: #%{{y}}<extra></extra>",
        ))
    for i, team in enumerate(highlight[:3]):
        g = progression[progression["team"] == team]
        color = SERIES[i]
        fig.add_trace(go.Scatter(
            x=g["giornata"], y=g["position"], mode="lines+markers", name=_short(team),
            line=dict(color=color, width=2.5), marker=dict(size=9, line=dict(width=2, color="white")),
            customdata=g[["points"]],
            hovertemplate=f"<b>{_short(team)}</b><br>MD%{{x}}: #%{{y}} · %{{customdata[0]}} pts<extra></extra>",
        ))
        end = g[g["giornata"] == last]
        if not end.empty:
            fig.add_annotation(x=last, y=end["position"].iloc[0], text=f" {_short(team)}", xanchor="left",
                               showarrow=False, font=dict(color=INK, size=11))
    n = progression["team"].nunique()
    fig.update_layout(
        template=TEMPLATE, height=460, showlegend=False, margin=dict(l=8, r=110, t=16, b=8),
        xaxis=dict(title="Matchday", dtick=1),
        yaxis=dict(title="Position", autorange="reversed", dtick=1, range=[n + 0.5, 0.5]),
    )
    return fig


def team_trend_fig(team_match_df: pd.DataFrame, team: str, column: str, label: str, pct: bool = False) -> go.Figure:
    """Andamento partita per partita di una metrica per la squadra scelta,
    contro la media del campionato nella stessa giornata."""
    league = team_match_df.groupby("giornata", as_index=False)[column].mean()
    own = team_match_df[team_match_df["team"] == team].sort_values("giornata")
    suffix = "%" if pct else ""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=league["giornata"], y=league[column], name="League average", mode="lines",
        line=dict(color=MUTED, width=2, dash="dot"),
        hovertemplate=f"MD%{{x}} · league average: %{{y:.1f}}{suffix}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=own["giornata"], y=own[column], name=_short(team), mode="lines+markers",
        line=dict(color=SERIES_1, width=2.5), marker=dict(size=10, line=dict(width=2, color="white")),
        customdata=own[["opponent", "goals_for", "goals_against"]],
        hovertemplate=(f"MD%{{x}} vs %{{customdata[0]}} (%{{customdata[1]}}-%{{customdata[2]}})<br>"
                       f"{label}: %{{y:.1f}}{suffix}<extra></extra>"),
    ))
    fig.update_layout(template=TEMPLATE, height=340, xaxis=dict(title="Matchday", dtick=1), yaxis_title=label)
    return fig


def dumbbell_fig(
    df: pd.DataFrame, label_col: str, a_col: str, b_col: str, a_name: str, b_name: str,
    x_title: str, highlight: str | None = None, decimals: int = 2,
) -> go.Figure:
    """Due valori sulla stessa scala per ogni riga (es. punti a partita in
    casa vs in trasferta), uniti da un segmento: la lunghezza del segmento è
    il divario."""
    df = df.dropna(subset=[a_col, b_col]).copy()
    df["_gap"] = df[a_col] - df[b_col]
    df = df.sort_values("_gap")
    labels = df[label_col].map(_short)
    fig = go.Figure()
    for (_, row), lab in zip(df.iterrows(), labels):
        emph = not highlight or row[label_col] == highlight
        fig.add_trace(go.Scatter(
            x=[row[a_col], row[b_col]], y=[lab, lab], mode="lines",
            line=dict(color=AXIS if emph else GRID, width=3), showlegend=False, hoverinfo="skip",
        ))
    for col, name, color in ((a_col, a_name, SERIES_1), (b_col, b_name, SERIES_2)):
        colors = [color if (not highlight or t == highlight) else DIM for t in df[label_col]]
        fig.add_trace(go.Scatter(
            x=df[col], y=labels, mode="markers", name=name,
            marker=dict(size=11, color=colors, line=dict(width=1.5, color="white")),
            hovertemplate=f"<b>%{{y}}</b><br>{name}: %{{x:.{decimals}f}}<extra></extra>",
        ))
    fig.update_layout(
        template=TEMPLATE, height=90 + 24 * len(df), xaxis_title=x_title,
        yaxis=dict(categoryorder="array", categoryarray=labels, gridcolor=GRID),
    )
    return fig


def match_comparison_fig(match_row: pd.Series, metrics: list[str]) -> go.Figure:
    """Confronto casa/ospite su una partita: ogni metrica come barra al 100%
    (quota della casa vs quota dell'ospite) — le metriche hanno scale troppo
    diverse (400 passaggi vs 10 tiri) per un grafico a barre su un solo asse.
    Il valore grezzo resta scritto dentro ogni segmento."""
    home, away = match_row["home"], match_row["away"]
    rows = []
    for metric in metrics:
        h, a = match_row.get(f"{metric}_home"), match_row.get(f"{metric}_away")
        h = 0.0 if pd.isna(h) else float(h)
        a = 0.0 if pd.isna(a) else float(a)
        total = h + a
        rows.append((metric, h, a, h / total * 100 if total else 50.0))
    df = pd.DataFrame(rows, columns=["metric", "home", "away", "home_pct"])[::-1]
    df["label"] = df["metric"].map(CORE_METRIC_LABELS).fillna(df["metric"])

    def _v(v: float, metric: str) -> str:
        return f"{v:.0f}%" if "%" in metric else f"{v:.0f}"

    fig = go.Figure([
        go.Bar(
            y=df["label"], x=df["home_pct"], orientation="h", name=_short(home), marker=dict(color=SERIES_1),
            text=[_v(v, m) for v, m in zip(df["home"], df["metric"])], textposition="inside",
            insidetextanchor="start", textfont=dict(color="white"),
            hovertemplate=f"<b>{_short(home)}</b> · %{{y}}: %{{text}}<extra></extra>",
        ),
        go.Bar(
            y=df["label"], x=100 - df["home_pct"], orientation="h", name=_short(away), marker=dict(color=SERIES_2),
            text=[_v(v, m) for v, m in zip(df["away"], df["metric"])], textposition="inside",
            insidetextanchor="end", textfont=dict(color="white"),
            hovertemplate=f"<b>{_short(away)}</b> · %{{y}}: %{{text}}<extra></extra>",
        ),
    ])
    fig.update_layout(
        barmode="stack", bargap=0.35, template=TEMPLATE, height=60 + 32 * len(df),
        xaxis=dict(range=[0, 100], showticklabels=False, showgrid=False),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        legend=dict(traceorder="normal"),
        shapes=[dict(type="line", x0=50, x1=50, y0=-0.5, y1=len(df) - 0.5, line=dict(color="white", width=2))],
    )
    return fig


# --------------------------------------------------------------------------- #
# Giocatori
# --------------------------------------------------------------------------- #

def _player_label(df: pd.DataFrame) -> pd.Series:
    return df["player"] + " · " + df["team"].map(_short)


def player_ranking_fig(
    df: pd.DataFrame, value_col: str, x_title: str, n: int = 10, pct: bool = False,
    decimals: int = 2, lowest: bool = False, highlight_team: str | None = None,
) -> go.Figure:
    """Classifica top-n orizzontale per giocatore. lowest=True per le
    metriche dove meno è meglio (es. gol subiti per 90')."""
    pool = df.dropna(subset=[value_col])
    picked = pool.nsmallest(n, value_col) if lowest else pool.nlargest(n, value_col)
    if picked.empty:
        return _empty("No eligible players with the current thresholds")
    plot_df = picked.iloc[::-1]
    labels = _player_label(plot_df)
    colors = [SERIES_1 if (not highlight_team or t == highlight_team) else DIM for t in plot_df["team"]]
    fig = go.Figure(go.Bar(
        x=plot_df[value_col], y=labels, orientation="h", marker=dict(color=colors, cornerradius=4),
        text=[_fmt(v, decimals, pct) for v in plot_df[value_col]], textposition="outside",
        textfont=dict(color=INK_2, size=11), cliponaxis=False,
        customdata=plot_df[["minutes", "matches"]],
        hovertemplate=(f"<b>%{{y}}</b><br>{x_title}: %{{x:.{decimals}f}}{'%' if pct else ''}<br>"
                       "Minutes: %{customdata[0]:.0f} · Apps: %{customdata[1]}<extra></extra>"),
    ))
    fig.update_layout(
        template=TEMPLATE, height=70 + 30 * len(plot_df),
        xaxis=dict(title=x_title, range=[0, plot_df[value_col].max() * 1.2]),
        yaxis=dict(categoryorder="array", categoryarray=labels, gridcolor="rgba(0,0,0,0)"),
    )
    return fig


def player_scatter_fig(
    df: pd.DataFrame, x: str, y: str, x_title: str, y_title: str,
    highlight_team: str | None = None, label_n: int = 8, height: int = 560,
) -> go.Figure:
    """Dispersione giocatori. Dimensione = minuti giocati, colore = posizione
    in classifica della squadra (più scuro = squadra più in basso). Linee
    tratteggiate = mediane del pool (quadranti). Etichette dirette solo sui
    label_n profili più estremi, il resto via hover."""
    plot_df = df.dropna(subset=[x, y]).copy()
    if plot_df.empty:
        return _empty("No eligible players with the current filters", height)

    plot_df["_extreme"] = plot_df[x].rank(pct=True) + plot_df[y].rank(pct=True)
    if highlight_team:
        chosen = plot_df[plot_df["team"] == highlight_team].nlargest(label_n, "_extreme").index
    else:
        chosen = plot_df.nlargest(label_n, "_extreme").index
    ordered = plot_df.loc[chosen].sort_values(x).index
    positions = {idx: ("top center" if k % 2 == 0 else "bottom center") for k, idx in enumerate(ordered)}
    minutes = plot_df["minutes"]
    sizes = 8 + (minutes - minutes.min()) / max(minutes.max() - minutes.min(), 1) * 18

    marker = dict(size=sizes, line=dict(width=1.5, color="white"), opacity=0.9)
    if highlight_team:
        marker["color"] = [SERIES_1 if t == highlight_team else DIM for t in plot_df["team"]]
    else:
        marker.update(color=plot_df["team_rank"], colorscale=RANK_RAMP, cmin=1, cmax=20,
                      colorbar=dict(title=dict(text="Team pos.", font=dict(size=11)), thickness=10, len=0.6,
                                    tickfont=dict(size=10)))

    fig = go.Figure(go.Scatter(
        x=plot_df[x], y=plot_df[y], mode="markers+text",
        text=[f"{p} ({t[:3]})" if i in positions else "" for i, p, t in zip(plot_df.index, plot_df["player"], plot_df["team"])],
        textposition=[positions.get(i, "top center") for i in plot_df.index], textfont=dict(size=10, color=INK),
        marker=marker,
        customdata=plot_df[["player", "team", "team_rank", "minutes"]],
        hovertemplate=("<b>%{customdata[0]}</b> · %{customdata[1]} (#%{customdata[2]:.0f})<br>"
                       f"{x_title}: %{{x:.2f}}<br>{y_title}: %{{y:.2f}}<br>"
                       "Minutes: %{customdata[3]:.0f}<extra></extra>"),
    ))
    fig.add_vline(x=plot_df[x].median(), line=dict(color=AXIS, width=1, dash="dot"))
    fig.add_hline(y=plot_df[y].median(), line=dict(color=AXIS, width=1, dash="dot"))
    fig.add_annotation(text="above median on both ↗", xref="paper", yref="paper", x=1, y=1,
                       xanchor="right", yanchor="top", showarrow=False, font=dict(size=11, color=MUTED))
    fig.update_layout(template=TEMPLATE, height=height, xaxis_title=x_title, yaxis_title=y_title)
    return fig


def percentile_bars_fig(
    profile_df: pd.DataFrame, labels: dict[str, str], x_title: str = "Percentile among eligible players",
) -> go.Figure:
    """Profilo percentile di un giocatore (0-100) rispetto ai giocatori
    idonei: una sola scala per metriche eterogenee, 50 = mediana."""
    if profile_df.empty:
        return _empty("Profile not available")
    df = profile_df.iloc[::-1]
    names = [labels.get(m, m) for m in df["metric"]]
    fig = go.Figure(go.Bar(
        x=df["percentile"], y=names, orientation="h", marker=dict(color=SERIES_1, cornerradius=4),
        text=[f"{p:.0f}" for p in df["percentile"]], textposition="outside", cliponaxis=False,
        textfont=dict(color=INK_2, size=11),
        customdata=df[["value"]],
        hovertemplate="<b>%{y}</b><br>Percentile: %{x:.0f}<br>Value: %{customdata[0]:.2f}<extra></extra>",
    ))
    fig.add_vline(x=50, line=dict(color=MUTED, width=1, dash="dot"),
                  annotation=dict(text="median", font=dict(color=MUTED, size=11), yanchor="bottom", y=1.0))
    fig.update_layout(
        template=TEMPLATE, height=70 + 30 * len(df),
        xaxis=dict(range=[0, 108], title=x_title, dtick=25),
        yaxis=dict(categoryorder="array", categoryarray=names, gridcolor="rgba(0,0,0,0)"),
    )
    return fig


def comparison_dots_fig(long_df: pd.DataFrame, labels: dict[str, str], metric_order: list[str]) -> go.Figure:
    """Confronto tra 2-3 entità (giocatori o squadre) sui percentili: una riga
    per metrica, un punto colorato per entità, un segmento grigio che mostra
    la distanza tra il migliore e il peggiore."""
    if long_df.empty:
        return _empty("Select at least one eligible item")
    metrics = [m for m in metric_order if m in set(long_df["metric"])][::-1]
    names = [labels.get(m, m) for m in metrics]
    fig = go.Figure()
    for m, name in zip(metrics, names):
        vals = long_df.loc[long_df["metric"] == m, "percentile"]
        fig.add_trace(go.Scatter(x=[vals.min(), vals.max()], y=[name, name], mode="lines",
                                 line=dict(color=GRID, width=6), showlegend=False, hoverinfo="skip"))
    for i, (entity, g) in enumerate(long_df.groupby("entity", sort=False)):
        g = g.set_index("metric").reindex(metrics).dropna(subset=["percentile"])
        fig.add_trace(go.Scatter(
            x=g["percentile"], y=[labels.get(m, m) for m in g.index], mode="markers", name=entity,
            marker=dict(size=14, color=SERIES[i % 3], line=dict(width=2, color="white")),
            customdata=g[["value"]],
            hovertemplate=f"<b>{entity}</b><br>%{{y}}: %{{customdata[0]:.2f}}<br>Percentile: %{{x:.0f}}<extra></extra>",
        ))
    fig.add_vline(x=50, line=dict(color=MUTED, width=1, dash="dot"))
    fig.update_layout(
        template=TEMPLATE, height=90 + 34 * len(metrics),
        xaxis=dict(range=[-3, 103], title="Percentile (50 = median)", dtick=25),
        yaxis=dict(categoryorder="array", categoryarray=names),
    )
    return fig


def player_match_bars_fig(series: pd.DataFrame, column: str, label: str) -> go.Figure:
    """Valore di una metrica partita per partita (barre: sono conteggi per
    singola gara), con avversario e minuti nel tooltip."""
    df = series.copy()
    if df.empty:
        return _empty("No matches")
    df["_v"] = df[column].fillna(0)
    df["_opp"] = df["match_id"].str.replace(r"^G\d+_", "", regex=True).str.replace("_", " - ").str.title()
    fig = go.Figure(go.Bar(
        x=df["giornata"], y=df["_v"], marker=dict(color=SERIES_1, cornerradius=4),
        text=[f"{v:.0f}" if v else "" for v in df["_v"]], textposition="outside", textfont=dict(color=INK_2),
        customdata=df[["_opp", "MIN"]], cliponaxis=False,
        hovertemplate=f"MD%{{x}} · %{{customdata[0]}}<br>{label}: %{{y:.0f}}<br>Minutes: %{{customdata[1]}}<extra></extra>",
    ))
    fig.update_layout(template=TEMPLATE, height=300, xaxis=dict(title="Matchday", dtick=1),
                      yaxis=dict(title=label, rangemode="tozero"))
    return fig

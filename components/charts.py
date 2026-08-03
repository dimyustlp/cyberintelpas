from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

COLORS = {
    "blue": "#1769AA",
    "navy": "#113A66",
    "gold": "#D4A72C",
    "green": "#16845B",
    "amber": "#CF7F0A",
    "red": "#C53A43",
    "gray": "#98A2B3",
}


def _layout(fig: go.Figure, height: int = 330) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=12, t=15, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, Arial", size=12),
        hoverlabel=dict(bgcolor="#06182C", font_color="white"),
    )
    return fig


def trend_chart(trend: pd.DataFrame) -> go.Figure:
    fig = px.area(trend, x="Tanggal", y="Jumlah", markers=True)
    fig.update_traces(
        line=dict(color=COLORS["blue"], width=3),
        fillcolor="rgba(23,105,170,.13)",
        hovertemplate="%{x|%d %b %Y}<br><b>%{y} berita</b><extra></extra>",
    )
    fig.update_layout(xaxis_title=None, yaxis_title=None, hovermode="x unified")
    return _layout(fig, 335)


def sentiment_donut(sentiment: pd.DataFrame, total: int) -> go.Figure:
    fig = px.pie(
        sentiment,
        names="Sentimen",
        values="Jumlah",
        hole=.66,
        color="Sentimen",
        color_discrete_map={
            "Positif": COLORS["green"],
            "Netral": COLORS["gold"],
            "Negatif": COLORS["red"],
            "Campuran": "#7C3AED",
            "Tidak diketahui": COLORS["gray"],
        },
    )
    fig.update_traces(
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>%{value} berita (%{percent})<extra></extra>",
    )
    fig.update_layout(
        showlegend=False,
        annotations=[dict(text=f"<b>{total}</b><br>Total", x=.5, y=.5, showarrow=False)],
    )
    return _layout(fig, 335)


def horizontal_bar(df: pd.DataFrame, category: str, value: str, color: str = "blue") -> go.Figure:
    plot = df.sort_values(value)
    fig = px.bar(plot, x=value, y=category, orientation="h", text=value)
    fig.update_traces(
        marker_color=COLORS.get(color, color),
        textposition="outside",
        hovertemplate=f"<b>%{{y}}</b><br>%{{x}} berita<extra></extra>",
    )
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    return _layout(fig, 330)


def vertical_bar(df: pd.DataFrame, category: str, value: str, color: str = "gold") -> go.Figure:
    fig = px.bar(df, x=category, y=value, text=value)
    fig.update_traces(
        marker_color=COLORS.get(color, color),
        textposition="outside",
        hovertemplate=f"<b>%{{x}}</b><br>%{{y}} berita<extra></extra>",
    )
    fig.update_layout(xaxis_title=None, yaxis_title=None, xaxis_tickangle=-25)
    return _layout(fig, 330)

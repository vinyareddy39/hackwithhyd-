"""Interactive Streamlit dashboard for the Hindsight Sales Agent (Person 5)."""

import os
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

from config import ANGLES, LOG_COLUMNS
from dashboard_utils import (
    angle_distribution_by_batch,
    angle_success_by_persona,
    get_comparison,
    load_log,
    response_rate_by_batch,
)
import make_dummy_log

# Configure Streamlit page for judges
st.set_page_config(
    page_title="Hindsight Sales Agent Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for prominent judge-friendly typography
st.markdown(
    """
    <style>
    .judge-title {
        font-size: 2.3rem;
        font-weight: 800;
        color: #0F172A;
        margin-bottom: 0.2rem;
    }
    .judge-subtitle {
        font-size: 1.15rem;
        color: #475569;
        margin-bottom: 1.8rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_file_mtime(filepath: str) -> float:
    """Return file modification timestamp or 0.0 if missing."""
    p = Path(filepath)
    return p.stat().st_mtime if p.is_file() else 0.0


@st.cache_data
def get_cached_log(filepath: str, mtime: float) -> pd.DataFrame:
    """Load log cached by file path and modification timestamp."""
    return load_log(filepath)


# Sidebar controls
st.sidebar.header("Agent Memory Settings")
log_path = st.sidebar.text_input("Memory Log Path", value="memory_log.json")
use_dummy_fallback = st.sidebar.toggle("Use dummy data if file is missing", value=True)

if st.sidebar.button("Reload data"):
    st.cache_data.clear()
    st.rerun()

# Data loading with graceful fallback
target_path = Path(log_path)
if not target_path.is_file():
    if use_dummy_fallback:
        # Generate or use dummy log
        if not Path("memory_log.json").is_file():
            make_dummy_log.generate("memory_log.json")
        log_path = "memory_log.json"
    else:
        st.info("Memory log file not found. Please provide a valid file path or enable dummy data fallback.")
        st.stop()

mtime = get_file_mtime(log_path)
df = get_cached_log(log_path, mtime)

if df.empty or len(df) == 0:
    st.info("No records found in the specified log file. Ensure the agent has logged batch runs.")
    st.stop()

# Header
st.markdown('<div class="judge-title">Hindsight Sales Agent</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="judge-subtitle">Cold-email agent that remembers winning personalization angles and adapts across batches.</div>',
    unsafe_allow_html=True,
)

# Batches and Rates
batches = sorted(df["batch_id"].dropna().unique())
if not batches:
    st.info("No valid batch IDs present in log records.")
    st.stop()

first_batch = batches[0]
last_batch = batches[-1]

response_rates = response_rate_by_batch(df)
rate_first = float(response_rates.get(first_batch, 0.0))
rate_last = float(response_rates.get(last_batch, 0.0))
improvement = rate_last - rate_first

# --- METRIC CARDS ---
st.subheader("Performance Overview")
m_col1, m_col2, m_col3 = st.columns(3)

with m_col1:
    m_col1.metric(
        label=f"Batch {first_batch} Response Rate",
        value=f"{rate_first:.1f}%",
    )

with m_col2:
    m_col2.metric(
        label=f"Batch {last_batch} Response Rate",
        value=f"{rate_last:.1f}%",
    )

with m_col3:
    m_col3.metric(
        label="Net Improvement",
        value=f"{improvement:+.1f} pts",
        delta=f"{improvement:+.1f} points",
    )

st.markdown("---")

# --- VIEW 1: Response Rate Trajectory ---
st.subheader("1. Response Rate Trajectory Across Batches")
rates_data = pd.DataFrame(
    {
        "Batch": [f"Batch {b}" for b in response_rates.index],
        "Response Rate (%)": response_rates.values,
        "Label": [f"{r:.1f}%" for r in response_rates.values],
    }
)

try:
    fig_line = px.line(
        rates_data,
        x="Batch",
        y="Response Rate (%)",
        text="Label",
        markers=True,
        title="Batch-over-Batch Positive Response Rate (Interested + Reply)",
    )
    fig_line.update_traces(
        textposition="top center",
        textfont_size=13,
        line=dict(color="#2563EB", width=3),
        marker=dict(size=10, color="#1D4ED8"),
    )
    fig_line.update_layout(
        yaxis=dict(range=[0, max(100, max(response_rates.values or [0]) + 15)]),
        margin=dict(l=40, r=40, t=50, b=40),
        height=380,
    )
    st.plotly_chart(fig_line, use_container_width=True)
except Exception:
    st.line_chart(rates_data.set_index("Batch")["Response Rate (%)"])

st.markdown("---")

# --- VIEW 2: Angle Adaptation & Persona Heatmap ---
st.subheader("2. Angle Adaptation & Persona Success Heatmap")
dist_df = angle_distribution_by_batch(df)

col_v2_left, col_v2_right = st.columns([1.1, 1.0])

with col_v2_left:
    st.markdown("#### Angle Distribution by Batch (%)")
    
    # Reshape for stacked bar chart
    dist_plot_df = dist_df.reset_index().melt(
        id_vars=["batch_id"],
        value_vars=[c for c in dist_df.columns if c in ANGLES],
        var_name="Personalization Angle",
        value_name="Percentage",
    )
    dist_plot_df["Batch"] = dist_plot_df["batch_id"].apply(lambda b: f"Batch {b}")

    fig_bar = px.bar(
        dist_plot_df,
        x="Batch",
        y="Percentage",
        color="Personalization Angle",
        barmode="stack",
        text=dist_plot_df["Percentage"].apply(lambda v: f"{v:.1f}%" if v > 5 else ""),
        color_discrete_map={
            "referenced_metric": "#3B82F6",
            "referenced_opinion": "#10B981",
            "generic": "#94A3B8",
        },
    )
    fig_bar.update_layout(height=360, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_bar, use_container_width=True)

    # Table beneath stacked bar
    st.markdown("**Angle Distribution Table (%)**")
    st.dataframe(dist_df, use_container_width=True)

    # Plain English dynamic green caption
    if last_batch in dist_df.index and first_batch in dist_df.index:
        last_row = dist_df.loc[last_batch]
        first_row = dist_df.loc[first_batch]
        dominant_angle = last_row.idxmax()
        dom_pct_last = last_row[dominant_angle]
        dom_pct_first = first_row.get(dominant_angle, 0.0)
        st.success(
            f"By Batch {last_batch}, {dom_pct_last:.1f}% of emails used {dominant_angle}, "
            f"up from {dom_pct_first:.1f}% in Batch {first_batch}."
        )

with col_v2_right:
    st.markdown("#### Persona × Angle Success Rate (%)")
    st.markdown(
        "<span style='color: #64748B; font-size: 0.9rem;'>Percentage of positive outcomes for each persona and angle combination.</span>",
        unsafe_allow_html=True,
    )
    heatmap_df = angle_success_by_persona(df)
    
    # Plotly imshow for heatmap (avoiding matplotlib)
    fig_heatmap = px.imshow(
        heatmap_df,
        text_auto=".1f",
        aspect="auto",
        color_continuous_scale="Blues",
        labels=dict(x="Angle", y="Persona", color="Success %"),
    )
    fig_heatmap.update_layout(height=430, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig_heatmap, use_container_width=True)

st.markdown("---")

# --- VIEW 3: Prospect Batch Comparison ---
st.subheader("3. Individual Prospect Adaptation (Batch 1 vs Batch 3)")

prospect_ids = sorted(df["prospect_id"].dropna().unique())
selected_prospect = st.selectbox(
    "Select Prospect to Inspect Email Evolution:",
    options=prospect_ids,
)

if selected_prospect:
    comparison = get_comparison(df, selected_prospect, first_batch, last_batch)
    if comparison is None:
        st.info(f"Comparison data between Batch {first_batch} and Batch {last_batch} is not available for prospect {selected_prospect}.")
    else:
        cmp_col1, cmp_col2 = st.columns(2)
        
        with cmp_col1:
            st.markdown(f"### Batch {first_batch} (Initial Exploration)")
            st.markdown(f"**Angle Used:** `{comparison['batch_a']['angle_used']}`")
            outcome_a = comparison['batch_a']['outcome']
            badge_color_a = "green" if outcome_a in ["interested", "reply"] else "red"
            st.markdown(f"**Outcome:** :{badge_color_a}[{outcome_a}]")
            st.markdown("**Message Sent:**")
            st.text_area(
                f"Batch {first_batch} Message",
                value=comparison['batch_a']['message_sent'],
                height=160,
                disabled=True,
                key=f"msg_a_{selected_prospect}",
            )
            sim_a = comparison['batch_a']['simulated_response']
            if sim_a:
                st.markdown(f"**Prospect Response:**\n> *\"{sim_a}\"*")
            else:
                st.markdown("**Prospect Response:** *(No response received)*")

        with cmp_col2:
            st.markdown(f"### Batch {last_batch} (Adaptive Exploitation)")
            st.markdown(f"**Angle Used:** `{comparison['batch_b']['angle_used']}`")
            outcome_b = comparison['batch_b']['outcome']
            badge_color_b = "green" if outcome_b in ["interested", "reply"] else "red"
            st.markdown(f"**Outcome:** :{badge_color_b}[{outcome_b}]")
            st.markdown("**Message Sent:**")
            st.text_area(
                f"Batch {last_batch} Message",
                value=comparison['batch_b']['message_sent'],
                height=160,
                disabled=True,
                key=f"msg_b_{selected_prospect}",
            )
            sim_b = comparison['batch_b']['simulated_response']
            if sim_b:
                st.markdown(f"**Prospect Response:**\n> *\"{sim_b}\"*")
            else:
                st.markdown("**Prospect Response:** *(No response received)*")

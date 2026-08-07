"""
dashboard.py
=============
Streamlit dashboard for visualizing production giveaway / weight-drift
losses. Robust version with input validation and improved UI.

Run with:
    streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Production Loss Dashboard",
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>
.stApp {
    background-color: #F5F7FA;
}
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 1rem;
    padding-left: 2rem;
    padding-right: 2rem;
}
h1 {
    color: #1f2937;
    font-weight: 700;
    letter-spacing: 0.3px;
}
h2, h3 {
    color: #374151;
}
[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid #E5E7EB;
}
[data-testid="metric-container"] {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 18px;
    box-shadow: 0px 2px 8px rgba(0,0,0,0.05);
}
button[data-baseweb="tab"] {
    font-size: 16px;
    font-weight: 600;
}
hr {
    margin-top: 0.5rem;
    margin-bottom: 1rem;
}
.formula-box {
    background: #F0F9FF;
    border-left: 4px solid #3B82F6;
    padding: 12px 16px;
    border-radius: 0 8px 8px 0;
    margin-bottom: 1rem;
    font-size: 0.92rem;
    color: #1e3a5f;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONSTANTS
# ============================================================

REQUIRED_COLUMNS = [
    "Timestamp",
    "Date",
    "Product Name",
    "Shift",
    "Actual Weight",
    "Weight Drift",
    "Giveaway",
    "Total Loss",
]

# Change this if your CSV has a different name/location
DEFAULT_DATA_PATH = "CerealBoxWeight_dataset.csv"

# ============================================================
# LOAD & VALIDATE DATA
# ============================================================

@st.cache_data
def load_and_validate(path: str):
    """Load CSV and perform basic validation. Returns (df, error_message)."""
    path = Path(path)

    if not path.exists():
        return None, f"File not found: `{path}`. Please place the CSV in the same folder as dashboard.py or update the path."

    try:
        df = pd.read_csv(path)
    except Exception as e:
        return None, f"Could not read the CSV file. Error: {e}"

    if df.empty:
        return None, "The CSV file is empty."

    # Check required columns
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        return None, f"Missing required columns: {', '.join(missing)}"

    # Convert types
    try:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    except Exception as e:
        return None, f"Date/Timestamp conversion failed: {e}"

    # Drop rows where Timestamp could not be parsed
    df = df.dropna(subset=["Timestamp"])

    # Ensure numeric columns are numeric
    for col in ["Actual Weight", "Weight Drift", "Giveaway", "Total Loss"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows with critical numeric nulls
    df = df.dropna(subset=["Actual Weight", "Giveaway", "Total Loss"])

    if df.empty:
        return None, "No valid rows left after cleaning the data."

    return df, None


def verify_calculations(df: pd.DataFrame) -> dict:
    """
    Optional sanity check.
    If Target Weight and Cost per Kg exist, recompute and compare.
    """
    report = {"checked": False, "mismatches": 0, "message": ""}

    if "Target Weight" in df.columns and "Cost per Kg" in df.columns:
        report["checked"] = True
        expected_drift = df["Actual Weight"] - df["Target Weight"]
        expected_giveaway = expected_drift.clip(lower=0)
        expected_loss = (expected_giveaway / 1000) * df["Cost per Kg"]

        drift_mismatch = (abs(df["Weight Drift"] - expected_drift) > 0.05).sum()
        giveaway_mismatch = (abs(df["Giveaway"] - expected_giveaway) > 0.05).sum()
        loss_mismatch = (abs(df["Total Loss"] - expected_loss) > 0.05).sum()

        total_mismatch = int(drift_mismatch + giveaway_mismatch + loss_mismatch)
        report["mismatches"] = total_mismatch

        if total_mismatch == 0:
            report["message"] = "All calculations verified successfully."
        else:
            report["message"] = f"Found {total_mismatch} calculation mismatches (tolerance ±0.05)."
    else:
        report["message"] = "Target Weight / Cost per Kg not present — skipping recalculation check."

    return report


# ============================================================
# LOAD DATA
# ============================================================

df_raw, load_error = load_and_validate(DEFAULT_DATA_PATH)

if load_error:
    st.error("Data loading failed")
    st.warning(load_error)
    st.info("Expected columns: " + ", ".join(REQUIRED_COLUMNS))
    st.stop()

calc_report = verify_calculations(df_raw)

# ============================================================
# HEADER
# ============================================================

st.title("▣ Production Loss Dashboard")
st.caption("Production giveaway, weight drift and financial loss monitoring dashboard.")

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("◇ Filters")
st.sidebar.markdown("---")

product_options = sorted(df_raw["Product Name"].dropna().unique())
product = st.sidebar.multiselect(
    "Product",
    product_options,
    default=product_options,
)

min_date = df_raw["Date"].min()
max_date = df_raw["Date"].max()
date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

shift_options = sorted(df_raw["Shift"].dropna().unique())
shift = st.sidebar.multiselect(
    "Shift",
    shift_options,
    default=shift_options,
)

st.sidebar.markdown("---")
st.sidebar.caption("Data source")
st.sidebar.code(DEFAULT_DATA_PATH, language=None)

if calc_report["checked"]:
    if calc_report["mismatches"] == 0:
        st.sidebar.success("Calculations verified")
    else:
        st.sidebar.warning(calc_report["message"])

# ============================================================
# FILTER DATA
# ============================================================

df = df_raw.copy()

if product:
    df = df[df["Product Name"].isin(product)]
else:
    st.warning("Please select at least one Product.")
    st.stop()

if shift:
    df = df[df["Shift"].isin(shift)]
else:
    st.warning("Please select at least one Shift.")
    st.stop()

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range
    df = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)]
elif isinstance(date_range, (list, tuple)) and len(date_range) == 1:
    df = df[df["Date"] == date_range[0]]

if df.empty:
    st.warning("No records match the selected filters. Try adjusting Product, Shift or Date Range.")
    st.stop()

# ============================================================
# COMMON CHART SETTINGS
# ============================================================

CHART_TEMPLATE = "plotly_white"

# ============================================================
# TABS
# ============================================================

tab_overview, tab_trends, tab_data = st.tabs(
    ["□ Overview", "↗ Trends", "▤ Data"]
)

# ============================================================
# OVERVIEW
# ============================================================

with tab_overview:
    st.subheader("Summary")

    col1, col2, col3, col4 = st.columns(4)

    total_packets = len(df)
    avg_weight = df["Actual Weight"].mean()
    total_giveaway = df["Giveaway"].sum()
    total_loss = df["Total Loss"].sum()

    col1.metric("■ Total Production", f"{total_packets:,} Packets")
    col2.metric("⚖ Average Weight", f"{avg_weight:,.2f} g")
    col3.metric("◆ Total Giveaway", f"{total_giveaway:,.2f} g")
    col4.metric("₹ Total Financial Loss", f"₹ {total_loss:,.2f}")

    st.markdown("---")

    # Formula reference
    st.markdown(
        """
        <div class="formula-box">
        <strong>Formulas used</strong><br>
        Weight Drift = Actual Weight − Target Weight<br>
        Giveaway = max(0, Weight Drift)<br>
        Total Loss (₹) = (Giveaway ÷ 1000) × Cost per Kg
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Product-wise Giveaway")

    product_giveaway = (
        df.groupby("Product Name", as_index=False)["Giveaway"]
        .sum()
        .sort_values("Giveaway", ascending=False)
    )

    fig = px.bar(
        product_giveaway,
        x="Product Name",
        y="Giveaway",
        color="Giveaway",
        color_continuous_scale="Blues",
        template=CHART_TEMPLATE,
        text_auto=".1f",
    )
    fig.update_traces(marker_line_width=0, textposition="outside")
    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=30, b=20),
        coloraxis_showscale=False,
        xaxis_title="Product",
        yaxis_title="Total Giveaway (g)",
        title="",
        uniformtext_minsize=8,
        uniformtext_mode="hide",
    )
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TRENDS
# ============================================================

with tab_trends:
    # Weight Drift Trend
    st.subheader("Weight Drift Trend")

    fig1 = px.line(
        df.sort_values("Timestamp"),
        x="Timestamp",
        y="Weight Drift",
        color="Product Name",
        markers=True,
        template=CHART_TEMPLATE,
    )
    fig1.add_hline(y=0, line_dash="dash", line_color="gray")
    fig1.update_traces(line_width=2.5, marker_size=6)
    fig1.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=35, b=20),
        xaxis_title="Timestamp",
        yaxis_title="Weight Drift (g)",
        legend_title="Product",
        title="",
    )
    st.plotly_chart(fig1, use_container_width=True)

    st.markdown("---")

    # Giveaway Trend
    st.subheader("Giveaway Trend")

    fig2 = px.line(
        df.sort_values("Timestamp"),
        x="Timestamp",
        y="Giveaway",
        color="Product Name",
        markers=True,
        template=CHART_TEMPLATE,
    )
    fig2.update_traces(line_width=2.5, marker_size=6)
    fig2.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=35, b=20),
        xaxis_title="Timestamp",
        yaxis_title="Giveaway (g)",
        legend_title="Product",
        title="",
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # Financial Loss Trend
    st.subheader("Financial Loss Trend")

    fig3 = px.line(
        df.sort_values("Timestamp"),
        x="Timestamp",
        y="Total Loss",
        markers=True,
        template=CHART_TEMPLATE,
    )
    fig3.update_traces(line_width=2.5, marker_size=6, line_color="#C0392B")
    fig3.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=35, b=20),
        xaxis_title="Timestamp",
        yaxis_title="Financial Loss (₹)",
        title="",
    )
    st.plotly_chart(fig3, use_container_width=True)

# ============================================================
# DATA
# ============================================================

with tab_data:
    st.subheader("Processed Production Records")

    display_cols = [
        c for c in [
            "Timestamp", "Date", "Shift", "Product Name",
            "Actual Weight", "Weight Drift", "Giveaway", "Total Loss", "Status"
        ] if c in df.columns
    ]

    st.dataframe(
        df[display_cols].sort_values("Timestamp", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered data as CSV",
        data=csv,
        file_name="filtered_production_data.csv",
        mime="text/csv",
    )

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
col1, col2 = st.columns([3, 1])
with col1:
    st.caption("Production Loss Dashboard | Streamlit | Plotly")
with col2:
    st.caption(f"Records : {len(df):,}")
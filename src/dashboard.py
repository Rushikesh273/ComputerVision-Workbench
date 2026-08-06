"""
dashboard.py
=============
Streamlit dashboard for visualizing production giveaway / weight-drift
losses, reading from production_data_processed.csv.

Run with:
    streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px

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

/* Background */

.stApp{
    background-color:#F5F7FA;
}

/* Main container */

.block-container{
    padding-top:1.2rem;
    padding-bottom:1rem;
    padding-left:2rem;
    padding-right:2rem;
}

/* Heading */

h1{
    color:#1f2937;
    font-weight:700;
    letter-spacing:0.3px;
}

h2,h3{
    color:#374151;
}

/* Sidebar */

[data-testid="stSidebar"]{
    background:#FFFFFF;
    border-right:1px solid #E5E7EB;
}

/* Metric cards */

[data-testid="metric-container"]{

    background:white;

    border:1px solid #E5E7EB;

    border-radius:12px;

    padding:18px;

    box-shadow:0px 2px 8px rgba(0,0,0,0.05);

}

/* Tabs */

button[data-baseweb="tab"]{

    font-size:16px;

    font-weight:600;

}

/* Horizontal line */

hr{

    margin-top:0.5rem;

    margin-bottom:1rem;

}

</style>
""", unsafe_allow_html=True)

# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data
def load_data(path):

    df = pd.read_csv(path)

    df["Timestamp"] = pd.to_datetime(df["Timestamp"])

    df["Date"] = pd.to_datetime(df["Date"]).dt.date

    return df


df = load_data("production_data_processed.csv")

# ============================================================
# HEADER
# ============================================================

st.title("▣ Production Loss Dashboard")

st.caption(
    "Production giveaway, weight drift and financial loss monitoring dashboard."
)

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("◇ Filters")

st.sidebar.markdown("---")

product = st.sidebar.multiselect(
    "Product",
    sorted(df["Product Name"].unique()),
    default=sorted(df["Product Name"].unique())
)

date_range = st.sidebar.date_input(
    "Date Range",
    (
        df["Date"].min(),
        df["Date"].max()
    )
)

shift = st.sidebar.multiselect(
    "Shift",
    sorted(df["Shift"].unique()),
    default=sorted(df["Shift"].unique())
)

# ============================================================
# FILTER DATA
# ============================================================

df = df[
    (df["Product Name"].isin(product))
    &
    (df["Shift"].isin(shift))
]

if isinstance(date_range, tuple) and len(date_range) == 2:

    df = df[
        (df["Date"] >= date_range[0])
        &
        (df["Date"] <= date_range[1])
    ]

if df.empty:

    st.warning("No records match the selected filters.")

    st.stop()

# ============================================================
# COMMON CHART SETTINGS
# ============================================================

CHART_TEMPLATE = "plotly_white"

# ============================================================
# TABS
# ============================================================

tab_overview, tab_trends, tab_data = st.tabs(
    [
        "□ Overview",
        "↗ Trends",
        "▤ Data"
    ]
)

# ============================================================
# OVERVIEW
# ============================================================

with tab_overview:

    st.subheader("Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "■ Total Production",
        f"{len(df):,} Packets"
    )

    col2.metric(
        "⚖ Average Weight",
        f"{df['Actual Weight'].mean():.2f} g"
    )

    col3.metric(
        "◆ Total Giveaway",
        f"{df['Giveaway'].sum():.2f} g"
    )

    col4.metric(
        "₹ Total Financial Loss",
        f"₹ {df['Total Loss'].sum():,.2f}"
    )

    st.markdown("---")

    st.subheader("Product-wise Giveaway")

    product_giveaway = (
        df.groupby("Product Name")["Giveaway"]
        .sum()
        .reset_index()
        .sort_values(
            "Giveaway",
            ascending=False
        )
    )

    fig = px.bar(
        product_giveaway,
        x="Product Name",
        y="Giveaway",
        color="Giveaway",
        color_continuous_scale="Blues",
        template=CHART_TEMPLATE,
    )

    fig.update_traces(
        marker_line_width=0
    )

    fig.update_layout(
        height=430,
        margin=dict(
            l=20,
            r=20,
            t=40,
            b=20
        ),
        coloraxis_showscale=False,
        xaxis_title="Product",
        yaxis_title="Total Giveaway (g)",
        title=None
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

# ============================================================
# TRENDS
# ============================================================

with tab_trends:

    # --------------------------------------------------------
    # Weight Drift Trend
    # --------------------------------------------------------

    st.subheader("Weight Drift Trend")

    fig1 = px.line(
        df.sort_values("Timestamp"),
        x="Timestamp",
        y="Weight Drift",
        color="Product Name",
        markers=True,
        template=CHART_TEMPLATE,
    )

    fig1.add_hline(
        y=0,
        line_dash="dash",
        line_color="gray"
    )

    fig1.update_traces(
        line_width=3,
        marker_size=7
    )

    fig1.update_layout(
        height=380,
        margin=dict(
            l=20,
            r=20,
            t=35,
            b=20
        ),
        xaxis_title="Timestamp",
        yaxis_title="Weight Drift (g)",
        legend_title="Product"
    )

    st.plotly_chart(
        fig1,
        use_container_width=True
    )

    st.markdown("---")

    # --------------------------------------------------------
    # Giveaway Trend
    # --------------------------------------------------------

    st.subheader("Giveaway Trend")

    fig2 = px.line(
        df.sort_values("Timestamp"),
        x="Timestamp",
        y="Giveaway",
        color="Product Name",
        markers=True,
        template=CHART_TEMPLATE,
    )

    fig2.update_traces(
        line_width=3,
        marker_size=7
    )

    fig2.update_layout(
        height=380,
        margin=dict(
            l=20,
            r=20,
            t=35,
            b=20
        ),
        xaxis_title="Timestamp",
        yaxis_title="Giveaway (g)",
        legend_title="Product"
    )

    st.plotly_chart(
        fig2,
        use_container_width=True
    )

    st.markdown("---")

    # --------------------------------------------------------
    # Financial Loss Trend
    # --------------------------------------------------------

    st.subheader("Financial Loss Trend")

    fig3 = px.line(
        df.sort_values("Timestamp"),
        x="Timestamp",
        y="Total Loss",
        markers=True,
        template=CHART_TEMPLATE,
    )

    fig3.update_traces(
        line_width=3,
        marker_size=7,
        line_color="#C0392B"
    )

    fig3.update_layout(
        height=380,
        margin=dict(
            l=20,
            r=20,
            t=35,
            b=20
        ),
        xaxis_title="Timestamp",
        yaxis_title="Financial Loss (₹)"
    )

    st.plotly_chart(
        fig3,
        use_container_width=True
    )

# ============================================================
# DATA
# ============================================================

with tab_data:

    st.subheader("Processed Production Records")

    st.dataframe(
        df.sort_values(
            "Timestamp",
            ascending=False
        ),
        use_container_width=True,
        hide_index=True,
    )

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

col1, col2 = st.columns([3, 1])

with col1:
    st.caption(
        "Production Loss Dashboard | Streamlit | Plotly"
    )

with col2:
    st.caption(
        f"Records : {len(df):,}"
    )
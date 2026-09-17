from datetime import UTC, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="Singapore Air Quality",
    page_icon="🌫️",
    layout="wide",
)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)


@st.cache_data(ttl=600)
def fetch_all(
    table_name: str,
    start_time: str | None = None,
) -> pd.DataFrame:
    page_size = 1000
    offset = 0
    records: list[dict] = []

    while True:
        query = (
            supabase.table(table_name)
            .select("*")
            .range(offset, offset + page_size - 1)
        )

        if start_time:
            query = query.gte("observed_at", start_time)

        batch = query.execute().data or []
        records.extend(batch)

        if len(batch) < page_size:
            break

        offset += page_size

    return pd.DataFrame(records)


st.title("Bear's Singapore Air Quality Dashboard")
st.caption(
    "Hourly NEA/data.gov.sg readings processed through "
    "GitHub Actions, Python and Supabase. Refer to NEA for official advice."
)

days = st.sidebar.selectbox(
    "Date range",
    options=[1, 3, 7, 30, 90],
    index=2,
)

start_time = (
    datetime.now(UTC) - timedelta(days=days)
).isoformat()

latest = fetch_all("v_latest_air_quality")
history = fetch_all("v_air_quality_hourly_change", start_time=start_time)
freshness = fetch_all("v_pipeline_freshness")

if latest.empty or history.empty:
    st.warning("No air-quality observations are currently available.")
    st.stop()

history["observed_at"] = pd.to_datetime(history["observed_at"], utc=True)
history["observed_at_sgt"] = history["observed_at"].dt.tz_convert(
    "Asia/Singapore"
)

numeric_columns = [
    "pm25_1h",
    "pm25_24h",
    "pm10_24h",
    "psi_24h",
    "pm25_change_1h",
    "psi_change_1h",
]

for column in numeric_columns:
    if column in history.columns:
        history[column] = pd.to_numeric(history[column], errors="coerce")
    if column in latest.columns:
        latest[column] = pd.to_numeric(latest[column], errors="coerce")

highest_pm25_row = latest.loc[latest["pm25_1h"].idxmax()]
highest_psi_row = latest.loc[latest["psi_24h"].idxmax()]

current_pm25 = float(highest_pm25_row["pm25_1h"])
pm25_change = highest_pm25_row["pm25_change_1h"]
pm25_delta = None if pd.isna(pm25_change) else f"{pm25_change:+.0f} in 1 hour"

metric_1, metric_2, metric_3, metric_4, metric_5 = st.columns(5)

metric_1.metric(
    "Highest hourly PM2.5",
    f"{current_pm25:.0f} µg/m³",
    delta=pm25_delta,
)
metric_2.metric("PM2.5 band", highest_pm25_row["pm25_1h_band"])
metric_3.metric("Highest 24-hour PSI", f"{highest_psi_row['psi_24h']:.0f}")
metric_4.metric("Highest region", str(highest_pm25_row["region"]).title())

if not freshness.empty:
    age = float(freshness.iloc[0]["observation_age_hours"])
    status = freshness.iloc[0]["freshness_status"]
    metric_5.metric("Data freshness", status)
    metric_5.caption(f"Latest observation: {age:.1f} hours old")

if current_pm25 >= 151:
    st.error("High hourly PM2.5 detected. Refer to official NEA health advice.")
elif current_pm25 >= 56:
    st.warning("Elevated hourly PM2.5 detected.")
else:
    st.success("Hourly PM2.5 is currently within NEA's Normal band.")

tab_current, tab_trends, tab_patterns = st.tabs(
    ["Current conditions", "Recent trends", "Historical patterns"]
)

with tab_current:
    st.subheader("Latest regional conditions")
    st.dataframe(
        latest[
            [
                "region",
                "pm25_1h",
                "pm25_1h_band",
                "pm25_change_1h",
                "psi_24h",
                "psi_24h_category",
            ]
        ].sort_values("region"),
        use_container_width=True,
        hide_index=True,
    )

    map_figure = px.scatter_map(
        latest,
        lat="latitude",
        lon="longitude",
        color="pm25_1h",
        size="pm25_1h",
        hover_name="region",
        hover_data={
            "pm25_1h": True,
            "pm25_1h_band": True,
            "psi_24h": True,
            "latitude": False,
            "longitude": False,
        },
        zoom=9.5,
        center={"lat": 1.3521, "lon": 103.8198},
        height=520,
    )
    st.plotly_chart(map_figure, use_container_width=True)

with tab_trends:
    chosen_regions = st.multiselect(
        "Regions",
        options=sorted(history["region"].unique()),
        default=sorted(history["region"].unique()),
    )
    filtered = history[history["region"].isin(chosen_regions)]

    pm25_figure = px.line(
        filtered,
        x="observed_at_sgt",
        y="pm25_1h",
        color="region",
        title="Hourly PM2.5 by region",
    )
    pm25_figure.add_hline(
        y=56,
        line_dash="dash",
        line_color="orange",
        annotation_text="Elevated: 56",
    )
    pm25_figure.add_hline(
        y=151,
        line_dash="dash",
        line_color="red",
        annotation_text="High: 151",
    )
    pm25_figure.add_hline(
        y=251,
        line_dash="dash",
        line_color="darkred",
        annotation_text="Very High: 251",
    )
    st.plotly_chart(pm25_figure, use_container_width=True)

    psi_figure = px.line(
        filtered,
        x="observed_at_sgt",
        y="psi_24h",
        color="region",
        title="24-hour PSI by region",
    )
    psi_figure.add_hline(
        y=101,
        line_dash="dash",
        line_color="red",
        annotation_text="Unhealthy: 101",
    )
    st.plotly_chart(psi_figure, use_container_width=True)

with tab_patterns:
    pattern_data = (
        history.assign(hour_sgt=history["observed_at_sgt"].dt.hour)
        .groupby(["region", "hour_sgt"], as_index=False)["pm25_1h"]
        .mean()
    )

    heatmap = px.density_heatmap(
        pattern_data,
        x="hour_sgt",
        y="region",
        z="pm25_1h",
        color_continuous_scale="YlOrRd",
        title="Average hourly PM2.5 pattern",
    )
    st.plotly_chart(heatmap, use_container_width=True)

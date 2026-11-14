from datetime import UTC, datetime, timedelta
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client

SGT = "Asia/Singapore"
PM25_LABEL = "1-hour PM2.5 (µg/m³)"
PSI_LABEL = "24-hour PSI"
PM25_BANDS = {
    "Normal": ("green", "#147d64"),
    "Elevated": ("orange", "#b25b05"),
    "High": ("red", "#bc392e"),
    "Very High": ("violet", "#8b389d"),
    "Unknown": ("gray", "#6b7280"),
}
PSI_COLORS = {
    "Good": "green",
    "Moderate": "orange",
    "Unhealthy": "red",
    "Very Unhealthy": "violet",
    "Hazardous": "violet",
}
REGION_COLORS = {
    "Central": "#1666a5",
    "East": "#a85d0c",
    "North": "#7d50a5",
    "South": "#16816e",
    "West": "#c14263",
}
CHART_LABELS = {
    "region": "Region",
    "observed_at_sgt": "Observation time (SGT)",
    "pm25_1h": PM25_LABEL,
    "pm25_1h_band": "PM2.5 band",
    "psi_24h": PSI_LABEL,
    "psi_24h_category": "PSI category",
}
HISTORY_RANGES = {1: "1 day", 3: "3 days", 7: "7 days", 30: "30 days", 90: "90 days"}

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
        query = supabase.table(table_name).select("*")
        if start_time:
            query = (
                query.gte("observed_at", start_time)
                .order("observed_at")
                .order("region")
            )

        batch = query.range(offset, offset + page_size - 1).execute().data or []
        records.extend(batch)
        if len(batch) < page_size:
            break

        offset += page_size

    return pd.DataFrame(records)


def prepare_readings(readings: pd.DataFrame) -> pd.DataFrame:
    if readings.empty:
        return readings

    readings["region"] = readings["region"].str.title()
    readings["observed_at_sgt"] = pd.to_datetime(
        readings["observed_at"], utc=True
    ).dt.tz_convert(SGT)
    for column in ("pm25_1h", "psi_24h", "pm25_change_1h"):
        readings[column] = pd.to_numeric(readings[column], errors="coerce")

    return readings.sort_values(["observed_at_sgt", "region"])


def format_reading(value: float, suffix: str = "") -> str:
    return "Unavailable" if pd.isna(value) else f"{value:.0f}{suffix}"


def render_regional_compass(latest: pd.DataFrame) -> None:
    by_region = latest.set_index("region")
    regions = []

    for region in ("North", "West", "Central", "East", "South"):
        if region in by_region.index:
            row = by_region.loc[region]
            pm25 = format_reading(row["pm25_1h"], " µg/m³")
            psi = format_reading(row["psi_24h"])
            band = str(row["pm25_1h_band"])
            category = str(row["psi_24h_category"])
            pm25_color = PM25_BANDS.get(band, PM25_BANDS["Unknown"])[0]
            psi_color = PSI_COLORS.get(category, "gray")
            observed = f"{row['observed_at_sgt']:%d %b, %H:%M} SGT"
            readings = f"""
                <dl>
                    <dt>1-hour PM2.5</dt>
                    <dd><strong>{pm25}</strong>
                        <span class="aq-status {pm25_color}">{escape(band)}</span>
                    </dd>
                    <dt>{PSI_LABEL}</dt>
                    <dd><strong>{psi}</strong>
                        <span class="aq-status {psi_color}">{escape(category)}</span>
                    </dd>
                </dl>
                <small>{observed}</small>
            """
        else:
            readings = "<p>No readings</p>"

        regions.append(f"""
            <section class="aq-region {region.lower()}" aria-label="{region}">
                <h3>{region}</h3>
                {readings}
            </section>
        """)

    st.html(
        '<div class="aq-compass" role="group" aria-label="Air quality compass">'
        + "".join(regions)
        + "</div>"
    )


def render_trend(
    readings: pd.DataFrame,
    metric: str,
    thresholds: dict[int, str],
) -> None:
    st.subheader(CHART_LABELS[metric])
    valid = readings[metric].dropna()
    if valid.empty:
        st.info("No readings for this indicator in the selected period.")
        return

    # Use Singapore wall-clock times so the chart is independent of browser timezone.
    plot_data = readings.assign(
        observed_at_sgt=readings["observed_at_sgt"].dt.tz_localize(None)
    )
    figure = px.line(
        plot_data,
        x="observed_at_sgt",
        y=metric,
        color="region",
        labels=CHART_LABELS,
        color_discrete_map=REGION_COLORS,
        category_orders={"region": list(REGION_COLORS)},
        markers=readings["observed_at_sgt"].nunique() == 1,
    )
    figure.update_traces(
        connectgaps=False,
        hovertemplate=(
            "%{x|%d %b %Y, %H:%M} SGT<br>"
            + CHART_LABELS[metric]
            + ": %{y:.0f}"
        ),
    )
    for value, label in thresholds.items():
        if valid.min() <= value <= valid.max():
            figure.add_hline(
                y=value,
                line_dash="dash",
                line_color="#b25b05",
                annotation_text=f"{label} · {value}",
            )

    figure.update_layout(
        height=350,
        margin=dict(l=12, r=12, t=12, b=12),
        legend=dict(title=None, orientation="h", y=1.02, yanchor="bottom"),
        hovermode="x unified",
        yaxis_rangemode="tozero",
    )
    st.plotly_chart(figure)


st.html("""
<style>
.st-key-history_range button { border-radius: 2px; min-height: 44px; }
.aq-compass {
    display: grid;
    grid-template-areas: ". north ." "west central east" ". south .";
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: clamp(0.25rem, 1.5vw, 0.85rem);
    max-width: 40rem;
    margin: 0 auto 0.75rem;
    text-align: center;
}
.aq-compass .north { grid-area: north; }
.aq-compass .west { grid-area: west; }
.aq-compass .central { grid-area: central; }
.aq-compass .east { grid-area: east; }
.aq-compass .south { grid-area: south; }
.aq-compass .aq-region {
    min-width: 0;
    padding: clamp(0.25rem, 1.35vw, 0.8rem);
    background: var(--secondary-background-color, transparent);
    border: 1px solid currentColor;
    border-color: color-mix(in srgb, currentColor 24%, transparent);
    border-radius: 0.5rem;
    overflow-wrap: anywhere;
    text-align: center;
}
.aq-compass .aq-region :is(h3, dl, dt, dd, strong, p, small, .aq-status) {
    text-align: center;
}
.aq-compass .aq-region.central { border-color: currentColor; }
.aq-compass h3 { margin: 0 0 0.35rem; padding: 0; font-size: 1.05rem; }
/* Clear Streamlit's definition-list indentation inside compass cards. */
.aq-compass .aq-region dl,
.aq-compass .aq-region dd {
    margin: 0;
    padding-inline: 0;
}
.aq-compass .aq-region dd { margin-bottom: 0.4rem; line-height: 1.3; }
.aq-compass dt { font-size: 0.75rem; }
.aq-compass strong { font-size: clamp(0.85rem, 2.7vw, 1.2rem); }
.aq-compass small, .aq-compass .aq-status { display: block; font-size: 0.73rem; }
.aq-compass .aq-status::before {
    content: "";
    display: inline-block;
    width: 0.45rem;
    height: 0.45rem;
    margin-right: 0.24rem;
    border-radius: 50%;
    background: var(--aq-status-color, #6b7280);
    vertical-align: 0.08rem;
}
.aq-compass .green { --aq-status-color: #147d64; }
.aq-compass .orange { --aq-status-color: #b25b05; }
.aq-compass .red { --aq-status-color: #bc392e; }
.aq-compass .violet { --aq-status-color: #8b389d; }
</style>
""")
st.title("Bear's Singapore Air Quality Dashboard")
st.caption(
    "Hourly readings from NEA via data.gov.sg. "
    "See [NEA’s Haze portal](https://www.haze.gov.sg/) for official advice."
)

latest = prepare_readings(fetch_all("v_latest_air_quality"))
freshness = fetch_all("v_pipeline_freshness")

if not freshness.empty and pd.notna(freshness.iloc[0]["observation_age_hours"]):
    status = freshness.iloc[0]
    observation = pd.Timestamp(status["latest_observation_utc"]).tz_convert(SGT)
    age = float(status["observation_age_hours"])
    freshness_label = (
        f"Latest observation · {observation:%d %b %Y, %H:%M} SGT · {age:.1f} hours ago"
    )
    if status["freshness_status"] == "FRESH":
        st.caption(freshness_label)
    else:
        st.warning(f"{status['freshness_status'].title()} data. {freshness_label}")

tab_current, tab_trends, tab_patterns = st.tabs(
    ["Current conditions", "Recent trends", "Historical patterns"]
)

with tab_current:
    st.subheader("Air quality by region")
    st.caption(
        "PM2.5 reflects the past hour. PSI summarises the past 24 hours."
    )
    if latest.empty:
        st.info("No regional readings are available.")
    else:
        render_regional_compass(latest)

        mapped = latest.dropna(subset=["latitude", "longitude"])
        if not mapped.empty:
            st.subheader("Regional PM2.5 map")
            map_figure = px.scatter_map(
                mapped,
                lat="latitude",
                lon="longitude",
                color="pm25_1h_band",
                color_discrete_map={
                    band: colors[1] for band, colors in PM25_BANDS.items()
                },
                category_orders={"pm25_1h_band": list(PM25_BANDS)},
                labels=CHART_LABELS,
                hover_name="region",
                hover_data={
                    "pm25_1h": ":.0f",
                    "psi_24h": ":.0f",
                    "psi_24h_category": True,
                    "latitude": False,
                    "longitude": False,
                },
                zoom=9.5,
                center={"lat": 1.3521, "lon": 103.8198},
                height=380,
            )
            map_figure.update_traces(marker_size=16)
            map_figure.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                legend=dict(title=None, orientation="h", y=1.02, yanchor="bottom"),
            )
            st.plotly_chart(map_figure)

        with st.expander("Regional readings and hourly changes"):
            table_labels = {
                **CHART_LABELS,
                "pm25_change_1h": "PM2.5 change in 1 hour (µg/m³)",
            }
            st.dataframe(
                latest[list(table_labels)].sort_values("region").rename(columns=table_labels),
                column_config={
                    CHART_LABELS["observed_at_sgt"]: st.column_config.DatetimeColumn(
                        format="DD MMM YYYY, HH:mm", timezone=SGT
                    ),
                },
                width="stretch",
                hide_index=True,
            )

with tab_trends:
    days = st.segmented_control(
        "History range",
        options=list(HISTORY_RANGES),
        default=7,
        format_func=HISTORY_RANGES.__getitem__,
        key="history_range",
    )
    if days is None:
        st.info("Select a history range to see recent trends.")
        history = pd.DataFrame()
    else:
        # Align the cutoff with hourly observations so it doubles as a cache key.
        current_hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        start_time = (current_hour - timedelta(hours=days * 24 - 1)).isoformat()
        history = prepare_readings(
            fetch_all("v_air_quality_hourly_change", start_time=start_time)
        )
        if history.empty:
            st.info("No observations in this range. Try a longer period.")

    if not history.empty:
        regions = sorted(history["region"].unique())
        chosen_regions = st.multiselect("Regions", regions, default=regions)
        if not chosen_regions:
            st.info("Select at least one region to see its trend.")
        else:
            filtered = history[history["region"].isin(chosen_regions)]
            hours = pd.date_range(
                history["observed_at_sgt"].min(),
                history["observed_at_sgt"].max(),
                freq="h",
            )
            grid = pd.MultiIndex.from_product(
                [chosen_regions, hours], names=["region", "observed_at_sgt"]
            )
            filtered = filtered.set_index(grid.names).reindex(grid).reset_index()
            st.caption(
                "Breaks in the lines show missing readings. Times are in SGT."
            )
            render_trend(
                filtered, "pm25_1h", {56: "Elevated", 151: "High", 251: "Very High"}
            )
            render_trend(
                filtered,
                "psi_24h",
                {101: "Unhealthy", 201: "Very Unhealthy", 301: "Hazardous"},
            )

with tab_patterns:
    st.subheader("Average PM2.5 by hour of day")
    if days is None:
        st.info("Choose a history range in Recent trends.")
    elif history.empty or history["pm25_1h"].isna().all():
        st.info(
            "No PM2.5 observations in this range. Try a longer range in Recent trends."
        )
    else:
        st.caption(
            f"Last {HISTORY_RANGES[days]} · Darker cells show higher averages. "
            "Blank cells have no readings."
        )
        averages = (
            history.assign(hour_sgt=history["observed_at_sgt"].dt.hour)
            .pivot_table(index="region", columns="hour_sgt", values="pm25_1h")
            .reindex(index=list(REGION_COLORS), columns=range(24))
        )
        heatmap = px.imshow(
            averages,
            labels={"x": "Hour of day (SGT)", "y": "Region", "color": PM25_LABEL},
            color_continuous_scale="YlOrRd",
            aspect="auto",
            height=340,
        )
        heatmap.update_traces(
            hoverongaps=False,
            hovertemplate=(
                "%{y} · %{x:02.0f}:00 SGT<br>"
                "Average PM2.5: %{z:.1f} µg/m³<extra></extra>"
            ),
        )
        heatmap.update_xaxes(tickvals=list(range(0, 24, 3)))
        heatmap.update_layout(
            margin=dict(l=12, r=12, t=12, b=12),
            coloraxis_colorbar_title="PM2.5<br>(µg/m³)",
        )
        st.plotly_chart(heatmap)

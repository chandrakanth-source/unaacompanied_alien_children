import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import analytics as an

st.set_page_config(page_title="UAC Care Transition Analytics", layout="wide", page_icon="")
CSS = """
    <style>
        .kpi-card { background:#1a1a2e; border-radius:12px; padding:16px; text-align:center; border:1px solid #2d2d5e; }
        .kpi-value { font-size:2rem; font-weight:700; color:#00d4aa; }
        .kpi-label { font-size:.85rem; color:#a0a0c0; margin-top:4px; }
        .kpi-sub { font-size:.75rem; color:#606080; }
        .alert-card { background:#2d1b1b; border-radius:8px; padding:10px 14px; border-left:4px solid #ff4444; margin:4px 0; }
        .alert-card.warning { background:#2d2b1b; border-left-color:#ffaa00; }
        .alert-card.success { background:#1b2d1b; border-left-color:#44ff44; }
        .insight-box { background:#0d1117; border-radius:8px; padding:12px 16px; border:1px solid #30363d; margin:4px 0; font-size:.9rem; }
        .insight-label { color:#8b949e; font-size:.75rem; text-transform:uppercase; }
        .insight-value { color:#00d4aa; font-size:1.1rem; font-weight:600; }
        h1, h2, h3 { margin-bottom:0.5rem; }
        .block-container { padding-top:2rem; padding-bottom:2rem; }
        hr { margin:.5rem 0; }
    </style>
""" 
st.markdown(CSS, unsafe_allow_html=True)

st.sidebar.image("https://img.icons8.com/fluency/96/passport.png", width=60)
st.sidebar.title("UAC Analytics")
st.sidebar.markdown("**Care Transition Efficiency & Placement Outcomes**")
st.sidebar.markdown("---")

df = an.load_data()
min_date, max_date = df["Date"].min(), df["Date"].max()
date_range = st.sidebar.date_input("Date Range", [min_date, max_date],
                                   min_value=min_date, max_value=max_date)
metric_toggle = st.sidebar.selectbox("Metric Display",
                                     ["Absolute Values", "Ratio / Percentage", "Both"])
threshold_pct = st.sidebar.slider("Alert Threshold (%)", 5, 50, 20, 5)
show_alerts = st.sidebar.checkbox("Show Alerts", True)

if len(date_range) == 2:
    df_filt = an.filter_by_date(df, date_range[0], date_range[1])
else:
    df_filt = df.copy()

kpis = an.compute_kpis(df_filt)
bottleneck_df = an.detect_bottlenecks(df_filt)
insights = an.get_eda_insights(df_filt)

st.title("UAC Care Pipeline — Transition Efficiency & Placement Analytics")
st.markdown("**Unaccompanied Alien Children Program** — *U.S. Department of Health and Human Services*")
st.markdown("Analyzing the multi-stage care pipeline: CBP Custody → HHS Care → Sponsor Placement")
st.markdown("---")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-value">{kpis['TER']:.2f}</div><div class="kpi-label">Transfer Efficiency Ratio</div><div class="kpi-sub">CBP → HHS flow rate</div></div>""", unsafe_allow_html=True)
with col2:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-value">{kpis['DEI']:.4f}</div><div class="kpi-label">Discharge Effectiveness</div><div class="kpi-sub">Placement success rate</div></div>""", unsafe_allow_html=True)
with col3:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-value">{kpis['PTR']:.2f}</div><div class="kpi-label">Pipeline Throughput</div><div class="kpi-sub">Exits ÷ Entries</div></div>""", unsafe_allow_html=True)
with col4:
    sign = "+" if kpis['BacklogNet'] > 0 else ""
    backlog_color = "#ff4444" if kpis['BacklogNet'] > 0 else "#44ff44"
    st.markdown(f"""<div class="kpi-card"><div class="kpi-value" style="color:{backlog_color}">{sign}{kpis['BacklogNet']:.0f}</div><div class="kpi-label">Backlog Accumulation</div><div class="kpi-sub">Inflow − Discharges</div></div>""", unsafe_allow_html=True)
with col5:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-value">{kpis['StabilityScore']:.1f}</div><div class="kpi-label">Outcome Stability Score</div><div class="kpi-sub">14d σ of discharges</div></div>""", unsafe_allow_html=True)

if show_alerts:
    st.markdown("### Alerts")
    alerts = an.generate_alerts(kpis, threshold_pct, df_filt)
    if len(alerts) == 0:
        st.markdown("""<div class="alert-card success">System operating within normal parameters.</div>""", unsafe_allow_html=True)
    else:
        for typ, msg in alerts:
            cls = "alert-card" if typ == "danger" else "alert-card warning"
            st.markdown(f"""<div class="{cls}">{msg}</div>""", unsafe_allow_html=True)

tabs = st.tabs(["Care Pipeline Flow", "Efficiency Metrics", "Bottleneck Detection",
                "Outcome Trends", "Advanced Analytics", "Data Explorer"])

with tabs[0]:
    st.subheader("Care Pipeline Flow")
    st.markdown("Daily volumes across the CBP → HHS → Sponsor pipeline stages.")

    flow_df = an.get_pipeline_flow(df_filt)
    fig = px.area(flow_df, x="Date", y="Count", color="Stage",
                  title="Pipeline Stage Volumes Over Time",
                  color_discrete_sequence=px.colors.qualitative.Plotly)
    fig.update_layout(height=450, hovermode="x unified", legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig, width='stretch')

    col_a, col_b = st.columns(2)
    with col_a:
        latest = an.get_latest_snapshot(df_filt)
        stages = ["CBP Custody", "HHS Care"]
        sizes = [latest.get("Children in CBP custody", 0), latest.get("Children in HHS Care", 0)]
        fig2 = px.pie(names=stages, values=sizes, title="Current Custody Split",
                      color_discrete_sequence=["#ff6b6b", "#4ecdc4"])
        fig2.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig2, width='stretch')
    with col_b:
        total_in = latest.get("Children apprehended and placed in CBP custody*", 0)
        total_out = latest.get("Children discharged from HHS Care", 0)
        in_transit = latest.get("Children transferred out of CBP custody", 0)
        fig2b = go.Figure(go.Bar(x=["Apprehended", "Transferred", "Discharged"],
                                 y=[total_in, in_transit, total_out],
                                 marker_color=["#ff6b6b", "#f9ca24", "#00d4aa"]))
        fig2b.update_layout(title="Daily Pipeline Movement", height=300, yaxis_title="Children")
        st.plotly_chart(fig2b, width='stretch')

    st.subheader("Cumulative Pipeline Flow")
    cum = an.get_cumulative_flow(df_filt)
    fig_cum = go.Figure()
    fig_cum.add_trace(go.Scatter(x=cum["Date"], y=cum["CumInflow"], mode="lines",
                                 name="Cumulative Inflow", line=dict(color="#ff6b6b", width=2)))
    fig_cum.add_trace(go.Scatter(x=cum["Date"], y=cum["CumTransfers"], mode="lines",
                                 name="Cumulative Transfers", line=dict(color="#f9ca24", width=2)))
    fig_cum.add_trace(go.Scatter(x=cum["Date"], y=cum["CumDischarges"], mode="lines",
                                 name="Cumulative Discharges", line=dict(color="#00d4aa", width=2)))
    fig_cum.add_trace(go.Scatter(x=cum["Date"], y=cum["CumGap"], mode="lines",
                                 name="Inflow − Discharge Gap", line=dict(color="#6c5ce7", width=2, dash="dot")))
    fig_cum.update_layout(height=400, hovermode="x unified",
                          legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig_cum, width='stretch')

with tabs[1]:
    st.subheader("Transfer & Discharge Efficiency Metrics")
    st.markdown("Tracking process efficiency: how effectively children move through each stage.")

    metric_choices = ["Transfer Efficiency Ratio (TER)", "Discharge Effectiveness Index (DEI)",
                      "Pipeline Throughput Rate (PTR)"]
    sel_metrics = st.multiselect("Select metrics to display", metric_choices, default=metric_choices)

    eff = an.get_efficiency_metrics(df_filt)
    fig3 = go.Figure()
    colors_m = {"TER": "#00d4aa", "DEI": "#f9ca24", "PTR": "#6c5ce7"}
    if "Transfer Efficiency Ratio (TER)" in sel_metrics:
        fig3.add_trace(go.Scatter(x=eff["Date"], y=eff["TER"], mode="lines+markers",
                                   name="TER (CBP→HHS)", line=dict(color=colors_m["TER"], width=2),
                                   marker=dict(size=4)))
    if "Discharge Effectiveness Index (DEI)" in sel_metrics:
        fig3.add_trace(go.Scatter(x=eff["Date"], y=eff["DEI"], mode="lines+markers",
                                   name="DEI (HHS→Sponsor)", line=dict(color=colors_m["DEI"], width=2),
                                   marker=dict(size=4)))
    if "Pipeline Throughput Rate (PTR)" in sel_metrics:
        fig3.add_trace(go.Scatter(x=eff["Date"], y=eff["PTR"], mode="lines+markers",
                                   name="PTR (Exits/Entries)", line=dict(color=colors_m["PTR"], width=2),
                                   marker=dict(size=4)))
    fig3.update_layout(height=400, hovermode="x unified", yaxis_title="Ratio",
                       legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig3, width='stretch')

    st.subheader("Weekday vs Weekend")
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        wday = an.get_weekly_pattern(df_filt)
        wday["Period"] = wday["IsWeekend"].map({False: "Weekday", True: "Weekend"})
        fig_wd = go.Figure()
        fig_wd.add_trace(go.Bar(name="Inflow", x=wday["Period"], y=wday["avg_inflow"],
                                marker_color="#ff6b6b"))
        fig_wd.add_trace(go.Bar(name="Transfers", x=wday["Period"], y=wday["avg_transfer"],
                                marker_color="#f9ca24"))
        fig_wd.add_trace(go.Bar(name="Discharges", x=wday["Period"], y=wday["avg_discharge"],
                                marker_color="#00d4aa"))
        fig_wd.update_layout(barmode="group", height=350, yaxis_title="Avg Daily Count",
                             legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig_wd, width='stretch')
    with col_w2:
        dow = an.get_dayofweek_pattern(df_filt)
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow["Weekday"] = pd.Categorical(dow["Weekday"], categories=day_order, ordered=True)
        dow = dow.sort_values("Weekday")
        fig_dow = go.Figure()
        fig_dow.add_trace(go.Bar(name="Inflow", x=dow["Weekday"], y=dow["avg_inflow"],
                                 marker_color="#ff6b6b"))
        fig_dow.add_trace(go.Bar(name="Discharges", x=dow["Weekday"], y=dow["avg_discharge"],
                                 marker_color="#00d4aa"))
        fig_dow.update_layout(barmode="group", height=350, yaxis_title="Avg Daily Count",
                              legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig_dow, width='stretch')

    st.subheader("Monthly Trend")
    monthly = an.get_monthly_trends(df_filt)
    fig_m = go.Figure()
    fig_m.add_trace(go.Scatter(x=monthly["Label"], y=monthly["inflow"], mode="lines+markers",
                                name="Inflow", line=dict(color="#ff6b6b", width=2)))
    fig_m.add_trace(go.Scatter(x=monthly["Label"], y=monthly["transfers"], mode="lines+markers",
                                name="Transfers", line=dict(color="#f9ca24", width=2)))
    fig_m.add_trace(go.Scatter(x=monthly["Label"], y=monthly["discharges"], mode="lines+markers",
                                name="Discharges", line=dict(color="#00d4aa", width=2)))
    fig_m.update_layout(height=400, xaxis_tickangle=-45, yaxis_title="Monthly Total",
                        hovermode="x unified", legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig_m, width='stretch')

with tabs[2]:
    st.subheader("Bottleneck & Delay Detection")
    st.markdown("Identifying where, when, and why the pipeline stalls.")

    delay_stats = an.get_delay_summary_stats(df_filt)

    col_b0a, col_b0b, col_b0c, col_b0d = st.columns(4)
    with col_b0a:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-value" style="font-size:1.3rem">{delay_stats['avg_total_days']}d</div><div class="kpi-label">Avg Total Delay</div><div class="kpi-sub">CBP → Sponsor</div></div>""", unsafe_allow_html=True)
    with col_b0b:
        color = "#ff4444" if delay_stats['transfer_lag_pct'] > 30 else "#f9ca24"
        st.markdown(f"""<div class="kpi-card"><div class="kpi-value" style="font-size:1.3rem;color:{color}">{delay_stats['transfer_lag_pct']}%</div><div class="kpi-label">Transfer Lag Days</div><div class="kpi-sub">Zero-transfer days</div></div>""", unsafe_allow_html=True)
    with col_b0c:
        color = "#ff4444" if delay_stats['discharge_lag_pct'] > 30 else "#f9ca24"
        st.markdown(f"""<div class="kpi-card"><div class="kpi-value" style="font-size:1.3rem;color:{color}">{delay_stats['discharge_lag_pct']}%</div><div class="kpi-label">Discharge Lag Days</div><div class="kpi-sub">Zero-discharge days</div></div>""", unsafe_allow_html=True)
    with col_b0d:
        score = an.get_bottleneck_score(df_filt)["BottleneckScore"].iloc[-1]
        color = "#00d4aa" if score < 1 else ("#f9ca24" if score < 1.5 else "#ff4444")
        st.markdown(f"""<div class="kpi-card"><div class="kpi-value" style="font-size:1.3rem;color:{color}">{score:.2f}</div><div class="kpi-label">Current Bottleneck</div><div class="kpi-sub">&lt;1=low, &gt;1.5=critical</div></div>""", unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("### Pipeline Delay Timeline — CBP Stay vs HHS Stay")
    delay_timeline = an.get_delay_timeline(df_filt)
    fig_dt = go.Figure()
    fig_dt.add_trace(go.Scatter(x=delay_timeline["Date"], y=delay_timeline["CBP_Stay"], mode="lines",
                                 name="Est. CBP Stay (days)", line=dict(color="#ff6b6b", width=2),
                                 fill="tozeroy", fillcolor="rgba(255,107,107,0.15)"))
    fig_dt.add_trace(go.Scatter(x=delay_timeline["Date"], y=delay_timeline["HHS_Stay"], mode="lines",
                                 name="Est. HHS Stay (days)", line=dict(color="#4ecdc4", width=2),
                                 fill="tozeroy", fillcolor="rgba(78,205,196,0.15)"))
    fig_dt.add_trace(go.Scatter(x=delay_timeline["Date"], y=delay_timeline["Total_Stay"], mode="lines",
                                 name="Total Est. Days", line=dict(color="#f9ca24", width=2, dash="dash")))
    fig_dt.update_layout(height=350, hovermode="x unified",
                          yaxis_title="Estimated Days in Stage",
                          legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig_dt, width='stretch')

    st.markdown("### Process Flow — Sankey Diagram")
    sankey = an.get_sankey_data(df_filt)
    fig_sk = go.Figure(go.Sankey(
        node=dict(label=sankey["labels"], color=["#ff6b6b", "#ff6b6b", "#f9ca24", "#4ecdc4", "#00d4aa", "#6c5ce7"],
                  pad=20, thickness=25),
        link=dict(source=sankey["source"], target=sankey["target"], value=sankey["value"],
                  color=["rgba(255,107,107,0.3)", "rgba(249,202,36,0.3)", "rgba(78,205,196,0.3)", "rgba(0,212,170,0.3)"])))
    fig_sk.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_sk, width='stretch')

    st.markdown("---")
    st.markdown("### Inflow vs Outflow — Imbalance Detection")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        fig_b1 = go.Figure()
        fig_b1.add_trace(go.Scatter(x=bottleneck_df["Date"], y=bottleneck_df["Inflow"], mode="lines",
                                     name="Inflow (Apprehended)", line=dict(color="#ff6b6b", width=2)))
        fig_b1.add_trace(go.Scatter(x=bottleneck_df["Date"], y=bottleneck_df["Discharges"], mode="lines",
                                     name="Discharged (Placed)", line=dict(color="#00d4aa", width=2)))
        fig_b1.add_trace(go.Scatter(x=bottleneck_df["Date"], y=bottleneck_df["CBPtoHHS"], mode="lines",
                                     name="Transferred (CBP→HHS)", line=dict(color="#f9ca24", width=2)))
        fig_b1.update_layout(title="Inflow, Transfers & Discharges", height=320, hovermode="x unified",
                             legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig_b1, width='stretch')
    with col_b2:
        bar_colors = ["#00d4aa" if v < 0 else "#ff6b6b" for v in bottleneck_df["NetAccumulation"]]
        fig_b2 = go.Figure()
        fig_b2.add_trace(go.Bar(x=bottleneck_df["Date"], y=bottleneck_df["NetAccumulation"],
                                 marker_color=bar_colors, name="Net (Inflow−Discharge)"))
        fig_b2.add_trace(go.Scatter(x=bottleneck_df["Date"], y=bottleneck_df["CumBacklog"],
                                     mode="lines", name="Cumulative Backlog",
                                     line=dict(color="#6c5ce7", width=2, dash="dash")))
        fig_b2.update_layout(title="Net Accumulation & Cumulative Backlog", height=320,
                             hovermode="x unified", yaxis_title="Children",
                             legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig_b2, width='stretch')

    st.markdown("---")
    st.markdown("### Zero-Activity Lag Streaks (Consecutive Days Without Movement)")

    col_z1, col_z2 = st.columns(2)
    with col_z1:
        st.markdown("**Transfer Halts** — Days with no CBP→HHS transfers despite children in CBP")
        t_streaks = an.get_transfer_lag_streaks(df_filt)
        if len(t_streaks) > 0:
            fig_ts = go.Figure()
            fig_ts.add_trace(go.Bar(x=t_streaks["start"].dt.strftime("%Y-%m-%d"), y=t_streaks["days"],
                                     marker_color="#ff6b6b", name="Consecutive Days"))
            fig_ts.add_hline(y=3, line_dash="dash", line_color="#f9ca24",
                             annotation_text="3-day alert")
            fig_ts.update_layout(height=280, xaxis_tickangle=-45, yaxis_title="Days without transfers")
            st.plotly_chart(fig_ts, width='stretch')
            worst = t_streaks.head(5)
            st.dataframe(worst[["start", "end", "days", "avg_cbp"]].rename(
                columns={"start": "From", "end": "To", "days": "Days", "avg_cbp": "Avg CBP Load"}),
                width='stretch', hide_index=True)
        else:
            st.markdown("No transfer lag periods detected.")
    with col_z2:
        st.markdown("**Discharge Halts** — Days with no sponsor placements despite children in HHS")
        d_streaks = an.get_discharge_lag_streaks(df_filt)
        if len(d_streaks) > 0:
            fig_ds = go.Figure()
            fig_ds.add_trace(go.Bar(x=d_streaks["start"].dt.strftime("%Y-%m-%d"), y=d_streaks["days"],
                                     marker_color="#00d4aa", name="Consecutive Days"))
            fig_ds.add_hline(y=3, line_dash="dash", line_color="#f9ca24",
                             annotation_text="3-day alert")
            fig_ds.update_layout(height=280, xaxis_tickangle=-45, yaxis_title="Days without discharges")
            st.plotly_chart(fig_ds, width='stretch')
            worst = d_streaks.head(5)
            st.dataframe(worst[["start", "end", "days", "avg_hhs"]].rename(
                columns={"start": "From", "end": "To", "days": "Days", "avg_hhs": "Avg HHS Load"}),
                width='stretch', hide_index=True)
        else:
            st.markdown("No discharge lag periods detected.")

    st.markdown("---")
    st.markdown("### Sustained Imbalance Periods (Inflow > Discharge for 5+ Days)")
    imbalances = an.get_sustained_imbalance_periods(df_filt)
    if len(imbalances) > 0:
        st.dataframe(imbalances.head(10).rename(columns={
            "start": "Start", "end": "End", "days": "Duration (days)",
            "avg_imbalance": "Avg Daily Imbalance", "peak_imbalance": "Peak Imbalance",
            "total_excess_inflow": "Total Excess Inflow"
        }), width='stretch', hide_index=True)
    else:
        st.markdown("No sustained imbalance periods detected.")

    st.markdown("---")
    st.markdown("### Weekday Delay Pattern — Which Days Have the Worst Delays?")
    wd_delay = an.get_weekday_delay_pattern(df_filt)
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    wd_delay["Weekday"] = pd.Categorical(wd_delay["Weekday"], categories=day_order, ordered=True)
    wd_delay = wd_delay.sort_values("Weekday")
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        fig_wd1 = go.Figure()
        fig_wd1.add_trace(go.Bar(x=wd_delay["Weekday"], y=wd_delay["transfer_lag_pct"] * 100,
                                 marker_color=["#ff4444" if v > 0.3 else "#ff6b6b" if v > 0.1 else "#f9ca24"
                                               for v in wd_delay["transfer_lag_pct"]],
                                 name="Transfer Lag %"))
        fig_wd1.update_layout(title="% of Days with Zero Transfers by Weekday",
                              height=300, yaxis_title="Lag %")
        st.plotly_chart(fig_wd1, width='stretch')
    with col_w2:
        fig_wd2 = go.Figure()
        fig_wd2.add_trace(go.Bar(x=wd_delay["Weekday"], y=wd_delay["discharge_lag_pct"] * 100,
                                 marker_color=["#ff4444" if v > 0.3 else "#ff6b6b" if v > 0.1 else "#f9ca24"
                                               for v in wd_delay["discharge_lag_pct"]],
                                 name="Discharge Lag %"))
        fig_wd2.update_layout(title="% of Days with Zero Discharges by Weekday",
                              height=300, yaxis_title="Lag %")
        st.plotly_chart(fig_wd2, width='stretch')

    st.markdown("---")
    col_b3, col_b4 = st.columns(2)
    with col_b3:
        backlog_summary = an.get_backlog_severity_summary(bottleneck_df)
        st.markdown("**Backlog Severity Distribution**")
        fig_b3 = px.pie(names=backlog_summary.index, values=backlog_summary.values,
                         color_discrete_sequence=["#ff4444", "#ffaa00", "#44ff44"])
        fig_b3.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_b3, width='stretch')
    with col_b4:
        st.markdown("**Pipeline Pressure Index**")
        press = bottleneck_df[["Date", "PressureIndex"]].dropna()
        fig_press = go.Figure()
        fig_press.add_trace(go.Scatter(x=press["Date"], y=press["PressureIndex"], mode="lines",
                                        name="Pressure Index", line=dict(color="#ff6b6b", width=2)))
        fig_press.add_hline(y=1, line_dash="dash", line_color="#44ff44", annotation_text="Balanced")
        fig_press.add_hline(y=1.5, line_dash="dash", line_color="#ff4444", annotation_text="Critical")
        fig_press.update_layout(height=300, hovermode="x unified")
        st.plotly_chart(fig_press, width='stretch')

    severe = an.get_critical_bottlenecks(bottleneck_df)
    if len(severe) > 0:
        st.markdown("**Critical Bottleneck Dates (Inflow >> Discharge Capacity)**")
        st.dataframe(severe, width='stretch', hide_index=True)

    st.markdown("**Prolonged Stagnation Periods (Discharges < 50% of Normal for 5+ Days)**")
    stagnant = an.get_prolonged_stagnation(df_filt, min_days=5)
    if len(stagnant) > 0:
        st.dataframe(stagnant.head(10).rename(columns={
            "start": "Start", "end": "End", "days": "Duration", "avg_discharge": "Avg Discharge"
        }), width='stretch', hide_index=True)
    else:
        st.markdown("None detected.")

with tabs[3]:
    st.subheader("Outcome Trend & Stability Analysis")
    st.markdown("Evaluating consistency and trends in placement outcomes.")

    outcome_df = an.get_outcome_trends(df_filt)
    fig_o1 = go.Figure()
    fig_o1.add_trace(go.Scatter(x=outcome_df["Date"], y=outcome_df["Discharges"], mode="markers",
                                 name="Daily Discharges", marker=dict(color="#00d4aa", size=4, opacity=0.5)))
    fig_o1.add_trace(go.Scatter(x=outcome_df["Date"], y=outcome_df["DischargeMA7"], mode="lines",
                                 name="7-Day MA", line=dict(color="#f9ca24", width=2)))
    fig_o1.add_trace(go.Scatter(x=outcome_df["Date"], y=outcome_df["DischargeMA30"], mode="lines",
                                 name="30-Day MA", line=dict(color="#6c5ce7", width=2)))
    fig_o1.update_layout(title="Discharge Trend with Moving Averages", height=400,
                         hovermode="x unified", legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig_o1, width='stretch')

    col_o1, col_o2 = st.columns(2)
    with col_o1:
        fig_o2 = px.bar(outcome_df, x="Date", y="DischargeStd14",
                        title="14-Day Rolling Std Dev (Volatility)",
                        color_discrete_sequence=["#6c5ce7"])
        fig_o2.update_traces(marker=dict(color="#6c5ce7"))
        fig_o2.update_layout(height=300, hovermode="x unified")
        st.plotly_chart(fig_o2, width='stretch')
    with col_o2:
        outlier_df = an.detect_outlier_days(df_filt)
        outlier_color = ["#ff4444" if abs(v) > 2 else "#00d4aa"
                         for v in outlier_df["DischargeZ"].fillna(0)]
        fig_o3 = go.Figure()
        fig_o3.add_trace(go.Bar(x=outlier_df["Date"], y=outlier_df["DischargeZ"].fillna(0),
                                 marker_color=outlier_color, name="Z-Score"))
        fig_o3.add_hline(y=2, line_dash="dash", line_color="#ff4444")
        fig_o3.add_hline(y=-2, line_dash="dash", line_color="#ff4444")
        fig_o3.update_layout(title="Discharge Anomaly Detection (|z|>2 = outlier)", height=300,
                             hovermode="x unified", yaxis_title="Z-Score")
        st.plotly_chart(fig_o3, width='stretch')

    st.markdown("**Outcome Stability by Month**")
    monthly_stab = an.get_stability_summary(df_filt)
    fig_o4 = go.Figure()
    fig_o4.add_trace(go.Scatter(x=monthly_stab["Label"], y=monthly_stab["cv"] * 100,
                                 mode="lines+markers",
                                 name="CV % (Lower = More Stable)",
                                 line=dict(color="#00d4aa", width=2), marker=dict(size=6)))
    fig_o4.update_layout(height=300, xaxis_tickangle=-45,
                         yaxis_title="Coefficient of Variation (%)", hovermode="x unified")
    st.plotly_chart(fig_o4, width='stretch')

    st.markdown("**Recent Outlier Events**")
    outliers = an.get_outlier_summary(df_filt)
    if len(outliers) > 0:
        st.dataframe(outliers.head(15), width='stretch', hide_index=True)

with tabs[4]:
    st.subheader("Advanced Analytics")

    col_aa1, col_aa2, col_aa3, col_aa4 = st.columns(4)
    with col_aa1:
        loc = an.estimate_length_of_care(df_filt)
        st.markdown(f"""<div class="kpi-card"><div class="kpi-value" style="font-size:1.4rem">{loc['est_cbp_days']}d</div><div class="kpi-label">Est. CBP Stay</div></div>""", unsafe_allow_html=True)
    with col_aa2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-value" style="font-size:1.4rem">{loc['est_hhs_days']}d</div><div class="kpi-label">Est. HHS Stay</div></div>""", unsafe_allow_html=True)
    with col_aa3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-value" style="font-size:1.4rem">{loc['est_total_days']}d</div><div class="kpi-label">Est. Total Stay</div></div>""", unsafe_allow_html=True)
    with col_aa4:
        fc = an.forecast_summary(df_filt)
        arrow = "\u2191" if fc["trend_dir"] == "increasing" else ("\u2193" if fc["trend_dir"] == "decreasing" else "\u2192")
        st.markdown(f"""<div class="kpi-card"><div class="kpi-value" style="font-size:1.4rem">{arrow} {fc['trend_dir']}</div><div class="kpi-label">Discharge Forecast</div><div class="kpi-sub">avg {fc['avg_pred']:.0f}/day</div></div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Correlation Analysis**")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        corr = an.get_correlation_matrix(df_filt)
        fig_corr = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                             title="Pipeline Stage Correlations", aspect="auto")
        fig_corr.update_layout(height=400)
        st.plotly_chart(fig_corr, width='stretch')
    with col_c2:
        eff_corr = an.get_efficiency_correlations(df_filt)
        fig_ecorr = px.imshow(eff_corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                               title="Efficiency Metrics Correlation", aspect="auto")
        fig_ecorr.update_layout(height=400)
        st.plotly_chart(fig_ecorr, width='stretch')

    st.markdown("**Year-over-Year Comparison**")
    yoy = an.get_yearly_comparison(df_filt)
    fig_yoy = go.Figure()
    fig_yoy.add_trace(go.Bar(name="Total Inflow", x=yoy["Year"].astype(str), y=yoy["inflow"],
                             marker_color="#ff6b6b"))
    fig_yoy.add_trace(go.Bar(name="Total Discharges", x=yoy["Year"].astype(str), y=yoy["discharges"],
                             marker_color="#00d4aa"))
    fig_yoy.add_trace(go.Scatter(name="Avg TER", x=yoy["Year"].astype(str), y=yoy["avg_ter"] * 100,
                                  mode="lines+markers", yaxis="y2", line=dict(color="#f9ca24", width=2)))
    fig_yoy.update_layout(height=380, yaxis_title="Count", yaxis2=dict(overlaying="y", side="right",
                           title="TER (%)"), legend=dict(orientation="h", y=-0.15),
                           barmode="group")
    st.plotly_chart(fig_yoy, width='stretch')

    st.markdown("**Quarterly Trends**")
    qt = an.get_quarterly_trends(df_filt)
    fig_qt = go.Figure()
    fig_qt.add_trace(go.Bar(name="Inflow", x=qt["YearQuarter"], y=qt["inflow"],
                            marker_color="#ff6b6b"))
    fig_qt.add_trace(go.Bar(name="Discharges", x=qt["YearQuarter"], y=qt["discharges"],
                            marker_color="#00d4aa"))
    fig_qt.add_trace(go.Scatter(name="Avg DEI", x=qt["YearQuarter"], y=qt["avg_dei"] * 100,
                                mode="lines+markers", yaxis="y2", line=dict(color="#f9ca24", width=2)))
    fig_qt.update_layout(height=380, yaxis_title="Count",
                         yaxis2=dict(overlaying="y", side="right", title="DEI (%)"),
                         legend=dict(orientation="h", y=-0.15), barmode="group")
    st.plotly_chart(fig_qt, width='stretch')

    st.markdown("**Efficiency Ratio Distributions**")
    dists = an.get_efficiency_distributions(df_filt)
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        fig_d1 = px.histogram(dists["TER"], nbins=30, title="TER Distribution",
                              color_discrete_sequence=["#00d4aa"])
        fig_d1.add_vline(x=dists["TER"].median(), line_dash="dash", line_color="white",
                         annotation_text=f"med={dists['TER'].median():.2f}")
        fig_d1.update_layout(height=250, showlegend=False)
        st.plotly_chart(fig_d1, width='stretch')
    with col_d2:
        fig_d2 = px.histogram(dists["DEI"], nbins=30, title="DEI Distribution",
                              color_discrete_sequence=["#f9ca24"])
        fig_d2.add_vline(x=dists["DEI"].median(), line_dash="dash", line_color="white",
                         annotation_text=f"med={dists['DEI'].median():.4f}")
        fig_d2.update_layout(height=250, showlegend=False)
        st.plotly_chart(fig_d2, width='stretch')
    with col_d3:
        fig_d3 = px.histogram(dists["PTR"], nbins=30, title="PTR Distribution",
                              color_discrete_sequence=["#6c5ce7"])
        fig_d3.add_vline(x=dists["PTR"].median(), line_dash="dash", line_color="white",
                         annotation_text=f"med={dists['PTR'].median():.2f}")
        fig_d3.update_layout(height=250, showlegend=False)
        st.plotly_chart(fig_d3, width='stretch')

with tabs[5]:
    st.subheader("Data Explorer")
    st.markdown("Raw dataset and summary statistics for the selected date range.")

    display_cols = ["Date"] + an.COLUMNS
    show_cols = [c for c in display_cols if c in df_filt.columns]
    st.dataframe(df_filt[show_cols], width='stretch', hide_index=True)

    st.markdown("**Summary Statistics**")
    stats = an.get_summary_stats(df_filt)
    st.dataframe(stats.style.format("{:.1f}"), width='stretch')

    csv_data = an.get_filtered_csv(df_filt)
    st.download_button("Download Filtered Data (CSV)", data=csv_data,
                       file_name="uac_pipeline_data.csv", mime="text/csv")

st.sidebar.markdown("---")
st.sidebar.markdown("**Data Source:** HHS Unaccompanied Alien Children Program")
st.sidebar.markdown(f"**Records:** {len(df_filt):,}")
st.sidebar.markdown(f"**Range:** {df_filt['Date'].min().date()} to {df_filt['Date'].max().date()}")
st.sidebar.markdown(f"**Total Inflow:** {insights['total_inflow']:,}")
st.sidebar.markdown(f"**Total Discharged:** {insights['total_discharges']:,}")
st.sidebar.markdown("---")
st.sidebar.markdown("*Analytics Engine → analytics.py  |  UI Layer → app.py*")

"""
analytics.py — Machine Learning & Analytics Core
Care Transition Efficiency & Placement Outcome Analytics
"""
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.linear_model import LinearRegression

DATA_PATH = "data/HHS_Unaccompanied_Alien_Children_Program.csv"

SHORT = "Children apprehended and placed in CBP custody*"
CBP = "Children in CBP custody"
TRANSFER = "Children transferred out of CBP custody"
HHS = "Children in HHS Care"
DISCHARGE = "Children discharged from HHS Care"

COLUMNS = [SHORT, CBP, TRANSFER, HHS, DISCHARGE]
SHORT_LABELS = ["Apprehended", "CBP_Custody", "Transferred", "HHS_Care", "Discharged"]

# ─────────────────────────── Data Layer ───────────────────────────

def load_data(path=DATA_PATH):
    df = pd.read_csv(path)
    df = df.dropna(how="all")
    df["Date"] = pd.to_datetime(df["Date"])
    for col in df.columns:
        if col != "Date":
            df[col] = df[col].astype(str).str.replace(",", "").str.replace('"', "").astype(float)
    df = df.sort_values("Date").reset_index(drop=True)
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["MonthName"] = df["Date"].dt.strftime("%b")
    df["Weekday"] = df["Date"].dt.day_name()
    df["WeekdayNum"] = df["Date"].dt.weekday
    df["IsWeekend"] = df["Weekday"].isin(["Saturday", "Sunday"])
    df["Quarter"] = df["Date"].dt.quarter
    df["YearQuarter"] = df["Year"].astype(str) + "-Q" + df["Quarter"].astype(str)
    df["DayOfYear"] = df["Date"].dt.dayofyear
    df["MonthYear"] = df["Date"].dt.to_period("M").astype(str)
    return df

def filter_by_date(df, start_date, end_date):
    mask = (df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))
    return df[mask].copy()

# ─────────────────────────── Feature Engineering ───────────────────────────

def enrich(df):
    d = df.copy()
    d["TER"] = d[TRANSFER] / d[CBP].replace(0, np.nan)
    d["DEI"] = d[DISCHARGE] / d[HHS].replace(0, np.nan)
    d["PTR"] = d[DISCHARGE] / d[SHORT].replace(0, np.nan)
    d["BacklogNet"] = d[SHORT] - d[DISCHARGE]
    d["Inflow"] = d[SHORT]
    d["Discharges"] = d[DISCHARGE]
    d["CBPtoHHS"] = d[TRANSFER]
    d["HHSChange"] = d[HHS].diff()
    d["CBPChange"] = d[CBP].diff()
    d["DischargeToTransfer"] = d[DISCHARGE] / d[TRANSFER].replace(0, np.nan)
    d["CBPHHSRatio"] = d[CBP] / d[HHS].replace(0, np.nan)
    return d

# ─────────────────────────── KPI Calculation ───────────────────────────

def compute_kpis(df):
    d = enrich(df)
    kpis = {}
    kpis["TER"] = d["TER"].iloc[-1] if len(d) > 0 else 0.0
    kpis["DEI"] = d["DEI"].iloc[-1] if len(d) > 0 else 0.0
    kpis["PTR"] = d["PTR"].iloc[-1] if len(d) > 0 else 0.0
    kpis["BacklogNet"] = d["BacklogNet"].iloc[-1] if len(d) > 0 else 0.0
    stability = d["Discharges"].rolling(14).std().mean()
    kpis["StabilityScore"] = 0.0 if pd.isna(stability) else stability
    kpis["AvgTER"] = d["TER"].mean()
    kpis["AvgDEI"] = d["DEI"].mean()
    kpis["AvgPTR"] = d["PTR"].mean()
    kpis["TotalInflow"] = d["Inflow"].sum()
    kpis["TotalDischarge"] = d["Discharges"].sum()
    kpis["AvgHHS"] = d[HHS].mean()
    kpis["AvgCBP"] = d[CBP].mean()
    kpis["MaxHHS"] = d[HHS].max()
    kpis["MaxCBP"] = d[CBP].max()
    transfer_pct = (d["CBPtoHHS"] > 0).sum() / max(len(d), 1) * 100
    kpis["TransferActivityPct"] = transfer_pct
    return kpis

# ─────────────────────────── Trend Forecasting ───────────────────────────

def forecast_discharges(df, days_ahead=30):
    d = enrich(df)
    train = d[["Date", "Discharges"]].dropna().copy()
    train["Days"] = (train["Date"] - train["Date"].min()).dt.days
    X = train[["Days"]].values
    y = train["Discharges"].values
    if len(X) < 5:
        return pd.DataFrame()
    model = LinearRegression()
    model.fit(X, y)
    last_day = X[-1][0]
    future_days = np.array(range(last_day + 1, last_day + days_ahead + 1)).reshape(-1, 1)
    preds = model.predict(future_days)
    future_dates = pd.date_range(start=d["Date"].max() + pd.Timedelta(days=1), periods=days_ahead)
    return pd.DataFrame({"Date": future_dates, "PredictedDischarges": preds, "Trend": model.coef_[0]})

def forecast_summary(df):
    fc = forecast_discharges(df)
    if len(fc) == 0:
        return {"trend_dir": "unknown", "avg_pred": 0, "trend_slope": 0}
    slope = fc["Trend"].iloc[0]
    return {
        "trend_dir": "increasing" if slope > 0.1 else ("decreasing" if slope < -0.1 else "stable"),
        "avg_pred": fc["PredictedDischarges"].mean(),
        "trend_slope": slope
    }

# ─────────────────────────── Correlation Analysis ───────────────────────────

def get_correlation_matrix(df):
    d = enrich(df)
    return d[COLUMNS].corr()

def get_efficiency_correlations(df):
    d = enrich(df)
    return d[["TER", "DEI", "PTR", "BacklogNet", "Inflow", "Discharges"]].corr()

# ─────────────────────────── Bottleneck Detection ───────────────────────────

def detect_bottlenecks(df):
    d = enrich(df)
    d["NetAccumulation"] = d["Inflow"] - d["Discharges"]
    d["CumBacklog"] = d["NetAccumulation"].cumsum()
    rolling_mean = d["NetAccumulation"].rolling(30).mean()
    rolling_std = d["NetAccumulation"].rolling(30).std()
    d["BacklogFlag"] = np.where(
        d["NetAccumulation"] > rolling_mean + rolling_std, "Critical",
        np.where(d["NetAccumulation"] > 0, "Elevated", "Normal")
    )
    d["PressureIndex"] = d["Inflow"] / d["Discharges"].rolling(7).mean().replace(0, np.nan)
    return d

def get_backlog_severity_summary(df):
    return df["BacklogFlag"].value_counts()

def get_critical_bottlenecks(df):
    return df[df["BacklogFlag"] == "Critical"][["Date", "Inflow", "Discharges", "NetAccumulation", "PressureIndex"]].head(10)

def get_prolonged_stagnation(df, min_days=7):
    d = enrich(df)
    d["Stagnant"] = (d["Discharges"] < d["Discharges"].rolling(14).mean() * 0.5).astype(int)
    d["StagnationGroup"] = (d["Stagnant"] != d["Stagnant"].shift()).cumsum()
    periods = d[d["Stagnant"] == 1].groupby("StagnationGroup").agg(
        start=("Date", "min"), end=("Date", "max"),
        days=("Date", "count"), avg_discharge=("Discharges", "mean")
    ).reset_index(drop=True)
    return periods[periods["days"] >= min_days].sort_values("days", ascending=False)

# ─────────────────────────── Efficiency Metrics ───────────────────────────

def get_efficiency_metrics(df):
    return enrich(df)[["Date", "TER", "DEI", "PTR", "DischargeToTransfer", "CBPHHSRatio"]]

def get_efficiency_distributions(df):
    d = enrich(df)
    return {
        "TER": d["TER"].dropna(),
        "DEI": d["DEI"].dropna(),
        "PTR": d["PTR"].dropna()
    }

# ─────────────────────────── Temporal Patterns ───────────────────────────

def get_weekly_pattern(df):
    d = enrich(df)
    return d.groupby("IsWeekend").agg(
        avg_inflow=(SHORT, "mean"),
        avg_transfer=(TRANSFER, "mean"),
        avg_discharge=(DISCHARGE, "mean"),
        avg_ter=("TER", "mean"),
        avg_dei=("DEI", "mean")
    ).reset_index()

def get_dayofweek_pattern(df):
    d = enrich(df)
    return d.groupby("Weekday").agg(
        avg_inflow=(SHORT, "mean"),
        avg_transfer=(TRANSFER, "mean"),
        avg_discharge=(DISCHARGE, "mean"),
        count=("Date", "count")
    ).reset_index().sort_values("count", ascending=False)

def get_monthly_trends(df):
    d = enrich(df)
    monthly = d.groupby(["Year", "Month"]).agg(
        inflow=(SHORT, "sum"),
        transfers=(TRANSFER, "sum"),
        discharges=(DISCHARGE, "sum"),
        avg_hhs=(HHS, "mean"),
        avg_cbp=(CBP, "mean"),
        avg_ter=("TER", "mean"),
        avg_dei=("DEI", "mean")
    ).reset_index()
    monthly["Label"] = monthly["Month"].apply(
        lambda m: datetime(2000, int(m), 1).strftime("%b")
    ) + " " + monthly["Year"].astype(str)
    return monthly

def get_quarterly_trends(df):
    d = enrich(df)
    return d.groupby("YearQuarter").agg(
        inflow=(SHORT, "sum"),
        transfers=(TRANSFER, "sum"),
        discharges=(DISCHARGE, "sum"),
        avg_hhs=(HHS, "mean"),
        avg_cbp=(CBP, "mean"),
        avg_ter=("TER", "mean"),
        avg_dei=("DEI", "mean")
    ).reset_index()

def get_yearly_comparison(df):
    d = enrich(df)
    return d.groupby("Year").agg(
        inflow=(SHORT, "sum"),
        transfers=(TRANSFER, "sum"),
        discharges=(DISCHARGE, "sum"),
        avg_hhs=(HHS, "mean"),
        avg_cbp=(CBP, "mean"),
        avg_ter=("TER", "mean"),
        avg_dei=("DEI", "mean"),
        days=("Date", "count")
    ).reset_index()

# ─────────────────────────── Outcome Stability ───────────────────────────

def get_outcome_trends(df):
    d = enrich(df)
    d["DischargeMA7"] = d["Discharges"].rolling(7).mean()
    d["DischargeMA30"] = d["Discharges"].rolling(30).mean()
    d["DischargeStd14"] = d["Discharges"].rolling(14).std()
    return d

def detect_outlier_days(df):
    d = get_outcome_trends(df)
    d["DischargeZ"] = (d["Discharges"] - d["DischargeMA30"]) / d["DischargeStd14"].replace(0, np.nan)
    return d

def get_monthly_stability(df):
    d = enrich(df)
    return d.groupby(["Year", "Month"]).agg(
        avg_discharge=("Discharges", "mean"),
        std_discharge=("Discharges", "std"),
        cv=("Discharges", lambda x: x.std() / x.mean() if x.mean() > 0 else 0),
        total_discharge=("Discharges", "sum")
    ).reset_index()

def get_stability_summary(df):
    monthly = get_monthly_stability(df)
    monthly["Label"] = monthly["Month"].apply(
        lambda m: datetime(2000, int(m), 1).strftime("%b")
    ) + " " + monthly["Year"].astype(str)
    return monthly

def get_outlier_summary(df):
    outliers = detect_outlier_days(df)
    severe = outliers[abs(outliers["DischargeZ"]) > 2].copy()
    severe["Type"] = np.where(severe["DischargeZ"] > 0, "Surge", "Drop")
    return severe[["Date", "Discharges", "DischargeZ", "Type"]].sort_values("Date", ascending=False)

# ─────────────────────────── Length of Care Estimation ───────────────────────────

def estimate_length_of_care(df):
    d = enrich(df)
    avg_cbp_stay = d[CBP].mean() / d[TRANSFER].replace(0, np.nan).mean() if d[TRANSFER].mean() > 0 else 0
    avg_hhs_stay = d[HHS].mean() / d[DISCHARGE].replace(0, np.nan).mean() if d[DISCHARGE].mean() > 0 else 0
    return {
        "est_cbp_days": avg_cbp_stay,
        "est_hhs_days": avg_hhs_stay,
        "est_total_days": avg_cbp_stay + avg_hhs_stay
    }

# ─────────────────────────── Alert System ───────────────────────────

def generate_alerts(kpis, threshold_pct=20, df=None):
    alerts = []
    if kpis["TER"] < 0.3:
        alerts.append(("danger", f"Transfer Efficiency Ratio critically low ({kpis['TER']:.2f}). Children remaining in CBP custody too long."))
    elif kpis["TER"] < 0.5:
        alerts.append(("warning", f"Transfer Efficiency Ratio below target ({kpis['TER']:.2f}). Monitor CBP→HHS handoff."))
    if kpis["DEI"] < 0.005:
        alerts.append(("danger", f"Discharge Effectiveness very low ({kpis['DEI']:.4f}). Sponsor placements stalled."))
    elif kpis["DEI"] < 0.01:
        alerts.append(("warning", f"Discharge Effectiveness below optimal ({kpis['DEI']:.4f})."))
    if df is not None and kpis["BacklogNet"] > threshold_pct * df[HHS].mean() / 100:
        alerts.append(("danger", f"Backlog accumulating ({kpis['BacklogNet']:.0f}). Inflow exceeds discharges by {abs(kpis['BacklogNet']):.0f}."))
    if kpis["StabilityScore"] > 50:
        alerts.append(("warning", f"Outcome stability deteriorating (σ={kpis['StabilityScore']:.1f}). Inconsistent placement performance."))
    if kpis.get("TransferActivityPct", 100) < 60:
        alerts.append(("warning", f"Low transfer activity ({kpis['TransferActivityPct']:.0f}% of days). Many days with zero CBP→HHS transfers."))
    return alerts

# ─────────────────────────── Pipeline Flow Data ───────────────────────────

def get_pipeline_flow(df):
    return enrich(df).melt(
        id_vars=["Date"],
        value_vars=COLUMNS,
        var_name="Stage", value_name="Count"
    )

def get_latest_snapshot(df):
    d = enrich(df)
    return d.iloc[-1] if len(d) > 0 else d.iloc[0]

# ─────────────────────────── Cumulative Flow ───────────────────────────

def get_cumulative_flow(df):
    d = enrich(df)
    cum = pd.DataFrame({"Date": d["Date"]})
    cum["CumInflow"] = d["Inflow"].cumsum()
    cum["CumTransfers"] = d["CBPtoHHS"].cumsum()
    cum["CumDischarges"] = d["Discharges"].cumsum()
    cum["CumGap"] = cum["CumInflow"] - cum["CumDischarges"]
    return cum

# ─────────────────────────── Delay & Bottleneck Analytics ───────────────────────────

def get_delay_metrics(df, cap_days=365):
    d = enrich(df)
    result = d.copy()
    result["CBP_Clearance_Days"] = (result[CBP] / result[TRANSFER].replace(0, np.nan)).clip(0, cap_days)
    result["HHS_Clearance_Days"] = (result[HHS] / result[DISCHARGE].replace(0, np.nan)).clip(0, cap_days)
    result["Total_Clearance_Days"] = result["CBP_Clearance_Days"] + result["HHS_Clearance_Days"]
    result["Transfer_Lag"] = np.where((result[SHORT] > 0) & (result[TRANSFER] == 0), 1, 0)
    result["Discharge_Lag"] = np.where((result[HHS] > 0) & (result[DISCHARGE] == 0), 1, 0)
    result["CBP_Efficiency"] = result[TRANSFER] / result[SHORT].replace(0, np.nan)
    result["HHS_Clearance_Rate"] = result[DISCHARGE] / result[HHS].replace(0, np.nan)
    return result

def get_bottleneck_score(df):
    d = get_delay_metrics(df)
    score = pd.DataFrame({"Date": d["Date"]})
    cbp_ma30 = d[CBP].rolling(30).mean().replace(0, np.nan)
    hhs_ma30 = d[HHS].rolling(30).mean().replace(0, np.nan)
    transfer_ma7 = d[TRANSFER].rolling(7).mean().replace(0, np.nan)
    discharge_ma7 = d[DISCHARGE].rolling(7).mean().replace(0, np.nan)
    score["CBP_Pressure"] = (d[CBP] / cbp_ma30).clip(0, 5).fillna(1)
    score["HHS_Pressure"] = (d[HHS] / hhs_ma30).clip(0, 5).fillna(1)
    score["Transfer_Stress"] = (d[SHORT] / transfer_ma7).clip(0, 5).fillna(1)
    score["Discharge_Stress"] = (d[HHS] / discharge_ma7).clip(0, 5).fillna(1)
    score["BottleneckScore"] = (
        score["CBP_Pressure"] * 0.25 +
        score["HHS_Pressure"] * 0.25 +
        score["Transfer_Stress"] * 0.25 +
        score["Discharge_Stress"] * 0.25
    )
    score["Severity"] = pd.cut(score["BottleneckScore"],
                                bins=[0, 0.8, 1.2, 1.5, 100],
                                labels=["Low", "Moderate", "High", "Critical"])
    return score

def get_transfer_lag_streaks(df):
    d = get_delay_metrics(df)
    d["LagGroup"] = (d["Transfer_Lag"] != d["Transfer_Lag"].shift()).cumsum()
    streaks = d[d["Transfer_Lag"] == 1].groupby("LagGroup").agg(
        start=("Date", "min"), end=("Date", "max"),
        days=("Date", "count"), avg_cbp=("Children in CBP custody", "mean"),
        avg_inflow=("Children apprehended and placed in CBP custody*", "mean")
    ).reset_index(drop=True)
    return streaks.sort_values("days", ascending=False)

def get_discharge_lag_streaks(df):
    d = get_delay_metrics(df)
    d["LagGroup"] = (d["Discharge_Lag"] != d["Discharge_Lag"].shift()).cumsum()
    streaks = d[d["Discharge_Lag"] == 1].groupby("LagGroup").agg(
        start=("Date", "min"), end=("Date", "max"),
        days=("Date", "count"), avg_hhs=("Children in HHS Care", "mean")
    ).reset_index(drop=True)
    return streaks.sort_values("days", ascending=False)

def get_sankey_data(df):
    d = enrich(df)
    total_inflow = int(d[SHORT].sum())
    total_transfers = int(d[TRANSFER].sum())
    total_discharges = int(d[DISCHARGE].sum())
    avg_cbp = int(d[CBP].mean())
    avg_hhs = int(d[HHS].mean())
    cbp_residual = max(0, total_inflow - total_transfers)
    hhs_residual = max(0, total_transfers - total_discharges)
    return {
        "labels": ["Apprehended", "CBP Custody", "Transferred to HHS", "HHS Care", "Discharged to Sponsor", "In Pipeline"],
        "source": [0, 1, 2, 3],
        "target": [1, 2, 3, 4],
        "value": [total_inflow, total_transfers, total_transfers, total_discharges]
    }

def get_delay_heatmap(df):
    d = get_delay_metrics(df)
    d["WeekdayNum"] = d["Date"].dt.weekday
    heat = d.groupby(["Year", "Month", "WeekdayNum"]).agg(
        avg_stay=("Total_Clearance_Days", "mean"),
        avg_cbp_stay=("CBP_Clearance_Days", "mean"),
        avg_hhs_stay=("HHS_Clearance_Days", "mean"),
        transfer_lag_pct=("Transfer_Lag", "mean"),
        discharge_lag_pct=("Discharge_Lag", "mean")
    ).reset_index()
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    heat["DayLabel"] = heat["WeekdayNum"].map({i: n for i, n in enumerate(day_names)})
    return heat

def get_weekday_delay_pattern(df):
    d = get_delay_metrics(df)
    return d.groupby("Weekday").agg(
        avg_transfer=("Children transferred out of CBP custody", "mean"),
        avg_discharge=("Children discharged from HHS Care", "mean"),
        transfer_lag_pct=("Transfer_Lag", "mean"),
        discharge_lag_pct=("Discharge_Lag", "mean"),
        avg_cbp_stay=("CBP_Clearance_Days", "mean"),
        avg_hhs_stay=("HHS_Clearance_Days", "mean"),
        count=("Date", "count")
    ).reset_index()

def get_delay_timeline(df):
    d = get_delay_metrics(df)
    timeline = pd.DataFrame({"Date": d["Date"]})
    timeline["CBP_Stay"] = d["CBP_Clearance_Days"]
    timeline["HHS_Stay"] = d["HHS_Clearance_Days"]
    timeline["Total_Stay"] = d["Total_Clearance_Days"]
    timeline["Active_Bottleneck"] = np.where(
        (d["Transfer_Lag"] == 1) | (d["Discharge_Lag"] == 1), "Yes", "No"
    )
    timeline["Delay_Type"] = np.where(
        d["Transfer_Lag"] == 1, "Transfer Halt",
        np.where(d["Discharge_Lag"] == 1, "Discharge Halt", "Normal")
    )
    return timeline

def get_sustained_imbalance_periods(df, min_days=5):
    d = enrich(df)
    d["Imbalance"] = (d["BacklogNet"] > d["BacklogNet"].rolling(14).mean() + d["BacklogNet"].rolling(14).std()).astype(int)
    d["ImbalanceGroup"] = (d["Imbalance"] != d["Imbalance"].shift()).cumsum()
    periods = d[d["Imbalance"] == 1].groupby("ImbalanceGroup").agg(
        start=("Date", "min"), end=("Date", "max"),
        days=("Date", "count"),
        avg_imbalance=("BacklogNet", "mean"),
        peak_imbalance=("BacklogNet", "max"),
        total_excess_inflow=("BacklogNet", "sum")
    ).reset_index(drop=True)
    return periods[periods["days"] >= min_days].sort_values("days", ascending=False)

def get_delay_summary_stats(df):
    d = get_delay_metrics(df)
    return {
        "avg_cbp_days": round(d["CBP_Clearance_Days"].mean(), 1),
        "avg_hhs_days": round(d["HHS_Clearance_Days"].mean(), 1),
        "avg_total_days": round(d["Total_Clearance_Days"].mean(), 1),
        "max_cbp_days": round(d["CBP_Clearance_Days"].max(), 1),
        "max_hhs_days": round(d["HHS_Clearance_Days"].max(), 1),
        "transfer_lag_days": int(d["Transfer_Lag"].sum()),
        "discharge_lag_days": int(d["Discharge_Lag"].sum()),
        "transfer_lag_pct": round(d["Transfer_Lag"].mean() * 100, 1),
        "discharge_lag_pct": round(d["Discharge_Lag"].mean() * 100, 1),
        "avg_cbp_efficiency": round(d["CBP_Efficiency"].mean(), 3),
        "avg_hhs_clearance": round(d["HHS_Clearance_Rate"].mean(), 4)
    }

# ─────────────────────────── Summary Stats ───────────────────────────

def get_summary_stats(df):
    display_cols = COLUMNS
    stats = df[display_cols].describe().T
    stats.columns = ["Count", "Mean", "Std Dev", "Min", "25%", "50%", "75%", "Max"]
    stats["Count"] = stats["Count"].astype(int)
    return stats

def get_filtered_csv(df):
    cols = ["Date"] + COLUMNS
    return df[[c for c in cols if c in df.columns]].to_csv(index=False).encode("utf-8")

# ─────────────────────────── EDA Helper ───────────────────────────

def get_eda_insights(df):
    d = enrich(df)
    insights = {}
    insights["total_records"] = len(d)
    insights["date_range"] = f"{d['Date'].min().date()} to {d['Date'].max().date()}"
    insights["total_inflow"] = int(d["Inflow"].sum())
    insights["total_discharges"] = int(d["Discharges"].sum())
    insights["net_pipeline"] = int(d["Inflow"].sum() - d["Discharges"].sum())
    insights["avg_daily_inflow"] = round(d["Inflow"].mean(), 1)
    insights["avg_daily_discharge"] = round(d["Discharges"].mean(), 1)
    insights["avg_ter"] = round(d["TER"].mean(), 3)
    insights["avg_dei"] = round(d["DEI"].mean(), 4)
    insights["avg_ptr"] = round(d["PTR"].mean(), 3)
    insights["peak_hhs"] = int(d[HHS].max())
    insights["peak_cbp"] = int(d[CBP].max())
    insights["ter_trend"] = "improving" if d["TER"].iloc[-30:].mean() > d["TER"].iloc[:30].mean() else "declining"
    insights["dei_trend"] = "improving" if d["DEI"].iloc[-30:].mean() > d["DEI"].iloc[:30].mean() else "declining"
    insights["busiest_month"] = d.groupby("MonthName")[SHORT].sum().idxmax()
    insights["quietest_month"] = d.groupby("MonthName")[SHORT].sum().idxmin()
    stagnant = get_prolonged_stagnation(d)
    insights["stagnation_periods"] = len(stagnant)
    insights["total_stagnant_days"] = int(stagnant["days"].sum()) if len(stagnant) > 0 else 0
    loc = estimate_length_of_care(d)
    insights["est_cbp_days"] = round(loc["est_cbp_days"], 1)
    insights["est_hhs_days"] = round(loc["est_hhs_days"], 1)
    insights["est_total_days"] = round(loc["est_total_days"], 1)
    weekday = get_dayofweek_pattern(d)
    insights["busiest_weekday"] = weekday.iloc[0]["Weekday"]
    weekend = get_weekly_pattern(d)
    insights["weekend_vs_weekday"] = round(weekend[weekend["IsWeekend"]]["avg_discharge"].values[0] / weekend[~weekend["IsWeekend"]]["avg_discharge"].values[0] * 100 if not weekend[~weekend["IsWeekend"]]["avg_discharge"].isna().any() else 0, 1)
    return insights

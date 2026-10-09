# -*- coding: utf-8 -*-
"""Baltic Bank | Chief Risk Officer dashboard. Data: Excel in repository root."""
from pathlib import Path
import html
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Baltic Bank | Credit Risk Management", page_icon="🏦", layout="wide", initial_sidebar_state="expanded")
ROOT = Path(__file__).resolve().parent
EXCEL_NAME = "credit_risk_test_data_baltic (3).xlsx"
COUNTRIES = {"LT": "Lithuania", "LV": "Latvia", "EE": "Estonia", "Lietuva": "Lithuania", "Latvija": "Latvia", "Estija": "Estonia", "Lithuania": "Lithuania", "Latvia": "Latvia", "Estonia": "Estonia"}
COLORS = {"Lithuania": "#1468C7", "Latvia": "#00A6A0", "Estonia": "#F4A340"}
PAGES = ["Executive Overview", "Baltic Country Risk", "Portfolio & Borrowers", "Customer Profile", "Risk Trends & Scenarios"]

st.markdown('''<style>
.stApp{background:#F7F9FC;color:#0A213C}.block-container{padding-top:1.5rem;max-width:1500px}
section[data-testid="stSidebar"]{background:linear-gradient(160deg,#0C356B,#061D3A 50%,#03162D)}
section[data-testid="stSidebar"] *{color:#F5F9FF}
section[data-testid="stSidebar"] [data-baseweb="select"] *,section[data-testid="stSidebar"] [data-baseweb="input"] *{color:#0A213C!important}
h1,h2,h3{color:#0A213C!important;letter-spacing:-.035em}
h1{font-size:2.1rem!important}h2{font-size:1.45rem!important}
[data-testid="stMetric"]{background:white;border:1px solid #E4EAF2;border-radius:16px;padding:16px 18px;box-shadow:0 4px 18px #0A27400B}
[data-testid="stMetricLabel"]{font-size:.9rem!important;color:#60758F!important} [data-testid="stMetricLabel"] p{white-space:normal!important;overflow:visible!important;text-overflow:clip!important;line-height:1.3!important}
[data-testid="stMetricValue"]{font-size:1.55rem!important;color:#0B2E57!important} [data-testid="stMetricValue"]>div{overflow:visible!important;text-overflow:clip!important;white-space:normal!important}
[data-testid="stPlotlyChart"]{background:#fff;border:1px solid #E7EDF5;border-radius:15px;padding:6px}
div[data-testid="stAlert"]{border-radius:12px}
.note{padding:13px 16px;background:#EFF5FC;border-left:3px solid #2276CE;border-radius:8px;color:#35506E;margin:5px 0 18px}
.eyebrow{font-size:.75rem;font-weight:800;letter-spacing:.14em;color:#4380BC;text-transform:uppercase}
</style>''', unsafe_allow_html=True)

@st.cache_data(show_spinner="Loading bank data...")
def load_data():
    # Read the same workbook that the previously working Lithuanian app used.
    # Streamlit Cloud checks out the repository to a local filesystem.
    path = ROOT / EXCEL_NAME
    if not path.is_file():
        raise FileNotFoundError(f"Excel workbook not found next to app.py: {path.name}")
    # A deployed Streamlit app runs inside a checkout of the GitHub repository.
    # Therefore this path is already the GitHub-tracked file, not a user upload.
    from zipfile import is_zipfile
    if not is_zipfile(path):
        header = path.read_bytes()[:120]
        if b"git-lfs.github.com/spec" in header:
            raise ValueError("GitHub contains a Git LFS pointer instead of the Excel workbook. The actual workbook must be committed to the repository.")
        raise ValueError("The GitHub-tracked file is not a valid Excel workbook. Please check the file stored in GitHub, not the file name.")
    with pd.ExcelFile(path, engine="openpyxl") as xls:
        required = ["Customers", "Loans", "Loan_Snapshot", "Underwriting", "Customer_Financials", "Stress_Scenarios"]
        missing = [s for s in required if s not in xls.sheet_names]
        if missing:
            raise ValueError("Missing Excel worksheets: " + ", ".join(missing))
        tables = {s: pd.read_excel(xls, sheet_name=s) for s in required}
        for s in ["Payments", "Collateral", "Default_Events", "Collections", "Macro"]:
            tables[s] = pd.read_excel(xls, sheet_name=s) if s in xls.sheet_names else pd.DataFrame()
    for key in ["Loans", "Loan_Snapshot", "Customers"]:
        tables[key].columns = tables[key].columns.str.strip()
    for key, datecols in {"Loans":["Origination_Date"],"Loan_Snapshot":["Snapshot_Date"],"Customer_Financials":["Snapshot_Date"],"Payments":["Due_Date"],"Default_Events":["Default_Date"]}.items():
        for col in datecols:
            if col in tables[key].columns:
                tables[key][col] = pd.to_datetime(tables[key][col], errors="coerce")
    for key in ["Customers", "Loans", "Loan_Snapshot", "Underwriting"]:
        if "Country" in tables[key].columns:
            tables[key]["Country"] = tables[key]["Country"].map(lambda x: COUNTRIES.get(str(x).strip(), str(x).strip()))
    loans = tables["Loans"]
    snaps = tables["Loan_Snapshot"]
    needed = ["Loan_ID", "Product_Name", "Origination_Date", "Original_Amount_EUR", "Interest_Rate", "Down_Payment_Pct", "Down_Payment_EUR", "Customer_ID", "Country"]
    for col in needed:
        if col not in loans.columns:
            raise ValueError(f"Missing required Loans column: {col}")
    for col in ["Snapshot_Date", "Loan_ID", "EAD_EUR", "IFRS9_Stage", "DPD_Days", "ECL_EUR"]:
        if col not in snaps.columns:
            raise ValueError(f"Missing required Loan_Snapshot column: {col}")
    extra = loans[["Loan_ID", "Product_Name", "Origination_Date", "Original_Amount_EUR", "Interest_Rate", "Down_Payment_Pct", "Down_Payment_EUR"]].drop_duplicates("Loan_ID")
    snaps = snaps.drop(columns=[c for c in extra.columns if c != "Loan_ID" and c in snaps.columns], errors="ignore").merge(extra, on="Loan_ID", how="left", validate="many_to_one")
    for col in ["EAD_EUR", "ECL_EUR", "DPD_Days", "IFRS9_Stage", "PD_12M", "LGD", "Current_LTV"]:
        if col in snaps.columns:
            snaps[col] = pd.to_numeric(snaps[col], errors="coerce")
    snaps["Country"] = snaps["Country"].map(lambda x: COUNTRIES.get(str(x).strip(), str(x).strip()))
    snaps["Month"] = snaps["Snapshot_Date"].dt.to_period("M").dt.to_timestamp()
    snaps["Problem_EAD"] = np.where(snaps["IFRS9_Stage"].eq(3), snaps["EAD_EUR"], 0)
    snaps["Elevated_EAD"] = np.where(snaps["IFRS9_Stage"].eq(2), snaps["EAD_EUR"], 0)
    snaps["Late90_EAD"] = np.where(snaps["DPD_Days"].ge(90), snaps["EAD_EUR"], 0)
    tables["Loan_Snapshot"] = snaps
    return tables

try:
    D = load_data()
except Exception as exc:
    st.error("Unable to load Excel data from GitHub.")
    st.code(str(exc))
    st.info(f"Expected GitHub repository file: {EXCEL_NAME} (in the same directory as app.py).")
    st.stop()

S = D["Loan_Snapshot"]
LOANS = D["Loans"]
CUSTOMERS = D["Customers"]
LATEST_DATE = S["Snapshot_Date"].dropna().max()
if pd.isna(LATEST_DATE):
    st.error("No valid dates found in monthly loan data.")
    st.stop()

with st.sidebar:
    st.markdown("## ◈ BALTIC BANK")
    st.caption("CHIEF RISK OFFICER · MANAGEMENT REPORT")
    page = st.radio("Report section", PAGES, label_visibility="collapsed")
    st.divider()
    selected_countries = st.multiselect("Countries", ["Lithuania", "Latvia", "Estonia"], default=["Lithuania", "Latvia", "Estonia"])
    st.caption("Synthetic demonstration data; not actual bank reporting.")
    st.caption(f"Reporting date: {LATEST_DATE:%Y-%m-%d}")
if not selected_countries:
    st.warning("Select at least one country.")
    st.stop()

S = S[S["Country"].isin(selected_countries)].copy()
LOANS = LOANS[LOANS["Country"].isin(selected_countries)].copy()
CUSTOMERS = CUSTOMERS[CUSTOMERS["Country"].isin(selected_countries)].copy()
latest = S[S["Snapshot_Date"].eq(LATEST_DATE)].copy()
if latest.empty:
    st.warning("No observations for selected countries at the latest reporting date.")
    st.stop()

fmt_eur = lambda x: f"€{x/1e9:,.2f}bn" if abs(x)>=1e9 else (f"€{x/1e6:,.2f}m" if abs(x)>=1e6 else f"€{x:,.0f}")
fmt_pct = lambda x: f"{100*x:.1f} %" if pd.notna(x) else "–"
ratio = lambda a,b: float(a/b) if b else 0.0

def title(text, subtitle):
    st.markdown('<div class="eyebrow">Baltic Bank / Risk intelligence</div>', unsafe_allow_html=True)
    st.title(text)
    st.caption(subtitle)

def section(text, expl):
    st.subheader(text)
    st.markdown(f'<div class="note">{html.escape(expl)}</div>', unsafe_allow_html=True)

def plot(fig, height=350, percent=False):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=20,r=20,t=45,b=30), font=dict(family="Arial",size=12,color="#244260"), title_font=dict(size=16,color="#0B2E57"), legend_title_text="", paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E9EFF6")
    if percent: fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

def country_table(df):
    if df.empty: return pd.DataFrame()
    g = df.groupby("Country", as_index=False).agg(Exposure=("EAD_EUR","sum"),Problem=("Problem_EAD","sum"),Elevated=("Elevated_EAD","sum"),Late90=("Late90_EAD","sum"),Loss=("ECL_EUR","sum"),Loans=("Loan_ID","nunique"))
    g["Non-performing loans"] = g["Problem"] / g["Exposure"].replace(0,np.nan)
    g["Loans with increased credit risk"] = g["Elevated"] / g["Exposure"].replace(0,np.nan)
    g["At least 90 days past due"] = g["Late90"] / g["Exposure"].replace(0,np.nan)
    return g

def kpis(df):
    exposure=df["EAD_EUR"].sum(); problem=df["Problem_EAD"].sum(); elevated=df["Elevated_EAD"].sum(); late=df["Late90_EAD"].sum(); loss=df["ECL_EUR"].sum()
    metrics = list(zip(["Loan portfolio", "Non-performing loans", "Loans with increased credit risk", "Loans at least 90 days past due", "Expected credit losses"], [fmt_eur(exposure),fmt_pct(ratio(problem,exposure)),fmt_pct(ratio(elevated,exposure)),fmt_pct(ratio(late,exposure)),fmt_eur(loss)]))
    first = st.columns(3, gap="medium")
    second = st.columns(3, gap="medium")
    for col, (label, value) in zip(first + second, metrics):
        col.metric(label, value)

def monthly(df):
    g=df.groupby("Month",as_index=False)[["EAD_EUR","Problem_EAD","Elevated_EAD","Late90_EAD","ECL_EUR"]].sum().sort_values("Month")
    for num,name in [("Problem_EAD","Non-performing"),("Elevated_EAD","Increased credit risk"),("Late90_EAD","90+ days past due")]:
        g[name]=g[num]/g["EAD_EUR"].replace(0,np.nan)
    return g

if page == "Executive Overview":
    title("Credit Risk | Executive Overview", "Consolidated credit risk report for one Baltic bank: emerging deterioration, concentrations and management priorities.")
    kpis(latest)
    m=monthly(S)
    section("Is credit quality deteriorating?", "The lines show the exposure-weighted share of non-performing loans, increased-risk loans and loans at least 90 days past due. An upward trend signals deterioration.")
    long=m.melt(id_vars="Month",value_vars=["Non-performing","Increased credit risk","90+ days past due"],var_name="Indicator",value_name="Share")
    plot(px.line(long,x="Month",y="Share",color="Indicator",markers=True,title="Monthly credit quality trends"),percent=True)
    g=country_table(latest)
    a,b=st.columns(2)
    with a:
        section("Which country has the largest loan exposure?", "Outstanding exposure, rather than number of loans, reveals geographic concentration.")
        plot(px.bar(g,x="Country",y="Exposure",color="Country",color_discrete_map=COLORS,title="Loan exposure by country (EUR)"))
    with b:
        section("Which country has the highest non-performing loan ratio?", "Non-performing exposure divided by each country’s total exposure enables comparison across different-sized portfolios.")
        plot(px.bar(g,x="Country",y="Non-performing loans",color="Country",color_discrete_map=COLORS,title="Non-performing loan ratio"),percent=True)
    section("Where should management focus?", "The largest problematic exposures are monitoring priorities, not automated lending decisions.")
    risk=latest.sort_values(["Problem_EAD","ECL_EUR"],ascending=False).head(15)
    st.dataframe(risk[["Loan_ID","Country","Product_Name","EAD_EUR","DPD_Days","ECL_EUR"]].rename(columns={"Loan_ID":"Loan","Country":"Country","Product_Name":"Product","EAD_EUR":"Credit exposure (EUR)","DPD_Days":"Days past due","ECL_EUR":"Expected credit loss (EUR)"}),use_container_width=True,hide_index=True)

elif page == "Baltic Country Risk":
    title("Baltic Country Risk Comparison", "Lithuania, Latvia and Estonia: exposure, credit quality and monthly trends.")
    g=country_table(latest)
    st.dataframe(g[["Country","Exposure","Loans","Non-performing loans","Loans with increased credit risk","At least 90 days past due","Loss"]].rename(columns={"Country":"Country","Exposure":"Outstanding loans (EUR)","Loans":"Number of loans","Loss":"Expected credit loss (EUR)"}).style.format({"Outstanding loans (EUR)":"{:,.0f}","Expected credit loss (EUR)":"{:,.0f}","Non-performing loans":"{:.1%}","Loans with increased credit risk":"{:.1%}","At least 90 days past due":"{:.1%}"}),use_container_width=True,hide_index=True)
    a,b=st.columns(2)
    with a:
        section("How is the portfolio distributed?", "Each country’s share of the selected bank portfolio.")
        plot(px.pie(g,names="Country",values="Exposure",hole=.55,color="Country",color_discrete_map=COLORS,title="Loan portfolio distribution"))
    with b:
        section("Which country has the highest credit risk?", "This chart compares non-performing loans and loans with increased credit risk as shares of country exposure.")
        q=g.melt(id_vars="Country",value_vars=["Non-performing loans","Loans with increased credit risk"],var_name="Risk category",value_name="Share")
        plot(px.bar(q,x="Country",y="Share",color="Risk category",barmode="group",title="Credit quality by country"),percent=True)
    section("How is the non-performing loan ratio changing by country?", "Each monthly ratio is calculated as non-performing exposure divided by total country exposure.")
    c=S.groupby(["Month","Country"],as_index=False)[["EAD_EUR","Problem_EAD"]].sum()
    c["Share"]=c["Problem_EAD"]/c["EAD_EUR"].replace(0,np.nan)
    plot(px.line(c,x="Month",y="Share",color="Country",color_discrete_map=COLORS,markers=True,title="Non-performing loan ratio by country"),percent=True)
    section("Which country-product combinations carry the most risk?", "Non-performing exposure shows the absolute amount of credit at risk.")
    p=latest.groupby(["Country","Product_Name"],as_index=False)[["EAD_EUR","Problem_EAD"]].sum()
    p["Share"]=p["Problem_EAD"]/p["EAD_EUR"].replace(0,np.nan)
    plot(px.bar(p,x="Product_Name",y="Problem_EAD",color="Country",barmode="group",color_discrete_map=COLORS,title="Non-performing exposure by product and country"),420)

elif page == "Portfolio & Borrowers":
    title("Portfolio & Borrower Insights", "Who borrows, when, how much and with what equity contribution.")
    section("When are most loans originated?", "New loans are counted by origination month, not repeated monthly outstanding balances.")
    l=LOANS.copy();l["Month"]=pd.to_datetime(l["Origination_Date"],errors="coerce").dt.to_period("M").dt.to_timestamp()
    orig=l.groupby(["Month","Country"],as_index=False).agg(Count=("Loan_ID","nunique"),Amount=("Original_Amount_EUR","sum"))
    plot(px.bar(orig,x="Month",y="Count",color="Country",color_discrete_map=COLORS,barmode="group",title="Monthly new loan originations"),410)
    a,b=st.columns(2)
    with a:
        section("What is the age distribution of borrowers?", "Unique borrowers are counted once, even if they hold several loans.")
        cs=CUSTOMERS.copy();cs["Age group"]=pd.cut(pd.to_numeric(cs["Age"],errors="coerce"),bins=[0,24,34,44,54,64,120],labels=["Under 25","25–34","35–44","45–54","55–64","65+"])
        ag=cs.groupby("Age group",observed=True).size().reset_index(name="Customers")
        plot(px.bar(ag,x="Age group",y="Customers",title="Borrower age distribution"))
    with b:
        section("What is the borrower gender distribution?", "This describes borrower composition, not creditworthiness. Gender must not be used for discriminatory credit decisions.")
        gender_en = {"Moteris":"Female", "Vyras":"Male", "moteris":"Female", "vyras":"Male", "Female":"Female", "Male":"Male", "F":"Female", "M":"Male"}
        sex=CUSTOMERS["Gender"].fillna("Not specified").astype(str).str.strip().replace(gender_en).value_counts().reset_index();sex.columns=["Gender","Customers"]
        plot(px.pie(sex,names="Gender",values="Customers",hole=.55,title="Borrower distribution"))
    section("How much equity do borrowers contribute?", "Only loans with meaningful down-payment data are included. The contribution is measured as a share of purchase price.")
    d=l.copy();d["Down_Payment_Pct"]=pd.to_numeric(d["Down_Payment_Pct"],errors="coerce")
    d=d[d["Down_Payment_Pct"].between(0,1)]
    if not d.empty:
        d["Down-payment band"]=pd.cut(d["Down_Payment_Pct"],bins=[-0.001,.10,.15,.20,.25,.30,.40,1.001],labels=["Under 10%","10–15 %","15–20 %","20–25 %","25–30 %","30–40 %","Over 40%"])
        dp=d.groupby(["Down-payment band","Country"],observed=True).size().reset_index(name="Loans")
        plot(px.bar(dp,x="Down-payment band",y="Loans",color="Country",color_discrete_map=COLORS,barmode="group",title="Down-payment distribution by country"),400)
    section("Which loan products dominate?", "Outstanding balances reveal dependence on particular products and borrower groups.")
    pr=latest.groupby("Product_Name",as_index=False)[["EAD_EUR","Problem_EAD"]].sum().sort_values("EAD_EUR",ascending=False)
    plot(px.bar(pr,x="Product_Name",y="EAD_EUR",title="Outstanding loans by product"),400)

elif page == "Customer Profile":
    title("Customer Credit Profile", "Individual loans, payment history and financial trends.")
    st.info("The dataset contains synthetic personal identifiers. Search by personal code or customer identifier.")
    search=st.text_input("Enter a personal code or customer identifier",placeholder="For example, Customer_ID or Personal_Code")
    if not search:
        st.caption("Enter an identifier to display the customer analysis.")
    else:
        match=CUSTOMERS[CUSTOMERS["Customer_ID"].astype(str).str.strip().eq(search.strip()) | CUSTOMERS["Personal_Code"].astype(str).str.strip().eq(search.strip())]
        if match.empty:
            st.warning("Customer not found in selected countries.")
        else:
            cust=match.iloc[0]; cid=cust["Customer_ID"]
            cl=latest[latest["Customer_ID"].eq(cid)].copy()
            if cl.empty:
                st.warning("Customer found, but no active loan snapshot for the latest month.")
            else:
                st.subheader(f"Customer {cid} · {cust['Country']}")
                x=st.columns(4)
                x[0].metric("Total outstanding loans",fmt_eur(cl["EAD_EUR"].sum()))
                x[1].metric("Number of loans",cl["Loan_ID"].nunique())
                x[2].metric("Maximum days past due",f"{cl['DPD_Days'].max():.0f} d.")
                x[3].metric("Expected credit loss",fmt_eur(cl["ECL_EUR"].sum()))
                st.dataframe(cl[["Loan_ID","Product_Name","EAD_EUR","DPD_Days","ECL_EUR"]].rename(columns={"Loan_ID":"Loan","Product_Name":"Product","EAD_EUR":"Outstanding balance (EUR)","DPD_Days":"Days past due","ECL_EUR":"Expected credit loss (EUR)"}),hide_index=True,use_container_width=True)
                hist=S[S["Customer_ID"].eq(cid)].groupby("Month",as_index=False)[["EAD_EUR","ECL_EUR"]].sum()
                section("How has customer debt changed?", "Outstanding balances indicate whether debt is being repaid or increasing.")
                plot(px.line(hist,x="Month",y="EAD_EUR",markers=True,title="Outstanding loan balance over time"))
                f=D["Customer_Financials"].copy();f=f[f["Customer_ID"].eq(cid)].sort_values("Snapshot_Date")
                if not f.empty:
                    section("Can the customer afford debt payments?", "Monthly income is compared with debt payments; a higher payment-to-income ratio leaves a smaller financial buffer.")
                    ff=f.melt(id_vars="Snapshot_Date",value_vars=["Monthly_Income_EUR","Debt_Service_EUR"],var_name="Indicator",value_name="EUR")
                    ff["Indicator"]=ff["Indicator"].replace({"Monthly_Income_EUR":"Monthly income","Debt_Service_EUR":"Monthly debt payments"})
                    plot(px.line(ff,x="Snapshot_Date",y="EUR",color="Indicator",title="Income and debt payments"))
                pay=D["Payments"]
                if not pay.empty and "Customer_ID" in pay.columns:
                    pay=pay[pay["Customer_ID"].eq(cid)]
                    if not pay.empty:
                        st.subheader("Payment history")
                        st.dataframe(pay.sort_values("Due_Date",ascending=False).head(30),hide_index=True,use_container_width=True)

elif page == "Risk Trends & Scenarios":
    title("Risk Trends & Stress Scenarios", "A forward-looking management view of credit quality, projected losses, lending income and resilience.")
    st.caption("All forecasts and earnings estimates below are illustrative sensitivities based on synthetic loan-level data, not regulatory forecasts or audited financial results.")

    history = monthly(S)
    current_ratio = ratio(latest["Problem_EAD"].sum(), latest["EAD_EUR"].sum())
    section("1 | How might credit quality develop over the next 12 months?", "Three transparent illustrative paths extend the latest observed non-performing loan ratio. These are scenario assumptions, not statistical forecasts.")
    forecast = []
    last_month = pd.Timestamp(LATEST_DATE).to_period("M").to_timestamp()
    for month_ahead in range(13):
        dt = last_month + pd.DateOffset(months=month_ahead)
        for name, annual_change in [("Base", -0.01), ("Adverse", 0.04), ("Severe", 0.10)]:
            forecast.append({"Month": dt, "Scenario": name, "Non-performing loan ratio": max(0, min(1, current_ratio + annual_change * month_ahead / 12))})
    fcast = pd.DataFrame(forecast)
    plot(px.line(fcast, x="Month", y="Non-performing loan ratio", color="Scenario", markers=True, title="Illustrative non-performing loan ratio paths"), 380, percent=True)

    section("2 | What happens to losses and lending income under stress?", "The interest-income estimate uses outstanding exposure multiplied by contractual interest rates. Funding and operating costs are adjustable assumptions, not actual accounting data.")
    scenarios = D["Stress_Scenarios"].copy()
    scenario_names = scenarios["Scenario"].astype(str).tolist()
    scenario = st.selectbox("Economic scenario", scenario_names, key="scenario_choice")
    scenario_row = scenarios.loc[scenarios["Scenario"].astype(str).eq(scenario)].iloc[0]
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        rate_shock = st.slider("Interest rate shock (percentage points)", -2.0, 5.0, float(scenario_row.get("EURIBOR_Shock_pp", 0)), 0.25)
    with c2:
        unemployment = st.slider("Unemployment increase (percentage points)", 0.0, 8.0, max(0.0, float(scenario_row.get("Unemployment_Shock_pp", 0))), 0.5)
    with c3:
        property_change = st.slider("Property price change (%)", -40, 10, int(round(100 * float(scenario_row.get("House_Price_Shock_pct", 0)))), 5)
    with c4:
        default_increase = st.slider("Default probability increase (%)", 0, 150, int(round(100 * (float(scenario_row.get("PD_Multiplier", 1)) - 1))), 5)
    with st.expander("Earnings assumptions (illustrative; not supplied by the workbook)"):
        funding_cost = st.slider("Annual funding cost on outstanding exposure (%)", 0.0, 8.0, 2.5, 0.25)
        operating_cost = st.slider("Annual operating cost on outstanding exposure (%)", 0.0, 5.0, 1.0, 0.25)
        repricing_share = st.slider("Share of loan exposure repricing with market rates (%)", 0, 100, 60, 5) / 100
    exposure = latest["EAD_EUR"].fillna(0).clip(lower=0)
    interest = pd.to_numeric(latest["Interest_Rate"], errors="coerce").fillna(0).clip(lower=0)
    pd_base = pd.to_numeric(latest.get("PD_12M", pd.Series(0, index=latest.index)), errors="coerce").fillna(0).clip(0,1)
    lgd_base = pd.to_numeric(latest.get("LGD", pd.Series(0, index=latest.index)), errors="coerce").fillna(0).clip(0,1)
    ltv = pd.to_numeric(latest.get("Current_LTV", pd.Series(np.nan, index=latest.index)), errors="coerce")
    # This is a sensitivity proxy; it does not claim to be a validated macro-credit model.
    macro_pd_factor = 1 + default_increase / 100 + unemployment * 0.04
    price_lgd_add = max(0, -property_change) / 100 * 0.15
    stressed_pd = (pd_base * macro_pd_factor).clip(0,1)
    stressed_lgd = (lgd_base + price_lgd_add * ltv.fillna(0).clip(0,2)).clip(0,1)
    loan_loss = exposure * stressed_pd * stressed_lgd
    base_loss = exposure * pd_base * lgd_base
    gross_interest = float((exposure * interest).sum())
    stressed_interest = float((exposure * (interest + rate_shock / 100 * repricing_share).clip(lower=0)).sum())
    annual_funding = float(exposure.sum()) * funding_cost / 100
    annual_operating = float(exposure.sum()) * operating_cost / 100
    net_interest = stressed_interest - annual_funding
    risk_income = net_interest - float(loan_loss.sum()) - annual_operating
    cols = st.columns(4)
    cols[0].metric("Projected 12-month credit loss proxy", fmt_eur(float(loan_loss.sum())))
    cols[1].metric("Estimated annual net interest income", fmt_eur(net_interest))
    cols[2].metric("Income after credit and operating costs", fmt_eur(risk_income))
    cols[3].metric("Additional loss vs baseline proxy", fmt_eur(float(loan_loss.sum()-base_loss.sum())))
    profit_df = pd.DataFrame({"Measure": ["Estimated net interest income", "Estimated credit losses", "Estimated operating costs", "Residual income proxy"], "EUR": [net_interest, -float(loan_loss.sum()), -annual_operating, risk_income]})
    plot(px.bar(profit_df, x="Measure", y="EUR", color="Measure", title="Annual earnings bridge components (EUR)"), 390)
    st.caption("The earnings proxy excludes fees, taxes, hedging, balance-sheet funding details and capital costs. Twelve-month default probability × loss given default is not equivalent to booked lifetime expected credit losses.")

    section("3 | Which products and countries contribute most to projected losses?", "Absolute losses highlight where the largest amounts are at risk; loss rates help compare portfolios of different sizes.")
    breakdown = latest[["Country", "Product_Name", "EAD_EUR"]].copy()
    breakdown["Projected loss"] = loan_loss.to_numpy()
    product_loss = breakdown.groupby("Product_Name", as_index=False)[["Projected loss", "EAD_EUR"]].sum().sort_values("Projected loss", ascending=False)
    product_loss["Loss rate"] = product_loss["Projected loss"] / product_loss["EAD_EUR"].replace(0,np.nan)
    left,right = st.columns(2)
    with left:
        plot(px.bar(product_loss, x="Product_Name", y="Projected loss", title="Projected loss by lending product"), 380)
    with right:
        country_loss = breakdown.groupby("Country", as_index=False)[["Projected loss", "EAD_EUR"]].sum()
        country_loss["Loss rate"] = country_loss["Projected loss"] / country_loss["EAD_EUR"].replace(0,np.nan)
        plot(px.bar(country_loss, x="Country", y="Loss rate", color="Country", color_discrete_map=COLORS, title="Projected loss rate by country"), 380, percent=True)
    st.dataframe(product_loss.rename(columns={"Product_Name":"Lending product", "EAD_EUR":"Outstanding exposure (EUR)", "Projected loss":"Projected loss (EUR)"}).style.format({"Outstanding exposure (EUR)":"{:,.0f}","Projected loss (EUR)":"{:,.0f}","Loss rate":"{:.2%}"}), use_container_width=True, hide_index=True)

    section("4 | Is loan growth followed by credit deterioration?", "New loan originations are compared with new non-performing exposures. They are different measures, so separate charts avoid misleading comparisons.")
    orig = LOANS.copy()
    orig["Month"] = pd.to_datetime(orig["Origination_Date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    originations = orig.groupby("Month", as_index=False)["Original_Amount_EUR"].sum().rename(columns={"Original_Amount_EUR":"New lending (EUR)"})
    ss = S.sort_values(["Loan_ID","Snapshot_Date"]).copy()
    ss["Previous stage"] = ss.groupby("Loan_ID")["IFRS9_Stage"].shift()
    inflows = ss.loc[ss["IFRS9_Stage"].eq(3) & ss["Previous stage"].notna() & ss["Previous stage"].ne(3)].groupby("Month",as_index=False)["EAD_EUR"].sum().rename(columns={"EAD_EUR":"New non-performing exposure (EUR)"})
    c1,c2 = st.columns(2)
    with c1: plot(px.bar(originations, x="Month", y="New lending (EUR)", title="Monthly new lending"), 350)
    with c2:
        if not inflows.empty: plot(px.bar(inflows, x="Month", y="New non-performing exposure (EUR)", title="Monthly inflows into non-performing status"), 350)
        else: st.info("No new non-performing transitions were observed.")
    st.caption("A causal relationship cannot be inferred from these two charts alone. Vintage analysis should compare loans at equivalent months since origination.")

    section("5 | How resilient is risk-adjusted lending income across the Baltics?", "Compare each country's annualised interest income after illustrative funding costs and scenario credit losses. This is not reported bank profitability.")
    country_income = latest[["Country", "EAD_EUR", "Interest_Rate"]].copy()
    country_income["Gross interest income"] = exposure.to_numpy() * (interest + rate_shock/100 * repricing_share).clip(lower=0).to_numpy()
    country_income["Credit loss"] = loan_loss.to_numpy()
    country_income["Funding cost"] = exposure.to_numpy() * funding_cost / 100
    country_income["Operating cost"] = exposure.to_numpy() * operating_cost / 100
    ct = country_income.groupby("Country", as_index=False)[["Gross interest income", "Credit loss", "Funding cost", "Operating cost"]].sum()
    ct["Risk-adjusted income proxy"] = ct["Gross interest income"] - ct["Funding cost"] - ct["Operating cost"] - ct["Credit loss"]
    plot(px.bar(ct, x="Country", y="Risk-adjusted income proxy", color="Country", color_discrete_map=COLORS, title="Risk-adjusted annual income proxy by country"), 370)
    st.dataframe(ct.style.format({c:"{:,.0f}" for c in ct.columns if c != "Country"}), use_container_width=True, hide_index=True)
    st.info("Management interpretation: assess whether projected credit losses are adequately compensated by lending income, identify stressed countries and products, and prioritise targeted risk actions. Scenario outcomes are sensitivity estimates, not validated forecasts.")

st.divider()
st.caption("Baltic Bank · CRO management report · Synthetic test data · Analytics demonstration only; not regulatory reporting")

from pathlib import Path
import math
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Banko kredito rizikos ataskaita",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# =========================
# Vizualinis stilius
# =========================
CSS = """
<style>
.stApp { background: #ffffff; }
.block-container { padding-top: 1.1rem; padding-left: 2rem; padding-right: 2rem; max-width: 100% !important; }
section[data-testid="stSidebar"] {
    background: radial-gradient(circle at top left, #0c356b 0%, #061d3a 35%, #03162d 100%) !important;
    min-width: 340px !important; max-width: 340px !important;
}
section[data-testid="stSidebar"] * { color: #ffffff; }
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] [data-baseweb="select"] {
    color: #061b34 !important; background: #ffffff !important;
}
.sidebar-title { font-size: 22px; font-weight: 900; margin-bottom: 8px; }
.sidebar-sub { color: #b8c9df !important; font-size: 13px; margin-bottom: 20px; }
.side-card { background: rgba(255,255,255,0.055); border: 1px solid rgba(157,190,230,.28); border-radius: 17px; padding: 16px; margin-bottom: 16px; }
.kpi { background: #ffffff; border: 1px solid #e5eaf1; border-radius: 17px; padding: 17px 18px; box-shadow: 0 8px 28px rgba(15,42,75,.07); height: 100%; }
.kpi-label { color: #6a7a90; font-size: 12px; text-transform: uppercase; font-weight: 800; letter-spacing: .04em; }
.kpi-value { color: #071a33; font-size: 27px; line-height: 1.1; font-weight: 900; margin-top: 6px; }
.kpi-sub { color: #6a7a90; font-size: 13px; margin-top: 6px; }
.kpi-red { border-top: 4px solid #d14343; }
.kpi-amber { border-top: 4px solid #e39a22; }
.kpi-green { border-top: 4px solid #14966d; }
.kpi-blue { border-top: 4px solid #1478ff; }
.question-title { font-size: 22px; font-weight: 900; color: #071a33; margin: 16px 0 4px; }
.question-sub { font-size: 14px; color: #65758b; margin-bottom: 14px; }
.note { background: #f5f8fc; border-left: 4px solid #1478ff; border-radius: 10px; padding: 10px 12px; color: #4c5c70; font-size: 13px; margin: 8px 0 16px; }
.alert { border-radius: 15px; padding: 14px 16px; margin: 9px 0; border: 1px solid #e5eaf1; background: #ffffff; }
.alert-red { border-left: 5px solid #d14343; }
.alert-amber { border-left: 5px solid #e39a22; }
.alert-green { border-left: 5px solid #14966d; }
.alert-title { font-weight: 900; color: #071a33; }
.alert-text { color: #4c5c70; font-size: 14px; line-height: 1.45; margin-top: 4px; }
.big-status { border-radius: 18px; padding: 18px 20px; border: 1px solid #e5eaf1; background:#fff; }
.big-status-red { border-left: 7px solid #d14343; }
.big-status-amber { border-left: 7px solid #e39a22; }
.big-status-green { border-left: 7px solid #14966d; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def money(v, decimals=1):
    if pd.isna(v):
        return "–"
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.{decimals}f} mln. €"
    if abs(v) >= 1_000:
        return f"{v/1_000:.{decimals}f} tūkst. €"
    return f"{v:,.0f} €".replace(",", " ")


def pct(v, decimals=1):
    if pd.isna(v):
        return "–"
    return f"{float(v)*100:.{decimals}f}%"


def num(s, default=np.nan):
    return pd.to_numeric(s, errors="coerce") if s is not None else pd.Series(dtype=float)


def q(title, subtitle):
    st.markdown(f"<div class='question-title'>{title}</div><div class='question-sub'>{subtitle}</div>", unsafe_allow_html=True)


def alert(kind, title, text):
    st.markdown(f"<div class='alert alert-{kind}'><div class='alert-title'>{title}</div><div class='alert-text'>{text}</div></div>", unsafe_allow_html=True)


def kpi(label, value, sub="", status="blue"):
    st.markdown(
        f"<div class='kpi kpi-{status}'><div class='kpi-label'>{label}</div><div class='kpi-value'>{value}</div><div class='kpi-sub'>{sub}</div></div>",
        unsafe_allow_html=True,
    )


def fig_style(fig, height=360):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=50, b=20),
        font=dict(family="Arial", color="#071a33"),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="white"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#edf1f6", zeroline=False)
    return fig


def find_data_file():
    """Look for valid loan workbooks including browser-added (3) suffixes."""
    import zipfile
    folders = [BASE_DIR, BASE_DIR / "data", BASE_DIR.parent]
    candidates = []
    for folder in folders:
        if folder.is_dir():
            candidates += list(folder.glob("*.xlsx")) + list(folder.glob("*.xlsm"))
    candidates = sorted(set(candidates), key=lambda p: (
        0 if "baltic" in p.name.lower() else 1,
        0 if "credit_risk" in p.name.lower() else 1,
        p.name.lower(),
    ))
    for path in candidates:
        try:
            if not zipfile.is_zipfile(path):
                continue
            with pd.ExcelFile(path, engine="openpyxl") as book:
                if {"Customers", "Loans", "Loan_Snapshot"}.issubset(book.sheet_names):
                    return path
        except Exception:
            pass
    return None


# Optional direct upload: does not depend on GitHub file names or folder paths.
with st.sidebar:
    st.markdown("### Duomenų šaltinis")
    uploaded_workbook = st.file_uploader(
        "Įkelti banko Excel duomenis (nebūtina, jei failas GitHub)",
        type=["xlsx", "xlsm"],
        key="bank_workbook_upload",
    )


@st.cache_data(show_spinner="Įkeliami banko duomenys...")
def read_workbook(raw_bytes):
    import io
    with pd.ExcelFile(io.BytesIO(raw_bytes), engine="openpyxl") as book:
        required = {"Customers", "Loans", "Loan_Snapshot"}
        if not required.issubset(set(book.sheet_names)):
            raise ValueError("Excel trūksta lapų: " + ", ".join(sorted(required - set(book.sheet_names))))
        return {sheet: pd.read_excel(book, sheet_name=sheet)
                for sheet in book.sheet_names if sheet not in {"README", "Data_Dictionary"}}


def load_data():
    if uploaded_workbook is not None:
        try:
            return read_workbook(uploaded_workbook.getvalue())
        except Exception as exc:
            st.error(f"Nepavyko perskaityti įkelto Excel: {exc}")
            st.stop()
    path = find_data_file()
    if path is None:
        st.error("GitHub projekte nerastas tinkamas banko Excel failas. Įkelk savo Excel kairėje esančiame laukelyje.")
        st.caption("Patikrinti failai: " + ", ".join(str(p.relative_to(BASE_DIR)) for p in BASE_DIR.rglob("*.xlsx")))
        st.stop()
    try:
        return read_workbook(path.read_bytes())
    except Exception as exc:
        st.error(f"Nepavyko atidaryti {path.name}: {exc}")
        st.stop()

D = load_data()
loans = D.get("Loans", pd.DataFrame()).copy()
snap = D.get("Loan_Snapshot", pd.DataFrame()).copy()
customers = D.get("Customers", pd.DataFrame()).copy()
financials = D.get("Customer_Financials", pd.DataFrame()).copy()
payments = D.get("Payments", pd.DataFrame()).copy()
underwriting = D.get("Underwriting", pd.DataFrame()).copy()
risk_appetite = D.get("Risk_Appetite", pd.DataFrame()).copy()
collateral = D.get("Collateral", pd.DataFrame()).copy()
loan_events = D.get("Loan_Events", pd.DataFrame()).copy()
collections = D.get("Collections", pd.DataFrame()).copy()
defaults = D.get("Default_Events", pd.DataFrame()).copy()

for df in [loans, snap, customers, financials, payments, underwriting, collateral, loan_events, collections, defaults]:
    for c in df.columns:
        if c.endswith("Date") or c in ["Snapshot_Date", "Month", "Application_Date", "Due_Date", "Payment_Date", "Default_Date", "Event_Date"]:
            df[c] = pd.to_datetime(df[c], errors="coerce")

# -------------------------
# Dabartinis portfelis
# -------------------------
if not snap.empty and "Snapshot_Date" in snap.columns:
    latest_date = snap["Snapshot_Date"].max()
    latest = snap[snap["Snapshot_Date"].eq(latest_date)].copy()
else:
    latest_date = pd.NaT
    latest = pd.DataFrame()

if not loans.empty and "Loan_ID" in loans.columns:
    latest = latest.merge(
        loans.drop_duplicates("Loan_ID"),
        on=[c for c in ["Loan_ID"] if c in latest.columns],
        how="left",
        suffixes=("", "_loan"),
    )

# Jei susijungus atsirado Country_x / Country_loan, suvienodiname
for target, candidates in {
    "Country": ["Country", "Country_loan"],
    "Product_Name": ["Product_Name", "Product_Name_loan"],
    "Customer_Segment": ["Customer_Segment", "Customer_Segment_loan"],
    "Region": ["Region", "Region_loan"],
}.items():
    if target not in latest.columns:
        for c in candidates:
            if c in latest.columns:
                latest[target] = latest[c]
                break

country_names = {"LT": "Lietuva", "LV": "Latvija", "EE": "Estija"}

# Sidebar
with st.sidebar:
    st.markdown("<div class='sidebar-title'>🏦 Kredito rizikos ataskaita</div>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-sub'>Vadovybės lygio banko kredito rizikos stebėsena</div>", unsafe_allow_html=True)
    available_countries = [c for c in ["LT", "LV", "EE"] if c in set(loans.get("Country", pd.Series(dtype=str)).dropna().astype(str))]
    if not available_countries:
        available_countries = ["LT", "LV", "EE"]
    selected = st.multiselect(
        "Šalys",
        options=available_countries,
        default=available_countries,
        format_func=lambda x: country_names.get(x, x),
    )
    search_customer = st.text_input("Kliento identifikatorius", value="")
    st.markdown("<div class='side-card'><b>Ataskaitos data</b><br><span style='color:#b8c9df'>" + (latest_date.strftime("%Y-%m-%d") if pd.notna(latest_date) else "–") + f"</span><br><br><b>Aktyvios paskolos</b><br><span style='color:#b8c9df'>{len(latest):,}</span></div>", unsafe_allow_html=True)

# Filtravimas pagal šalis
if selected:
    latest_f = latest[latest.get("Country", "").astype(str).isin(selected)].copy() if not latest.empty else latest.copy()
    loans_f = loans[loans.get("Country", "").astype(str).isin(selected)].copy() if not loans.empty else loans.copy()
    customers_f = customers[customers.get("Country", "").astype(str).isin(selected)].copy() if not customers.empty else customers.copy()
else:
    latest_f, loans_f, customers_f = latest.copy(), loans.copy(), customers.copy()

# -------------------------
# Pagalbiniai dabartiniai rodikliai
# -------------------------
def ead_share(mask):
    denom = float(num(latest_f.get("EAD_EUR")).sum()) if not latest_f.empty else 0
    return float(num(latest_f.loc[mask, "EAD_EUR"]).sum()) / denom if denom else 0


stages = num(latest_f.get("IFRS9_Stage")) if not latest_f.empty else pd.Series(dtype=float)
dpd = num(latest_f.get("DPD_Days")) if not latest_f.empty else pd.Series(dtype=float)
pd_12 = num(latest_f.get("PD_12M")) if not latest_f.empty else pd.Series(dtype=float)
ltv = num(latest_f.get("Current_LTV")) if not latest_f.empty else pd.Series(dtype=float)

portfolio_ead = float(num(latest_f.get("EAD_EUR")).sum()) if not latest_f.empty else 0
problem_share = ead_share(stages.eq(3)) if not latest_f.empty else 0
higher_risk_share = ead_share(stages.eq(2)) if not latest_f.empty else 0
late90_share = ead_share(dpd.ge(90)) if not latest_f.empty else 0
avg_pd = float(pd_12.mean()) if not pd_12.dropna().empty else 0
weighted_ltv = float((ltv * num(latest_f.get("EAD_EUR"))).sum() / portfolio_ead) if portfolio_ead else 0
ecl = float(num(latest_f.get("ECL_EUR")).sum()) if not latest_f.empty else 0

def status_high_worse(value, green, amber, red):
    if value <= green: return "ŽALIA"
    if value <= amber: return "GELTONA"
    return "RAUDONA"

# ============================================================
# PUSLAPIAI
# ============================================================
page = st.sidebar.radio(
    "Ataskaitos dalis",
    ["Vadovybės apžvalga", "Kliento profilis", "Portfelio ir kreditavimo analizė", "Kredito rizika ir scenarijai"],
)

# ============================================================
# 1. VADOVYBĖS APŽVALGA
# ============================================================
if page == "Vadovybės apžvalga":
    st.title("Vadovybės kredito rizikos apžvalga")
    st.caption(f"Ataskaitos data: {latest_date.strftime('%Y-%m-%d') if pd.notna(latest_date) else '–'} | Pasirinktos šalys: {', '.join(country_names.get(c,c) for c in selected) if selected else 'visos'}")

    cols = st.columns(5)
    with cols[0]: kpi("Paskolų portfelis", money(portfolio_ead), "dabartinis paskolų likutis", "blue")
    with cols[1]: kpi("Probleminės paskolos", pct(problem_share), money(portfolio_ead * problem_share), "red" if problem_share > .03 else "amber")
    with cols[2]: kpi("Padidėjusios rizikos paskolos", pct(higher_risk_share), money(portfolio_ead * higher_risk_share), "amber" if higher_risk_share > .06 else "green")
    with cols[3]: kpi("Daugiau kaip 90 dienų vėlavimas", pct(late90_share), money(portfolio_ead * late90_share), "red" if late90_share > .02 else "amber")
    with cols[4]: kpi("Prognozuojamas nuostolis", money(ecl), pct(ecl / portfolio_ead if portfolio_ead else 0), "red" if ecl / portfolio_ead > .02 else "green")

    st.markdown("### Vadovybei svarbiausia")
    alert_count = 0
    if problem_share > .03:
        alert("red", "Probleminių paskolų dalis viršija 3 %", f"Šiuo metu {money(portfolio_ead * problem_share)} paskolų likutis yra probleminis."); alert_count += 1
    if higher_risk_share > .06:
        alert("amber", "Daugėja paskolų, kurių kredito būklė pablogėjusi", f"Padidėjusios rizikos paskolos sudaro {pct(higher_risk_share)} portfelio."); alert_count += 1
    if late90_share > .02:
        alert("red", "Reikšminga vėluojančių mokėjimų koncentracija", f"Daugiau kaip 90 dienų vėluojančių paskolų dalis siekia {pct(late90_share)}."); alert_count += 1
    if avg_pd > .04:
        alert("red", "Vidutinė įsipareigojimų nevykdymo tikimybė aukšta", f"Vidutinė įsipareigojimų nevykdymo tikimybė siekia {pct(avg_pd)}."); alert_count += 1
    if alert_count == 0:
        alert("green", "Reikšmingų rizikos viršijimų nenustatyta", "Pagal testinių duomenų rodiklius portfelis šiuo metu neperžengia nustatytų pagrindinių rizikos ribų.")

    q("Kaip keičiasi kredito portfelio kokybė?", "Vadovybei svarbu matyti, ar probleminių paskolų ir padidėjusios rizikos paskolų dalis auga, mažėja ar išlieka stabili.")
    if not snap.empty and "Snapshot_Date" in snap.columns:
        sf = snap[snap.get("Country", "").astype(str).isin(selected)].copy() if selected and "Country" in snap.columns else snap.copy()
        sf["IFRS9_Stage"] = pd.to_numeric(sf["IFRS9_Stage"], errors="coerce")
        monthly = sf.groupby("Snapshot_Date", as_index=False).agg(
            Portfelis=("EAD_EUR", "sum"),
            Padidėjusios_rizikos=("EAD_EUR", lambda x: float(x.sum())),
        )
        monthly["Probleminės paskolos"] = sf.groupby("Snapshot_Date")["EAD_EUR"].apply(lambda x: float(x[sf.loc[x.index, "IFRS9_Stage"].eq(3)].sum())).values
        monthly["Padidėjusios rizikos paskolos"] = sf.groupby("Snapshot_Date")["EAD_EUR"].apply(lambda x: float(x[sf.loc[x.index, "IFRS9_Stage"].eq(2)].sum())).values
        monthly["Probleminių dalis"] = monthly["Probleminės paskolos"] / monthly["Portfelis"]
        monthly["Padidėjusios rizikos dalis"] = monthly["Padidėjusios rizikos paskolos"] / monthly["Portfelis"]
        long = monthly.melt("Snapshot_Date", value_vars=["Probleminių dalis", "Padidėjusios rizikos dalis"], var_name="Rodiklis", value_name="Dalis")
        long["Rodiklis"] = long["Rodiklis"].replace({"Probleminių dalis": "Probleminės paskolos", "Padidėjusios rizikos dalis": "Padidėjusios rizikos paskolos"})
        fig = px.line(long, x="Snapshot_Date", y="Dalis", color="Rodiklis")
        fig.update_yaxes(tickformat=".1%", title="Portfelio dalis")
        fig.update_xaxes(title="Mėnuo")
        st.plotly_chart(fig_style(fig, 380), use_container_width=True)

    q("Kurioje šalyje šiuo metu didžiausia kredito rizika?", "Palyginame Baltijos šalis pagal paskolų dydį, probleminių paskolų dalį ir daugiau kaip 90 dienų vėlavimus.")
    if "Country" in latest_f.columns and not latest_f.empty:
        rows = []
        for c, part in latest_f.groupby("Country"):
            e = float(num(part.get("EAD_EUR")).sum())
            stg = num(part.get("IFRS9_Stage"))
            d = num(part.get("DPD_Days"))
            p = num(part.get("PD_12M"))
            rows.append({
                "Šalis": country_names.get(c, c),
                "Paskolų likutis": e,
                "Portfelio dalis": e / portfolio_ead if portfolio_ead else 0,
                "Probleminės paskolos": float((num(part.get("EAD_EUR"))[stg.eq(3)].sum()) / e) if e else 0,
                "Padidėjusios rizikos paskolos": float((num(part.get("EAD_EUR"))[stg.eq(2)].sum()) / e) if e else 0,
                "Daugiau kaip 90 dienų vėlavimas": float((num(part.get("EAD_EUR"))[d.ge(90)].sum()) / e) if e else 0,
                "Vidutinė įsipareigojimų nevykdymo tikimybė": float(p.mean()) if not p.dropna().empty else 0,
            })
        country_df = pd.DataFrame(rows).sort_values("Probleminės paskolos", ascending=False)
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(country_df, x="Šalis", y="Paskolų likutis", text="Portfelio dalis")
            fig.update_traces(texttemplate="%{text:.1%}", textposition="outside")
            fig.update_yaxes(title="Paskolų likutis")
            fig.update_xaxes(title="")
            st.plotly_chart(fig_style(fig, 360), use_container_width=True)
        with c2:
            r = country_df.melt(id_vars="Šalis", value_vars=["Probleminės paskolos", "Padidėjusios rizikos paskolos", "Daugiau kaip 90 dienų vėlavimas"], var_name="Rodiklis", value_name="Dalis")
            fig = px.bar(r, x="Šalis", y="Dalis", color="Rodiklis", barmode="group")
            fig.update_yaxes(tickformat=".1%", title="Portfelio dalis")
            fig.update_xaxes(title="")
            st.plotly_chart(fig_style(fig, 360), use_container_width=True)
        st.dataframe(
            country_df.style.format({
                "Paskolų likutis": lambda x: money(x),
                "Portfelio dalis": lambda x: pct(x),
                "Probleminės paskolos": lambda x: pct(x),
                "Padidėjusios rizikos paskolos": lambda x: pct(x),
                "Daugiau kaip 90 dienų vėlavimas": lambda x: pct(x),
                "Vidutinė įsipareigojimų nevykdymo tikimybė": lambda x: pct(x, 2),
            }),
            use_container_width=True,
            hide_index=True,
        )

    q("Kur banko rizika labiausiai susitelkusi?", "Didesnis ratas reiškia didesnę paskolų sumą, o aukštesnė padėtis reiškia didesnę probleminių paskolų dalį.")
    if not latest_f.empty and "Product_Name" in latest_f.columns:
        prod = latest_f.groupby("Product_Name", as_index=False).agg(Paskolų_likutis=("EAD_EUR", "sum"))
        bad_by_prod = latest_f.assign(Probleminė=num(latest_f.get("IFRS9_Stage")).eq(3)).groupby("Product_Name", as_index=False)["Probleminė"].mean().rename(columns={"Probleminė":"Probleminių dalis"})
        prod = prod.merge(bad_by_prod, on="Product_Name", how="left")
        fig = px.scatter(prod, x="Paskolų_likutis", y="Probleminių dalis", size="Paskolų_likutis", hover_name="Product_Name")
        fig.update_yaxes(tickformat=".1%", title="Probleminių paskolų dalis")
        fig.update_xaxes(title="Paskolų likutis")
        st.plotly_chart(fig_style(fig, 380), use_container_width=True)
        st.markdown("<div class='note'>Viršutinėje dešinėje esančios kategorijos yra svarbiausios vadovybei: jos turi didelį portfelį ir kartu aukštą probleminių paskolų dalį.</div>", unsafe_allow_html=True)

# ============================================================
# 2. KLIENTO PROFILIS
# ============================================================
elif page == "Kliento profilis":
    st.title("Kliento kredito profilis")
    st.caption("Vieno kliento finansinė padėtis, paskolos, mokėjimų istorija ir aiškūs rizikos signalai.")
    cid = search_customer.strip()
    if not cid:
        st.info("Kairėje įrašykite kliento identifikatorių. Testiniuose duomenyse galima naudoti reikšmes iš Customers lentelės.")
    else:
        cust = customers[customers.get("Customer_ID", pd.Series(dtype=str)).astype(str).eq(cid)].copy()
        if cust.empty:
            cust = customers[customers.get("Personal_Code", pd.Series(dtype=str)).astype(str).eq(cid)].copy()
        if cust.empty:
            st.warning("Toks klientas testiniuose duomenyse nerastas.")
        else:
            c = cust.iloc[0]
            csnap = snap[snap.get("Customer_ID", pd.Series(dtype=str)).astype(str).eq(str(c["Customer_ID"]))].copy()
            if selected and "Country" in csnap.columns:
                csnap = csnap[csnap["Country"].astype(str).isin(selected)]
            latest_c = csnap[csnap["Snapshot_Date"].eq(csnap["Snapshot_Date"].max())].copy() if not csnap.empty else pd.DataFrame()
            f = financials[financials.get("Customer_ID", pd.Series(dtype=str)).astype(str).eq(str(c["Customer_ID"]))].sort_values("Snapshot_Date") if not financials.empty else pd.DataFrame()

            st.markdown(f"### {c.get('Customer_ID','')} — {country_names.get(str(c.get('Country','')), str(c.get('Country','')))}")
            cols = st.columns(5)
            total_debt = float(num(latest_c.get("EAD_EUR")).sum()) if not latest_c.empty else 0
            monthly_payment = float(num(f.get("Debt_Service_EUR")).iloc[-1]) if not f.empty and "Debt_Service_EUR" in f.columns else 0
            annual_income = float(num(f.get("Annual_Income_EUR")).iloc[-1]) if not f.empty and "Annual_Income_EUR" in f.columns else float(c.get("Annual_Income_EUR", 0) or 0)
            max_dpd = int(num(latest_c.get("DPD_Days")).max()) if not latest_c.empty and not num(latest_c.get("DPD_Days")).dropna().empty else 0
            with cols[0]: kpi("Amžius", f"{int(c.get('Age',0))} m.", str(c.get("Gender","")), "blue")
            with cols[1]: kpi("Metinės pajamos", money(annual_income), str(c.get("Employment_Status","")), "blue")
            with cols[2]: kpi("Bendra paskolų suma", money(total_debt), f"{len(latest_c)} paskolų", "blue")
            with cols[3]: kpi("Mėnesinės įmokos", money(monthly_payment), f"pajamų dalis {pct(monthly_payment*12/annual_income if annual_income else np.nan)}", "amber" if annual_income and monthly_payment*12/annual_income>.4 else "green")
            with cols[4]: kpi("Didžiausias vėlavimas", f"{max_dpd} d.", "mokėjimo istorija", "red" if max_dpd>=90 else "amber" if max_dpd>=30 else "green")

            q("Kokia kliento finansinė padėtis?", "Šis grafikas parodo, ar pajamos ir skola juda klientui palankia ar nepalankia kryptimi.")
            if not f.empty:
                chart = f[[c for c in ["Snapshot_Date","Annual_Income_EUR","Total_Debt_EUR"] if c in f.columns]].copy()
                long = chart.melt("Snapshot_Date", var_name="Rodiklis", value_name="Suma")
                long["Rodiklis"] = long["Rodiklis"].replace({"Annual_Income_EUR":"Metinės pajamos", "Total_Debt_EUR":"Bendra skola"})
                fig = px.line(long, x="Snapshot_Date", y="Suma", color="Rodiklis")
                fig.update_yaxes(title="Eurais")
                fig.update_xaxes(title="Mėnuo")
                st.plotly_chart(fig_style(fig, 340), use_container_width=True)

            q("Kodėl šis klientas laikomas rizikingu?", "Pateikiami tik tie signalai, kurie gali būti aktualūs kredito sprendimui.")
            signals = 0
            if max_dpd >= 90:
                alert("red", "Klientas reikšmingai vėluoja mokėti", f"Didžiausias nustatytas vėlavimas – {max_dpd} dienos."); signals += 1
            elif max_dpd >= 30:
                alert("amber", "Kliento mokėjimai vėluoja", f"Didžiausias nustatytas vėlavimas – {max_dpd} dienos."); signals += 1
            if annual_income and monthly_payment*12/annual_income > .5:
                alert("red", "Didelė mėnesinių įmokų našta", f"Metinių paskolos įmokų ir pajamų santykis siekia {pct(monthly_payment*12/annual_income)}."); signals += 1
            if not latest_c.empty and num(latest_c.get("IFRS9_Stage")).eq(3).any():
                alert("red", "Bent viena paskola yra probleminė", "Tai reiškia, kad kredito rizika šiam klientui jau yra materializavusis."); signals += 1
            if signals == 0:
                alert("green", "Stiprių dabartinių rizikos signalų nenustatyta", "Pagal turimus testinius duomenis reikšmingų vėlavimų ar probleminių paskolų nėra.")

            q("Kokias paskolas turi klientas?", "Visa kliento kredito pozicija vienoje lentelėje.")
            if not latest_c.empty:
                show = [c for c in ["Loan_ID","Product_Name","EAD_EUR","Interest_Rate","Current_LTV","DPD_Days","PD_12M","LGD","Country"] if c in latest_c.columns]
                st.dataframe(latest_c[show], use_container_width=True, hide_index=True)

# ============================================================
# 3. PORTFELIO IR KREDITAVIMO ANALIZĖ
# ============================================================
elif page == "Portfelio ir kreditavimo analizė":
    st.title("Portfelio ir kreditavimo analizė")
    st.caption("Kas skolinasi, kada skolinasi, kiek įneša savo lėšų ir kurioms klientų grupėms bankas prisiima daugiausia rizikos?")

    q("Kada klientai dažniausiai ima paskolas?", "Paskolų skaičius ir suteikta suma pagal mėnesį padeda matyti sezoniškumą ir kreditavimo tempą.")
    if not loans_f.empty:
        monthly = loans_f.dropna(subset=["Origination_Date"]).copy()
        monthly["Mėnuo"] = monthly["Origination_Date"].dt.to_period("M").astype(str)
        monthly = monthly.groupby("Mėnuo", as_index=False).agg(Naujų_paskolų_skaičius=("Loan_ID","nunique"), Suteikta_suma=("Original_Amount_EUR","sum"))
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(monthly, x="Mėnuo", y="Naujų_paskolų_skaičius")
            fig.update_yaxes(title="Naujų paskolų skaičius")
            fig.update_xaxes(title="Suteikimo mėnuo")
            st.plotly_chart(fig_style(fig, 340), use_container_width=True)
        with c2:
            fig = px.line(monthly, x="Mėnuo", y="Suteikta_suma")
            fig.update_yaxes(title="Suteikta suma, eurais")
            fig.update_xaxes(title="Suteikimo mėnuo")
            st.plotly_chart(fig_style(fig, 340), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        q("Kokio amžiaus klientai dažniausiai skolinasi?", "Padeda suprasti, kurios amžiaus grupės sudaro naujo kreditavimo srautą.")
        if not customers_f.empty and "Age" in customers_f.columns:
            x = customers_f.copy()
            x["Amžiaus grupė"] = pd.cut(pd.to_numeric(x["Age"], errors="coerce"), bins=[17,24,34,44,54,64,200], labels=["18–24","25–34","35–44","45–54","55–64","65+"], include_lowest=True)
            a = x.groupby("Amžiaus grupė", observed=False).size().reset_index(name="Klientų skaičius")
            a["Amžiaus grupė"] = a["Amžiaus grupė"].astype(str)
            fig = px.bar(a, x="Amžiaus grupė", y="Klientų skaičius")
            fig.update_yaxes(title="Klientų skaičius")
            st.plotly_chart(fig_style(fig, 320), use_container_width=True)
    with c2:
        q("Kas dažniau ima paskolas – moterys ar vyrai?", "Parodomas klientų pasiskirstymas pagal lytį; pagal poreikį vėliau galime susieti jį su rizika.")
        if not customers_f.empty and "Gender" in customers_f.columns:
            g = customers_f.groupby("Gender", as_index=False).size().rename(columns={"size":"Klientų skaičius"})
            fig = px.pie(g, names="Gender", values="Klientų skaičius", hole=.60)
            st.plotly_chart(fig_style(fig, 320), use_container_width=True)

    q("Kokį pradinį įnašą klientai dažniausiai įneša?", "Mažesnis pradinis įnašas reiškia mažesnį kliento nuosavą finansinį rezervą ir dažniausiai didesnį banko finansavimo santykį.")
    if not loans_f.empty and "Down_Payment_Pct" in loans_f.columns:
        x = loans_f[pd.to_numeric(loans_f["Down_Payment_Pct"], errors="coerce").gt(0)].copy()
        x["Pradinio įnašo grupė"] = pd.cut(pd.to_numeric(x["Down_Payment_Pct"], errors="coerce"), bins=[0,.1,.15,.2,.25,.3,.4,2], labels=["<10 %","10–15 %","15–20 %","20–25 %","25–30 %","30–40 %",">40 %"], right=False, include_lowest=True)
        d = x.groupby("Pradinio įnašo grupė", observed=False).agg(Paskolų_skaičius=("Loan_ID","nunique"), Suteikta_suma=("Original_Amount_EUR","sum")).reset_index()
        d["Pradinio įnašo grupė"] = d["Pradinio įnašo grupė"].astype(str)
        st.plotly_chart(fig_style(px.bar(d, x="Pradinio įnašo grupė", y="Paskolų_skaičius", hover_data=["Suteikta_suma"]), 330), use_container_width=True)

    q("Ar mažesnis pradinis įnašas susijęs su didesne kredito rizika?", "Lyginame pradinio įnašo dydį su vėliau probleminėmis tapusių paskolų dalimi.")
    if not underwriting.empty and not snap.empty:
        base = underwriting[["Loan_ID","Down_Payment_Pct"]].drop_duplicates("Loan_ID").copy()
        bad = snap[snap["Snapshot_Date"].eq(snap["Snapshot_Date"].max())][["Loan_ID","IFRS9_Stage"]].drop_duplicates("Loan_ID").copy()
        base = base.merge(bad, on="Loan_ID", how="left")
        base["Down_Payment_Pct"] = pd.to_numeric(base["Down_Payment_Pct"], errors="coerce")
        base["Probleminė"] = pd.to_numeric(base["IFRS9_Stage"], errors="coerce").eq(3)
        base["Pradinio įnašo grupė"] = pd.cut(base["Down_Payment_Pct"], bins=[0,.1,.15,.2,.25,.3,.4,2], labels=["<10 %","10–15 %","15–20 %","20–25 %","25–30 %","30–40 %",">40 %"], right=False, include_lowest=True)
        out = base.groupby("Pradinio įnašo grupė", observed=False)["Probleminė"].mean().reset_index(name="Probleminių paskolų dalis")
        out["Pradinio įnašo grupė"] = out["Pradinio įnašo grupė"].astype(str)
        fig = px.bar(out, x="Pradinio įnašo grupė", y="Probleminių paskolų dalis")
        fig.update_yaxes(tickformat=".1%", title="Probleminių paskolų dalis")
        st.plotly_chart(fig_style(fig, 340), use_container_width=True)

    q("Kaip skiriasi skolinimasis tarp Lietuvos, Latvijos ir Estijos?", "Tai padeda vadovybei matyti ne tik portfelio dydį, bet ir klientų struktūros skirtumus tarp šalių.")
    if not loans_f.empty:
        country_loan = loans_f.groupby("Country", as_index=False).agg(
            Paskolų_skaičius=("Loan_ID","nunique"),
            Suteikta_suma=("Original_Amount_EUR","sum"),
            Vidutinė_paskola=("Original_Amount_EUR","mean"),
            Vidutinis_pradinis_įnašas=("Down_Payment_Pct","mean"),
        )
        country_loan["Šalis"] = country_loan["Country"].map(country_names).fillna(country_loan["Country"])
        country_loan["Vidutinis_pradinis_įnašas"] = country_loan["Vidutinis_pradinis_įnašas"] * 100
        st.dataframe(country_loan[["Šalis","Paskolų_skaičius","Suteikta_suma","Vidutinė_paskola","Vidutinis_pradinis_įnašas"]], use_container_width=True, hide_index=True, column_config={"Suteikta_suma":st.column_config.NumberColumn(format="%.0f €"), "Vidutinė_paskola":st.column_config.NumberColumn(format="%.0f €"), "Vidutinis_pradinis_įnašas":st.column_config.NumberColumn(format="%.1f%%")})

# ============================================================
# 4. KREDITŲ RIZIKA IR SCENARIJAI
# ============================================================
else:
    st.title("Kredito rizika ir scenarijai")
    st.caption("Klausimas: kur rizika kaupiasi, kas jau blogėja ir kokių nuostolių galime tikėtis nepalankiu atveju?")

    q("Kurios paskolos turi didžiausią riziką?", "Vertiname ne tik rizikos procentą, bet ir pinigų sumą, kurią bankas yra paskolinęs.")
    if not latest_f.empty:
        rr = latest_f.copy()
        rr["Rizikos rodiklis"] = (
            pd.to_numeric(rr.get("PD_12M"), errors="coerce").fillna(0).rank(pct=True) * 0.45
            + pd.to_numeric(rr.get("Current_LTV"), errors="coerce").fillna(0).rank(pct=True) * 0.20
            + pd.to_numeric(rr.get("DPD_Days"), errors="coerce").fillna(0).clip(0, 180).rank(pct=True) * 0.35
        )
        show = [c for c in ["Loan_ID","Customer_ID","Product_Name","EAD_EUR","PD_12M","Current_LTV","DPD_Days","Country"] if c in rr.columns]
        st.dataframe(rr.nlargest(20,"Rizikos rodiklis")[show], use_container_width=True, hide_index=True)

    q("Ar paskolų kokybė blogėja?", "Parodome, kiek paskolų per kiekvieną mėnesį tapo problemiškesnėmis ir kiek jų grįžo į geresnę būklę.")
    if not loan_events.empty:
        ev = loan_events.copy()
        if selected and "Country" in ev.columns: ev = ev[ev["Country"].astype(str).isin(selected)]
        ev["Event_Date"] = pd.to_datetime(ev.get("Event_Date"), errors="coerce")
        month_ev = ev.dropna(subset=["Event_Date"]).assign(Mėnuo=lambda x: x["Event_Date"].dt.to_period("M").astype(str)).groupby(["Mėnuo","Event_Type"], as_index=False).size().rename(columns={"size":"Įvykių skaičius"})
        fig = px.bar(month_ev, x="Mėnuo", y="Įvykių skaičius", color="Event_Type", barmode="stack")
        fig.update_xaxes(title="Mėnuo"); fig.update_yaxes(title="Įvykių skaičius")
        st.plotly_chart(fig_style(fig, 350), use_container_width=True)

    q("Ar naujesnės paskolos yra rizikingesnės?", "Palyginame paskolų suteikimo metus ir šiandieninę probleminių paskolų dalį.")
    if not loans_f.empty and not latest_f.empty:
        a = loans_f[["Loan_ID","Origination_Date"]].drop_duplicates("Loan_ID").copy()
        a["Suteikimo metai"] = pd.to_datetime(a["Origination_Date"], errors="coerce").dt.year
        b = latest_f[["Loan_ID","IFRS9_Stage"]].drop_duplicates("Loan_ID").copy()
        b["Probleminė"] = pd.to_numeric(b["IFRS9_Stage"], errors="coerce").eq(3)
        v = a.merge(b, on="Loan_ID", how="left").dropna(subset=["Suteikimo metai"])
        v = v.groupby("Suteikimo metai", as_index=False)["Probleminė"].mean().rename(columns={"Probleminė":"Probleminių paskolų dalis"})
        fig = px.bar(v, x="Suteikimo metai", y="Probleminių paskolų dalis")
        fig.update_yaxes(tickformat=".1%", title="Probleminių paskolų dalis")
        st.plotly_chart(fig_style(fig, 330), use_container_width=True)

    q("Ar užstatas pakankamai apsaugo banką?", "Didėjanti paskolos ir užstato vertės dalis reiškia mažesnį banko apsaugos rezervą.")
    if not latest_f.empty and "Current_LTV" in latest_f.columns:
        x = latest_f.copy(); x["Current_LTV"] = pd.to_numeric(x["Current_LTV"], errors="coerce")
        bins=[0,.6,.7,.8,.9,1,10]; labels=["<60 %","60–70 %","70–80 %","80–90 %","90–100 %",">100 %"]
        x["Užstato padengimo grupė"] = pd.cut(x["Current_LTV"], bins=bins, labels=labels, right=False, include_lowest=True)
        ltvc = x.groupby("Užstato padengimo grupė", observed=False).agg(Paskolų_likutis=("EAD_EUR","sum"), Paskolų_skaičius=("Loan_ID","nunique")).reset_index()
        ltvc["Užstato padengimo grupė"] = ltvc["Užstato padengimo grupė"].astype(str)
        fig = px.bar(ltvc, x="Užstato padengimo grupė", y="Paskolų_likutis", hover_data=["Paskolų_skaičius"])
        fig.update_xaxes(title="Paskolos ir užstato vertės santykis")
        fig.update_yaxes(title="Paskolų likutis")
        st.plotly_chart(fig_style(fig, 340), use_container_width=True)

    q("Kas nutiktų, jei kredito rizika padidėtų?", "Testinis scenarijus parodo papildomo prognozuojamo nuostolio dydį, jei įsipareigojimų nevykdymo tikimybė padidėtų.")
    scenario = st.selectbox("Scenarijus", ["Nedidelis pablogėjimas", "Vidutinis pablogėjimas", "Stiprus pablogėjimas"])
    shock = {"Nedidelis pablogėjimas":0.15, "Vidutinis pablogėjimas":0.30, "Stiprus pablogėjimas":0.50}[scenario]
    stress = latest_f.copy()
    stress["Papildomas prognozuojamas nuostolis"] = num(stress.get("EAD_EUR")) * num(stress.get("LGD"), .45).fillna(.45) * num(stress.get("PD_12M"), .02).fillna(.02) * shock
    stress_loss = float(stress["Papildomas prognozuojamas nuostolis"].sum()) if not stress.empty else 0
    c1,c2,c3=st.columns(3)
    with c1: kpi("Scenarijus", scenario, "įsipareigojimų nevykdymo tikimybės šokas", "amber")
    with c2: kpi("Papildomas nuostolis", money(stress_loss), "pagal testinį scenarijų", "red")
    with c3: kpi("Nuostolis nuo portfelio", pct(stress_loss/portfolio_ead if portfolio_ead else 0), "nuo dabartinio paskolų likučio", "red")
    if not stress.empty:
        q("Kurios paskolos labiausiai paveiktų banką?", "Pateikiamos pozicijos, kurioms scenarijus sugeneruotų didžiausią papildomą nuostolį.")
        cols = [c for c in ["Loan_ID","Customer_ID","Product_Name","Country","EAD_EUR","PD_12M","LGD","Papildomas prognozuojamas nuostolis"] if c in stress.columns]
        st.dataframe(stress.nlargest(15,"Papildomas prognozuojamas nuostolis")[cols], use_container_width=True, hide_index=True)

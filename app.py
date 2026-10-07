from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Banko kredito rizikos ataskaita", page_icon="🏦", layout="wide", initial_sidebar_state="expanded")

BASE_DIR = Path(__file__).resolve().parent
EXPECTED_DATA_FILE = "credit_risk_test_data.xlsx"

CSS = """
<style>
.stApp{background:#ffffff}
.block-container{padding-top:1.1rem;padding-left:2rem;padding-right:2rem;max-width:100%!important}
section[data-testid="stSidebar"]{background:radial-gradient(circle at top left,#0c356b 0%,#061d3a 35%,#03162d 100%)!important;min-width:330px!important;max-width:330px!important}
section[data-testid="stSidebar"] *{color:#fff}
section[data-testid="stSidebar"] [data-testid="stTextInput"] input{color:#061b34!important;background:#fff!important;-webkit-text-fill-color:#061b34!important}
.card{background:#fff;border:1px solid #e5eaf1;border-radius:17px;padding:18px 20px;box-shadow:0 8px 28px rgba(15,42,75,.07);height:100%}
.kpi-title{font-size:12px;color:#65758b;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.kpi-value{font-size:28px;font-weight:900;color:#071a33;margin-top:5px}
.kpi-sub{font-size:13px;color:#65758b;margin-top:5px}
.kpi-up{color:#d14343;font-weight:800}.kpi-down{color:#14966d;font-weight:800}.kpi-neutral{color:#65758b;font-weight:800}
.alert{border-radius:15px;padding:14px 16px;margin-bottom:10px;border:1px solid #e5eaf1;background:#fff}
.alert-red{border-left:5px solid #d14343}.alert-amber{border-left:5px solid #e39a22}.alert-green{border-left:5px solid #14966d}
.alert-title{font-weight:900;color:#071a33}.alert-text{color:#4c5c70;font-size:14px;line-height:1.45;margin-top:3px}
.section-title{font-size:22px;font-weight:900;color:#071a33;margin:8px 0 4px}.section-sub{font-size:14px;color:#65758b;margin-bottom:16px}
.small-note{font-size:12px;color:#728197;margin-top:4px}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

def find_data_file():
    """Find the test Excel file reliably on Streamlit Cloud and locally."""
    roots = []
    for root in [BASE_DIR, Path.cwd()]:
        if root.exists() and root not in roots:
            roots.append(root)

    # 1) Exact filename, including project subfolders.
    for root in roots:
        exact = root / EXPECTED_DATA_FILE
        if exact.is_file():
            return exact
        for candidate in root.rglob("*.xlsx"):
            if candidate.name.lower() == EXPECTED_DATA_FILE.lower():
                return candidate

    # 2) If only one Excel file exists in the project, use it.
    all_xlsx = []
    for root in roots:
        try:
            all_xlsx.extend([p for p in root.rglob("*.xlsx") if p.is_file() and not p.name.startswith("~$")])
        except Exception:
            pass
    unique = []
    seen = set()
    for p in all_xlsx:
        rp = str(p.resolve())
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    if len(unique) == 1:
        return unique[0]

    return None


@st.cache_data
def load_data():
    data_path = find_data_file()
    if data_path is None:
        visible = []
        for root in [BASE_DIR, Path.cwd()]:
            try:
                visible.extend(str(p.relative_to(root)) for p in root.rglob("*.xlsx") if p.is_file())
            except Exception:
                pass
        visible = sorted(set(visible))
        st.error("Nerastas kredito rizikos duomenų Excel failas.")
        st.markdown(
            "**Tikimasi:** `credit_risk_test_data.xlsx`\n\n"
            "Failas turi būti įkeltas į tą patį GitHub projektą kaip `app.py` arba jo subfolderį.\n\n"
            f"**Rasti Excel failai:** {', '.join(visible) if visible else 'nerasta nė vieno .xlsx failo'}"
        )
        st.stop()
    try:
        xls = pd.ExcelFile(data_path)
        return {s: pd.read_excel(xls, sheet_name=s) for s in xls.sheet_names}
    except Exception as e:
        st.error(f"Nepavyko atidaryti duomenų failo `{data_path.name}`.")
        st.exception(e)
        st.stop()

D = load_data()
loans = D.get("Loans", pd.DataFrame()).copy()
snap = D.get("Loan_Snapshot", pd.DataFrame()).copy()
customers = D.get("Customers", pd.DataFrame()).copy()
fin = D.get("Customer_Financials", pd.DataFrame()).copy()
pay = D.get("Payments", pd.DataFrame()).copy()
uw = D.get("Underwriting", pd.DataFrame()).copy()
defaults = D.get("Default_Events", pd.DataFrame()).copy()
coll = D.get("Collateral", pd.DataFrame()).copy()
mac = D.get("Macro", pd.DataFrame()).copy()

for df in [loans,snap,customers,fin,pay,uw,defaults,coll,mac]:
    if not df.empty:
        for c in df.columns:
            if "Date" in c or "date" in c or c in ["Snapshot_Date","Month","Application_Date","Approval_Date","Due_Date","Default_Date","Event_Date","Valuation_Date"]:
                try: df[c] = pd.to_datetime(df[c], errors="coerce")
                except Exception: pass

# Normalise likely date columns
for c in ["Snapshot_Date","Month"]:
    if c in fin.columns:
        fin[c]=pd.to_datetime(fin[c],errors="coerce")
        break

# latest snapshot
if not snap.empty and "Snapshot_Date" in snap.columns:
    snap["Snapshot_Date"] = pd.to_datetime(snap["Snapshot_Date"], errors="coerce")
    latest_date = snap["Snapshot_Date"].max()
    latest = snap[snap["Snapshot_Date"].eq(latest_date)].copy()
else:
    latest_date = pd.NaT
    latest = snap.copy()

# Friendly labels
stage_map = {1:"Geros kredito kokybės paskolos",2:"Padidėjusios rizikos paskolos",3:"Probleminės paskolos"}

# Common numeric helpers

def num(df, col, default=0.0):
    return pd.to_numeric(df[col], errors="coerce").fillna(default) if col in df.columns else pd.Series(default,index=df.index,dtype=float)

def pct(x): return f"{x*100:.1f}%"
def eur(x):
    if pd.isna(x): return "–"
    if abs(x)>=1_000_000: return f"{x/1_000_000:.1f} mln. €"
    if abs(x)>=1_000: return f"{x/1_000:.0f} tūkst. €"
    return f"{x:,.0f} €"

def money(x): return f"{x:,.0f} €".replace(","," ")

def safe_delta(cur, prev):
    if prev in [0,None] or pd.isna(prev): return None
    return cur-prev

def metric_card(title, value, subtitle="", tone="neutral"):
    cls = f"kpi-{tone}"
    st.markdown(f'<div class="card"><div class="kpi-title">{title}</div><div class="kpi-value">{value}</div><div class="kpi-sub {cls}">{subtitle}</div></div>', unsafe_allow_html=True)

def fig_base(fig, height=360):
    fig.update_layout(height=height, margin=dict(l=10,r=10,t=45,b=10), paper_bgcolor="white", plot_bgcolor="white", font=dict(family="Arial",color="#20324a"), legend=dict(orientation="h",y=1.08,x=0), hoverlabel=dict(bgcolor="white"))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#edf1f6", zeroline=False)
    return fig

def question(title, subtitle):
    st.markdown(f'<div class="section-title">{title}</div><div class="section-sub">{subtitle}</div>', unsafe_allow_html=True)

def alert(kind, title, text):
    st.markdown(f'<div class="alert alert-{kind}"><div class="alert-title">{title}</div><div class="alert-text">{text}</div></div>', unsafe_allow_html=True)

# sidebar
with st.sidebar:
    st.markdown('<div style="font-size:22px;font-weight:900;margin-bottom:5px">🏦 Kredito rizika</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:13px;color:#b8c9df!important;margin-bottom:18px">Vieno banko vadovybės rizikos ataskaita</div>', unsafe_allow_html=True)
    page = st.radio("Ataskaitos dalis", ["Vadovybės apžvalga","Asmens profilis","Portfelio rizika","Rizikos raida ir scenarijai"], label_visibility="collapsed")
    st.markdown('<div class="sidebar-card"><b>Ataskaitos data</b><br><span style="color:#b8c9df">'+("Nėra duomenų" if pd.isna(latest_date) else latest_date.strftime("%Y-%m-%d"))+f'</span><br><br><b>Aktyvios paskolos</b><br><span style="color:#b8c9df">{len(latest):,}</span></div>',unsafe_allow_html=True)

# prepare latest fields
EAD = num(latest,"EAD_EUR").sum()
if "IFRS9_Stage" in latest.columns:
    latest["IFRS9_Stage"] = pd.to_numeric(latest["IFRS9_Stage"],errors="coerce")
problem_ead = num(latest.loc[latest.get("IFRS9_Stage",pd.Series(index=latest.index)).eq(3)],"EAD_EUR").sum() if not latest.empty else 0
stage2_ead = num(latest.loc[latest.get("IFRS9_Stage",pd.Series(index=latest.index)).eq(2)],"EAD_EUR").sum() if not latest.empty else 0
past90_ead = num(latest.loc[num(latest,"Days_Past_Due").ge(90)],"EAD_EUR").sum() if not latest.empty else 0
problem_ratio = problem_ead/EAD if EAD else 0
stage2_ratio = stage2_ead/EAD if EAD else 0
past90_ratio = past90_ead/EAD if EAD else 0

# 1 Management overview
if page=="Vadovybės apžvalga":
    st.title("Vadovybės kredito rizikos apžvalga")
    st.caption("Pagrindinis klausimas: ar banko kredito portfelio rizika didėja ir kur reikia vadovybės dėmesio?")
    cols=st.columns(5)
    vals=[("Paskolų portfelis",eur(EAD),"dabartinis likutis","neutral"),("Padidėjusios rizikos paskolos",pct(stage2_ratio),"dalis viso portfelio","amber"),("Probleminės paskolos",pct(problem_ratio),"dalis viso portfelio","red"),("Daugiau kaip 90 d. vėlavimas",pct(past90_ratio),"dalis viso portfelio","red"),("Probleminių paskolų suma",eur(problem_ead),"paskolos su didžiausiu kredito kokybės pablogėjimu","red")]
    for c,(a,b,d,t) in zip(cols,vals):
        with c: metric_card(a,b,d,t)

    st.markdown("###")
    alerts=[]
    if problem_ratio>0.05: alerts.append(("red","Probleminių paskolų lygis viršija 5 %",f"Probleminių paskolų likutis sudaro {pct(problem_ratio)} banko paskolų portfelio. Tai reikšminga rizikos zona, kurią verta vertinti kartu su naujų probleminių paskolų srautu ir užstato padengimu."))
    else: alerts.append(("green","Probleminių paskolų dalis kontroliuojama",f"Probleminės paskolos sudaro {pct(problem_ratio)} portfelio."))
    if stage2_ratio>0.10: alerts.append(("amber","Daugėja paskolų, kurių rizika jau pablogėjusi",f"{pct(stage2_ratio)} portfelio priskirta padidėjusios rizikos grupei. Tai svarbus išankstinis signalas prieš klientui tampant probleminiu."))
    high_ltv=(num(latest,"LTV").gt(.9)&num(latest,"EAD_EUR").gt(0)).mean() if not latest.empty and "LTV" in latest.columns else 0
    if high_ltv>0.10: alerts.append(("amber","Reikšminga portfelio dalis turi aukštą užstato riziką",f"{pct(high_ltv)} kredito pozicijų turi didesnį nei 90 % paskolos ir užstato vertės santykį."))
    for a,b,c in alerts: alert(a,b,c)

    question("Ar kredito kokybė gerėja, ar blogėja?","Šis grafikas rodo tris svarbiausius sluoksnius: jau problemines paskolas ir ankstyvus signalus, kad paskola gali tapti problemine.")
    if not snap.empty:
        tmp=snap.groupby("Snapshot_Date").apply(lambda g: pd.Series({"Probleminės paskolos":num(g.loc[pd.to_numeric(g.get("IFRS9_Stage"),errors="coerce").eq(3)],"EAD_EUR").sum()/num(g,"EAD_EUR").sum() if num(g,"EAD_EUR").sum() else 0,"Padidėjusios rizikos paskolos":num(g.loc[pd.to_numeric(g.get("IFRS9_Stage"),errors="coerce").eq(2)],"EAD_EUR").sum()/num(g,"EAD_EUR").sum() if num(g,"EAD_EUR").sum() else 0,"Daugiau kaip 90 d. vėlavimas":num(g.loc[num(g,"Days_Past_Due").ge(90)],"EAD_EUR").sum()/num(g,"EAD_EUR").sum() if num(g,"EAD_EUR").sum() else 0})).reset_index()
        long=tmp.melt(id_vars="Snapshot_Date",var_name="Rodiklis",value_name="Dalis")
        fig=px.line(long,x="Snapshot_Date",y="Dalis",color="Rodiklis",markers=True)
        fig.update_yaxes(tickformat=".1%")
        st.plotly_chart(fig_base(fig),use_container_width=True)

    question("Kur banko rizika didžiausia?","Didelis portfelis kartu su dideliu probleminių paskolų lygiu yra svarbesnis nei maža, bet labai rizikinga nišinė grupė.")
    if not latest.empty:
        g=latest.groupby("Product",as_index=False).agg(Paskolų_likutis=("EAD_EUR","sum"), Probleminės_paskolos=("IFRS9_Stage",lambda s:(pd.to_numeric(s,errors="coerce").eq(3)).mean()))
        g["Pavadinimas"]=g["Product"]
        fig=px.scatter(g,x="Paskolų_likutis",y="Probleminės_paskolos",size="Paskolų_likutis",text="Pavadinimas")
        fig.update_traces(textposition="top center")
        fig.update_yaxes(tickformat=".1%",title="Probleminių paskolų dalis")
        fig.update_xaxes(title="Paskolų likutis")
        st.plotly_chart(fig_base(fig,360),use_container_width=True)

# 2 Customer
elif page=="Asmens profilis":
    st.title("Asmens kredito profilis")
    st.caption("Įveskite kliento kodą ir įvertinkite jo dabartinę finansinę būklę bei kredito riziką.")
    if customers.empty or "Customer_ID" not in customers.columns:
        st.error("Klientų duomenų lentelėje nėra Customer_ID.")
        st.stop()
    default_cid=str(customers.iloc[0]["Customer_ID"])
    cid=st.text_input("Asmens kodas / kliento kodas",value=default_cid).strip()
    cust=customers[customers["Customer_ID"].astype(str).eq(cid)]
    if cust.empty:
        st.warning("Tokio kliento testiniuose duomenyse nėra.")
    else:
        row=cust.iloc[0]
        l=loans[loans["Customer_ID"].astype(str).eq(cid)] if "Customer_ID" in loans.columns else loans.iloc[0:0]
        s=latest[latest["Customer_ID"].astype(str).eq(cid)] if "Customer_ID" in latest.columns else latest.iloc[0:0]
        f=fin[fin["Customer_ID"].astype(str).eq(cid)].sort_values(next((c for c in ["Snapshot_Date","Month"] if c in fin.columns),fin.columns[0]))
        dcols=st.columns(5)
        vals=[("Kliento segmentas",str(row.get("Customer_Segment","–")),""), ("Paskolų skaičius",str(len(l)),""),("Bendra skola",eur(num(s,"EAD_EUR").sum()),"dabartinis likutis"),("Paskutinės pajamos",eur(float(num(f,"Monthly_Income_EUR").iloc[-1])) if not f.empty else "–","per mėnesį"),("Didžiausias vėlavimas",f"{int(num(s,'Days_Past_Due').max() if not s.empty else 0)} d.","mūsų duomenyse")]
        for c,(a,b,d) in zip(dcols,vals):
            with c: metric_card(a,b,d)
        st.markdown("###")
        left,right=st.columns([1.4,1])
        with left:
            question("Kaip keitėsi kliento finansinė padėtis?","Palyginame pajamas, skolos likutį ir mėnesio mokėjimus. Tikslas – nustatyti, ar kliento gebėjimas mokėti paskolas silpnėja.")
            if not f.empty:
                cols=[c for c in ["Snapshot_Date","Month"] if c in f.columns]
                datecol=cols[0]
                q=f[[datecol]+[c for c in ["Monthly_Income_EUR","Total_Debt_EUR"] if c in f.columns]].melt(id_vars=datecol,var_name="Rodiklis",value_name="Suma")
                fig=px.line(q,x=datecol,y="Suma",color="Rodiklis",markers=True)
                fig.update_yaxes(tickprefix="€")
                st.plotly_chart(fig_base(fig,330),use_container_width=True)
        with right:
            question("Kas šiuo metu kelia riziką?","Automatiškai išrenkami aiškiausi signalai, kuriuos vadovas galėtų perduoti rizikos valdymo komandai.")
            income=float(num(f,"Monthly_Income_EUR").iloc[-1]) if not f.empty and "Monthly_Income_EUR" in f.columns else 0
            totaldebt=float(num(f,"Total_Debt_EUR").iloc[-1]) if not f.empty and "Total_Debt_EUR" in f.columns else 0
            maxdpd=int(num(s,"Days_Past_Due").max()) if not s.empty else 0
            if income and totaldebt/income>60: alert("red","Didelė skolos našta",f"Kliento skola sudaro apie {totaldebt/income:.1f} mėnesio pajamų.")
            if maxdpd>=30: alert("red","Reikšmingas mokėjimų vėlavimas",f"Maksimalus nustatytas vėlavimas – {maxdpd} dienos.")
            if maxdpd==0 and income and totaldebt/income<=60: alert("green","Šiuo metu nėra aiškaus didelio rizikos signalo","Pagal testinius duomenis klientas neturi reikšmingo mokėjimų vėlavimo, o skolos našta nėra išskirtinai didelė.")
        question("Kokias paskolas turi klientas?","Visos kliento paskolos vienoje vietoje, kad būtų galima pamatyti bendrą poziciją ir riziką.")
        if not s.empty:
            showcols=[c for c in ["Loan_ID","Product","EAD_EUR","Interest_Rate","LTV","Days_Past_Due","IFRS9_Stage","PD"] if c in s.columns]
            tbl=s[showcols].copy()
            if "IFRS9_Stage" in tbl.columns: tbl["Kredito būklė"]=tbl["IFRS9_Stage"].map(stage_map)
            st.dataframe(tbl.drop(columns=["IFRS9_Stage"] if "IFRS9_Stage" in tbl.columns else []),use_container_width=True,hide_index=True)

# 3 portfolio risk
elif page=="Portfelio rizika":
    st.title("Portfelio rizika")
    st.caption("Kur rizika yra susikaupusi ir kokie klientų ar produktų požymiai ją geriausiai paaiškina?")
    if latest.empty: st.warning("Nėra naujausio portfelio stebėjimo."); st.stop()
    q=latest.groupby("Product",as_index=False).agg(Paskolų_likutis=("EAD_EUR","sum"),Vidutinė_rizika=("PD", "mean"),Probleminių_paskolų_dalis=("IFRS9_Stage",lambda s:(pd.to_numeric(s,errors="coerce").eq(3)).mean())) if "PD" in latest.columns else latest.groupby("Product",as_index=False).agg(Paskolų_likutis=("EAD_EUR","sum"),Probleminių_paskolų_dalis=("IFRS9_Stage",lambda s:(pd.to_numeric(s,errors="coerce").eq(3)).mean()))
    question("Kur rizika didžiausia pagal produktą?","Kuo stulpelis didesnis, tuo daugiau banko pinigų yra tame produkte. Kuo spalva tamsesnė, tuo didesnė probleminių paskolų dalis.")
    fig=px.bar(q.sort_values("Paskolų_likutis"),x="Paskolų_likutis",y="Product",orientation="h",color="Probleminių_paskolų_dalis",color_continuous_scale=["#cfe9df","#e39a22","#d14343"])
    fig.update_xaxes(title="Paskolų likutis")
    fig.update_yaxes(title="")
    fig.update_coloraxes(colorbar_title="Probleminių paskolų dalis",colorbar_tickformat=".0%")
    st.plotly_chart(fig_base(fig,390),use_container_width=True)
    question("Ar paskolų suteikimo metu buvo matomi rizikos signalai?","Ši analizė tikrina, ar klientai, kuriems paskolos pradžioje buvo taikoma didesnė skolos našta ar didesnis paskolos ir užstato santykis, vėliau tapo problemiškesni.")
    if not uw.empty and "Origination_LTV" in uw.columns and "IFRS9_Stage" in uw.columns:
        tmp=uw.copy(); tmp["Origination_LTV"]=pd.to_numeric(tmp["Origination_LTV"],errors="coerce")
        tmp["LTV grupė"] = pd.cut(tmp["Origination_LTV"],bins=[0,.6,.7,.8,.9,1,10],right=False,include_lowest=True).astype(str)
        out=tmp.groupby("LTV grupė",observed=True).apply(lambda g: (pd.to_numeric(g["IFRS9_Stage"],errors="coerce").eq(3)).mean(),include_groups=False).reset_index(name="Probleminių paskolų dalis")
        fig=px.bar(out,x="LTV grupė",y="Probleminių paskolų dalis")
        fig.update_yaxes(tickformat=".1%",title="Probleminių paskolų dalis")
        fig.update_xaxes(title="Paskolos ir užstato vertės santykis suteikimo metu")
        st.plotly_chart(fig_base(fig,340),use_container_width=True)
    question("Kurios paskolos šiuo metu reikalauja daugiausia dėmesio?","Sąrašas, skirtas ne statistikai, o konkrečiai rizikos valdymo veiklai.")
    r=latest.copy(); r["Rizikos balas"]=num(r,"PD")*0.5+num(r,"LTV")*0.2+(num(r,"Days_Past_Due").clip(0,90)/90)*0.3 if "PD" in r.columns else (num(r,"Days_Past_Due").clip(0,90)/90)
    show=[c for c in ["Loan_ID","Customer_ID","Product","EAD_EUR","PD","LTV","Days_Past_Due","IFRS9_Stage"] if c in r.columns]
    st.dataframe(r.sort_values("Rizikos balas",ascending=False).head(20)[show],use_container_width=True,hide_index=True)

# 4 evolution / scenarios
else:
    st.title("Rizikos raida ir scenarijai")
    st.caption("Ar rizika atsiranda naujose paskolose, kaip greitai klientai blogėja ir kas nutiktų nepalankaus scenarijaus atveju?")
    question("Kiek paskolų per laiką pagerėjo ir kiek pablogėjo?","Tai paprastesnė migracijos analizė: stebime, kaip portfelis juda nuo geros būklės link didesnės rizikos.")
    if not snap.empty:
        s2=snap.copy(); s2["IFRS9_Stage"]=pd.to_numeric(s2["IFRS9_Stage"],errors="coerce")
        g=s2.groupby("Snapshot_Date",as_index=False).agg(Geros=("IFRS9_Stage",lambda s:(s==1).sum()),Padidėjusios_rizikos=("IFRS9_Stage",lambda s:(s==2).sum()),Probleminės=("IFRS9_Stage",lambda s:(s==3).sum()))
        long=g.melt(id_vars="Snapshot_Date",var_name="Kredito būklė",value_name="Paskolų skaičius")
        fig=px.area(long,x="Snapshot_Date",y="Paskolų skaičius",color="Kredito būklė")
        st.plotly_chart(fig_base(fig,350),use_container_width=True)
    question("Ar naujesnės paskolos yra rizikingesnės?","Palyginame paskolas pagal suteikimo metus ir žiūrime, kokia jų dalis iki šiandien tapo problemine.")
    if not loans.empty and "Origination_Date" in loans.columns and "Loan_ID" in loans.columns:
        a=loans[["Loan_ID","Origination_Date"]].copy(); a["Suteikimo metai"]=pd.to_datetime(a["Origination_Date"],errors="coerce").dt.year
        ss=latest[[c for c in ["Loan_ID","IFRS9_Stage"] if c in latest.columns]].copy(); ss["IFRS9_Stage"]=pd.to_numeric(ss["IFRS9_Stage"],errors="coerce")
        v=a.merge(ss,on="Loan_ID",how="left").groupby("Suteikimo metai",as_index=False)["IFRS9_Stage"].apply(lambda s:(s==3).mean()).reset_index(name="Probleminių paskolų dalis")
        if "Suteikimo metai" not in v.columns: v=v.rename(columns={v.columns[0]:"Suteikimo metai"})
        fig=px.bar(v,x="Suteikimo metai",y="Probleminių paskolų dalis")
        fig.update_yaxes(tickformat=".1%")
        st.plotly_chart(fig_base(fig,330),use_container_width=True)
    question("Kas nutiktų nepalankaus scenarijaus atveju?","Testinis scenarijus padidina riziką pagal paskolos rizikingumą. Rezultatas skirtas parodyti, kuri portfelio dalis būtų jautriausia ekonomikos pablogėjimui.")
    scenario=st.selectbox("Scenarijus",["Vidutinis pablogėjimas","Stiprus pablogėjimas"])
    shock=0.25 if scenario=="Vidutinis pablogėjimas" else 0.50
    stressed=latest.copy(); stressed["Papildomas nuostolis"] = num(stressed,"EAD_EUR")*num(stressed,"LGD").replace(0,np.nan).fillna(0.45)*num(stressed,"PD").clip(lower=0)*shock if "PD" in stressed.columns else 0
    stress_loss=stressed["Papildomas nuostolis"].sum()
    c1,c2=st.columns(2)
    with c1: metric_card("Papildomas prognozuojamas nuostolis",eur(stress_loss),scenario,"red")
    with c2:
        top=stressed.nlargest(10,"Papildomas nuostolis")[[c for c in ["Loan_ID","Customer_ID","Product","EAD_EUR","Papildomas nuostolis"] if c in stressed.columns]]
        st.dataframe(top,use_container_width=True,hide_index=True)

# -*- coding: utf-8 -*-
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='Credit Risk Dashboard', page_icon='🏦', layout='wide', initial_sidebar_state='expanded')

DATA_PATH = Path(__file__).with_name('credit_risk_test_data.xlsx')

# ---------------------------- STYLE ----------------------------
CSS = """
<style>
.stApp { background: #ffffff; }
.block-container { padding-top: 1.2rem; padding-left: 2rem; padding-right: 2rem; max-width: 100% !important; }
section[data-testid="stSidebar"] { background: radial-gradient(circle at top left, #0c356b 0%, #061d3a 35%, #03162d 100%) !important; min-width: 340px !important; max-width: 340px !important; }
section[data-testid="stSidebar"] > div { padding: 14px 18px 22px 18px; }
section[data-testid="stSidebar"] * { color: #ffffff; }
.sidebar-title { font-size: 21px; font-weight: 900; margin-bottom: 3px; }
.sidebar-subtitle { color: #b8c9df !important; font-size: 13px; margin-bottom: 18px; }
.sidebar-card { background: rgba(255,255,255,.055); border: 1px solid rgba(157,190,230,.28); border-radius: 17px; padding: 18px 16px; box-shadow: 0 18px 45px rgba(0,0,0,.24); margin-bottom: 17px; }
.sidebar-card-title { font-size: 15px; font-weight: 900; margin-bottom: 8px; }
.sidebar-card-subtitle { color:#b8c9df !important; font-size:12px; line-height:1.45; }
.kpi-card { background: #ffffff; border:1px solid #e4e9f0; border-radius:18px; padding:18px 18px 15px 18px; box-shadow: 0 10px 28px rgba(3,22,45,.07); min-height: 120px; }
.kpi-label { color:#64748b; font-size:12px; font-weight:800; text-transform:uppercase; letter-spacing:.04em; }
.kpi-value { color:#0b2342; font-size:30px; font-weight:900; margin-top:5px; }
.kpi-note { color:#64748b; font-size:12px; margin-top:3px; }
.section-title { color:#0b2342; font-size:22px; font-weight:900; margin: 8px 0 3px 0; }
.section-subtitle { color:#64748b; font-size:13px; margin-bottom:12px; }
.risk-pill { display:inline-block; border-radius:999px; padding:5px 11px; font-size:12px; font-weight:900; }
.risk-low { background:#e7f8f0; color:#0b7a4b; }
.risk-medium { background:#fff4df; color:#a35b00; }
.risk-high { background:#ffe8e8; color:#b42318; }
.metric-panel { background:#f7f9fc; border:1px solid #e9eef5; border-radius:18px; padding:14px 16px; }
.small-muted { color:#64748b; font-size:12px; }
div[data-testid="stMetric"] { background:#ffffff; border:1px solid #e4e9f0; border-radius:18px; padding:12px 14px; }
button[kind="primary"] { border-radius:12px !important; font-weight:800 !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- DATA ----------------------------
@st.cache_data(show_spinner='Kraunami kredito rizikos duomenys...')
def load_data(path: str):
    excel = pd.ExcelFile(path)
    names = excel.sheet_names
    data = {name: pd.read_excel(path, sheet_name=name) for name in names if name not in ['README','Data_Dictionary','KPI_Controls','Risk_Appetite']}
    for key, df in data.items():
        for c in df.columns:
            if 'Date' in c or c.endswith('_Date'):
                data[key][c] = pd.to_datetime(data[key][c], errors='coerce')
    return data

try:
    D = load_data(str(DATA_PATH))
except Exception as e:
    st.error(f'Nepavyko įkelti Excel failo: {e}')
    st.stop()

customers = D['Customers']
loans = D['Loans']
snap = D['Loan_Snapshot']
financials = D['Customer_Financials']
underwriting = D['Underwriting']
collateral = D['Collateral']
payments = D['Payments']
ratings = D['Risk_Ratings']
defaults = D['Default_Events']
collections = D['Collections']
events = D['Loan_Events']
macro = D['Macro']
stress = D['Stress_Scenarios']

# normalize date fields
for df, col in [(loans,'Origination_Date'), (snap,'Snapshot_Date'), (financials,'Month'), (underwriting,'Origination_Date'), (collateral,'Valuation_Date'), (payments,'Payment_Date'), (ratings,'Rating_Date'), (defaults,'Default_Date'), (collections,'Action_Date'), (events,'Event_Date'), (macro,'Month')]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors='coerce')

# ---------------------------- HELPERS ----------------------------
def euro(x):
    if pd.isna(x): return '—'
    if abs(x) >= 1_000_000: return f'€{x/1_000_000:.1f} mln'
    if abs(x) >= 1_000: return f'€{x/1_000:.0f} tūkst.'
    return f'€{x:,.0f}'

def pct(x): return '—' if pd.isna(x) else f'{x*100:.1f}%'

def num(x): return '—' if pd.isna(x) else f'{x:,.0f}'.replace(',', ' ')

def risk_label(pd_value):
    if pd_value < 0.02: return 'Žema rizika', 'risk-low'
    if pd_value < 0.06: return 'Vidutinė rizika', 'risk-medium'
    return 'Aukšta rizika', 'risk-high'

def card(label, value, note=''):
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-note">{note}</div></div>', unsafe_allow_html=True)

def section(title, subtitle=''):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{subtitle}</div>', unsafe_allow_html=True)

def chart_layout(fig, height=330):
    fig.update_layout(height=height, margin=dict(l=10,r=10,t=42,b=10), paper_bgcolor='white', plot_bgcolor='white', font=dict(color='#0b2342'), legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor='#edf1f6')
    return fig

latest_date = snap['Snapshot_Date'].max()
latest_snap = snap[snap['Snapshot_Date'] == latest_date].copy()
products = D['Products'] if 'Products' in D else pd.DataFrame()
if not products.empty and 'Product_Code' in products.columns:
    latest_snap = latest_snap.merge(products[['Product_Code','Product_Name']], on='Product_Code', how='left')
    snap = snap.merge(products[['Product_Code','Product_Name']], on='Product_Code', how='left')

# ---------------------------- SIDEBAR ----------------------------
with st.sidebar:
    st.markdown('<div class="sidebar-title">🏦 Credit Risk</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-subtitle">Kredito portfelio rizikos stebėsenos centras</div>', unsafe_allow_html=True)

    page = st.radio('Ataskaita', ['Apžvalga','Asmens profilis','Rizikos statistika','Portfelio statistika','Migracija ir vintage','Užstatas ir koncentracija','Streso testavimas','Paskolų paieška'], label_visibility='collapsed')

    st.markdown('<div class="sidebar-card"><div class="sidebar-card-title">Filtrai</div><div class="sidebar-card-subtitle">Filtrai taikomi portfelio analizės puslapiams.</div></div>', unsafe_allow_html=True)
    selected_segments = st.multiselect('Kliento segmentas', sorted(loans['Customer_Segment'].dropna().unique()), default=sorted(loans['Customer_Segment'].dropna().unique()))
    selected_products = st.multiselect('Paskolos produktas', sorted(loans['Product_Name'].dropna().unique()), default=sorted(loans['Product_Name'].dropna().unique()))
    selected_banks = st.multiselect('Bankas', sorted(loans['Bank_ID'].dropna().unique()), default=sorted(loans['Bank_ID'].dropna().unique()))

    base_loans = loans[loans['Customer_Segment'].isin(selected_segments) & loans['Product_Name'].isin(selected_products) & loans['Bank_ID'].isin(selected_banks)].copy()
    selected_loan_ids = set(base_loans['Loan_ID'])
    base_snap = latest_snap[latest_snap['Loan_ID'].isin(selected_loan_ids)].copy()

    st.markdown('<div class="sidebar-card"><div class="sidebar-card-title">Duomenų būklė</div><div class="sidebar-card-subtitle">Paskutinė portfelio data</div><b>' + latest_date.strftime('%Y-%m-%d') + '</b><br><span class="small-muted">' + num(len(base_loans)) + ' paskolų</span></div>', unsafe_allow_html=True)

# ---------------------------- PAGES ----------------------------
if page == 'Apžvalga':
    section('Kredito rizikos apžvalga', 'Vadovybės vaizdas: dabartinė portfelio būklė, pagrindinės rizikos ir jų dinamika.')
    total_ead = base_snap['EAD_EUR'].sum()
    npl = base_snap.loc[base_snap['IFRS9_Stage'].eq('Stage 3'),'EAD_EUR'].sum() / total_ead if total_ead else 0
    stage2 = base_snap.loc[base_snap['IFRS9_Stage'].eq('Stage 2'),'EAD_EUR'].sum() / total_ead if total_ead else 0
    d90 = base_snap.loc[base_snap['DPD_Days'] >= 90,'EAD_EUR'].sum() / total_ead if total_ead else 0
    ecl = base_snap['ECL_EUR'].sum()
    avg_pd = np.average(base_snap['PD_12M'], weights=base_snap['EAD_EUR']) if total_ead else np.nan

    cols = st.columns(6)
    for c, lab, val, note in zip(cols,['Paskolų likutis','Neveiksnių paskolų dalis','Antrojo etapo dalis','Daugiau kaip 90 dienų vėlavimas','Tikėtinas kredito nuostolis','Svertinis įsipareigojimų nevykdymo tikimybės vidurkis'],[euro(total_ead),pct(npl),pct(stage2),pct(d90),euro(ecl),pct(avg_pd)],['Bendra rizikos ekspozicija', 'Pagal ekspoziciją','Pagal ekspoziciją','Pagal ekspoziciją','Esama portfelio vertė','Pagal ekspoziciją']):
        with c: card(lab,val,note)

    st.write('')
    c1,c2 = st.columns([1.25,1])
    with c1:
        section('Rizikos struktūra','Paskolų likutis pagal kredito rizikos etapą.')
        x = base_snap.groupby('Stage',as_index=False)['EAD_EUR'].sum().sort_values('EAD_EUR',ascending=False)
        fig = px.bar(x,x='Stage',y='EAD_EUR',text='EAD_EUR')
        fig.update_traces(texttemplate='%{text:.2s}', textposition='outside')
        st.plotly_chart(chart_layout(fig),use_container_width=True)
    with c2:
        section('Rizikos pasiskirstymas','Paskolų skaičius pagal mokėjimo vėlavimą.')
        b = base_snap.assign(Vėlavimas=np.select([base_snap.DPD_Days.eq(0),base_snap.DPD_Days.between(1,30),base_snap.DPD_Days.between(31,60),base_snap.DPD_Days.between(61,90),base_snap.DPD_Days.gt(90)],['Laiku','1–30 dienų','31–60 dienų','61–90 dienų','Daugiau kaip 90 dienų']))
        x = b.groupby('Vėlavimas').size().reset_index(name='Paskolų skaičius')
        fig = px.bar(x,x='Vėlavimas',y='Paskolų skaičius',text='Paskolų skaičius')
        st.plotly_chart(chart_layout(fig),use_container_width=True)

    c3,c4 = st.columns(2)
    with c3:
        section('Rizikos dinamika','Neveiksnių paskolų ir antrojo rizikos etapo dalies pokytis.')
        t = snap.groupby('Snapshot_Date').apply(lambda g: pd.Series({'Neveiksnių paskolų dalis': g.loc[g.IFRS9_Stage.eq('Stage 3'),'EAD_EUR'].sum()/g.EAD_EUR.sum(),'Antrojo etapo dalis':g.loc[g.IFRS9_Stage.eq('Stage 2'),'EAD_EUR'].sum()/g.EAD_EUR.sum()})).reset_index()
        long=t.melt('Snapshot_Date',var_name='Rodiklis',value_name='Dalis')
        fig=px.line(long,x='Snapshot_Date',y='Dalis',color='Rodiklis',markers=True)
        fig.update_yaxes(tickformat='.0%')
        st.plotly_chart(chart_layout(fig),use_container_width=True)
    with c4:
        section('Didžiausios rizikos','Paskolos su didžiausia įsipareigojimų nevykdymo tikimybe.')
        top=base_snap.sort_values('PD_12M',ascending=False)[['Loan_ID','Customer_ID','Product_Name','EAD_EUR','PD_12M','Current_LTV','Stage','DPD_Days']].head(10).copy()
        top['EAD_EUR']=top['EAD_EUR'].map(euro); top['PD_12M']=top['PD_12M'].map(pct); top['Current_LTV']=top['Current_LTV'].map(pct)
        st.dataframe(top,use_container_width=True,hide_index=True)

elif page == 'Asmens profilis':
    section('Asmens profilis','Įveskite asmens kodą arba pasirinkite klientą ir peržiūrėkite jo kredito rizikos profilį.')
    ids = customers['Customer_ID'].dropna().astype(str).tolist()
    selected = st.selectbox('Asmens kodas / kliento numeris', ids, index=0 if ids else None)
    cid = selected
    cust = customers[customers['Customer_ID'].astype(str).eq(cid)]
    if cust.empty: st.warning('Klientas nerastas.'); st.stop()
    cust=cust.iloc[0]
    cl = loans[loans['Customer_ID'].astype(str).eq(cid)]
    ls = snap[snap['Loan_ID'].isin(cl['Loan_ID'])].copy()
    latest=ls[ls['Snapshot_Date'].eq(ls['Snapshot_Date'].max())]
    fin=financials[financials['Customer_ID'].astype(str).eq(cid)].sort_values('Month')
    uw=underwriting[underwriting['Customer_ID'].astype(str).eq(cid)]

    total=latest.EAD_EUR.sum(); pdw=np.average(latest.PD_12M,weights=latest.EAD_EUR) if total else np.nan
    risk, cls=risk_label(pdw if not pd.isna(pdw) else 0)
    cols=st.columns(6)
    vals=[str(cust.get('Customer_Segment','—')),num(len(cl)),euro(total),pct(pdw),' '.join(sorted(latest.IFRS9_Stage.dropna().unique())),risk]
    labs=['Segmentas','Paskolų skaičius','Paskolų likutis','Vidutinė įsipareigojimų nevykdymo tikimybė','Esamas rizikos etapas','Bendra rizika']
    notes=['Kliento kategorija','Aktyvios paskolos','Esama ekspozicija','Svertinis pagal ekspoziciją','Pagal naujausią stebėjimą','Pagal vidutinę tikimybę']
    for c,l,v,n in zip(cols,labs,vals,notes):
        with c: card(l,v,n)

    st.markdown('')
    a,b=st.columns(2)
    with a:
        section('Pagrindinė finansinė padėtis')
        f=fin.tail(1).iloc[0] if not fin.empty else None
        if f is not None:
            st.dataframe(pd.DataFrame({'Rodiklis':['Mėnesio pajamos','Mėnesio išlaidos','Bendra skola','Skolos ir pajamų santykis','Mokėjimų ir pajamų santykis','Kredito balas'], 'Reikšmė':[euro(f.Monthly_Income_EUR),euro(f.Monthly_Expenses_EUR),euro(f.Total_Debt_EUR),pct(f.DTI),pct(f.DSTI),num(last.Credit_Score)]}), hide_index=True, use_container_width=True)
        else: st.info('Finansinės istorijos nėra.')
    with b:
        section('Ankstyvieji rizikos signalai')
        alerts=[]
        if not fin.empty:
            last=fin.iloc[-1]; prev=fin.iloc[-7] if len(fin)>=7 else fin.iloc[0]
            if last.Monthly_Income_EUR < prev.Monthly_Income_EUR*0.9: alerts.append(('Aukštas','Pajamos sumažėjo daugiau kaip 10 procentų.'))
            if last.DSTI > 0.5: alerts.append(('Aukštas','Mokėjimų ir pajamų santykis viršija 50 procentų.'))
            if False: alerts.append(('Aukštas','Kredito balas yra žemas.'))
        if (latest.DPD_Days>=30).any(): alerts.append(('Aukštas','Nustatytas reikšmingas mokėjimų vėlavimas.'))
        if (latest.Current_LTV>0.85).any(): alerts.append(('Vidutinis','Dalis paskolų turi aukštą paskolos ir užstato vertės santykį.'))
        if not alerts: alerts=[('Žemas','Reikšmingų ankstyvųjų rizikos signalų nenustatyta.')]
        for severity,text in alerts:
            st.markdown(f'<div class="metric-panel"><b>{severity}</b> &nbsp; {text}</div><div style="height:7px"></div>',unsafe_allow_html=True)

    section('Paskolų portfelis','Visos pasirinkto asmens paskolos.')
    if not latest.empty:
        table=latest.merge(cl[['Loan_ID','Origination_Date','Interest_Rate']],on='Loan_ID',how='left')
        table=table[['Loan_ID','Product_Name','EAD_EUR','Interest_Rate','Current_LTV','PD_12M','Stage','DPD_Days','ECL_EUR']]
        table.columns=['Paskola','Produktas','Paskolos likutis','Palūkanų norma','Paskolos ir užstato vertės santykis','Įsipareigojimų nevykdymo tikimybė','Rizikos etapas','Vėlavimas dienomis','Tikėtinas kredito nuostolis']
        table['Paskolos likutis']=table['Paskolos likutis'].map(euro); table['Palūkanų norma']=table['Palūkanų norma'].map(pct); table['Paskolos ir užstato vertės santykis']=table['Paskolos ir užstato vertės santykis'].map(pct); table['Įsipareigojimų nevykdymo tikimybė']=table['Įsipareigojimų nevykdymo tikimybė'].map(pct); table['Tikėtinas kredito nuostolis']=table['Tikėtinas kredito nuostolis'].map(euro)
        st.dataframe(table,hide_index=True,use_container_width=True)

    c,d=st.columns(2)
    with c:
        section('Rizikos istorija')
        tr=ls.groupby('Snapshot_Date').apply(lambda g: pd.Series({'Įsipareigojimų nevykdymo tikimybė':np.average(g.PD_12M,weights=g.EAD_EUR) if g.EAD_EUR.sum() else np.nan,'Paskolos likutis':g.EAD_EUR.sum()})).reset_index()
        fig=px.line(tr,x='Snapshot_Date',y='Įsipareigojimų nevykdymo tikimybė',markers=True); fig.update_yaxes(tickformat='.0%'); st.plotly_chart(chart_layout(fig),use_container_width=True)
    with d:
        section('Paskolos likučio dinamika')
        fig=px.area(tr,x='Snapshot_Date',y='Paskolos likutis'); st.plotly_chart(chart_layout(fig),use_container_width=True)

elif page == 'Rizikos statistika':
    section('Rizikos statistika','Kredito kokybės, mokėjimų vėlavimų ir tikėtinų nuostolių analizė.')
    total=base_snap.EAD_EUR.sum(); stage3=base_snap.loc[base_snap.IFRS9_Stage.eq('Stage 3'),'EAD_EUR'].sum(); stage2=base_snap.loc[base_snap.IFRS9_Stage.eq('Stage 2'),'EAD_EUR'].sum(); ecl=base_snap.ECL_EUR.sum()
    cols=st.columns(5)
    for c,l,v,n in zip(cols,['Paskolos likutis','Neveiksnių paskolų dalis','Antrojo etapo dalis','Tikėtinas kredito nuostolis','Nuostolių padengimas'],[euro(total),pct(stage3/total),pct(stage2/total),euro(ecl),pct(ecl/stage3 if stage3 else np.nan)],['','Pagal ekspoziciją','Pagal ekspoziciją','','Tikėtinas kredito nuostolis / 3 etapo likutis']):
        with c: card(l,v,n)
    a,b=st.columns(2)
    with a:
        section('Kredito rizikos etapai')
        x=base_snap.groupby('Stage').agg(Paskolos=('Loan_ID','count'),Ekspozicija=('EAD_EUR','sum')).reset_index(); x['Paskolos likutis']=x.Ekspozicija.map(euro)
        st.dataframe(x[['Stage','Paskolos','Paskolos likutis']],hide_index=True,use_container_width=True)
    with b:
        section('Mokėjimų vėlavimas')
        x=base_snap.assign(Bucket=pd.cut(base_snap.DPD_Days,bins=[-1,0,30,60,90,99999],labels=['Laiku','1–30','31–60','61–90','Daugiau kaip 90'])).groupby('Bucket',observed=False).agg(Paskolos=('Loan_ID','count'),Ekspozicija=('EAD_EUR','sum')).reset_index()
        x['Ekspozicija']=x['Ekspozicija'].map(euro); st.dataframe(x,hide_index=True,use_container_width=True)
    section('Tikėtino kredito nuostolio struktūra')
    a,b=st.columns(2)
    with a:
        x=base_snap.groupby('Product_Name').ECL_EUR.sum().reset_index().sort_values('ECL_EUR',ascending=False); fig=px.bar(x,x='ECL_EUR',y='Product_Name',orientation='h',text='ECL_EUR'); st.plotly_chart(chart_layout(fig),use_container_width=True)
    with b:
        x=base_snap.assign(Rizika=np.select([base_snap.PD_12M<.02,base_snap.PD_12M<.06],['Žema','Vidutinė'],default='Aukšta')).groupby('Rizika').EAD_EUR.sum().reset_index(); fig=px.pie(x,names='Rizika',values='EAD_EUR',hole=.55); st.plotly_chart(chart_layout(fig),use_container_width=True)

elif page == 'Portfelio statistika':
    section('Portfelio statistika','Portfelio dydis, produktai, klientų segmentai ir rizikos bei grąžos santykis.')
    byprod=base_snap.groupby('Product_Name').agg(Paskolos=('Loan_ID','count'),Ekspozicija=('EAD_EUR','sum'),Vidutinė_įsipareigojimų_nevykdymo_tikimybė=('PD_12M','mean'),Vidutinis_LTV=('Current_LTV','mean'),Tikėtinas_kredito_nuostolis=('ECL_EUR','sum')).reset_index()
    a,b,c=st.columns(3)
    for col,(lab,val) in zip([a,b,c],[('Didžiausias produktas pagal likutį',byprod.loc[byprod.Ekspozicija.idxmax(),'Product_Name']),('Didžiausias rizikos produktas',byprod.loc[byprod.Vidutinė_įsipareigojimų_nevykdymo_tikimybė.idxmax(),'Product_Name']),('Didžiausias tikėtinas nuostolis',byprod.loc[byprod.Tikėtinas_kredito_nuostolis.idxmax(),'Product_Name'])]):
        with col: card(lab,str(val))
    a,b=st.columns(2)
    with a:
        section('Paskolų likutis pagal produktą')
        fig=px.bar(byprod.sort_values('Ekspozicija'),x='Ekspozicija',y='Product_Name',orientation='h',text='Ekspozicija'); st.plotly_chart(chart_layout(fig),use_container_width=True)
    with b:
        section('Rizikos ir likučio santykis')
        fig=px.scatter(byprod,x='Vidutinė_įsipareigojimų_nevykdymo_tikimybė',y='Ekspozicija',size='Tikėtinas_kredito_nuostolis',color='Product_Name',hover_name='Product_Name'); fig.update_xaxes(tickformat='.0%'); st.plotly_chart(chart_layout(fig),use_container_width=True)
    section('Segmentų palyginimas')
    x=base_snap.groupby('Customer_Segment').agg(Paskolos=('Loan_ID','count'),Ekspozicija=('EAD_EUR','sum'),Vidutinė_rizika=('PD_12M','mean'),Tikėtinas_nuostolis=('ECL_EUR','sum')).reset_index(); x['Ekspozicija']=x['Ekspozicija'].map(euro); x['Vidutinė rizika']=x['Vidutinė_rizika'].map(pct); x['Tikėtinas nuostolis']=x['Tikėtinas_nuostolis'].map(euro); st.dataframe(x,hide_index=True,use_container_width=True)

elif page == 'Migracija ir vintage':
    section('Migracija ir vintage','Kaip paskolos pereina tarp rizikos būsenų ir kaip elgiasi skirtingų suteikimo laikotarpių portfeliai.')
    hist=snap.sort_values(['Loan_ID','Snapshot_Date']).copy(); hist['Previous_Stage']=hist.groupby('Loan_ID').IFRS9_Stage.shift(1); mig=hist.dropna(subset=['Previous_Stage']); mig=mig[mig.Previous_Stage.ne(mig.IFRS9_Stage)]
    a,b=st.columns(2)
    with a:
        section('Rizikos etapų migracijos')
        x=mig.groupby(['Previous_Stage','Stage']).size().reset_index(name='Atvejų skaičius'); x['Migracija']=x.Previous_Stage+' → '+x.IFRS9_Stage; x=x.sort_values('Atvejų skaičius',ascending=False).head(12); st.dataframe(x[['Migracija','Atvejų skaičius']],hide_index=True,use_container_width=True)
    with b:
        section('Paskolų rizikos etapų perėjimai')
        x=mig.groupby('Snapshot_Date').size().reset_index(name='Perėjimai'); fig=px.line(x,x='Snapshot_Date',y='Perėjimai',markers=True); st.plotly_chart(chart_layout(fig),use_container_width=True)
    section('Vintage analizė')
    vint=loans.copy(); vint['Suteikimo_metai']=vint.Origination_Date.dt.year; v=vint.merge(defaults[['Loan_ID','Default_Date']],on='Loan_ID',how='left'); v['Default']=v.Default_Date.notna(); x=v.groupby('Suteikimo_metai').agg(Paskolos=('Loan_ID','count'),Pradinė_suma=('Initial_Amount','sum'),Default_rate=('Default','mean')).reset_index(); x['Pradinė suma']=x.Pradinė_suma.map(euro); x['Default_rate']=x['Default_rate'].map(pct); st.dataframe(x,hide_index=True,use_container_width=True)
    fig=px.line(x,x='Suteikimo_metai',y='Default_rate',markers=True); fig.update_yaxes(tickformat='.0%'); st.plotly_chart(chart_layout(fig),use_container_width=True)

elif page == 'Užstatas ir koncentracija':
    section('Užstatas ir koncentracija','Užstato pakankamumas ir portfelio koncentracija pagal klientą, produktą ir sektorių.')
    ls=base_snap.merge(loans[['Loan_ID','Customer_Segment']],on='Loan_ID',how='left',suffixes=('','_loan'))
    a,b=st.columns(2)
    with a:
        section('Paskolos ir užstato vertės santykis')
        x=ls.copy(); fig=px.histogram(x,x='Current_LTV',nbins=20); fig.update_xaxes(tickformat='.0%'); st.plotly_chart(chart_layout(fig),use_container_width=True)
    with b:
        section('Aukšto paskolos ir užstato vertės santykio dalis')
        x=ls.assign(GTV=pd.cut(ls.Current_LTV,bins=[-1,.7,.8,.9,1.0,99],labels=['iki 70%','70–80%','80–90%','90–100%','daugiau kaip 100%'])).groupby('GTV',observed=False).EAD_EUR.sum().reset_index(); fig=px.bar(x,x='GTV',y='EAD_EUR',text='EAD_EUR'); st.plotly_chart(chart_layout(fig),use_container_width=True)
    section('Didžiausios klientų koncentracijos')
    x=ls.groupby('Customer_ID').EAD_EUR.sum().reset_index().sort_values('EAD_EUR',ascending=False); top10=x.head(10).EAD_EUR.sum()/x.EAD_EUR.sum(); card('TOP 10 klientų koncentracija',pct(top10),'Dalis nuo bendro paskolų likučio')
    st.write(''); x=x.head(20); x['Ekspozicija']=x['EAD_EUR'].map(euro); st.dataframe(x[['Customer_ID','Ekspozicija']],hide_index=True,use_container_width=True)

elif page == 'Streso testavimas':
    section('Streso testavimas','Scenarijų analizė, leidžianti įvertinti galimą portfelio pablogėjimą.')
    scen=st.selectbox('Scenarijus',stress['Scenario'].tolist(),index=0)
    srow=stress[stress.Scenario.eq(scen)].iloc[0]
    cols=st.columns(5)
    for c,l,v in zip(cols,['Bendrojo vidaus produkto pokytis','Nedarbo pokytis','Būsto kainų pokytis','Palūkanų normos pokytis','Infliacijos pokytis'],[pct(srow.GDP_Shock_pp),f"{srow.Unemployment_Shock_pp:.1f} p. p.",pct(srow.House_Price_Shock_pct),f"{srow.EURIBOR_Shock_pp:.1f} p. p.",pct(srow.GDP_Shock_pp)]):
        with c: card(l,v,'Scenarijaus prielaida')
    # simple transparent stress overlay
    stress_multiplier = 1 + max(0,srow.Unemployment_Shock_pp)*0.06 + max(0,-srow.House_Price_Shock_pct)*0.45 + max(0,srow.EURIBOR_Shock_pp)*0.05
    stressed_pd = np.minimum(base_snap.PD_12M * stress_multiplier, 0.99)
    stressed_ecl = (stressed_pd * base_snap.LGD * base_snap.EAD_EUR).sum()
    a,b,c=st.columns(3)
    with a: card('Esamas tikėtinas nuostolis',euro(base_snap.ECL_EUR.sum()))
    with b: card('Stresinis tikėtinas nuostolis',euro(stressed_ecl))
    with c: card('Nuostolio padidėjimas',pct((stressed_ecl/base_snap.ECL_EUR.sum()-1) if base_snap.ECL_EUR.sum() else np.nan))
    section('Streso poveikis pagal produktą')
    tmp=base_snap.copy(); tmp['Stresinis_PD']=stressed_pd; tmp['Stresinis_ECL']=tmp.Stresinis_PD*tmp.LGD*tmp.EAD_EUR
    x=tmp.groupby('Product_Name').agg(Esamas=('ECL_EUR','sum'),Stresinis=('Stresinis_ECL','sum')).reset_index(); long=x.melt('Product_Name',var_name='Rodiklis',value_name='Nuostolis'); fig=px.bar(long,x='Product_Name',y='Nuostolis',color='Rodiklis',barmode='group'); st.plotly_chart(chart_layout(fig),use_container_width=True)

elif page == 'Paskolų paieška':
    section('Paskolų paieška','Filtruokite paskolas ir atsidarykite analizei tinkamą detalų vaizdą.')
    c1,c2,c3,c4=st.columns(4)
    with c1: stage_sel=st.multiselect('Rizikos etapas',sorted(base_snap.IFRS9_Stage.dropna().unique()),default=sorted(base_snap.IFRS9_Stage.dropna().unique()))
    with c2: min_pd=st.number_input('Mažiausia įsipareigojimų nevykdymo tikimybė',0.0,1.0,0.0,0.01)
    with c3: min_ltv=st.number_input('Mažiausias paskolos ir užstato vertės santykis',0.0,2.0,0.0,0.05)
    with c4: min_dpd=st.number_input('Mažiausias vėlavimas dienomis',0,365,0,1)
    x=base_snap[base_snap.IFRS9_Stage.isin(stage_sel) & (base_snap.PD_12M>=min_pd) & (base_snap.Current_LTV>=min_ltv) & (base_snap.DPD_Days>=min_dpd)].copy()
    x=x.merge(loans[['Loan_ID','Origination_Date']],on='Loan_ID',how='left')
    x=x[['Loan_ID','Customer_ID','Product_Name','Customer_Segment','EAD_EUR','PD_12M','LGD','Current_LTV','Stage','DPD_Days','ECL_EUR','Origination_Date']].sort_values(['PD_12M','EAD_EUR'],ascending=False)
    st.caption(f'Rasta paskolų: {len(x):,}')
    y=x.copy();
    for c in ['EAD_EUR','ECL_EUR']: y[c]=y[c].map(euro)
    for c in ['PD_12M','LGD','Current_LTV']: y[c]=y[c].map(pct)
    y.columns=['Paskola','Klientas','Produktas','Segmentas','Paskolos likutis','Įsipareigojimų nevykdymo tikimybė','Nuostolio dydis nevykdymo atveju','Paskolos ir užstato vertės santykis','Rizikos etapas','Vėlavimas dienomis','Tikėtinas kredito nuostolis','Suteikimo data']
    st.dataframe(y,use_container_width=True,hide_index=True)


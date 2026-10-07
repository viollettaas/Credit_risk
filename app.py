# -*- coding: utf-8 -*-
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='Kredito rizikos stebėsena', page_icon='🏦', layout='wide', initial_sidebar_state='expanded')

DATA_PATH = Path(__file__).with_name('credit_risk_test_data.xlsx')
BANK_ID = 'B01'

CSS = '''
<style>
.stApp{background:#ffffff}
.block-container{padding:1.15rem 2rem 2rem;max-width:100%!important}
section[data-testid="stSidebar"]{background:radial-gradient(circle at top left,#0c356b 0%,#061d3a 38%,#03162d 100%)!important;min-width:350px!important;max-width:350px!important}
section[data-testid="stSidebar"]>div{padding:16px 18px 24px}
section[data-testid="stSidebar"] *{color:#ffffff}
section[data-testid="stSidebar"] input{color:#061b34!important;-webkit-text-fill-color:#061b34!important;background:#fff!important}
.sidebar-title{font-size:22px;font-weight:900}.sidebar-sub{color:#b8c9df!important;font-size:13px;margin:4px 0 20px}
.side-card{background:rgba(255,255,255,.055);border:1px solid rgba(157,190,230,.28);border-radius:17px;padding:16px;margin:14px 0 20px}
.page-title{font-size:30px;font-weight:950;color:#092545;margin-bottom:2px}.page-sub{color:#64748b;font-size:14px;margin-bottom:18px}
.section{font-size:20px;font-weight:900;color:#0b2a4d;margin:24px 0 4px}.section-sub{color:#64748b;font-size:13px;margin-bottom:12px;line-height:1.45}
.kpi{background:#fff;border:1px solid #e4eaf2;border-radius:18px;padding:16px 17px;box-shadow:0 9px 26px rgba(3,22,45,.07);min-height:112px}
.kpi-l{font-size:11px;font-weight:850;color:#64748b;text-transform:uppercase;letter-spacing:.035em}.kpi-v{font-size:27px;font-weight:950;color:#092545;margin-top:5px}.kpi-n{font-size:12px;color:#64748b;margin-top:3px}
.chart-help{background:#f6f9fd;border:1px solid #e0e8f3;border-left:4px solid #1478ff;border-radius:14px;padding:12px 15px;margin:8px 0 12px;color:#334155;font-size:13px;line-height:1.5}
.warn{background:#fff8e8;border:1px solid #f5dda3;border-left:4px solid #e8a317;border-radius:14px;padding:14px 16px;margin:8px 0;color:#614715}
.danger{background:#fff1f1;border:1px solid #f1c5c5;border-left:4px solid #d84a4a;border-radius:14px;padding:14px 16px;margin:8px 0;color:#7d2626}
.good{background:#eefbf5;border:1px solid #bfe8d5;border-left:4px solid #19a66b;border-radius:14px;padding:14px 16px;margin:8px 0;color:#185c42}
[data-testid="stDataFrame"]{border:1px solid #e4eaf2;border-radius:14px;overflow:hidden}
div[data-testid="stPlotlyChart"]{border:1px solid #edf1f6;border-radius:18px;padding:8px;background:#fff;box-shadow:0 6px 20px rgba(3,22,45,.04)}
.small-note{font-size:12px;color:#64748b}
</style>
'''
st.markdown(CSS, unsafe_allow_html=True)


def find_data_file():
    candidates = [DATA_PATH, Path.cwd() / DATA_PATH.name]
    for p in candidates:
        if p.exists():
            return p
    root = Path(__file__).resolve().parent
    xs = [p for p in root.glob('*.xlsx') if not p.name.startswith('~$')]
    preferred = [p for p in xs if 'credit' in p.name.lower()]
    if preferred:
        return preferred[0]
    if len(xs) == 1:
        return xs[0]
    return None


@st.cache_data(show_spinner=False)
def load_data():
    p = find_data_file()
    if p is None:
        raise FileNotFoundError('Nerastas credit_risk_test_data.xlsx. Įkelk jį į tą patį GitHub katalogą kaip app.py.')
    xls = pd.ExcelFile(p)
    return {s: pd.read_excel(xls, sheet_name=s) for s in xls.sheet_names}


D = load_data()
loans = D['Loans'].copy()
snapshots = D['Loan_Snapshot'].copy()
customers = D['Customers'].copy()
financials = D['Customer_Financials'].copy()
payments = D['Payments'].copy()
collateral = D['Collateral'].copy()
ratings = D['Risk_Ratings'].copy()
defaults = D['Default_Events'].copy()
collections = D['Collections'].copy()
underwriting = D['Underwriting'].copy()
events = D['Loan_Events'].copy()
macro = D['Macro'].copy()
stress = D['Stress_Scenarios'].copy()
risk_appetite = D.get('Risk_Appetite', pd.DataFrame())

for df, cols in [
    (snapshots,['Snapshot_Date']), (financials,['Snapshot_Date']), (payments,['Due_Date']),
    (ratings,['Rating_Date']), (defaults,['Default_Date']), (events,['Event_Date']),
    (collections,['Event_Date']), (underwriting,['Application_Date']), (macro,['Snapshot_Date']),
    (loans,['Origination_Date','Maturity_Date'])
]:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors='coerce')

# One-bank portfolio
bank_loan_ids = set(loans.loc[loans['Bank_ID'].astype(str).eq(BANK_ID), 'Loan_ID'].astype(str))
loans = loans[loans['Loan_ID'].astype(str).isin(bank_loan_ids)].copy()
snapshots = snapshots[snapshots['Loan_ID'].astype(str).isin(bank_loan_ids)].copy()
ratings = ratings[ratings['Loan_ID'].astype(str).isin(bank_loan_ids)].copy()
defaults = defaults[defaults['Loan_ID'].astype(str).isin(bank_loan_ids)].copy()
underwriting = underwriting[underwriting['Loan_ID'].astype(str).isin(bank_loan_ids)].copy()
events = events[events['Loan_ID'].astype(str).isin(bank_loan_ids)].copy()
payments = payments[payments['Loan_ID'].astype(str).isin(bank_loan_ids)].copy()
collateral = collateral[collateral['Loan_ID'].astype(str).isin(bank_loan_ids)].copy()
collections = collections[collections['Loan_ID'].astype(str).isin(bank_loan_ids)].copy()
bank_customer_ids = set(loans['Customer_ID'].astype(str))
customers = customers[customers['Customer_ID'].astype(str).isin(bank_customer_ids)].copy()
financials = financials[financials['Customer_ID'].astype(str).isin(bank_customer_ids)].copy()

latest_date = snapshots['Snapshot_Date'].max()
if pd.isna(latest_date):
    st.error('Nėra galiojančios stebėjimo datos paskolų duomenyse.')
    st.stop()
latest = snapshots[snapshots['Snapshot_Date'].eq(latest_date)].copy()

STAGE_LABEL = {1:'Pirmas kredito rizikos etapas', 2:'Antras kredito rizikos etapas', 3:'Trečias kredito rizikos etapas'}
latest['Kredito rizikos etapas'] = latest['IFRS9_Stage'].map(STAGE_LABEL).fillna(latest['IFRS9_Stage'].astype(str))
snapshots['Kredito rizikos etapas'] = snapshots['IFRS9_Stage'].map(STAGE_LABEL).fillna(snapshots['IFRS9_Stage'].astype(str))

BLUE='#1478ff'; NAVY='#092545'; RED='#d84a4a'; AMBER='#e8a317'; GREEN='#19a66b'

def eur(x):
    if pd.isna(x): return '–'
    if abs(x) >= 1_000_000: return f'€{x/1_000_000:,.1f} mln.'
    if abs(x) >= 1_000: return f'€{x/1_000:,.0f} tūkst.'
    return f'€{x:,.0f}'

def pct(x, digits=1):
    return '–' if pd.isna(x) else f'{100*x:.{digits}f} %'

def kpi(label,value,note=''):
    st.markdown(f'<div class="kpi"><div class="kpi-l">{label}</div><div class="kpi-v">{value}</div><div class="kpi-n">{note}</div></div>', unsafe_allow_html=True)

def title(t,s):
    st.markdown(f'<div class="page-title">{t}</div><div class="page-sub">{s}</div>', unsafe_allow_html=True)

def section(t,s=''):
    st.markdown(f'<div class="section">{t}</div><div class="section-sub">{s}</div>', unsafe_allow_html=True)

def explain(text):
    st.markdown(f'<div class="chart-help">{text}</div>', unsafe_allow_html=True)

def style_fig(fig, height=390):
    fig.update_layout(height=height, margin=dict(l=15,r=15,t=55,b=15), paper_bgcolor='white', plot_bgcolor='white', font=dict(family='Arial', color='#334155'), legend_title_text='', hoverlabel=dict(bgcolor='white'))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor='#edf1f6')
    return fig

def weighted_average(df, value, weight='EAD_EUR'):
    z = df[[value,weight]].dropna()
    return np.average(z[value], weights=z[weight]) if len(z) and z[weight].sum() > 0 else np.nan

def latest_per_loan(df):
    x = df.sort_values(['Loan_ID','Snapshot_Date']).drop_duplicates('Loan_ID', keep='last')
    return x

with st.sidebar:
    st.markdown('<div class="sidebar-title">🏦 Kredito rizikos stebėsena</div><div class="sidebar-sub">Vieno banko paskolų portfelio analizė</div>', unsafe_allow_html=True)
    page = st.radio('Ataskaita', ['Vadovybės apžvalga','Asmens profilis','Kredito portfelio rizika','Rizikos dinamika ir scenarijai'], label_visibility='collapsed')
    st.markdown(f'<div class="side-card"><b>Ataskaitos data</b><br><span style="color:#b8c9df">{latest_date:%Y-%m-%d}</span><br><br><b>Aktyvios paskolos</b><br><span style="color:#b8c9df">{len(latest):,}</span></div>', unsafe_allow_html=True)

# Core KPIs
latest_ead = latest['EAD_EUR'].sum()
stage2_ratio = latest.loc[latest['IFRS9_Stage'].eq(2),'EAD_EUR'].sum()/latest_ead if latest_ead else np.nan
stage3_ratio = latest.loc[latest['IFRS9_Stage'].eq(3),'EAD_EUR'].sum()/latest_ead if latest_ead else np.nan
npl_ratio = latest.loc[latest['DPD_Days'].ge(90),'EAD_EUR'].sum()/latest_ead if latest_ead else np.nan
ecl = latest['ECL_EUR'].sum()
avg_pd = weighted_average(latest,'PD_12M')
avg_ltv = weighted_average(latest,'Current_LTV')

if page == 'Vadovybės apžvalga':
    title('Vadovybės kredito rizikos apžvalga','Pagrindinis ekranas: kas yra rizikinga, kur rizika auga ir kur reikia vadovybės dėmesio.')
    cols=st.columns(6)
    vals=[
        ('Kredito pozicija',eur(latest_ead),f'{latest["Loan_ID"].nunique():,} paskolų'),
        ('Antras kredito rizikos etapas',pct(stage2_ratio),'portfelio pagal kredito poziciją'),
        ('Trečias kredito rizikos etapas',pct(stage3_ratio),'portfelio pagal kredito poziciją'),
        ('Daugiau kaip 90 dienų vėluojanti dalis',pct(npl_ratio),'portfelio pagal kredito poziciją'),
        ('Tikėtinas kredito nuostolis',eur(ecl),pct(ecl/latest_ead) if latest_ead else '–'),
        ('Vidutinė įsipareigojimų nevykdymo tikimybė',pct(avg_pd),'svertinė pagal kredito poziciją')]
    for c,v in zip(cols,vals):
        with c:kpi(*v)

    section('1. Ar kredito kokybė blogėja?','Vadovybei svarbiausia matyti ne vien dabartinę situaciją, bet kryptį. Šis grafikas rodo tris pagrindinius ankstyvo ir vėlyvo pablogėjimo signalus.')
    monthly = snapshots.groupby('Snapshot_Date',as_index=False).apply(lambda g: pd.Series({
        'Antro etapo dalis': g.loc[g.IFRS9_Stage.eq(2),'EAD_EUR'].sum()/g.EAD_EUR.sum(),
        'Trečio etapo dalis': g.loc[g.IFRS9_Stage.eq(3),'EAD_EUR'].sum()/g.EAD_EUR.sum(),
        'Daugiau kaip 90 dienų vėlavimo dalis': g.loc[g.DPD_Days.ge(90),'EAD_EUR'].sum()/g.EAD_EUR.sum(),
    }), include_groups=False).reset_index()
    long = monthly.melt('Snapshot_Date', var_name='Rodiklis', value_name='Dalis')
    fig=px.line(long,x='Snapshot_Date',y='Dalis',color='Rodiklis',markers=True,title='Kredito kokybės blogėjimo signalai laikui bėgant')
    fig.update_yaxes(tickformat='.1%',title='Portfelio dalis')
    st.plotly_chart(style_fig(fig,410),use_container_width=True)
    explain('Kaip skaityti: jei antras etapas didėja anksčiau nei trečias etapas ir daugiau kaip 90 dienų vėlavimai, tai reiškia, kad rizika pradeda didėti dar prieš paskoloms tampant probleminėmis. Tai vienas svarbiausių stebėjimų vadovybei. ECB kredito rizikos metodikoje atskirai vertinama portfelio kokybės raida, antras etapas, pradelstos pozicijos ir jų dinamika. citeturn511280view0')

    section('2. Kur bankas turi daugiausia rizikos?','Rodome ne tik rizikingumo procentą, bet ir kredito pozicijos dydį. Didelė rizika mažame portfelyje ir didelė rizika dideliame portfelyje nėra tas pats.')
    prod=latest.groupby('Product_Code',as_index=False).agg(Kredito_pozicija=('EAD_EUR','sum'), Problemines=('EAD_EUR',lambda x:0))
    prod['Problemines']=latest.groupby('Product_Code').apply(lambda g:g.loc[g.IFRS9_Stage.eq(3),'EAD_EUR'].sum(),include_groups=False).values
    prod['Probleminiu_dalis']=prod['Problemines']/prod['Kredito_pozicija']
    prod=prod.merge(D['Products'][['Product_Code','Product_Name']],on='Product_Code',how='left').sort_values('Kredito_pozicija',ascending=False)
    fig=px.scatter(prod,x='Kredito_pozicija',y='Probleminiu_dalis',size='Kredito_pozicija',text='Product_Name',title='Produktų rizikos žemėlapis',labels={'Kredito_pozicija':'Kredito pozicija, eurais','Probleminiu_dalis':'Trečio etapo dalis'})
    fig.update_yaxes(tickformat='.1%')
    fig.update_traces(textposition='top center')
    st.plotly_chart(style_fig(fig,410),use_container_width=True)
    explain('Kaip skaityti: dešinėje esantys burbulai yra dideli portfeliai; kylantys aukštyn – rizikingesni portfeliai. Viršutiniame dešiniajame kampe esantis produktas būtų prioritetinė vadovybės rizikos tema. ECB ir Bazelio komiteto kredito rizikos analizė remiasi portfelio sudėtimi, rizikos kokybe ir rizikos parametrais. citeturn511280view0turn511280view2')

    section('3. Kur atsiranda nauja rizika?','Ši lentelė skirta ne visoms paskoloms, o toms, kurių dabartiniai rodikliai jau signalizuoja apie galimą problemą.')
    risk=latest.copy()
    risk['Rizikos balas']=risk['IFRS9_Stage']*30+risk['PD_12M']*100+risk['DPD_Days'].clip(upper=180)/6+risk['Current_LTV'].fillna(0)*10
    risk=risk.sort_values(['Rizikos balas','EAD_EUR'],ascending=False).head(15).merge(loans[['Loan_ID','Product_Name','Region']],on='Loan_ID',how='left')
    st.dataframe(risk[['Loan_ID','Customer_ID','Product_Name','Region','EAD_EUR','IFRS9_Stage','DPD_Days','PD_12M','Current_LTV','ECL_EUR']].rename(columns={
        'Loan_ID':'Paskola','Customer_ID':'Klientas','Product_Name':'Produktas','Region':'Regionas','EAD_EUR':'Kredito pozicija','IFRS9_Stage':'Kredito rizikos etapas','DPD_Days':'Vėlavimo dienos','PD_12M':'Įsipareigojimų nevykdymo tikimybė','Current_LTV':'Paskolos ir užstato vertės santykis','ECL_EUR':'Tikėtinas kredito nuostolis'}),use_container_width=True,hide_index=True)

elif page == 'Asmens profilis':
    title('Asmens profilis','Vieno kliento „360°“ vaizdas: finansinė padėtis, paskolos, mokėjimų disciplina ir kredito rizikos pokyčiai.')
    cid_input=st.text_input('Įveskite kliento kodą', value=str(customers['Customer_ID'].iloc[0]) if len(customers) else '')
    cid=str(cid_input).strip()
    cust=customers[customers['Customer_ID'].astype(str).eq(cid)]
    if cust.empty:
        st.warning('Tokio kliento testiniuose duomenyse nerasta.')
    else:
        c=cust.iloc[0]
        cust_loans=loans[loans['Customer_ID'].astype(str).eq(cid)].copy()
        cust_latest=latest[latest['Customer_ID'].astype(str).eq(cid)].copy()
        cust_fin=financials[financials['Customer_ID'].astype(str).eq(cid)].sort_values('Snapshot_Date').copy()
        cols=st.columns(6)
        metrics=[('Klientų segmentas',c['Customer_Segment'],f'Regionas: {c["Region"]}'),('Amžius',f'{int(c["Age"])} m.', 'pagal kliento duomenis'),('Metinės pajamos',eur(c['Annual_Income_EUR']),'deklaruotos'),('Paskolų skaičius',f'{len(cust_loans):,}','banko portfelyje'),('Likusi kredito pozicija',eur(cust_latest['EAD_EUR'].sum()),'dabartinė'),('Vidutinė įsipareigojimų nevykdymo tikimybė',pct(weighted_average(cust_latest,'PD_12M')), 'svertinė pagal poziciją')]
        for col,v in zip(cols,metrics):
            with col:kpi(*v)
        c1,c2=st.columns(2)
        with c1:
            section('Finansinės padėties dinamika','Šis grafikas atsako į klausimą: ar kliento pajėgumas aptarnauti skolą gerėja, ar blogėja?')
            if not cust_fin.empty:
                fig=go.Figure()
                fig.add_trace(go.Scatter(x=cust_fin['Snapshot_Date'],y=cust_fin['Annual_Income_EUR'],mode='lines+markers',name='Metinės pajamos'))
                fig.add_trace(go.Scatter(x=cust_fin['Snapshot_Date'],y=cust_fin['Total_Debt_EUR'],mode='lines+markers',name='Bendra skola'))
                fig.update_layout(title='Pajamų ir bendros skolos pokytis',yaxis_title='Eurai')
                st.plotly_chart(style_fig(fig,370),use_container_width=True)
                explain('Jeigu skola kyla tuo metu, kai pajamos mažėja, finansinė padėtis blogėja. Tai svarbiau už vienkartinį kredito balą.')
        with c2:
            section('Mokėjimų elgsena','Rodoma, ar klientas pradeda vėluoti ir ar vėlavimai ilgėja.')
            pay=payments[payments['Customer_ID'].astype(str).eq(cid)].copy()
            if not pay.empty:
                paym=pay.groupby(pay['Due_Date'].dt.to_period('M'),as_index=False).agg(Vėlavimo_dienos=('Days_Late','mean'),Vėluojančių_mokėjimų_dalis=('Days_Late',lambda x:(x>0).mean()))
                paym['Mėnuo']=paym['Due_Date'].astype(str)
                fig=px.bar(paym,x='Mėnuo',y='Vėlavimo_dienos',title='Vidutinis mokėjimo vėlavimas pagal mėnesį')
                st.plotly_chart(style_fig(fig,370),use_container_width=True)
                explain('Didėjantis vidutinis vėlavimas yra ankstyvas įspėjimo signalas. Ypač svarbu, jei vėliau klientas pereina į aukštesnį kredito rizikos etapą.')
        section('Kliento paskolos','Visos kliento paskolos su dabartine rizikos būsena.')
        table=cust_latest.merge(loans[['Loan_ID','Product_Name','Origination_Date','Original_Amount_EUR']],on='Loan_ID',how='left')
        st.dataframe(table[['Loan_ID','Product_Name','Origination_Date','Original_Amount_EUR','EAD_EUR','IFRS9_Stage','DPD_Days','PD_12M','LGD','Current_LTV','ECL_EUR']].rename(columns={
            'Loan_ID':'Paskola','Product_Name':'Produktas','Origination_Date':'Suteikimo data','Original_Amount_EUR':'Pradinė paskolos suma','EAD_EUR':'Kredito pozicija','IFRS9_Stage':'Kredito rizikos etapas','DPD_Days':'Vėlavimo dienos','PD_12M':'Įsipareigojimų nevykdymo tikimybė','LGD':'Nuostolio dalis įsipareigojimų nevykdymo atveju','Current_LTV':'Paskolos ir užstato vertės santykis','ECL_EUR':'Tikėtinas kredito nuostolis'}),use_container_width=True,hide_index=True)
        section('Automatiniai rizikos signalai','Signalai padeda greitai nuspręsti, ar klientą verta papildomai peržiūrėti.')
        alerts=[]
        if (cust_latest['DPD_Days']>=30).any(): alerts.append(('danger','Klientas turi paskolą, kurios mokėjimai vėluoja 30 ar daugiau dienų.'))
        if (cust_latest['IFRS9_Stage']==2).any(): alerts.append(('warn','Bent viena paskola yra antrame kredito rizikos etape.'))
        if (cust_latest['IFRS9_Stage']==3).any(): alerts.append(('danger','Bent viena paskola yra trečiame kredito rizikos etape.'))
        if (cust_latest['Current_LTV']>0.9).any(): alerts.append(('warn','Bent vienos paskolos paskolos ir užstato vertės santykis viršija 90 procentų.'))
        if not cust_fin.empty and len(cust_fin)>=2:
            latest_fin=cust_fin.iloc[-1]; prev_fin=cust_fin.iloc[-2]
            if prev_fin['Annual_Income_EUR'] and latest_fin['Annual_Income_EUR']/prev_fin['Annual_Income_EUR']-1 < -0.1: alerts.append(('warn','Metinės pajamos per paskutinį stebėjimo laikotarpį sumažėjo daugiau kaip 10 procentų.'))
        if not alerts: alerts=[('good','Reikšmingų automatiškai aptiktų rizikos signalų nėra.')]
        for typ,msg in alerts:
            st.markdown(f'<div class="{typ}">{msg}</div>',unsafe_allow_html=True)

elif page == 'Kredito portfelio rizika':
    title('Kredito portfelio rizika','Portfelio sudėtis, paskolų suteikimo kokybė, užstatas ir rizikos koncentracija.')
    cols=st.columns(5)
    vals=[('Kredito pozicija',eur(latest_ead),'dabartinis portfelis'),('Probleminių paskolų dalis',pct(stage3_ratio),'trečias kredito rizikos etapas'),('Antras kredito rizikos etapas',pct(stage2_ratio),'ankstyvas pablogėjimo signalas'),('Vidutinis paskolos ir užstato vertės santykis',pct(avg_ltv),'svertinis pagal poziciją'),('Tikėtino kredito nuostolio dalis',pct(ecl/latest_ead),'nuo kredito pozicijos')]
    for c,v in zip(cols,vals):
        with c:kpi(*v)

    section('1. Kur rizika susikaupusi pagal produktą?','Palyginame portfelio dydį su probleminių paskolų dalimi. Taip išvengiame klaidos vertinti riziką vien pagal procentą.')
    p=latest.merge(D['Products'][['Product_Code','Product_Name']],on='Product_Code',how='left')
    p=p.groupby('Product_Name').apply(lambda g: pd.Series({'Kredito pozicija':g.EAD_EUR.sum(),'Probleminių paskolų dalis':g.loc[g.IFRS9_Stage.eq(3),'EAD_EUR'].sum()/g.EAD_EUR.sum(),'Antro etapo dalis':g.loc[g.IFRS9_Stage.eq(2),'EAD_EUR'].sum()/g.EAD_EUR.sum()}),include_groups=False).reset_index().sort_values('Kredito pozicija',ascending=False)
    fig=px.bar(p,x='Product_Name',y='Kredito pozicija',color='Probleminių paskolų dalis',title='Kredito pozicija pagal produktą',labels={'Product_Name':'Produktas','Kredito pozicija':'Eurai','Probleminių paskolų dalis':'Trečio etapo dalis'},color_continuous_scale=['#dff3ea','#f5e6b0','#f1c5c5'])
    st.plotly_chart(style_fig(fig,410),use_container_width=True)
    explain('Kaip skaityti: stulpelio aukštis parodo, kiek pinigų bankas turi konkrečiame produkte; spalvos intensyvumas parodo, kiek to produkto pozicijos jau yra trečiame etape. Tai leidžia vienu metu matyti dydį ir riziką. ECB viešose priežiūros statistikose taip pat skelbiami probleminių paskolų dydžiai ir jų pjūviai pagal sektorių. citeturn562348search4')

    section('2. Ar pradinio paskolos vertinimo kokybė paaiškina dabartinę riziką?','Tai svarbus kredito suteikimo kontrolės testas: ar paskolos, kurioms jau suteikiant buvo didesnė finansinė našta, dažniau tampa probleminėmis?')
    uw=underwriting.merge(latest[['Loan_ID','IFRS9_Stage','EAD_EUR']],on='Loan_ID',how='inner').copy()
    c1,c2=st.columns(2)
    with c1:
        uw['Skolos naštos grupė']=uw['Debt_To_Income_Band'].astype(object)
        tmp=uw.groupby('Skolos naštos grupė',observed=False).apply(lambda g:pd.Series({'Probleminių paskolų dalis':g.loc[g.IFRS9_Stage.eq(3),'EAD_EUR'].sum()/g.EAD_EUR.sum() if g.EAD_EUR.sum() else np.nan}),include_groups=False).reset_index()
        fig=px.bar(tmp,x='Skolos naštos grupė',y='Probleminių paskolų dalis',title='Probleminių paskolų dalis pagal pradinę skolos naštą')
        fig.update_yaxes(tickformat='.1%',title='Trečio etapo dalis pagal kredito poziciją')
        st.plotly_chart(style_fig(fig,370),use_container_width=True)
        explain('Kaip skaityti: jeigu dešinėje esančios grupės turi daug didesnę probleminių paskolų dalį, tai rodo, kad didelė skolos našta suteikimo metu yra susijusi su vėlesniu kredito pablogėjimu.')
    with c2:
        uw['Pradinio kredito balo grupė']=pd.cut(uw['Credit_Score'],bins=[0,550,600,650,700,750,1000],labels=['Iki 550','550–599','600–649','650–699','700–749','750 ir daugiau'],right=False,ordered=False).astype(object)
        tmp=uw.groupby('Pradinio kredito balo grupė',observed=False).apply(lambda g:pd.Series({'Probleminių paskolų dalis':g.loc[g.IFRS9_Stage.eq(3),'EAD_EUR'].sum()/g.EAD_EUR.sum() if g.EAD_EUR.sum() else np.nan}),include_groups=False).reset_index()
        fig=px.bar(tmp,x='Pradinio kredito balo grupė',y='Probleminių paskolų dalis',title='Probleminių paskolų dalis pagal pradinį kredito balą')
        fig.update_yaxes(tickformat='.1%',title='Trečio etapo dalis pagal kredito poziciją')
        st.plotly_chart(style_fig(fig,370),use_container_width=True)
        explain('Kaip skaityti: geras kredito balas turėtų būti susijęs su mažesne vėlesne rizika. Jei kreivė tokio ryšio nerodo, verta tikrinti kredito vertinimo modelį arba duomenų kokybę.')

    section('3. Koncentracija: kur vienas netikėtas smūgis galėtų labiausiai paveikti banką?','Koncentracijos analizė paprastai atliekama pagal klientus, sektorius, regionus, produktus ir užstato rūšis. ECB metodika aiškiai išskiria vieno kliento, sektoriaus, regiono ir kitų rizikos veiksnių koncentraciją. citeturn511280view0')
    c1,c2=st.columns(2)
    with c1:
        cust_con=latest.groupby('Customer_ID',as_index=False)['EAD_EUR'].sum().sort_values('EAD_EUR',ascending=False).head(15)
        cust_con['Klientas']=cust_con['Customer_ID'].astype(str)
        fig=px.bar(cust_con,x='Klientas',y='EAD_EUR',title='Didžiausios vieno kliento kredito pozicijos',labels={'EAD_EUR':'Kredito pozicija, eurais'})
        st.plotly_chart(style_fig(fig,370),use_container_width=True)
        explain('Kaip skaityti: kuo aukštesnis stulpelis, tuo didesnė vieno kliento įtaka portfeliui. Tai padeda matyti vieno vardo koncentracijos riziką.')
    with c2:
        reg=latest.groupby('Region',as_index=False)['EAD_EUR'].sum().sort_values('EAD_EUR',ascending=False)
        fig=px.pie(reg,names='Region',values='EAD_EUR',hole=.55,title='Kredito pozicijos pasiskirstymas pagal regioną')
        st.plotly_chart(style_fig(fig,370),use_container_width=True)
        explain('Kaip skaityti: didelė vieno regiono dalis reiškia, kad tam regionui nepalankus ekonominis ar nekilnojamojo turto pokytis galėtų turėti neproporcingą poveikį bankui.')

elif page == 'Rizikos dinamika ir scenarijai':
    title('Rizikos dinamika ir scenarijai','Paskolų migracija, suteikimo kartos, užstato atsparumas ir ekonominio pablogėjimo scenarijai.')

    section('1. Kas iš tikrųjų blogėja?','Migracija parodo, kiek kredito pozicijos persikelia į blogesnę ar geresnę rizikos būseną. Tai informatyviau nei vien dabartinė trečio etapo dalis.')
    dates=sorted(pd.Series(snapshots['Snapshot_Date'].dropna().unique()).tolist())
    if len(dates)>=2:
        prev_date=dates[-2]; cur_date=dates[-1]
        prev=snapshots[snapshots['Snapshot_Date'].eq(prev_date)][['Loan_ID','IFRS9_Stage']].rename(columns={'IFRS9_Stage':'Ankstesnis etapas'})
        cur=latest[['Loan_ID','IFRS9_Stage','EAD_EUR']].rename(columns={'IFRS9_Stage':'Dabartinis etapas'})
        mig=prev.merge(cur,on='Loan_ID',how='inner')
        mig['Ankstesnis etapas']=mig['Ankstesnis etapas'].map(STAGE_LABEL).fillna(mig['Ankstesnis etapas'].astype(str))
        mig['Dabartinis etapas']=mig['Dabartinis etapas'].map(STAGE_LABEL).fillna(mig['Dabartinis etapas'].astype(str))
        matrix=mig.pivot_table(index='Ankstesnis etapas',columns='Dabartinis etapas',values='EAD_EUR',aggfunc='sum',fill_value=0)
        fig=px.imshow(matrix,aspect='auto',text_auto='.3s',title=f'Kredito pozicijos pasikeitimas nuo {pd.Timestamp(prev_date):%Y-%m-%d} iki {pd.Timestamp(cur_date):%Y-%m-%d}',labels={'x':'Dabartinis etapas','y':'Ankstesnis etapas','color':'Kredito pozicija'})
        st.plotly_chart(style_fig(fig,420),use_container_width=True)
        explain('Kaip skaityti: langeliai įstrižainėje rodo stabilias paskolas. Langeliai į dešinę rodo pablogėjimą, į kairę – pagerėjimą. Didelis pablogėjimo srautas iš pirmo į antrą etapą yra ankstyvas signalas, kurį verta tirti. ECB metodika tiesiogiai akcentuoja kredito rizikos etapų perėjimus ir antro etapo pozicijų raidą. citeturn511280view0')

    section('2. Ar naujesnės paskolos blogesnės už senesnes?','Paskolų suteikimo kartų analizė leidžia palyginti skirtingais metais suteiktų paskolų kokybę.')
    vint=loans[['Loan_ID','Origination_Date']].copy(); vint['Suteikimo metai']=vint['Origination_Date'].dt.year
    vv=latest.merge(vint[['Loan_ID','Suteikimo metai']],on='Loan_ID',how='left')
    vintage=vv.groupby('Suteikimo metai',as_index=False).apply(lambda g:pd.Series({
        'Kredito pozicija':g.EAD_EUR.sum(),
        'Probleminių paskolų dalis':g.loc[g.IFRS9_Stage.eq(3),'EAD_EUR'].sum()/g.EAD_EUR.sum(),
        'Daugiau kaip 90 dienų vėlavimo dalis':g.loc[g.DPD_Days.ge(90),'EAD_EUR'].sum()/g.EAD_EUR.sum()}),include_groups=False).reset_index(drop=True)
    long=vintage.melt('Suteikimo metai',value_vars=['Probleminių paskolų dalis','Daugiau kaip 90 dienų vėlavimo dalis'],var_name='Rodiklis',value_name='Dalis')
    fig=px.line(long,x='Suteikimo metai',y='Dalis',color='Rodiklis',markers=True,title='Rizikos kokybė pagal paskolos suteikimo metus')
    fig.update_yaxes(tickformat='.1%',title='Kredito pozicijos dalis')
    st.plotly_chart(style_fig(fig,410),use_container_width=True)
    explain('Kaip skaityti: jei jaunesnių suteikimo metų linijos yra aukščiau, naujesnės paskolos šiuo metu pasižymi didesne rizika. ECB vertina ne tik NPL dydį, bet ir jo sudėtį pagal paskolų suteikimo kartas. citeturn511280view0turn562348search9')

    section('3. Ką reikštų ekonomikos pablogėjimas?','Streso testas skirtas atsakyti į praktinį klausimą: kiek padidėtų tikėtinas kredito nuostolis, jeigu rizikos parametrai pablogėtų.')
    scenario=st.selectbox('Ekonominis scenarijus',stress['Scenario'].astype(str).tolist(),index=min(2,max(0,len(stress)-1)))
    sc=stress[stress['Scenario'].astype(str).eq(scenario)].iloc[0]
    stressed_pd=(latest['PD_12M']*sc['PD_Multiplier']).clip(upper=1)
    stressed_lgd=(latest['LGD']+sc['LGD_Add']).clip(upper=1)
    stressed_ead=latest['EAD_EUR']*(1+sc['EAD_Growth_pct'])
    stressed_loss=(stressed_pd*stressed_lgd*stressed_ead).sum()
    increase=stressed_loss/ecl-1 if ecl else np.nan
    cols=st.columns(5)
    vals=[('Dabartinis tikėtinas kredito nuostolis',eur(ecl),'dabartinė padėtis'),('Nuostolis po scenarijaus',eur(stressed_loss),scenario),('Nuostolio padidėjimas',pct(increase),'palyginti su dabartiniu'),('Nedarbo lygio šokas',f'{sc["Unemployment_Shock_pp"]:+.1f} proc. punkto','scenarijaus prielaida'),('Būsto kainų šokas',f'{sc["House_Price_Shock_pct"]:+.1%}','scenarijaus prielaida')]
    for c,v in zip(cols,vals):
        with c:kpi(*v)
    stress_df=latest[['Loan_ID','Customer_Segment','EAD_EUR','ECL_EUR']].copy()
    stress_df['Nuostolis po scenarijaus']=stressed_pd*stressed_lgd*stressed_ead
    stress_df['Papildomas nuostolis']=stress_df['Nuostolis po scenarijaus']-stress_df['ECL_EUR']
    seg=stress_df.groupby('Customer_Segment',as_index=False)[['ECL_EUR','Nuostolis po scenarijaus']].sum().melt('Customer_Segment',var_name='Būsena',value_name='Nuostolis')
    seg['Būsena']=seg['Būsena'].replace({'ECL_EUR':'Dabartinis tikėtinas kredito nuostolis'})
    fig=px.bar(seg,x='Customer_Segment',y='Nuostolis',color='Būsena',barmode='group',title='Tikėtino kredito nuostolio palyginimas pagal klientų segmentą',labels={'Customer_Segment':'Klientų segmentas','Nuostolis':'Eurai'})
    st.plotly_chart(style_fig(fig,410),use_container_width=True)
    explain('Kaip skaityti: kiekviename segmente lyginamas dabartinis nuostolis su nuostoliu po pasirinkto scenarijaus. Tai padeda nustatyti, kuris verslo segmentas labiausiai jautrus ekonominiam pablogėjimui. ECB kredito rizikos vertinimas apima forward-looking perspektyvą ir išorinių ekonominių veiksnių poveikį. citeturn511280view0')
    top=stress_df.nlargest(15,'Papildomas nuostolis').merge(loans[['Loan_ID','Product_Name']],on='Loan_ID',how='left')
    st.dataframe(top[['Loan_ID','Product_Name','Customer_Segment','EAD_EUR','ECL_EUR','Nuostolis po scenarijaus','Papildomas nuostolis']].rename(columns={'Loan_ID':'Paskola','Product_Name':'Produktas','Customer_Segment':'Klientų segmentas','EAD_EUR':'Kredito pozicija','ECL_EUR':'Dabartinis tikėtinas kredito nuostolis'}),use_container_width=True,hide_index=True)

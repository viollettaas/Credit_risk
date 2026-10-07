from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

st.set_page_config(page_title='Banko kredito rizikos ataskaita', page_icon='🏦', layout='wide', initial_sidebar_state='expanded')

BASE_DIR = Path(__file__).resolve().parent
EXPECTED_DATA_FILE = 'credit_risk_test_data.xlsx'

CSS = '''
<style>
.stApp{background:#ffffff}
.block-container{padding-top:1.1rem;padding-left:2rem;padding-right:2rem;max-width:100%!important}
section[data-testid="stSidebar"]{background:radial-gradient(circle at top left,#0c356b 0%,#061d3a 35%,#03162d 100%)!important;min-width:330px!important;max-width:330px!important}
section[data-testid="stSidebar"] *{color:#fff}
section[data-testid="stSidebar"] input{color:#061b34!important;background:#fff!important;-webkit-text-fill-color:#061b34!important}
.card{background:#fff;border:1px solid #e5eaf1;border-radius:17px;padding:18px 20px;box-shadow:0 8px 28px rgba(15,42,75,.07);height:100%}
.kpi-title{font-size:12px;color:#65758b;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.kpi-value{font-size:28px;font-weight:900;color:#071a33;margin-top:5px}
.kpi-sub{font-size:13px;color:#65758b;margin-top:5px}
.alert{border-radius:15px;padding:14px 16px;margin-bottom:10px;border:1px solid #e5eaf1;background:#fff}
.alert-red{border-left:5px solid #d14343}.alert-amber{border-left:5px solid #e39a22}.alert-green{border-left:5px solid #14966d}
.alert-title{font-weight:900;color:#071a33}.alert-text{color:#4c5c70;font-size:14px;line-height:1.45;margin-top:3px}
.section-title{font-size:22px;font-weight:900;color:#071a33;margin:8px 0 4px}.section-sub{font-size:14px;color:#65758b;margin-bottom:16px}
.note{background:#f5f8fc;border-left:4px solid #1478ff;border-radius:10px;padding:10px 12px;color:#4c5c70;font-size:13px;margin:8px 0 16px}
</style>'''
st.markdown(CSS, unsafe_allow_html=True)


def find_data_file():
    roots=[]
    for r in (BASE_DIR, Path.cwd()):
        if r.exists() and r not in roots: roots.append(r)
    exact=[]
    for r in roots:
        p=r/EXPECTED_DATA_FILE
        if p.is_file(): exact.append(p)
        try:
            exact += [p for p in r.rglob('*.xlsx') if p.is_file() and p.name.lower()==EXPECTED_DATA_FILE.lower()]
        except Exception: pass
    if exact: return exact[0]
    all_xlsx=[]
    for r in roots:
        try: all_xlsx += [p for p in r.rglob('*.xlsx') if p.is_file() and not p.name.startswith('~$')]
        except Exception: pass
    uniq=[]; seen=set()
    for p in all_xlsx:
        s=str(p.resolve())
        if s not in seen: seen.add(s); uniq.append(p)
    return uniq[0] if len(uniq)==1 else None

@st.cache_data

def load_data():
    p=find_data_file()
    if p is None:
        st.error('Nerastas kredito rizikos duomenų Excel failas. Įkelkite credit_risk_test_data.xlsx į tą patį GitHub projektą kaip app.py.')
        st.stop()
    xl=pd.ExcelFile(p)
    return {s:pd.read_excel(xl,sheet_name=s) for s in xl.sheet_names}

D=load_data()
loans=D.get('Loans',pd.DataFrame()).copy()
snap=D.get('Loan_Snapshot',pd.DataFrame()).copy()
customers=D.get('Customers',pd.DataFrame()).copy()
fin=D.get('Customer_Financials',pd.DataFrame()).copy()
pay=D.get('Payments',pd.DataFrame()).copy()
uw=D.get('Underwriting',pd.DataFrame()).copy()

for df in [loans,snap,customers,fin,pay,uw]:
    for c in df.columns:
        if 'Date' in c or c in ['Snapshot_Date','Month','Application_Date','Due_Date','Payment_Date']:
            df[c]=pd.to_datetime(df[c],errors='coerce')

# Explicitly reconcile the real Excel schema with dashboard-friendly analysis fields.
if not snap.empty and 'Snapshot_Date' in snap.columns:
    snap['Snapshot_Date']=pd.to_datetime(snap['Snapshot_Date'],errors='coerce')
if not snap.empty and 'IFRS9_Stage' in snap.columns:
    snap['IFRS9_Stage']=pd.to_numeric(snap['IFRS9_Stage'],errors='coerce')

# Loan_Snapshot contains product/risk fields via codes; bring the descriptive loan attributes from Loans.
loan_lookup=[c for c in ['Loan_ID','Product_Code','Product_Name','Customer_Segment','Region','Origination_Date','Original_Amount_EUR','Origination_LTV','Interest_Rate'] if c in loans.columns]
if 'Loan_ID' in snap.columns and 'Loan_ID' in loans.columns:
    snap=snap.merge(loans[loan_lookup].drop_duplicates('Loan_ID'),on='Loan_ID',how='left',suffixes=('','_loan'))

# Create stable aliases only where the source field exists.
if 'PD_12M' in snap.columns: snap['PD']=pd.to_numeric(snap['PD_12M'],errors='coerce')
if 'Current_LTV' in snap.columns: snap['LTV']=pd.to_numeric(snap['Current_LTV'],errors='coerce')
if 'DPD_Days' in snap.columns: snap['Days_Past_Due']=pd.to_numeric(snap['DPD_Days'],errors='coerce')
if 'Outstanding_Balance_EUR' in snap.columns and 'EAD_EUR' not in snap.columns: snap['EAD_EUR']=pd.to_numeric(snap['Outstanding_Balance_EUR'],errors='coerce')

if not snap.empty:
    latest_date=snap['Snapshot_Date'].max() if 'Snapshot_Date' in snap.columns else pd.NaT
    latest=snap[snap['Snapshot_Date'].eq(latest_date)].copy() if pd.notna(latest_date) else snap.copy()
else:
    latest_date=pd.NaT; latest=snap.copy()

stage_map={1:'Geros kredito kokybės paskolos',2:'Padidėjusios rizikos paskolos',3:'Probleminės paskolos'}

def num(df,col,default=0.0):
    if col not in df.columns: return pd.Series(default,index=df.index,dtype=float)
    return pd.to_numeric(df[col],errors='coerce').fillna(default)

def pct(x): return f'{x*100:.1f}%'
def eur(x):
    if pd.isna(x): return '–'
    if abs(x)>=1_000_000: return f'{x/1_000_000:.1f} mln. €'
    if abs(x)>=1_000: return f'{x/1_000:.0f} tūkst. €'
    return f'{x:,.0f} €'

def metric_card(title,value,subtitle='',tone='neutral'):
    color={'red':'#d14343','amber':'#e39a22','green':'#14966d','neutral':'#65758b'}.get(tone,'#65758b')
    st.markdown(f'<div class="card"><div class="kpi-title">{title}</div><div class="kpi-value">{value}</div><div class="kpi-sub" style="color:{color};font-weight:800">{subtitle}</div></div>',unsafe_allow_html=True)

def fig_base(fig,height=350):
    fig.update_layout(height=height,margin=dict(l=10,r=10,t=48,b=10),paper_bgcolor='white',plot_bgcolor='white',font=dict(family='Arial',color='#20324a'),legend=dict(orientation='h',y=1.08,x=0))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor='#edf1f6',zeroline=False)
    return fig

def question(title,sub):
    st.markdown(f'<div class="section-title">{title}</div><div class="section-sub">{sub}</div>',unsafe_allow_html=True)

def note(text): st.markdown(f'<div class="note">{text}</div>',unsafe_allow_html=True)
def alert(kind,title,text): st.markdown(f'<div class="alert alert-{kind}"><div class="alert-title">{title}</div><div class="alert-text">{text}</div></div>',unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div style="font-size:22px;font-weight:900;margin-bottom:5px">🏦 Kredito rizika</div>',unsafe_allow_html=True)
    st.markdown('<div style="font-size:13px;color:#b8c9df!important;margin-bottom:18px">Vieno banko vadovybės rizikos ataskaita</div>',unsafe_allow_html=True)
    page=st.radio('Ataskaitos dalis',['Vadovybės apžvalga','Asmens profilis','Portfelio rizika','Rizikos raida ir scenarijai'],label_visibility='collapsed')
    date_text='Nėra duomenų' if pd.isna(latest_date) else latest_date.strftime('%Y-%m-%d')
    st.markdown(f'<div class="card" style="background:rgba(255,255,255,.055);border-color:rgba(157,190,230,.28);box-shadow:none"><b>Ataskaitos data</b><br><span style="color:#b8c9df">{date_text}</span><br><br><b>Aktyvios paskolos</b><br><span style="color:#b8c9df">{len(latest):,}</span></div>',unsafe_allow_html=True)

EAD=float(num(latest,'EAD_EUR').sum())
stage=num(latest,'IFRS9_Stage')
problem_ead=float(num(latest.loc[stage.eq(3)],'EAD_EUR').sum()) if len(latest) else 0
stage2_ead=float(num(latest.loc[stage.eq(2)],'EAD_EUR').sum()) if len(latest) else 0
past90_ead=float(num(latest.loc[num(latest,'Days_Past_Due').ge(90)],'EAD_EUR').sum()) if len(latest) else 0
problem_ratio=problem_ead/EAD if EAD else 0
stage2_ratio=stage2_ead/EAD if EAD else 0
past90_ratio=past90_ead/EAD if EAD else 0

if page=='Vadovybės apžvalga':
    st.title('Vadovybės kredito rizikos apžvalga')
    st.caption('Tikslas – per kelias minutes suprasti, kur banko kredito portfelyje yra didžiausios rizikos ir ar jos didėja.')
    cs=st.columns(5)
    vals=[('Paskolų portfelis',eur(EAD),'dabartinis likutis','neutral'),('Padidėjusios rizikos paskolos',pct(stage2_ratio),'dalis portfelio','amber'),('Probleminės paskolos',pct(problem_ratio),'dalis portfelio','red'),('Daugiau kaip 90 dienų vėluojančios',pct(past90_ratio),'dalis portfelio','red'),('Probleminių paskolų suma',eur(problem_ead),'suma, į kurią reikia daugiausia dėmesio','red')]
    for c,v in zip(cs,vals):
        with c: metric_card(*v)
    question('Kur dabar reikėtų vadovybės dėmesio?','Čia pateikiami ne techniniai rodikliai, o praktinės rizikos išvados.')
    if problem_ratio>0.05: alert('red','Probleminių paskolų dalis yra aukšta',f'{pct(problem_ratio)} portfelio yra probleminės paskolos. Vertėtų vertinti naujų problemų srautą, atidėjinius, užstato vertę ir išieškojimo rezultatus.')
    else: alert('green','Probleminių paskolų dalis kol kas kontroliuojama',f'Probleminės paskolos sudaro {pct(problem_ratio)} portfelio.')
    if stage2_ratio>0.10: alert('amber','Reikšminga dalis paskolų jau turi padidėjusią riziką',f'{pct(stage2_ratio)} portfelio yra padidėjusios rizikos. Tai ankstyvas signalas, kad dalis paskolų gali tapti probleminėmis.')
    if past90_ratio>0.03: alert('red','Mokėjimų vėlavimai rodo realų kredito kokybės pablogėjimą',f'{pct(past90_ratio)} portfelio vėluojama daugiau kaip 90 dienų.')
    question('Ar kredito kokybė gerėja ar blogėja?','Svarbiausia yra kryptis, todėl rodome, kaip keitėsi probleminių ir padidėjusios rizikos paskolų dalis.')
    if not snap.empty:
        trend=snap.groupby('Snapshot_Date',as_index=False).agg(Paskolų_likutis=('EAD_EUR','sum'),Probleminės=('IFRS9_Stage',lambda s:(pd.to_numeric(s,errors='coerce')==3).mean()),Padidėjusios_rizikos=('IFRS9_Stage',lambda s:(pd.to_numeric(s,errors='coerce')==2).mean()))
        long=trend.melt(id_vars='Snapshot_Date',value_vars=['Probleminės','Padidėjusios_rizikos'],var_name='Rodiklis',value_name='Dalis')
        long['Rodiklis']=long['Rodiklis'].replace({'Probleminės':'Probleminės paskolos','Padidėjusios_rizikos':'Padidėjusios rizikos paskolos'})
        fig=px.line(long,x='Snapshot_Date',y='Dalis',color='Rodiklis',markers=True)
        fig.update_yaxes(tickformat='.1%',title='Dalis viso portfelio')
        fig.update_xaxes(title='Data')
        st.plotly_chart(fig_base(fig,360),use_container_width=True)
    question('Kur yra didžiausia rizika?','Palyginame portfelio dydį su probleminių paskolų dalimi. Dešinėje ir aukščiau esančios sritys yra svarbiausios.')
    if not latest.empty and 'Product_Name' in latest.columns:
        g=latest.groupby('Product_Name',as_index=False).agg(Paskolų_likutis=('EAD_EUR','sum'),Probleminių_paskolų_dalis=('IFRS9_Stage',lambda s:(pd.to_numeric(s,errors='coerce')==3).mean()))
        fig=px.scatter(g,x='Paskolų_likutis',y='Probleminių_paskolų_dalis',size='Paskolų_likutis',text='Product_Name')
        fig.update_yaxes(tickformat='.1%',title='Probleminių paskolų dalis')
        fig.update_xaxes(title='Paskolų likutis')
        st.plotly_chart(fig_base(fig,360),use_container_width=True)

elif page=='Asmens profilis':
    st.title('Asmens kredito profilis')
    st.caption('Įveskite kliento kodą ir gaukite aiškų vieno kliento rizikos vaizdą.')
    if customers.empty or 'Customer_ID' not in customers.columns: st.error('Trūksta klientų identifikatoriaus.'); st.stop()
    cid=st.text_input('Asmens kodas / kliento kodas',value=str(customers.iloc[0]['Customer_ID'])).strip()
    cust=customers[customers['Customer_ID'].astype(str).eq(cid)]
    if cust.empty: st.warning('Tokio kliento testiniuose duomenyse nėra.'); st.stop()
    row=cust.iloc[0]
    l=loans[loans['Customer_ID'].astype(str).eq(cid)] if 'Customer_ID' in loans.columns else loans.iloc[0:0]
    s=latest[latest['Customer_ID'].astype(str).eq(cid)] if 'Customer_ID' in latest.columns else latest.iloc[0:0]
    datecol='Snapshot_Date' if 'Snapshot_Date' in fin.columns else fin.columns[0]
    f=fin[fin['Customer_ID'].astype(str).eq(cid)].sort_values(datecol) if 'Customer_ID' in fin.columns else fin.iloc[0:0]
    cs=st.columns(5)
    income=float(num(f,'Monthly_Income_EUR').iloc[-1]) if len(f) else 0
    debt=float(num(f,'Total_Debt_EUR').iloc[-1]) if len(f) else float(num(s,'EAD_EUR').sum())
    maxdpd=int(num(s,'Days_Past_Due').max()) if len(s) else 0
    vals=[('Kliento segmentas',str(row.get('Customer_Segment','–')),'','neutral'),('Paskolų skaičius',f'{len(l):,}','','neutral'),('Bendra skola',eur(debt),'dabartinis likutis','neutral'),('Paskutinės mėnesio pajamos',eur(income),'','neutral'),('Didžiausias vėlavimas',f'{maxdpd} dienos','pagal turimus duomenis','red' if maxdpd>=30 else 'green')]
    for c,v in zip(cs,vals):
        with c: metric_card(*v)
    left,right=st.columns([1.5,1])
    with left:
        question('Ar kliento finansinė padėtis blogėja?','Palyginame pajamas ir bendrą skolą per laiką.')
        if not f.empty:
            cols=[c for c in [datecol,'Monthly_Income_EUR','Total_Debt_EUR'] if c in f.columns]
            q=f[cols].melt(id_vars=datecol,var_name='Rodiklis',value_name='Suma')
            fig=px.line(q,x=datecol,y='Suma',color='Rodiklis',markers=True)
            fig.update_yaxes(title='Eurais',tickprefix='€')
            st.plotly_chart(fig_base(fig,330),use_container_width=True)
    with right:
        question('Kas šiuo metu kelia riziką?','Tik tie signalai, kurie turi tiesioginę praktinę reikšmę.')
        if maxdpd>=90: alert('red','Klientas vėluoja daugiau kaip 90 dienų',f'Didžiausias nustatytas vėlavimas – {maxdpd} dienos.')
        elif maxdpd>=30: alert('amber','Kliento mokėjimai vėluoja',f'Didžiausias nustatytas vėlavimas – {maxdpd} dienos.')
        if income and 'DSTI' in f.columns and float(num(f,'DSTI').iloc[-1])>0.5: alert('red','Didelė mėnesinių įmokų našta',f'Mokėjimų ir pajamų santykis siekia {pct(float(num(f,"DSTI").iloc[-1]))}.')
        if income and float(num(f,'Annual_Income_EUR').iloc[-1] if 'Annual_Income_EUR' in f.columns else 0)>0: pass
        if not s.empty and (s['IFRS9_Stage'].eq(3).any()): alert('red','Bent viena paskola yra probleminė','Tai reiškia, kad kredito rizika jau materializavosi bent vienoje kliento paskoloje.')
        if maxdpd==0 and not s['IFRS9_Stage'].eq(3).any() if not s.empty else True: alert('green','Nėra stipraus dabartinio rizikos signalo','Pagal turimus testinius duomenis reikšmingo vėlavimo nėra.')
    question('Kokias paskolas turi klientas?','Visos paskolos pateikiamos vienoje vietoje, kad būtų matoma bendra kliento pozicija.')
    if not s.empty:
        show=[c for c in ['Loan_ID','Product_Name','EAD_EUR','Interest_Rate','LTV','Days_Past_Due','PD','LGD'] if c in s.columns]
        tbl=s[show].copy()
        if 'IFRS9_Stage' in s.columns: tbl['Kredito būklė']=s['IFRS9_Stage'].map(stage_map)
        st.dataframe(tbl,use_container_width=True,hide_index=True)

elif page=='Portfelio rizika':
    st.title('Portfelio rizika')
    st.caption('Kur susikaupusi rizika ir kokie paskolų požymiai ją paaiškina?')
    if latest.empty: st.warning('Nėra naujausio portfelio stebėjimo.'); st.stop()
    question('Kur rizika didžiausia pagal produktą?','Stulpelio dydis parodo banko pinigų sumą. Spalva parodo probleminių paskolų dalį.')
    if 'Product_Name' in latest.columns:
        g=latest.groupby('Product_Name',as_index=False).agg(Paskolų_likutis=('EAD_EUR','sum'),Probleminių_paskolų_dalis=('IFRS9_Stage',lambda s:(pd.to_numeric(s,errors='coerce')==3).mean()))
        fig=px.bar(g.sort_values('Paskolų_likutis'),x='Paskolų_likutis',y='Product_Name',orientation='h',color='Probleminių_paskolų_dalis',color_continuous_scale=['#cfe9df','#e39a22','#d14343'])
        fig.update_xaxes(title='Paskolų likutis'); fig.update_yaxes(title='')
        fig.update_coloraxes(colorbar_title='Probleminių paskolų dalis',colorbar_tickformat='.0%')
        st.plotly_chart(fig_base(fig,380),use_container_width=True)
    question('Ar paskolos suteikimo metu buvo matomi rizikos signalai?','Lyginame pradinį paskolos ir užstato santykį su vėlesniu probleminių paskolų lygiu.')
    if not uw.empty and 'Origination_LTV' in uw.columns:
        tmp=uw.copy(); tmp['Origination_LTV']=pd.to_numeric(tmp['Origination_LTV'],errors='coerce')
        tmp=tmp.dropna(subset=['Origination_LTV'])
        tmp['LTV grupė']=pd.cut(tmp['Origination_LTV'],bins=[0,.6,.7,.8,.9,1,10],labels=['<60 %','60–70 %','70–80 %','80–90 %','90–100 %','>100 %'],right=False,include_lowest=True)
        if 'Loan_ID' in tmp.columns and 'Loan_ID' in latest.columns:
            bad=latest[['Loan_ID','IFRS9_Stage']].drop_duplicates('Loan_ID'); bad['Probleminė']=pd.to_numeric(bad['IFRS9_Stage'],errors='coerce').eq(3)
            tmp=tmp.merge(bad,on='Loan_ID',how='left')
            out=tmp.groupby('LTV grupė',observed=False)['Probleminė'].mean().reset_index(name='Probleminių paskolų dalis')
            out['LTV grupė']=out['LTV grupė'].astype(str)
            fig=px.bar(out,x='LTV grupė',y='Probleminių paskolų dalis')
            fig.update_yaxes(tickformat='.1%',title='Probleminių paskolų dalis'); fig.update_xaxes(title='Paskolos ir užstato vertės santykis suteikimo metu')
            st.plotly_chart(fig_base(fig,340),use_container_width=True)
    question('Kurios paskolos šiuo metu reikalauja daugiausia dėmesio?','Viršuje pateikiamos didžiausios rizikos pozicijos pagal vėlavimą, rizikos tikimybę ir paskolos bei užstato santykį.')
    r=latest.copy(); pdv=num(r,'PD'); ltv=num(r,'LTV'); dpd=num(r,'Days_Past_Due')
    r['Rizikos balas']=pdv.rank(pct=True,method='average').fillna(0)*0.45+ltv.rank(pct=True,method='average').fillna(0)*0.20+(dpd.clip(0,90).rank(pct=True,method='average').fillna(0))*0.35
    show=[c for c in ['Loan_ID','Customer_ID','Product_Name','EAD_EUR','PD','LTV','Days_Past_Due','IFRS9_Stage'] if c in r.columns]
    st.dataframe(r.sort_values('Rizikos balas',ascending=False).head(20)[show],use_container_width=True,hide_index=True)

else:
    st.title('Rizikos raida ir scenarijai')
    st.caption('Klausimas: ar portfelis blogėja, ar naujai suteiktos paskolos yra rizikingesnės ir kas nutiktų pablogėjus ekonomikai?')
    question('Kiek paskolų laikui bėgant tapo rizikingesnės?','Parodome, kaip keičiasi geros, padidėjusios rizikos ir probleminės paskolos.')
    if not snap.empty:
        s2=snap.copy(); s2['IFRS9_Stage']=pd.to_numeric(s2['IFRS9_Stage'],errors='coerce')
        g=s2.groupby('Snapshot_Date',as_index=False).agg(Geros=('IFRS9_Stage',lambda s:(s==1).sum()),Padidėjusios_rizikos=('IFRS9_Stage',lambda s:(s==2).sum()),Probleminės=('IFRS9_Stage',lambda s:(s==3).sum()))
        long=g.melt(id_vars='Snapshot_Date',var_name='Kredito būklė',value_name='Paskolų skaičius')
        long['Kredito būklė']=long['Kredito būklė'].replace({'Geros':'Geros kredito kokybės','Padidėjusios_rizikos':'Padidėjusios rizikos','Probleminės':'Probleminės'})
        fig=px.area(long,x='Snapshot_Date',y='Paskolų skaičius',color='Kredito būklė')
        st.plotly_chart(fig_base(fig,360),use_container_width=True)
    question('Ar naujesnės paskolos yra rizikingesnės?','Palyginame paskolas pagal suteikimo metus ir nustatome, kokia jų dalis šiandien yra probleminė.')
    if not loans.empty and not latest.empty and 'Origination_Date' in loans.columns and 'Loan_ID' in loans.columns:
        a=loans[['Loan_ID','Origination_Date']].drop_duplicates('Loan_ID').copy(); a['Suteikimo metai']=pd.to_datetime(a['Origination_Date'],errors='coerce').dt.year
        ss=latest[['Loan_ID','IFRS9_Stage']].drop_duplicates('Loan_ID').copy(); ss['IFRS9_Stage']=pd.to_numeric(ss['IFRS9_Stage'],errors='coerce')
        v=a.merge(ss,on='Loan_ID',how='left')
        v['Probleminė']=v['IFRS9_Stage'].eq(3)
        v=v.dropna(subset=['Suteikimo metai']).groupby('Suteikimo metai',as_index=False)['Probleminė'].mean().rename(columns={'Probleminė':'Probleminių paskolų dalis'})
        fig=px.bar(v,x='Suteikimo metai',y='Probleminių paskolų dalis')
        fig.update_yaxes(tickformat='.1%',title='Probleminių paskolų dalis')
        st.plotly_chart(fig_base(fig,330),use_container_width=True)
    question('Kas nutiktų nepalankaus scenarijaus atveju?','Testinis scenarijus parodo, kiek papildomo nuostolio gali atsirasti, jei kredito rizika padidėtų.')
    scenario=st.selectbox('Scenarijus',['Vidutinis pablogėjimas','Stiprus pablogėjimas'])
    shock=.25 if scenario=='Vidutinis pablogėjimas' else .50
    stressed=latest.copy(); stressed['Papildomas nuostolis']=num(stressed,'EAD_EUR')*num(stressed,'LGD',.45)*num(stressed,'PD').clip(lower=0)*shock
    stress_loss=float(stressed['Papildomas nuostolis'].sum())
    c1,c2=st.columns([1,2])
    with c1: metric_card('Papildomas prognozuojamas nuostolis',eur(stress_loss),scenario,'red')
    with c2:
        show=[c for c in ['Loan_ID','Customer_ID','Product_Name','EAD_EUR','PD','Papildomas nuostolis'] if c in stressed.columns]
        st.dataframe(stressed.nlargest(10,'Papildomas nuostolis')[show],use_container_width=True,hide_index=True)

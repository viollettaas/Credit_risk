# -----------------------------------------------------------------------------
elif page == 'Užstatas ir koncentracija':
    section('Užstatas ir koncentracija', 'Užstato pakankamumas ir kredito ekspozicijos koncentracija.')
    if base_snap.empty:
        st.warning('Pagal pasirinktus filtrus paskolų nerasta.')
        st.stop()
    a, b = st.columns(2)
    with a:
        section('Paskolos ir užstato vertės santykio pasiskirstymas')
        fig = px.histogram(base_snap, x='Current_LTV', nbins=20)
        fig.update_xaxes(tickformat='.0%')
        st.plotly_chart(style_chart(fig), use_container_width=True)
    with b:
        section('Ekspozicija pagal paskolos ir užstato vertės santykį')
        tmp = base_snap.assign(Grupe=pd.cut(base_snap.Current_LTV, bins=[-1,.7,.8,.9,1.0,99], labels=['iki 70%','70–80%','80–90%','90–100%','daugiau kaip 100%']))
        x = tmp.groupby('Grupe', observed=False)['EAD_EUR'].sum().reset_index()
        fig = px.bar(x, x='Grupe', y='EAD_EUR', text='EAD_EUR')
        st.plotly_chart(style_chart(fig), use_container_width=True)

    section('Didžiausios klientų koncentracijos')
    concentration = base_snap.groupby('Customer_ID', as_index=False)['EAD_EUR'].sum().sort_values('EAD_EUR', ascending=False)
    concentration_share = concentration.head(10)['EAD_EUR'].sum() / concentration['EAD_EUR'].sum() if concentration['EAD_EUR'].sum() else np.nan
    card('Didžiausių 10 klientų koncentracija', pct(concentration_share), 'Dalis nuo bendro paskolų likučio')
    st.write('')
    top20 = concentration.head(20).copy()
    top20['Ekspozicija'] = top20['EAD_EUR'].map(euro)
    st.dataframe(top20[['Customer_ID','Ekspozicija']].rename(columns={'Customer_ID':'Klientas'}), hide_index=True, use_container_width=True)

    section('Koncentracija pagal produktą')
    prod_conc = base_snap.groupby('Product_Name', as_index=False)['EAD_EUR'].sum().sort_values('EAD_EUR', ascending=False)
    fig = px.bar(prod_conc, x='Product_Name', y='EAD_EUR', text='EAD_EUR')
    st.plotly_chart(style_chart(fig), use_container_width=True)

# -----------------------------------------------------------------------------
# 7. STRESS TESTING
# -----------------------------------------------------------------------------
elif page == 'Streso testavimas':
    section('Streso testavimas', 'Scenarijų analizė, leidžianti įvertinti galimą kredito portfelio pablogėjimą.')
    scenario_list = stress['Scenario'].dropna().astype(str).tolist()
    if not scenario_list:
        st.warning('Streso scenarijų duomenų nėra.')
        st.stop()
    scenario = st.selectbox('Scenarijus', scenario_list)
    row = stress.loc[stress['Scenario'].eq(scenario)].iloc[0]

    cols = st.columns(5)
    scenario_values = [
        ('Bendrojo vidaus produkto šokas', f"{row['GDP_Shock_pp']:.1f} p. p."),
        ('Nedarbo šokas', f"{row['Unemployment_Shock_pp']:.1f} p. p."),
        ('Būsto kainų šokas', f"{row['House_Price_Shock_pct'] * 100:.1f}%"),
        ('Palūkanų normos šokas', f"{row['EURIBOR_Shock_pp']:.1f} p. p."),
        ('Įsipareigojimų nevykdymo tikimybės daugiklis', f"{row['PD_Multiplier']:.2f}x"),
    ]
    for c, (lab, val) in zip(cols, scenario_values):
        with c: card(lab, val, 'Scenarijaus prielaida')

    baseline_ecl = base_snap['ECL_EUR'].sum()
    stressed_pd = np.minimum(base_snap['PD_12M'].fillna(0) * float(row['PD_Multiplier']), 0.99)
    stressed_lgd = np.minimum(base_snap['LGD'].fillna(0) + float(row['LGD_Add']), 0.99)
    stressed_ead = base_snap['EAD_EUR'].fillna(0) * (1 + float(row['EAD_Growth_pct']))
    stressed_ecl = (stressed_pd * stressed_lgd * stressed_ead).sum()
    increase = stressed_ecl / baseline_ecl - 1 if baseline_ecl else np.nan

    cols = st.columns(3)
    for c, (lab, val, note) in zip(cols, [
        ('Esamas tikėtinas kredito nuostolis', euro(baseline_ecl), 'Naujausias portfelio stebėjimas'),
        ('Stresinis tikėtinas kredito nuostolis', euro(stressed_ecl), 'Pagal pasirinktą scenarijų'),
        ('Tikėtino nuostolio padidėjimas', pct(increase), 'Palyginti su dabartine padėtimi'),
    ]):
        with c: card(lab, val, note)

    section('Streso poveikis pagal produktą')
    tmp = base_snap.copy()
    tmp['Stresinis_įsipareigojimų_nevykdymo_tikimybė'] = stressed_pd
    tmp['Stresinis_tikėtinas_kredito_nuostolis'] = stressed_pd * stressed_lgd * stressed_ead
    x = tmp.groupby('Product_Name').agg(Dabartinis=('ECL_EUR','sum'), Stresinis=('Stresinis_tikėtinas_kredito_nuostolis','sum')).reset_index()
    long = x.melt('Product_Name', var_name='Rodiklis', value_name='Nuostolis')
    fig = px.bar(long, x='Product_Name', y='Nuostolis', color='Rodiklis', barmode='group')
    st.plotly_chart(style_chart(fig), use_container_width=True)

    section('Didžiausios rizikos paskolos po streso')
    tmp = base_snap.copy()
    tmp['Stresinis_ECL'] = stressed_pd * stressed_lgd * stressed_ead
    worst = tmp.sort_values('Stresinis_ECL', ascending=False).head(15)[['Loan_ID','Customer_ID','Product_Name','EAD_EUR','Stresinis_ECL','Current_LTV','IFRS9_Stage']].copy()
    worst.columns = ['Paskola','Klientas','Produktas','Paskolos likutis','Stresinis tikėtinas kredito nuostolis','Paskolos ir užstato vertės santykis','Kredito rizikos etapas']
    worst['Paskolos likutis'] = worst['Paskolos likutis'].map(euro)
    worst['Stresinis tikėtinas kredito nuostolis'] = worst['Stresinis tikėtinas kredito nuostolis'].map(euro)
    worst['Paskolos ir užstato vertės santykis'] = worst['Paskolos ir užstato vertės santykis'].map(pct)
    worst['Kredito rizikos etapas'] = worst['Kredito rizikos etapas'].map(stage_name)
    st.dataframe(worst, hide_index=True, use_container_width=True)

# -----------------------------------------------------------------------------
# 8. LOAN SEARCH
# -----------------------------------------------------------------------------
elif page == 'Paskolų paieška':
    section('Paskolų paieška', 'Filtruokite paskolas pagal rizikos rodiklius ir raskite didžiausios rizikos pozicijas.')
    c1, c2, c3, c4 = st.columns(4)
    stage_options = sorted(base_snap['IFRS9_Stage'].dropna().unique().tolist())
    with c1:
        selected_stages = st.multiselect('Kredito rizikos etapas', stage_options, default=stage_options, format_func=stage_name)
    with c2:
        min_pd = st.number_input('Mažiausia įsipareigojimų nevykdymo tikimybė', min_value=0.0, max_value=1.0, value=0.0, step=0.01)
    with c3:
        min_ltv = st.number_input('Mažiausias paskolos ir užstato vertės santykis', min_value=0.0, max_value=2.0, value=0.0, step=0.05)
    with c4:
        min_dpd = st.number_input('Mažiausias vėlavimas dienomis', min_value=0, max_value=365, value=0, step=1)

    x = base_snap[
        base_snap['IFRS9_Stage'].isin(selected_stages)
        & (base_snap['PD_12M'] >= min_pd)
        & (base_snap['Current_LTV'] >= min_ltv)
        & (base_snap['DPD_Days'] >= min_dpd)
    ].copy()
    x = x.merge(loans[['Loan_ID','Origination_Date']], on='Loan_ID', how='left')
    x = x[['Loan_ID','Customer_ID','Product_Name','Customer_Segment','EAD_EUR','PD_12M','LGD','Current_LTV','IFRS9_Stage','DPD_Days','ECL_EUR','Origination_Date']].sort_values(['PD_12M','EAD_EUR'], ascending=False)
    st.caption(f'Rasta paskolų: {len(x):,}')
    y = x.copy()
    y['EAD_EUR'] = y['EAD_EUR'].map(euro)
    y['PD_12M'] = y['PD_12M'].map(pct)
    y['LGD'] = y['LGD'].map(pct)
    y['Current_LTV'] = y['Current_LTV'].map(pct)
    y['ECL_EUR'] = y['ECL_EUR'].map(euro)
    y['IFRS9_Stage'] = y['IFRS9_Stage'].map(stage_name)
    y.columns = ['Paskola','Klientas','Produktas','Segmentas','Paskolos likutis','Įsipareigojimų nevykdymo tikimybė','Nuostolio dydis nevykdymo atveju','Paskolos ir užstato vertės santykis','Kredito rizikos etapas','Vėlavimas dienomis','Tikėtinas kredito nuostolis','Suteikimo data']
    st.dataframe(y, use_container_width=True, hide_index=True)

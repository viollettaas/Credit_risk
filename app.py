    if high_ltv>0.1: alerts.append(("warn",f"{pct(high_ltv)} kredito pozicijos turi didesnį nei 90 procentų paskolos ir užstato vertės santykį."))
    worst=latest.groupby("Customer_Segment").apply(lambda g:g.loc[g.IFRS9_Stage.eq(3),"EAD_EUR"].sum()/g.EAD_EUR.sum(),include_groups=False).sort_values(ascending=False)
    if len(worst): alerts.append(("insight",f"Didžiausia trečio kredito rizikos etapo dalis yra segmente „{worst.index[0]}“ – {pct(worst.iloc[0])}."))
    for cls,msg in alerts: st.markdown(f'<div class="{cls}">{msg}</div>',unsafe_allow_html=True)
    section("Portfelio struktūra ir probleminės zonos")
    c1,c2,c3=st.columns(3)
    with c1:
        s=latest.groupby("Kredito rizikos etapas",as_index=False).EAD_EUR.sum(); fig=px.donut(s,names="Kredito rizikos etapas",values="EAD_EUR",hole=.62,title="Portfelis pagal kredito rizikos etapą"); st.plotly_chart(style_fig(fig,350),use_container_width=True)
    with c2:
        d=latest.groupby("DPD_Bucket",as_index=False).EAD_EUR.sum(); fig=px.bar(d,x="DPD_Bucket",y="EAD_EUR",title="Portfelis pagal mokėjimo vėlavimą",labels={"DPD_Bucket":"Vėlavimo grupė","EAD_EUR":"Kredito pozicija, eurais"}); st.plotly_chart(style_fig(fig,350),use_container_width=True)
    with c3:
        r=latest.groupby("Risk_Band",as_index=False).EAD_EUR.sum().sort_values("EAD_EUR",ascending=False); fig=px.bar(r,x="Risk_Band",y="EAD_EUR",title="Portfelis pagal rizikos lygį",labels={"Risk_Band":"Rizikos lygis","EAD_EUR":"Kredito pozicija, eurais"}); st.plotly_chart(style_fig(fig,350),use_container_width=True)

elif page=="Asmens profilis":
    title("Asmens profilis","Įveskite kliento identifikatorių ir matykite visą jo finansinę bei kredito rizikos istoriją.")
    cid=st.text_input("Kliento identifikatorius",placeholder="Pavyzdžiui, C00001").strip()
    if not cid:
        sample=customers.Customer_ID.astype(str).head(8).tolist(); st.info("Testui galite naudoti vieną iš šių identifikatorių: "+", ".join(sample))
    elif cid not in bank_customers:
        st.error("Tokio kliento šio banko portfelyje nėra.")
    else:
        cust=customers[customers.Customer_ID.astype(str).eq(cid)].iloc[0]; cl=loans[loans.Customer_ID.astype(str).eq(cid)]; cs=snapshots[snapshots.Customer_ID.astype(str).eq(cid)].sort_values("Snapshot_Date"); current=cs[cs.Snapshot_Date.eq(cs.Snapshot_Date.max())]; fin=financials[financials.Customer_ID.astype(str).eq(cid)].sort_values("Snapshot_Date")
        current_ead=current.EAD_EUR.sum(); worst_stage=current.IFRS9_Stage.max(); max_dpd=current.DPD_Days.max(); customer_pd=weighted_average(current,"PD_12M"); customer_ltv=weighted_average(current,"Current_LTV")
        cols=st.columns(6); vals=[("Klientų segmentas",str(cust.Customer_Segment),str(cust.Region)),("Bendra kredito pozicija",eur(current_ead),f"{len(current)} aktyvių paskolų"),("Kredito rizikos etapas",STAGE_LABEL.get(worst_stage,str(worst_stage)),"blogiausia aktyvi paskola"),("Didžiausias vėlavimas",f"{int(max_dpd)} dienų","dabartinė būklė"),("Įsipareigojimų nevykdymo tikimybė",pct(customer_pd),"svertinė pagal poziciją"),("Paskolos ir užstato vertės santykis",pct(customer_ltv),"svertinis vidurkis")]
        for c,v in zip(cols,vals):
            with c:kpi(*v)
        section("Finansinė būklė ir ankstyvieji rizikos signalai")
        c1,c2=st.columns([1.25,1])
        with c1:
            if len(fin):
                ff=fin.melt("Snapshot_Date",value_vars=["Monthly_Income_EUR","Monthly_Expenses_EUR","Debt_Service_EUR"],var_name="Rodiklis",value_name="Suma"); ff["Rodiklis"]=ff.Rodiklis.map({"Monthly_Income_EUR":"Mėnesio pajamos","Monthly_Expenses_EUR":"Mėnesio išlaidos","Debt_Service_EUR":"Skolos aptarnavimo suma"}); fig=px.line(ff,x="Snapshot_Date",y="Suma",color="Rodiklis",markers=True,title="Pajamų, išlaidų ir skolos aptarnavimo raida",labels={"Snapshot_Date":"Data","Suma":"Eurai"}); st.plotly_chart(style_fig(fig),use_container_width=True)
        with c2:
            if len(fin):
                ff=fin.melt("Snapshot_Date",value_vars=["DTI","DSTI"],var_name="Rodiklis",value_name="Reikšmė"); ff["Rodiklis"]=ff.Rodiklis.map({"DTI":"Skolos ir pajamų santykis","DSTI":"Skolos įmokų ir pajamų santykis"}); fig=px.line(ff,x="Snapshot_Date",y="Reikšmė",color="Rodiklis",markers=True,title="Kliento finansinės naštos raida"); fig.update_yaxes(tickformat=".0%"); st.plotly_chart(style_fig(fig),use_container_width=True)
        signals=[]
        if len(fin):
            lf=fin.iloc[-1]
            if lf.DSTI>0.5:signals.append(("danger",f"Skolos įmokų ir pajamų santykis yra aukštas – {pct(lf.DSTI)}."))
            if lf.Income_Change_YoY<-0.1:signals.append(("warn",f"Kliento pajamos per metus sumažėjo {pct(abs(lf.Income_Change_YoY))}."))
            if lf.Overdraft_Used_EUR>0:signals.append(("warn",f"Klientas naudoja sąskaitos kredito limitą – {eur(lf.Overdraft_Used_EUR)}."))
        if max_dpd>=30:signals.append(("danger",f"Bent viena paskola vėluoja {int(max_dpd)} dienų."))
        if customer_ltv>0.9:signals.append(("warn",f"Paskolos ir užstato vertės santykis siekia {pct(customer_ltv)}."))
        if not signals:signals.append(("good","Pagal pagrindinius rodiklius reikšmingų ankstyvųjų rizikos signalų šiuo metu nenustatyta."))
        for cls,msg in signals:st.markdown(f'<div class="{cls}">{msg}</div>',unsafe_allow_html=True)
        section("Kredito rizikos istorija")
        hist=cs.groupby("Snapshot_Date").apply(lambda g:pd.Series({"Įsipareigojimų nevykdymo tikimybė":weighted_average(g,"PD_12M"),"Didžiausias vėlavimas dienomis":g.DPD_Days.max(),"Bendra kredito pozicija":g.EAD_EUR.sum()}),include_groups=False).reset_index()
        c1,c2=st.columns(2)
        with c1:
            fig=px.line(hist,x="Snapshot_Date",y="Įsipareigojimų nevykdymo tikimybė",markers=True,title="Įsipareigojimų nevykdymo tikimybės raida"); fig.update_yaxes(tickformat=".1%"); st.plotly_chart(style_fig(fig),use_container_width=True)
        with c2:
            fig=px.bar(hist,x="Snapshot_Date",y="Didžiausias vėlavimas dienomis",title="Mokėjimų vėlavimo raida"); st.plotly_chart(style_fig(fig),use_container_width=True)
        section("Kliento paskolos")
        table=current.merge(loans[["Loan_ID","Product_Name","Origination_Date","Maturity_Date","Original_Amount_EUR","Interest_Rate"]],on="Loan_ID",how="left")
        table=table[["Loan_ID","Product_Name","Original_Amount_EUR","EAD_EUR","Interest_Rate","IFRS9_Stage","DPD_Days","PD_12M","Current_LTV","ECL_EUR"]].rename(columns={"Loan_ID":"Paskolos identifikatorius","Product_Name":"Produktas","Original_Amount_EUR":"Pradinė suma","EAD_EUR":"Dabartinė kredito pozicija","Interest_Rate":"Palūkanų norma","IFRS9_Stage":"Kredito rizikos etapas","DPD_Days":"Vėlavimo dienos","PD_12M":"Įsipareigojimų nevykdymo tikimybė","Current_LTV":"Paskolos ir užstato vertės santykis","ECL_EUR":"Tikėtinas kredito nuostolis"})
        st.dataframe(table,use_container_width=True,hide_index=True)

elif page=="Portfelio rizikos analizė":
    title("Portfelio rizikos analizė","Kredito kokybė, koncentracijos, paskolų suteikimo kokybė ir rizikos segmentai.")
    cols=st.columns(6); vals=[("Bendra kredito pozicija",eur(total_ead),"dabartinis portfelis"),("Tikėtinas kredito nuostolis",eur(ecl),pct(ecl/total_ead)+" nuo pozicijos"),("Antras kredito rizikos etapas",pct(stage2),"padidėjusi rizika"),("Trečias kredito rizikos etapas",pct(stage3),"probleminės paskolos"),("Vidutinė įsipareigojimų nevykdymo tikimybė",pct(avg_pd),"svertinis vidurkis"),("Vidutinis paskolos ir užstato vertės santykis",pct(avg_ltv),"svertinis vidurkis")]
    for c,v in zip(cols,vals):
        with c:kpi(*v)
    section("Rizikos matrica","Kredito pozicija pagal klientų segmentą ir kredito rizikos etapą.")
    heat=latest.pivot_table(index="Customer_Segment",columns="Kredito rizikos etapas",values="EAD_EUR",aggfunc="sum",fill_value=0)
    fig=px.imshow(heat,aspect="auto",text_auto=".3s",title="Kredito pozicijos koncentracija",labels=dict(x="Kredito rizikos etapas",y="Klientų segmentas",color="Kredito pozicija")); st.plotly_chart(style_fig(fig,380),use_container_width=True)
    c1,c2=st.columns(2)
    with c1:
        section("Produktų rizika")
        prod=latest.groupby("Product_Code").apply(lambda g:pd.Series({"Kredito pozicija":g.EAD_EUR.sum(),"Trečio etapo dalis":g.loc[g.IFRS9_Stage.eq(3),"EAD_EUR"].sum()/g.EAD_EUR.sum(),"Tikėtino nuostolio dalis":g.ECL_EUR.sum()/g.EAD_EUR.sum(),"Vidutinė įsipareigojimų nevykdymo tikimybė":weighted_average(g,"PD_12M")}),include_groups=False).reset_index().merge(loans[["Product_Code","Product_Name"]].drop_duplicates(),on="Product_Code",how="left")
        fig=px.scatter(prod,x="Trečio etapo dalis",y="Tikėtino nuostolio dalis",size="Kredito pozicija",text="Product_Name",title="Produktų rizikos ir nuostolio žemėlapis"); fig.update_xaxes(tickformat=".1%"); fig.update_yaxes(tickformat=".1%"); fig.update_traces(textposition="top center"); st.plotly_chart(style_fig(fig),use_container_width=True)
    with c2:
        section("Regionų rizika")
        reg=latest.groupby("Loan_ID",as_index=False).agg(EAD_EUR=("EAD_EUR","sum"),IFRS9_Stage=("IFRS9_Stage","max")).merge(loans[["Loan_ID","Region"]],on="Loan_ID",how="left"); reg=reg.groupby("Region").apply(lambda g:pd.Series({"Kredito pozicija":g.EAD_EUR.sum(),"Trečio etapo dalis":g.loc[g.IFRS9_Stage.eq(3),"EAD_EUR"].sum()/g.EAD_EUR.sum()}),include_groups=False).reset_index().sort_values("Kredito pozicija",ascending=False)
        fig=px.bar(reg,x="Region",y="Kredito pozicija",color="Trečio etapo dalis",title="Kredito pozicija ir probleminių paskolų dalis pagal regioną"); st.plotly_chart(style_fig(fig),use_container_width=True)
    section("Paskolų suteikimo kokybė","Ar didesnė rizika buvo matoma jau paskolos suteikimo metu?")
    uw=underwriting.merge(latest[["Loan_ID","IFRS9_Stage","PD_12M","DPD_Days","EAD_EUR"]],on="Loan_ID",how="inner")
    c1,c2,c3=st.columns(3)
    with c1:
        tmp=uw.groupby("Debt_To_Income_Band").apply(lambda g:pd.Series({"Paskolų skaičius":len(g),"Trečio etapo dalis":(g.IFRS9_Stage.eq(3)).mean()}),include_groups=False).reset_index(); fig=px.bar(tmp,x="Debt_To_Income_Band",y="Trečio etapo dalis",title="Probleminių paskolų dalis pagal pradinę skolos naštą"); fig.update_yaxes(tickformat=".1%"); st.plotly_chart(style_fig(fig,350),use_container_width=True)
    with c2:
        uw["Pradinio kredito balo grupė"]=pd.cut(uw.Credit_Score,bins=[0,550,600,650,700,750,1000],right=False); tmp=uw.groupby("Pradinio kredito balo grupė",observed=True).IFRS9_Stage.apply(lambda x:(x==3).mean()).reset_index(name="Trečio etapo dalis"); tmp["Pradinio kredito balo grupė"]=tmp["Pradinio kredito balo grupė"].astype(str); fig=px.bar(tmp,x="Pradinio kredito balo grupė",y="Trečio etapo dalis",title="Probleminės paskolos pagal pradinį kredito balą"); fig.update_yaxes(tickformat=".1%"); st.plotly_chart(style_fig(fig,350),use_container_width=True)
    with c3:
        uw["Pradinio paskolos ir užstato santykio grupė"]=pd.cut(uw.Origination_LTV,bins=[0,.6,.7,.8,.9,1,10],right=False); tmp=uw.groupby("Pradinio paskolos ir užstato santykio grupė",observed=True).IFRS9_Stage.apply(lambda x:(x==3).mean()).reset_index(name="Trečio etapo dalis"); tmp.iloc[:,0]=tmp.iloc[:,0].astype(str); fig=px.bar(tmp,x=tmp.columns[0],y="Trečio etapo dalis",title="Probleminės paskolos pagal pradinį užstato padengimą"); fig.update_yaxes(tickformat=".1%"); st.plotly_chart(style_fig(fig,350),use_container_width=True)
    section("Didžiausios rizikos paskolos","Paskolos, kurios pagal dabartinius rodiklius labiausiai prisideda prie portfelio rizikos.")
    risk=latest.merge(loans[["Loan_ID","Product_Name","Region"]],on="Loan_ID",how="left"); risk["Rizikos_balai"]=(risk.IFRS9_Stage*30+risk.PD_12M*100+risk.DPD_Days.clip(upper=180)/6+risk.Current_LTV.fillna(0)*10); risk=risk.sort_values(["Rizikos_balai","EAD_EUR"],ascending=False).head(20)
    st.dataframe(risk[["Loan_ID","Customer_ID","Product_Name","Region","EAD_EUR","IFRS9_Stage","DPD_Days","PD_12M","LGD","Current_LTV","ECL_EUR"]].rename(columns={"Loan_ID":"Paskola","Customer_ID":"Klientas","Product_Name":"Produktas","Region":"Regionas","EAD_EUR":"Kredito pozicija","IFRS9_Stage":"Kredito rizikos etapas","DPD_Days":"Vėlavimo dienos","PD_12M":"Įsipareigojimų nevykdymo tikimybė","LGD":"Nuostolio dalis įsipareigojimų nevykdymo atveju","Current_LTV":"Paskolos ir užstato vertės santykis","ECL_EUR":"Tikėtinas kredito nuostolis"}),use_container_width=True,hide_index=True)

else:
    title("Giluminė analizė ir scenarijai","Migracijos, paskolų suteikimo kartos, užstatas, koncentracijos ir streso testavimas.")
    section("Kredito rizikos etapų migracija","Parodo, kaip paskolos juda tarp kredito rizikos etapų.")
    dates=sorted(snapshots.Snapshot_Date.dropna().unique()); prev_date=dates[-2] if len(dates)>1 else dates[-1]
    prev=snapshots[snapshots.Snapshot_Date.eq(prev_date)][["Loan_ID","IFRS9_Stage"]].rename(columns={"IFRS9_Stage":"Ankstesnis etapas"}); cur=latest[["Loan_ID","IFRS9_Stage","EAD_EUR"]].rename(columns={"IFRS9_Stage":"Dabartinis etapas"}); mig=prev.merge(cur,on="Loan_ID"); matrix=mig.pivot_table(index="Ankstesnis etapas",columns="Dabartinis etapas",values="EAD_EUR",aggfunc="sum",fill_value=0); matrix.index=[STAGE_LABEL.get(x,x) for x in matrix.index]; matrix.columns=[STAGE_LABEL.get(x,x) for x in matrix.columns]
    c1,c2=st.columns([1.15,1])
    with c1:
        fig=px.imshow(matrix,aspect="auto",text_auto=".3s",title=f"Migracija nuo {pd.Timestamp(prev_date):%Y-%m-%d} iki {latest_date:%Y-%m-%d}",labels=dict(x="Dabartinis etapas",y="Ankstesnis etapas",color="Kredito pozicija")); st.plotly_chart(style_fig(fig),use_container_width=True)
    with c2:
        deterioration=mig[mig["Dabartinis etapas"]>mig["Ankstesnis etapas"]].EAD_EUR.sum()/mig.EAD_EUR.sum(); improvement=mig[mig["Dabartinis etapas"]<mig["Ankstesnis etapas"]].EAD_EUR.sum()/mig.EAD_EUR.sum();
        kpi("Pablogėjusi kredito pozicija",pct(deterioration),"per paskutinį stebėjimo laikotarpį"); st.write(""); kpi("Pagerėjusi kredito pozicija",pct(improvement),"per paskutinį stebėjimo laikotarpį")
    section("Paskolų suteikimo kartų analizė","Lyginama, kaip skirtingais metais suteiktos paskolos elgiasi vėliau.")
    vint=loans[["Loan_ID","Origination_Date"]].copy(); vint["Suteikimo metai"]=pd.to_datetime(vint.Origination_Date).dt.year; v=latest.merge(vint[["Loan_ID","Suteikimo metai"]],on="Loan_ID",how="left"); vintage=v.groupby("Suteikimo metai").apply(lambda g:pd.Series({"Kredito pozicija":g.EAD_EUR.sum(),"Trečio etapo dalis":g.loc[g.IFRS9_Stage.eq(3),"EAD_EUR"].sum()/g.EAD_EUR.sum(),"Daugiau kaip 90 dienų vėlavimo dalis":g.loc[g.DPD_Days.ge(90),"EAD_EUR"].sum()/g.EAD_EUR.sum(),"Tikėtino nuostolio dalis":g.ECL_EUR.sum()/g.EAD_EUR.sum()}),include_groups=False).reset_index()
    long=vintage.melt("Suteikimo metai",value_vars=["Trečio etapo dalis","Daugiau kaip 90 dienų vėlavimo dalis","Tikėtino nuostolio dalis"],var_name="Rodiklis",value_name="Dalis"); fig=px.line(long,x="Suteikimo metai",y="Dalis",color="Rodiklis",markers=True,title="Rizikos kokybė pagal paskolos suteikimo metus"); fig.update_yaxes(tickformat=".1%"); st.plotly_chart(style_fig(fig),use_container_width=True)
    section("Užstato ir koncentracijos analizė")
    c1,c2=st.columns(2)
    with c1:
        ltv=latest.dropna(subset=["Current_LTV"]).copy(); ltv["Paskolos ir užstato santykio grupė"]=pd.cut(ltv.Current_LTV,bins=[0,.6,.7,.8,.9,1,10],labels=["Iki 60 %","60–70 %","70–80 %","80–90 %","90–100 %","Virš 100 %"],right=False); tmp=ltv.groupby("Paskolos ir užstato santykio grupė",observed=True).EAD_EUR.sum().reset_index(); fig=px.bar(tmp,x="Paskolos ir užstato santykio grupė",y="EAD_EUR",title="Kredito pozicija pagal užstato padengimą",labels={"EAD_EUR":"Kredito pozicija, eurais"}); st.plotly_chart(style_fig(fig,360),use_container_width=True)
    with c2:
        seg=latest.groupby("Customer_Segment",as_index=False).EAD_EUR.sum().sort_values("EAD_EUR",ascending=False); fig=px.bar(seg,x="Customer_Segment",y="EAD_EUR",title="Koncentracija pagal klientų segmentą",labels={"Customer_Segment":"Klientų segmentas","EAD_EUR":"Kredito pozicija, eurais"}); st.plotly_chart(style_fig(fig,360),use_container_width=True)
    section("Streso testavimas","Pasirinkite scenarijų ir įvertinkite, kaip keistųsi tikėtinas kredito nuostolis.")
    scenario=st.selectbox("Ekonominis scenarijus",stress.Scenario.astype(str).tolist(),index=min(2,len(stress)-1)); sc=stress[stress.Scenario.astype(str).eq(scenario)].iloc[0]
    stressed_pd=(latest.PD_12M*sc.PD_Multiplier).clip(upper=1); stressed_lgd=(latest.LGD+sc.LGD_Add).clip(upper=1); stressed_ead=latest.EAD_EUR*(1+sc.EAD_Growth_pct); stressed_loss=(stressed_pd*stressed_lgd*stressed_ead).sum(); increase=stressed_loss/ecl-1 if ecl else np.nan
    cols=st.columns(5); vals=[("Dabartinis tikėtinas kredito nuostolis",eur(ecl),"prieš scenarijų"),("Tikėtinas nuostolis po streso",eur(stressed_loss),scenario),("Nuostolio padidėjimas",pct(increase),"palyginti su dabartiniu"),("Nedarbo lygio šokas",f"{sc.Unemployment_Shock_pp:+.1f} proc. punkto","scenarijaus prielaida"),("Būsto kainų šokas",f"{sc.House_Price_Shock_pct:+.1%}","scenarijaus prielaida")]
    for c,vv in zip(cols,vals):
        with c:kpi(*vv)
    stress_df=latest[["Loan_ID","Customer_Segment","Product_Code","EAD_EUR","ECL_EUR"]].copy(); stress_df["Nuostolis po streso"]=stressed_pd*stressed_lgd*stressed_ead; stress_df["Nuostolio padidėjimas"]=stress_df["Nuostolis po streso"]-stress_df.ECL_EUR; stress_seg=stress_df.groupby("Customer_Segment",as_index=False)[["ECL_EUR","Nuostolis po streso"]].sum().melt("Customer_Segment",var_name="Būsena",value_name="Nuostolis"); stress_seg["Būsena"]=stress_seg.Būsena.replace({"ECL_EUR":"Dabartinis tikėtinas kredito nuostolis"}); fig=px.bar(stress_seg,x="Customer_Segment",y="Nuostolis",color="Būsena",barmode="group",title="Tikėtino kredito nuostolio pokytis pagal klientų segmentą",labels={"Customer_Segment":"Klientų segmentas","Nuostolis":"Eurai"}); st.plotly_chart(style_fig(fig),use_container_width=True)
    top=stress_df.nlargest(15,"Nuostolio padidėjimas").merge(loans[["Loan_ID","Product_Name"]],on="Loan_ID",how="left"); st.markdown('<div class="insight"><b>Vadovybės klausimas:</b> žemiau pateiktos paskolos generuoja didžiausią papildomą nuostolį pasirinkto ekonominio scenarijaus atveju. Jos būtų pirmos kandidatės individualiai peržiūrai.</div>',unsafe_allow_html=True); st.dataframe(top[["Loan_ID","Product_Name","Customer_Segment","EAD_EUR","ECL_EUR","Nuostolis po streso","Nuostolio padidėjimas"]].rename(columns={"Loan_ID":"Paskola","Product_Name":"Produktas","Customer_Segment":"Klientų segmentas","EAD_EUR":"Kredito pozicija","ECL_EUR":"Dabartinis tikėtinas kredito nuostolis"}),use_container_width=True,hide_index=True)

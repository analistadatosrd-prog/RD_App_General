valor_7 = df_filtrado["valorventa7dias"].apply(to_num).sum()
unds_7 = df_filtrado["undvendidas7dias"].apply(to_num).sum()
prom_7 = unds_7 / 7 if unds_7 else 0
quiebre_7 = df_filtrado["quiebrestock7dias"].apply(to_num).mean()

valor_30 = df_filtrado["valorventa30dias"].apply(to_num).sum()
unds_30 = df_filtrado["undvendidas30dias"].apply(to_num).sum()
prom_30 = unds_30 / 30 if unds_30 else 0
quiebre_30 = df_filtrado["quiebrestock30dias"].apply(to_num).mean()

st.markdown("---")
st.markdown('<div class="block-title">Ventas 7 días</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-card-label">Valor vendido</div>
        <div class="kpi-card-value">{fmt_money(valor_7)}</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-card-label">Unidades vendidas</div>
        <div class="kpi-card-value">{fmt_units(unds_7)}</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-card-label">Promedio venta x día</div>
        <div class="kpi-card-value">{fmt_units(prom_7)}</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(quiebre_badge_html(quiebre_7), unsafe_allow_html=True)

st.markdown('<div class="block-title">Ventas 30 días</div>', unsafe_allow_html=True)

d1, d2, d3, d4 = st.columns(4)
with d1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-card-label">Valor vendido</div>
        <div class="kpi-card-value">{fmt_money(valor_30)}</div>
    </div>
    """, unsafe_allow_html=True)

with d2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-card-label">Unidades vendidas</div>
        <div class="kpi-card-value">{fmt_units(unds_30)}</div>
    </div>
    """, unsafe_allow_html=True)

with d3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-card-label">Promedio venta x día</div>
        <div class="kpi-card-value">{fmt_units(prom_30)}</div>
    </div>
    """, unsafe_allow_html=True)

with d4:
    st.markdown(quiebre_badge_html(quiebre_30), unsafe_allow_html=True)

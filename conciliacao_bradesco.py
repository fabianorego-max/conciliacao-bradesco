# -*- coding: utf-8 -*-
"""
Sistema Web de Conciliação de Cartões Bradesco (Streamlit)

Estrutura de colunas (A até O):
  A) Cartão            - Dado cadastral
  B) Resumo 7 dígitos  - Dado cadastral
  C) Titular           - Dado cadastral
  D) CPF               - Dado cadastral
  E) Localidade        - Dado cadastral
  F) Limite            - Dado cadastral
  G) Aprovado Reunião  - Entrada manual
  H) Valor Fatura      - Entrada manual
  I) Saldo Anterior    - Recebe valor da Coluna O do mês anterior
  J) Diferença a Pagar - Lógica: se H > G => J = H - G, senão J = 0
  K) Diferença a Receber - Lógica: se H < G => K = G - H, senão K = 0
  L) Saldo Final Ajustado - Fórmula: I + J - K
  M) Saldo Próxima Reunião - Fórmula: G + L - H
  N) Pós-Fechamento    - Entrada manual
  O) Saldo Final do Mês - Fórmula: G + L - N
"""
import streamlit as st
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP

# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Conciliação Bradesco",
    page_icon="💳",
    layout="wide",
)

st.title("Conciliação Bradesco")

# ---------------------------------------------------------------------------
# Chaves internas das colunas A a O
# ---------------------------------------------------------------------------
COLUNAS_TEXTO = [
    "A_Cartao",
    "B_Bandeira",
    "C_Titular",
    "D_Categoria",
    "E_Status",
]

COLUNAS_NUMERO = [
    "F_Compras",
    "G_Pagamentos",
    "H_Taxas",
    "I_SaldoInicial",
    "J_TotalDebito",
    "K_AposPagamento",
    "L_ComTaxas",
    "M_PagMinimo",
    "N_SaldoDevedor",
    "O_SaldoFinal",
]

TODAS_COLUNAS = COLUNAS_TEXTO + COLUNAS_NUMERO

# Apelidos padrão (rótulos exibidos no data_editor)
APELIDOS_PADRAO = {
    "A_Cartao": "A - Cartão",
    "B_Bandeira": "B - Bandeira",
    "C_Titular": "C - Titular",
    "D_Categoria": "D - Categoria",
    "E_Status": "E - Status",
    "F_Compras": "F - Compras",
    "G_Pagamentos": "G - Pagamentos",
    "H_Taxas": "H - Taxas",
    "I_SaldoInicial": "I - Saldo Inicial",
    "J_TotalDebito": "J - Total Débito",
    "K_AposPagamento": "K - Após Pagamento",
    "L_ComTaxas": "L - Com Taxas",
    "M_PagMinimo": "M - Pag. Mínimo",
    "N_SaldoDevedor": "N - Saldo Devedor",
    "O_SaldoFinal": "O - Saldo Final",
}

# ---------------------------------------------------------------------------
# Inicialização do session_state
# ---------------------------------------------------------------------------
if "apelidos" not in st.session_state:
    st.session_state.apelidos = dict(APELIDOS_PADRAO)

# Garante que TODAS as chaves A a O existam no dicionário de apelidos
for chave, apelido_padrao in APELIDOS_PADRAO.items():
    if chave not in st.session_state.apelidos or not st.session_state.apelidos[chave]:
        st.session_state.apelidos[chave] = apelido_padrao

if "dados" not in st.session_state:
    st.session_state.dados = {}

if "anos_disponiveis" not in st.session_state:
    st.session_state.anos_disponiveis = list(range(2023, 2031))

if "ano_selecionado" not in st.session_state:
    st.session_state.ano_selecionado = st.session_state.anos_disponiveis[0]

if "mes_selecionado" not in st.session_state:
    st.session_state.mes_selecionado = 1

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def chave_periodo(ano: int, mes: int) -> str:
    return f"{ano}-{mes:02d}"


def obter_dataframe_periodo(ano: int, mes: int) -> pd.DataFrame:
    """Retorna o DataFrame do período, criando um vazio se não existir."""
    chave = chave_periodo(ano, mes)
    if chave not in st.session_state.dados:
        st.session_state.dados[chave] = pd.DataFrame(columns=TODAS_COLUNAS)
    df = st.session_state.dados[chave].copy()
    # Garante que todas as colunas existam
    for col in TODAS_COLUNAS:
        if col not in df.columns:
            df[col] = None
    return df[TODAS_COLUNAS]


def salvar_dataframe_periodo(ano: int, mes: int, df: pd.DataFrame) -> None:
    chave = chave_periodo(ano, mes)
    st.session_state.dados[chave] = df.copy()


def calcular_saldo_final(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica a lógica de transporte de saldo linha a linha.

    - Saldo Inicial (I) da primeira linha vem do Saldo Final (O) do período anterior.
    - Saldo Inicial das linhas seguintes = Saldo Final da linha anterior.
    - Total Débito (J) = Compras (F) + Taxas (H)
    - Após Pagamento (K) = Saldo Inicial (I) + Total Débito (J) - Pagamentos (G)
    - Com Taxas (L) = Após Pagamento (K) + Taxas (H)
    - Pag. Mínimo (M) = 5% de Com Taxas (L)
    - Saldo Devedor (N) = Com Taxas (L) - Pagamentos (G)
    - Saldo Final (O) = Saldo Devedor (N)
    """
    df = df.copy()

    # Converte colunas numéricas para float
    for col in COLUNAS_NUMERO:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Saldo inicial do período: transporta do período anterior
    ano = st.session_state.ano_selecionado
    mes = st.session_state.mes_selecionado
    mes_anterior = mes - 1
    ano_anterior = ano
    if mes_anterior < 1:
        mes_anterior = 12
        ano_anterior = ano - 1

    saldo_inicial_periodo = 0.0
    chave_anterior = chave_periodo(ano_anterior, mes_anterior)
    if chave_anterior in st.session_state.dados:
        df_anterior = st.session_state.dados[chave_anterior]
        if not df_anterior.empty and "O_SaldoFinal" in df_anterior.columns:
            serie = pd.to_numeric(df_anterior["O_SaldoFinal"], errors="coerce").fillna(0.0)
            saldo_inicial_periodo = float(serie.iloc[-1])

    saldo_corrente = saldo_inicial_periodo

    for idx in df.index:
        compras = float(df.at[idx, "F_Compras"] or 0.0)
        pagamentos = float(df.at[idx, "G_Pagamentos"] or 0.0)
        taxas = float(df.at[idx, "H_Taxas"] or 0.0)

        saldo_inicial = saldo_corrente
        total_debito = compras + taxas
        apos_pagamento = saldo_inicial + total_debito - pagamentos
        com_taxas = apos_pagamento + taxas
        pag_minimo = round(com_taxas * 0.05, 2)
        saldo_devedor = com_taxas - pagamentos
        saldo_final = saldo_devedor

        df.at[idx, "I_SaldoInicial"] = round(saldo_inicial, 2)
        df.at[idx, "J_TotalDebito"] = round(total_debito, 2)
        df.at[idx, "K_AposPagamento"] = round(apos_pagamento, 2)
        df.at[idx, "L_ComTaxas"] = round(com_taxas, 2)
        df.at[idx, "M_PagMinimo"] = round(pag_minimo, 2)
        df.at[idx, "N_SaldoDevedor"] = round(saldo_devedor, 2)
        df.at[idx, "O_SaldoFinal"] = round(saldo_final, 2)

        saldo_corrente = saldo_final

    return df


def arredondar(valor: float) -> float:
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Navegação")

    # Navegação por Ano/Mês
    st.session_state.ano_selecionado = st.selectbox(
        "Ano",
        options=st.session_state.anos_disponiveis,
        index=st.session_state.anos_disponiveis.index(st.session_state.ano_selecionado)
        if st.session_state.ano_selecionado in st.session_state.anos_disponiveis
        else 0,
        key="select_ano",
    )

    indice_mes = st.session_state.mes_selecionado - 1
    mes_nome = st.selectbox(
        "Mês",
        options=MESES,
        index=indice_mes if 0 <= indice_mes < 12 else 0,
        key="select_mes",
    )
    st.session_state.mes_selecionado = MESES.index(mes_nome) + 1

    st.divider()

    # -----------------------------------------------------------------------
    # Configurar Apelidos - TODAS as colunas A a O
    # -----------------------------------------------------------------------
    with st.expander("Configurar Apelidos", expanded=False):
        st.caption("Edite o apelido exibido para cada coluna (A a O).")

        st.markdown("**Colunas Alfanuméricas (A - E)**")
        for chave in COLUNAS_TEXTO:
            st.text_input(
                label=chave,
                value=st.session_state.apelidos.get(chave, APELIDOS_PADRAO[chave]),
                key=f"apelido_{chave}",
                on_change=lambda c=chave: st.session_state.apelidos.update(
                    {c: st.session_state[f"apelido_{c}"]}
                ),
            )

        st.markdown("**Colunas Numéricas (F - O)**")
        for chave in COLUNAS_NUMERO:
            st.text_input(
                label=chave,
                value=st.session_state.apelidos.get(chave, APELIDOS_PADRAO[chave]),
                key=f"apelido_{chave}",
                on_change=lambda c=chave: st.session_state.apelidos.update(
                    {c: st.session_state[f"apelido_{c}"]}
                ),
            )

    st.divider()

    # Ações
    if st.button("➕ Adicionar Linha", use_container_width=True):
        df_atual = obter_dataframe_periodo(st.session_state.ano_selecionado, st.session_state.mes_selecionado)
        nova_linha = {col: "" for col in COLUNAS_TEXTO}
        nova_linha.update({col: 0.0 for col in COLUNAS_NUMERO})
        df_atual = pd.concat([df_atual, pd.DataFrame([nova_linha])], ignore_index=True)
        salvar_dataframe_periodo(st.session_state.ano_selecionado, st.session_state.mes_selecionado, df_atual)
        st.rerun()

    if st.button("🔄 Recalcular Saldos", use_container_width=True):
        df_atual = obter_dataframe_periodo(st.session_state.ano_selecionado, st.session_state.mes_selecionado)
        df_atual = calcular_saldo_final(df_atual)
        salvar_dataframe_periodo(st.session_state.ano_selecionado, st.session_state.mes_selecionado, df_atual)
        st.rerun()

# ---------------------------------------------------------------------------
# Corpo principal
# ---------------------------------------------------------------------------
st.subheader(f"Período: {mes_nome} / {st.session_state.ano_selecionado}")

df_periodo = obter_dataframe_periodo(st.session_state.ano_selecionado, st.session_state.mes_selecionado)

# ---------------------------------------------------------------------------
# Construção do column_config mapeando TODAS as chaves A a O
# ---------------------------------------------------------------------------
column_config = {}

# Colunas A a E => TextColumn (alfanumérico)
for chave in COLUNAS_TEXTO:
    column_config[chave] = st.column_config.TextColumn(
        label=st.session_state.apelidos.get(chave, APELIDOS_PADRAO[chave]),
        help=f"Coluna alfanumérica {chave}",
    )

# Colunas F a O => NumberColumn
for chave in COLUNAS_NUMERO:
    column_config[chave] = st.column_config.NumberColumn(
        label=st.session_state.apelidos.get(chave, APELIDOS_PADRAO[chave]),
        help=f"Coluna numérica {chave}",
        format="%.2f",
        step=0.01,
    )

# ---------------------------------------------------------------------------
# Data Editor
# ---------------------------------------------------------------------------
df_editado = st.data_editor(
    df_periodo,
    column_config=column_config,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_{chave_periodo(st.session_state.ano_selecionado, st.session_state.mes_selecionado)}",
    hide_index=False,
)

# Salva as edições do usuário
salvar_dataframe_periodo(st.session_state.ano_selecionado, st.session_state.mes_selecionado, df_editado)

# ---------------------------------------------------------------------------
# Recálculo automático de saldos após edição
# ---------------------------------------------------------------------------
df_recalculado = calcular_saldo_final(df_editado)
salvar_dataframe_periodo(st.session_state.ano_selecionado, st.session_state.mes_selecionado, df_recalculado)

st.divider()

# Exibe o DataFrame recalculado (somente leitura) para conferência
st.markdown("### Visualização com Saldos Recalculados")
st.dataframe(
    df_recalculado.rename(columns=st.session_state.apelidos),
    use_container_width=True,
    hide_index=False,
)

# ---------------------------------------------------------------------------
# Resumo do período
# ---------------------------------------------------------------------------
st.divider()
st.markdown("### Resumo do Período")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(
        label=st.session_state.apelidos.get("F_Compras", "F - Compras"),
        value=f"R$ {arredondar(df_recalculado['F_Compras'].sum()):,.2f}",
    )
with col2:
    st.metric(
        label=st.session_state.apelidos.get("G_Pagamentos", "G - Pagamentos"),
        value=f"R$ {arredondar(df_recalculado['G_Pagamentos'].sum()):,.2f}",
    )
with col3:
    st.metric(
        label=st.session_state.apelidos.get("H_Taxas", "H - Taxas"),
        value=f"R$ {arredondar(df_recalculado['H_Taxas'].sum()):,.2f}",
    )
with col4:
    saldo_final_exibido = (
        float(df_recalculado["O_SaldoFinal"].iloc[-1])
        if not df_recalculado.empty
        else 0.0
    )
    st.metric(
        label=st.session_state.apelidos.get("O_SaldoFinal", "O - Saldo Final"),
        value=f"R$ {arredondar(saldo_final_exibido):,.2f}",
    )

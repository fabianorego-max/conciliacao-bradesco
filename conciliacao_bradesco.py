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
import numpy as np
from io import BytesIO


# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Conciliação",
    page_icon="💳",
    layout="wide",
)

st.title("💳 Sistema de Conciliação")
st.subheader("Edição manual das colunas A a F")


# ---------------------------------------------------------------------------
# Funções utilitárias para tratamento seguro de valores numéricos
# ---------------------------------------------------------------------------
def to_number(value):
    """Converte um valor qualquer para número de forma segura."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return 0.0
        # Remove separadores de milhar e troca vírgula decimal por ponto
        value = value.replace(".", "").replace(",", ".")
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def safe_format_currency(value):
    """Formata um valor numérico como moeda brasileira de forma segura."""
    number = to_number(value)
    return f"R$ {number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def safe_format_percent(value):
    """Formata um valor numérico como percentual de forma segura."""
    number = to_number(value)
    return f"{number:.2f}%"


# ---------------------------------------------------------------------------
# Dados de exemplo (simulação de conciliação)
# ---------------------------------------------------------------------------
@st.cache_data
def load_sample_data() -> pd.DataFrame:
    data = {
        "A_Cartao": ["1234****5678", "2345****6789", "3456****7890", "4567****8901"],
        "B_Resumo": ["Resumo 001", "Resumo 002", "Resumo 003", "Resumo 004"],
        "C_Titular": ["João da Silva", "Maria Oliveira", "Carlos Santos", "Ana Souza"],
        "D_CPF": ["123.456.789-00", "987.654.321-00", "456.789.123-00", "321.654.987-00"],
        "E_Localidade": ["São Paulo / SP", "Rio de Janeiro / RJ", "Belo Horizonte / MG", "Curitiba / PR"],
        "F_Limite": [10000.00, 15000.00, 8000.00, 12000.00],
        "G_Valores": [2500.00, 3200.00, 1800.00, 4500.00],
        "H_Pagamentos": [2300.00, 3100.00, 1700.00, 4400.00],
        "I_Saldo": [200.00, 100.00, 100.00, 100.00],
        "J_PercentualUsado": [25.00, 21.33, 22.50, 37.50],
        "K_Diferenca": [0.00, 0.00, 0.00, 0.00],
        "L_Status": ["Conciliado", "Conciliado", "Conciliado", "Conciliado"],
        "M_TotalDevido": [2500.00, 3200.00, 1800.00, 4500.00],
        "N_Observacoes": ["", "", "", ""],
        "O_IndiceConciliacao": [100.00, 100.00, 100.00, 100.00],
    }
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Inicialização do estado da sessão
# ---------------------------------------------------------------------------
if "df_conciliacao" not in st.session_state:
    st.session_state.df_conciliacao = load_sample_data().copy()

if "edicoes_manuais" not in st.session_state:
    st.session_state.edicoes_manuais = {}


def recalcular_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Recalcula as colunas de cálculo (J, K, L, M, O) de forma segura."""
    df = df.copy()

    # M_TotalDevido = G_Valores - H_Pagamentos
    df["M_TotalDevido"] = df.apply(
        lambda row: to_number(row["G_Valores"]) - to_number(row["H_Pagamentos"]),
        axis=1,
    )

    # J_PercentualUsado = (G_Valores / F_Limite) * 100
    df["J_PercentualUsado"] = df.apply(
        lambda row: (
            (to_number(row["G_Valores"]) / to_number(row["F_Limite"]) * 100)
            if to_number(row["F_Limite"]) != 0
            else 0.0
        ),
        axis=1,
    )

    # K_Diferenca = G_Valores - H_Pagamentos - I_Saldo
    df["K_Diferenca"] = df.apply(
        lambda row: (
            to_number(row["G_Valores"])
            - to_number(row["H_Pagamentos"])
            - to_number(row["I_Saldo"])
        ),
        axis=1,
    )

    # L_Status baseado na diferença
    df["L_Status"] = df["K_Diferenca"].apply(
        lambda diff: "Conciliado" if abs(to_number(diff)) < 0.01 else "Divergente"
    )

    # O_IndiceConciliacao = (H_Pagamentos / G_Valores) * 100
    df["O_IndiceConciliacao"] = df.apply(
        lambda row: (
            (to_number(row["H_Pagamentos"]) / to_number(row["G_Valores"]) * 100)
            if to_number(row["G_Valores"]) != 0
            else 0.0
        ),
        axis=1,
    )

    return df


# ---------------------------------------------------------------------------
# Exibição do data_editor
# ---------------------------------------------------------------------------
st.markdown("### Tabela de Conciliação")
st.info(
    "ℹ️ As colunas **A a F** (Cartão, Resumo, Titular, CPF, Localidade, Limite) "
    "são editáveis. As colunas de cálculo **J, K, L, M, O** são somente leitura."
)

# Configuração das colunas: A a F editáveis, cálculo (J, K, L, M, O) desabilitadas
column_config = {
    "A_Cartao": st.column_config.TextColumn(
        "A - Cartão",
        help="Número do cartão (editável)",
    ),
    "B_Resumo": st.column_config.TextColumn(
        "B - Resumo",
        help="Resumo da transação (editável)",
    ),
    "C_Titular": st.column_config.TextColumn(
        "C - Titular",
        help="Nome do titular (editável)",
    ),
    "D_CPF": st.column_config.TextColumn(
        "D - CPF",
        help="CPF do titular (editável)",
    ),
    "E_Localidade": st.column_config.TextColumn(
        "E - Localidade",
        help="Localidade do titular (editável)",
    ),
    "F_Limite": st.column_config.NumberColumn(
        "F - Limite",
        help="Limite do cartão (editável)",
        format="R$ %.2f",
        step=0.01,
    ),
    "G_Valores": st.column_config.NumberColumn(
        "G - Valores",
        format="R$ %.2f",
        step=0.01,
    ),
    "H_Pagamentos": st.column_config.NumberColumn(
        "H - Pagamentos",
        format="R$ %.2f",
        step=0.01,
    ),
    "I_Saldo": st.column_config.NumberColumn(
        "I - Saldo",
        format="R$ %.2f",
        step=0.01,
    ),
    "J_PercentualUsado": st.column_config.NumberColumn(
        "J - % Usado",
        help="Percentual do limite usado (somente leitura)",
        format="%.2f%%",
        disabled=True,
    ),
    "K_Diferenca": st.column_config.NumberColumn(
        "K - Diferença",
        help="Diferença de conciliação (somente leitura)",
        format="R$ %.2f",
        disabled=True,
    ),
    "L_Status": st.column_config.TextColumn(
        "L - Status",
        help="Status da conciliação (somente leitura)",
        disabled=True,
    ),
    "M_TotalDevido": st.column_config.NumberColumn(
        "M - Total Devido",
        help="Total devido (somente leitura)",
        format="R$ %.2f",
        disabled=True,
    ),
    "N_Observacoes": st.column_config.TextColumn(
        "N - Observações",
        help="Observações adicionais (editável)",
    ),
    "O_IndiceConciliacao": st.column_config.NumberColumn(
        "O - Índice Conciliação",
        help="Índice de conciliação (somente leitura)",
        format="%.2f%%",
        disabled=True,
    ),
}

# Lista de colunas de cálculo que devem permanecer desabilitadas
colunas_calculo_disabled = [
    "J_PercentualUsado",
    "K_Diferenca",
    "L_Status",
    "M_TotalDevido",
    "O_IndiceConciliacao",
]

# Renderiza o data_editor
# As colunas A_Cartao, B_Resumo, C_Titular, D_CPF, E_Localidade e F_Limite
# NÃO possuem disabled=True, portanto são editáveis.
df_editado = st.data_editor(
    st.session_state.df_conciliacao,
    column_config=column_config,
    disabled=colunas_calculo_disabled,
    num_rows="dynamic",
    use_container_width=True,
    key="data_editor_conciliacao",
    hide_index=True,
)

# ---------------------------------------------------------------------------
# Processamento das edições
# ---------------------------------------------------------------------------
if df_editado is not None and not df_editado.equals(st.session_state.df_conciliacao):
    # Atualiza o DataFrame com as edições manuais das colunas A a F
    st.session_state.df_conciliacao = df_editado.copy()

    # Recalcula as colunas de cálculo de forma segura
    st.session_state.df_conciliacao = recalcular_colunas(
        st.session_state.df_conciliacao
    )

    # Garante que os valores numéricos estejam corretamente tipados
    colunas_numericas = [
        "F_Limite",
        "G_Valores",
        "H_Pagamentos",
        "I_Saldo",
        "J_PercentualUsado",
        "K_Diferenca",
        "M_TotalDevido",
        "O_IndiceConciliacao",
    ]
    for col in colunas_numericas:
        st.session_state.df_conciliacao[col] = (
            st.session_state.df_conciliacao[col].apply(to_number)
        )

    st.success("✅ Edições manuais aplicadas e colunas de cálculo recalculadas!")
    st.rerun()


# ---------------------------------------------------------------------------
# Resumo e exportação
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### 📊 Resumo da Conciliação")

df_atual = st.session_state.df_conciliacao

col1, col2, col3, col4 = st.columns(4)

total_limite = df_atual["F_Limite"].apply(to_number).sum()
total_valores = df_atual["G_Valores"].apply(to_number).sum()
total_pagamentos = df_atual["H_Pagamentos"].apply(to_number).sum()
total_divergencias = (
    df_atual["K_Diferenca"].apply(to_number).abs().apply(lambda x: x if x >= 0.01 else 0).sum()
)

col1.metric("Total Limite", safe_format_currency(total_limite))
col2.metric("Total Valores", safe_format_currency(total_valores))
col3.metric("Total Pagamentos", safe_format_currency(total_pagamentos))
col4.metric("Total Divergências", safe_format_currency(total_divergencias))


# ---------------------------------------------------------------------------
# Exportação para Excel
# ---------------------------------------------------------------------------
st.markdown("### 📥 Exportar")

def exportar_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Conciliação")
    return output.getvalue()


st.download_button(
    label="⬇️ Baixar Excel",
    data=exportar_excel(df_atual),
    file_name="conciliacao.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

if st.button("🔄 Recalcular Tudo"):
    st.session_state.df_conciliacao = recalcular_colunas(df_atual)
    st.success("✅ Recálculo concluído!")
    st.rerun()

if st.button("🗑️ Restaurar Dados de Exemplo"):
    st.session_state.df_conciliacao = load_sample_data().copy()
    st.cache_data.clear()
    st.success("✅ Dados restaurados!")
    st.rerun()

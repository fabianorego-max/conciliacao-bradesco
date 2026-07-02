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

import pandas as pd
import streamlit as st
from io import BytesIO

# Colunas financeiras que devem ser tratadas com seguranca numerica
FINANCIAL_COLUMNS = ['F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O']


def safe_numeric(df: pd.DataFrame, columns=FINANCIAL_COLUMNS) -> pd.DataFrame:
    """Converte colunas financeiras para numerico de forma segura.

    Usa pd.to_numeric com errors='coerce' e fillna(0) para evitar
    ValueError durante somas ou formatacoes de st.metric.
    """
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


def format_currency(value: float) -> str:
    """Formata um valor numerico como moeda brasileira de forma segura."""
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


def load_data(uploaded_file) -> pd.DataFrame:
    """Carrega um arquivo Excel/CSV e aplica a conversao numerica segura."""
    if uploaded_file is None:
        return pd.DataFrame()

    if uploaded_file.name.lower().endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df = safe_numeric(df)
    return df


def calculate_reconciliation(df: pd.DataFrame) -> dict:
    """Realiza os calculos de conciliacao usando colunas financeiras tratadas."""
    df = safe_numeric(df)

    totals = {}
    for col in FINANCIAL_COLUMNS:
        if col in df.columns:
            totals[col] = float(df[col].sum())
        else:
            totals[col] = 0.0

    total_entradas = float(df['F'].sum() + df['H'].sum() + df['J'].sum() + df['L'].sum() + df['N'].sum()) \
        if all(c in df.columns for c in ['F', 'H', 'J', 'L', 'N']) else 0.0

    total_saidas = float(df['G'].sum() + df['I'].sum() + df['K'].sum() + df['M'].sum() + df['O'].sum()) \
        if all(c in df.columns for c in ['G', 'I', 'K', 'M', 'O']) else 0.0

    saldo_conciliado = total_entradas - total_saidas

    return {
        'totals': totals,
        'total_entradas': total_entradas,
        'total_saidas': total_saidas,
        'saldo_conciliado': saldo_conciliado,
    }


def render_dashboard(df: pd.DataFrame, results: dict) -> None:
    """Renderiza o Dashboard com metricas seguras contra erros de conversao."""
    st.subheader("Dashboard de Conciliacao")

    df = safe_numeric(df)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Total de Entradas", value=format_currency(results['total_entradas']))
    with col2:
        st.metric(label="Total de Saidas", value=format_currency(results['total_saidas']))
    with col3:
        st.metric(label="Saldo Conciliado", value=format_currency(results['saldo_conciliado']))

    st.markdown("### Detalhamento por Coluna Financeira")
    metric_cols = st.columns(len(FINANCIAL_COLUMNS))
    for idx, col in enumerate(FINANCIAL_COLUMNS):
        with metric_cols[idx]:
            value = results['totals'].get(col, 0.0)
            st.metric(label=f"Coluna {col}", value=format_currency(value))

    st.markdown("### Dados Conciliados")
    st.dataframe(df, use_container_width=True)


def export_results(df: pd.DataFrame) -> BytesIO:
    """Exporta os dados conciliados para um arquivo Excel em memoria."""
    df = safe_numeric(df)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Conciliacao')
    output.seek(0)
    return output


def main() -> None:
    st.title("Sistema de Conciliacao Financeira")

    uploaded_file = st.file_uploader(
        "Selecione o arquivo de conciliacao (Excel ou CSV)",
        type=['xlsx', 'xls', 'csv']
    )

    if uploaded_file is not None:
        df = load_data(uploaded_file)

        if df.empty:
            st.warning("Nenhum dado valido encontrado no arquivo.")
            return

        df = safe_numeric(df)
        results = calculate_reconciliation(df)
        render_dashboard(df, results)

        st.markdown("### Exportar Resultados")
        excel_data = export_results(df)
        st.download_button(
            label="Baixar Conciliacao (Excel)",
            data=excel_data,
            file_name='conciliacao_resultado.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        st.info("Carregue um arquivo para iniciar a conciliacao.")


if __name__ == '__main__':
    main()

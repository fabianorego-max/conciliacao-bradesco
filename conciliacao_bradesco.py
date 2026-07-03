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
from streamlit.components.v1 import html


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
EXPECTED_COLUMNS = [
    "Data",
    "Documento",
    "Historico",
    "Entrada (I)",
    "Saida (O)",
    "Saldo",
]

NUMERIC_COLUMNS = ["Entrada (I)", "Saida (O)", "Saldo"]
STRING_COLUMNS = ["Data", "Documento", "Historico"]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the DataFrame has the expected columns in the expected order."""
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        st.error(f"Planilha sem colunas obrigatórias: {', '.join(missing)}")
        st.stop()

    df = df[EXPECTED_COLUMNS].copy()
    return df


def cast_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cast every column to the exact type expected by st.data_editor.

    This is the core fix for StreamlitAPIException: numeric columns must be
    real floats (not object/str) and text columns must be real strings.
    Empty/blank values are converted to 0.0 for numerics and "" for strings,
    so the editor never receives mixed types.
    """
    df = df.copy()

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            # Coerce to numeric, turn non-numeric/blank into NaN, then fill with 0.0
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    for col in STRING_COLUMNS:
        if col in df.columns:
            # Convert everything to string, treat NaN/None as empty string
            df[col] = df[col].astype(object).where(df[col].notna(), "")
            df[col] = df[col].astype(str).str.strip()

    return df


def calculate_saldo(df: pd.DataFrame, initial_balance: float = 0.0) -> pd.DataFrame:
    """
    Automatic calculation of the running Saldo.
    Saldo = previous Saldo + Entrada (I) - Saida (O)
    """
    df = df.copy()
    running = float(initial_balance)
    saldos = []
    for _, row in df.iterrows():
        entrada = float(row["Entrada (I)"] or 0.0)
        saida = float(row["Saida (O)"] or 0.0)
        running = running + entrada - saida
        saldos.append(round(running, 2))
    df["Saldo"] = saldos
    return df


def carry_over_balance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Balance carry-over (O -> I):
    If a row has a value in 'Saida (O)' and the next row has no 'Entrada (I)',
    carry the previous 'Saida (O)' into the next row's 'Entrada (I)'.
    """
    df = df.copy().reset_index(drop=True)
    for i in range(1, len(df)):
        prev_saida = float(df.loc[i - 1, "Saida (O)"] or 0.0)
        curr_entrada = float(df.loc[i, "Entrada (I)"] or 0.0)
        if prev_saida != 0.0 and curr_entrada == 0.0:
            df.loc[i, "Entrada (I)"] = prev_saida
    return df


def build_column_config():
    """Build a st.column_config that matches the casted DataFrame types."""
    return {
        "Data": st.column_config.TextColumn("Data", help="Data do lançamento"),
        "Documento": st.column_config.TextColumn("Documento", help="Número do documento"),
        "Historico": st.column_config.TextColumn("Histórico", help="Descrição do lançamento"),
        "Entrada (I)": st.column_config.NumberColumn(
            "Entrada (I)",
            help="Valor de entrada",
            format="%.2f",
            step=0.01,
        ),
        "Saida (O)": st.column_config.NumberColumn(
            "Saída (O)",
            help="Valor de saída",
            format="%.2f",
            step=0.01,
        ),
        "Saldo": st.column_config.NumberColumn(
            "Saldo",
            help="Saldo calculado automaticamente",
            format="%.2f",
            step=0.01,
            disabled=True,
        ),
    }


# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Bradesco Conciliação", layout="wide")
st.title("Bradesco Conciliação")
st.caption(
    "Importe uma planilha padrão, edite os lançamentos e o sistema recalcula "
    "automaticamente o saldo e o carry-over (O -> I)."
)

# Upload
uploaded_file = st.file_uploader(
    "Importar planilha padrão (xlsx, xls, csv)",
    type=["xlsx", "xls", "csv"],
)

if "df" not in st.session_state:
    st.session_state["df"] = pd.DataFrame(columns=EXPECTED_COLUMNS)

if uploaded_file is not None:
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            raw = pd.read_csv(uploaded_file)
        else:
            raw = pd.read_excel(uploaded_file)

        raw = normalize_columns(raw)
        raw = cast_columns(raw)
        raw = carry_over_balance(raw)
        raw = calculate_saldo(raw, initial_balance=0.0)
        st.session_state["df"] = raw
        st.success("Planilha importada e processada com sucesso.")
    except Exception as exc:
        st.error(f"Erro ao importar a planilha: {exc}")

# Toolbar
col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    if st.button("Adicionar linha"):
        new_row = {c: "" for c in EXPECTED_COLUMNS}
        new_row["Entrada (I)"] = 0.0
        new_row["Saida (O)"] = 0.0
        new_row["Saldo"] = 0.0
        st.session_state["df"] = pd.concat(
            [st.session_state["df"], pd.DataFrame([new_row])],
            ignore_index=True,
        )
with col2:
    if st.button("Recalcular"):
        st.session_state["df"] = cast_columns(st.session_state["df"])
        st.session_state["df"] = carry_over_balance(st.session_state["df"])
        st.session_state["df"] = calculate_saldo(st.session_state["df"], initial_balance=0.0)
        st.success("Cálculos atualizados.")

# -----------------------------------------------------------------------------
# Data Editor
# -----------------------------------------------------------------------------
# CRITICAL FIX: always cast before rendering so column types match
# the column_config exactly. This prevents StreamlitAPIException caused
# by object/str values in numeric columns.
editor_df = cast_columns(st.session_state["df"])

edited = st.data_editor(
    editor_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config=build_column_config(),
    key="bradesco_data_editor",
)

# Persist edits and keep Saldo in sync
st.session_state["df"] = cast_columns(edited)

# Recalculate Saldo automatically after edits
recalculated = calculate_saldo(st.session_state["df"], initial_balance=0.0)
if not recalculated.equals(st.session_state["df"]):
    st.session_state["df"] = recalculated
    st.rerun()

# Summary
st.subheader("Resumo")
total_entrada = float(st.session_state["df"]["Entrada (I)"].sum())
total_saida = float(st.session_state["df"]["Saida (O)"].sum())
saldo_final = float(st.session_state["df"]["Saldo"].iloc[-1]) if len(st.session_state["df"]) else 0.0

m1, m2, m3 = st.columns(3)
m1.metric("Total Entradas (I)", f"R$ {total_entrada:,.2f}")
m2.metric("Total Saídas (O)", f"R$ {total_saida:,.2f}")
m3.metric("Saldo Final", f"R$ {saldo_final:,.2f}")

# Export
st.subheader("Exportar")
export_name = st.text_input("Nome do arquivo", value="conciliacao_bradesco.xlsx")
if st.button("Baixar planilha"):
    out = cast_columns(st.session_state["df"])
    out = calculate_saldo(out, initial_balance=0.0)
    st.download_button(
        label="Baixar .xlsx",
        data=out.to_excel(index=False),
        file_name=export_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

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

# =============================================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================================
st.set_page_config(
    page_title="Conciliação Bradesco",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏦 Conciliação Bradesco")

# =============================================================================
# BARRA LATERAL — APELIDOS PERSONIZADOS E NAVEGAÇÃO
# =============================================================================
st.sidebar.header("⚙️ Configurações")

# Apelidos personalizados para as colunas A a O
st.sidebar.subheader("Apelidos Personalizados")

default_aliases = {
    "A": "Coluna A",
    "B": "Coluna B",
    "C": "Coluna C",
    "D": "Coluna D",
    "E": "Coluna E",
    "F": "Coluna F",
    "G": "Coluna G",
    "H": "Coluna H",
    "I": "Coluna I",
    "J": "Coluna J",
    "K": "Coluna K",
    "L": "Coluna L",
    "M": "Coluna M",
    "N": "Coluna N",
    "O": "Coluna O",
}

# Inicializa apelidos no session_state
if "aliases" not in st.session_state:
    st.session_state.aliases = default_aliases.copy()

with st.sidebar.expander("Editar Apelidos das Colunas", expanded=False):
    for col in list(default_aliases.keys()):
        st.session_state.aliases[col] = st.text_input(
            f"Apelido para coluna {col}",
            value=st.session_state.aliases.get(col, default_aliases[col]),
            key=f"alias_{col}",
        )

# Navegação por Ano/Mês
st.sidebar.subheader("📅 Navegação por Ano/Mês")

anos_disponiveis = [2021, 2022, 2023, 2024, 2025]
meses_disponiveis = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

ano_selecionado = st.sidebar.selectbox("Ano", anos_disponiveis, index=len(anos_disponiveis) - 1)
mes_selecionado = st.sidebar.selectbox(
    "Mês",
    list(meses_disponiveis.keys()),
    format_func=lambda m: meses_disponiveis[m],
)

st.sidebar.markdown(f"**Período selecionado:** {meses_disponiveis[mes_selecionado]} / {ano_selecionado}")

# =============================================================================
# COLUNAS DO DATAFRAME
# =============================================================================
COLUNAS_ALFANUMERICAS = ["A", "B", "C", "D", "E"]
COLUNAS_NUMERICAS = ["F", "G", "H", "I"]
COLUNAS_CALCULADAS = ["J", "K", "L", "M", "N", "O"]
TODAS_COLUNAS = COLUNAS_ALFANUMERICAS + COLUNAS_NUMERICAS + COLUNAS_CALCULADAS

# =============================================================================
# INICIALIZAÇÃO DO DATAFRAME NO SESSION_STATE
# =============================================================================
if "df_conciliacao" not in st.session_state:
    dados_iniciais = {col: [""] * 5 for col in COLUNAS_ALFANUMERICAS}
    for col in COLUNAS_NUMERICAS:
        dados_iniciais[col] = [0.0] * 5
    for col in COLUNAS_CALCULADAS:
        dados_iniciais[col] = [0.0] * 5
    st.session_state.df_conciliacao = pd.DataFrame(dados_iniciais, columns=TODAS_COLUNAS)

# =============================================================================
# FUNÇÃO DE PROCESSAMENTO DE DADOS
# =============================================================================
def processar_dados(df: pd.DataFrame) -> pd.DataFrame:
    """
    Processa o DataFrame garantindo que as colunas A a E sejam tratadas
    como strings (texto alfanumérico) antes de qualquer manipulação.
    Calcula as colunas J a O com base nas colunas F a I.
    """
    df = df.copy()

    # Garantir que as colunas alfanuméricas sejam strings
    for col in COLUNAS_ALFANUMERICAS:
        if col in df.columns:
            df[col] = df[col].astype(str)
            # Substituir valores 'nan', 'None', 'NaN' por string vazia
            df[col] = df[col].replace(["nan", "None", "NaN", "NaT"], "")

    # Garantir que as colunas numéricas sejam float
    for col in COLUNAS_NUMERICAS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # =====================================================================
    # LÓGICA DE CÁLCULO — COLUNAS J A O
    # =====================================================================
    # J = F + G
    df["J"] = df["F"] + df["G"]

    # K = H - I
    df["K"] = df["H"] - df["I"]

    # L = J - K
    df["L"] = df["J"] - df["K"]

    # M = F * 0.10 (exemplo: 10% sobre F)
    df["M"] = df["F"] * 0.10

    # N = L + M
    df["N"] = df["L"] + df["M"]

    # O = N / (J + 1) (evita divisão por zero)
    df["O"] = np.where(df["J"] + 1 != 0, df["N"] / (df["J"] + 1), 0.0)

    # Arredondar colunas calculadas para 2 casas decimais
    for col in COLUNAS_CALCULADAS:
        df[col] = df[col].round(2)

    return df

# =============================================================================
# UPLOAD DE ARQUIVO (OPCIONAL)
# =============================================================================
st.subheader("📂 Importar Dados")
arquivo = st.file_uploader(
    "Carregar arquivo Excel ou CSV (opcional)",
    type=["xlsx", "xls", "csv"],
    key=f"uploader_{ano_selecionado}_{mes_selecionado}",
)

if arquivo is not None:
    try:
        if arquivo.name.endswith(".csv"):
            df_importado = pd.read_csv(arquivo, dtype=str)
        else:
            df_importado = pd.read_excel(arquivo, dtype=str)

        # Mapear colunas existentes para o formato esperado
        for col in TODAS_COLUNAS:
            if col not in df_importado.columns:
                df_importado[col] = "" if col in COLUNAS_ALFANUMERICAS else 0.0

        df_importado = df_importado[TODAS_COLUNAS]
        st.session_state.df_conciliacao = df_importado
        st.success(f"Arquivo '{arquivo.name}' carregado com sucesso!")
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo: {e}")

# =============================================================================
# EDITOR DE DADOS — st.data_editor
# =============================================================================
st.subheader(f"📝 Tabela de Conciliação — {meses_disponiveis[mes_selecionado]} / {ano_selecionado}")

# Construir a configuração de colunas para o data_editor
column_config_dict = {}

# Colunas A a E como TextColumn (alfanumérico)
for col in COLUNAS_ALFANUMERICAS:
    column_config_dict[col] = st.column_config.TextColumn(
        label=st.session_state.aliases.get(col, col),
        help=f"Digite valores alfanuméricos (texto) para a coluna {col}",
        width="medium",
    )

# Colunas F a I como NumberColumn
for col in COLUNAS_NUMERICAS:
    column_config_dict[col] = st.column_config.NumberColumn(
        label=st.session_state.aliases.get(col, col),
        help=f"Valores numéricos para a coluna {col}",
        format="%.2f",
        width="medium",
    )

# Colunas J a O como NumberColumn (somente leitura — calculadas)
for col in COLUNAS_CALCULADAS:
    column_config_dict[col] = st.column_config.NumberColumn(
        label=st.session_state.aliases.get(col, col),
        help=f"Coluna calculada automaticamente ({col})",
        format="%.2f",
        width="medium",
        disabled=True,
    )

# Exibir o data_editor
df_editado = st.data_editor(
    st.session_state.df_conciliacao,
    column_config=column_config_dict,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_{ano_selecionado}_{mes_selecionado}",
    hide_index=False,
)

# Atualizar o DataFrame no session_state com as edições
st.session_state.df_conciliacao = df_editado

# =============================================================================
# PROCESSAR E EXIBIR RESULTADOS
# =============================================================================
st.subheader("📊 Resultado Processado")

df_processado = processar_dados(st.session_state.df_conciliacao)

# Exibir o DataFrame processado (somente leitura)
st.dataframe(
    df_processado,
    use_container_width=True,
    hide_index=False,
    column_config={
        col: st.column_config.TextColumn(
            label=st.session_state.aliases.get(col, col),
        )
        for col in COLUNAS_ALFANUMERICAS
    },
)

# =============================================================================
# EXPORTAÇÃO
# =============================================================================
st.subheader("💾 Exportar")

col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    if st.button("📥 Exportar para Excel"):
        try:
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_processado.to_excel(writer, index=False, sheet_name=f"{mes_selecionado}_{ano_selecionado}")
            output.seek(0)
            st.download_button(
                label="Baixar Excel",
                data=output,
                file_name=f"conciliacao_bradesco_{mes_selecionado}_{ano_selecionado}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"Erro ao exportar: {e}")

with col_exp2:
    if st.button("📥 Exportar para CSV"):
        try:
            csv_data = df_processado.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Baixar CSV",
                data=csv_data,
                file_name=f"conciliacao_bradesco_{mes_selecionado}_{ano_selecionado}.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"Erro ao exportar: {e}")

# =============================================================================
# RODAPÉ
# =============================================================================
st.markdown("---")
st.caption("Sistema de Conciliação Bradesco — Colunas A a E aceitam valores alfanuméricos.")

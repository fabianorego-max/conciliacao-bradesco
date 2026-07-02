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

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(page_title="Conciliação Bradesco", page_icon="🏦", layout="wide")

st.title("🏦 Conciliação Bradesco")

# ============================================================
# COLUNAS PADRÃO
# ============================================================
COLUNAS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O"]
COLUNAS_TEXTO = ["A", "B", "C", "D", "E"]
COLUNAS_NUMERICAS_MANUAIS = ["F", "G", "H", "I"]
COLUNAS_CALCULADAS = ["J", "K", "L", "M", "N", "O"]

LABELS = {
    "A": "Data",
    "B": "Descrição",
    "C": "Documento",
    "D": "Categoria",
    "E": "Observação",
    "F": "Valor Bruto",
    "G": "Tarifas",
    "H": "Outros Débitos",
    "I": "Saldo Anterior",
    "J": "Entradas",
    "K": "Saídas",
    "L": "Saldo Parcial",
    "M": "Conciliado",
    "N": "Diferença",
    "O": "Saldo Final",
}

# ============================================================
# INICIALIZAÇÃO DE ESTADO
# ============================================================
if "df" not in st.session_state:
    dados_iniciais = {col: [] for col in COLUNAS}
    st.session_state["df"] = pd.DataFrame(dados_iniciais)

if "apelidos" not in st.session_state:
    st.session_state["apelidos"] = {col: LABELS.get(col, col) for col in COLUNAS}

if "ano" not in st.session_state:
    st.session_state["ano"] = 2024

if "mes" not in st.session_state:
    st.session_state["mes"] = 1

if "saldo_transportado" not in st.session_state:
    st.session_state["saldo_transportado"] = 0.0


# ============================================================
# FUNÇÃO RECALCULAR — DEFINIDA ANTES DE QUALQUER USO
# ============================================================
def recalcular(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recalcula automaticamente as colunas J a O com base nos
    valores numéricos das colunas F a I.

    J = Entradas (valores positivos de F)
    K = Saídas (valores negativos de F + G + H)
    L = Saldo Parcial (I + J + K)
    M = Conciliado (L se |N| == 0, senão 0)
    N = Diferença (L - valor esperado, aqui usa 0 como referência)
    O = Saldo Final (I + J + K)
    """
    if df.empty:
        return df.copy()

    df = df.copy()

    # Garantir que colunas numéricas existam e sejam numéricas
    for col in COLUNAS_NUMERICAS_MANUAIS + COLUNAS_CALCULADAS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Garantir colunas de texto
    for col in COLUNAS_TEXTO:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype(str).replace("nan", "")

    # J = Entradas: soma de valores positivos de F
    df["J"] = df["F"].apply(lambda v: v if v > 0 else 0.0)

    # K = Saídas: valores negativos de F + tarifas (G) + outros débitos (H)
    df["K"] = df["F"].apply(lambda v: v if v < 0 else 0.0) + df["G"] + df["H"]

    # L = Saldo Parcial: Saldo Anterior + Entradas + Saídas
    df["L"] = df["I"] + df["J"] + df["K"]

    # N = Diferença: diferença entre saldo parcial e o valor bruto esperado
    #    (aqui consideramos a diferença em relação ao valor líquido F - G - H)
    df["N"] = df["L"] - (df["I"] + df["F"] - df["G"] - df["H"])

    # M = Conciliado: 1 se diferença for zero (ou muito próxima), senão 0
    df["M"] = df["N"].apply(lambda v: 1.0 if abs(v) < 0.01 else 0.0)

    # O = Saldo Final
    df["O"] = df["I"] + df["J"] + df["K"]

    return df


# ============================================================
# SIDEBAR — CONTROLE DE ANO/MÊS E APELIDOS
# ============================================================
st.sidebar.header("📅 Controle de Período")

anos = list(range(2020, 2031))
indice_ano = anos.index(st.session_state["ano"]) if st.session_state["ano"] in anos else 0
st.session_state["ano"] = st.sidebar.selectbox("Ano", anos, index=indice_ano)

meses = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]
indice_mes = st.session_state["mes"] - 1
st.session_state["mes"] = st.sidebar.selectbox("Mês", range(1, 13), index=indice_mes, format_func=lambda m: meses[m - 1])

st.sidebar.markdown("---")
st.sidebar.header("🏷️ Configuração de Apelidos")

with st.sidebar.expander("Editar Apelidos das Colunas", expanded=False):
    for col in COLUNAS:
        novo_apelido = st.text_input(
            f"Coluna {col}",
            value=st.session_state["apelidos"].get(col, LABELS.get(col, col)),
            key=f"apelido_{col}"
        )
        st.session_state["apelidos"][col] = novo_apelido

st.sidebar.markdown("---")

# ============================================================
# IMPORTAÇÃO DE EXCEL/CSV
# ============================================================
st.sidebar.header("📂 Importar Planilha")
arquivo = st.sidebar.file_uploader("Selecione Excel ou CSV", type=["xlsx", "xls", "csv"])

if arquivo is not None:
    try:
        if arquivo.name.lower().endswith(".csv"):
            df_importado = pd.read_csv(arquivo)
        else:
            df_importado = pd.read_excel(arquivo)

        # Mapear colunas importadas para o formato esperado
        df_temp = pd.DataFrame(columns=COLUNAS)

        # Se o arquivo já tem as colunas A-O, usa diretamente
        for col in COLUNAS:
            if col in df_importado.columns:
                df_temp[col] = df_importado[col]
            elif LABELS[col] in df_importado.columns:
                df_temp[col] = df_importado[LABELS[col]]
            else:
                df_temp[col] = None

        # Converter colunas numéricas com segurança
        for col in COLUNAS_NUMERICAS_MANUAIS + COLUNAS_CALCULADAS:
            df_temp[col] = pd.to_numeric(df_temp[col], errors="coerce").fillna(0)

        # Converter colunas de texto
        for col in COLUNAS_TEXTO:
            df_temp[col] = df_temp[col].astype(str).replace("nan", "")

        # Recalcular colunas J-O imediatamente após importação
        df_temp = recalcular(df_temp)

        st.session_state["df"] = df_temp
        st.sidebar.success(f"✅ Importado: {len(df_temp)} registros")
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao importar: {e}")

# ============================================================
# BOTÃO FECHAR MÊS
# ============================================================
st.sidebar.markdown("---")
st.sidebar.header("🔒 Fechar Mês")

if st.sidebar.button("Fechar Mês", help="Transporta o saldo da Coluna O para a Coluna I do próximo mês"):
    df_atual = st.session_state["df"].copy()
    if not df_atual.empty:
        saldo_final = pd.to_numeric(df_atual["O"], errors="coerce").fillna(0).iloc[-1]
        st.session_state["saldo_transportado"] = float(saldo_final)

        # Avançar para o próximo mês
        if st.session_state["mes"] == 12:
            st.session_state["mes"] = 1
            st.session_state["ano"] += 1
        else:
            st.session_state["mes"] += 1

        # Criar nova tabela vazia com saldo transportado na coluna I da primeira linha
        novo_df = pd.DataFrame(columns=COLUNAS)
        nova_linha = {col: "" for col in COLUNAS_TEXTO}
        for col in COLUNAS_NUMERICAS_MANUAIS + COLUNAS_CALCULADAS:
            nova_linha[col] = 0.0
        nova_linha["I"] = st.session_state["saldo_transportado"]
        nova_linha["A"] = f"{st.session_state['mes']:02d}/{st.session_state['ano']}"
        nova_linha["B"] = "Saldo transportado do mês anterior"

        novo_df = pd.concat([novo_df, pd.DataFrame([nova_linha])], ignore_index=True)
        novo_df = recalcular(novo_df)
        st.session_state["df"] = novo_df

        st.sidebar.success(f"✅ Mês fechado! Saldo R$ {st.session_state['saldo_transportado']:.2f} transportado para a Coluna I.")
        st.rerun()
    else:
        st.sidebar.warning("⚠️ Tabela vazia. Nada para fechar.")

# ============================================================
# EXIBIÇÃO DO PERÍODO ATUAL
# ============================================================
st.subheader(f"📋 Período: {meses[st.session_state['mes'] - 1]} / {st.session_state['ano']}")

if st.session_state["saldo_transportado"] != 0.0:
    st.info(f"💰 Saldo transportado do mês anterior: R$ {st.session_state['saldo_transportado']:.2f}")

# ============================================================
# PREPARAR DATAFRAME PARA EXIBIÇÃO COM APELIDOS
# ============================================================
df_exibicao = st.session_state["df"].copy()

# Renomear colunas para exibição usando apelidos
apelidos_display = {col: st.session_state["apelidos"].get(col, LABELS.get(col, col)) for col in COLUNAS}
df_exibicao_display = df_exibicao.rename(columns=apelidos_display)

# ============================================================
# DATA EDITOR — EDIÇÃO MANUAL
# ============================================================
st.subheader("✏️ Tabela de Conciliação")

# Configuração de colunas para o data_editor
config_colunas = {}
for col in COLUNAS_TEXTO:
    config_colunas[apelidos_display[col]] = st.column_config.TextColumn(
        label=apelidos_display[col],
        help=f"Coluna {col} (alfanumérico)",
    )

for col in COLUNAS_NUMERICAS_MANUAIS:
    config_colunas[apelidos_display[col]] = st.column_config.NumberColumn(
        label=apelidos_display[col],
        help=f"Coluna {col} (numérico)",
        format="%.2f",
        step=0.01,
    )

for col in COLUNAS_CALCULADAS:
    config_colunas[apelidos_display[col]] = st.column_config.NumberColumn(
        label=apelidos_display[col],
        help=f"Coluna {col} (calculada automaticamente)",
        format="%.2f",
        disabled=True,
    )

df_editado = st.data_editor(
    df_exibicao_display,
    num_rows="dynamic",
    use_container_width=True,
    column_config=config_colunas,
    key="data_editor_conciliacao",
)

# ============================================================
# PROCESSAR EDIÇÃO — RECALCULAR APÓS ALTERAÇÃO
# ============================================================
# Reverter apelidos para nomes internos
revert_map = {v: k for k, v in apelidos_display.items()}
df_processado = df_editado.rename(columns=revert_map)

# Garantir todas as colunas existam
for col in COLUNAS:
    if col not in df_processado.columns:
        df_processado[col] = 0 if col not in COLUNAS_TEXTO else ""

# Converter colunas numéricas com segurança
for col in COLUNAS_NUMERICAS_MANUAIS + COLUNAS_CALCULADAS:
    df_processado[col] = pd.to_numeric(df_processado[col], errors="coerce").fillna(0)

# Converter colunas de texto
for col in COLUNAS_TEXTO:
    df_processado[col] = df_processado[col].astype(str).replace("nan", "")

# Recalcular colunas J-O
df_recalculado = recalcular(df_processado)

# Atualizar estado
st.session_state["df"] = df_recalculado

# ============================================================
# EXIBIR TABELA RECALCULADA (SOMENTE LEITURA)
# ============================================================
st.subheader("📊 Tabela Recalculada")
df_recalculado_display = df_recalculado.rename(columns=apelidos_display)
st.dataframe(df_recalculado_display, use_container_width=True, hide_index=True)

# ============================================================
# EXPORTAÇÃO
# ============================================================
st.markdown("---")
st.subheader("💾 Exportar")

col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    if st.button("📥 Exportar Excel"):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_recalculado.to_excel(writer, index=False, sheet_name=f"{meses[st.session_state['mes'] - 1]}_{st.session_state['ano']}")
        output.seek(0)
        st.download_button(
            label="Baixar Excel",
            data=output,
            file_name=f"conciliacao_bradesco_{st.session_state['mes']:02d}_{st.session_state['ano']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

with col_exp2:
    if st.button("📥 Exportar CSV"):
        csv = df_recalculado.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Baixar CSV",
            data=csv,
            file_name=f"conciliacao_bradesco_{st.session_state['mes']:02d}_{st.session_state['ano']}.csv",
            mime="text/csv",
        )

# ============================================================
# RODAPÉ
# ============================================================
st.markdown("---")
st.caption("Sistema de Conciliação Bradesco — Edição manual (A-E texto, F-I numérico) | Cálculo automático (J-O)")

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
from datetime import datetime
import io
import os

# -----------------------------------------------------------------------------
# FUNÇÕES UTILITÁRIAS (definidas no topo do arquivo)
# -----------------------------------------------------------------------------

COLUNAS_TEXTO = ["A", "B", "C", "D", "E"]
COLUNAS_NUMERO = ["F", "G", "H", "I", "J", "K", "L", "M", "N", "O"]
TODAS_COLUNAS = COLUNAS_TEXTO + COLUNAS_NUMERO


def recalcular(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recalcula colunas dependentes do DataFrame de conciliação Bradesco.

    Garante que as colunas F, G, H, I, J, K, L, M, N e O sejam numéricas,
    convertendo valores inválidos/vazios para 0.0 (pd.to_numeric com coerce).
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # 1) Garantir que as colunas numéricas sejam float
    for col in COLUNAS_NUMERO:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    # 2) Garantir que as colunas de texto sejam string
    for col in COLUNAS_TEXTO:
        if col in df.columns:
            df[col] = df[col].astype(str).replace({"nan": "", "None": ""})

    # 3) Recálculo de colunas dependentes (exemplo de lógica de conciliação)
    #    F = Entradas, G = Saídas, H = Saldo Parcial, I = Saldo Acumulado
    if {"F", "G", "H"}.issubset(df.columns):
        df["H"] = df["F"] - df["G"]

    if "H" in df.columns and "I" in df.columns:
        saldo_acum = 0.0
        saldos = []
        for _, row in df.iterrows():
            saldo_acum += float(row["H"])
            saldos.append(round(saldo_acum, 2))
        df["I"] = saldos

    # J = Diferença esperada x realizado (exemplo)
    if {"I", "J", "K"}.issubset(df.columns):
        df["J"] = df["I"] - df["K"]

    # L, M, N, O = colunas auxiliares de conferência
    if {"L", "M"}.issubset(df.columns):
        df["N"] = df["L"] + df["M"]
    if {"N", "O"}.issubset(df.columns):
        df["O"] = df["N"]

    return df


def normalizar_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Força a conversão de tipos antes de passar o DataFrame ao st.data_editor:
      - Colunas A-E como string
      - Colunas F-O como float
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    for col in COLUNAS_TEXTO:
        if col in df.columns:
            df[col] = df[col].astype(str).replace({"nan": "", "None": ""})
        else:
            df[col] = ""

    for col in COLUNAS_NUMERO:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
        else:
            df[col] = 0.0

    # Reordenar colunas
    colunas_presentes = [c for c in TODAS_COLUNAS if c in df.columns]
    extras = [c for c in df.columns if c not in TODAS_COLUNAS]
    df = df[colunas_presentes + extras]

    return df


def criar_dataframe_vazio() -> pd.DataFrame:
    """Cria um DataFrame vazio com as colunas padrão A-O."""
    dados = {col: [""] if col in COLUNAS_TEXTO else [0.0] for col in TODAS_COLUNAS}
    df = pd.DataFrame(dados)
    return normalizar_tipos(df)


def carregar_apelidos() -> dict:
    """Carrega os apelidos salvos na session_state."""
    return st.session_state.get("apelidos", {})


def salvar_apelidos(apelidos: dict) -> None:
    """Salva os apelidos na session_state."""
    st.session_state["apelidos"] = apelidos


def transportar_saldo(df: pd.DataFrame, saldo_anterior: float) -> pd.DataFrame:
    """
    Transporta o saldo do mês anterior para a primeira linha do mês atual.
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    if "I" in df.columns and len(df) > 0:
        df.loc[0, "I"] = float(df.loc[0, "I"]) + float(saldo_anterior)
        # Recalcular acumulado
        saldo_acum = 0.0
        saldos = []
        for _, row in df.iterrows():
            saldo_acum += float(row.get("H", 0.0))
            saldos.append(round(saldo_acum + float(saldo_anterior), 2))
        df["I"] = saldos
    return df


# -----------------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Conciliação Bradesco",
    page_icon="🏦",
    layout="wide",
)

st.title("🏦 Sistema de Conciliação Bradesco")

# -----------------------------------------------------------------------------
# INICIALIZAÇÃO DA SESSION_STATE
# -----------------------------------------------------------------------------

if "df_conciliacao" not in st.session_state:
    st.session_state["df_conciliacao"] = criar_dataframe_vazio()

if "apelidos" not in st.session_state:
    st.session_state["apelidos"] = {}

if "ano_selecionado" not in st.session_state:
    st.session_state["ano_selecionado"] = datetime.now().year

if "mes_selecionado" not in st.session_state:
    st.session_state["mes_selecionado"] = datetime.now().month

if "saldo_transportado" not in st.session_state:
    st.session_state["saldo_transportado"] = 0.0

if "mes_fechado" not in st.session_state:
    st.session_state["mes_fechado"] = False

# -----------------------------------------------------------------------------
# BARRA LATERAL - CONFIGURAÇÕES
# -----------------------------------------------------------------------------

st.sidebar.header("⚙️ Configurações")

# Seleção de Ano e Mês
anos_disponiveis = list(range(2020, datetime.now().year + 5))
ano_selecionado = st.sidebar.selectbox(
    "📅 Ano",
    options=anos_disponiveis,
    index=anos_disponiveis.index(st.session_state["ano_selecionado"])
    if st.session_state["ano_selecionado"] in anos_disponiveis
    else len(anos_disponiveis) - 5,
)

meses = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
mes_selecionado = st.sidebar.selectbox(
    "📆 Mês",
    options=list(range(1, 13)),
    format_func=lambda x: meses[x - 1],
    index=st.session_state["mes_selecionado"] - 1,
)

st.session_state["ano_selecionado"] = ano_selecionado
st.session_state["mes_selecionado"] = mes_selecionado

st.sidebar.divider()

# -----------------------------------------------------------------------------
# GESTÃO DE APELIDOS
# -----------------------------------------------------------------------------

st.sidebar.subheader("🏷️ Apelidos de Contas")

apelidos = carregar_apelidos()

with st.sidebar.expander("Gerenciar Apelidos", expanded=False):
    novo_apelido_chave = st.text_input("Chave (ex: conta X)", key="apelido_chave")
    novo_apelido_valor = st.text_input("Apelido", key="apelido_valor")

    if st.button("➕ Adicionar Apelido"):
        if novo_apelido_chave.strip():
            apelidos[novo_apelido_chave.strip()] = novo_apelido_valor.strip()
            salvar_apelidos(apelidos)
            st.success(f"Apelido '{novo_apelido_chave}' adicionado!")
            st.rerun()

    if apelidos:
        st.write("**Apelidos cadastrados:**")
        for chave, valor in list(apelidos.items()):
            col1, col2 = st.columns([3, 1])
            col1.write(f"**{chave}** → {valor}")
            if col2.button("🗑️", key=f"del_{chave}"):
                del apelidos[chave]
                salvar_apelidos(apelidos)
                st.rerun()

st.sidebar.divider()

# -----------------------------------------------------------------------------
# IMPORTAÇÃO DE ARQUIVOS
# -----------------------------------------------------------------------------

st.sidebar.subheader("📥 Importação")

arquivo_importado = st.sidebar.file_uploader(
    "Importar arquivo (CSV ou Excel)",
    type=["csv", "xlsx", "xls"],
    key=f"import_{ano_selecionado}_{mes_selecionado}",
)

if arquivo_importado is not None:
    try:
        if arquivo_importado.name.endswith(".csv"):
            df_import = pd.read_csv(arquivo_importado, dtype=str)
        else:
            df_import = pd.read_excel(arquivo_importado, dtype=str)

        # Mapear colunas importadas para A-O se possível
        colunas_mapeadas = {}
        for i, col in enumerate(TODAS_COLUNAS):
            if i < len(df_import.columns):
                colunas_mapeadas[col] = df_import.columns[i]

        if colunas_mapeadas:
            df_novo = df_import.rename(columns={v: k for k, v in colunas_mapeadas.items()})
            df_novo = df_novo[[c for c in TODAS_COLUNAS if c in df_novo.columns]]
            df_novo = normalizar_tipos(df_novo)
            df_novo = recalcular(df_novo)
            st.session_state["df_conciliacao"] = df_novo
            st.sidebar.success("✅ Arquivo importado com sucesso!")
        else:
            st.sidebar.warning("⚠️ Não foi possível mapear as colunas do arquivo.")
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao importar arquivo: {e}")

st.sidebar.divider()

# -----------------------------------------------------------------------------
# TRANSPORTE DE SALDO
# -----------------------------------------------------------------------------

st.sidebar.subheader("💰 Transporte de Saldo")

saldo_anterior = st.sidebar.number_input(
    "Saldo do mês anterior",
    min_value=0.0,
    value=float(st.session_state["saldo_transportado"]),
    format="%.2f",
    key="saldo_input",
)

if st.sidebar.button("🔄 Aplicar Transporte de Saldo"):
    st.session_state["df_conciliacao"] = transportar_saldo(
        st.session_state["df_conciliacao"], saldo_anterior
    )
    st.session_state["saldo_transportado"] = saldo_anterior
    st.sidebar.success("✅ Saldo transportado!")
    st.rerun()

st.sidebar.divider()

# -----------------------------------------------------------------------------
# FECHAR MÊS
# -----------------------------------------------------------------------------

st.sidebar.subheader("🔒 Fechar Mês")

if st.sidebar.button("📌 Fechar Mês Atual", type="primary"):
    df_atual = st.session_state["df_conciliacao"]
    df_atual = recalcular(df_atual)

    # Calcular saldo final para transporte
    if "I" in df_atual.columns and not df_atual.empty:
        saldo_final = float(df_atual["I"].iloc[-1])
    else:
        saldo_final = 0.0

    st.session_state["saldo_transportado"] = saldo_final
    st.session_state["mes_fechado"] = True

    # Avançar para o próximo mês
    if mes_selecionado == 12:
        st.session_state["mes_selecionado"] = 1
        st.session_state["ano_selecionado"] = ano_selecionado + 1
    else:
        st.session_state["mes_selecionado"] = mes_selecionado + 1

    # Limpar DataFrame para o novo mês
    st.session_state["df_conciliacao"] = criar_dataframe_vazio()
    st.sidebar.success(f"✅ Mês fechado! Saldo transportado: R$ {saldo_final:.2f}")
    st.rerun()

if st.session_state["mes_fechado"]:
    st.sidebar.info(f"💼 Saldo transportado: R$ {st.session_state['saldo_transportado']:.2f}")

# -----------------------------------------------------------------------------
# ÁREA PRINCIPAL - EDITOR DE DADOS
# -----------------------------------------------------------------------------

st.header(f"📋 Conciliação - {meses[mes_selecionado - 1]} {ano_selecionado}")

# Botões de ação
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

with col_btn1:
    if st.button("➕ Adicionar Linha"):
        nova_linha = {col: "" if col in COLUNAS_TEXTO else 0.0 for col in TODAS_COLUNAS}
        st.session_state["df_conciliacao"] = pd.concat(
            [st.session_state["df_conciliacao"], pd.DataFrame([nova_linha])],
            ignore_index=True,
        )
        st.rerun()

with col_btn2:
    if st.button("🔄 Recalcular"):
        st.session_state["df_conciliacao"] = recalcular(st.session_state["df_conciliacao"])
        st.success("✅ Recálculo concluído!")
        st.rerun()

with col_btn3:
    if st.button("🗑️ Limpar Tudo"):
        st.session_state["df_conciliacao"] = criar_dataframe_vazio()
        st.rerun()

# -----------------------------------------------------------------------------
# DATA EDITOR COM CONFIGURAÇÃO DE COLUNAS CORRETA
# -----------------------------------------------------------------------------

df_editor = normalizar_tipos(st.session_state["df_conciliacao"])
df_editor = recalcular(df_editor)

# Construir column_config com tipos EXATOS
column_config = {}

# Colunas A-E: TextColumn
for col in COLUNAS_TEXTO:
    column_config[col] = st.column_config.TextColumn(
        label=col,
        help=f"Coluna de texto {col}",
        required=False,
    )

# Colunas F-O: NumberColumn
for col in COLUNAS_NUMERO:
    column_config[col] = st.column_config.NumberColumn(
        label=col,
        help=f"Coluna numérica {col}",
        format="%.2f",
        required=False,
        default=0.0,
    )

# Exibir o data_editor
df_editado = st.data_editor(
    df_editor,
    num_rows="dynamic",
    use_container_width=True,
    column_config=column_config,
    column_order=TODAS_COLUNAS,
    key=f"editor_{ano_selecionado}_{mes_selecionado}",
    hide_index=False,
)

# Atualizar session_state com as edições
if df_editado is not None:
    st.session_state["df_conciliacao"] = normalizar_tipos(df_editado)

# -----------------------------------------------------------------------------
# RESUMO / ESTATÍSTICAS
# -----------------------------------------------------------------------------

st.divider()
st.subheader("📊 Resumo")

df_resumo = st.session_state["df_conciliacao"]

if not df_resumo.empty:
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)

    total_entradas = float(df_resumo["F"].sum()) if "F" in df_resumo.columns else 0.0
    total_saidas = float(df_resumo["G"].sum()) if "G" in df_resumo.columns else 0.0
    saldo_final = float(df_resumo["I"].iloc[-1]) if "I" in df_resumo.columns and len(df_resumo) > 0 else 0.0
    total_linhas = len(df_resumo)

    col_r1.metric("Entradas (F)", f"R$ {total_entradas:,.2f}")
    col_r2.metric("Saídas (G)", f"R$ {total_saidas:,.2f}")
    col_r3.metric("Saldo Final (I)", f"R$ {saldo_final:,.2f}")
    col_r4.metric("Total de Linhas", total_linhas)

    # Aplicar apelidos na exibição se houver correspondência
    if apelidos and "A" in df_resumo.columns:
        st.write("**Apelidos aplicados:**")
        for chave, valor in apelidos.items():
            matches = df_resumo[df_resumo["A"].astype(str).str.contains(chave, case=False, na=False)]
            if not matches.empty:
                st.write(f"- **{chave}** ({valor}): {len(matches)} ocorrências")

# -----------------------------------------------------------------------------
# EXPORTAÇÃO
# -----------------------------------------------------------------------------

st.divider()
st.subheader("💾 Exportação")

col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    if st.button("📥 Exportar CSV"):
        df_export = normalizar_tipos(st.session_state["df_conciliacao"])
        csv = df_export.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Baixar CSV",
            data=csv,
            file_name=f"conciliacao_bradesco_{mes_selecionado:02d}_{ano_selecionado}.csv",
            mime="text/csv",
        )

with col_exp2:
    if st.button("📥 Exportar Excel"):
        df_export = normalizar_tipos(st.session_state["df_conciliacao"])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="Conciliação")
        excel_data = output.getvalue()
        st.download_button(
            label="Baixar Excel",
            data=excel_data,
            file_name=f"conciliacao_bradesco_{mes_selecionado:02d}_{ano_selecionado}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# -----------------------------------------------------------------------------
# RODAPÉ
# -----------------------------------------------------------------------------

st.divider()
st.caption("Sistema de Conciliação Bradesco - Desenvolvido com Streamlit")

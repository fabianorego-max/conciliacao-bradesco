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


# -----------------------------------------------------------------------------
# Funções utilitárias (definidas no topo para robustez)
# -----------------------------------------------------------------------------
def recalcular(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recalcula automaticamente as colunas J a O com base nos valores editáveis.
    Utiliza pd.to_numeric(errors='coerce').fillna(0) para garantir robustez.
    """
    df = df.copy()

    # Garantir que as colunas numéricas sejam tratadas como número
    for col in ["F", "G", "H", "I", "N"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # J (Dif. Pagar): H - G se H > G, senão 0
    df["J"] = np.where(df["H"] > df["G"], df["H"] - df["G"], 0)

    # K (Dif. Receber): G - H se G > H, senão 0
    df["K"] = np.where(df["G"] > df["H"], df["G"] - df["H"], 0)

    # L (Saldo Final Ajustado): I + J - K
    df["L"] = pd.to_numeric(df["I"], errors="coerce").fillna(0) + \
              pd.to_numeric(df["J"], errors="coerce").fillna(0) - \
              pd.to_numeric(df["K"], errors="coerce").fillna(0)

    # M (Saldo Próxima Reunião): G + L - H
    df["M"] = pd.to_numeric(df["G"], errors="coerce").fillna(0) + \
              pd.to_numeric(df["L"], errors="coerce").fillna(0) - \
              pd.to_numeric(df["H"], errors="coerce").fillna(0)

    # O (Saldo Final do Mês): G + L - N
    df["O"] = pd.to_numeric(df["G"], errors="coerce").fillna(0) + \
              pd.to_numeric(df["L"], errors="coerce").fillna(0) - \
              pd.to_numeric(df["N"], errors="coerce").fillna(0)

    return df


def criar_dataframe_vazio(n_linhas: int = 10) -> pd.DataFrame:
    """Cria um DataFrame vazio com as colunas A até O."""
    colunas = [chr(c) for c in range(ord("A"), ord("O") + 1)]
    df = pd.DataFrame(np.nan, index=range(n_linhas), columns=colunas)
    # Inicializar colunas numéricas com 0
    for col in ["F", "G", "H", "I", "N"]:
        df[col] = 0
    return df


def normalizar_dataframe_importado(df_import: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza um DataFrame importado para o formato esperado (colunas A a O).
    """
    colunas_esperadas = [chr(c) for c in range(ord("A"), ord("O") + 1)]
    df = df_import.copy()

    # Renomear colunas se o número coincidir
    if len(df.columns) == len(colunas_esperadas):
        df.columns = colunas_esperadas
    else:
        # Garantir que todas as colunas existam
        for col in colunas_esperadas:
            if col not in df.columns:
                df[col] = np.nan
        df = df[colunas_esperadas]

    # Garantir tipos
    for col in ["A", "B", "C", "D", "E"]:
        df[col] = df[col].astype(str).replace("nan", "")
    for col in ["F", "G", "H", "I", "N"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return recalcular(df)


def chave_periodo(ano: int, mes: str) -> str:
    """Retorna a chave de sessão para um período."""
    return f"dados_{ano}_{mes}"


def mes_seguinte(mes: str) -> str:
    """Retorna o nome do mês seguinte."""
    meses = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    idx = meses.index(mes)
    return meses[(idx + 1) % 12]


def ano_seguinte(ano: int, mes: str) -> int:
    """Retorna o ano do mês seguinte."""
    return ano + 1 if mes == "Dezembro" else ano


# -----------------------------------------------------------------------------
# Configuração da página
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Conciliação Bradesco",
    page_icon="🏦",
    layout="wide",
)

st.title("🏦 Sistema de Conciliação Bradesco")
st.caption("Versão definitiva - Conciliação por período com transporte de saldo individualizado")

# -----------------------------------------------------------------------------
# Inicialização do session_state
# -----------------------------------------------------------------------------
if "apelidos" not in st.session_state:
    st.session_state["apelidos"] = {
        "A": "Cartão",
        "B": "Titular",
        "C": "Agência",
        "D": "Conta",
        "E": "Observação",
        "F": "Saldo Inicial",
        "G": "Total a Pagar",
        "H": "Total Pago",
        "I": "Saldo Anterior",
        "J": "Dif. Pagar",
        "K": "Dif. Receber",
        "L": "Saldo Final Ajustado",
        "M": "Saldo Próxima Reunião",
        "N": "Ajuste Manual",
        "O": "Saldo Final do Mês",
    }

if "periodo_atual" not in st.session_state:
    st.session_state["periodo_atual"] = {"ano": 2024, "mes": "Janeiro"}

# -----------------------------------------------------------------------------
# Sidebar - Controle de Período
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("📅 Controle de Período")

    anos = list(range(2024, 2031))
    meses = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]

    ano_selecionado = st.selectbox("Ano", anos,
                                   index=anos.index(st.session_state["periodo_atual"]["ano"]))
    mes_selecionado = st.selectbox("Mês", meses,
                                   index=meses.index(st.session_state["periodo_atual"]["mes"]))

    st.session_state["periodo_atual"] = {"ano": ano_selecionado, "mes": mes_selecionado}

    chave = chave_periodo(ano_selecionado, mes_selecionado)

    # ---------------------------------------------------------------------
    # Configuração de Apelidos (A a O)
    # ---------------------------------------------------------------------
    with st.expander("✏️ Configurar Apelidos das Colunas", expanded=False):
        st.markdown("**Colunas Alfanuméricas (A - E)**")
        for col in ["A", "B", "C", "D", "E"]:
            st.session_state["apelidos"][col] = st.text_input(
                f"Coluna {col}",
                value=st.session_state["apelidos"][col],
                key=f"apelido_{col}"
            )

        st.markdown("**Colunas Numéricas (F - O)**")
        for col in [chr(c) for c in range(ord("F"), ord("O") + 1)]:
            st.session_state["apelidos"][col] = st.text_input(
                f"Coluna {col}",
                value=st.session_state["apelidos"][col],
                key=f"apelido_{col}"
            )

    st.divider()

    # ---------------------------------------------------------------------
    # Importação Inteligente
    # ---------------------------------------------------------------------
    st.header("📥 Importação Inteligente")
    arquivo = st.file_uploader(
        "Importar Excel/CSV",
        type=["xlsx", "xls", "csv"],
        key=f"uploader_{chave}"
    )

    if arquivo is not None:
        try:
            if arquivo.name.lower().endswith(".csv"):
                df_import = pd.read_csv(arquivo)
            else:
                df_import = pd.read_excel(arquivo)
            df_normalizado = normalizar_dataframe_importado(df_import)
            st.session_state[chave] = df_normalizado
            st.success(f"✅ Arquivo importado e carregado para {mes_selecionado}/{ano_selecionado}!")
        except Exception as e:
            st.error(f"❌ Erro ao importar arquivo: {e}")

    st.divider()

    # ---------------------------------------------------------------------
    # Botão Fechar Mês (Transporte de Saldo Individualizado)
    # ---------------------------------------------------------------------
    st.header("🔒 Fechar Mês")
    if st.button("Fechar Mês e Transportar Saldo", type="primary"):
        if chave in st.session_state and isinstance(st.session_state[chave], pd.DataFrame):
            df_atual = st.session_state[chave].copy()
            df_atual = recalcular(df_atual)

            # Coluna O de cada linha -> Coluna I do mês seguinte
            prox_ano = ano_seguinte(ano_selecionado, mes_selecionado)
            prox_mes = mes_seguinte(mes_selecionado)
            prox_chave = chave_periodo(prox_ano, prox_mes)

            if prox_chave not in st.session_state or not isinstance(st.session_state[prox_chave], pd.DataFrame):
                st.session_state[prox_chave] = criar_dataframe_vazio(len(df_atual))

            df_prox = st.session_state[prox_chave].copy()
            # Garantir mesmo número de linhas
            if len(df_prox) < len(df_atual):
                # Adicionar linhas faltantes
                colunas = [chr(c) for c in range(ord("A"), ord("O") + 1)]
                linhas_extra = pd.DataFrame(np.nan,
                                            index=range(len(df_prox), len(df_atual)),
                                            columns=colunas)
                for col in ["F", "G", "H", "I", "N"]:
                    linhas_extra[col] = 0
                df_prox = pd.concat([df_prox, linhas_extra], ignore_index=True)
            elif len(df_prox) > len(df_atual):
                df_prox = df_prox.iloc[:len(df_atual)].copy()

            # Transportar O -> I linha a linha
            for idx in range(len(df_atual)):
                df_prox.at[idx, "I"] = pd.to_numeric(df_atual.at[idx, "O"], errors="coerce")
                # Transportar também identificação (A e B) para facilitar
                df_prox.at[idx, "A"] = df_atual.at[idx, "A"]
                df_prox.at[idx, "B"] = df_atual.at[idx, "B"]

            df_prox = recalcular(df_prox)
            st.session_state[prox_chave] = df_prox
            st.session_state[chave] = df_atual
            st.success(f"✅ Mês fechado! Saldo transportado para {prox_mes}/{prox_ano}.")
            st.rerun()
        else:
            st.warning("⚠️ Nenhum dado disponível para fechar o mês.")

    st.divider()

    # ---------------------------------------------------------------------
    # Exportação
    # ---------------------------------------------------------------------
    st.header("📤 Exportar")
    if chave in st.session_state and isinstance(st.session_state[chave], pd.DataFrame):
        df_export = st.session_state[chave].copy()
        # Renomear para apelidos
        df_export = df_export.rename(columns=st.session_state["apelidos"])
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name=f"{mes_selecionado[:3]}_{ano_selecionado}")
        output.seek(0)
        st.download_button(
            label="⬇️ Baixar Excel",
            data=output,
            file_name=f"conciliacao_{mes_selecionado}_{ano_selecionado}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# -----------------------------------------------------------------------------
# Área principal - Tabela do período selecionado
# -----------------------------------------------------------------------------
st.header(f"📊 Conciliação - {mes_selecionado} / {ano_selecionado}")

# Obter ou criar DataFrame do período
if chave not in st.session_state or not isinstance(st.session_state[chave], pd.DataFrame):
    st.session_state[chave] = criar_dataframe_vazio(10)

df_periodo = st.session_state[chave].copy()

# Garantir que as colunas A-O existam e estejam tipadas corretamente
colunas_esperadas = [chr(c) for c in range(ord("A"), ord("O") + 1)]
for col in colunas_esperadas:
    if col not in df_periodo.columns:
        df_periodo[col] = 0 if col in ["F", "G", "H", "I", "N"] else ""

df_periodo = df_periodo[colunas_esperadas]

# Garantir tipos antes da edição
for col in ["A", "B", "C", "D", "E"]:
    df_periodo[col] = df_periodo[col].astype(str).replace("nan", "")
for col in ["F", "G", "H", "I", "N"]:
    df_periodo[col] = pd.to_numeric(df_periodo[col], errors="coerce").fillna(0)

# Recalcular antes de exibir
df_periodo = recalcular(df_periodo)

# -----------------------------------------------------------------------------
# Configuração das colunas do data_editor
# -----------------------------------------------------------------------------
apelidos = st.session_state["apelidos"]

# Colunas editáveis: A, B, C, D, E, F, G, H, N
colunas_editaveis = ["A", "B", "C", "D", "E", "F", "G", "H", "N"]

column_config = {}
for col in colunas_esperadas:
    label = apelidos.get(col, col)
    if col in ["A", "B", "C", "D", "E"]:
        # Colunas alfanuméricas
        column_config[col] = st.column_config.TextColumn(
            label=label,
            help=f"Coluna {col} (alfanumérica)",
        )
    else:
        # Colunas numéricas (F a O)
        column_config[col] = st.column_config.NumberColumn(
            label=label,
            help=f"Coluna {col} (numérica)",
            format="R$ %.2f",
        )

# Definir quais colunas são editáveis
disabled_cols = [col for col in colunas_esperadas if col not in colunas_editaveis]

# -----------------------------------------------------------------------------
# Data Editor
# -----------------------------------------------------------------------------
df_editado = st.data_editor(
    df_periodo,
    column_config=column_config,
    disabled=disabled_cols,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_{chave}",
    hide_index=True,
)

# Salvar edições e recalcular
df_recalculado = recalcular(df_editado)
st.session_state[chave] = df_recalculado

# -----------------------------------------------------------------------------
# Resumo do período
# -----------------------------------------------------------------------------
st.divider()
st.subheader("📋 Resumo do Período")

col1, col2, col3, col4 = st.columns(4)
with col1:
    total_pagar = pd.to_numeric(df_recalculado["G"], errors="coerce").fillna(0).sum()
    st.metric("Total a Pagar (G)", f"R$ {total_pagar:,.2f}")
with col2:
    total_pago = pd.to_numeric(df_recalculado["H"], errors="coerce").fillna(0).sum()
    st.metric("Total Pago (H)", f"R$ {total_pago:,.2f}")
with col3:
    total_dif_pagar = pd.to_numeric(df_recalculado["J"], errors="coerce").fillna(0).sum()
    st.metric("Dif. Pagar (J)", f"R$ {total_dif_pagar:,.2f}")
with col4:
    total_saldo_final = pd.to_numeric(df_recalculado["O"], errors="coerce").fillna(0).sum()
    st.metric("Saldo Final Mês (O)", f"R$ {total_saldo_final:,.2f}")

# -----------------------------------------------------------------------------
# Informações de debug / status
# -----------------------------------------------------------------------------
with st.expander("🔍 Informações Técnicas", expanded=False):
    st.write(f"**Período ativo:** {mes_selecionado} / {ano_selecionado}")
    st.write(f"**Chave de sessão:** `{chave}`")
    st.write(f"**Colunas editáveis:** {', '.join(colunas_editaveis)}")
    st.write(f"**Colunas calculadas:** J, K, L, M, O")
    st.write(f"**Linhas na tabela:** {len(df_recalculado)}")
    st.write("**Apelidos atuais:**")
    st.json(apelidos)

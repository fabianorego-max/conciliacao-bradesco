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
    page_title="Sistema de Conciliação Bradesco",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏦 Sistema de Conciliação Bradesco")
st.caption("Controle de conciliação bancária por período com cálculos automáticos.")

# =============================================================================
# CONSTANTES
# =============================================================================
ANOS = list(range(2024, 2031))
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
COLUNAS_PADRAO = {
    "A": "Coluna A",
    "B": "Coluna B",
    "C": "Coluna C",
    "D": "Coluna D",
    "E": "Coluna E",
    "F": "Coluna F",
    "G": "Coluna G",
    "H": "Coluna H",
    "I": "Saldo Inicial",
    "J": "Dif. Pagar",
    "K": "Dif. Receber",
    "L": "Saldo Final Ajustado",
    "M": "Saldo Próxima Reunião",
    "N": "Coluna N",
    "O": "Saldo Final do Mês",
}
COLUNAS_ALFANUMERICAS = ["A", "B", "C", "D", "E"]
COLUNAS_NUMERICAS = ["F", "G", "H", "I", "J", "K", "L", "M", "N", "O"]
COLUNAS_EDITAVEIS = ["A", "B", "C", "D", "E", "F", "G", "H", "N"]
COLUNAS_CALCULADAS = ["J", "K", "L", "M", "O"]

# =============================================================================
# INICIALIZAÇÃO DO ESTADO
# =============================================================================
def init_state():
    if "dados_periodo" not in st.session_state:
        st.session_state["dados_periodo"] = {}
    if "apelidos" not in st.session_state:
        st.session_state["apelidos"] = dict(COLUNAS_PADRAO)
    if "ultimo_periodo" not in st.session_state:
        st.session_state["ultimo_periodo"] = None

init_state()

def chave_periodo(ano: int, mes: str) -> str:
    return f"{ano}_{mes}"

def obter_dados_periodo(ano: int, mes: str) -> pd.DataFrame:
    chave = chave_periodo(ano, mes)
    if chave not in st.session_state["dados_periodo"]:
        st.session_state["dados_periodo"][chave] = criar_dataframe_vazio()
    return st.session_state["dados_periodo"][chave]

def salvar_dados_periodo(ano: int, mes: str, df: pd.DataFrame):
    chave = chave_periodo(ano, mes)
    st.session_state["dados_periodo"][chave] = df

def criar_dataframe_vazio(n_linhas: int = 20) -> pd.DataFrame:
    dados = {col: [""] * n_linhas if col in COLUNAS_ALFANUMERICAS else [0.0] * n_linhas for col in COLUNAS_PADRAO.keys()}
    return pd.DataFrame(dados)

def aplicar_apelidos(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={k: st.session_state["apelidos"][k] for k in COLUNAS_PADRAO.keys()})

def reverter_apelidos(df: pd.DataFrame) -> pd.DataFrame:
    apelido_para_coluna = {v: k for k, v in st.session_state["apelidos"].items()}
    return df.rename(columns=apelido_para_coluna)

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.header("📅 Controle de Período")
    ano_selecionado = st.selectbox("Ano", ANOS, index=ANOS.index(2024))
    mes_selecionado = st.selectbox("Mês", MESES)
    periodo_atual = chave_periodo(ano_selecionado, mes_selecionado)

    st.divider()

    # Configuração de Colunas
    with st.expander("⚙️ Configuração de Colunas (A a O)", expanded=False):
        st.markdown("Defina os apelidos das colunas:")
        novos_apelidos = {}
        for col in COLUNAS_PADRAO.keys():
            novos_apelidos[col] = st.text_input(
                f"Coluna {col}",
                value=st.session_state["apelidos"].get(col, COLUNAS_PADRAO[col]),
                key=f"apelido_{col}",
            )
        if st.button("Salvar Apelidos", use_container_width=True):
            st.session_state["apelidos"] = novos_apelidos
            st.success("Apelidos salvos com sucesso!")
            st.rerun()

    st.divider()

    # Importação
    st.header("📂 Importação Inteligente")
    arquivo = st.file_uploader(
        "Carregar Excel/CSV",
        type=["xlsx", "xls", "csv"],
        key=f"uploader_{periodo_atual}",
    )

    if arquivo is not None:
        try:
            if arquivo.name.lower().endswith(".csv"):
                df_importado = pd.read_csv(arquivo, dtype=str)
            else:
                df_importado = pd.read_excel(arquivo, dtype=str)

            # Normalizar colunas: tentar mapear por apelido ou por letra
            df_importado.columns = [str(c).strip() for c in df_importado.columns]
            apelido_para_coluna = {v.strip().lower(): k for k, v in st.session_state["apelidos"].items()}
            mapa_renome = {}
            for c in df_importado.columns:
                c_lower = c.lower()
                if c_lower in apelido_para_coluna:
                    mapa_renome[c] = apelido_para_coluna[c_lower]
                elif c.upper() in COLUNAS_PADRAO.keys():
                    mapa_renome[c] = c.upper()
            if mapa_renome:
                df_importado = df_importado.rename(columns=mapa_renome)

            # Garantir todas as colunas existam
            df_final = criar_dataframe_vazio(len(df_importado))
            for col in COLUNAS_PADRAO.keys():
                if col in df_importado.columns:
                    if col in COLUNAS_ALFANUMERICAS:
                        df_final[col] = df_importado[col].astype(str).fillna("")
                    else:
                        df_final[col] = pd.to_numeric(df_importado[col], errors="coerce").fillna(0.0)

            # Recalcular colunas automáticas
            df_final = recalcular(df_final)
            salvar_dados_periodo(ano_selecionado, mes_selecionado, df_final)
            st.success(f"✅ {len(df_importado)} linhas importadas para {mes_selecionado}/{ano_selecionado}!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao importar arquivo: {e}")

    st.divider()

    # Fechar Mês
    st.header("🔒 Fechar Mês")
    if st.button("Fechar Mês e Transportar Saldo", use_container_width=True, type="primary"):
        df_atual = obter_dados_periodo(ano_selecionado, mes_selecionado)
        saldo_final = pd.to_numeric(df_atual["O"], errors="coerce").fillna(0.0).sum()

        idx_mes = MESES.index(mes_selecionado)
        if idx_mes == 11:
            prox_ano = ano_selecionado + 1
            prox_mes = MESES[0]
        else:
            prox_ano = ano_selecionado
            prox_mes = MESES[idx_mes + 1]

        df_proximo = obter_dados_periodo(prox_ano, prox_mes)
        df_proximo["I"] = pd.to_numeric(df_proximo["I"], errors="coerce").fillna(0.0)
        if len(df_proximo) > 0:
            df_proximo.loc[0, "I"] = saldo_final
        df_proximo = recalcular(df_proximo)
        salvar_dados_periodo(prox_ano, prox_mes, df_proximo)
        st.success(f"✅ Saldo {saldo_final:,.2f} transportado para {prox_mes}/{prox_ano} (Coluna I).")
        st.rerun()

# =============================================================================
# FUNÇÕES DE CÁLCULO
# =============================================================================
def recalcular(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Garantir tipos numéricos
    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # J (Dif. Pagar): H - G se H > G, senão 0
    df["J"] = np.where(df["H"] > df["G"], df["H"] - df["G"], 0.0)
    # K (Dif. Receber): G - H se G > H, senão 0
    df["K"] = np.where(df["G"] > df["H"], df["G"] - df["H"], 0.0)
    # L (Saldo Final Ajustado): I + J - K
    df["L"] = df["I"] + df["J"] - df["K"]
    # M (Saldo Próxima Reunião): G + L - H
    df["M"] = df["G"] + df["L"] - df["H"]
    # O (Saldo Final do Mês): G + L - N
    df["O"] = df["G"] + df["L"] - df["N"]

    # Robustez final
    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    return df

# =============================================================================
# TABELA PRINCIPAL
# =============================================================================
st.subheader(f"📊 Tabela de Conciliação — {mes_selecionado}/{ano_selecionado}")

df_periodo = obter_dados_periodo(ano_selecionado, mes_selecionado)
df_periodo = recalcular(df_periodo)
salvar_dados_periodo(ano_selecionado, mes_selecionado, df_periodo)

df_exibicao = aplicar_apelidos(df_periodo.copy())

# Configurar colunas do data_editor
column_config = {}
for col in COLUNAS_PADRAO.keys():
    apelido = st.session_state["apelidos"][col]
    if col in COLUNAS_ALFANUMERICAS:
        column_config[apelido] = st.column_config.TextColumn(apelido, help=f"Coluna {col} (alfanumérica)")
    else:
        column_config[apelido] = st.column_config.NumberColumn(
            apelido,
            help=f"Coluna {col} (numérica)",
            format="%.2f",
        )

# Colunas não editáveis (calculadas e I) devem ser desabilitadas
disabled_cols = []
for col in COLUNAS_PADRAO.keys():
    if col not in COLUNAS_EDITAVEIS:
        disabled_cols.append(st.session_state["apelidos"][col])

df_editado = st.data_editor(
    df_exibicao,
    column_config=column_config,
    disabled=disabled_cols,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_{periodo_atual}",
)

# Reverter apelidos e salvar
if df_editado is not None:
    df_revertido = reverter_apelidos(df_editado)
    df_revertido = recalcular(df_revertido)
    salvar_dados_periodo(ano_selecionado, mes_selecionado, df_revertido)

# =============================================================================
# RESUMO FINANCEIRO
# =============================================================================
st.divider()
st.subheader("💰 Resumo Financeiro")

df_resumo = obter_dados_periodo(ano_selecionado, mes_selecionado)
for col in COLUNAS_NUMERICAS:
    df_resumo[col] = pd.to_numeric(df_resumo[col], errors="coerce").fillna(0.0)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Saldo Inicial (I)", f"{df_resumo['I'].sum():,.2f}")
with col2:
    st.metric("Dif. Pagar (J)", f"{df_resumo['J'].sum():,.2f}")
with col3:
    st.metric("Dif. Receber (K)", f"{df_resumo['K'].sum():,.2f}")
with col4:
    st.metric("Saldo Final Ajustado (L)", f"{df_resumo['L'].sum():,.2f}")
with col5:
    st.metric("Saldo Final do Mês (O)", f"{df_resumo['O'].sum():,.2f}")

col6, col7, col8 = st.columns(3)
with col6:
    st.metric("Total Coluna G", f"{df_resumo['G'].sum():,.2f}")
with col7:
    st.metric("Total Coluna H", f"{df_resumo['H'].sum():,.2f}")
with col8:
    st.metric("Saldo Próxima Reunião (M)", f"{df_resumo['M'].sum():,.2f}")

# =============================================================================
# EXPORTAÇÃO
# =============================================================================
st.divider()
st.subheader("📥 Exportar Dados")

def to_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Conciliação")
    return output.getvalue()

col_exp1, col_exp2 = st.columns(2)
with col_exp1:
    df_export = aplicar_apelidos(obter_dados_periodo(ano_selecionado, mes_selecionado))
    st.download_button(
        "⬇️ Exportar Excel",
        data=to_excel(df_export),
        file_name=f"conciliacao_{mes_selecionado}_{ano_selecionado}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
with col_exp2:
    st.download_button(
        "⬇️ Exportar CSV",
        data=df_export.to_csv(index=False).encode("utf-8"),
        file_name=f"conciliacao_{mes_selecionado}_{ano_selecionado}.csv",
        mime="text/csv",
        use_container_width=True,
    )

# Rodapé
st.divider()
st.caption("Sistema de Conciliação Bradesco — Dados salvos por período em st.session_state.")

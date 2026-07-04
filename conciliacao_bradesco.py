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
import unicodedata
from io import BytesIO

# -----------------------------------------------------------------------------
# Configuração da página
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Conciliação Bradesco", layout="wide", page_icon="🏦")

# -----------------------------------------------------------------------------
# Constantes / Estrutura de colunas A-O
# -----------------------------------------------------------------------------
COLUNAS = [
    "Cartão",               # A
    "Resumo 7 dígitos",     # B (auto a partir de A)
    "Titular",              # C
    "CPF",                  # D
    "Localidade",           # E
    "Limite",               # F
    "Aprovado Reunião",    # G
    "Valor Fatura",        # H
    "Saldo Anterior",      # I
    "Diferença a Pagar",   # J (H>G)
    "Diferença a Receber", # K (G>H)
    "Saldo Final Ajustado",# L (I+J-K)
    "Saldo Próxima Reunião",# M (G+L-H)
    "Pós-Fechamento",      # N
    "Saldo Final do Mês",  # O (G+L-N)
]

COLUNAS_NUMERICAS = [
    "Limite",
    "Aprovado Reunião",
    "Valor Fatura",
    "Saldo Anterior",
    "Diferença a Pagar",
    "Diferença a Receber",
    "Saldo Final Ajustado",
    "Saldo Próxima Reunião",
    "Pós-Fechamento",
    "Saldo Final do Mês",
]

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

ANOS = list(range(2020, 2031))

SINONIMOS = {
    "Cartão": [
        "cartao", "cartão", "numero", "número", "n_cartao", "n_cartão",
        "card", "numero_cartao", "número_cartao", "n_do_cartao",
        "n_do_cartão", "n_cart", "num_cartao"
    ],
    "Titular": [
        "titular", "nome", "cliente", "nome_cliente", "owner",
        "nome_do_titular", "nome_completo", "razao_social"
    ],
    "CPF": [
        "cpf", "documento", "doc", "cpf_cnpj", "cnpj"
    ],
}

# -----------------------------------------------------------------------------
# Inicialização do session_state
# -----------------------------------------------------------------------------
if "periodos" not in st.session_state:
    st.session_state.periodos = {}

if "apelidos" not in st.session_state:
    st.session_state.apelidos = {col: col for col in COLUNAS}

def periodo_chave(mes: str, ano: int) -> str:
    return f"{mes}_{ano}"

def criar_dataframe_vazio() -> pd.DataFrame:
    df = pd.DataFrame(columns=COLUNAS)
    for col in COLUNAS_NUMERICAS:
        df[col] = df[col].astype(float)
    return df

def obter_periodo_atual(mes: str, ano: int) -> pd.DataFrame:
    chave = periodo_chave(mes, ano)
    if chave not in st.session_state.periodos:
        st.session_state.periodos[chave] = criar_dataframe_vazio()
    return st.session_state.periodos[chave]

def _normalizar_texto(texto: str) -> str:
    if texto is None: return ""
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII")
    texto = texto.replace(" ", "").replace("_", "")
    return texto

def _construir_mapa_colunas() -> dict:
    mapa = {}
    for k, v in st.session_state.apelidos.items():
        mapa[_normalizar_texto(v)] = k
    for k in COLUNAS:
        mapa[_normalizar_texto(k)] = k
    for col_alvo, sinonimos in SINONIMOS.items():
        for sin in sinonimos:
            mapa[_normalizar_texto(sin)] = col_alvo
    return mapa

def normalizar_dataframe_importado(df_import: pd.DataFrame) -> pd.DataFrame:
    df = df_import.copy()
    mapa = _construir_mapa_colunas()
    novas_colunas = {}
    for col in df.columns:
        chave = _normalizar_texto(col)
        if chave in mapa:
            novas_colunas[col] = mapa[chave]
    if novas_colunas:
        df = df.rename(columns=novas_colunas)

    for col in COLUNAS:
        if col not in df.columns:
            df[col] = np.nan

    df = df[COLUNAS]
    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    df["Cartão"] = df["Cartão"].astype(str).str.replace(r"\.0$", "", regex=True).replace({"nan": "", "None": ""})
    df["Resumo 7 dígitos"] = df["Cartão"].str.replace(r"\D", "", regex=True).str[-7:]
    return df.reset_index(drop=True)

def recalcular(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
    
    df["Resumo 7 dígitos"] = df["Cartão"].astype(str).str.replace(r"\D", "", regex=True).str[-7:]
    df["Diferença a Pagar"] = np.where(df["Valor Fatura"] > df["Aprovado Reunião"], df["Valor Fatura"] - df["Aprovado Reunião"], 0.0)
    df["Diferença a Receber"] = np.where(df["Aprovado Reunião"] > df["Valor Fatura"], df["Aprovado Reunião"] - df["Valor Fatura"], 0.0)
    df["Saldo Final Ajustado"] = df["Saldo Anterior"] + df["Diferença a Pagar"] - df["Diferença a Receber"]
    df["Saldo Próxima Reunião"] = df["Aprovado Reunião"] + df["Saldo Final Ajustado"] - df["Valor Fatura"]
    df["Saldo Final do Mês"] = df["Aprovado Reunião"] + df["Saldo Final Ajustado"] - df["Pós-Fechamento"]
    return df

def periodo_anterior(mes: str, ano: int) -> str | None:
    idx = MESES.index(mes)
    if idx == 0 and ano == ANOS[0]: return None
    if idx == 0: return periodo_chave(MESES[-1], ano - 1)
    return periodo_chave(MESES[idx - 1], ano)

def periodo_seguinte(mes: str, ano: int) -> str | None:
    idx = MESES.index(mes)
    if idx == len(MESES) - 1 and ano == ANOS[-1]: return None
    if idx == len(MESES) - 1: return periodo_chave(MESES[0], ano + 1)
    return periodo_chave(MESES[idx + 1], ano)

def carry_over(mes: str, ano: int) -> None:
    chave_atual = periodo_chave(mes, ano)
    chave_prox = periodo_seguinte(mes, ano)
    if chave_prox is None: return
    df_atual = st.session_state.periodos.get(chave_atual, criar_dataframe_vazio())
    if df_atual.empty: return
    base = df_atual[["Cartão", "Resumo 7 dígitos", "Titular", "CPF", "Localidade", "Limite"]].copy()
    base["Saldo Anterior"] = pd.to_numeric(df_atual["Saldo Final do Mês"], errors="coerce").fillna(0.0)
    for col in ["Aprovado Reunião", "Valor Fatura", "Diferença a Pagar", "Diferença a Receber", "Saldo Final Ajustado", "Saldo Próxima Reunião", "Pós-Fechamento", "Saldo Final do Mês"]:
        base[col] = 0.0
    st.session_state.periodos[chave_prox] = base[COLUNAS].reset_index(drop=True)
    st.success(f"Carry over realizado para {chave_prox}.")

def exportar_excel(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Conciliação")
    return buf.getvalue()

# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------
st.sidebar.title("🏦 Conciliação Bradesco")
mes_sel = st.sidebar.selectbox("Mês", MESES, index=0)
ano_sel = st.sidebar.selectbox("Ano", ANOS, index=ANOS.index(2024))
chave_atual = periodo_chave(mes_sel, ano_sel)

st.sidebar.divider()
with st.sidebar.expander("Renomear colunas exibidas"):
    for col in COLUNAS:
        novo = st.text_input(f"{col}", value=st.session_state.apelidos.get(col, col), key=f"ap_{col}")
        st.session_state.apelidos[col] = novo or col

st.sidebar.divider()
if st.sidebar.button("⏭️ Carry over para próximo período"):
    carry_over(mes_sel, ano_sel)
    st.rerun()

# -----------------------------------------------------------------------------
# Importação
# -----------------------------------------------------------------------------
st.subheader(f"Período: {mes_sel} / {ano_sel}")
col_imp1, col_imp2 = st.columns([2, 1])
with col_imp1:
    # Key dinâmica evita erro de duplicidade ao trocar de período
    arquivo = st.file_uploader("Importar Excel/CSV", type=["xlsx", "xls", "csv"], key=f"uploader_{chave_atual}")
with col_imp2:
    st.write("")
    st.write("")
    btn_importar = st.button("📥 Importar dados")

if btn_importar and arquivo is not None:
    try:
        df_import = pd.read_csv(arquivo) if arquivo.name.lower().endswith(".csv") else pd.read_excel(arquivo)
        df_norm = recalcular(normalizar_dataframe_importado(df_import))
        st.session_state.periodos[chave_atual] = df_norm
        st.success("Importação concluída.")
        st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# -----------------------------------------------------------------------------
# Editor de Dados (Unificado)
# -----------------------------------------------------------------------------
df_atual = obter_periodo_atual(mes_sel, ano_sel)
df_editor = df_atual.copy()
for col in COLUNAS_NUMERICAS:
    df_editor[col] = pd.to_numeric(df_editor[col], errors="coerce").fillna(0.0).astype(float)

df_display = df_editor.rename(columns=st.session_state.apelidos)
st.write(f"**Registros:** {len(df_display)}")

edited_df = st.data_editor(
    df_display,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_main_{chave_atual}",
    column_config={st.session_state.apelidos.get(c, c): st.column_config.NumberColumn(format="%.2f") for c in COLUNAS_NUMERICAS}
)

# Lógica de salvamento e recalculo
mapa_reverso = {v: k for k, v in st.session_state.apelidos.items()}
df_salvar_raw = edited_df.rename(columns=mapa_reverso)

# Só recalcula e salva se houver mudança real para evitar loops de rerun
if not df_salvar_raw.equals(df_atual):
    df_final = recalcular(df_salvar_raw)
    st.session_state.periodos[chave_atual] = df_final
    st.rerun()

# -----------------------------------------------------------------------------
# Exportação
# -----------------------------------------------------------------------------
st.divider()
col_exp1, col_exp2 = st.columns([1, 3])
with col_exp1:
    if st.button("📤 Gerar Excel"):
        dados = exportar_excel(st.session_state.periodos[chave_atual])
        st.download_button(
            label="⬇️ Baixar arquivo",
            data=dados,
            file_name=f"conciliacao_{chave_atual}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

chave_ant = periodo_anterior(mes_sel, ano_sel)
if chave_ant and chave_ant in st.session_state.periodos:
    if not st.session_state.periodos[chave_ant].empty:
        st.info(f"📌 Período anterior ({chave_ant}) disponível para Carry Over.")

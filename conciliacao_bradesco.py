# -*- coding: utf-8 -*-
"""
Sistema Web de Conciliação de Cartões Bradesco (Streamlit)
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

# Sinônimos para mapeamento resiliente de colunas na importação
SINONIMOS = {
    "Cartão": [
        "cartao", "cartão", "numero", "número", "n_cartao", "n_cartão",
        "card", "numero_cartao", "número_cartao", "n_do_cartao",
        "n_do_cartão", "n_cart", "num_cartao", "nº cartão", "nº cartao", "nº", "no"
    ],
    "Titular": [
        "titular", "nome", "cliente", "nome_cliente", "owner",
        "nome_do_titular", "nome_completo", "razao_social", "nome titular", "portador"
    ],
    "CPF": [
        "cpf", "documento", "doc", "cpf_cnpj", "cnpj", "cpf/cnpj", "identificação", "identificacao"
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
    if texto is None:
        return ""
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
    """Garante que o DataFrame importado tenha exatamente as colunas A-O mapeadas corretamente."""
    st.write(f"🔍 **Colunas detectadas no arquivo:** `{list(df_import.columns)}`")
    
    df = df_import.copy()
    mapa = _construir_mapa_colunas()

    # 1. Mapeamento por nome (Prioridade)
    novas_colunas = {}
    mapeamento_debug = []
    for col in df.columns:
        chave = _normalizar_texto(col)
        if chave in mapa:
            nome_oficial = mapa[chave]
            # Se já mapeamos algo para esse nome oficial, ignoramos duplicatas
            if nome_oficial not in novas_colunas.values():
                novas_colunas[col] = nome_oficial
                mapeamento_debug.append({"Arquivo": col, "Sistema": nome_oficial})

    if novas_colunas:
        df = df.rename(columns=novas_colunas)

    # 2. Detecção por conteúdo para colunas críticas se ainda faltarem
    if "Cartão" not in df.columns:
        for col in df.columns:
            if col in COLUNAS: continue
            serie = df[col].dropna().astype(str)
            if not serie.empty:
                digitos = serie.str.replace(r"\D", "", regex=True).str.len()
                if (digitos >= 4).mean() > 0.5:
                    df = df.rename(columns={col: "Cartão"})
                    mapeamento_debug.append({"Arquivo": col, "Sistema": "Cartão (Conteúdo)"})
                    break

    if "Titular" not in df.columns:
        for col in df.columns:
            if col in COLUNAS or col == "Localidade": continue
            serie = df[col].dropna().astype(str)
            if not serie.empty:
                digitos = serie.str.replace(r"\D", "", regex=True).str.len()
                if (digitos < 4).mean() > 0.5:
                    df = df.rename(columns={col: "Titular"})
                    mapeamento_debug.append({"Arquivo": col, "Sistema": "Titular (Conteúdo)"})
                    break

    if mapeamento_debug:
        st.info("Mapeamento realizado:")
        st.table(pd.DataFrame(mapeamento_debug))

    # 3. Garantir todas as colunas A-O (Preencher faltantes com NaN)
    for col in COLUNAS:
        if col not in df.columns:
            df[col] = np.nan

    # 4. Limpeza e Formatação
    df = df[COLUNAS].copy()
    
    # Limpeza Cartão
    df["Cartão"] = df["Cartão"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["Cartão"] = df["Cartão"].replace({"nan": "", "None": "", "NaN": ""}).str.strip()

    # Resumo 7 dígitos (Apenas se Cartão for válido)
    def extrair_resumo(val):
        s = str(val).strip()
        if not s or s.lower() in ["nan", "none", ""]:
            return ""
        digits = "".join(filter(str.isdigit, s))
        return digits[-7:] if len(digits) >= 7 else digits

    df["Resumo 7 dígitos"] = df["Cartão"].apply(extrair_resumo)

    # Cast numérico
    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    return df.reset_index(drop=True)


def recalcular(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    # J) Diferença a Pagar (H>G)
    df["Diferença a Pagar"] = np.where(df["Valor Fatura"] > df["Aprovado Reunião"],
                                        df["Valor Fatura"] - df["Aprovado Reunião"], 0.0)

    # K) Diferença a Receber (G>H)
    df["Diferença a Receber"] = np.where(df["Aprovado Reunião"] > df["Valor Fatura"],
                                         df["Aprovado Reunião"] - df["Valor Fatura"], 0.0)

    # L) Saldo Final Ajustado (I+J-K)
    df["Saldo Final Ajustado"] = df["Saldo Anterior"] + df["Diferença a Pagar"] - df["Diferença a Receber"]

    # M) Saldo Próxima Reunião (G+L-H)
    df["Saldo Próxima Reunião"] = df["Aprovado Reunião"] + df["Saldo Final Ajustado"] - df["Valor Fatura"]

    # O) Saldo Final do Mês (G+L-N)
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
    base["Saldo Anterior"] = df_atual["Saldo Final do Mês"]

    for col in ["Aprovado Reunião", "Valor Fatura", "Diferença a Pagar",
                "Diferença a Receber", "Saldo Final Ajustado", "Saldo Próxima Reunião",
                "Pós-Fechamento", "Saldo Final do Mês"]:
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
st.sidebar.subheader("Apelidos de Colunas")
with st.sidebar.expander("Configurar nomes de exibição"):
    for col in COLUNAS:
        novo = st.text_input(f"{col}", value=st.session_state.apelidos.get(col, col), key=f"ap_{col}")
        st.session_state.apelidos[col] = novo or col

st.sidebar.divider()
if st.sidebar.button("⏭️ Carry over para próximo período"):
    carry_over(mes_sel, ano_sel)
    st.rerun()

# -----------------------------------------------------------------------------
# Main UI
# -----------------------------------------------------------------------------
st.subheader(f"Período: {mes_sel} / {ano_sel}")

col_imp1, col_imp2 = st.columns([2, 1])
with col_imp1:
    arquivo = st.file_uploader("Importar Excel/CSV", type=["xlsx", "xls", "csv"], key=f"up_{chave_atual}")
with col_imp2:
    st.write("")
    st.write("")
    btn_importar = st.button("📥 Importar dados")

if btn_importar and arquivo is not None:
    try:
        df_import = pd.read_csv(arquivo) if arquivo.name.endswith(".csv") else pd.read_excel(arquivo)
        df_norm = normalizar_dataframe_importado(df_import)
        st.session_state.periodos[chave_atual] = recalcular(df_norm)
        st.success("Importação concluída.")
        st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# -----------------------------------------------------------------------------
# Editor de Dados (Único)
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
    column_config={
        st.session_state.apelidos.get(c, c): st.column_config.NumberColumn(format="%.2f")
        for c in COLUNAS_NUMERICAS
    },
)

if not edited_df.equals(df_display):
    mapa_reverso = {v: k for k, v in st.session_state.apelidos.items()}
    df_salvar = edited_df.rename(columns=mapa_reverso)
    st.session_state.periodos[chave_atual] = recalcular(df_salvar)
    st.rerun()

# -----------------------------------------------------------------------------
# Exportação e Info
# -----------------------------------------------------------------------------
st.divider()
col_exp1, col_exp2 = st.columns([1, 3])
with col_exp1:
    if st.button("📤 Exportar Excel"):
        dados = exportar_excel(st.session_state.periodos[chave_atual])
        st.download_button("⬇️ Baixar", dados, f"conciliacao_{chave_atual}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

chave_ant = periodo_anterior(mes_sel, ano_sel)
if chave_ant and chave_ant in st.session_state.periodos:
    st.info(f"📌 Período anterior ({chave_ant}) detectado. Use Carry Over se necessário.")

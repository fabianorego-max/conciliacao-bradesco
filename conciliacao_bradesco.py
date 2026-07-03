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

# -----------------------------------------------------------------------------
# Mapeamento explícito de sinônimos comuns para colunas cadastrais
# -----------------------------------------------------------------------------
SINONIMOS = {
    "Cartão": ["cartao", "numero", "n_cartao", "card", "numero_cartao"],
    "Titular": ["titular", "nome", "cliente", "nome_cliente", "owner"],
    "CPF": ["cpf", "documento", "doc"],
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


def _limpar_cartao(valor) -> str:
    """Converte o valor de Cartão para string removendo '.0' residual."""
    if pd.isna(valor):
        return ""
    texto = str(valor).strip()
    # Remove sufixo .0 de conversões automáticas do pandas (ex.: 1234567.0)
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


def normalizar_dataframe_importado(df_import: pd.DataFrame) -> pd.DataFrame:
    """Garante que o DataFrame importado tenha exatamente as colunas A-O.

    Etapas:
      1) Mapeia sinônimos comuns (Cartão, Titular, CPF) e apelidos configurados.
      2) Garante todas as colunas A-O.
      3) Converte Cartão para string removendo '.0' residual.
      4) Extrai os 7 dígitos (Coluna B) imediatamente após normalizar a Coluna A.
      5) Trata conversão numérica individualmente para as colunas J-O.
    """
    df = df_import.copy()

    # --- Mapeamento flexível: apelidos configurados + nomes canônicos ---
    mapa = {v.lower(): k for k, v in st.session_state.apelidos.items()}
    mapa.update({k.lower(): k for k in COLUNAS})

    # --- Mapeamento explícito de sinônimos comuns ---
    for col_canonica, sinonimos in SINONIMOS.items():
        for sin in sinonimos:
            mapa[sin.lower()] = col_canonica

    novas_colunas = {}
    for col in df.columns:
        chave = str(col).strip().lower()
        if chave in mapa:
            novas_colunas[col] = mapa[chave]

    if novas_colunas:
        df = df.rename(columns=novas_colunas)

    # --- Garante todas as colunas A-O ---
    for col in COLUNAS:
        if col not in df.columns:
            df[col] = np.nan

    df = df[COLUNAS]

    # --- Conversão individual de tipos ---
    # Coluna A (Cartão): string sem '.0' residual
    df["Cartão"] = df["Cartão"].apply(_limpar_cartao)

    # Coluna B (Resumo 7 dígitos): extração imediata a partir de Cartão
    df["Resumo 7 dígitos"] = (
        df["Cartão"].astype(str).str.replace(r"\D", "", regex=True).str[-7:]
    )

    # Colunas C (Titular) e D (CPF): string
    df["Titular"] = df["Titular"].astype(str).replace({"nan": "", "None": ""}).str.strip()
    df["CPF"] = df["CPF"].astype(str).replace({"nan": "", "None": ""}).str.strip()

    # Coluna E (Localidade): string
    df["Localidade"] = df["Localidade"].astype(str).replace({"nan": "", "None": ""}).str.strip()

    # Colunas numéricas (F, G-O): cast numérico + fill 0.0
    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    return df.reset_index(drop=True)


def recalcular(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica a lógica de cálculo das colunas J-O."""
    df = df.copy()

    # Garante tipos numéricos
    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    # Resumo 7 dígitos automático
    df["Resumo 7 dígitos"] = df["Cartão"].astype(str).str.replace(r"\D", "", regex=True).str[-7:]

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
    if idx == 0 and ano == ANOS[0]:
        return None
    if idx == 0:
        return periodo_chave(MESES[-1], ano - 1)
    return periodo_chave(MESES[idx - 1], ano)


def periodo_seguinte(mes: str, ano: int) -> str | None:
    idx = MESES.index(mes)
    if idx == len(MESES) - 1 and ano == ANOS[-1]:
        return None
    if idx == len(MESES) - 1:
        return periodo_chave(MESES[0], ano + 1)
    return periodo_chave(MESES[idx + 1], ano)


def carry_over(mes: str, ano: int) -> None:
    """Copia a coluna O do período atual para a coluna I do próximo período,
    preservando os dados cadastrais (A-F)."""
    chave_atual = periodo_chave(mes, ano)
    chave_prox = periodo_seguinte(mes, ano)
    if chave_prox is None:
        st.warning("Não há próximo período disponível para carry over.")
        return

    df_atual = st.session_state.periodos.get(chave_atual, criar_dataframe_vazio())
    if df_atual.empty:
        st.warning("Período atual está vazio. Nada para carry over.")
        return

    df_prox = st.session_state.periodos.get(chave_prox, criar_dataframe_vazio()).copy()

    # Base cadastral A-F do período atual
    base = df_atual[["Cartão", "Resumo 7 dígitos", "Titular", "CPF", "Localidade", "Limite"]].copy()
    base["Saldo Anterior"] = pd.to_numeric(df_atual["Saldo Final do Mês"], errors="coerce").fillna(0.0).astype(float)

    # Demais colunas zeradas
    for col in ["Aprovado Reunião", "Valor Fatura", "Diferença a Pagar",
                "Diferença a Receber", "Saldo Final Ajustado", "Saldo Próxima Reunião",
                "Pós-Fechamento", "Saldo Final do Mês"]:
        base[col] = 0.0

    base = base[COLUNAS]
    st.session_state.periodos[chave_prox] = base.reset_index(drop=True)
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

st.sidebar.subheader("Período")
mes_sel = st.sidebar.selectbox("Mês", MESES, index=0)
ano_sel = st.sidebar.selectbox("Ano", ANOS, index=ANOS.index(2024))
chave_atual = periodo_chave(mes_sel, ano_sel)

st.sidebar.divider()

st.sidebar.subheader("Apelidos de Colunas")
with st.sidebar.expander("Renomear colunas exibidas", expanded=False):
    for col in COLUNAS:
        novo = st.text_input(f"{col}", value=st.session_state.apelidos.get(col, col), key=f"apelido_{col}")
        st.session_state.apelidos[col] = novo or col

st.sidebar.divider()

st.sidebar.subheader("Ações")
acao_carry = st.sidebar.button("⏭️ Carry over para próximo período")
if acao_carry:
    carry_over(mes_sel, ano_sel)
    st.rerun()

# -----------------------------------------------------------------------------
# Importação de dados
# -----------------------------------------------------------------------------
st.subheader(f"Período: {mes_sel} / {ano_sel}")

col_imp1, col_imp2 = st.columns([2, 1])
with col_imp1:
    arquivo = st.file_uploader("Importar Excel/CSV", type=["xlsx", "xls", "csv"], key=f"uploader_{chave_atual}")
with col_imp2:
    st.write("")
    st.write("")
    btn_importar = st.button("📥 Importar dados")

if btn_importar and arquivo is not None:
    try:
        # Leitura bruta sem dtype=str global para evitar conflitos em formatos mistos.
        # A conversão de tipos é tratada individualmente em normalizar_dataframe_importado.
        if arquivo.name.lower().endswith(".csv"):
            df_import = pd.read_csv(arquivo)
        else:
            df_import = pd.read_excel(arquivo)

        # Tabela temporária: mostra exatamente como o pandas está lendo as colunas
        # originais antes de qualquer processamento.
        st.write("### 📋 Pré-visualização bruta (como o pandas leu o arquivo)")
        st.dataframe(df_import.head(20), use_container_width=True)
        st.write(f"Colunas detectadas: {list(df_import.columns)}")

        df_norm = normalizar_dataframe_importado(df_import)
        df_norm = recalcular(df_norm)

        # FIX DO BUG: salvar explicitamente no período atual e forçar rerun
        st.session_state.periodos[chave_atual] = df_norm
        st.success(f"Importação concluída: {len(df_norm)} linha(s) carregada(s) para {chave_atual}.")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao importar arquivo: {e}")
elif btn_importar and arquivo is None:
    st.warning("Selecione um arquivo antes de importar.")

# -----------------------------------------------------------------------------
# Editor de dados
# -----------------------------------------------------------------------------
df_atual = obter_periodo_atual(mes_sel, ano_sel)

# FIX StreamlitAPIException: cast explícito + fill 0.0
df_editor = df_atual.copy()
for col in COLUNAS_NUMERICAS:
    df_editor[col] = pd.to_numeric(df_editor[col], errors="coerce").fillna(0.0).astype(float)

# Apelidos para exibição
df_display = df_editor.rename(columns=st.session_state.apelidos)

st.write(f"**Registros no período:** {len(df_display)}")

edited = st.data_editor(
    df_display,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_{chave_atual}",
    column_config={
        st.session_state.apelidos.get(c, c): st.column_config.NumberColumn(format="%.2f")
        for c in COLUNAS_NUMERICAS
    },
)

# Reverter apelidos -> nomes reais e salvar no session_state
mapa_reverso = {v: k for k, v in st.session_state.apelidos.items()}
df_salvar = edited.rename(columns=mapa_reverso)

# Garantir colunas numéricas
for col in COLUNAS_NUMERICAS:
    if col in df_salvar.columns:
        df_salvar[col] = pd.to_numeric(df_salvar[col], errors="coerce").fillna(0.0).astype(float)

# Recalcular lógica
df_salvar = recalcular(df_salvar)

st.session_state.periodos[chave_atual] = df_salvar

# -----------------------------------------------------------------------------
# Exportação
# -----------------------------------------------------------------------------
st.divider()
col_exp1, col_exp2 = st.columns([1, 3])
with col_exp1:
    btn_exportar = st.button("📤 Exportar Excel")
if btn_exportar:
    dados = exportar_excel(df_salvar)
    st.download_button(
        label="⬇️ Baixar arquivo",
        data=dados,
        file_name=f"conciliacao_{chave_atual}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# -----------------------------------------------------------------------------
# Informação de carry over
# -----------------------------------------------------------------------------
chave_ant = periodo_anterior(mes_sel, ano_sel)
if chave_ant and chave_ant in st.session_state.periodos:
    df_ant = st.session_state.periodos[chave_ant]
    if not df_ant.empty:
        st.info(f"📌 Período anterior ({chave_ant}) possui {len(df_ant)} registro(s). "
                f"Use 'Carry over' no período anterior para trazer o Saldo Final do Mês para o Saldo Anterior deste período.")

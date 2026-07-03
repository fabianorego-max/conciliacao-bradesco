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

# -----------------------------------------------------------------------------
# Configuração da página
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Bradesco Conciliação", layout="wide")

# -----------------------------------------------------------------------------
# Apelidos (renomeação amigável das colunas A-O)
# -----------------------------------------------------------------------------
APELIDOS = {
    "A": "Data",
    "B": "Documento",
    "C": "Histórico",
    "D": "Débito",
    "E": "Crédito",
    "F": "Saldo Bancário",
    "G": "Conciliado",
    "H": "Observação",
    "I": "Valor Conciliado",
    "J": "Saldo Anterior",
    "K": "Entradas",
    "L": "Saídas",
    "M": "Saldo Atual",
    "N": "Diferença",
    "O": "Status",
}

COLUNAS = list(APELIDOS.keys())
COLUNAS_NUMERICAS = ["D", "E", "F", "I", "J", "K", "L", "M", "N"]

# -----------------------------------------------------------------------------
# Inicialização do session_state
# -----------------------------------------------------------------------------
if "periodos" not in st.session_state:
    st.session_state.periodos = {}

if "periodo_atual" not in st.session_state:
    st.session_state.periodo_atual = None


def garantir_periodo(periodo: str) -> None:
    """Cria a estrutura base do período caso ainda não exista."""
    if periodo not in st.session_state.periodos:
        st.session_state.periodos[periodo] = criar_dataframe_vazio()


def criar_dataframe_vazio() -> pd.DataFrame:
    """Cria um DataFrame vazio com a estrutura A-O e tipos corretos."""
    dados = {col: [] for col in COLUNAS}
    df = pd.DataFrame(dados)
    return normalizar_dataframe(df)


def normalizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Garante que todas as colunas A-O existam, com tipos corretos."""
    for col in COLUNAS:
        if col not in df.columns:
            df[col] = 0.0 if col in COLUNAS_NUMERICAS else ""

    # Reordenar para A-O
    df = df[COLUNAS].copy()

    # Cast numérico + fill 0.0 para evitar StreamlitAPIException
    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    # Coluna G (Conciliado) como bool
    df["G"] = (
        df["G"].astype(str).str.lower().isin(["true", "1", "sim", "yes", "x"])
        if df["G"].dtype != bool
        else df["G"]
    )
    df["G"] = df["G"].fillna(False).astype(bool)

    # Strings como texto seguro
    for col in ["A", "B", "C", "H", "O"]:
        df[col] = df[col].astype(str).replace("nan", "")

    return df.reset_index(drop=True)


def calcular_colunas(df: pd.DataFrame, saldo_anterior: float = 0.0) -> pd.DataFrame:
    """Calcula J, K, L, M, N, O."""
    df = df.copy()

    # J - Saldo Anterior (carry-over do período anterior)
    df["J"] = float(saldo_anterior)

    # K - Entradas (crédito acumulado)
    df["K"] = df["E"].astype(float).cumsum()

    # L - Saídas (débito acumulado)
    df["L"] = df["D"].astype(float).cumsum()

    # M - Saldo Atual = Saldo Anterior + Entradas - Saídas
    df["M"] = df["J"] + df["K"] - df["L"]

    # N - Diferença entre saldo bancário e saldo calculado
    df["N"] = (df["F"].astype(float) - df["M"]).fillna(0.0)

    # O - Status
    df["O"] = df["N"].apply(lambda v: "Conciliado" if abs(float(v)) < 0.01 else "Pendente")

    return df


def obter_saldo_anterior(periodo_atual: str) -> float:
    """Recupera o saldo final do período anterior para carry-over."""
    try:
        mes, ano = periodo_atual.split("/")
        mes = int(mes)
        ano = int(ano)
        mes_ant = mes - 1
        ano_ant = ano
        if mes_ant == 0:
            mes_ant = 12
            ano_ant = ano - 1
        periodo_ant = f"{mes_ant:02d}/{ano_ant}"
        df_ant = st.session_state.periodos.get(periodo_ant)
        if df_ant is not None and not df_ant.empty:
            return float(df_ant["M"].iloc[-1])
    except Exception:
        pass
    return 0.0


def mapear_arquivo(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Mapeia colunas do arquivo importado para a estrutura A-O.

    Aceita tanto os apelidos quanto as letras A-O como cabeçalho.
    """
    mapa_inverso = {v.lower(): k for k, v in APELIDOS.items()}
    mapa_inverso.update({k.lower(): k for k in COLUNAS})

    novas_colunas = {}
    for col in df_raw.columns:
        chave = str(col).strip().lower()
        if chave in mapa_inverso:
            novas_colunas[col] = mapa_inverso[chave]

    df = df_raw.rename(columns=novas_colunas)

    # Manter apenas colunas reconhecidas; demais são descartadas
    df = df[[c for c in COLUNAS if c in df.columns]]

    return normalizar_dataframe(df)


# -----------------------------------------------------------------------------
# Cabeçalho
# -----------------------------------------------------------------------------
st.title("Bradesco Conciliação")

# -----------------------------------------------------------------------------
# Seletor de Mês/Ano
# -----------------------------------------------------------------------------
col_mes, col_ano, col_novo = st.columns([1, 1, 1])

with col_mes:
    mes_sel = st.selectbox(
        "Mês",
        options=[f"{m:02d}" for m in range(1, 13)],
        index=0,
        key="sel_mes",
    )

with col_ano:
    ano_sel = st.selectbox(
        "Ano",
        options=[str(a) for a in range(2020, 2031)],
        index=4,
        key="sel_ano",
    )

with col_novo:
    st.write("")
    st.write("")
    if st.button("Abrir / Criar Período"):
        periodo = f"{mes_sel}/{ano_sel}"
        garantir_periodo(periodo)
        st.session_state.periodo_atual = periodo
        st.rerun()

periodo = st.session_state.periodo_atual

if not periodo:
    st.info("Selecione um Mês/Ano e clique em 'Abrir / Criar Período' para começar.")
    st.stop()

garantir_periodo(periodo)

st.subheader(f"Período: {periodo}")

# -----------------------------------------------------------------------------
# Upload de arquivo (Excel/CSV)
# -----------------------------------------------------------------------------
with st.expander("Importar arquivo (Excel/CSV)", expanded=False):
    arquivo = st.file_uploader(
        "Selecione um arquivo .xlsx ou .csv",
        type=["xlsx", "xls", "csv"],
        key=f"uploader_{periodo}",
    )

    if arquivo is not None:
        try:
            if arquivo.name.lower().endswith(".csv"):
                df_raw = pd.read_csv(arquivo, dtype=str)
            else:
                df_raw = pd.read_excel(arquivo, dtype=str)

            df_mapeado = mapear_arquivo(df_raw)
            saldo_ant = obter_saldo_anterior(periodo)
            df_processado = calcular_colunas(df_mapeado, saldo_anterior)

            # FIX 1: armazenar corretamente no período atual
            st.session_state.periodos[periodo] = df_processado

            # FIX 2: garantir que o data_editor usará o valor atualizado
            st.session_state.periodo_atual = periodo

            st.success(
                f"Importação concluída com sucesso! "
                f"{len(df_processado)} registro(s) carregado(s) para {periodo}."
            )

            # FIX 6: rerun para atualizar a UI e exibir os novos dados
            st.rerun()

        except Exception as e:
            st.error(f"Erro ao importar o arquivo: {e}")

# -----------------------------------------------------------------------------
# Data Editor
# -----------------------------------------------------------------------------
df_atual = st.session_state.periodos.get(periodo, criar_dataframe_vazio())
df_atual = normalizar_dataframe(df_atual)

# Apelidos para exibição no data_editor
df_exibicao = df_atual.rename(columns=APELIDOS)

st.markdown("### Lançamentos")

config_colunas = {}
for letra, apelido in APELIDOS.items():
    if letra in COLUNAS_NUMERICAS:
        config_colunas[apelido] = st.column_config.NumberColumn(format="%.2f")
    elif letra == "G":
        config_colunas[apelido] = st.column_config.CheckboxColumn(default=False)
    elif letra == "A":
        config_colunas[apelido] = st.column_config.TextColumn(help="Data do lançamento")
    else:
        config_colunas[apelido] = st.column_config.TextColumn()

df_editado = st.data_editor(
    df_exibicao,
    num_rows="dynamic",
    use_container_width=True,
    column_config=config_colunas,
    key=f"editor_{periodo}",
    hide_index=True,
)

# -----------------------------------------------------------------------------
# Persistir edições do data_editor de volta no session_state
# -----------------------------------------------------------------------------
if df_editado is not None:
    # Reverter apelidos -> letras
    apelido_para_letra = {v: k for k, v in APELIDOS.items()}
    df_revertido = df_editado.rename(columns=apelido_para_letra)
    df_revertido = normalizar_dataframe(df_revertido)

    saldo_ant = obter_saldo_anterior(periodo)
    df_recalculado = calcular_colunas(df_revertido, saldo_ant)

    st.session_state.periodos[periodo] = df_recalculado

# -----------------------------------------------------------------------------
# Resumo do período
# -----------------------------------------------------------------------------
st.markdown("### Resumo")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Saldo Anterior (J)", f"{df_atual['J'].iloc[-1] if not df_atual.empty else 0.0:.2f}")
c2.metric("Entradas (K)", f"{df_atual['K'].iloc[-1] if not df_atual.empty else 0.0:.2f}")
c3.metric("Saídas (L)", f"{df_atual['L'].iloc[-1] if not df_atual.empty else 0.0:.2f}")
c4.metric("Saldo Atual (M)", f"{df_atual['M'].iloc[-1] if not df_atual.empty else 0.0:.2f}")

# -----------------------------------------------------------------------------
# Exportação
# -----------------------------------------------------------------------------
st.markdown("### Exportar")
col_exp_csv, col_exp_xlsx = st.columns(2)

with col_exp_csv:
    if st.button("Exportar CSV"):
        df_export = df_atual.rename(columns=APELIDOS)
        st.download_button(
            label="Baixar CSV",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name=f"conciliacao_bradesco_{periodo.replace('/', '-')}.csv",
            mime="text/csv",
        )

with col_exp_xlsx:
    if st.button("Exportar Excel"):
        df_export = df_atual.rename(columns=APELIDOS)
        st.download_button(
            label="Baixar XLSX",
            data=df_export.to_excel(index=False),
            file_name=f"conciliacao_bradesco_{periodo.replace('/', '-')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

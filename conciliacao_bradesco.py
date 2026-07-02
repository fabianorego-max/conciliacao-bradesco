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
from io import BytesIO


# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Conciliação Bradesco",
    page_icon="🏦",
    layout="wide",
)

st.title("🏦 Sistema de Conciliação Bradesco")

# ---------------------------------------------------------------------------
# Constantes auxiliares
# ---------------------------------------------------------------------------
ANOS = list(range(2024, 2031))
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

# Colunas base do Excel (A a O)
COLUNAS_PADRAO = {
    "A": "A",
    "B": "B",
    "C": "C",
    "D": "D",
    "E": "E",
    "F": "F",
    "G": "G",
    "H": "H",
    "I": "I",
    "J": "J",
    "K": "K",
    "L": "L",
    "M": "M",
    "N": "N",
    "O": "O",
}

# Colunas editáveis manualmente
COLUNAS_EDITAVEIS = ["A", "B", "C", "D", "E", "F", "G", "H", "N"]

# Colunas calculadas
COLUNAS_CALCULADAS = ["J", "K", "L", "M", "O"]

# Ordem final das colunas
ORDEM_COLUNAS = ["A", "B", "C", "D", "E", "F", "G", "H", "I",
                 "J", "K", "L", "M", "N", "O"]


# ---------------------------------------------------------------------------
# Inicialização do session_state
# ---------------------------------------------------------------------------
def init_state():
    if "dados" not in st.session_state:
        # dados[ano][mes] = DataFrame
        st.session_state["dados"] = {}
    if "apelidos" not in st.session_state:
        st.session_state["apelidos"] = dict(COLUNAS_PADRAO)


init_state()


# ---------------------------------------------------------------------------
# Funções utilitárias
# ---------------------------------------------------------------------------
def chave_mes(ano: int, mes: str) -> str:
    return f"{ano}_{mes}"


def obter_df(ano: int, mes: str) -> pd.DataFrame:
    """Retorna o DataFrame do mês/ano, criando um vazio se não existir."""
    chave = chave_mes(ano, mes)
    if ano not in st.session_state["dados"]:
        st.session_state["dados"][ano] = {}
    if chave not in st.session_state["dados"][ano]:
        st.session_state["dados"][ano][chave] = criar_df_vazio()
    return st.session_state["dados"][ano][chave]


def salvar_df(ano: int, mes: str, df: pd.DataFrame):
    chave = chave_mes(ano, mes)
    if ano not in st.session_state["dados"]:
        st.session_state["dados"][ano] = {}
    st.session_state["dados"][ano][chave] = df


def criar_df_vazio() -> pd.DataFrame:
    df = pd.DataFrame(columns=ORDEM_COLUNAS)
    return df


def aplicar_calculos(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica as fórmulas das colunas J, K, L, M e O de forma robusta."""
    df = df.copy()

    # Garantir que as colunas existam
    for col in ORDEM_COLUNAS:
        if col not in df.columns:
            df[col] = 0

    # Conversão robusta para numérico
    g = pd.to_numeric(df["G"], errors="coerce").fillna(0)
    h = pd.to_numeric(df["H"], errors="coerce").fillna(0)
    i = pd.to_numeric(df["I"], errors="coerce").fillna(0)
    n = pd.to_numeric(df["N"], errors="coerce").fillna(0)

    # J (Dif. Pagar): H - G se H > G, senão 0
    df["J"] = (h - g).where(h > g, 0)

    # K (Dif. Receber): G - H se G > H, senão 0
    df["K"] = (g - h).where(g > h, 0)

    # L (Saldo Final Ajustado): I + J - K
    df["L"] = i + pd.to_numeric(df["J"], errors="coerce").fillna(0) - pd.to_numeric(df["K"], errors="coerce").fillna(0)

    # M (Saldo Próxima Reunião): G + L - H
    df["M"] = g + pd.to_numeric(df["L"], errors="coerce").fillna(0) - h

    # O (Saldo Final do Mês): G + L - N
    df["O"] = g + pd.to_numeric(df["L"], errors="coerce").fillna(0) - n

    return df


def renomear_para_apelidos(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna uma cópia do DataFrame com os apelidos definidos pelo usuário."""
    mapa = st.session_state["apelidos"]
    return df.rename(columns=mapa)


def reverter_apelidos(df: pd.DataFrame) -> pd.DataFrame:
    """Reverte os apelidos para as letras originais (A-O)."""
    mapa = st.session_state["apelidos"]
    inverso = {v: k for k, v in mapa.items()}
    return df.rename(columns=inverso)


def mes_seguinte(mes: str) -> str:
    idx = MESES.index(mes)
    return MESES[(idx + 1) % 12]


def ano_seguinte(ano: int, mes: str) -> int:
    if mes == "Dezembro":
        return ano + 1
    return ano


def exportar_excel(df: pd.DataFrame) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Conciliacao")
    output.seek(0)
    return output


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuração")

    ano = st.selectbox("Ano", ANOS, index=ANOS.index(2024))
    mes = st.selectbox("Mês", MESES, index=0)

    st.divider()

    # Configuração de apelidos das colunas A a O
    with st.expander("🏷️ Apelidos das Colunas (A a O)"):
        st.caption("Defina nomes amigáveis para cada coluna.")
        for letra in ORDEM_COLUNAS:
            valor_atual = st.session_state["apelidos"].get(letra, letra)
            novo = st.text_input(
                f"Coluna {letra}",
                value=valor_atual,
                key=f"apelido_{letra}",
            )
            st.session_state["apelidos"][letra] = novo if novo.strip() else letra

    st.divider()

    # Importação de arquivo
    st.subheader("📂 Importar Planilha")
    arquivo = st.file_uploader(
        "Carregar arquivo Excel/CSV",
        type=["xlsx", "xls", "csv"],
        key=f"uploader_{ano}_{mes}",
    )

    if arquivo is not None:
        try:
            if arquivo.name.lower().endswith(".csv"):
                df_import = pd.read_csv(arquivo)
            else:
                df_import = pd.read_excel(arquivo)

            # Garantir que as colunas A-O existam
            for col in ORDEM_COLUNAS:
                if col not in df_import.columns:
                    df_import[col] = 0

            # Manter apenas as colunas A-O na ordem correta
            df_import = df_import[ORDEM_COLUNAS]

            # Aplicar cálculos
            df_import = aplicar_calculos(df_import)

            salvar_df(ano, mes, df_import)
            st.success(f"✅ Arquivo carregado para {mes}/{ano}!")
        except Exception as e:
            st.error(f"❌ Erro ao importar arquivo: {e}")

    st.divider()

    # Botão Fechar Mês
    st.subheader("🔒 Fechar Mês")
    if st.button("Fechar Mês e Transportar Saldo", type="primary"):
        df_atual = obter_df(ano, mes)
        if df_atual.empty:
            st.warning("⚠️ Não há dados para o mês atual.")
        else:
            df_atual = aplicar_calculos(df_atual)
            # Saldo final do mês (coluna O) - soma caso haja múltiplas linhas
            saldo_final = pd.to_numeric(df_atual["O"], errors="coerce").fillna(0).sum()

            prox_mes = mes_seguinte(mes)
            prox_ano = ano_seguinte(ano, mes)

            df_prox = obter_df(prox_ano, prox_mes)
            df_prox = df_prox.copy()

            # Se o próximo mês estiver vazio, cria uma linha inicial
            if df_prox.empty:
                df_prox = pd.DataFrame([{col: 0 for col in ORDEM_COLUNAS}])

            # Transporta o valor da coluna O para a coluna I do próximo mês
            df_prox["I"] = pd.to_numeric(df_prox["I"], errors="coerce").fillna(0)
            df_prox["I"] = saldo_final

            df_prox = aplicar_calculos(df_prox)
            salvar_df(prox_ano, prox_mes, df_prox)

            # Marca o mês atual como fechado (atualiza os cálculos)
            salvar_df(ano, mes, df_atual)

            st.success(
                f"✅ Mês fechado! Saldo R$ {saldo_final:,.2f} transportado para "
                f"{prox_mes}/{prox_ano} (Coluna I)."
            )
            st.rerun()

    st.divider()

    # Exportar
    st.subheader("💾 Exportar")
    df_export = obter_df(ano, mes)
    if not df_export.empty:
        df_export_calc = aplicar_calculos(df_export)
        df_export_apelidos = renomear_para_apelidos(df_export_calc)
        excel_bytes = exportar_excel(df_export_apelidos)
        st.download_button(
            label="⬇️ Baixar Excel",
            data=excel_bytes,
            file_name=f"conciliacao_{mes}_{ano}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.info("Nenhum dado para exportar.")


# ---------------------------------------------------------------------------
# Área principal
# ---------------------------------------------------------------------------
st.subheader(f"📋 Conciliação — {mes} / {ano}")

df = obter_df(ano, mes)

if df.empty:
    st.info(
        "ℹ️ Nenhum dado encontrado para este mês. "
        "Importe um arquivo Excel/CSV na sidebar ou adicione linhas manualmente."
    )
    if st.button("➕ Criar tabela vazia com 1 linha"):
        df_novo = pd.DataFrame([{col: 0 for col in ORDEM_COLUNAS}])
        salvar_df(ano, mes, df_novo)
        st.rerun()
else:
    # Preparar DataFrame para o editor (com apelidos)
    df_calc = aplicar_calculos(df)
    df_editor = renomear_para_apelidos(df_calc).reset_index(drop=True)

    # Determinar quais colunas (apelidos) são editáveis
    apelidos_editaveis = [st.session_state["apelidos"][c] for c in COLUNAS_EDITAVEIS]

    st.caption(
        "✏️ Colunas editáveis: "
        + ", ".join(apelidos_editaveis)
        + "  |  🧮 Colunas calculadas automaticamente: "
        + ", ".join([st.session_state["apelidos"][c] for c in COLUNAS_CALCULADAS])
    )

    df_editado = st.data_editor(
        df_editor,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            apelido: st.column_config.NumberColumn(
                label=apelido,
                help=f"Coluna {letra} (editável)" if letra in COLUNAS_EDITAVEIS else f"Coluna {letra} (calculada)",
                format="%.2f",
            )
            for letra, apelido in st.session_state["apelidos"].items()
        },
        key=f"editor_{ano}_{mes}",
    )

    # Reverter apelidos e salvar
    df_revertido = reverter_apelidos(df_editado)
    # Garantir ordem das colunas
    for col in ORDEM_COLUNAS:
        if col not in df_revertido.columns:
            df_revertido[col] = 0
    df_revertido = df_revertido[ORDEM_COLUNAS]

    # Recalcular com base nos valores editados
    df_recalculado = aplicar_calculos(df_revertido)
    salvar_df(ano, mes, df_recalculado)

    # Exibir resumo
    st.divider()
    st.subheader("📊 Resumo")
    col1, col2, col3, col4 = st.columns(4)
    total_g = pd.to_numeric(df_recalculado["G"], errors="coerce").fillna(0).sum()
    total_h = pd.to_numeric(df_recalculado["H"], errors="coerce").fillna(0).sum()
    total_o = pd.to_numeric(df_recalculado["O"], errors="coerce").fillna(0).sum()
    total_i = pd.to_numeric(df_recalculado["I"], errors="coerce").fillna(0).sum()

    col1.metric(st.session_state["apelidos"]["G"], f"R$ {total_g:,.2f}")
    col2.metric(st.session_state["apelidos"]["H"], f"R$ {total_h:,.2f}")
    col3.metric(st.session_state["apelidos"]["I"], f"R$ {total_i:,.2f}")
    col4.metric(st.session_state["apelidos"]["O"], f"R$ {total_o:,.2f}")

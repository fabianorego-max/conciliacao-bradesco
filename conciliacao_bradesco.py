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
from datetime import datetime

# =============================================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================================
st.set_page_config(
    page_title="Conciliação Bradesco",
    page_icon="🏦",
    layout="wide",
)

st.title("🏦 Sistema de Conciliação Bradesco")
st.markdown("---")

# =============================================================================
# COLUNAS PADRÃO (A a O)
# =============================================================================
COLUNAS_ORIGINAIS = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I",
    "J", "K", "L", "M", "N", "O",
]

# Rótulos padrão para exibição (podem ser sobrescritos pelo usuário)
ROTULOS_PADRAO = {
    "A": "Data",
    "B": "Descrição",
    "C": "Documento",
    "D": "Débito",
    "E": "Crédito",
    "F": "Valor",
    "G": "Saldo",
    "H": "Categoria",
    "I": "Observação",
    "J": "Entradas",
    "K": "Saídas",
    "L": "Saldo Calculado",
    "M": "Diferença",
    "N": "Status",
    "O": "Saldo Acumulado",
}

# Colunas que participam da lógica de cálculo
COLUNAS_CALCULO = ["J", "K", "L", "M", "O"]

# =============================================================================
# SESSÃO: INICIALIZAÇÃO DE ESTADO
# =============================================================================
if "df_conciliacao" not in st.session_state:
    dados_iniciais = {
        col: [0.0] * 5 for col in COLUNAS_ORIGINAIS
    }
    # Ajustar tipos iniciais para colunas específicas
    dados_iniciais["A"] = ["01/01/2024", "02/01/2024", "03/01/2024", "04/01/2024", "05/01/2024"]
    dados_iniciais["B"] = ["Depósito", "Pagamento", "Transferência", "Recebimento", "Taxa"]
    dados_iniciais["C"] = ["001", "002", "003", "004", "005"]
    dados_iniciais["D"] = [0.0, 150.00, 500.00, 0.0, 25.00]
    dados_iniciais["E"] = [1000.00, 0.0, 0.0, 750.00, 0.0]
    dados_iniciais["F"] = [1000.00, -150.00, -500.00, 750.00, -25.00]
    dados_iniciais["G"] = [1000.00, 850.00, 350.00, 1100.00, 1075.00]
    dados_iniciais["H"] = ["Receita", "Despesa", "Despesa", "Receita", "Despesa"]
    dados_iniciais["I"] = ["", "Boleto", "PIX", "Depósito", "Tarifa"]
    dados_iniciais["J"] = [1000.00, 0.0, 0.0, 750.00, 0.0]
    dados_iniciais["K"] = [0.0, 150.00, 500.00, 0.0, 25.00]
    dados_iniciais["L"] = [0.0, 0.0, 0.0, 0.0, 0.0]
    dados_iniciais["M"] = [0.0, 0.0, 0.0, 0.0, 0.0]
    dados_iniciais["N"] = ["Pendente", "Pendente", "Pendente", "Pendente", "Pendente"]
    dados_iniciais["O"] = [0.0, 0.0, 0.0, 0.0, 0.0]

    st.session_state["df_conciliacao"] = pd.DataFrame(dados_iniciais)

if "apelidos_colunas" not in st.session_state:
    st.session_state["apelidos_colunas"] = dict(ROTULOS_PADRAO)

if "saldo_anterior" not in st.session_state:
    st.session_state["saldo_anterior"] = 0.0

if "ano_selecionado" not in st.session_state:
    st.session_state["ano_selecionado"] = datetime.now().year

if "mes_selecionado" not in st.session_state:
    st.session_state["mes_selecionado"] = datetime.now().month

# =============================================================================
# BARRA LATERAL: FILTROS DE ANO/MÊS E SALDO ANTERIOR
# =============================================================================
st.sidebar.header("📅 Filtros de Período")

anos_disponiveis = list(range(2020, datetime.now().year + 2))
ano_selecionado = st.sidebar.selectbox(
    "Ano",
    options=anos_disponiveis,
    index=anos_disponiveis.index(st.session_state["ano_selecionado"])
        if st.session_state["ano_selecionado"] in anos_disponiveis
        else len(anos_disponiveis) - 2,
)
st.session_state["ano_selecionado"] = ano_selecionado

meses_nomes = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
mes_selecionado = st.sidebar.selectbox(
    "Mês",
    options=list(range(1, 13)),
    format_func=lambda x: meses_nomes[x - 1],
    index=st.session_state["mes_selecionado"] - 1,
)
st.session_state["mes_selecionado"] = mes_selecionado

st.sidebar.markdown("---")

st.sidebar.header("💰 Transporte de Saldo")
saldo_anterior = st.sidebar.number_input(
    "Saldo Anterior (transportado)",
    value=float(st.session_state["saldo_anterior"]),
    format="%.2f",
    step=0.01,
    help="Saldo transportado do mês anterior para cálculo do saldo acumulado.",
)
st.session_state["saldo_anterior"] = saldo_anterior

st.sidebar.markdown("---")

# =============================================================================
# BARRA LATERAL: CONFIGURAÇÕES DE COLUNAS (Apelidos)
# =============================================================================
with st.sidebar.expander("⚙️ Configurações de Colunas", expanded=False):
    st.caption("Defina um apelido personalizado para cada coluna (A a O).")
    st.caption("A lógica interna de cálculo não é afetada.")

    apelidos = {}
    for col in COLUNAS_ORIGINAIS:
        rotulo_padrao = ROTULOS_PADRAO.get(col, col)
        valor_atual = st.session_state["apelidos_colunas"].get(col, rotulo_padrao)
        novo_apelido = st.text_input(
            f"Coluna {col} (padrão: {rotulo_padrao})",
            value=valor_atual,
            key=f"apelido_{col}",
            help=f"Apelido exibido para a coluna {col}.",
        )
        apelidos[col] = novo_apelido if novo_apelido.strip() else col

    st.session_state["apelidos_colunas"] = apelidos

    col_reset1, col_reset2 = st.columns(2)
    if col_reset1.button("🔄 Restaurar Padrão", use_container_width=True):
        st.session_state["apelidos_colunas"] = dict(ROTULOS_PADRAO)
        st.rerun()

# =============================================================================
# LÓGICA DE CÁLCULO (usa chaves internas J, K, L, M, O)
# =============================================================================
def recalcular_saldos(df: pd.DataFrame, saldo_inicial: float) -> pd.DataFrame:
    """
    Recalcula as colunas internas de cálculo:
      J = Entradas
      K = Saídas
      L = Saldo Calculado (acumulado)
      M = Diferença (L - G)
      O = Saldo Acumulado (transporte de saldo)
    """
    df = df.copy()

    # J (Entradas) e K (Saídas) a partir de E (Crédito) e D (Débito)
    df["J"] = pd.to_numeric(df.get("E", 0), errors="coerce").fillna(0.0)
    df["K"] = pd.to_numeric(df.get("D", 0), errors="coerce").fillna(0.0)

    # L (Saldo Calculado) = saldo acumulado linha a linha
    entradas = pd.to_numeric(df["J"], errors="coerce").fillna(0.0)
    saidas = pd.to_numeric(df["K"], errors="coerce").fillna(0.0)
    df["L"] = (saldo_inicial + (entradas - saidas).cumsum()).round(2)

    # M (Diferença) = L - G (Saldo informado)
    saldo_informado = pd.to_numeric(df.get("G", 0), errors="coerce").fillna(0.0)
    df["M"] = (df["L"] - saldo_informado).round(2)

    # O (Saldo Acumulado) = transporte de saldo + acumulado
    df["O"] = df["L"]

    return df

# Aplicar recálculo sempre que os dados mudarem
df_atual = st.session_state["df_conciliacao"].copy()
df_atual = recalcular_saldos(df_atual, st.session_state["saldo_anterior"])

# =============================================================================
# CONSTRUÇÃO DO column_config PARA st.data_editor
# =============================================================================
apelidos_atuais = st.session_state["apelidos_colunas"]

column_config = {}
for col in COLUNAS_ORIGINAIS:
    label = apelidos_atuais.get(col, col)
    if col in ["D", "E", "F", "G", "J", "K", "L", "M", "O"]:
        column_config[col] = st.column_config.NumberColumn(
            label=label,
            format="%.2f",
            help=f"Coluna interna: {col}",
        )
    elif col == "A":
        column_config[col] = st.column_config.TextColumn(
            label=label,
            help=f"Coluna interna: {col}",
        )
    else:
        column_config[col] = st.column_config.TextColumn(
            label=label,
            help=f"Coluna interna: {col}",
        )

# =============================================================================
# EXIBIÇÃO DO DATA EDITOR
# =============================================================================
st.subheader(
    f"📋 Conciliação — {meses_nomes[mes_selecionado - 1]} / {ano_selecionado}"
)

st.markdown(
    """
    Edite os valores diretamente na tabela abaixo. As colunas de cálculo
    (**J**, **K**, **L**, **M**, **O**) são recalculadas automaticamente
    usando as chaves internas, independentemente dos apelidos definidos.
    """
)

df_editor = st.data_editor(
    df_atual,
    column_config=column_config,
    column_order=COLUNAS_ORIGINAIS,
    num_rows="dynamic",
    use_container_width=True,
    key="data_editor_conciliacao",
    hide_index=True,
)

# Atualizar o DataFrame na sessão com as edições do usuário
st.session_state["df_conciliacao"] = df_editor.copy()

# =============================================================================
# RESUMO E VALIDAÇÃO
# =============================================================================
st.markdown("---")
st.subheader("📊 Resumo da Conciliação")

col_r1, col_r2, col_r3, col_r4 = st.columns(4)

total_entradas = float(pd.to_numeric(df_editor["J"], errors="coerce").fillna(0).sum())
total_saidas = float(pd.to_numeric(df_editor["K"], errors="coerce").fillna(0).sum())
saldo_final = float(pd.to_numeric(df_editor["L"], errors="coerce").fillna(0).iloc[-1]) if len(df_editor) > 0 else 0.0
diferenca_total = float(pd.to_numeric(df_editor["M"], errors="coerce").fillna(0).sum())

col_r1.metric(
    label=f"Total {apelidos_atuais.get('J', 'Entradas')}",
    value=f"R$ {total_entradas:,.2f}",
)
col_r2.metric(
    label=f"Total {apelidos_atuais.get('K', 'Saídas')}",
    value=f"R$ {total_saidas:,.2f}",
)
col_r3.metric(
    label=f"{apelidos_atuais.get('L', 'Saldo Calculado')}",
    value=f"R$ {saldo_final:,.2f}",
)
col_r4.metric(
    label=f"{apelidos_atuais.get('M', 'Diferença')}",
    value=f"R$ {diferenca_total:,.2f}",
    delta="Conciliado" if abs(diferenca_total) < 0.01 else "Divergência",
    delta_color="normal" if abs(diferenca_total) < 0.01 else "inverse",
)

st.markdown("---")
st.caption(
    "Sistema de Conciliação Bradesco — Os apelidos das colunas são apenas visuais; "
    "a lógica de cálculo utiliza as chaves internas (A–O)."
)

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
st.set_page_config(page_title="Conciliação de Cartões Bradesco", page_icon="💳", layout="wide")

# ---------------------------------------------------------------------------
# Constantes e definição das colunas
# ---------------------------------------------------------------------------
COLUNAS = [
    "A_Cartao",            # A
    "B_Resumo",            # B
    "C_Titular",           # C
    "D_CPF",               # D
    "E_Localidade",        # E
    "F_Limite",            # F
    "G_Aprovado_Reuniao", # G (manual)
    "H_Valor_Fatura",      # H (manual)
    "I_Saldo_Anterior",    # I (recebe O do mês anterior)
    "J_Dif_Pagar",         # J (lógica)
    "K_Dif_Receber",       # K (lógica)
    "L_Saldo_Final_Ajust", # L (fórmula)
    "M_Saldo_Prox_Reuniao",# M (fórmula)
    "N_Pos_Fechamento",    # N (manual)
    "O_Saldo_Final_Mes",   # O (fórmula)
]

COLUNAS_CADASTRAIS = COLUNAS[0:6]   # A-F
COLUNAS_MANUAIS = ["G_Aprovado_Reuniao", "H_Valor_Fatura", "N_Pos_Fechamento"]
COLUNAS_CALCULADAS = ["J_Dif_Pagar", "K_Dif_Receber", "L_Saldo_Final_Ajust",
                      "M_Saldo_Prox_Reuniao", "O_Saldo_Final_Mes"]

# ---------------------------------------------------------------------------
# Inicialização do estado da sessão
# ---------------------------------------------------------------------------
if "df" not in st.session_state:
    # DataFrame inicial vazio com todas as colunas
    st.session_state.df = pd.DataFrame(columns=COLUNAS)
    # Tipos numéricos para colunas monetárias
    for c in ["F_Limite", "G_Aprovado_Reuniao", "H_Valor_Fatura",
              "I_Saldo_Anterior", "J_Dif_Pagar", "K_Dif_Receber",
              "L_Saldo_Final_Ajust", "M_Saldo_Prox_Reuniao",
              "N_Pos_Fechamento", "O_Saldo_Final_Mes"]:
        st.session_state.df[c] = pd.Series(dtype="float")

if "mes_fechado" not in st.session_state:
    st.session_state.mes_fechado = False


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------
def calcular_formulas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica todas as fórmulas de conciliação ao DataFrame.

    Regras:
      - Coluna J (Diferença a Pagar): se H > G => J = H - G, senão J = 0
      - Coluna K (Diferença a Receber): se H < G => K = G - H, senão K = 0
      - Coluna L (Saldo Final Ajustado): I + J - K
      - Coluna M (Saldo Próxima Reunião): G + L - H
      - Coluna O (Saldo Final do Mês): G + L - N
    """
    df = df.copy()

    # Garantir valores numéricos (NaN -> 0 para cálculos)
    G = df["G_Aprovado_Reuniao"].fillna(0).astype(float)
    H = df["H_Valor_Fatura"].fillna(0).astype(float)
    I = df["I_Saldo_Anterior"].fillna(0).astype(float)
    N = df["N_Pos_Fechamento"].fillna(0).astype(float)

    # --- Coluna J: Diferença a Pagar ---
    # Se a fatura (H) for maior que o aprovado (G), existe valor a pagar.
    # J = H - G quando H > G, caso contrário J = 0.
    df["J_Dif_Pagar"] = (H - G).where(H > G, 0.0)

    # --- Coluna K: Diferença a Receber ---
    # Se o aprovado (G) for maior que a fatura (H), existe valor a receber.
    # K = G - H quando H < G, caso contrário K = 0.
    df["K_Dif_Receber"] = (G - H).where(H < G, 0.0)

    # Quando H == G, ambas as condições acima resultam em 0 (J = 0 e K = 0).

    # --- Coluna L: Saldo Final Ajustado ---
    # L = I + J - K
    # Soma o saldo anterior, acrescenta o que há a pagar e subtrai o que há a receber.
    df["L_Saldo_Final_Ajust"] = I + df["J_Dif_Pagar"] - df["K_Dif_Receber"]

    # --- Coluna M: Saldo Próxima Reunião ---
    # M = G + L - H
    # Valor aprovado na reunião atual mais o saldo final ajustado, menos a fatura.
    df["M_Saldo_Prox_Reuniao"] = G + df["L_Saldo_Final_Ajust"] - H

    # --- Coluna O: Saldo Final do Mês ---
    # O = G + L - N
    # Valor aprovado mais o saldo final ajustado, menos o pós-fechamento.
    df["O_Saldo_Final_Mes"] = G + df["L_Saldo_Final_Ajust"] - N

    return df


def fechar_mes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Funcionalidade 'Fechar Mês':
      1) Transporta os valores da Coluna O (Saldo Final do Mês) para a Coluna I (Saldo Anterior).
      2) Limpa os lançamentos manuais (G, H, N).
    """
    df = df.copy()
    # Transporta O -> I (saldo final do mês vira saldo anterior do próximo mês)
    df["I_Saldo_Anterior"] = df["O_Saldo_Final_Mes"].fillna(0).astype(float)
    # Limpa lançamentos manuais
    df["G_Aprovado_Reuniao"] = 0.0
    df["H_Valor_Fatura"] = 0.0
    df["N_Pos_Fechamento"] = 0.0
    # Recalcula as fórmulas com os novos valores
    df = calcular_formulas(df)
    return df


def exportar_excel(df: pd.DataFrame) -> BytesIO:
    """Exporta o DataFrame para um arquivo Excel em memória."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Conciliacao")
    output.seek(0)
    return output


# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------
st.title("💳 Conciliação de Cartões Bradesco")
st.markdown("Sistema completo para conciliação mensal de cartões com lógica automática de saldos.")

# ---------------------------------------------------------------------------
# Barra lateral: ações e importação
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Ações")

    # Adicionar nova linha (cartão)
    if st.button("➕ Adicionar Cartão", use_container_width=True):
        nova_linha = {c: "" for c in COLUNAS}
        for c in ["F_Limite", "G_Aprovado_Reuniao", "H_Valor_Fatura",
                  "I_Saldo_Anterior", "J_Dif_Pagar", "K_Dif_Receber",
                  "L_Saldo_Final_Ajust", "M_Saldo_Prox_Reuniao",
                  "N_Pos_Fechamento", "O_Saldo_Final_Mes"]:
            nova_linha[c] = 0.0
        st.session_state.df = pd.concat(
            [st.session_state.df, pd.DataFrame([nova_linha])],
            ignore_index=True
        )
        st.success("Cartão adicionado!")

    # Importar planilha Excel
    uploaded = st.file_uploader("📂 Importar Excel", type=["xlsx", "xls"])
    if uploaded is not None:
        try:
            df_import = pd.read_excel(uploaded)
            # Renomeia colunas se necessário (mantém compatibilidade)
            for c in COLUNAS:
                if c not in df_import.columns:
                    df_import[c] = 0.0 if c not in COLUNAS_CADASTRAIS else ""
            df_import = df_import[COLUNAS]
            st.session_state.df = calcular_formulas(df_import)
            st.success("Planilha importada com sucesso!")
        except Exception as e:
            st.error(f"Erro ao importar: {e}")

    # Exportar Excel
    st.download_button(
        label="💾 Exportar Excel",
        data=exportar_excel(st.session_state.df),
        file_name="conciliacao_bradesco.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()

    # Botão Fechar Mês
    st.subheader("🔒 Fechar Mês")
    st.caption("Transporta a Coluna O para a Coluna I e limpa G, H e N.")
    if st.button("Fechar Mês", type="primary", use_container_width=True):
        if st.session_state.df.empty:
            st.warning("Não há dados para fechar o mês.")
        else:
            st.session_state.df = fechar_mes(st.session_state.df)
            st.session_state.mes_fechado = True
            st.success("Mês fechado! Saldo final transportado para o saldo anterior.")

    if st.session_state.mes_fechado:
        st.info("✅ Mês fechado. Pronto para o próximo ciclo.")

# ---------------------------------------------------------------------------
# Tabela editável (st.data_editor)
# ---------------------------------------------------------------------------
st.header("📋 Tabela de Conciliação")

# Recalcula fórmulas antes de exibir (mantém consistência)
df_exibicao = calcular_formulas(st.session_state.df)

# Configuração das colunas no data_editor
config_colunas = {}
for c in COLUNAS_CADASTRAIS:
    config_colunas[c] = st.column_config.TextColumn(c, required=False)
for c in ["F_Limite", "G_Aprovado_Reuniao", "H_Valor_Fatura",
          "I_Saldo_Anterior", "N_Pos_Fechamento"]:
    config_colunas[c] = st.column_config.NumberColumn(
        c, format="%.2f", step=0.01, required=False
    )
# Colunas calculadas: somente leitura
for c in COLUNAS_CALCULADAS:
    config_colunas[c] = st.column_config.NumberColumn(c, format="%.2f", disabled=True)

# Editor de dados
df_editado = st.data_editor(
    df_exibicao,
    column_config=config_colunas,
    num_rows="dynamic",
    use_container_width=True,
    key="editor_conciliacao",
)

# Atualiza o estado com as edições do usuário e recalcula
st.session_state.df = calcular_formulas(df_editado)

# ---------------------------------------------------------------------------
# Dashboard com métricas totais
# ---------------------------------------------------------------------------
st.header("📊 Dashboard de Métricas")

df_metricas = calcular_formulas(st.session_state.df)

if not df_metricas.empty:
    total_limite = df_metricas["F_Limite"].sum()
    total_aprovado = df_metricas["G_Aprovado_Reuniao"].sum()
    total_fatura = df_metricas["H_Valor_Fatura"].sum()
    total_saldo_anterior = df_metricas["I_Saldo_Anterior"].sum()
    total_pagar = df_metricas["J_Dif_Pagar"].sum()
    total_receber = df_metricas["K_Dif_Receber"].sum()
    total_saldo_ajust = df_metricas["L_Saldo_Final_Ajust"].sum()
    total_prox_reuniao = df_metricas["M_Saldo_Prox_Reuniao"].sum()
    total_pos_fech = df_metricas["N_Pos_Fechamento"].sum()
    total_saldo_mes = df_metricas["O_Saldo_Final_Mes"].sum()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Limite Total", f"R$ {total_limite:,.2f}")
        st.metric("Aprovado Reunião (G)", f"R$ {total_aprovado:,.2f}")
        st.metric("Valor Fatura (H)", f"R$ {total_fatura:,.2f}")
    with col2:
        st.metric("Saldo Anterior (I)", f"R$ {total_saldo_anterior:,.2f}")
        st.metric("Diferença a Pagar (J)", f"R$ {total_pagar:,.2f}")
        st.metric("Diferença a Receber (K)", f"R$ {total_receber:,.2f}")
    with col3:
        st.metric("Saldo Final Ajustado (L)", f"R$ {total_saldo_ajust:,.2f}")
        st.metric("Saldo Próx. Reunião (M)", f"R$ {total_prox_reuniao:,.2f}")
        st.metric("Pós-Fechamento (N)", f"R$ {total_pos_fech:,.2f}")
    with col4:
        st.metric("Saldo Final do Mês (O)", f"R$ {total_saldo_mes:,.2f}")
        # Indicador de equilíbrio
        if total_pagar > 0:
            st.warning("⚠️ Há valores a pagar.")
        elif total_receber > 0:
            st.info("ℹ️ Há valores a receber.")
        else:
            st.success("✅ Faturas e aprovados equilibrados.")

    # Gráfico de saldo final por cartão
    st.subheader("📈 Saldo Final do Mês por Cartão")
    df_grafico = df_metricas.copy()
    df_grafico["Label"] = df_grafico["A_Cartao"].astype(str) + " - " + df_grafico["C_Titular"].astype(str)
    st.bar_chart(df_grafico.set_index("Label")[["O_Saldo_Final_Mes"]])
else:
    st.info("Nenhum cartão cadastrado. Use o botão '➕ Adicionar Cartão' na barra lateral ou importe uma planilha.")

# ---------------------------------------------------------------------------
# Rodapé explicativo das fórmulas
# ---------------------------------------------------------------------------
with st.expander("📖 Explicação das Fórmulas"):
    st.markdown("""
    **Colunas A-F:** Dados cadastrais (Cartão, Resumo 7 dígitos, Titular, CPF, Localidade, Limite).

    **Colunas G, H, N:** Entradas manuais (Aprovado Reunião, Valor Fatura, Pós-Fechamento).

    **Coluna I (Saldo Anterior):** Recebe o valor da Coluna O do mês anterior.

    **Colunas J e K (Lógica):**
    - Se **H > G**: **J = H - G** (diferença a pagar) e **K = 0**.
    - Se **H < G**: **K = G - H** (diferença a receber) e **J = 0**.
    - Se **H == G**: **J = 0** e **K = 0** (equilibrado).

    **Coluna L (Saldo Final Ajustado):** `L = I + J - K`
    Soma o saldo anterior, acrescenta o que há a pagar e subtrai o que há a receber.

    **Coluna M (Saldo Próxima Reunião):** `M = G + L - H`
    Valor aprovado na reunião atual mais o saldo final ajustado, menos a fatura.

    **Coluna O (Saldo Final do Mês):** `O = G + L - N`
    Valor aprovado mais o saldo final ajustado, menos o pós-fechamento.

    **Fechar Mês:** Transporta a Coluna O para a Coluna I e limpa as entradas manuais (G, H, N).
    """)
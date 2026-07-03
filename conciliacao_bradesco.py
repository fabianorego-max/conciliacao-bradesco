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
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Conciliação Bradesco", layout="wide")

# --- INICIALIZAÇÃO DO ESTADO ---
if "dados" not in st.session_state:
    st.session_state.dados = {}  # Armazena DataFrames por 'YYYY-MM'
if "apelidos" not in st.session_state:
    st.session_state.apelidos = {
        "A": "Cartão", "B": "Resumo (7 dígitos)", "C": "Titular", 
        "D": "CPF", "E": "Localidade", "F": "Limite", 
        "G": "Valor Reunião", "H": "Valor Fatura", "I": "Saldo Inicial",
        "J": "Dif. Pagar", "K": "Dif. Receber", "L": "Saldo Final Ajustado",
        "M": "Saldo Próxima Reunião", "N": "Pós-Fechamento", "O": "Saldo Final Mês"
    }

# --- FUNÇÕES DE CÁLCULO ---
def calcular_colunas(df):
    df = df.copy()
    # Garantir tipos numéricos
    for col in ["F", "G", "H", "I", "N"]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # B: Últimos 7 dígitos do cartão
    df["B"] = df["A"].astype(str).apply(lambda x: x[-7:] if len(x) >= 7 else x)
    
    # J e K: Lógica de Diferença
    df["J"] = np.where(df["H"] > df["G"], df["H"] - df["G"], 0.0)
    df["K"] = np.where(df["H"] < df["G"], df["G"] - df["H"], 0.0)
    
    # L: I + J - K
    df["L"] = df["I"] + df["J"] - df["K"]
    
    # M: G + L - H
    df["M"] = df["G"] + df["L"] - df["H"]
    
    # O: G + L - N
    df["O"] = df["G"] + df["L"] - df["N"]
    
    return df

# --- INTERFACE ---
st.title("🏦 Sistema de Conciliação Bradesco")

with st.sidebar:
    st.header("📅 Período de Trabalho")
    ano = st.selectbox("Ano", range(2024, 2031), index=2)
    mes = st.selectbox("Mês", ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"], index=6)
    periodo_atual = f"{ano}-{mes}"
    
    st.divider()
    st.header("🏷️ Personalizar Colunas")
    with st.expander("Editar Nomes"):
        for letra in "ABCDEFGHIJKLMNO":
            st.session_state.apelidos[letra] = st.text_input(f"Coluna {letra}", st.session_state.apelidos[letra])

# Obter ou Criar dados do mês
if periodo_atual not in st.session_state.dados:
    # Se for o primeiro acesso, podemos carregar os dados da planilha anexa aqui
    st.session_state.dados[periodo_atual] = pd.DataFrame(columns=list("ABCDEFGHIJKLMNO"))

df_mes = st.session_state.dados[periodo_atual]

# Editor de Dados
st.subheader(f"Lançamentos de {mes} de {ano}")
column_config = {
    "A": st.column_config.TextColumn(st.session_state.apelidos["A"]),
    "B": st.column_config.TextColumn(st.session_state.apelidos["B"], disabled=True),
    "C": st.column_config.TextColumn(st.session_state.apelidos["C"]),
    "D": st.column_config.TextColumn(st.session_state.apelidos["D"]),
    "E": st.column_config.TextColumn(st.session_state.apelidos["E"]),
    "F": st.column_config.NumberColumn(st.session_state.apelidos["F"], format="R$ %.2f"),
    "G": st.column_config.NumberColumn(st.session_state.apelidos["G"], format="R$ %.2f"),
    "H": st.column_config.NumberColumn(st.session_state.apelidos["H"], format="R$ %.2f"),
    "I": st.column_config.NumberColumn(st.session_state.apelidos["I"], format="R$ %.2f", disabled=True),
    "J": st.column_config.NumberColumn(st.session_state.apelidos["J"], format="R$ %.2f", disabled=True),
    "K": st.column_config.NumberColumn(st.session_state.apelidos["K"], format="R$ %.2f", disabled=True),
    "L": st.column_config.NumberColumn(st.session_state.apelidos["L"], format="R$ %.2f", disabled=True),
    "M": st.column_config.NumberColumn(st.session_state.apelidos["M"], format="R$ %.2f", disabled=True),
    "N": st.column_config.NumberColumn(st.session_state.apelidos["N"], format="R$ %.2f"),
    "O": st.column_config.NumberColumn(st.session_state.apelidos["O"], format="R$ %.2f", disabled=True),
}

df_editado = st.data_editor(
    df_mes,
    column_config=column_config,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key=f"editor_{periodo_atual}"
)

# Salvar e Recalcular
if st.button("💾 Salvar e Calcular"):
    df_calculado = calcular_colunas(df_editado)
    st.session_state.dados[periodo_atual] = df_calculado
    st.success("Cálculos atualizados!")
    st.rerun()

# --- FECHAR MÊS (TRANSPORTE) ---
if st.sidebar.button("🔒 Fechar Mês e Transportar Saldo"):
    # Calcular próximo mês
    meses_lista = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    idx_atual = meses_lista.index(mes)
    if idx_atual == 11:
        prox_periodo = f"{ano+1}-{meses_lista[0]}"
    else:
        prox_periodo = f"{ano}-{meses_lista[idx_atual+1]}"
    
    df_atual = calcular_colunas(st.session_state.dados[periodo_atual])
    
    # Criar ou obter próximo mês
    df_prox = st.session_state.dados.get(prox_periodo, pd.DataFrame(columns=list("ABCDEFGHIJKLMNO")))
    
    # Transporte linha a linha
    for _, row in df_atual.iterrows():
        cartao = str(row["A"])
        saldo_final = row["O"]
        
        # Verifica se o cartão já existe no próximo mês
        mask = df_prox["A"].astype(str) == cartao
        if mask.any():
            df_prox.loc[mask, "I"] = saldo_final
        else:
            # Adiciona nova linha com dados de identificação e saldo inicial
            nova_linha = {letra: row[letra] for letra in "ABCDE"}
            nova_linha.update({letra: 0 for letra in "FGHJKLMNO"})
            nova_linha["I"] = saldo_final
            df_prox = pd.concat([df_prox, pd.DataFrame([nova_linha])], ignore_index=True)
    
    st.session_state.dados[prox_periodo] = calcular_colunas(df_prox)
    st.sidebar.success(f"Saldo transportado para {prox_periodo}!")

# Resumo Financeiro
st.divider()
st.subheader("📊 Resumo do Mês")
df_res = st.session_state.dados[periodo_atual]
if not df_res.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Autorizado (G)", f"R$ {df_res['G'].sum():,.2f}")
    c2.metric("Total Fatura (H)", f"R$ {df_res['H'].sum():,.2f}")
    c3.metric("Saldo Final (O)", f"R$ {df_res['O'].sum():,.2f}")

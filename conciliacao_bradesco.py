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
        "G": "Aprovado Reunião", "H": "Valor Fatura", "I": "Saldo Anterior",
        "J": "Diferença a Pagar", "K": "Diferença a Receber", "L": "Saldo Final Ajustado",
        "M": "Saldo Próxima Reunião", "N": "Pós-Fechamento", "O": "Saldo Final do Mês"
    }

# --- FUNÇÕES DE APOIO ---
def calcular_colunas(df):
    """Aplica as fórmulas lógicas do sistema nas colunas A-O"""
    df = df.copy()
    # Garantir que colunas numéricas sejam tratadas corretamente
    cols_numericas = ["F", "G", "H", "I", "J", "K", "L", "M", "N", "O"]
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    # B: Últimos 7 dígitos do cartão (Dado cadastral automático)
    if "A" in df.columns:
        df["B"] = df["A"].astype(str).apply(lambda x: x[-7:] if len(x) >= 7 else x)
    
    # J: Diferença a Pagar (se H > G => J = H - G, senão 0)
    df["J"] = np.where(df["H"] > df["G"], df["H"] - df["G"], 0.0)
    
    # K: Diferença a Receber (se H < G => K = G - H, senão 0)
    df["K"] = np.where(df["H"] < df["G"], df["G"] - df["H"], 0.0)
    
    # L: Saldo Final Ajustado (I + J - K)
    df["L"] = df["I"] + df["J"] - df["K"]
    
    # M: Saldo Próxima Reunião (G + L - H)
    df["M"] = df["G"] + df["L"] - df["H"]
    
    # O: Saldo Final do Mês (G + L - N)
    df["O"] = df["G"] + df["L"] - df["N"]
    
    return df

# --- INTERFACE ---
st.title("🏦 Sistema de Conciliação Bradesco")

with st.sidebar:
    st.header("📅 Período de Trabalho")
    ano = st.selectbox("Ano", range(2024, 2031), index=2)
    meses_lista = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes = st.selectbox("Mês", meses_lista, index=datetime.now().month - 1)
    periodo_atual = f"{ano}-{mes}"
    
    st.divider()
    
    # --- MELHORIA 1: IMPORTAÇÃO DE PLANILHA PADRÃO ---
    st.header("📥 Importar Dados")
    arquivo_upload = st.file_uploader("Carregar planilha inicial (.xlsx ou .csv)", type=["xlsx", "csv"])
    
    if arquivo_upload is not None:
        if st.button("Confirmar Importação"):
            try:
                if arquivo_upload.name.endswith('.csv'):
                    df_importado = pd.read_csv(arquivo_upload)
                else:
                    df_importado = pd.read_excel(arquivo_upload)
                
                # Garantir que o DF importado tenha as colunas necessárias (A-O)
                # Se a planilha vier apenas com dados cadastrais (A-F), preenchemos o resto
                for letra in "ABCDEFGHIJKLMNO":
                    if letra not in df_importado.columns:
                        df_importado[letra] = 0.0
                
                st.session_state.dados[periodo_atual] = calcular_colunas(df_importado[list("ABCDEFGHIJKLMNO")])
                st.success("Dados importados com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao importar: {e}")

    st.divider()
    st.header("🏷️ Personalizar Colunas")
    with st.expander("Editar Nomes das Colunas"):
        for letra in "ABCDEFGHIJKLMNO":
            st.session_state.apelidos[letra] = st.text_input(f"Coluna {letra}", st.session_state.apelidos[letra], key=f"label_{letra}")

# Inicializar DataFrame do mês se não existir
if periodo_atual not in st.session_state.dados:
    st.session_state.dados[periodo_atual] = pd.DataFrame(columns=list("ABCDEFGHIJKLMNO"))

df_mes = st.session_state.dados[periodo_atual]

# Configuração do Editor
st.subheader(f"Lançamentos: {mes} / {ano}")

column_config = {
    "A": st.column_config.TextColumn(st.session_state.apelidos["A"]),
    "B": st.column_config.TextColumn(st.session_state.apelidos["B"], disabled=True),
    "C": st.column_config.TextColumn(st.session_state.apelidos["C"]),
    "D": st.column_config.TextColumn(st.session_state.apelidos["D"]),
    "E": st.column_config.TextColumn(st.session_state.apelidos["E"]),
    "F": st.column_config.NumberColumn(st.session_state.apelidos["F"], format="R$ %.2f"),
    "G": st.column_config.NumberColumn(st.session_state.apelidos["G"], format="R$ %.2f"),
    "H": st.column_config.NumberColumn(st.session_state.apelidos["H"], format="R$ %.2f"),
    "I": st.column_config.NumberColumn(st.session_state.apelidos["I"], format="R$ %.2f"), # Saldo Anterior
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

# Botões de Ação
col_btn1, col_btn2 = st.columns([1, 5])

with col_btn1:
    if st.button("💾 Salvar e Calcular"):
        df_calculado = calcular_colunas(df_editado)
        st.session_state.dados[periodo_atual] = df_calculado
        st.success("Dados salvos!")
        st.rerun()

# --- MELHORIA 2: TRANSPORTE DE SALDO (O -> I) ---
with st.sidebar:
    st.divider()
    if st.button("🔒 Fechar Mês e Transportar Saldo"):
        # 1. Salvar mês atual primeiro
        df_atual_finalizado = calcular_colunas(df_editado)
        st.session_state.dados[periodo_atual] = df_atual_finalizado
        
        # 2. Calcular qual é o próximo mês
        idx_atual = meses_lista.index(mes)
        if idx_atual == 11: # Dezembro
            prox_periodo = f"{ano+1}-{meses_lista[0]}"
        else:
            prox_periodo = f"{ano}-{meses_lista[idx_atual+1]}"
        
        # 3. Preparar DataFrame do próximo mês
        # Pegamos os dados cadastrais (A-F) do mês atual para o próximo
        df_proximo = df_atual_finalizado[["A", "B", "C", "D", "E", "F"]].copy()
        
        # O pulo do gato: Coluna I do próximo recebe Coluna O do atual
        df_proximo["I"] = df_atual_finalizado["O"]
        
        # Inicializar as outras colunas de entrada manual como zero
        for col in ["G", "H", "N"]:
            df_proximo[col] = 0.0
            
        # Calcular as fórmulas para o próximo mês (J, K, L, M, O)
        df_proximo = calcular_colunas(df_proximo)
        
        # Salvar no estado
        st.session_state.dados[prox_periodo] = df_proximo
        
        st.sidebar.success(f"Mês fechado! Saldo transportado para {prox_periodo}")
        st.info(f"Mude o seletor de período para '{prox_periodo}' para ver os dados transportados.")

# Resumo Financeiro
if not st.session_state.dados[periodo_atual].empty:
    st.divider()
    st.subheader("📊 Resumo Consolidado")
    df_res = st.session_state.dados[periodo_atual]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Reunião (G)", f"R$ {df_res['G'].sum():,.2f}")
    c2.metric("Total Faturas (H)", f"R$ {df_res['H'].sum():,.2f}")
    c3.metric("Saldo Anterior (I)", f"R$ {df_res['I'].sum():,.2f}")
    c4.metric("Saldo Final (O)", f"R$ {df_res['O'].sum():,.2f}")

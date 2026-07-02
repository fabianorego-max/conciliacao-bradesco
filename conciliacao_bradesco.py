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
import json
import os
from datetime import datetime

# =============================================================================
# Configurações e Constantes
# =============================================================================
DATA_FILE = "bradesco_conciliacao.json"
APELIDOS_FILE = "bradesco_apelidos.json"

ALL_COLS = [
    "A_Cartao", "B_Bandeira", "C_Titular", "D_Categoria", "E_Status",
    "F_Compras", "G_Pagamentos", "H_Taxas", "I_SaldoInicial",
    "J_TotalDebito", "K_AposPagamento", "L_ComTaxas",
    "M_PagMinimo", "N_SaldoDevedor", "O_SaldoFinal",
]

LABELS = {
    "A_Cartao": "A - Cartão",
    "B_Bandeira": "B - Bandeira",
    "C_Titular": "C - Titular",
    "D_Categoria": "D - Categoria",
    "E_Status": "E - Status",
    "F_Compras": "F - Compras",
    "G_Pagamentos": "G - Pagamentos",
    "H_Taxas": "H - Taxas",
    "I_SaldoInicial": "I - Saldo Inicial",
    "J_TotalDebito": "J - Total Débito",
    "K_AposPagamento": "K - Após Pagamento",
    "L_ComTaxas": "L - Com Taxas",
    "M_PagMinimo": "M - Pag. Mínimo",
    "N_SaldoDevedor": "N - Saldo Devedor",
    "O_SaldoFinal": "O - Saldo Final",
}

ALPHA_COLS = ["A_Cartao", "B_Bandeira", "C_Titular", "D_Categoria", "E_Status"]
NUM_MANUAL_COLS = ["F_Compras", "G_Pagamentos", "H_Taxas", "I_SaldoInicial"]
CALC_COLS = [
    "J_TotalDebito", "K_AposPagamento", "L_ComTaxas",
    "M_PagMinimo", "N_SaldoDevedor", "O_SaldoFinal",
]
NUMERIC_COLS = NUM_MANUAL_COLS + CALC_COLS

MES_NAMES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

ANOS = list(range(2020, datetime.now().year + 5))


# =============================================================================
# Persistência
# =============================================================================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_apelidos():
    if os.path.exists(APELIDOS_FILE):
        with open(APELIDOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_apelidos(apelidos):
    with open(APELIDOS_FILE, "w", encoding="utf-8") as f:
        json.dump(apelidos, f, ensure_ascii=False, indent=2)


# =============================================================================
# Utilidades de Mês
# =============================================================================
def month_key(ano, mes):
    return f"{int(ano):04d}-{int(mes):02d}"


def next_month(ano, mes):
    mes = int(mes)
    ano = int(ano)
    if mes == 12:
        return ano + 1, 1
    return ano, mes + 1


def get_month_df(data, ano, mes):
    key = month_key(ano, mes)
    if key in data and data[key]:
        df = pd.DataFrame(data[key])
        for col in ALL_COLS:
            if col not in df.columns:
                df[col] = "" if col in ALPHA_COLS else 0
        return df[ALL_COLS].copy()
    return pd.DataFrame(columns=ALL_COLS)


# =============================================================================
# Cálculos Automáticos (J a O)
# =============================================================================
def calculate_columns(df):
    df = df.copy()
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # J = Saldo Inicial + Compras
    df["J_TotalDebito"] = df["I_SaldoInicial"] + df["F_Compras"]

    # K = Total Débito - Pagamentos
    df["K_AposPagamento"] = df["J_TotalDebito"] - df["G_Pagamentos"]

    # L = Após Pagamento + Taxas
    df["L_ComTaxas"] = df["K_AposPagamento"] + df["H_Taxas"]

    # M = Pagamento Mínimo (15% do saldo com taxas)
    df["M_PagMinimo"] = (df["L_ComTaxas"] * 0.15).round(2)

    # N = Saldo Devedor (igual ao saldo com taxas)
    df["N_SaldoDevedor"] = df["L_ComTaxas"]

    # O = Saldo Final (transportado no Fechar Mês)
    df["O_SaldoFinal"] = df["N_SaldoDevedor"]

    return df


# =============================================================================
# Fechar Mês – Transporte linha a linha, cartão a cartão
# =============================================================================
def fechar_mes(data, ano, mes):
    ano = int(ano)
    mes = int(mes)
    key_atual = month_key(ano, mes)

    if key_atual not in data or not data[key_atual]:
        return False, "O mês atual não possui dados para fechar."

    df_atual = get_month_df(data, ano, mes)
    df_atual = calculate_columns(df_atual)

    prox_ano, prox_mes = next_month(ano, mes)
    key_prox = month_key(prox_ano, prox_mes)

    df_prox = get_month_df(data, prox_ano, prox_mes)
    prox_rows = df_prox.to_dict("records")

    # Índice por (Cartão, Titular) para casar linhas
    prox_index = {}
    for idx, row in enumerate(prox_rows):
        match_key = (
            str(row.get("A_Cartao", "")).strip(),
            str(row.get("C_Titular", "")).strip(),
        )
        prox_index[match_key] = idx

    transportes = 0

    for _, row_atual in df_atual.iterrows():
        cartao = str(row_atual.get("A_Cartao", "")).strip()
        titular = str(row_atual.get("C_Titular", "")).strip()
        match_key = (cartao, titular)

        saldo_final = pd.to_numeric(
            row_atual.get("O_SaldoFinal", 0), errors="coerce"
        )
        if pd.isna(saldo_final):
            saldo_final = 0.0
        saldo_final = float(saldo_final)

        if match_key in prox_index:
            idx = prox_index[match_key]
            prox_rows[idx]["I_SaldoInicial"] = saldo_final
            # Preservar identificação
            prox_rows[idx]["A_Cartao"] = cartao
            prox_rows[idx]["B_Bandeira"] = row_atual.get("B_Bandeira", "")
            prox_rows[idx]["C_Titular"] = titular
            prox_rows[idx]["D_Categoria"] = row_atual.get("D_Categoria", "")
            prox_rows[idx]["E_Status"] = row_atual.get("E_Status", "")
        else:
            new_row = {col: "" if col in ALPHA_COLS else 0 for col in ALL_COLS}
            new_row["A_Cartao"] = cartao
            new_row["B_Bandeira"] = row_atual.get("B_Bandeira", "")
            new_row["C_Titular"] = titular
            new_row["D_Categoria"] = row_atual.get("D_Categoria", "")
            new_row["E_Status"] = row_atual.get("E_Status", "")
            new_row["I_SaldoInicial"] = saldo_final
            prox_rows.append(new_row)
            prox_index[match_key] = len(prox_rows) - 1

        transportes += 1

    # Reconstruir DataFrame e recalcular J a O imediatamente
    df_prox = pd.DataFrame(prox_rows, columns=ALL_COLS)
    df_prox = calculate_columns(df_prox)

    data[key_prox] = df_prox.to_dict("records")
    save_data(data)

    msg = (
        f"Mês fechado com sucesso! {transportes} transporte(s) realizado(s) "
        f"linha a linha para {MES_NAMES[prox_mes - 1]} {prox_ano}. "
        f"Cálculos J–O aplicados automaticamente."
    )
    return True, msg


# =============================================================================
# Aplicação Streamlit
# =============================================================================
def main():
    st.set_page_config(
        page_title="Conciliação Bradesco",
        page_icon="💳",
        layout="wide",
    )
    st.title("💳 Conciliação Bradesco – Cartões")

    # -----------------------------------------------------------------
    # Inicialização de session state
    # -----------------------------------------------------------------
    if "data" not in st.session_state:
        st.session_state.data = load_data()
    if "apelidos" not in st.session_state:
        st.session_state.apelidos = load_apelidos()
    if "selected_ano" not in st.session_state:
        st.session_state.selected_ano = datetime.now().year
    if "selected_mes" not in st.session_state:
        st.session_state.selected_mes = datetime.now().month
    if "fechar_msg" not in st.session_state:
        st.session_state.fechar_msg = None
    if "fechar_erro" not in st.session_state:
        st.session_state.fechar_erro = None

    data = st.session_state.data
    apelidos = st.session_state.apelidos

    # -----------------------------------------------------------------
    # Sidebar – Ano/Mês e Apelidos
    # -----------------------------------------------------------------
    with st.sidebar:
        st.header("📅 Seleção de Período")
        ano = st.selectbox("Ano", ANOS, index=ANOS.index(st.session_state.selected_ano))
        mes = st.selectbox(
            "Mês",
            list(range(1, 13)),
            format_func=lambda m: MES_NAMES[m - 1],
            index=st.session_state.selected_mes - 1,
        )
        st.session_state.selected_ano = ano
        st.session_state.selected_mes = mes

        st.divider()
        st.header("🏷️ Apelidos")
        with st.expander("Configurar Apelidos", expanded=False):
            apelido_cartao = st.text_input("Apelido para Cartão (Coluna A)")
            apelido_titular = st.text_input("Apelido para Titular (Coluna C)")
            if st.button("Salvar Apelido"):
                if apelido_cartao:
                    apelidos["cartao"] = apelido_cartao
                if apelido_titular:
                    apelidos["titular"] = apelido_titular
                st.session_state.apelidos = apelidos
                save_apelidos(apelidos)
                st.success("Apelido(s) salvo(s)!")

            if apelidos:
                st.write("**Apelidos atuais:**")
                for k, v in apelidos.items():
                    st.write(f"- {k.capitalize()}: {v}")

        st.divider()
        st.header("🔒 Fechar Mês")
        st.write(
            f"Transporta o saldo (Coluna O) de cada linha de "
            f"**{MES_NAMES[mes - 1]} {ano}** para a Coluna I do próximo mês, "
            f"linha a linha, cartão a cartão."
        )
        if st.button("Fechar Mês", type="primary"):
            ok, msg = fechar_mes(data, ano, mes)
            if ok:
                st.session_state.fechar_msg = msg
                st.session_state.fechar_erro = None
                st.session_state.data = load_data()
            else:
                st.session_state.fechar_erro = msg
                st.session_state.fechar_msg = None

    # -----------------------------------------------------------------
    # Mensagens de feedback
    # -----------------------------------------------------------------
    if st.session_state.fechar_msg:
        st.success(st.session_state.fechar_msg)
        st.session_state.fechar_msg = None
    if st.session_state.fechar_erro:
        st.error(st.session_state.fechar_erro)
        st.session_state.fechar_erro = None

    # -----------------------------------------------------------------
    # Tabela principal
    # -----------------------------------------------------------------
    st.subheader(f"Conciliação – {MES_NAMES[mes - 1]} {ano}")

    df = get_month_df(data, ano, mes)

    # Aplicar apelidos nos rótulos se configurados
    display_labels = dict(LABELS)
    if "cartao" in apelidos:
        display_labels["A_Cartao"] = f"A - {apelidos['cartao']}"
    if "titular" in apelidos:
        display_labels["C_Titular"] = f"C - {apelidos['titular']}"

    # Configuração de colunas para o data_editor
    column_config = {}
    for col in ALL_COLS:
        if col in ALPHA_COLS:
            column_config[col] = st.column_config.TextColumn(display_labels[col], width="medium")
        elif col in NUM_MANUAL_COLS:
            column_config[col] = st.column_config.NumberColumn(
                display_labels[col],
                format="%.2f",
                width="medium",
            )
        else:
            column_config[col] = st.column_config.NumberColumn(
                display_labels[col],
                format="%.2f",
                width="medium",
                disabled=True,
            )

    # Garantir que colunas calculadas estejam preenchidas
    if not df.empty:
        df = calculate_columns(df)

    edited = st.data_editor(
        df,
        column_config=column_config,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_{ano}_{mes}",
        hide_index=True,
    )

    # -----------------------------------------------------------------
    # Salvar alterações
    # -----------------------------------------------------------------
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])

    with col_btn1:
        if st.button("💾 Salvar"):
            # Recalcular J a O antes de salvar
            edited_calc = calculate_columns(edited)
            key = month_key(ano, mes)
            data[key] = edited_calc.to_dict("records")
            st.session_state.data = data
            save_data(data)
            st.success("Dados salvos e cálculos atualizados!")
            st.rerun()

    with col_btn2:
        if st.button("🔄 Recalcular"):
            st.rerun()

    # -----------------------------------------------------------------
    # Resumo
    # -----------------------------------------------------------------
    if not edited.empty:
        st.divider()
        st.subheader("📊 Resumo do Mês")
        edited_calc = calculate_columns(edited)
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        with col_r1:
            st.metric("Total Compras (F)", f"R$ {edited_calc['F_Compras'].sum():.2f}")
        with col_r2:
            st.metric("Total Pagamentos (G)", f"R$ {edited_calc['G_Pagamentos'].sum():.2f}")
        with col_r3:
            st.metric("Total Taxas (H)", f"R$ {edited_calc['H_Taxas'].sum():.2f}")
        with col_r4:
            st.metric("Saldo Final Total (O)", f"R$ {edited_calc['O_SaldoFinal'].sum():.2f}")

        st.write("**Saldo por Cartão:**")
        resumo = (
            edited_calc.groupby(["A_Cartao", "C_Titular"], dropna=False)
            .agg(
                Compras=("F_Compras", "sum"),
                Pagamentos=("G_Pagamentos", "sum"),
                Taxas=("H_Taxas", "sum"),
                Saldo_Final=("O_SaldoFinal", "sum"),
            )
            .reset_index()
        )
        st.dataframe(resumo, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()

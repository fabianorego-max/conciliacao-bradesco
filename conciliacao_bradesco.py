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
import calendar
from datetime import date
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Conciliação Bradesco", layout="wide")

MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

COLUNAS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O"]
COLUNAS_EDITAVEIS = ["A", "B", "C", "D", "E", "F"]


def chave_periodo(ano: int, mes: int) -> str:
    return f"{ano:04d}-{mes:02d}"


def proximo_periodo(ano: int, mes: int) -> tuple[int, int]:
    if mes == 12:
        return ano + 1, 1
    return ano, mes + 1


def criar_dataframe_vazio() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUNAS)


def obter_periodo_atual(ano: int, mes: int) -> pd.DataFrame:
    chave = chave_periodo(ano, mes)
    if "historico" not in st.session_state:
        st.session_state.historico = {}
    if chave not in st.session_state.historico:
        st.session_state.historico[chave] = criar_dataframe_vazio()
    return st.session_state.historico[chave]


def recalcular_automaticos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["J", "K", "L", "M", "N", "O"]:
        if col not in df.columns:
            df[col] = 0.0

    def to_num(valor):
        if pd.isna(valor):
            return 0.0
        try:
            return float(str(valor).replace(".", "").replace(",", "."))
        except (ValueError, TypeError):
            return 0.0

    for idx in df.index:
        a = to_num(df.at[idx, "A"])
        b = to_num(df.at[idx, "B"])
        c = to_num(df.at[idx, "C"])
        d = to_num(df.at[idx, "D"])
        e = to_num(df.at[idx, "E"])
        f = to_num(df.at[idx, "F"])
        i = to_num(df.at[idx, "I"])

        df.at[idx, "J"] = a + b
        df.at[idx, "K"] = c + d
        df.at[idx, "L"] = e + f
        df.at[idx, "M"] = df.at[idx, "J"] - df.at[idx, "K"]
        df.at[idx, "N"] = df.at[idx, "M"] + i
        df.at[idx, "O"] = df.at[idx, "N"] + df.at[idx, "L"]

    return df


def fechar_mes(ano: int, mes: int) -> tuple[int, int]:
    df_atual = obter_periodo_atual(ano, mes)
    df_atual = recalcular_automaticos(df_atual)
    st.session_state.historico[chave_periodo(ano, mes)] = df_atual

    prox_ano, prox_mes = proximo_periodo(ano, mes)
    df_prox = obter_periodo_atual(prox_ano, prox_mes)

    saldo_transportar = 0.0
    if not df_atual.empty and "O" in df_atual.columns:
        saldo_transportar = float(pd.to_numeric(df_atual["O"], errors="coerce").fillna(0).sum())

    nova_linha = {col: "" for col in COLUNAS}
    nova_linha["I"] = saldo_transportar
    df_prox = pd.concat([df_prox, pd.DataFrame([nova_linha])], ignore_index=True)
    df_prox = recalcular_automaticos(df_prox)
    st.session_state.historico[chave_periodo(prox_ano, prox_mes)] = df_prox

    return prox_ano, prox_mes, saldo_transportar


def main() -> None:
    st.title("Conciliação Bradesco")

    with st.sidebar:
        st.header("Controle de Período")
        anos_disponiveis = list(range(2024, 2031))
        ano = st.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(2026))
        mes = st.selectbox("Mês", list(MESES.keys()),
                           format_func=lambda m: MESES[m],
                           index=6)
        st.divider()
        st.markdown(f"**Período ativo:** {MESES[mes]} {ano}")
        st.caption(f"Chave: {chave_periodo(ano, mes)}")

    df_periodo = obter_periodo_atual(ano, mes)

    st.subheader(f"Lançamentos - {MESES[mes]} {ano}")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.data_editor(
            df_periodo,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{chave_periodo(ano, mes)}",
            column_config={
                col: st.column_config.NumberColumn(format="%.2f")
                for col in COLUNAS
            },
            disabled=[col for col in COLUNAS if col not in COLUNAS_EDITAVEIS],
        )
    with col2:
        st.markdown("**Resumo**")
        if not df_periodo.empty:
            df_calc = recalcular_automaticos(df_periodo)
            st.metric("Total Coluna O", f"{pd.to_numeric(df_calc['O'], errors='coerce').fillna(0).sum():.2f}")
            st.metric("Total Coluna I", f"{pd.to_numeric(df_calc['I'], errors='coerce').fillna(0).sum():.2f}")
        else:
            st.info("Sem lançamentos no período.")

    st.divider()
    st.subheader("Ações do Período")

    if st.button("Salvar lançamentos do mês"):
        editor_state = st.session_state.get(f"editor_{chave_periodo(ano, mes)}", None)
        if editor_state is not None and "edited_rows" in editor_state:
            df_editado = df_periodo.copy()
            for row_idx, changes in editor_state["edited_rows"].items():
                real_idx = list(df_editado.index)[row_idx] if row_idx < len(df_editado.index) else row_idx
                for col, valor in changes.items():
                    df_editado.at[real_idx, col] = valor
            df_editado = recalcular_automaticos(df_editado)
            st.session_state.historico[chave_periodo(ano, mes)] = df_editado
            st.success("Lançamentos salvos e colunas J a O recalculadas.")
        else:
            df_editado = recalcular_automaticos(df_periodo)
            st.session_state.historico[chave_periodo(ano, mes)] = df_editado
            st.success("Nenhuma alteração manual detectada. Cálculos atualizados.")
        st.rerun()

    if st.button("Fechar Mês"):
        prox_ano, prox_mes, saldo = fechar_mes(ano, mes)
        st.success(
            f"Mês fechado! Saldo de {saldo:.2f} transportado da Coluna O "
            f"para a Coluna I de {MESES[prox_mes]} {prox_ano} "
            f"({chave_periodo(prox_ano, prox_mes)})."
        )
        st.info("Selecione o próximo mês na barra lateral para visualizar o saldo transportado.")

    st.divider()
    with st.expander("Períodos armazenados em memória", expanded=False):
        if st.session_state.get("historico"):
            resumo = []
            for chave, df in st.session_state.historico.items():
                resumo.append({
                    "Período": chave,
                    "Linhas": len(df),
                    "Total O": float(pd.to_numeric(df.get("O", []), errors="coerce").fillna(0).sum())
                    if not df.empty else 0.0,
                })
            st.dataframe(pd.DataFrame(resumo), use_container_width=True)
        else:
            st.write("Nenhum período armazenado ainda.")


if __name__ == "__main__":
    main()

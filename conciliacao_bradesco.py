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
import io


def inicializar_session_state():
    """Inicializa as variáveis de sessão utilizadas pela conciliação Bradesco."""
    if "df_conciliacao" not in st.session_state:
        st.session_state.df_conciliacao = pd.DataFrame()


def processar_dados():
    """
    Processa o DataFrame de conciliação calculando as colunas J a O.
    As colunas calculadas dependem das colunas A-I previamente carregadas.
    """
    df = st.session_state.df_conciliacao

    if df is None or df.empty:
        return

    colunas = list(df.columns)

    # Mapeia as colunas A-I por posição (índices 0 a 8)
    if len(colunas) < 9:
        st.warning("O arquivo enviado não possui colunas suficientes (A até I) para processamento.")
        return

    col_a = colunas[0]
    col_b = colunas[1]
    col_c = colunas[2]
    col_d = colunas[3]
    col_e = colunas[4]
    col_f = colunas[5]
    col_g = colunas[6]
    col_h = colunas[7]
    col_i = colunas[8]

    # J: Diferença entre F e G
    df[colunas[8 + 1] if len(colunas) > 9 else "J_Diferenca_F_G"] = (
        pd.to_numeric(df[col_f], errors="coerce") - pd.to_numeric(df[col_g], errors="coerce")
    ) if len(colunas) <= 9 else df[colunas[9]]

    # Garante nomes estáveis para as colunas calculadas J a O
    nomes_calculados = {
        "J_Diferenca_F_G": pd.to_numeric(df[col_f], errors="coerce") - pd.to_numeric(df[col_g], errors="coerce"),
        "K_Soma_H_I": pd.to_numeric(df[col_h], errors="coerce") + pd.to_numeric(df[col_i], errors="coerce"),
        "L_Status": np.where(
            (pd.to_numeric(df[col_f], errors="coerce") - pd.to_numeric(df[col_g], errors="coerce")).abs() < 0.01,
            "Conciliado",
            "Divergente",
        ),
        "M_Valor_Absoluto": (pd.to_numeric(df[col_f], errors="coerce") - pd.to_numeric(df[col_g], errors="coerce")).abs(),
        "N_Indicador": np.where(pd.to_numeric(df[col_f], errors="coerce") > 0, "Positivo", "Negativo"),
        "O_Observacao": "",
    }

    for nome, valor in nomes_calculados.items():
        df[nome] = valor

    st.session_state.df_conciliacao = df


def converter_tipos(df):
    """
    Converte as colunas A-E para string e as colunas F-I para numérico.
    """
    if df is None or df.empty:
        return df

    colunas = list(df.columns)

    # Colunas A-E (índices 0 a 4) -> string
    for idx in range(min(5, len(colunas))):
        df[colunas[idx]] = df[colunas[idx]].astype(str).str.strip()

    # Colunas F-I (índices 5 a 8) -> numérico
    for idx in range(5, min(9, len(colunas))):
        df[colunas[idx]] = pd.to_numeric(df[colunas[idx]], errors="coerce")

    return df


def carregar_arquivo(arquivo):
    """
    Lê o arquivo enviado (Excel ou CSV) e retorna um DataFrame.
    """
    nome = arquivo.name.lower()

    if nome.endswith(".csv"):
        # Tenta diferentes separadores comuns
        try:
            df = pd.read_csv(arquivo, sep=";", encoding="utf-8")
        except Exception:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, sep=",", encoding="utf-8")
    elif nome.endswith(".xlsx") or nome.endswith(".xls"):
        df = pd.read_excel(arquivo)
    else:
        st.error("Formato de arquivo não suportado. Envie um arquivo .csv, .xlsx ou .xls")
        return None

    return df


def main():
    st.set_page_config(page_title="Conciliação Bradesco", layout="wide")
    st.title("Conciliação Bradesco")

    inicializar_session_state()

    # Upload do arquivo
    st.subheader("Upload do arquivo de conciliação")
    arquivo = st.file_uploader(
        "Selecione um arquivo Excel ou CSV",
        type=["csv", "xlsx", "xls"],
        key="upload_conciliacao",
    )

    if arquivo is not None:
        try:
            df = carregar_arquivo(arquivo)

            if df is not None and not df.empty:
                # 1. Converte os tipos imediatamente após a leitura
                df = converter_tipos(df)

                # 2. Salva o DataFrame no session_state
                st.session_state.df_conciliacao = df

                # 3. Processa as colunas calculadas (J a O)
                processar_dados()

                st.success("Arquivo carregado e processado com sucesso!")
            else:
                st.warning("O arquivo enviado está vazio ou não pôde ser lido.")
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")

    # Tabela editável utilizando o session_state como fonte de dados
    st.subheader("Tabela editável de conciliação")

    if not st.session_state.df_conciliacao.empty:
        st.data_editor(
            st.session_state.df_conciliacao,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_conciliacao",
        )
    else:
        st.info("Nenhum dado carregado. Envie um arquivo para visualizar a conciliação.")


if __name__ == "__main__":
    main()

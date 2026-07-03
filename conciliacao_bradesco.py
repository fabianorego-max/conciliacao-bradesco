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
st.title("Bradesco Conciliação")

# -----------------------------------------------------------------------------
# Definição da estrutura A-O
# -----------------------------------------------------------------------------
COLUNAS_ORIGINAIS = [
    "A_Cartao",
    "B_Resumo",
    "C_Titular",
    "D_CPF",
    "E_Localidade",
    "F_Limite",
    "G_Aprovado_Reuniao",
    "H_Valor_Fatura",
    "I_Saldo_Anterior",
    "J_Diferenca_Pagar",
    "K_Diferenca_Receber",
    "L_Saldo_Final_Ajustado",
    "M_Saldo_Proxima_Reuniao",
    "N_Pos_Fechamento",
    "O_Saldo_Final_Mes",
]

COLUNAS_NUMERICAS = [
    "F_Limite",
    "G_Aprovado_Reuniao",
    "H_Valor_Fatura",
    "I_Saldo_Anterior",
    "J_Diferenca_Pagar",
    "K_Diferenca_Receber",
    "L_Saldo_Final_Ajustado",
    "M_Saldo_Proxima_Reuniao",
    "N_Pos_Fechamento",
    "O_Saldo_Final_Mes",
]

COLUNAS_CALCULADAS = [
    "J_Diferenca_Pagar",
    "K_Diferenca_Receber",
    "L_Saldo_Final_Ajustado",
    "M_Saldo_Proxima_Reuniao",
    "O_Saldo_Final_Mes",
]

NOMES_PADRAO = {
    "A_Cartao": "A) Cartão",
    "B_Resumo": "B) Resumo 7 dígitos",
    "C_Titular": "C) Titular",
    "D_CPF": "D) CPF",
    "E_Localidade": "E) Localidade",
    "F_Limite": "F) Limite",
    "G_Aprovado_Reuniao": "G) Aprovado Reunião",
    "H_Valor_Fatura": "H) Valor Fatura",
    "I_Saldo_Anterior": "I) Saldo Anterior",
    "J_Diferenca_Pagar": "J) Diferença a Pagar",
    "K_Diferenca_Receber": "K) Diferença a Receber",
    "L_Saldo_Final_Ajustado": "L) Saldo Final Ajustado",
    "M_Saldo_Proxima_Reuniao": "M) Saldo Próxima Reunião",
    "N_Pos_Fechamento": "N) Pós-Fechamento",
    "O_Saldo_Final_Mes": "O) Saldo Final do Mês",
}

# -----------------------------------------------------------------------------
# Inicialização do session_state
# -----------------------------------------------------------------------------
if "periodos" not in st.session_state:
    st.session_state.periodos = {}  # chave: "MM/YYYY" -> DataFrame

if "apelidos" not in st.session_state:
    st.session_state.apelidos = dict(NOMES_PADRAO)

if "periodo_atual" not in st.session_state:
    st.session_state.periodo_atual = None


def criar_df_vazio() -> pd.DataFrame:
    df = pd.DataFrame(columns=COLUNAS_ORIGINAIS)
    for col in COLUNAS_NUMERICAS:
        df[col] = df[col].astype(float)
    return df


def normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    """Garante que o DataFrame possua todas as colunas A-O e tipos corretos."""
    for col in COLUNAS_ORIGINAIS:
        if col not in df.columns:
            df[col] = 0.0 if col in COLUNAS_NUMERICAS else ""
    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
    for col in COLUNAS_ORIGINAIS:
        if col not in COLUNAS_NUMERICAS:
            df[col] = df[col].astype(str).fillna("")
    return df[COLUNAS_ORIGINAIS]


def recalcular(df: pd.DataFrame) -> pd.DataFrame:
    """Recalcula as colunas derivadas J, K, L, M, O."""
    df = df.copy()
    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    g = df["G_Aprovado_Reuniao"]
    h = df["H_Valor_Fatura"]
    i = df["I_Saldo_Anterior"]
    n = df["N_Pos_Fechamento"]

    df["J_Diferenca_Pagar"] = (h - g).where(h > g, 0.0)
    df["K_Diferenca_Receber"] = (g - h).where(g > h, 0.0)
    df["L_Saldo_Final_Ajustado"] = i + df["J_Diferenca_Pagar"] - df["K_Diferenca_Receber"]
    df["M_Saldo_Proxima_Reuniao"] = g + df["L_Saldo_Final_Ajustado"] - h
    df["O_Saldo_Final_Mes"] = g + df["L_Saldo_Final_Ajustado"] - n

    return df


def gerar_resumo(cartao: str) -> str:
    """Gera o resumo de 7 dígitos a partir do número do cartão (A)."""
    if not isinstance(cartao, str):
        cartao = str(cartao) if cartao is not None else ""
    digitos = "".join(ch for ch in cartao if ch.isdigit())
    if len(digitos) >= 7:
        return digitos[-7:]
    return digitos.zfill(7)


def nome_exibicao(col: str) -> str:
    return st.session_state.apelidos.get(col, NOMES_PADRAO.get(col, col))


def proximo_periodo(periodo: str) -> str:
    mes, ano = periodo.split("/")
    mes = int(mes)
    ano = int(ano)
    mes += 1
    if mes > 12:
        mes = 1
        ano += 1
    return f"{mes:02d}/{ano}"


# -----------------------------------------------------------------------------
# Sidebar: seletor de Mês/Ano e ações
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Período")

    meses = [
        "01", "02", "03", "04", "05", "06",
        "07", "08", "09", "10", "11", "12",
    ]
    anos = [str(a) for a in range(2020, 2036)]

    col_m, col_a = st.columns(2)
    with col_m:
        mes_sel = st.selectbox("Mês", meses, index=0)
    with col_a:
        ano_sel = st.selectbox("Ano", anos, index=len(anos) - 1)

    periodo_chave = f"{mes_sel}/{ano_sel}"

    if st.button("Abrir / Criar período", use_container_width=True):
        st.session_state.periodo_atual = periodo_chave
        if periodo_chave not in st.session_state.periodos:
            st.session_state.periodos[periodo_chave] = criar_df_vazio()
        st.rerun()

    st.divider()

    periodos_existentes = sorted(st.session_state.periodos.keys())
    if periodos_existentes:
        periodo_selecionado = st.selectbox(
            "Períodos cadastrados",
            periodos_existentes,
            index=periodos_existentes.index(st.session_state.periodo_atual)
            if st.session_state.periodo_atual in periodos_existentes
            else 0,
        )
        if st.button("Selecionar período", use_container_width=True):
            st.session_state.periodo_atual = periodo_selecionado
            st.rerun()

    st.divider()

    st.subheader("Renomear colunas")
    with st.form("form_apelidos"):
        novos_apelidos = {}
        for col in COLUNAS_ORIGINAIS:
            novos_apelidos[col] = st.text_input(
                NOMES_PADRAO[col],
                value=st.session_state.apelidos.get(col, NOMES_PADRAO[col]),
                key=f"apelido_{col}",
            )
        submitted = st.form_submit_button("Salvar apelidos")
        if submitted:
            st.session_state.apelidos = novos_apelidos
            st.success("Apelidos atualizados!")

    st.divider()

    st.subheader("Importar planilha")
    arquivo = st.file_uploader(
        "Selecione um arquivo Excel ou CSV",
        type=["xlsx", "xls", "csv"],
    )
    if arquivo is not None:
        try:
            if arquivo.name.lower().endswith(".csv"):
                df_import = pd.read_csv(arquivo, dtype=str)
            else:
                df_import = pd.read_excel(arquivo, dtype=str)

            # Mapeamento flexível: tenta casar nomes (case-insensitive, sem acentos)
            mapa_normalizado = {
                str(col).strip().lower().replace(" ", "_"): col
                for col in df_import.columns
            }
            df_map = pd.DataFrame()
            for col_orig in COLUNAS_ORIGINAIS:
                alvo = NOMES_PADRAO[col_orig].lower().replace(" ", "_")
                encontrado = None
                for chave, nome_real in mapa_normalizado.items():
                    if alvo in chave or chave in alvo:
                        encontrado = nome_real
                        break
                if encontrado is not None:
                    df_map[col_orig] = df_import[encontrado]
                else:
                    df_map[col_orig] = 0.0 if col_orig in COLUNAS_NUMERICAS else ""

            df_map = normalizar_df(df_map)
            df_map["B_Resumo"] = df_map["A_Cartao"].apply(gerar_resumo)
            df_map = recalcular(df_map)

            if st.session_state.periodo_atual is None:
                st.session_state.periodo_atual = periodo_chave
            if st.session_state.periodo_atual not in st.session_state.periodos:
                st.session_state.periodos[st.session_state.periodo_atual] = criar_df_vazio()

            st.session_state.periodos[st.session_state.periodo_atual] = df_map
            st.success(f"Importado em {st.session_state.periodo_atual}: {len(df_map)} linhas.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao importar: {e}")

    st.divider()

    st.subheader("Carry over")
    if st.button("Avançar para próximo mês", use_container_width=True):
        if st.session_state.periodo_atual is None:
            st.error("Selecione um período primeiro.")
        else:
            df_atual = st.session_state.periodos.get(
                st.session_state.periodo_atual, criar_df_vazio()
            )
            df_atual = recalcular(df_atual)
            prox = proximo_periodo(st.session_state.periodo_atual)

            df_prox = st.session_state.periodos.get(prox, criar_df_vazio()).copy()
            df_prox = normalizar_df(df_prox)

            # Preserva dados cadastrais (A-F) e copia O -> I do próximo período
            for idx, row in df_atual.iterrows():
                cartao = row["A_Cartao"]
                if not cartao:
                    continue
                mask = df_prox["A_Cartao"] == cartao
                if mask.any():
                    df_prox.loc[mask, "I_Saldo_Anterior"] = float(row["O_Saldo_Final_Mes"])
                    for col in ["A_Cartao", "B_Resumo", "C_Titular", "D_CPF",
                                "E_Localidade", "F_Limite"]:
                        df_prox.loc[mask, col] = row[col]
                else:
                    nova_linha = {col: "" for col in COLUNAS_ORIGINAIS}
                    nova_linha["A_Cartao"] = cartao
                    nova_linha["B_Resumo"] = gerar_resumo(cartao)
                    nova_linha["C_Titular"] = row["C_Titular"]
                    nova_linha["D_CPF"] = row["D_CPF"]
                    nova_linha["E_Localidade"] = row["E_Localidade"]
                    nova_linha["F_Limite"] = float(row["F_Limite"])
                    nova_linha["I_Saldo_Anterior"] = float(row["O_Saldo_Final_Mes"])
                    for col in COLUNAS_NUMERICAS:
                        if col not in nova_linha:
                            nova_linha[col] = 0.0
                    df_prox = pd.concat(
                        [df_prox, pd.DataFrame([nova_linha])], ignore_index=True
                    )

            df_prox = normalizar_df(df_prox)
            df_prox = recalcular(df_prox)
            st.session_state.periodos[prox] = df_prox
            st.session_state.periodo_atual = prox
            st.success(f"Carry over concluído para {prox}.")
            st.rerun()

# -----------------------------------------------------------------------------
# Área principal
# -----------------------------------------------------------------------------
if st.session_state.periodo_atual is None:
    st.info("Selecione ou crie um período na barra lateral para começar.")
    st.stop()

st.subheader(f"Período atual: {st.session_state.periodo_atual}")

df_periodo = st.session_state.periodos.get(
    st.session_state.periodo_atual, criar_df_vazio()
)
df_periodo = normalizar_df(df_periodo)

# Atualiza B (Resumo) automaticamente a partir de A (Cartão)
df_periodo["B_Resumo"] = df_periodo["A_Cartao"].apply(gerar_resumo)

# Garante cast explícito para float e preenchimento com 0.0 (evita StreamlitAPIException)
for col in COLUNAS_NUMERICAS:
    df_periodo[col] = pd.to_numeric(df_periodo[col], errors="coerce").fillna(0.0).astype(float)

# Renomeia colunas para exibição conforme apelidos
df_exibicao = df_periodo.rename(columns={c: nome_exibicao(c) for c in COLUNAS_ORIGINAIS})
nomes_exibicao = [nome_exibicao(c) for c in COLUNAS_ORIGINAIS]

# Configuração de colunas: calculadas como somente leitura
config_colunas = {}
for col_orig in COLUNAS_ORIGINAIS:
    nome = nome_exibicao(col_orig)
    if col_orig in COLUNAS_NUMERICAS:
        config_colunas[nome] = st.column_config.NumberColumn(
            nome,
            format="%.2f",
            step=0.01,
        )
    else:
        config_colunas[nome] = st.column_config.TextColumn(nome)

df_editado = st.data_editor(
    df_exibicao,
    column_config=config_colunas,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_{st.session_state.periodo_atual}",
)

# Reverte nomes para colunas internas e recalcula
mapa_reverso = {nome_exibicao(c): c for c in COLUNAS_ORIGINAIS}
df_revertido = df_editado.rename(columns=mapa_reverso)
df_revertido = normalizar_df(df_revertido)
df_revertido["B_Resumo"] = df_revertido["A_Cartao"].apply(gerar_resumo)
df_revertido = recalcular(df_revertido)

st.session_state.periodos[st.session_state.periodo_atual] = df_revertido

# Exibe resultado recalculado (somente leitura)
st.subheader("Resultado recalculado")
df_resultado = df_revertido.rename(
    columns={c: nome_exibicao(c) for c in COLUNAS_ORIGINAIS}
)
st.dataframe(df_resultado, use_container_width=True, hide_index=True)

# Exportação
st.subheader("Exportar")
col_exp1, col_exp2 = st.columns(2)
with col_exp1:
    if st.button("Exportar para Excel"):
        df_export = df_revertido.rename(
            columns={c: nome_exibicao(c) for c in COLUNAS_ORIGINAIS}
        )
        st.download_button(
            label="Baixar Excel",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name=f"bradesco_conciliacao_{st.session_state.periodo_atual.replace('/', '-')}.csv",
            mime="text/csv",
        )
with col_exp2:
    if st.button("Exportar todos os períodos"):
        frames = []
        for per, dfp in st.session_state.periodos.items():
            dfp_exp = recalcular(normalizar_df(dfp)).copy()
            dfp_exp.insert(0, "Período", per)
            dfp_exp = dfp_exp.rename(
                columns={c: nome_exibicao(c) for c in COLUNAS_ORIGINAIS}
            )
            frames.append(dfp_exp)
        df_all = pd.concat(frames, ignore_index=True)
        st.download_button(
            label="Baixar CSV consolidado",
            data=df_all.to_csv(index=False).encode("utf-8"),
            file_name="bradesco_conciliacao_todos_periodos.csv",
            mime="text/csv",
        )

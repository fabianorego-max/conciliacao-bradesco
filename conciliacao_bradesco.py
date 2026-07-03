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
# Configuration
# ---------------------------------------------------------------------------

# Canonical internal column names (A to O)
CANONICAL_COLUMNS = [
    "cartao",               # A
    "resumo",               # B
    "titular",              # C
    "cpf",                  # D
    "localidade",           # E
    "limite",               # F
    "aprovado_reuniao",    # G
    "valor_fatura",         # H
    "saldo_anterior",       # I
    "diferenca_pagar",      # J
    "diferenca_receber",    # K
    "saldo_final_ajustado", # L
    "saldo_proxima_reuniao",# M
    "pos_fechamento",       # N
    "saldo_final_mes",      # O
]

NUMERIC_COLUMNS = [
    "limite",               # F
    "aprovado_reuniao",    # G
    "valor_fatura",         # H
    "saldo_anterior",       # I
    "diferenca_pagar",      # J
    "diferenca_receber",    # K
    "saldo_final_ajustado", # L
    "saldo_proxima_reuniao",# M
    "pos_fechamento",       # N
    "saldo_final_mes",      # O
]

DEFAULT_LABELS = {
    "cartao": "Cartão",
    "resumo": "Resumo 7 dígitos",
    "titular": "Titular",
    "cpf": "CPF",
    "localidade": "Localidade",
    "limite": "Limite",
    "aprovado_reuniao": "Aprovado Reunião",
    "valor_fatura": "Valor Fatura",
    "saldo_anterior": "Saldo Anterior",
    "diferenca_pagar": "Diferença a Pagar",
    "diferenca_receber": "Diferença a Receber",
    "saldo_final_ajustado": "Saldo Final Ajustado",
    "saldo_proxima_reuniao": "Saldo Próxima Reunião",
    "pos_fechamento": "Pós-Fechamento",
    "saldo_final_mes": "Saldo Final do Mês",
}


def get_labels() -> dict:
    """Return the current label mapping, honoring st.session_state.apelidos."""
    if "apelidos" not in st.session_state:
        st.session_state.apelidos = dict(DEFAULT_LABELS)
    # Ensure all canonical keys exist even if apelidos was partially customized
    labels = dict(DEFAULT_LABELS)
    labels.update(st.session_state.apelidos)
    st.session_state.apelidos = labels
    return labels


def display_labels() -> dict:
    """Map canonical names -> display labels for st.data_editor columns."""
    return get_labels()


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

def empty_grid(rows: int = 1) -> pd.DataFrame:
    """Create an empty grid with the canonical A-O structure."""
    data = {col: [""] * rows for col in CANONICAL_COLUMNS}
    df = pd.DataFrame(data)
    return cast_numeric(df)


def cast_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """
    Force every numeric column (F, G, H, I, J, K, L, M, N, O) to float and
    fill missing values with 0.0. This prevents StreamlitAPIException when
    the dataframe is passed to st.data_editor.
    """
    df = df.copy()
    for col in NUMERIC_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
    # Ensure all canonical columns exist and are ordered A-O
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col not in NUMERIC_COLUMNS else 0.0
    df = df[CANONICAL_COLUMNS]
    return df.reset_index(drop=True)


def compute_resumo(cartao: str) -> str:
    """B) Resumo 7 dígitos automatically derived from A) Cartão."""
    if cartao is None:
        return ""
    s = str(cartao).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 7:
        return digits[-7:]
    return digits.ljust(7, "0")[:7]


def recompute(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recalculate derived columns while preserving user-entered values:
      B  = last 7 digits of A
      J  = max(H - G, 0)        (Diferença a Pagar, when H > G)
      K  = max(G - H, 0)        (Diferença a Receber, when G > H)
      L  = I + J - K            (Saldo Final Ajustado)
      M  = G + L - H            (Saldo Próxima Reunião)
      O  = G + L - N            (Saldo Final do Mês)
    """
    df = cast_numeric(df).copy()

    # B) Resumo from A) Cartão
    df["resumo"] = df["cartao"].apply(compute_resumo)

    # Numeric helpers
    g = df["aprovado_reuniao"]
    h = df["valor_fatura"]
    i = df["saldo_anterior"]
    n = df["pos_fechamento"]

    # J and K
    df["diferenca_pagar"] = (h - g).clip(lower=0.0)
    df["diferenca_receber"] = (g - h).clip(lower=0.0)

    # L = I + J - K
    df["saldo_final_ajustado"] = i + df["diferenca_pagar"] - df["diferenca_receber"]

    # M = G + L - H
    df["saldo_proxima_reuniao"] = g + df["saldo_final_ajustado"] - h

    # O = G + L - N
    df["saldo_final_mes"] = g + df["saldo_final_ajustado"] - n

    return cast_numeric(df)


def carry_over_to_next_month(current: pd.DataFrame) -> pd.DataFrame:
    """
    Create next month's grid where Column I (saldo_anterior) receives the
    current month's Column O (saldo_final_mes). Other numeric columns reset.
    """
    current = cast_numeric(current)
    next_df = empty_grid(rows=len(current))
    next_df["cartao"] = current["cartao"].values
    next_df["resumo"] = current["cartao"].apply(compute_resumo).values
    next_df["titular"] = current["titular"].values
    next_df["cpf"] = current["cpf"].values
    next_df["localidade"] = current["localidade"].values
    next_df["limite"] = current["limite"].values
    # I) Saldo Anterior <- O) Saldo Final do Mês
    next_df["saldo_anterior"] = current["saldo_final_mes"].astype(float).values
    return cast_numeric(next_df)


# ---------------------------------------------------------------------------
# Import mapping
# ---------------------------------------------------------------------------

def map_imported_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map an imported Excel/CSV dataframe into the canonical A-O structure.
    Matching is case-insensitive and ignores accents/spaces for robustness.
    """
    import unicodedata

    def normalize(s: str) -> str:
        s = str(s).strip().lower()
        s = "".join(
            ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch)
        )
        return " ".join(s.split())

    labels = get_labels()
    # Build reverse lookup: normalized display label -> canonical
    rev = {normalize(v): k for k, v in labels.items()}
    rev.update({normalize(k): k for k in CANONICAL_COLUMNS})

    mapped = {}
    for src_col in df.columns:
        key = normalize(src_col)
        if key in rev:
            canon = rev[key]
            if canon not in mapped:
                mapped[canon] = df[src_col]

    out = empty_grid(rows=len(df))
    for canon, series in mapped.items():
        out[canon] = series.values

    out = cast_numeric(out)
    out["resumo"] = out["cartao"].apply(compute_resumo)
    return recompute(out)


def read_uploaded_file(uploaded) -> pd.DataFrame:
    """Read an uploaded CSV or Excel file into a dataframe."""
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        try:
            return pd.read_csv(uploaded, sep=None, engine="python")
        except Exception:
            uploaded.seek(0)
            return pd.read_csv(uploaded)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded)
    raise ValueError("Formato de arquivo não suportado. Use CSV ou Excel (.xlsx).")


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Export dataframe to Excel bytes for download."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Conciliacao")
    return output.getvalue()


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

def configure_editor_columns() -> dict:
    """Build column config for st.data_editor using display labels."""
    labels = display_labels()
    config = {}
    for col in CANONICAL_COLUMNS:
        if col in NUMERIC_COLUMNS:
            config[col] = st.column_config.NumberColumn(
                label=labels[col],
                format="%.2f",
                step=0.01,
                min_value=-1e12,
                max_value=1e12,
            )
        else:
            config[col] = st.column_config.TextColumn(label=labels[col])
    return config


def main() -> None:
    st.set_page_config(page_title="Bradesco Conciliação", layout="wide")
    st.title("Bradesco Conciliação")

    # Initialize session state
    if "grid" not in st.session_state:
        st.session_state.grid = empty_grid(rows=3)
    if "apelidos" not in st.session_state:
        st.session_state.apelidos = dict(DEFAULT_LABELS)

    # -----------------------------------------------------------------------
    # Sidebar: label customization + import
    # -----------------------------------------------------------------------
    with st.sidebar:
        st.header("Configurações")

        with st.expander("Renomear colunas (apelidos)", expanded=False):
            new_labels = {}
            changed = False
            for canon in CANONICAL_COLUMNS:
                current = st.session_state.apelidos.get(canon, DEFAULT_LABELS[canon])
                val = st.text_input(
                    f"{canon}", value=current, key=f"label_{canon}"
                )
                new_labels[canon] = val
                if val != current:
                    changed = True
            if st.button("Aplicar apelidos") or changed:
                st.session_state.apelidos = new_labels
                st.success("Apelidos atualizados.")
                st.rerun()

        st.divider()
        st.header("Importar planilha")
        uploaded = st.file_uploader(
            "CSV ou Excel", type=["csv", "xlsx", "xls"], key="uploader"
        )
        if uploaded is not None:
            try:
                raw = read_uploaded_file(uploaded)
                mapped = map_imported_columns(raw)
                st.session_state.grid = mapped
                st.success(f"Importado {len(mapped)} linha(s).")
            except Exception as exc:
                st.error(f"Erro ao importar: {exc}")

        st.divider()
        st.header("Exportar")
        export_df = cast_numeric(st.session_state.grid)
        st.download_button(
            "Baixar Excel",
            data=to_excel_bytes(export_df),
            file_name="bradesco_conciliacao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.download_button(
            "Baixar CSV",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name="bradesco_conciliacao.csv",
            mime="text/csv",
        )

    # -----------------------------------------------------------------------
    # Main editor
    # -----------------------------------------------------------------------
    st.subheader("Planilha de Conciliação (Colunas A–O)")

    # Ensure the grid is always cast before passing to the editor
    st.session_state.grid = cast_numeric(st.session_state.grid)

    edited = st.data_editor(
        st.session_state.grid,
        column_config=configure_editor_columns(),
        num_rows="dynamic",
        use_container_width=True,
        key="data_editor",
        hide_index=True,
    )

    # Recompute derived columns after edits
    st.session_state.grid = recompute(edited)

    # -----------------------------------------------------------------------
    # Carry-over to next month
    # -----------------------------------------------------------------------
    st.divider()
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Avançar para próximo mês", type="primary"):
            st.session_state.grid = carry_over_to_next_month(st.session_state.grid)
            st.success("Coluna O foi transferida para a Coluna I do próximo mês.")
            st.rerun()
    with col2:
        st.caption(
            "O saldo final do mês (O) será copiado para o saldo anterior (I) do próximo mês."
        )

    # -----------------------------------------------------------------------
    # Preview of computed values
    # -----------------------------------------------------------------------
    with st.expander("Resumo calculado", expanded=False):
        st.dataframe(
            cast_numeric(st.session_state.grid),
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    main()

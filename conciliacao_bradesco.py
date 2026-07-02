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
import numpy as np


# Apelidos de colunas suportados pelo sistema de conciliação Bradesco
APELIDOS_COLUNAS = {
    'D': ['D', 'Saldo', 'SALDO', 'saldo_final', 'SALDO_FINAL'],
    'E': ['E', 'Débito', 'Debito', 'DEBITO', 'debito', 'valor_debito'],
    'Ano': ['Ano', 'ANO', 'ano', 'Year', 'YEAR'],
    'Mes': ['Mes', 'Mês', 'MES', 'MÊS', 'mes', 'mês', 'Month', 'MONTH'],
}


def _resolver_coluna(df, alvo):
    """Retorna o nome real da coluna no DataFrame para um alvo, considerando apelidos."""
    if not isinstance(df, pd.DataFrame):
        return None
    if alvo in df.columns:
        return alvo
    for apelido in APELIDOS_COLUNAS.get(alvo, []):
        if apelido in df.columns:
            return apelido
    return None


def _garantir_coluna(df, alvo, valor_padrao=0.0):
    """Garante que a coluna alvo exista no DataFrame, criando-a se necessário."""
    nome = _resolver_coluna(df, alvo)
    if nome is None:
        df[alvo] = float(valor_padrao)
        return alvo
    return nome


def recalcular_saldos(df, col_saldo='D', col_debito='E', manter_ano_mes=True):
    """
    Recalcula os saldos da conciliação Bradesco.

    Garante que:
      - O input seja um DataFrame válido (caso contrário, retorna um DataFrame vazio).
      - As colunas de saldo e débito existam (criadas com 0.0 se ausentes).
      - As conversões numéricas usem df['coluna'] (Series) antes de to_numeric.
      - O controle de Ano/Mês seja preservado quando manter_ano_mes=True.
      - O retorno seja sempre um DataFrame processado.
    """
    # 1. Garantir que o input seja um DataFrame válido
    if df is None or not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    # Trabalhar com uma cópia para não mutar o original
    df = df.copy()

    # 5. Resolver apelidos de colunas e garantir existência de D e E
    nome_saldo = _garantir_coluna(df, col_saldo, 0.0)
    nome_debito = _garantir_coluna(df, col_debito, 0.0)

    # 2. Usar df['coluna'] para obter Series antes do to_numeric
    df[nome_saldo] = pd.to_numeric(df[nome_saldo], errors='coerce').fillna(0.0)
    df[nome_debito] = pd.to_numeric(df[nome_debito], errors='coerce').fillna(0.0)

    # 3. Garantir colunas D e E com valor 0.0 caso não existissem
    if col_saldo not in df.columns:
        df[col_saldo] = 0.0
    if col_debito not in df.columns:
        df[col_debito] = 0.0

    # Recalcular saldo: saldo = saldo - débito (lógica de conciliação)
    df[col_saldo] = df[col_saldo] - df[col_debito]

    # 5. Manter funcionalidade de Ano/Mês
    if manter_ano_mes:
        nome_ano = _resolver_coluna(df, 'Ano')
        nome_mes = _resolver_coluna(df, 'Mes')

        if nome_ano is not None:
            df['Ano'] = pd.to_numeric(df[nome_ano], errors='coerce').fillna(0).astype(int)
        else:
            df['Ano'] = 0

        if nome_mes is not None:
            df['Mes'] = pd.to_numeric(df[nome_mes], errors='coerce').fillna(0).astype(int)
        else:
            df['Mes'] = 0

    # 4. Retorno sempre um DataFrame processado
    return df


if __name__ == '__main__':
    # Exemplo de uso
    dados = {
        'Saldo': ['100.50', '200.00', 'abc'],
        'Débito': ['10.00', '20.00', '5.00'],
        'Ano': [2023, 2023, 2024],
        'Mês': [1, 2, 3],
    }
    df_exemplo = pd.DataFrame(dados)
    resultado = recalcular_saldos(df_exemplo)
    print(resultado)

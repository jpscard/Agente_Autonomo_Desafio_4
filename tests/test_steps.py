
import pandas as pd
import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from steps import Contexto, montar_base_elegiveis

# Fixture para o contexto padrão, pode ser reutilizado por vários testes
@pytest.fixture
def contexto_padrao():
    return Contexto(
        periodo_ini=pd.to_datetime("2025-05-01"),
        periodo_fim=pd.to_datetime("2025-05-31"),
        competencia=pd.to_datetime("2025-05-01"),
        pos15_regra="integral"
    )

# Fixture para as bases de dados, com dados mínimos para os testes
@pytest.fixture
def bases_padrao():
    return {
        "ATIVOS": pd.DataFrame({"MATRICULA": [1, 2, 3], "TITULO DO CARGO": ["ANALISTA", "ANALISTA", "DIRETOR"], "SINDICATO": ["SINDICATO SP", "SINDICATO RJ", "SINDICATO SP"]}),
        "ADMISSAO": pd.DataFrame(),
        "DESLIGADOS": pd.DataFrame(),
        "FERIAS": pd.DataFrame(),
        "AFASTAMENTOS": pd.DataFrame(),
        "APRENDIZ": pd.DataFrame(),
        "ESTAGIO": pd.DataFrame(),
        "EXTERIOR": pd.DataFrame(),
        "DIAS_UTEIS": pd.DataFrame([
            ["SINDICADO", "DIAS UTEIS "],
            ["SINDICATO SP", 22],
            ["SINDICATO RJ", 21]
        ]),
        "SIND_VALOR": pd.DataFrame({"ESTADO": ["São Paulo", "Rio de Janeiro"], "VALOR": [30.0, 35.0]})
    }

def test_calculo_vr_base(contexto_padrao, bases_padrao):
    """Testa o cálculo base para um funcionário ativo, sem ajustes."""
    base_final = montar_base_elegiveis(bases_padrao, contexto_padrao)
    funcionario_1 = base_final[base_final["MATRICULA"] == 1].iloc[0]
    
    assert funcionario_1["DIAS_CALCULADOS"] == 22
    assert funcionario_1["VALOR_UNITARIO"] == 30.0
    assert funcionario_1["VR_TOTAL"] == 22 * 30.0

def test_exclusao_diretor(contexto_padrao, bases_padrao):
    """Testa se um funcionário com cargo de 'DIRETOR' é excluído da base final."""
    base_final = montar_base_elegiveis(bases_padrao, contexto_padrao)
    assert 3 not in base_final["MATRICULA"].values

def test_desligamento_antes_dia_15(contexto_padrao, bases_padrao):
    """Testa se um funcionário desligado antes do dia 15 (com OK) tem o VR zerado."""
    bases_padrao["DESLIGADOS"] = pd.DataFrame({
        "MATRICULA": [1],
        "DATA DEMISSÃO": [pd.to_datetime("2025-05-10")],
        "COMUNICADO DE DESLIGAMENTO": ["OK"]
    })
    base_final = montar_base_elegiveis(bases_padrao, contexto_padrao)
    assert base_final.loc[base_final["MATRICULA"] == 1, "DIAS_CALCULADOS"].iloc[0] == 0

def test_admissao_proporcional(contexto_padrao, bases_padrao):
    """Testa o cálculo proporcional para um funcionário admitido no meio do mês."""
    # Total de dias úteis em Maio/2025 = 22
    # Admitido em 15/05/2025. Dias úteis de 15/05 a 31/05 = 12
    bases_padrao["ADMISSAO"] = pd.DataFrame({
        "MATRICULA": [1],
        "ADMISSAO": [pd.to_datetime("2025-05-15")]
    })
    base_final = montar_base_elegiveis(bases_padrao, contexto_padrao)
    dias_esperados = 12 # Calculado manualmente para o período
    fator_esperado = dias_esperados / 22

    assert pytest.approx(base_final.loc[base_final["MATRICULA"] == 1, "FATOR_ADMISSAO"].iloc[0]) == fator_esperado
    assert base_final.loc[base_final["MATRICULA"] == 1, "DIAS_CALCULADOS"].iloc[0] == round(22 * fator_esperado)



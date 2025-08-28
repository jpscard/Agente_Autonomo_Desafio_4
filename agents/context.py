
from dataclasses import dataclass
import pandas as pd

@dataclass
class Contexto:
    # Período em que o benefício será utilizado (ex: Maio)
    periodo_beneficio_ini: pd.Timestamp
    periodo_beneficio_fim: pd.Timestamp
    
    # Período onde os eventos de ajuste ocorreram (ex: Abril)
    periodo_eventos_ini: pd.Timestamp
    periodo_eventos_fim: pd.Timestamp

    competencia: pd.Timestamp
    pos15_regra: str = "integral"

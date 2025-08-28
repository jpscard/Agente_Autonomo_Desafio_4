
import pandas as pd
import logging
from .context import Contexto

class ValidatorAgent:
    """
    Agente que garante a qualidade e a integridade dos dados.
    """

    def _preparar_dias_uteis(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return pd.DataFrame(columns=["SINDICATO","DIAS_UTEIS"])
        df = df.copy()
        header = df.iloc[0].tolist()
        df.columns = [h if isinstance(h, str) else f"C{i}" for i,h in enumerate(header)]
        df = df.iloc[1:].rename(columns={"SINDICADO":"SINDICATO","DIAS UTEIS ":"DIAS_UTEIS"})
        df["SINDICATO"] = df["SINDICATO"].astype(str).str.strip()
        df["DIAS_UTEIS"] = pd.to_numeric(df["DIAS_UTEIS"], errors="coerce").fillna(0).astype(int)
        return df[["SINDICATO","DIAS_UTEIS"]]

    def _preparar_sind_valor(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return pd.DataFrame(columns=["ESTADO","VALOR"])
        df = df.copy()
        df = df.rename(columns={df.columns[0]:"ESTADO", df.columns[1]:"VALOR"})
        df["VALOR"] = pd.to_numeric(df["VALOR"], errors="coerce")
        return df.dropna(subset=["VALOR"])

    def _preparar_desligados(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return pd.DataFrame(columns=["MATRICULA", "DATA DEMISSÃO", "OK"])
        des = df.copy()
        des.columns = [c.strip() for c in des.columns]
        des["MATRICULA"] = pd.to_numeric(des["MATRICULA"], errors="coerce").astype("Int64")
        des["DATA DEMISSÃO"] = pd.to_datetime(des["DATA DEMISSÃO"], errors="coerce")
        des["OK"] = des["COMUNICADO DE DESLIGAMENTO"].astype(str).str.strip().str.upper().eq("OK")
        return des

    def _validar_dados(self, bases: dict) -> list[str]:
        mensagens = []
        colunas_esperadas = {
            "ATIVOS": ["MATRICULA", "TITULO DO CARGO", "SINDICATO"],
            "DESLIGADOS": ["MATRICULA", "DATA DEMISSÃO", "COMUNICADO DE DESLIGAMENTO"],
            "FERIAS": ["MATRICULA", "DIAS DE FÉRIAS"],
            "ADMISSAO": ["MATRICULA", "ADMISSAO"],
            "SIND_VALOR": ["ESTADO", "VALOR"]
        }

        for nome_base, df in bases.items():
            if nome_base in colunas_esperadas and not df.empty:
                colunas_faltantes = [col for col in colunas_esperadas[nome_base] if col not in df.columns]
                if colunas_faltantes:
                    mensagens.append(f"ERRO: Na base '{nome_base}', colunas obrigatórias não encontradas: {colunas_faltantes}")

        if "ATIVOS" in bases and "DESLIGADOS" in bases:
            ativos_df, desligados_df = bases["ATIVOS"], bases["DESLIGADOS"]
            if not ativos_df.empty and not desligados_df.empty and "MATRICULA" in ativos_df.columns and "MATRICULA" in desligados_df.columns:
                matriculas_ativos = set(pd.to_numeric(ativos_df["MATRICULA"], errors='coerce').dropna())
                matriculas_desligados = set(pd.to_numeric(desligados_df["MATRICULA"], errors='coerce').dropna())
                desligados_nao_encontrados = matriculas_desligados - matriculas_ativos
                if desligados_nao_encontrados:
                    mensagens.append(f"AVISO: Matrículas de DESLIGADOS não encontradas em ATIVOS: {list(desligados_nao_encontrados)[:5]}")
        return mensagens

    def execute(self, bases: dict, ctx: Contexto) -> tuple[dict, list[str]]:
        """
        Executa todas as validações, separando erros críticos de avisos.
        Retorna as bases preparadas e uma lista de avisos.
        Levanta um ValueError se encontrar erros críticos.
        """
        logging.info("Agente Validador: Iniciando validação e preparação dos dados.")
        bases_preparadas = bases.copy()
        
        # Prepara as bases que precisam de tratamento especial
        if "DIAS_UTEIS" in bases_preparadas:
            bases_preparadas["DIAS_UTEIS"] = self._preparar_dias_uteis(bases_preparadas["DIAS_UTEIS"])
        if "SIND_VALOR" in bases_preparadas:
            bases_preparadas["SIND_VALOR"] = self._preparar_sind_valor(bases_preparadas["SIND_VALOR"])
        if "DESLIGADOS" in bases_preparadas:
            bases_preparadas["DESLIGADOS"] = self._preparar_desligados(bases_preparadas["DESLIGADOS"])

        # Coleta todas as mensagens de validação
        mensagens_validacao = self._validar_dados(bases_preparadas)
        mensagens_validacao.extend(self._validar_competencia(bases_preparadas, ctx))

        # Separa erros de avisos
        erros = [m.replace("ERRO: ", "") for m in mensagens_validacao if m.startswith("ERRO")]
        avisos = [m.replace("AVISO: ", "") for m in mensagens_validacao if m.startswith("AVISO")]

        if erros:
            # Levanta uma exceção apenas com os erros críticos para parar o processo
            raise ValueError("Erros de validação impediram o cálculo: " + "; ".join(erros))

        logging.info("Agente Validador: Validação concluída.")
        # Retorna as bases e a lista de avisos para o orquestrador
        return bases_preparadas, avisos

    def _validar_competencia(self, bases: dict, ctx: Contexto) -> list[str]:
        """Verifica se o mês de competência é compatível com as datas nos arquivos."""
        mensagens = []
        # No modelo "Mês Fechado", a validação é contra o mês de eventos (ex: Abril)
        competencia_eventos = ctx.periodo_eventos_ini

        def get_mes_predominante(df: pd.DataFrame, col_data: str) -> int | None:
            if df.empty or col_data not in df.columns:
                return None
            datas_validas = pd.to_datetime(df[col_data], errors='coerce').dropna()
            if datas_validas.empty:
                return None
            return datas_validas.dt.month.mode()[0]

        # Apenas a base de Admissão precisa ser estritamente do mês de competência de eventos.
        bases_para_checar = {
            "ADMISSAO": "ADMISSAO"
        }

        meses_pt = {
            1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
            7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
        }
        mes_beneficio_pt = meses_pt.get(ctx.competencia.month)
        mes_eventos_pt = meses_pt.get(competencia_eventos.month)

        for nome_base, nome_coluna in bases_para_checar.items():
            mes_dados = get_mes_predominante(bases.get(nome_base, pd.DataFrame()), nome_coluna)
            if mes_dados and mes_dados != competencia_eventos.month:
                # Erro crítico que deve parar o processo
                msg = (
                    f"ERRO: Falha na Validação de Dados.\n\n" \
                    f"Para calcular o benefício de **{mes_beneficio_pt}**, o sistema precisa analisar os eventos de **{mes_eventos_pt}**. " \
                    f"No entanto, o arquivo de `{nome_base}` que você enviou contém dados de um mês diferente.\n\n" \
                    f"**Para corrigir, por favor, verifique se:**\n" \
                    f"1. O mês selecionado na interface está correto.\n" \
                    f"2. Os arquivos que você está enviando são os corretos para o período de cálculo desejado."
                )
                mensagens.append(msg)
        
        return mensagens

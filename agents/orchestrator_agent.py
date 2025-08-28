import pandas as pd
import logging
import yaml

# Importa as classes dos outros agentes
from .collector_agent import CollectorAgent
from .validator_agent import ValidatorAgent
from .eligibility_agent import EligibilityAgent
from .calculator_agent import CalculatorAgent
from .context import Contexto
from .reporter_agent import ReporterAgent

class OrchestratorAgent:
    """
    Agente Orquestrador que gerencia todo o fluxo de trabalho de cálculo de VR.
    """

    def __init__(self, config_path: str = 'config.yaml'):
        self.config = self._load_config(config_path)
        self.collector = CollectorAgent(self.config)
        self.validator = ValidatorAgent()
        self.eligibility = EligibilityAgent()
        self.calculator = CalculatorAgent()
        self.reporter = ReporterAgent()

    def _load_config(self, config_path: str) -> dict:
        logging.info(f"Orquestrador: Carregando configuração de '{config_path}'.")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logging.error(f"Erro crítico: Arquivo de configuração '{config_path}' não encontrado.")
            raise
        except Exception as e:
            logging.error(f"Erro ao carregar o arquivo de configuração: {e}")
            raise

    def run(self, input_dir: str, output_dir: str, competencia_str: str, regra_desligamento: str = 'proporcional', progress_callback=None) -> dict:
        """
        Executa o pipeline completo de processamento do VR, narrando cada etapa.
        """
        def report(step, message):
            logging.info(f"[{step}] {message}")
            if progress_callback:
                progress_callback(step, message)

        results = {
            "total_vr": 0.0, "base_final": pd.DataFrame(), "bases": {},
            "file_report": {}, "logs": {},
            "competencia": None
        }
        logs = {
            "contexto": [], "coleta": [], "validacao": [],
            "elegibilidade": [], "calculo": [], "relatorio": []
        }

        def report(step, message):
            logging.info(f"[{step}] {message}")
            if step in logs:
                logs[step].append(message)
            if progress_callback:
                progress_callback(step, message)

        try:
            # Etapa 1: Contexto
            competencia_selecionada = pd.to_datetime(competencia_str)
            results["competencia"] = competencia_str # Salva a competência nos resultados
            
            # Define o período do benefício (mês selecionado)
            periodo_beneficio_ini = competencia_selecionada.replace(day=1)
            periodo_beneficio_fim = competencia_selecionada + pd.offsets.MonthEnd(0)

            # Define o período dos eventos (mês anterior ao do benefício)
            mes_eventos = competencia_selecionada - pd.DateOffset(months=1)
            periodo_eventos_ini = mes_eventos.replace(day=1)
            periodo_eventos_fim = mes_eventos + pd.offsets.MonthEnd(0)

            ctx = Contexto(
                periodo_beneficio_ini=periodo_beneficio_ini,
                periodo_beneficio_fim=periodo_beneficio_fim,
                periodo_eventos_ini=periodo_eventos_ini,
                periodo_eventos_fim=periodo_eventos_fim,
                competencia=competencia_selecionada,
                pos15_regra=regra_desligamento
            )
            report("contexto", f"Mês de Competência (Benefício): **{ctx.competencia.strftime('%B')}**")
            report("contexto", f"Mês de Referência para Eventos (Admissão/Demissão): **{mes_eventos.strftime('%B')}**")
            report("contexto", f"Regra de Desligamento (pós dia 15): **{regra_desligamento.capitalize()}**")

            # Etapa 2: Coleta
            bases, file_report = self.collector.execute(input_dir)
            results["bases"] = bases
            results["file_report"] = file_report
            for base_name, filename in file_report.items():
                report("coleta", f"Base `{base_name}`: Carregada do arquivo `{filename}` com **{len(bases.get(base_name, []))}** registros.")

            # Etapa 3: Validação
            bases_validadas, avisos = self.validator.execute(bases, ctx)
            report("validacao", "Estruturas de dados internas preparadas e normalizadas.")
            if avisos:
                for aviso in avisos:
                    report("validacao", f"⚠️ **Aviso:** {aviso}")
            report("validacao", "Checagem de consistência de dados concluída.")

            # Etapa 4: Elegibilidade
            ativos_antes = len(bases_validadas.get("ATIVOS", pd.DataFrame()))
            base_elegiveis = self.eligibility.execute(bases_validadas)
            elegiveis_depois = len(base_elegiveis)
            report("elegibilidade", f"Base inicial com **{ativos_antes}** colaboradores ativos.")
            report("elegibilidade", f"Após aplicar as regras de exclusão (Diretores, Estagiários, etc.), **{elegiveis_depois}** colaboradores permaneceram.")
            report("elegibilidade", f"Total de **{ativos_antes - elegiveis_depois}** colaboradores removidos da base de cálculo.")

            if base_elegiveis.empty:
                report("calculo", "AVISO: Nenhum colaborador elegível encontrado. Cálculos não serão executados.")
                return results

            # Etapa 5: Cálculo
            base_calculada = self.calculator.execute(base_elegiveis, bases_validadas, ctx)
            results["base_final"] = base_calculada
            report("calculo", "Fatores de ajuste para admissões e desligamentos foram calculados.")
            report("calculo", "Dias de férias foram descontados dos dias a serem pagos.")
            report("calculo", "Valor final do benefício foi calculado multiplicando os dias devidos pelo valor do sindicato.")
            
            # Resumo dos ajustes para o log
            admitidos_ajustados = (base_calculada["FATOR_ADMISSAO"] < 1.0).sum()
            deslig_zerados = (base_calculada["FATOR_DESLIG"] == 0.0).sum()
            ferias_ajustadas = (base_calculada["FERIAS_DIAS"] > 0).sum()
            report("calculo", f"Resumo dos Ajustes: **{admitidos_ajustados}** com VR proporcional (admissão), **{deslig_zerados}** com VR zerado (desligamento), **{ferias_ajustadas}** com desconto de dias por férias.")

            # Etapa 6: Relatório
            output_filename = f"VR MENSAL {competencia_selecionada.strftime('%m.%Y')}.xlsx"
            output_path = f"{output_dir}/{output_filename}"
            total_vr = self.reporter.execute(base_calculada, bases_validadas, ctx, output_path)
            results["total_vr"] = total_vr
            total_formatado = f"R$ {total_vr:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            report("relatorio", f"Planilha final gerada em: `{output_path}`")
            report("relatorio", f"Valor total do benefício consolidado: **{total_formatado}**")

            results["logs"] = logs
            return results

        except (FileNotFoundError, ValueError) as e:
            logging.error(f"Erro de negócio tratado: {e}")
            report("validacao", f"**ERRO:** {e}")
            raise
        except Exception as e:
            logging.error(f"Erro inesperado no orquestrador: {e}", exc_info=True)
            report("validacao", f"**ERRO INESPERADO:** {e}")
            raise
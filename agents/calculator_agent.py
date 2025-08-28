
import pandas as pd
import logging
import unicodedata

from .context import Contexto

class CalculatorAgent:
    """
    Agente que realiza todos os cálculos de valores e dias.
    """

    def _infer_estado_from_sindicato(self, s: str):
        if not isinstance(s, str):
            return None
        S = s.upper()
        if " SP " in f" {S} " or S.endswith(" SP") or S.startswith("SINDPD SP"):
            return "São Paulo"
        if " RJ " in f" {S} " or S.endswith(" RJ"):
            return "Rio de Janeiro"
        if " RS " in f" {S} " or S.endswith(" RS"):
            return "Rio Grande do Sul"
        if " PR " in f" {S} " or S.endswith(" PR") or S.startswith("SITEPD PR"):
            return "Paraná"
        return None

    def _gerar_observacoes(self, row: pd.Series, bases: dict, ctx: Contexto) -> str:
        parts = []
        if pd.notna(row.get("ADMISSAO")) and row.get("FATOR_ADMISSAO", 1.0) < 1.0:
            parts.append(f"Admitido em {pd.Timestamp(row['ADMISSAO']).date().isoformat()} (proporcional)")
        if row.get("FERIAS_DIAS", 0) > 0:
            parts.append(f"Férias {int(row['FERIAS_DIAS'])} dia(s)")

        des_df = bases.get("DESLIGADOS", pd.DataFrame())
        if not des_df.empty and pd.notna(row["MATRICULA"]):
            des_info = des_df[des_df["MATRICULA"] == row["MATRICULA"]]
            if not des_info.empty:
                info = des_info.iloc[0]
                d = info.get("DATA DEMISSÃO")
                ok = info.get("OK")
                if pd.notna(d) and ok:
                    if d.day <= 15:
                        parts.append(f"Desligado em {d.date().isoformat()} (OK até dia 15)")
                    elif d.day >= 16:
                        if ctx.pos15_regra == "integral":
                            parts.append(f"Desligado em {d.date().isoformat()} (>15) - compra integral, ajuste em rescisão")
                        else:
                            parts.append(f"Desligado em {d.date().isoformat()} (>15) - pró-rata no período")
        return " | ".join(parts)

    def execute(self, base_elegiveis: pd.DataFrame, bases: dict, ctx: Contexto) -> pd.DataFrame:
        logging.info("Agente de Cálculo: Iniciando processamento matemático com lógica Mês Fechado.")
        if base_elegiveis.empty:
            logging.warning("Agente de Cálculo: Base de elegíveis está vazia. Nenhum cálculo a ser feito.")
            return pd.DataFrame()

        base = base_elegiveis.copy()

        # --- Etapa 1: Mapeamento Inteligente de Dias Úteis e Valores ---
        base["ESTADO"] = base["SINDICATO"].apply(self._infer_estado_from_sindicato)

        # Mapeia dias úteis por estado, de forma robusta
        du = bases.get("DIAS_UTEIS", pd.DataFrame())
        estado_dias_map = {}
        if not du.empty:
            for _, row in du.iterrows():
                estado = self._infer_estado_from_sindicato(row.get('SINDICATO'))
                if estado:
                    estado_dias_map[estado] = row.get('DIAS_UTEIS')
        base["DIAS_UTEIS_BASE"] = base["ESTADO"].map(estado_dias_map).fillna(0).astype(int)

        # Mapeia valor do VR por estado
        sv = bases.get("SIND_VALOR", pd.DataFrame())
        val_map = sv.set_index("ESTADO")["VALOR"].to_dict() if not sv.empty else {}
        base["VALOR_UNITARIO"] = base["ESTADO"].map(val_map).fillna(0)
        logging.info(f"Agente de Cálculo: {base['ESTADO'].isna().sum()} colaboradores sem ESTADO inferido.")
        logging.info(f"Agente de Cálculo: {base[base['DIAS_UTEIS_BASE'] == 0].shape[0]} colaboradores com DIAS_UTEIS_BASE = 0.")
        logging.info(f"Agente de Cálculo: {base[base['VALOR_UNITARIO'] == 0].shape[0]} colaboradores com VALOR_UNITARIO = 0.")

        # Mapeia férias e admissões
        fer_map = bases.get("FERIAS", pd.DataFrame()).groupby("MATRICULA")["DIAS DE FÉRIAS"].sum()
        base["FERIAS_DIAS"] = base["MATRICULA"].map(fer_map).fillna(0).astype(int)
        adm_map = bases.get("ADMISSAO", pd.DataFrame()).set_index("MATRICULA")["ADMISSAO"]
        base["ADMISSAO"] = base["MATRICULA"].map(adm_map)

        # --- Etapa 2: Calcular Fatores de Ajuste com base no Mês de Eventos ---
        dias_uteis_eventos = pd.bdate_range(ctx.periodo_eventos_ini, ctx.periodo_eventos_fim).size
        logging.info(f"Agente de Cálculo: Dias úteis no mês de eventos ({ctx.periodo_eventos_ini.strftime('%Y-%m-%d')} a {ctx.periodo_eventos_fim.strftime('%Y-%m-%d')}): {dias_uteis_eventos}")

        def fator_adm(d):
            if pd.isna(d) or d < ctx.periodo_eventos_ini or d > ctx.periodo_eventos_fim:
                return 1.0
            dias_trabalhados = pd.bdate_range(d, ctx.periodo_eventos_fim).size
            return dias_trabalhados / dias_uteis_eventos if dias_uteis_eventos else 1.0
        base["FATOR_ADMISSAO"] = base["ADMISSAO"].apply(fator_adm)

        des_map = bases.get("DESLIGADOS", pd.DataFrame()).set_index("MATRICULA").to_dict('index')
        def fator_deslig(row):
            info = des_map.get(row["MATRICULA"])
            if not info: return 1.0
            d, ok = info.get("DATA DEMISSÃO"), info.get("OK")
            if pd.notna(d) and ok and (d >= ctx.periodo_eventos_ini and d <= ctx.periodo_eventos_fim):
                if d.day <= 15:
                    return 0.0  # Regra: Demitido no mês de eventos até dia 15 -> benefício zerado.
                else: # d.day > 15
                    # Regra do PDF: Demitido após dia 15 -> benefício proporcional.
                    dias_trabalhados = pd.bdate_range(ctx.periodo_eventos_ini, d).size
                    return dias_trabalhados / dias_uteis_eventos if dias_uteis_eventos else 1.0
            return 1.0
        base["FATOR_DESLIG"] = base.apply(fator_deslig, axis=1)

        # --- Etapa 3: Cálculo Final ---
        base["DIAS_CALCULADOS"] = (base["DIAS_UTEIS_BASE"] * base["FATOR_ADMISSAO"] * base["FATOR_DESLIG"]).round()
        # A regra de "exclusão parcial" de férias implica em subtrair os dias.
        base["DIAS_CALCULADOS"] = (base["DIAS_CALCULADOS"] - base["FERIAS_DIAS"]).clip(lower=0).astype(int)
        
        base["VR_TOTAL"] = (base["DIAS_CALCULADOS"] * base["VALOR_UNITARIO"]).round(2)
        base["EMPRESA_80"] = (base["VR_TOTAL"] * 0.80).round(2)
        base["COLABORADOR_20"] = (base["VR_TOTAL"] * 0.20).round(2)

        logging.info(f"Agente de Cálculo: {base[base['DIAS_CALCULADOS'] == 0].shape[0]} colaboradores com DIAS_CALCULADOS = 0 após ajustes.")
        logging.info(f"Agente de Cálculo: {base[base['VR_TOTAL'] == 0].shape[0]} colaboradores com VR_TOTAL = 0.")

        base["OBS GERAL"] = base.apply(lambda row: self._gerar_observacoes(row, bases, ctx), axis=1)

        logging.info("Agente de Cálculo: Processamento matemático finalizado.")
        return base

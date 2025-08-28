
import pandas as pd
import logging
import unicodedata

class EligibilityAgent:
    """
    Agente que aplica as regras de negócio para determinar quem é elegível.
    """

    def _strip_accents_upper(self, s: str):
        if pd.isna(s):
            return s
        return unicodedata.normalize('NFKD', str(s)).encode('ascii','ignore').decode('utf-8').upper()

    def execute(self, bases: dict) -> pd.DataFrame:
        """
        Filtra a base de ativos para retornar apenas os colaboradores elegíveis.
        """
        logging.info("Agente de Elegibilidade: Iniciando filtro de colaboradores.")
        
        ativos = bases.get("ATIVOS", pd.DataFrame()).copy()
        if ativos.empty:
            logging.error("Base de ATIVOS está vazia. Não é possível encontrar elegíveis.")
            return pd.DataFrame()
            
        ativos["MATRICULA"] = pd.to_numeric(ativos["MATRICULA"], errors="coerce").astype("Int64")
        
        # 1. Remover Diretores
        ativos["CARGO_UP"] = ativos["TITULO DO CARGO"].astype(str).apply(self._strip_accents_upper)
        base_elegiveis = ativos[~ativos["CARGO_UP"].str.contains("DIRETOR", na=False)].copy()
        logging.info(f"{len(ativos) - len(base_elegiveis)} diretores removidos.")

        # 2. Remover outros grupos
        excl_matriculas = []
        grupos_para_excluir = {
            "APRENDIZ": "MATRICULA",
            "ESTAGIO": "MATRICULA",
            "AFASTAMENTOS": "MATRICULA",
            "EXTERIOR": "CADASTRO" # Note que a coluna é diferente aqui
        }

        for key, col_matricula in grupos_para_excluir.items():
            df_excl = bases.get(key, pd.DataFrame())
            if not df_excl.empty and col_matricula in df_excl.columns:
                s = pd.to_numeric(df_excl[col_matricula], errors="coerce").dropna().astype(int)
                matriculas = s.tolist()
                if matriculas:
                    logging.info(f"{len(matriculas)} colaboradores removidos da base '{key}'.")
                    excl_matriculas.extend(matriculas)
        
        if excl_matriculas:
            base_elegiveis = base_elegiveis[~base_elegiveis["MATRICULA"].isin(set(excl_matriculas))]

        logging.info(f"Agente de Elegibilidade: Filtro finalizado. {len(base_elegiveis)} colaboradores são elegíveis.")
        return base_elegiveis

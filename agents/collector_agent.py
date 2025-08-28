
import pandas as pd
import logging
import os
import glob
import unicodedata

class CollectorAgent:
    """
    Agente responsável por encontrar e carregar os dados brutos de entrada.
    """

    def __init__(self, config: dict):
        self.config = config
        self.key_map = {
            'ativos': 'ATIVOS', 'admissoes': 'ADMISSAO', 'desligados': 'DESLIGADOS',
            'ferias': 'FERIAS', 'afastamentos': 'AFASTAMENTOS', 'aprendiz': 'APRENDIZ',
            'estagio': 'ESTAGIO', 'exterior': 'EXTERIOR', 'dias_uteis': 'DIAS_UTEIS',
            'sind_valor': 'SIND_VALOR'
        }

    def _normalize_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normaliza as colunas de um DataFrame.
        """
        df = df.copy()
        column_map = {
            "MATRICULA": ["MATRICULA", "CHAPA", "CADASTRO"],
            "TITULO DO CARGO": ["TITULO DO CARGO", "CARGO"],
            "SINDICATO": ["SINDICATO", "SINDICATO DO COLABORADOR"],
            "DATA DEMISSÃO": ["DATA DEMISSÃO", "DATA DEMISSAO", "DEMISSAO"],
            "COMUNICADO DE DESLIGAMENTO": ["COMUNICADO DE DESLIGAMENTO", "COMUNICADO"],
            "DIAS DE FÉRIAS": ["DIAS DE FÉRIAS", "DIAS DE FERIAS", "FERIAS DIAS"],
            "ADMISSAO": ["ADMISSAO", "ADMISSÃO", "DATA DE ADMISSÃO", "DATA ADMISSAO"],
            "DIAS_UTEIS": ["DIAS_UTEIS", "DIAS UTEIS"],
            "ESTADO": ["ESTADO", "UF"],
            "VALOR": ["VALOR", "VALOR DIARIO", "VALOR DIÁRIO"]
        }
        inverted_map = {var.upper(): standard for standard, variations in column_map.items() for var in variations}
        new_columns = []
        for col in df.columns:
            normalized_col = str(col).strip().upper()
            normalized_col = unicodedata.normalize('NFKD', normalized_col).encode('ascii', 'ignore').decode('utf-8')
            if normalized_col in inverted_map:
                new_columns.append(inverted_map[normalized_col])
            else:
                new_columns.append(normalized_col)
        df.columns = new_columns
        return df

    def _read(self, input_dir: str, name_like: str, sheet_hint: str | None = None) -> tuple[pd.DataFrame, str | None]:
        """
        Lê um arquivo Excel que corresponde a um padrão de nome, garantindo que seja fechado.
        Retorna o dataframe e o nome do arquivo lido.
        """
        matches = [p for p in glob.glob(os.path.join(input_dir, "*.xlsx")) if name_like.lower() in p.lower()]
        if not matches:
            raise FileNotFoundError(f"Arquivo contendo '{name_like}' não encontrado no diretório {input_dir}")
        
        file_path = matches[0]
        logging.info(f"Lendo arquivo: {os.path.basename(file_path)} (para base: {name_like})")
        
        try:
            with pd.ExcelFile(file_path) as xl:
                if sheet_hint and sheet_hint in xl.sheet_names:
                    sheet_name = sheet_hint
                else:
                    sheet_name = xl.sheet_names[0]
                    if sheet_hint:
                        logging.warning(f"Aba '{sheet_hint}' não encontrada em {file_path}. Usando a primeira aba: '{sheet_name}'.")
                
                df = xl.parse(sheet_name)
            return df, os.path.basename(file_path)
        except Exception as e:
            logging.error(f"Falha ao ler o arquivo Excel {file_path}: {e}")
            raise

    

    def execute(self, input_dir: str) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
        """
        Executa o processo de coleta de dados.
        Retorna uma tupla contendo:
        - Dicionário de dataframes das bases.
        - Dicionário com o relatório de arquivos lidos.
        """
        logging.info("Agente Coletor: Iniciando coleta de dados.")
        bases = {}
        file_report = {} # Initialize file_report
        file_map = self.config['arquivos_entrada']
        sheet_map = self.config.get('sheets', {})

        for config_key, internal_key in self.key_map.items():
            name_like = file_map.get(config_key)
            if not name_like:
                logging.warning(f"Arquivo para '{config_key}' não definido no config.yaml. Pulando.")
                continue
            try:
                sheet_hint = sheet_map.get(config_key)
                df, filename = self._read(input_dir, name_like, sheet_hint) # Unpack df and filename
                bases[internal_key] = self._normalize_cols(df)
                file_report[internal_key] = filename # Add filename to file_report
            except FileNotFoundError as e:
                logging.warning(str(e))
                bases[internal_key] = pd.DataFrame()
                file_report[internal_key] = "Não encontrado" # Add "Não encontrado" to file_report

        logging.info("Agente Coletor: Coleta de dados finalizada.")
        return bases, file_report # Return bases and file_report

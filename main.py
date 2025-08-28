
import argparse
import logging
import os
from agents.orchestrator_agent import OrchestratorAgent

def main():
    """
    Ponto de entrada principal para execução do processo de cálculo de VR via linha de comando.
    """
    # Configuração do logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] - %(message)s")

    # Configuração dos argumentos da linha de comando
    parser = argparse.ArgumentParser(description="Executa o pipeline de cálculo de Vale Refeição.")
    parser.add_argument(
        "-i", "--input", 
        default="documentos",
        help="Diretório contendo os arquivos de entrada. Padrão: 'documentos'"
    )
    parser.add_argument(
        "-o", "--output", 
        default="output",
        help="Diretório para salvar o relatório final. Padrão: 'output'"
    )
    parser.add_argument(
        "-c", "--competencia", 
        required=True, 
        help="Data de competência no formato YYYY-MM-DD (ex: 2024-05-01)"
    )
    args = parser.parse_args()

    # Garante que o diretório de saída exista
    if not os.path.exists(args.output):
        os.makedirs(args.output)

    # Instancia e executa o orquestrador
    try:
        orchestrator = OrchestratorAgent(config_path='config.yaml')
        orchestrator.run(
            input_dir=args.input,
            output_dir=args.output,
            competencia_str=args.competencia
        )
    except Exception as e:
        logging.error(f"Falha na execução do processo: {e}")
        print(f"Ocorreu uma falha. Verifique o log para mais detalhes.")

if __name__ == "__main__":
    main()

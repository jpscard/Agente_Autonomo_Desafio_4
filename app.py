import streamlit as st
import pandas as pd
import json
import ast # Adicionado para ast.literal_eval
import logging
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Importações da nova arquitetura de agentes
from agents.orchestrator_agent import OrchestratorAgent

# Importações do LangChain para o Google Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage

# --- Configuração de Logging e Variáveis de Ambiente ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] - %(message)s")
load_dotenv()

# --- Funções de Cache e Configuração ---
@st.cache_resource
def get_llm():
    """Inicializa o Large Language Model (LLM)."""
    if not os.getenv("GOOGLE_API_KEY"):
        return None
    return ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0, convert_system_message_to_human=True)

# --- Ferramenta do Agente de IA (usando a nova arquitetura) ---
@tool
def executar_calculo_vr_agente(competencia: str, input_dir: str = "documentos", output_dir: str = "output") -> str:
    """
    Executa o processo completo de cálculo do vale-refeição (VR) usando a equipe de agentes.
    
    Args:
        competencia (str): Mês de competência no formato 'YYYY-MM-DD'.
        input_dir (str): Diretório de entrada dos arquivos. Padrão: 'documentos'.
        output_dir (str): Diretório de saída para o relatório. Padrão: 'output'.
    """
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        orchestrator = OrchestratorAgent(config_path='config.yaml')
        results = orchestrator.run(input_dir=input_dir, output_dir=output_dir, competencia_str=competencia)
        
        total_vr = results.get("total_vr", 0.0)
        output_filename = f"VR MENSAL {pd.to_datetime(competencia).strftime('%m.%Y')}.xlsx"
        total_formatado = f"R$ {total_vr:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        return f"Processo concluído com sucesso! Valor total do benefício: **{total_formatado}**. A planilha foi salva em '{output_dir}/{output_filename}'."
    except Exception as e:
        logging.error(f"Falha na ferramenta de cálculo: {e}", exc_info=True)
        return f"Ocorreu um erro ao executar o cálculo: {e}"

# --- Lógica do Agente de IA ---
def get_agent():
    """Monta e retorna o agente de IA com a ferramenta refatorada."""
    llm = get_llm()
    if not llm: return None
    tools = [executar_calculo_vr_agente]
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Você é um assistente prestativo para calcular o Vale Refeição (VR). O usuário fornecerá a competência (mês/ano). Use a ferramenta `executar_calculo_vr_agente` para realizar a tarefa. Confirme a data de competência antes de agir."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)

# --- Interface Principal do Streamlit ---
st.set_page_config(page_title="Agente de VR", layout="wide")

st.title("Automação de Cálculo de Vale Refeição")

# --- Barra Lateral ---
with st.sidebar:
    st.header("Configurações Gerais")
    
    api_key_input = st.text_input(
        "Chave de API do Google Gemini", 
        type="password",
        help="Insira sua chave para ativar a Interface de Chat (IA). A chave não será salva."
    )

    if api_key_input:
        os.environ["GOOGLE_API_KEY"] = api_key_input
        st.success("Chave de API carregada com sucesso!")
    
    st.divider()

    st.header("Modo de Operação")
    modo = st.radio("Escolha a interface:", ("Interface Gráfica", "Interface de Chat (IA)"), label_visibility="collapsed")

# --- Lógica Principal ---
if modo == "Interface Gráfica":
    # Inicializa o estado da sessão para guardar os resultados
    if "results" not in st.session_state:
        st.session_state.results = None

    # --- Coluna da Esquerda: Controles ---
    with st.sidebar:
        st.divider()
        st.header("Parâmetros de Cálculo")
        
        from datetime import datetime
        meses_pt = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        map_mes_num = {nome: i+1 for i, nome in enumerate(meses_pt)}
        
        hoje = datetime.now()
        mes_selecionado = st.selectbox("Mês de Competência", options=meses_pt, index=hoje.month - 1)
        ano_selecionado = st.number_input("Ano de Competência", min_value=2020, max_value=hoje.year + 5, value=hoje.year)

        num_mes = map_mes_num[mes_selecionado]
        competencia_str = f"{ano_selecionado}-{num_mes:02d}-01"

        with st.expander("Regras de Negócio (Avançado)"):
            regra_desligamento = st.radio(
                "Regra para desligamento após dia 15:",
                options=["Proporcional", "Integral"],
                index=1, # Padrão é Integral, conforme desafio
                help="**Proporcional**: Calcula os dias de VR até a data da demissão. **Integral**: Paga o mês cheio, com o ajuste sendo feito na rescisão."
            ).lower()

    # --- Coluna da Direita: Upload e Execução ---
    st.header("1. Upload dos Arquivos de Entrada")
    uploaded_files = st.file_uploader(
        "Selecione os arquivos Excel necessários (ATIVOS, DESLIGADOS, FÉRIAS, etc.)",
        type=["xlsx"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    st.header("2. Execução do Processo")
    if st.button("Iniciar Processamento", type="primary", disabled=not uploaded_files, use_container_width=True):
        if not os.path.exists("output"):
            os.makedirs("output")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            for uploaded_file in uploaded_files:
                with open(temp_path / uploaded_file.name, "wb") as f:
                    f.write(uploaded_file.getbuffer())
            
            logs = {
                "contexto": [], "coleta": [], "validacao": [],
                "elegibilidade": [], "calculo": [], "relatorio": []
            }

            def progress_callback(step, message):
                if step in logs:
                    logs[step].append(message)

            try:
                with st.spinner("Executando a equipe de agentes... Por favor, aguarde."):
                    orchestrator = OrchestratorAgent(config_path='config.yaml')
                    # Salva os resultados no estado da sessão
                    st.session_state.results = orchestrator.run(
                        input_dir=str(temp_path), 
                        output_dir="output",
                        competencia_str=competencia_str,
                        regra_desligamento=regra_desligamento,
                        progress_callback=progress_callback
                    )
            except Exception as e:
                st.error(f"Ocorreu um erro durante a execução: {e}")
                st.session_state.results = None # Limpa resultados em caso de erro

    # --- Seção de Resultados (lê do estado da sessão) ---
    if st.session_state.results:
        results = st.session_state.results
        st.success("Processo finalizado com sucesso!")

        st.divider()
        st.header("Resultados do Cálculo")

        # --- Container de Dashboards ---
        with st.container(border=True):
            st.subheader("Resumo Geral")
            base_final = results.get("base_final", pd.DataFrame())
            total_vr = results.get("total_vr", 0.0)
            custo_empresa = base_final["EMPRESA_80"].sum()

            col1, col2, col3 = st.columns(3)
            col1.metric("Valor Total do Benefício", f"R$ {total_vr:,.2f}")
            col2.metric("Custo Total para Empresa", f"R$ {custo_empresa:,.2f}")
            col3.metric("Colaboradores Beneficiados", f"{len(base_final)}")
            
            st.divider()
            st.subheader("Custo Total de VR por Sindicato")
            custo_sindicato = base_final.groupby("SINDICATO")["VR_TOTAL"].sum()
            st.bar_chart(custo_sindicato)

        # --- Container de Logs ---
        with st.container(border=True):
            st.subheader("Log de Execução Detalhado")
            # Acessa o log que foi salvo dentro do objeto results
            logs = results.get("logs", {})
            etapas = [
                ("Contexto da Execução", logs.get("contexto", [])),
                ("Coleta de Dados", logs.get("coleta", [])),
                ("Validação dos Dados", logs.get("validacao", [])),
                ("Análise de Elegibilidade", logs.get("elegibilidade", [])),
                ("Cálculo do Benefício", logs.get("calculo", [])),
                ("Geração do Relatório Final", logs.get("relatorio", []))
            ]
            for titulo, mensagens in etapas:
                with st.expander(titulo):
                    if mensagens:
                        for msg in mensagens:
                            st.markdown(f"- {msg}")
                    else:
                        st.write("Nenhum detalhe registrado para esta etapa.")
        
        # --- Botão de Download ---
        num_mes = pd.to_datetime(results["competencia"]).month
        ano_selecionado = pd.to_datetime(results["competencia"]).year
        output_filename = f"VR MENSAL {num_mes:02d}.{ano_selecionado}.xlsx"
        output_path = os.path.join("output", output_filename)
        with open(output_path, "rb") as f:
            file_bytes = f.read()
        st.download_button(
            label="Baixar Relatório Completo",
            data=file_bytes,
            file_name=output_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
            
            

elif modo == "Interface de Chat (IA)":
    st.header("💬 Modo: Interface de Chat (IA)")

    # Área de Upload de Arquivos para o Chat
    st.subheader("1. Upload dos Arquivos de Entrada")
    uploaded_files_chat = st.file_uploader(
        "Selecione os arquivos Excel necessários (ATIVOS, DESLIGADOS, FÉRIAS, etc.) para o cálculo via chat.",
        type=["xlsx"],
        accept_multiple_files=True,
        key="chat_file_uploader" # Chave única para este uploader
    )

    # Salva os arquivos em um diretório temporário e armazena o caminho
    if uploaded_files_chat:
        if "chat_temp_dir" not in st.session_state:
            st.session_state.chat_temp_dir = tempfile.TemporaryDirectory()
            st.session_state.chat_temp_path = Path(st.session_state.chat_temp_dir.name)
        
        for uploaded_file in uploaded_files_chat:
            file_path = st.session_state.chat_temp_path / uploaded_file.name
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
        st.success(f"Arquivos carregados para: {st.session_state.chat_temp_path}")
    else:
        # Limpa o diretório temporário se nenhum arquivo estiver carregado
        if "chat_temp_dir" in st.session_state:
            st.session_state.chat_temp_dir.cleanup()
            del st.session_state.chat_temp_dir
            del st.session_state.chat_temp_path
            
    st.subheader("2. Converse com o Agente")
    agent_executor = get_agent()
    if not agent_executor:
        st.warning("⚠️ Chave de API do Google não encontrada. Configure o arquivo .env para usar este modo.")
    else:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        if prompt := st.chat_input("Qual a competência para o cálculo? (ex: 05/2024)"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Pensando..."):
                    history = [HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"]) for m in st.session_state.messages[:-1]]
                    
                    # Passa o input_dir para o agente se houver arquivos carregados
                    tool_kwargs = {}
                    if "chat_temp_path" in st.session_state:
                        tool_kwargs["input_dir"] = str(st.session_state.chat_temp_path)
                    
                    response = agent_executor.invoke({"input": prompt, "chat_history": history, "tool_kwargs": tool_kwargs})
                    st.write(f"DEBUG: Agent raw output: {response['output']}") # Debugging line
                    
                    # O output do agente agora é um dicionário (string representation)
                    try:
                        agent_output = ast.literal_eval(response['output'])
                        st.write(f"DEBUG: agent_output after literal_eval: {agent_output}") # Debugging line
                        output_message = agent_output.get("output_message", "Processo concluído.")
                        output_path = agent_output.get("output_path")
                        st.write(f"DEBUG: Extracted output_path: {output_path}") # Debugging line
                        st.write(f"DEBUG: os.path.exists(output_path): {os.path.exists(output_path)}") # Debugging line
                        logs = agent_output.get("logs", {})
                        
                        st.markdown(output_message)
                        
                        # Exibe botão de download se o processo foi concluído com sucesso
                        if output_path and os.path.exists(output_path):
                            try:
                                output_filename = os.path.basename(output_path)
                                with open(output_path, "rb") as f:
                                    file_bytes = f.read()
                                st.download_button(
                                    label="Baixar Relatório Gerado",
                                    data=file_bytes,
                                    file_name=output_filename,
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True
                                )
                            except Exception as e:
                                st.error(f"Erro ao preparar o download: {e}")
                                logging.error(f"Erro ao preparar o download: {e}", exc_info=True)
                        
                        # Exibe os logs detalhados
                        if logs:
                            st.divider()
                            st.subheader("Log de Execução Detalhado")
                            etapas = [
                                ("Contexto da Execução", logs.get("contexto", [])),
                                ("Coleta de Dados", logs.get("coleta", [])),
                                ("Validação dos Dados", logs.get("validacao", [])),
                                ("Análise de Elegibilidade", logs.get("elegibilidade", [])),
                                ("Cálculo do Benefício", logs.get("calculo", [])),
                                ("Geração do Relatório Final", logs.get("relatorio", []))
                            ]
                            for titulo, mensagens in etapas:
                                with st.expander(titulo):
                                    if mensagens:
                                        for msg in mensagens:
                                            st.markdown(f"- {msg}")
                                    else:
                                        st.write("Nenhum detalhe registrado para esta etapa.")
                                        
                    except (ValueError, SyntaxError) as e:
                        # Se não for um dicionário válido, exibe a resposta bruta (erro do agente, etc.)
                        st.markdown(response['output'])
                        logging.error(f"Erro ao avaliar a saída do agente: {e} - Saída: {response['output']}", exc_info=True)
                        
            st.session_state.messages.append({"role": "assistant", "content": response['output']})
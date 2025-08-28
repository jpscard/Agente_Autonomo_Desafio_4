# Agente Autônomo de Cálculo de Vale Refeição v3.0

## 📖 Visão Geral do Projeto

Este projeto é um sistema de agentes autônomos projetado para automatizar o complexo processo de cálculo do Vale Refeição (VR) para os colaboradores de uma empresa. A aplicação utiliza uma interface gráfica moderna para upload de arquivos, configuração de parâmetros e visualização de resultados, garantindo um processo seguro, rápido e preciso.

A versão 3.0 introduz a lógica de negócio "Mês Fechado", validações de dados aprimoradas, uma interface de usuário redesenhada e a capacidade de configurar regras de negócio dinamicamente.

---

## ✨ Principais Funcionalidades

*   **Interface Gráfica Intuitiva**: Permite o upload direto dos arquivos Excel, eliminando a necessidade de colocá-los em pastas específicas.
*   **Lógica de "Mês Fechado"**: Calcula o benefício de um mês (ex: Maio) com base nos eventos (admissões, demissões) ocorridos no mês anterior (ex: Abril), refletindo um processo de folha de pagamento comum no mercado.
*   **Validação Inteligente de Competência**: O sistema cruza a informação do mês selecionado pelo usuário com as datas presentes nos arquivos, impedindo o cálculo com dados inconsistentes e exibindo uma mensagem de erro clara.
*   **Regras de Negócio Configuráveis**: Através de um menu avançado, o usuário pode alterar parâmetros de cálculo, como a regra de pagamento para desligamentos (proporcional ou integral).
*   **Dashboards de Resultado**: Após o cálculo, exibe gráficos e métricas que oferecem insights visuais sobre o resultado, como o custo total por sindicato.
*   **Mapeamento Robusto de Dados**: O sistema identifica e associa corretamente os dados de diferentes arquivos, mesmo que os nomes dos sindicatos não sejam 100% idênticos.
*   **Modo de Chat com IA**: Uma interface conversacional experimental com Google Gemini, que pode ser ativada com uma chave de API.

---

## 📂 Estrutura do Projeto

```
📂 agente-vr-mensal-main
┣ 📄 .env                  # Arquivo para a chave de API do Google (uso local)
┣ 📄 app.py                # Aplicação unificada com interface Gráfica e de Chat (Streamlit)
┣ 📄 config.yaml           # Arquivo de configuração central
┣ 📄 main.py               # Ponto de entrada para execução via terminal (CLI)
┣ 📄 requirements.txt      # Dependências do projeto
┣ 📂 agents/               # Agentes autônomos para coleta, cálculo, validação, etc.
┣ 📂 output/               # Pasta onde os relatórios são salvos
┗ 📄 README.md             # Esta documentação
```

---

## 🛠️ Manual de Uso

### 1. Instalação

**Pré-requisitos**: Python 3.9 ou superior.

**Passos:**

1.  **Clone o repositório** e entre na pasta do projeto.
2.  **Crie e ative um ambiente virtual** (recomendado).
3.  **Instale as dependências** com `pip install -r requirements.txt`.

### 2. Execução

A aplicação principal é executada com um único comando no seu terminal:

```bash
streamlit run app.py
```

### 3. Passo a Passo (Interface Gráfica)

1.  **Configure os Parâmetros**: Na barra lateral, selecione o **Mês** e o **Ano de Competência** para o qual você deseja calcular o benefício.
2.  **Carregue os Arquivos**: Na área principal, clique para selecionar ou arraste e solte todos os arquivos Excel necessários para o cálculo (ATIVOS, DESLIGADOS, FÉRIAS, etc.). O botão de processamento só será ativado após o upload.
3.  **(Opcional) Ajuste as Regras de Negócio**: Expanda a seção "Regras de Negócio (Avançado)" na barra lateral para alterar parâmetros, como a regra de pagamento para funcionários desligados.
4.  **Execute o Processamento**: Clique no botão **"Iniciar Processamento"**.
5.  **Analise os Resultados**: Após o processamento, a aplicação exibirá:
    *   Um **Dashboard** com as métricas principais e gráficos.
    *   Um **Log de Execução Detalhado** em formato de menu expansível ("acordeão"), permitindo que você audite cada etapa do processo.
    *   O botão para **baixar o relatório** completo em formato Excel.

---

## ✅ Testando a Aplicação

Para garantir a confiabilidade da lógica de cálculo, execute os testes unitários com `pytest`:

```bash
pytest
```
# 🚀 IIS Log Analyzer - Multi-Core Engine

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask%203.1-black.svg)](https://flask.palletsprojects.com/)
[![OpenShift](https://img.shields.io/badge/OpenShift-Kubernetes-red.svg)](https://www.redhat.com/openshift)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20%7C%20SQLite-blue.svg)](https://www.postgresql.org/)

Sistema Web de alta performance construído em **Python Flask** para ingestão, análise e visualização de logs do **Microsoft IIS (formato W3C Extended Log)**. Equipado com motor de processamento paralelo **Multi-Core** (`multiprocessing`), visualizador tabular com filtros avançados e Dashboard com métricas e gráficos analíticos interativos.

---

## ⚡ Principais Funcionalidades

- **Motor de Parsing Multi-Core**:
  - Processamento paralelo dividindo arquivos de log em blocos contíguos preservando integridade das linhas.
  - Permite escolher quantos núcleos da CPU usar no momento do upload.
  - Capacidade de processar **25.000+ linhas em ~0.14 segundos** (~170.000 logs/segundo).
- **Dashboard Analítico**:
  - **KPIs em Tempo Real**: Total de requisições, IPs distintos, taxa de erro (4xx/5xx) e latência média/máxima.
  - **Gráficos Interativos (Chart.js)**: Volume de requisições vs erros ao longo do tempo, distribuição de famílias HTTP (2xx, 3xx, 4xx, 5xx), métodos HTTP (GET, POST, etc.) e top 10 códigos de status.
  - **Contadores de Requisições por Minuto**: Abas especializadas agregando requisições por **URI Path**, **IP de Cliente** e **Método HTTP**, com ordenação crescente/decrescente em todas as métricas (*Requisições/min*, *Tempo Médio*, *Erros*).
  - **Top 10 Endpoints Mais Lentos**: Visualização rápida de gargalos de latência.
- **Visualizador de Logs com Filtros**:
  - Filtros instantâneos por Status HTTP (2xx, 3xx, 4xx, 5xx ou código específico), Método, IP de Origem, URI e Tempo Mínimo de Resposta.
  - Ordenação dinâmica por clique em **Data/Hora** e **Latência** (Crescente/Decrescente).
  - Modal com visão completa da requisição: *User-Agent*, *Referer*, *Query String*, *Substatus*, *Win32-Status*, *Servidor/Porta* e *Usuário autenticado*.
- **Histórico de Análises & Retenção de Dados**:
  - **Retenção Padrão de 24 Horas**: Logs são purgados automaticamente após 24h para economizar armazenamento.
  - **Modo Persistente (Fixar)**: Permite marcar análises importantes como permanentes para que nunca sejam apagadas.
  - **Exclusão Manual Imediata**: Botão para apagar qualquer análise e liberar espaço do banco de dados na hora.
  - **Alternância entre Análises**: Seletor global no topo e tela dedicada de histórico (`/history`) para alternar entre diferentes arquivos analisados.
- **Compatibilidade Híbrida de Banco de Dados**:
  - **PostgreSQL 15+** nativo para produção/OpenShift via conexão de alta performance.
  - **SQLite** automático para desenvolvimento local e testes rápidos sem infraestrutura externa.

---

## 📁 Estrutura do Projeto

```
loganalizer/
├── app.py                    # Aplicação Flask e endpoints da API
├── parser.py                 # Motor Multi-Core de leitura e parsing de logs IIS W3C
├── database.py               # Camada de dados híbrida (PostgreSQL e SQLite)
├── requirements.txt          # Dependências Python (Flask, psycopg2, gunicorn)
├── Dockerfile                # Imagem de container baseada em Red Hat UBI9 Python
├── openshift/
│   └── loganalizer.yaml      # Manifesto Kubernetes/OpenShift (BuildConfig, ImageStream, etc.)
├── static/
│   ├── css/style.css         # UI moderna (Dark mode, glassmorphism e tipografia Inter)
│   └── js/
│       ├── main.js           # Upload com barra de progresso em tempo real
│       ├── dashboard.js      # Gráficos Chart.js e contadores minuto a minuto
│       └── logs.js           # Tabela com filtros, ordenação e modais de detalhes
└── templates/
    ├── base.html             # Layout base responsivo com sidebar
    ├── index.html            # Upload e seleção de núcleos de CPU
    ├── dashboard.html        # Dashboard com KPIs, gráficos e contadores
    └── logs.html             # Visualizador avançado de registros
```

---

## 🛠️ Execução Local

### 1. Clonar o repositório
```bash
git clone https://github.com/kassi0/loganalizer.git
cd loganalizer
```

### 2. Criar e ativar o ambiente virtual (Python 3.11+)
Com `uv`:
```bash
uv add -r requirements.txt
source .venv/bin/activate
```
Ou com `venv` padrão:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Iniciar o servidor
```bash
python app.py
```
Acesse no navegador: **`http://localhost:5000`**

---

## ☸️ Implantação no OpenShift

O projeto já contém o manifesto completo em [`openshift/loganalizer.yaml`](openshift/loganalizer.yaml), configurado para o namespace **`detran-apps-internos`** e integrado ao **PostgreSQL 15** existente.

### Recursos Inclusos no Manifesto:
1. **`ImageStream`**: `loganalizer`
2. **`BuildConfig`**: Puxa diretamente do repositório público `https://github.com/kassi0/loganalizer` (branch `master`) e executa o build via Docker Strategy.
3. **`Secret`** (`loganalizer-pg-secret`):
   - Conexão ao serviço de banco `postgres:5432`
   - Usuário: `downdetector`
   - Senha: `down@2024`
   - Banco de Dados: `loganalizer`
4. **`Deployment`**: 1 réplica, com probes de liveness/readiness configurados, limites de recursos e variáveis de ambiente injetadas.
5. **`Service`**: Porta `8080` (HTTP).
6. **`Route`**: Rota externa com terminação TLS *edge* e redirecionamento HTTPS automático.

### Como aplicar no cluster OpenShift:

1. **Faça login no cluster e selecione o namespace:**
   ```bash
   oc project detran-apps-internos
   ```

2. **Aplique todos os recursos:**
   ```bash
   oc apply -f openshift/loganalizer.yaml
   ```

3. **Inicie o primeiro build da imagem:**
   ```bash
   oc start-build loganalizer --follow
   ```

4. **Acompanhe o rollout do pod:**
   ```bash
   oc rollout status deployment/loganalizer
   ```

5. **Obtenha a URL pública gerada pela Route:**
   ```bash
   oc get route loganalizer
   ```

---

## 📄 Formato de Log Suportado

O sistema aceita arquivos padrão **Microsoft IIS W3C Extended Log Format** (`.log`, `.txt`), reconhecendo dinamicamente as colunas definidas no cabeçalho `#Fields:`, como por exemplo:
```text
#Fields: date time s-ip cs-method cs-uri-stem cs-uri-query s-port cs-username c-ip cs(User-Agent) cs(Referer) sc-status sc-substatus sc-win32-status time-taken
```

---

## 👤 Autor
Desenvolvido por **Kassio** / DETRAN.

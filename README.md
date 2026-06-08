# PI5: Aplicações de Inteligência Artificial - API (Motor de Decisão)

Repositório oficial do back-end (API) do Projeto Integrador 5 (PI5). Este microsserviço atua como o núcleo analítico do agente computacional PalermaBot, sendo responsável por receber o estado do tabuleiro dinâmico, computar as possibilidades de ação e retornar a melhor jogada de forma autônoma e em tempo real.

---

## 1. Arquitetura e Modelo de IA

O objetivo deste componente é atuar como o motor de tomada de decisão do agente. A arquitetura afasta-se de modelos probabilísticos ou redes neurais tradicionais, adotando uma abordagem de **Inteligência Artificial Simbólica baseada em Busca Heurística (Lookahead / Greedy Search)**.

A cada turno, a API recebe o estado atual da matriz tridimensional do jogo (grade 5x5 com níveis altimétricos de 0 a 4). O algoritmo analisa o posicionamento de todas as entidades, gera o espaço de estados para movimentos e construções válidas, avalia matematicamente a utilidade desses cenários por meio de uma Função Heurística e devolve a resposta ideal ao orquestrador central.

---

## 2. Estrutura do Projeto

A organização dos arquivos segue padrões de design de software para microsserviços em Python (FastAPI), garantindo a separação entre a camada de roteamento HTTP e a lógica de negócio:

* **`app/main.py`**: Pontos de entrada (Endpoints) e configuração central da API.
* **`app/logic.py`**: Algoritmos de busca, função heurística e regras de tomada de decisão.
* **`app/schemas.py`**: Modelos de dados e validações estruturais estritas (utilizando Pydantic).
* **`Procfile`**: Instrução de inicialização automatizada para o ambiente de produção.
* **`requirements.txt`**: Declaração de dependências e bibliotecas do ecossistema.

---

## 3. Especificação dos Endpoints

A comunicação com a API é assíncrona e baseada no padrão RESTful:

* **`GET /health`**: Retorna o estado operacional atual do servidor e a data corrente, validando a disponibilidade do microsserviço na infraestrutura de nuvem.
* **`POST /move`**: Recebe o payload com o estado do turno atual (`turn_phase`, matriz `board` e identificador `your_team`). Retorna um objeto validado detalhando a entidade a ser movida e as coordenadas de destino e construção.

---

## 4. Instruções de Execução Local

Para configurar e executar o servidor em um ambiente de desenvolvimento local, siga as etapas abaixo:

**1. Clone o repositório para a sua máquina local:**

```bash
git clone [https://github.com/EricDonat0/pi5-api-ai.git](https://github.com/EricDonat0/pi5-api-ai.git)
```

**2. Navegue até o diretório do projeto:**

```bash
cd pi5-api-ai
```

**3. Crie e ative um ambiente virtual (Recomendado):**

* No sistema operacional Windows:
```bash
python -m venv venv
.\venv\Scripts\activate
```

* No sistema operacional Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

**4. Instale as dependências declaradas:**

```bash
pip install -r requirements.txt
```

**5. Inicie o servidor local:**

```bash
uvicorn app.main:app --reload
```

O servidor local estará ativo e acessível através do endereço de loopback `http://127.0.0.1:8000`. A documentação interativa da API (Swagger UI) pode ser acessada em `http://127.0.0.1:8000/docs`.

---

## 5. Implantação e Infraestrutura (Deploy)

A infraestrutura de produção deste back-end está implantada na plataforma de nuvem **Railway**. O processo de integração contínua (CI/CD) está atrelado à branch principal deste repositório. O comando de inicialização é gerenciado deterministicamente pelo arquivo `Procfile`, que instrui o driver de execução conteinerizada a iniciar o servidor através do seguinte comando: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
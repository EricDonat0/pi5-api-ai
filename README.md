# PI5 API AI

API de jogadores autônomos para o projeto PI5 - Aplicações de IA, construída em Python com FastAPI.

Este repositório contém os motores de decisão responsáveis por controlar agentes artificiais em um jogo de estratégia determinístico, em tabuleiro 5x5, inspirado em mecânicas de movimentação, construção e vitória por elevação similares ao jogo Santorini.

O projeto foi estruturado para fins acadêmicos, permitindo comparar diferentes abordagens de inteligência artificial: heurística gulosa, lookahead tático e busca adversarial com poda alfa-beta.

---

## Sumário

- [Visão geral](#visão-geral)
- [Objetivos da API](#objetivos-da-api)
- [Modelo do jogo](#modelo-do-jogo)
- [Arquitetura do projeto](#arquitetura-do-projeto)
- [Jogadores implementados](#jogadores-implementados)
- [Endpoints principais](#endpoints-principais)
- [Fluxo de decisão da IA](#fluxo-de-decisão-da-ia)
- [Schemas de entrada e saída](#schemas-de-entrada-e-saída)
- [PalermaBot_1: lógica V1](#palermabot_1-lógica-v1)
- [palerma_Lookahead_v2_turbo_vtec: lógica V2](#palermalookaheadv2turbovtec-lógica-v2)
- [Eriguei: lógica V3](#eriguei-lógica-v3)
- [Instalação e execução](#instalação-e-execução)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Testes manuais com curl](#testes-manuais-com-curl)
- [Estratégias de competição](#estratégias-de-competição)
- [Cuidados técnicos](#cuidados-técnicos)
- [Possíveis melhorias futuras](#possíveis-melhorias-futuras)
- [Licença e contexto acadêmico](#licença-e-contexto-acadêmico)

---

## Visão geral

O `pi5-api-ai` é uma API FastAPI que expõe endpoints de movimento para bots de IA.

Cada bot recebe o estado completo da partida e devolve uma decisão no formato esperado pelo orquestrador do jogo.

A API não controla a partida inteira. Ela atua como um jogador autônomo chamado pelo backend principal da competição.

Fluxo conceitual:

```text
Backend da competição
        ↓
POST /move ou /move-v2 ou /move-v3
        ↓
API do bot recebe o estado atual
        ↓
Motor de decisão escolhe jogada
        ↓
API devolve movimento ao orquestrador
```

---

## Objetivos da API

Os principais objetivos deste projeto são:

1. Implementar agentes autônomos capazes de jogar o jogo proposto.
2. Comparar diferentes estratégias de tomada de decisão.
3. Criar uma base modular para experimentação com IA em jogos.
4. Garantir compatibilidade com o contrato HTTP do orquestrador.
5. Reduzir falhas técnicas como timeout, jogadas inválidas ou respostas malformadas.
6. Documentar e organizar a evolução dos agentes de IA.

---

## Modelo do jogo

O jogo ocorre em um tabuleiro 5x5.

Cada célula possui:

- um nível de construção;
- opcionalmente, um professor posicionado.

Os níveis vão de 0 a 4:

```text
0: chão inicial
1: primeiro nível
2: segundo nível
3: nível de vitória
4: cúpula ou bloqueio máximo
```

Cada time possui dois professores:

```text
Time 1: CLARO e REY
Time 2: KARIN e BEATRIZ
```

As direções possíveis são as oito casas adjacentes:

```python
DIRECOES = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]
```

Em cada turno normal, a IA deve:

```text
1. Escolher um professor próprio.
2. Mover para uma casa adjacente válida.
3. Construir em uma casa adjacente ao novo destino.
```

Condição de vitória:

```text
Se um professor se move para uma casa de nível 3, o jogador vence.
```

---

## Arquitetura do projeto

Estrutura esperada:

```text
app/
  main.py
  schemas.py
  logic_v1.py
  logic_v2.py
  logic_v3.py
```

Responsabilidades principais:

```text
main.py
  Define a API FastAPI e os endpoints HTTP.

schemas.py
  Define os modelos de entrada e saída usados pela API.

logic_v1.py
  Implementa o PalermaBot_1 com heurística direta.

logic_v2.py
  Implementa o palerma_Lookahead_v2_turbo_vtec com lookahead tático.

logic_v3.py
  Implementa o Eriguei com busca adversarial Negamax e poda alfa-beta.
```

---

## Jogadores implementados

### PalermaBot_1

Arquivo:

```text
app/logic_v1.py
```

Endpoint sugerido:

```text
POST /move
```

Tipo de IA:

```text
Heurística gulosa com avaliação imediata de movimento e construção.
```

### palerma_Lookahead_v2_turbo_vtec

Arquivo:

```text
app/logic_v2.py
```

Endpoint sugerido:

```text
POST /move-v2
```

Tipo de IA:

```text
Lookahead tático de um turno com avaliação de ameaças, bloqueios e mobilidade.
```

### Eriguei

Arquivo:

```text
app/logic_v3.py
```

Endpoint sugerido:

```text
POST /move-v3
```

Tipo de IA:

```text
Busca adversarial com Negamax, poda alfa-beta, tabela de transposição e limite de tempo.
```

---

## Endpoints principais

### Health check

```http
GET /health
```

Retorna o estado da API.

Exemplo:

```json
{
  "status": "online",
  "time": "2026-06-09T12:00:00"
}
```

### Movimento da IA V1

```http
POST /move
```

Usado para o PalermaBot_1.

### Movimento da IA V2

```http
POST /move-v2
```

Usado para o palerma_Lookahead_v2_turbo_vtec.

### Movimento da IA V3

```http
POST /move-v3
```

Usado para o Eriguei.

---

## Exemplo de `main.py` com três bots

```python
from fastapi import FastAPI, HTTPException
from app.schemas import AITurnRequest, TurnPhase

from app.logic_v1 import choose_setup as setup_v1, choose_turn as turn_v1
from app.logic_v2 import choose_setup as setup_v2, choose_turn as turn_v2
from app.logic_v3 import choose_setup as setup_v3, choose_turn as turn_v3

app = FastAPI(title="PalermaBot API")

@app.get("/health")
async def health_check():
    import datetime
    return {"status": "online", "time": datetime.datetime.now().isoformat()}

@app.post("/move")
async def move_bot_v1(body: AITurnRequest):
    if body.turn_phase == TurnPhase.SETUP:
        return setup_v1(body.board)
    return turn_v1(body.board, int(body.your_team))

@app.post("/move-v2")
async def move_bot_v2(body: AITurnRequest):
    if body.turn_phase == TurnPhase.SETUP:
        return setup_v2(body.board, int(body.your_team))
    return turn_v2(body.board, int(body.your_team))

@app.post("/move-v3")
async def move_bot_v3(body: AITurnRequest):
    if body.turn_phase == TurnPhase.SETUP:
        return setup_v3(body.board, int(body.your_team))
    return turn_v3(body.board, int(body.your_team))
```

---

## Fluxo de decisão da IA

Cada bot segue o mesmo contrato geral:

```text
1. Recebe AITurnRequest.
2. Verifica a fase do turno.
3. Se for setup, retorna uma posição de posicionamento.
4. Se for turno normal, escolhe professor, destino e construção.
5. Retorna um PlayerTurnResponse.
```

Fluxo simplificado:

```text
AITurnRequest
    ↓
Identificar fase
    ↓
setup_placement?
    ↓ sim                  ↓ não
choose_setup()             choose_turn()
    ↓                      ↓
SetupResponse              PlayerTurnResponse
```

---

## Schemas de entrada e saída

A API trabalha com modelos definidos em `schemas.py`.

### Entrada de turno

O orquestrador envia um corpo contendo informações como:

```json
{
  "game_id": "uuid-da-partida",
  "turn_number": 5,
  "turn_phase": "player_turn",
  "your_team": 1,
  "professor_to_place": null,
  "board": [[...]]
}
```

### Saída de setup

```json
{
  "row": 2,
  "col": 2
}
```

### Saída de turno

```json
{
  "professor": "CLARO",
  "move_to": {
    "row": 2,
    "col": 3
  },
  "mentor_at": {
    "row": 3,
    "col": 3
  }
}
```

Em algumas regras, `mentor_at` pode ser omitido ou enviado como `null` quando o movimento já é uma vitória imediata.

---

## PalermaBot_1: lógica V1

O PalermaBot_1 é a primeira versão do agente.

Ele usa uma abordagem heurística direta, também chamada de gulosa, pois avalia as jogadas disponíveis no turno atual e escolhe a que tem maior pontuação imediata.

### Estratégia de setup

A V1 prioriza posições centrais por uma lista fixa:

```python
preferencias = [
    (2, 2),
    (1, 2), (2, 1), (2, 3), (3, 2),
    (1, 1), (1, 3), (3, 1), (3, 3)
]
```

A ideia é controlar o centro do tabuleiro, pois casas centrais têm mais mobilidade.

Se nenhuma posição preferida estiver livre, a IA escolhe aleatoriamente uma casa válida:

```python
candidates = [
    (r, c)
    for r in range(5)
    for c in range(5)
    if board[r][c].level == 0 and board[r][c].professor is None
]
```

### Estratégia de turno

A V1 procura todos os movimentos válidos e todas as construções possíveis após cada movimento.

Para cada combinação, calcula uma nota:

```python
nota = avaliar_estado(
    mov_r,
    mov_c,
    casa_mov.level,
    bld_r,
    bld_c,
    board[bld_r][bld_c].level,
    inimigos_posicoes
)
```

A melhor jogada encontrada é retornada.

### Critérios de pontuação

A função `avaliar_estado` considera:

- altura alcançada;
- criação de degrau para vitória futura;
- proximidade do centro;
- bloqueio de inimigo no nível 2;
- risco de entregar casa nível 3 para o adversário;
- risco de ficar perto de inimigo que pode responder.

Exemplo:

```python
pontos = lvl_novo * 1000
```

Isso significa que estar em níveis mais altos é valorizado.

Bloqueio crítico:

```python
if inimigo["lvl"] == 2 and dist_inimigo_bld <= 1:
    if novo_lvl_construido == 4:
        pontos += 8000
```

Erro crítico:

```python
elif novo_lvl_construido == 3:
    pontos -= 10000
```

Esse trecho evita construir uma casa nível 3 ao lado de um inimigo que já está no nível 2.

### Pontos fortes

- Simples e rápida.
- Baixo risco de timeout.
- Fácil de entender e alterar.
- Boa contra bots muito simples.
- Usa noções importantes de altura, centro e bloqueio.

### Limitações

- Não simula profundamente o adversário.
- Pode escolher uma jogada boa no curto prazo, mas ruim no turno seguinte.
- Não detecta sequências longas de vitória forçada.
- Depende muito dos pesos escolhidos manualmente.

---

## palerma_Lookahead_v2_turbo_vtec: lógica V2

A V2 é uma evolução tática da V1.

Ela mantém heurísticas, mas passa a analisar melhor o estado resultante da jogada e o impacto no próximo turno.

### Estrutura auxiliar

A V2 usa dataclasses para organizar o estado:

```python
@dataclass(frozen=True)
class ProfessorState:
    nome: str
    r: int
    c: int
    lvl: int

@dataclass(frozen=True)
class Jogada:
    professor: str
    origem: Tuple[int, int]
    destino: Tuple[int, int]
    build: Optional[Tuple[int, int]]
```

Isso torna o código mais legível e mais próximo de uma modelagem formal do jogo.

### Geração de jogadas

A função `gerar_jogadas` enumera todos os movimentos legais:

```python
def gerar_jogadas(board: list[list[Cell]], professores: List[str]) -> List[Jogada]:
    jogadas: List[Jogada] = []
```

Se uma jogada chega ao nível 3, ela é adicionada como vitória imediata:

```python
if board[destino[0]][destino[1]].level == WIN_LEVEL:
    jogadas.append(Jogada(aliado.nome, origem, destino, build=None))
    continue
```

### Lookahead de um turno

A V2 aplica a jogada internamente e avalia o estado posterior:

```python
levels_pos, professores_pos = aplicar_jogada(board, jogada)
```

Depois avalia:

- quantos turnos legais o próprio time terá;
- quantos turnos legais o inimigo terá;
- quantas vitórias imediatas o inimigo terá;
- quantas vitórias imediatas o próprio time terá.

Exemplo:

```python
vitorias_inimigo = contar_vitorias_imediatas(
    levels_pos,
    professores_pos,
    inimigos_professores
)

pontos -= vitorias_inimigo * PESO_INIMIGO_VENCE_PROXIMO
```

Isso faz a IA evitar jogadas que entregam vitória imediata.

### Pesos estratégicos

A V2 define pesos centrais:

```python
PESO_VITORIA_PROXIMO_TURNO = 35_000
PESO_BLOQUEIO_VITORIA = 160_000
PESO_DAR_VITORIA_AO_INIMIGO = 180_000
PESO_INIMIGO_VENCE_PROXIMO = 140_000
```

Esses pesos deixam clara a prioridade da IA:

```text
1. Bloquear vitória inimiga.
2. Nunca entregar vitória ao adversário.
3. Criar ameaça própria.
4. Ganhar mobilidade e altura.
```

### Pontuação de construção

A função `pontuar_construcao` diferencia construções ofensivas e defensivas.

Bloquear uma ameaça inimiga:

```python
if build in ameacas_antes and nivel_depois == MAX_LEVEL:
    pontos += PESO_BLOQUEIO_VITORIA
```

Evitar entregar vitória:

```python
if build_ajuda_inimigo_a_vencer(board, build, inimigos_antes):
    pontos -= PESO_DAR_VITORIA_AO_INIMIGO
```

### Pontos fortes

- Mais segura que a V1.
- Detecta ameaças imediatas.
- Melhora a defesa contra vitórias no próximo turno.
- Avalia mobilidade própria e inimiga.
- Possui código mais estruturado.

### Limitações

- Ainda não realiza busca profunda de vários turnos.
- Pode não encontrar vitórias forçadas com mais de uma resposta.
- Ainda depende bastante dos pesos heurísticos.
- É mais lenta que a V1, embora ainda seja leve.

---

## Eriguei: lógica V3

O Eriguei é a versão mais avançada.

Ele usa busca adversarial com Negamax, poda alfa-beta, aprofundamento iterativo, tabela de transposição e limite de tempo.

Essa abordagem é mais próxima de agentes clássicos usados em jogos determinísticos de informação perfeita.

### Representação interna do estado

A V3 converte o tabuleiro em uma estrutura imutável:

```python
@dataclass(frozen=True)
class GameState:
    levels: Tuple[int, ...]
    positions: Tuple[int, int, int, int]
```

Em vez de trabalhar diretamente com matriz 5x5, o estado usa:

```text
levels: níveis das 25 casas
positions: posição de CLARO, REY, KARIN e BEATRIZ
```

Isso torna o estado:

- mais barato de copiar;
- mais fácil de comparar;
- adequado para cache;
- adequado para tabela de transposição.

### Geração de jogadas

A V3 trabalha com jogadas internas:

```python
@dataclass(frozen=True)
class SearchMove:
    prof_idx: int
    from_idx: int
    to_idx: int
    build_idx: Optional[int]
    is_win: bool = False
```

Essa estrutura permite diferenciar rapidamente jogadas normais e jogadas vencedoras.

### Negamax

A busca principal usa Negamax:

```python
score = -self.negamax(child, next_team, depth - 1, -beta, -alpha, ply + 1)
```

A ideia é que uma posição boa para o adversário é ruim para o jogador atual.

Isso simplifica a implementação do Minimax.

### Poda alfa-beta

A poda alfa-beta evita analisar ramos que não podem melhorar a decisão final:

```python
alpha = max(alpha, score)
if alpha >= beta:
    break
```

Essa técnica permite analisar mais profundamente dentro do mesmo limite de tempo.

### Aprofundamento iterativo

A V3 busca em profundidades crescentes:

```python
for depth in range(1, MAX_SEARCH_DEPTH + 1):
    ...
```

Se o tempo acabar, a IA mantém a melhor jogada encontrada na última profundidade completa.

Isso é importante em ambiente de API, pois evita timeout.

### Limite de tempo

A V3 usa variáveis de ambiente:

```python
MAX_SEARCH_DEPTH = int(os.getenv("PALERMA_MAX_SEARCH_DEPTH", "4"))
SEARCH_TIME_LIMIT_SECONDS = float(os.getenv("PALERMA_SEARCH_TIME_SECONDS", "0.75"))
```

Esses parâmetros controlam o equilíbrio entre força e segurança.

Exemplo conservador:

```env
PALERMA_SEARCH_TIME_SECONDS=0.25
PALERMA_MAX_SEARCH_DEPTH=3
```

Exemplo competitivo:

```env
PALERMA_SEARCH_TIME_SECONDS=0.75
PALERMA_MAX_SEARCH_DEPTH=4
```

### Tabela de transposição

A V3 armazena avaliações de estados já analisados:

```python
self.tt: Dict[
    Tuple[Tuple[int, ...], Tuple[int, int, int, int], int, int],
    TTEntry
] = {}
```

Isso reduz recálculo em posições que podem ser alcançadas por ordens diferentes de jogadas.

### Heurística estática

Quando a busca chega ao limite de profundidade, a V3 chama:

```python
evaluate_state(state, team_id)
```

A avaliação considera:

- altura dos professores;
- mobilidade;
- controle do centro;
- ameaças imediatas;
- ameaças duplas;
- risco de travamento;
- coordenação entre professores;
- pressão ofensiva e defensiva.

Exemplo de ameaça imediata:

```python
score += len(my_threats) * 140_000
score -= len(enemy_threats) * 180_000
```

A ameaça inimiga pesa mais que a própria ameaça, tornando a IA mais conservadora em posições perigosas.

### Fallback de segurança

Se a busca não completar a tempo, a V3 usa uma jogada fallback:

```python
best_move = self._fallback_move(state, team_id, root_moves)
```

Esse fallback tenta evitar principalmente:

- entregar vitória imediata;
- deixar de bloquear ameaça clara;
- retornar `None` quando há jogada legal;
- estourar o tempo da requisição.

### Pontos fortes

- Considera a melhor resposta do adversário.
- Busca múltiplos turnos à frente.
- Possui poda alfa-beta.
- Usa cache por tabela de transposição.
- Tem limite de tempo configurável.
- Tem fallback em caso de busca incompleta.
- É a arquitetura mais competitiva entre as três.

### Limitações

- Mais complexa.
- Mais sensível a timeout.
- Depende de calibração de profundidade e tempo.
- Pode precisar de ajustes finos nos pesos heurísticos.
- Em produção, logs e métricas são importantes para diagnosticar derrotas.

---

## Instalação e execução

### Pré-requisitos

- Python 3.10 ou superior;
- FastAPI;
- Uvicorn;
- dependências do projeto instaladas.

### Instalação

```bash
pip install -r requirements.txt
```

### Execução local

```bash
uvicorn app.main:app --reload
```

A API ficará disponível em:

```text
http://127.0.0.1:8000
```

### Documentação automática

FastAPI disponibiliza documentação interativa em:

```text
http://127.0.0.1:8000/docs
```

E documentação alternativa em:

```text
http://127.0.0.1:8000/redoc
```

---

## Variáveis de ambiente

A V3 pode ser configurada por variáveis de ambiente.

```env
PALERMA_SEARCH_TIME_SECONDS=0.75
PALERMA_MAX_SEARCH_DEPTH=4
```

Recomendações:

```text
Ambiente com timeout curto:
PALERMA_SEARCH_TIME_SECONDS=0.25
PALERMA_MAX_SEARCH_DEPTH=3

Ambiente equilibrado:
PALERMA_SEARCH_TIME_SECONDS=0.50
PALERMA_MAX_SEARCH_DEPTH=4

Ambiente com tempo confortável:
PALERMA_SEARCH_TIME_SECONDS=1.00
PALERMA_MAX_SEARCH_DEPTH=5
```

---

## Testes manuais com curl

### Health check

```bash
curl http://127.0.0.1:8000/health
```

### Setup

```bash
curl -X POST http://127.0.0.1:8000/move-v3 \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": "teste",
    "turn_number": 1,
    "turn_phase": "setup_placement",
    "your_team": 1,
    "professor_to_place": "CLARO",
    "board": [
      [{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null}],
      [{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null}],
      [{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null}],
      [{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null}],
      [{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null},{"level":0,"professor":null}]
    ]
  }'
```

Resposta esperada:

```json
{
  "row": 2,
  "col": 2
}
```

---

## Estratégias de competição

Para competição entre IAs, recomenda-se avaliar cada bot em múltiplas partidas e alternar os lados.

Exemplo:

```text
Bot A como Time 1 contra Bot B como Time 2
Bot B como Time 1 contra Bot A como Time 2
```

Isso evita conclusões incorretas caso exista vantagem de slot, ordem de setup ou primeira jogada.

Também é recomendado registrar:

- número do turno final;
- vencedor;
- motivo da vitória;
- se houve timeout;
- se houve jogada inválida;
- lado de cada bot;
- configuração de profundidade e tempo.

---

## Cuidados técnicos

### Evitar timeout

Bots com busca profunda podem perder por timeout antes mesmo de perder estrategicamente.

Ajuste:

```env
PALERMA_SEARCH_TIME_SECONDS
PALERMA_MAX_SEARCH_DEPTH
```

### Validar `your_team`

A IA depende do campo `your_team` para saber quais professores controla.

```python
TEAM_TO_PROF_INDEXES = {
    1: (PROF_TO_INDEX["CLARO"], PROF_TO_INDEX["REY"]),
    2: (PROF_TO_INDEX["KARIN"], PROF_TO_INDEX["BEATRIZ"]),
}
```

Se o backend enviar `your_team` incorreto, o bot pode tentar mover professores adversários.

### Sempre retornar jogada válida

Quando não há jogada possível, a IA pode retornar `None`, mas em ambiente de competição isso pode ser tratado como derrota.

Por isso, sempre que possível, os motores devem:

- gerar todas as jogadas válidas;
- priorizar vitória imediata;
- evitar movimentos ilegais;
- retornar fallback seguro.

### Cuidado com `mentor_at`

Alguns validadores aceitam `mentor_at = null` em jogadas vencedoras. Outros exigem uma construção mesmo após o movimento.

Se houver rejeição por schema, adapte a resposta para sempre incluir uma construção válida quando possível.

---

## Possíveis melhorias futuras

- Criar suíte automatizada de testes unitários para geração de jogadas.
- Criar simulador local de partidas entre bots.
- Registrar logs estruturados por turno.
- Persistir histórico de decisões da IA.
- Criar ferramenta de self-play para calibrar pesos.
- Implementar análise estatística de vitórias por slot.
- Adicionar replay de partidas.
- Diferenciar derrota por regra e derrota por erro técnico.
- Implementar cache persistente para aberturas.
- Criar livro de aberturas baseado em resultados simulados.
- Testar Monte Carlo Tree Search como alternativa experimental.

---

## Licença e contexto acadêmico

Este projeto foi desenvolvido no contexto da disciplina PI5 - Aplicações de IA.

Seu objetivo é demonstrar a construção de agentes inteligentes autônomos aplicados a jogos de estratégia, explorando desde heurísticas simples até busca adversarial com técnicas clássicas de inteligência artificial.
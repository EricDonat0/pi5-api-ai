# Documentação Técnica da Inteligência Artificial - Agente PalermaBot

Este documento detalha a arquitetura, a modelagem estratégica e o funcionamento da Inteligência Artificial (IA) que compõe o núcleo decisório do agente computacional **PalermaBot**, desenvolvido para o torneio da disciplina de Projeto Integrador 5.

## 1. Arquitetura da Inteligência Artificial: Heurística Simbólica

Diferentemente de modelos baseados em Aprendizado de Máquina (*Machine Learning*), como Redes Neurais Artificiais ou Aprendizado por Reforço, o PalermaBot não requer o processamento de grandes volumes de dados ou execuções prévias para calibração de pesos.

O agente emprega uma arquitetura de **Inteligência Artificial Simbólica baseada em Busca Heurística (Abordagem Gulosa e Antecipação/Lookahead)**. Trata-se de um modelo estritamente determinístico, no qual as regras de domínio e a expertise do jogo são modeladas matematicamente por meio de uma Função de Avaliação. A cada turno, o algoritmo gera uma árvore de estados futuros possíveis, calcula o valor de utilidade de cada estado e executa a jogada que maximiza as probabilidades de vitória. Esta abordagem garante eficiência computacional e respostas em tempo real viáveis para execução em infraestrutura de nuvem baseada em microsserviços.

## 2. Modelagem Estratégica de Jogo

O ambiente do jogo é fundamentado em mecânicas de posicionamento tridimensional em uma matriz 5x5, exigindo controle territorial e vantagem altimétrica. A lógica do agente foi segmentada nas duas fases inerentes à partida:

### 2.1. Fase de Posicionamento Inicial (Setup)
O objetivo principal na fase inicial é o **Domínio Territorial**. Agentes restritos às bordas ou vértices da matriz sofrem drástica redução em seus graus de liberdade (limitados a 3 ou 5 casas adjacentes). 

A rotina de alocação do PalermaBot busca sistematicamente o controle das coordenadas centrais, priorizando a posição absoluta `(2,2)`, seguida pelo perímetro interno. Essa diretriz assegura alcance geográfico, maximizando as opções na árvore de decisão logo no primeiro turno da partida.

### 2.2. Fase de Turno (Batalha)
Em cada turno regular, o agente realiza um escaneamento completo da matriz, identificando as coordenadas de entidades aliadas e adversárias. O algoritmo aplica permutação para todas as movimentações válidas (deslocamento unitário com variação máxima de +1 nível) e, subsequentemente, itera sobre todas as opções legais de construção (mentoria) adjacentes a cada novo estado de movimento.

A escolha da jogada ideal é determinada pela Função Heurística detalhada na seção a seguir.

## 3. Função Heurística e Sistema de Avaliação

A validação de cada combinação possível de [Movimento + Construção] é submetida a uma função de avaliação matemática (`avaliar_estado`). O estado que retornar a maior pontuação (Score) ditará a resposta do agente à API. Os pesos foram calibrados conforme os seguintes critérios de prioridade:

* **Condição de Vitória Imediata (+10.000 pontos):** Trata-se da prioridade máxima do sistema. Caso a simulação identifique uma ramificação onde a entidade aliada pode acessar uma célula de Nível 3 (Graduação) no turno corrente, a função ignora todas as restrições secundárias e executa o movimento, finalizando a partida.
* **Bloqueio Estratégico do Adversário (+8.000 pontos):** O algoritmo implementa monitoramento defensivo contínuo. Se um agente adversário estiver alocado em uma célula de Nível 2 (iminência de vitória) e o PalermaBot detiver alcance para construir no entorno desse adversário, o sistema priorizará a elevação daquela célula para os níveis 3 ou 4. Essa ação quebra a rota de progressão do oponente.
* **Vantagem Altimétrica (+1.000 pontos por Nível):** A heurística valoriza a verticalidade. Movimentos que resultam na elevação da peça aliada recebem bonificação proporcional ao nível alcançado, garantindo superioridade tática de mobilidade ao longo do tempo.
* **Penalidade por Afastamento Radial (-10 pontos por unidade espacial):** Para mitigar o risco de isolamento, a função aplica um fator de penalidade baseado na Distância de Manhattan em relação ao centro geométrico da matriz. Movimentos periféricos reduzem o Score final da jogada simulada.
* **Mitigação de Ameaças (-500 pontos):** O sistema realiza previsões de risco. Caso o movimento projetado coloque o agente sob o alcance direto de um adversário posicionado em um nível igual ou superior, uma penalidade severa é aplicada, evitando o encurralamento da peça aliada.

## 4. Fluxo de Execução Técnica e Integração

O agente está encapsulado em uma API RESTful desenvolvida em Python (Framework FastAPI). O fluxo de processamento por turno ocorre na seguinte ordem cronológica:

1. O orquestrador do torneio enviay uma requisição `POST` para o endpoint `/move`, carregando o payload JSON representativo do estado atual do tabuleiro.
2. A requisição é validada por meio de schemas tipados (*Pydantic*).
3. A camada de controle repassa a matriz de objetos para a lógica de negócio (`logic.py`).
4. O algoritmo gera o espaço de estados, calcula a Função Heurística para todas as interações e identifica o Score máximo.
5. A resposta é formatada e devolvida ao orquestrador da partida, respeitando estritamente o tempo limite (timeout) e os padrões estruturais estipulados pela arquitetura do Projeto Integrador.

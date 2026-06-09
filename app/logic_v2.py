from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from app.schemas import Cell, PlayerTurnResponse, Position, SetupResponse

# Constantes do tabuleiro
BOARD_SIZE = 5
MAX_LEVEL = 4
WIN_LEVEL = 3
CENTER = (2, 2)
DIRECOES: Tuple[Tuple[int, int], ...] = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
)

# Pesos principais da heurística. Eles ficam centralizados para facilitar calibração.
PESO_VITORIA_PROXIMO_TURNO = 35_000
PESO_BLOQUEIO_VITORIA = 160_000
PESO_DAR_VITORIA_AO_INIMIGO = 180_000
PESO_INIMIGO_VENCE_PROXIMO = 140_000


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


def get_professores_por_time(team_id: int) -> Tuple[List[str], List[str]]:
    meus = ["CLARO", "REY"] if team_id == 1 else ["KARIN", "BEATRIZ"]
    inimigos = ["KARIN", "BEATRIZ"] if team_id == 1 else ["CLARO", "REY"]
    return meus, inimigos


def pos_valida(r: int, c: int) -> bool:
    return 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE


def adjacentes(r: int, c: int) -> Iterable[Tuple[int, int]]:
    for dr, dc in DIRECOES:
        nr, nc = r + dr, c + dc
        if pos_valida(nr, nc):
            yield nr, nc


def distancia_manhattan(a: Tuple[int, int], b: Tuple[int, int] = CENTER) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def distancia_chebyshev(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def board_para_matrizes(board: list[list[Cell]]) -> Tuple[List[List[int]], List[List[Optional[str]]]]:
    levels = [[board[r][c].level for c in range(BOARD_SIZE)] for r in range(BOARD_SIZE)]
    professores = [[board[r][c].professor for c in range(BOARD_SIZE)] for r in range(BOARD_SIZE)]
    return levels, professores


def encontrar_professores(board: list[list[Cell]], nomes: List[str]) -> List[ProfessorState]:
    encontrados: List[ProfessorState] = []
    nomes_set = set(nomes)
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            nome = board[r][c].professor
            if nome in nomes_set:
                encontrados.append(ProfessorState(nome=nome, r=r, c=c, lvl=board[r][c].level))
    return encontrados


def encontrar_professores_matriz(
    levels: List[List[int]],
    professores: List[List[Optional[str]]],
    nomes: List[str],
) -> List[ProfessorState]:
    encontrados: List[ProfessorState] = []
    nomes_set = set(nomes)
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            nome = professores[r][c]
            if nome in nomes_set:
                encontrados.append(ProfessorState(nome=nome, r=r, c=c, lvl=levels[r][c]))
    return encontrados


def choose_setup(board: list[list[Cell]], team_id: int = 1) -> SetupResponse:
    """
    Fase de posicionamento.

    Em vez de seguir só uma lista fixa, pontuamos as casas livres para:
    - manter controle do centro;
    - evitar cantos;
    - separar minimamente os dois professores aliados;
    - não nascer colado em professor inimigo quando houver alternativa.
    """
    meus_professores, inimigos = get_professores_por_time(team_id)
    minhas_posicoes = encontrar_professores(board, meus_professores)
    inimigos_posicoes = encontrar_professores(board, inimigos)

    candidatos = [
        (r, c)
        for r in range(BOARD_SIZE)
        for c in range(BOARD_SIZE)
        if board[r][c].level == 0 and board[r][c].professor is None
    ]

    if not candidatos:
        raise ValueError("Nenhuma casa livre para posicionamento inicial.")

    def pontuar_casa_setup(pos: Tuple[int, int]) -> int:
        r, c = pos
        pontos = 0

        # Centro e anel interno costumam ter mais mobilidade.
        pontos -= distancia_manhattan(pos) * 35
        pontos += sum(1 for nr, nc in adjacentes(r, c) if board[nr][nc].professor is None) * 4

        # Evita canto no setup, pois canto tem só 3 adjacências.
        if r in (0, BOARD_SIZE - 1) and c in (0, BOARD_SIZE - 1):
            pontos -= 45

        # Segundo professor: melhor cobrir outra região sem abandonar o centro.
        for aliado in minhas_posicoes:
            d = abs(r - aliado.r) + abs(c - aliado.c)
            if d == 1:
                pontos -= 25
            elif d in (2, 3):
                pontos += 35
            else:
                pontos += 5

        # Não começar grudado no inimigo se houver outras casas boas.
        for inimigo in inimigos_posicoes:
            d = distancia_chebyshev(pos, (inimigo.r, inimigo.c))
            if d == 1:
                pontos -= 30
            elif d >= 3:
                pontos += 5

        return pontos

    melhor = max(candidatos, key=lambda p: (pontuar_casa_setup(p), -distancia_manhattan(p), -p[0], -p[1]))
    return SetupResponse(row=melhor[0], col=melhor[1])


def movimento_valido(board: list[list[Cell]], origem: Tuple[int, int], destino: Tuple[int, int]) -> bool:
    or_r, or_c = origem
    de_r, de_c = destino
    if not pos_valida(de_r, de_c):
        return False

    casa_destino = board[de_r][de_c]
    return (
        casa_destino.professor is None
        and casa_destino.level < MAX_LEVEL
        and casa_destino.level <= board[or_r][or_c].level + 1
    )


def construcao_valida(
    board: list[list[Cell]],
    origem: Tuple[int, int],
    destino: Tuple[int, int],
    build: Tuple[int, int],
) -> bool:
    b_r, b_c = build
    if not pos_valida(b_r, b_c):
        return False
    if distancia_chebyshev(destino, build) != 1:
        return False
    if build == destino:
        return False
    if board[b_r][b_c].level >= MAX_LEVEL:
        return False

    # Depois do movimento, a origem fica vazia; as demais casas ocupadas continuam bloqueadas.
    return board[b_r][b_c].professor is None or build == origem


def gerar_jogadas(board: list[list[Cell]], professores: List[str]) -> List[Jogada]:
    jogadas: List[Jogada] = []

    for aliado in encontrar_professores(board, professores):
        origem = (aliado.r, aliado.c)
        for destino in adjacentes(aliado.r, aliado.c):
            if not movimento_valido(board, origem, destino):
                continue

            # Entrar no nível 3 vence. Não precisamos exigir construção depois disso.
            if board[destino[0]][destino[1]].level == WIN_LEVEL:
                jogadas.append(Jogada(aliado.nome, origem, destino, build=None))
                continue

            for build in adjacentes(*destino):
                if construcao_valida(board, origem, destino, build):
                    jogadas.append(Jogada(aliado.nome, origem, destino, build))

    return jogadas


def aplicar_jogada(
    board: list[list[Cell]],
    jogada: Jogada,
) -> Tuple[List[List[int]], List[List[Optional[str]]]]:
    levels, professores = board_para_matrizes(board)
    or_r, or_c = jogada.origem
    de_r, de_c = jogada.destino

    professores[or_r][or_c] = None
    professores[de_r][de_c] = jogada.professor

    if jogada.build is not None:
        b_r, b_c = jogada.build
        levels[b_r][b_c] += 1

    return levels, professores


def movimento_valido_matriz(
    levels: List[List[int]],
    professores: List[List[Optional[str]]],
    origem: Tuple[int, int],
    destino: Tuple[int, int],
) -> bool:
    or_r, or_c = origem
    de_r, de_c = destino
    return (
        pos_valida(de_r, de_c)
        and professores[de_r][de_c] is None
        and levels[de_r][de_c] < MAX_LEVEL
        and levels[de_r][de_c] <= levels[or_r][or_c] + 1
    )


def construcao_valida_matriz(
    levels: List[List[int]],
    professores: List[List[Optional[str]]],
    origem: Tuple[int, int],
    destino: Tuple[int, int],
    build: Tuple[int, int],
) -> bool:
    b_r, b_c = build
    if not pos_valida(b_r, b_c):
        return False
    if distancia_chebyshev(destino, build) != 1:
        return False
    if build == destino:
        return False
    if levels[b_r][b_c] >= MAX_LEVEL:
        return False

    return professores[b_r][b_c] is None or build == origem


def contar_movimentos_legais(
    levels: List[List[int]],
    professores: List[List[Optional[str]]],
    nomes: List[str],
) -> int:
    total = 0
    for prof in encontrar_professores_matriz(levels, professores, nomes):
        origem = (prof.r, prof.c)
        for destino in adjacentes(prof.r, prof.c):
            if movimento_valido_matriz(levels, professores, origem, destino):
                total += 1
    return total


def contar_turnos_legais(
    levels: List[List[int]],
    professores: List[List[Optional[str]]],
    nomes: List[str],
) -> int:
    total = 0
    for prof in encontrar_professores_matriz(levels, professores, nomes):
        origem = (prof.r, prof.c)
        for destino in adjacentes(prof.r, prof.c):
            if not movimento_valido_matriz(levels, professores, origem, destino):
                continue
            if levels[destino[0]][destino[1]] == WIN_LEVEL:
                total += 1
                continue
            if any(construcao_valida_matriz(levels, professores, origem, destino, build) for build in adjacentes(*destino)):
                total += 1
    return total


def casas_de_vitoria_imediata(
    levels: List[List[int]],
    professores: List[List[Optional[str]]],
    nomes: List[str],
) -> set[Tuple[int, int]]:
    vitorias: set[Tuple[int, int]] = set()
    for prof in encontrar_professores_matriz(levels, professores, nomes):
        origem = (prof.r, prof.c)
        for destino in adjacentes(prof.r, prof.c):
            if movimento_valido_matriz(levels, professores, origem, destino) and levels[destino[0]][destino[1]] == WIN_LEVEL:
                vitorias.add(destino)
    return vitorias


def contar_vitorias_imediatas(
    levels: List[List[int]],
    professores: List[List[Optional[str]]],
    nomes: List[str],
) -> int:
    return len(casas_de_vitoria_imediata(levels, professores, nomes))


def build_ajuda_inimigo_a_vencer(
    board: list[list[Cell]],
    build: Tuple[int, int],
    inimigos: List[ProfessorState],
) -> bool:
    """
    Detecta o erro mais perigoso: construir uma célula de nível 2 para nível 3
    ao lado de um inimigo que já está no nível 2, entregando a vitória para ele.
    """
    b_r, b_c = build
    if board[b_r][b_c].level != 2:
        return False

    for inimigo in inimigos:
        if inimigo.lvl != 2:
            continue
        if distancia_chebyshev((inimigo.r, inimigo.c), build) == 1:
            # A construção fica vazia depois do turno; se for alcançável, virou vitória adversária.
            return True
    return False


def pontuar_construcao(
    board: list[list[Cell]],
    jogada: Jogada,
    meus_professores: List[str],
    inimigos_professores: List[str],
    levels_pos: List[List[int]],
    professores_pos: List[List[Optional[str]]],
) -> int:
    if jogada.build is None:
        return 0

    pontos = 0
    b_r, b_c = jogada.build
    build = jogada.build
    nivel_antes = board[b_r][b_c].level
    nivel_depois = nivel_antes + 1

    inimigos_antes = encontrar_professores(board, inimigos_professores)
    levels_antes, professores_antes = board_para_matrizes(board)
    ameacas_antes = casas_de_vitoria_imediata(levels_antes, professores_antes, inimigos_professores)

    # Melhor defesa: transformar em cúpula uma casa de nível 3 que o inimigo podia vencer.
    if build in ameacas_antes and nivel_depois == MAX_LEVEL:
        pontos += PESO_BLOQUEIO_VITORIA

    if build_ajuda_inimigo_a_vencer(board, build, inimigos_antes):
        pontos -= PESO_DAR_VITORIA_AO_INIMIGO

    # Construir cúpula sem bloquear ameaça direta às vezes reduz o próprio espaço de jogo.
    if nivel_depois == MAX_LEVEL and build not in ameacas_antes:
        pontos -= 800

    # Construções boas para nós: criar degraus próximos das nossas peças.
    meus_pos = encontrar_professores_matriz(levels_pos, professores_pos, meus_professores)
    for aliado in meus_pos:
        dist = distancia_chebyshev((aliado.r, aliado.c), build)
        if dist != 1:
            continue

        if nivel_depois == WIN_LEVEL and aliado.lvl >= 2:
            pontos += 25_000
        elif nivel_depois == 2 and aliado.lvl >= 1:
            pontos += 1_500
        elif nivel_depois == 1 and aliado.lvl == 0:
            pontos += 500

    # Se a construção aumenta muito a mobilidade/rotas do inimigo, reduza a nota.
    for inimigo in encontrar_professores_matriz(levels_pos, professores_pos, inimigos_professores):
        if distancia_chebyshev((inimigo.r, inimigo.c), build) != 1:
            continue
        if nivel_depois == WIN_LEVEL and inimigo.lvl >= 2:
            pontos -= 45_000
        elif nivel_depois == 2 and inimigo.lvl >= 1:
            pontos -= 1_200

    return pontos


def avaliar_jogada(board: list[list[Cell]], jogada: Jogada, team_id: int) -> int:
    meus_professores, inimigos_professores = get_professores_por_time(team_id)
    levels_pos, professores_pos = aplicar_jogada(board, jogada)

    origem = jogada.origem
    destino = jogada.destino
    nivel_origem = board[origem[0]][origem[1]].level
    nivel_destino = board[destino[0]][destino[1]].level

    pontos = 0

    # Altura importa, mas subir é melhor que apenas permanecer alto.
    pontos += nivel_destino * 1_200
    pontos += (nivel_destino - nivel_origem) * 650

    # Controle do centro e mobilidade.
    pontos -= distancia_manhattan(destino) * 45
    meus_turnos = contar_turnos_legais(levels_pos, professores_pos, meus_professores)
    inimigos_turnos = contar_turnos_legais(levels_pos, professores_pos, inimigos_professores)
    pontos += meus_turnos * 85
    pontos -= inimigos_turnos * 75

    # Lookahead defensivo de 1 turno: nunca entregue vitória imediata.
    vitorias_inimigo = contar_vitorias_imediatas(levels_pos, professores_pos, inimigos_professores)
    pontos -= vitorias_inimigo * PESO_INIMIGO_VENCE_PROXIMO

    # Lookahead ofensivo: criar ameaça real de vitória para a próxima rodada.
    vitorias_minhas = contar_vitorias_imediatas(levels_pos, professores_pos, meus_professores)
    pontos += vitorias_minhas * PESO_VITORIA_PROXIMO_TURNO

    pontos += pontuar_construcao(
        board,
        jogada,
        meus_professores,
        inimigos_professores,
        levels_pos,
        professores_pos,
    )

    # Coordenação: professores aliados muito longe tendem a não criar pressão conjunta.
    meus_pos = encontrar_professores_matriz(levels_pos, professores_pos, meus_professores)
    if len(meus_pos) == 2:
        d = distancia_chebyshev((meus_pos[0].r, meus_pos[0].c), (meus_pos[1].r, meus_pos[1].c))
        if d == 1:
            pontos += 150
        elif d == 2:
            pontos += 300
        else:
            pontos -= 250

    # Desempate leve: preferir jogadas determinísticas e menos periféricas.
    pontos -= destino[0] + destino[1]
    if jogada.build is not None:
        pontos -= jogada.build[0] + jogada.build[1]

    return pontos


def resposta(jogada: Jogada) -> PlayerTurnResponse:
    mentor_at = None if jogada.build is None else Position(row=jogada.build[0], col=jogada.build[1])
    return PlayerTurnResponse(
        professor=jogada.professor,
        move_to=Position(row=jogada.destino[0], col=jogada.destino[1]),
        mentor_at=mentor_at,
    )


def choose_turn(board: list[list[Cell]], team_id: int) -> Optional[PlayerTurnResponse]:
    """
    Fase de turno.

    Lookahead de 1 turno. Prioridades:
    1. vencer imediatamente;
    2. bloquear vitória imediata do adversário;
    3. não criar vitória para o adversário;
    4. criar ameaça própria para o próximo turno;
    5. maximizar altura, centro e mobilidade.
    """
    meus_professores, _ = get_professores_por_time(team_id)
    jogadas = gerar_jogadas(board, meus_professores)

    if not jogadas:
        return None

    # Vitória imediata sempre vence qualquer heurística.
    for jogada in jogadas:
        de_r, de_c = jogada.destino
        if board[de_r][de_c].level == WIN_LEVEL:
            return resposta(jogada)

    melhor_jogada = max(jogadas, key=lambda j: avaliar_jogada(board, j, team_id))
    return resposta(melhor_jogada)

import random
from typing import Optional, List, Tuple
from app.schemas import Cell, SetupResponse, PlayerTurnResponse, Position

DIRECOES = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

def get_professores_por_time(team_id: int) -> Tuple[List[str], List[str]]:
    meus = ["CLARO", "REY"] if team_id == 1 else ["KARIN", "BEATRIZ"]
    inimigos = ["KARIN", "BEATRIZ"] if team_id == 1 else ["CLARO", "REY"]
    return meus, inimigos

def pos_valida(r: int, c: int) -> bool:
    return 0 <= r < 5 and 0 <= c < 5

def choose_setup(board: list[list[Cell]]) -> SetupResponse:
    # Prioriza o centro e os aneis internos para domínio territorial inicial
    preferencias = [(2, 2), (1, 2), (2, 1), (2, 3), (3, 2), (1, 1), (1, 3), (3, 1), (3, 3)]
    for r, c in preferencias:
        if board[r][c].level == 0 and board[r][c].professor is None:
            return SetupResponse(row=r, col=c)
            
    # Fallback aleatório caso as coordenadas ideais estejam ocupadas
    candidates = [(r, c) for r in range(5) for c in range(5) if board[r][c].level == 0 and board[r][c].professor is None]
    row, col = random.choice(candidates)
    return SetupResponse(row=row, col=col)

def choose_turn(board: list[list[Cell]], team_id: int) -> Optional[PlayerTurnResponse]:
    meus_professores, inimigos = get_professores_por_time(team_id)
    melhor_jogada = None
    melhor_nota = -float('inf')
    minhas_posicoes = []
    inimigos_posicoes = []
    
    # Mapeamento do estado atual das entidades no grid
    for r in range(5):
        for c in range(5):
            prof = board[r][c].professor
            if prof in meus_professores:
                minhas_posicoes.append({"nome": prof, "r": r, "c": c, "lvl": board[r][c].level})
            elif prof in inimigos:
                inimigos_posicoes.append({"nome": prof, "r": r, "c": c, "lvl": board[r][c].level})

    for aliado in minhas_posicoes:
        for dr, dc in DIRECOES:
            mov_r, mov_c = aliado["r"] + dr, aliado["c"] + dc
            
            # Validação do movimento (limites da matriz, ocupação e altura máxima permitida)
            if pos_valida(mov_r, mov_c):
                casa_mov = board[mov_r][mov_c]
                if casa_mov.professor is None and casa_mov.level <= aliado["lvl"] + 1 and casa_mov.level < 4:
                    
                    # Condição de Vitória
                    if casa_mov.level == 3:
                        for br, bc in DIRECOES:
                            bld_r, bld_c = mov_r + br, mov_c + bc
                            if pos_valida(bld_r, bld_c) and (board[bld_r][bld_c].professor is None or (bld_r == aliado["r"] and bld_c == aliado["c"])) and board[bld_r][bld_c].level < 4:
                                return PlayerTurnResponse(professor=aliado["nome"], move_to=Position(row=mov_r, col=mov_c), mentor_at=Position(row=bld_r, col=bld_c))

                    # Permutação de Construções para o movimento atual
                    for br, bc in DIRECOES:
                        bld_r, bld_c = mov_r + br, mov_c + bc
                        if pos_valida(bld_r, bld_c) and board[bld_r][bld_c].level < 4 and (board[bld_r][bld_c].professor is None or (bld_r == aliado["r"] and bld_c == aliado["c"])):
                            
                            # Avaliação heurística do estado resultante
                            nota = avaliar_estado(mov_r, mov_c, casa_mov.level, bld_r, bld_c, board[bld_r][bld_c].level, inimigos_posicoes)
                            if nota > melhor_nota:
                                melhor_nota = nota
                                melhor_jogada = PlayerTurnResponse(professor=aliado["nome"], move_to=Position(row=mov_r, col=mov_c), mentor_at=Position(row=bld_r, col=bld_c))

    return melhor_jogada

def avaliar_estado(mov_r: int, mov_c: int, lvl_novo: int, bld_r: int, bld_c: int, bld_lvl: int, inimigos: List[dict]) -> int:
    """
    Motor Heurístico: Atribui um score matemático simulando o impacto estratégico de um turno.
    """
    pontos = lvl_novo * 1000 # Fator base de progressão altimétrica
    novo_lvl_construido = bld_lvl + 1
    
    if lvl_novo == 2 and novo_lvl_construido == 3:
        dist_mov_bld = max(abs(mov_r - bld_r), abs(mov_c - bld_c))
        if dist_mov_bld <= 1:
            pontos += 5000

    if novo_lvl_construido == lvl_novo + 1:
        pontos += 300

    pontos -= (abs(mov_r - 2) + abs(mov_c - 2)) * 10
    
    for inimigo in inimigos:
        dist_inimigo_bld = max(abs(inimigo["r"] - bld_r), abs(inimigo["c"] - bld_c))
        dist_inimigo_mov = max(abs(inimigo["r"] - mov_r), abs(inimigo["c"] - mov_c))

        if inimigo["lvl"] == 2 and dist_inimigo_bld <= 1:
            if novo_lvl_construido == 4:
                pontos += 8000 # Bloqueio Crítico
            elif novo_lvl_construido == 3:
                pontos -= 10000 # Falha Crítica

        if inimigo["lvl"] == 1 and dist_inimigo_bld <= 1 and novo_lvl_construido == 2:
            pontos -= 2000

        if dist_inimigo_mov <= 1 and inimigo["lvl"] >= lvl_novo - 1:
            pontos -= 500

    return pontos

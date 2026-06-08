import random
from typing import Optional, List, Tuple
from app.schemas import Cell, SetupResponse, PlayerTurnResponse, Position

# Constantes do tabuleiro
DIRECOES = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

def get_professores_por_time(team_id: int) -> Tuple[List[str], List[str]]:
    meus = ["CLARO", "REY"] if team_id == 1 else ["KARIN", "BEATRIZ"]
    inimigos = ["KARIN", "BEATRIZ"] if team_id == 1 else ["CLARO", "REY"]
    return meus, inimigos

def pos_valida(r: int, c: int) -> bool:
    return 0 <= r < 5 and 0 <= c < 5

def choose_setup(board: list[list[Cell]]) -> SetupResponse:
    """
    Fase de posicionamento: A estratégia aqui é dominar o centro da Arena.
    """
    # Ordem de preferência: Centro absoluto, depois os anéis internos.
    preferencias = [(2, 2), (1, 2), (2, 1), (2, 3), (3, 2), (1, 1), (1, 3), (3, 1), (3, 3)]
    
    for r, c in preferencias:
        if board[r][c].level == 0 and board[r][c].professor is None:
            return SetupResponse(row=r, col=c)
            
    # Fallback caso o centro esteja um caos
    candidates = [
        (r, c) for r in range(5) for c in range(5)
        if board[r][c].level == 0 and board[r][c].professor is None
    ]
    
    row, col = random.choice(candidates)
    return SetupResponse(row=row, col=col)

def choose_turn(board: list[list[Cell]], team_id: int) -> Optional[PlayerTurnResponse]:
    """
    Fase de turno: Simula movimentos e construções para escolher a jogada mais destrutiva.
    """
    meus_professores, inimigos = get_professores_por_time(team_id)
    
    melhor_jogada = None
    melhor_nota = -float('inf')

    # 1. Encontra onde estão nossas peças e as do inimigo
    minhas_posicoes = []
    inimigos_posicoes = []
    
    for r in range(5):
        for c in range(5):
            prof = board[r][c].professor
            if prof in meus_professores:
                minhas_posicoes.append({"nome": prof, "r": r, "c": c, "lvl": board[r][c].level})
            elif prof in inimigos:
                inimigos_posicoes.append({"nome": prof, "r": r, "c": c, "lvl": board[r][c].level})

    # 2. Testa todos os professores aliados
    for aliado in minhas_posicoes:
        # Testa todos os movimentos ao redor do aliado
        for dr, dc in DIRECOES:
            mov_r, mov_c = aliado["r"] + dr, aliado["c"] + dc
            
            # É um movimento válido? (Dentro do mapa, sem professor, e sobe no máximo 1 andar)
            if pos_valida(mov_r, mov_c):
                casa_mov = board[mov_r][mov_c]
                if casa_mov.professor is None and casa_mov.level <= aliado["lvl"] + 1 and casa_mov.level < 4:
                    
                    # VITÓRIA IMEDIATA: Se o movimento é para o Nível 3, ganhamos!
                    if casa_mov.level == 3:
                        # Constrói em qualquer lugar válido ao redor só para cumprir a regra da API
                        for br, bc in DIRECOES:
                            bld_r, bld_c = mov_r + br, mov_c + bc
                            if pos_valida(bld_r, bld_c) and (board[bld_r][bld_c].professor is None or (bld_r == aliado["r"] and bld_c == aliado["c"])) and board[bld_r][bld_c].level < 4:
                                return PlayerTurnResponse(
                                    professor=aliado["nome"],
                                    move_to=Position(row=mov_r, col=mov_c),
                                    mentor_at=Position(row=bld_r, col=bld_c)
                                )

                    # Testa todas as construções (mentor) a partir do novo lugar
                    for br, bc in DIRECOES:
                        bld_r, bld_c = mov_r + br, mov_c + bc
                        
                        # Pode construir onde ele estava antes, ou em casas vazias com nível < 4
                        pode_construir_aqui = pos_valida(bld_r, bld_c) and board[bld_r][bld_c].level < 4 and (
                            board[bld_r][bld_c].professor is None or (bld_r == aliado["r"] and bld_c == aliado["c"])
                        )

                        if pode_construir_aqui:
                            # Avalia a combinação (Movimento + Construção)
                            nota = avaliar_estado(
                                aliado["lvl"], mov_r, mov_c, casa_mov.level, 
                                bld_r, bld_c, board[bld_r][bld_c].level, 
                                inimigos_posicoes
                            )
                            
                            if nota > melhor_nota:
                                melhor_nota = nota
                                melhor_jogada = PlayerTurnResponse(
                                    professor=aliado["nome"],
                                    move_to=Position(row=mov_r, col=mov_c),
                                    mentor_at=Position(row=bld_r, col=bld_c)
                                )

    return melhor_jogada

def avaliar_estado(
    lvl_antigo: int, mov_r: int, mov_c: int, lvl_novo: int, 
    bld_r: int, bld_c: int, bld_lvl: int, 
    inimigos: List[dict]
) -> int:
    """
    A função Heurística: Dá pontos baseados na força estratégica do estado final.
    """
    pontos = 0
    
    # 1. Ganho de altura (Prioridade alta)
    pontos += (lvl_novo * 1000)
    
    # 2. Dominância Central
    distancia_centro = abs(mov_r - 2) + abs(mov_c - 2)
    pontos -= (distancia_centro * 10)
    
    # 3. Análise de Ameaça e Bloqueio (Onde o adversário está?)
    for inimigo in inimigos:
        # O inimigo está no nível 2 e eu construí na casa adjacente a ele?
        dist_inimigo_bld = max(abs(inimigo["r"] - bld_r), abs(inimigo["c"] - bld_c))
        
        if inimigo["lvl"] == 2 and dist_inimigo_bld <= 1:
            # Se eu construí para o nível 4 ou 3 ao lado de um inimigo nível 2, eu acabei de quebrar o jogo dele!
            if bld_lvl + 1 >= 3:
                pontos += 8000
                
        # O inimigo ameaça a casa para onde eu me movi?
        dist_inimigo_mov = max(abs(inimigo["r"] - mov_r), abs(inimigo["c"] - mov_c))
        if dist_inimigo_mov <= 1 and inimigo["lvl"] >= lvl_novo - 1:
            pontos -= 500 # Evita pisar onde o inimigo pode facilmente subir atrás de você

    return pontos

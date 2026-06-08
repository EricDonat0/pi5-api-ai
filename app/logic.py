import random
from typing import Optional, List
from app.schemas import Cell, SetupResponse, PlayerTurnResponse, Position

def choose_setup(board: list[list[Cell]]) -> SetupResponse:
    """
    Fase de posicionamento: escolhe uma casa nivel 0 desocupada.
    """
    candidates = [
        (r, c)
        for r in range(5) # CORREÇÃO: range(5)
        for c in range(5) # CORREÇÃO: range(5)
        if board[r][c].level == 0 and board[r][c].professor is None # CORREÇÃO: == 0
    ]
    
    row, col = random.choice(candidates)
    return SetupResponse(row=row, col=col)
    
def choose_turn(board: list[list[Cell]], team_id: int) -> Optional[PlayerTurnResponse]:
    """
    Fase de turno: escolhe um professor do time, move e constrói.
    """
    # Identifica quais são os nossos professores dependendo do lado que caímos
    meus_professores = ["CLARO", "REY"] if team_id == 1 else ["KARIN", "BEATRIZ"]
    
    return PlayerTurnResponse(
        professor=meus_professores[0],
        move_to=Position(row=0, col=0),
        mentor_at=Position(row=0, col=1)
    )
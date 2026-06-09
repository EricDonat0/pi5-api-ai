from datetime import date
from fastapi import FastAPI, HTTPException
from app.schemas import AITurnRequest, TurnPhase

# Importa a IA V1 (Heurística Gulosa)
from app.logic_v1 import choose_setup as setup_v1, choose_turn as turn_v1

# Importa a IA V2 (Lookahead Heurístico)
from app.logic_v2 import choose_setup as setup_v2, choose_turn as turn_v2

# Importa a nova IA V3 (Negamax + Poda Alfa-Beta)
from app.logic_v3 import choose_setup as setup_v3, choose_turn as turn_v3

app = FastAPI(
    title="PalermaBot Arena Multi-Engine",
    description="API tripla: Gulosa (V1), Lookahead (V2) e Negamax Competitivo (V3).",
    version="1.3.0",
)

@app.get("/health")
async def health():
    return date.today()

# ---------------------------------------------------------
# MOTOR V1 - GULOSO
# ---------------------------------------------------------
@app.post("/move")
async def move_v1(body: AITurnRequest):
    try:
        if body.turn_phase == TurnPhase.SETUP:
            return setup_v1(body.board) 
        return turn_v1(body.board, int(body.your_team))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro na V1: {exc}")

# ---------------------------------------------------------
# MOTOR V2 - LOOKAHEAD
# ---------------------------------------------------------
@app.post("/move-v2")
async def move_v2(body: AITurnRequest):
    try:
        if body.turn_phase == TurnPhase.SETUP:
            return setup_v2(body.board, int(body.your_team))
        return turn_v2(body.board, int(body.your_team))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro na V2: {exc}")

# ---------------------------------------------------------
# MOTOR V3 - NEGAMAX COMPETITIVO
# ---------------------------------------------------------
@app.post("/move-v3")
async def move_v3(body: AITurnRequest):
    """
    Endpoint da nova IA adversarial com poda alfa-beta e simulação profunda.
    """
    try:
        if body.turn_phase == TurnPhase.SETUP:
            return setup_v3(body.board, int(body.your_team))

        jogada = turn_v3(body.board, int(body.your_team))
        if jogada is None:
            raise HTTPException(status_code=422, detail="Nenhuma jogada válida encontrada pelo Negamax.")
        return jogada

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro no cálculo do Negamax V3: {exc}") from exc
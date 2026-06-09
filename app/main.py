from fastapi import FastAPI
from app.schemas import AITurnRequest, TurnPhase

# Importa as funções da IA Antiga (V1) renomeando para não dar conflito
from app.logic_v1 import choose_setup as setup_v1, choose_turn as turn_v1

# Importa as funções da IA Nova (V2) renomeando para não dar conflito
from app.logic_v2 import choose_setup as setup_v2, choose_turn as turn_v2

app = FastAPI(title="PalermaBot API")

@app.get("/health")
async def health_check():
    import datetime
    return {"status": "online", "time": datetime.datetime.now().isoformat()}

# ---------------------------------------------------------
# ENDPOINT DA IA V1
# ---------------------------------------------------------
@app.post("/move")
async def move_bot_v1(body: AITurnRequest):
    """
    Motor Heurístico Guloso Original
    """
    if body.turn_phase == TurnPhase.SETUP:
        # A função setup_v1 original não recebia team_id
        return setup_v1(body.board) 
    else:
        return turn_v1(body.board, int(body.your_team))

# ---------------------------------------------------------
# ENDPOINT DA IA V2 (Bot com Lookahead)
# ---------------------------------------------------------
@app.post("/move-v2")
async def move_bot_v2(body: AITurnRequest):
    """
    Motor Avançado com Simulação de Transição de Estado e Lookahead
    """
    if body.turn_phase == TurnPhase.SETUP:
        # A função setup_v2 nova exige o team_id para separar os aliados
        return setup_v2(body.board, int(body.your_team))
    else:
        return turn_v2(body.board, int(body.your_team))
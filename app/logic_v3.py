"""
Motor de decisao competitivo para o jogo Palerma/Santorini-like.

Ideia central:
- Gerar todas as jogadas legais: mover um professor e depois construir.
- Procurar vitorias imediatas.
- Usar busca adversarial Negamax com poda alfa-beta para simular respostas do inimigo.
- Usar uma heuristica forte apenas quando a busca nao consegue calcular ate o fim.

Essa abordagem e mais forte que uma heuristica gulosa porque considera a melhor resposta
possivel do adversario, nao apenas o beneficio imediato da jogada atual.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from app.schemas import Cell, PlayerTurnResponse, Position, SetupResponse


# ---------------------------------------------------------------------------
# Constantes do jogo
# ---------------------------------------------------------------------------

BOARD_SIZE = 5
CELL_COUNT = BOARD_SIZE * BOARD_SIZE
MAX_LEVEL = 4
WIN_LEVEL = 3

DIRECOES: Tuple[Tuple[int, int], ...] = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
)

PROFESSORS: Tuple[str, str, str, str] = ("CLARO", "REY", "KARIN", "BEATRIZ")
PROF_TO_INDEX: Dict[str, int] = {name: i for i, name in enumerate(PROFESSORS)}
TEAM_TO_PROF_INDEXES: Dict[int, Tuple[int, int]] = {
    1: (PROF_TO_INDEX["CLARO"], PROF_TO_INDEX["REY"]),
    2: (PROF_TO_INDEX["KARIN"], PROF_TO_INDEX["BEATRIZ"]),
}
OPPONENT_TEAM: Dict[int, int] = {1: 2, 2: 1}

# Pontuacoes grandes. Mantemos terminal muito maior que qualquer heuristica.
WIN_SCORE = 1_000_000_000
INF = 10**18

# Limites praticos para API. A IA sempre tem fallback, entao, se o tempo acabar,
# ela devolve a melhor jogada encontrada na ultima profundidade completa.
MAX_SEARCH_DEPTH = int(os.getenv("PALERMA_MAX_SEARCH_DEPTH", "4"))
SEARCH_TIME_LIMIT_SECONDS = float(os.getenv("PALERMA_SEARCH_TIME_SECONDS", "0.75"))

# Em profundidades altas, limitar os candidatos torna a busca viavel em producao.
# A ordenacao de jogadas coloca vitorias, bloqueios e ameacas na frente.
CANDIDATE_LIMIT_BY_DEPTH = {
    4: 48,
    3: 56,
    2: 72,
}

# Tabela de vizinhos pre-computada.
def _idx(row: int, col: int) -> int:
    return row * BOARD_SIZE + col


def _row_col(index: int) -> Tuple[int, int]:
    return divmod(index, BOARD_SIZE)


def _in_bounds(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


NEIGHBORS: Tuple[Tuple[int, ...], ...] = tuple(
    tuple(
        _idx(r + dr, c + dc)
        for dr, dc in DIRECOES
        if _in_bounds(r + dr, c + dc)
    )
    for r in range(BOARD_SIZE)
    for c in range(BOARD_SIZE)
)

# Bonus posicional: centro > anel interno > bordas > cantos.
CENTER_BONUS: Tuple[int, ...] = tuple(
    4 - (abs(r - 2) + abs(c - 2))
    for r in range(BOARD_SIZE)
    for c in range(BOARD_SIZE)
)


@dataclass(frozen=True)
class GameState:
    """Estado imutavel e barato de comparar/cachear."""

    levels: Tuple[int, ...]
    positions: Tuple[int, int, int, int]


@dataclass(frozen=True)
class SearchMove:
    """Jogada interna da busca."""

    prof_idx: int
    from_idx: int
    to_idx: int
    build_idx: Optional[int]
    is_win: bool = False


@dataclass(frozen=True)
class TTEntry:
    """Entrada da tabela de transposicao usada pela poda alfa-beta."""

    depth: int
    score: int
    flag: str  # EXACT, LOWER, UPPER
    best_move: Optional[SearchMove]


class SearchTimeout(Exception):
    """Interrompe a busca quando o limite de tempo da requisicao esta perto."""


# ---------------------------------------------------------------------------
# Utilitarios basicos
# ---------------------------------------------------------------------------


def get_professores_por_time(team_id: int) -> Tuple[List[str], List[str]]:
    """Mantem compatibilidade com o codigo antigo."""
    meus_idx = TEAM_TO_PROF_INDEXES[int(team_id)]
    inimigos_idx = TEAM_TO_PROF_INDEXES[OPPONENT_TEAM[int(team_id)]]
    return [PROFESSORS[i] for i in meus_idx], [PROFESSORS[i] for i in inimigos_idx]


def pos_valida(r: int, c: int) -> bool:
    """Mantem compatibilidade com o codigo antigo."""
    return _in_bounds(r, c)


def _board_to_state(board: List[List[Cell]]) -> GameState:
    levels: List[int] = [0] * CELL_COUNT
    positions: List[int] = [-1, -1, -1, -1]

    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            cell = board[r][c]
            index = _idx(r, c)
            levels[index] = int(cell.level)
            if cell.professor in PROF_TO_INDEX:
                positions[PROF_TO_INDEX[cell.professor]] = index

    return GameState(levels=tuple(levels), positions=tuple(positions))


def _is_occupied(state: GameState, index: int) -> bool:
    return index in state.positions


def _opponent(team_id: int) -> int:
    return OPPONENT_TEAM[int(team_id)]


def _is_valid_move_destination(state: GameState, from_idx: int, to_idx: int) -> bool:
    if state.levels[to_idx] >= MAX_LEVEL:
        return False
    if _is_occupied(state, to_idx):
        return False
    return state.levels[to_idx] <= state.levels[from_idx] + 1


def _response_from_move(move: SearchMove) -> PlayerTurnResponse:
    move_r, move_c = _row_col(move.to_idx)

    # Pela regra documentada no schema, mentor_at pode ser omitido em jogada de vitoria.
    if move.is_win or move.build_idx is None:
        return PlayerTurnResponse(
            professor=PROFESSORS[move.prof_idx],
            move_to=Position(row=move_r, col=move_c),
            mentor_at=None,
        )

    build_r, build_c = _row_col(move.build_idx)
    return PlayerTurnResponse(
        professor=PROFESSORS[move.prof_idx],
        move_to=Position(row=move_r, col=move_c),
        mentor_at=Position(row=build_r, col=build_c),
    )


# ---------------------------------------------------------------------------
# Geracao de jogadas legais
# ---------------------------------------------------------------------------


def generate_moves(
    state: GameState,
    team_id: int,
    *,
    only_winning: bool = False,
) -> List[SearchMove]:
    """
    Gera todas as jogadas legais para o time.

    Regra usada:
    - O professor move para uma casa adjacente vazia.
    - Nao pode subir mais de 1 nivel.
    - Nivel 4 e bloqueado.
    - Mover para nivel 3 vence imediatamente; nesse caso nao precisa construir.
    - Caso nao vença, deve construir em uma casa adjacente ao destino, vazia apos o movimento,
      com nivel menor que 4. A casa antiga fica livre e pode receber construcao.
    """
    moves: List[SearchMove] = []

    for prof_idx in TEAM_TO_PROF_INDEXES[int(team_id)]:
        from_idx = state.positions[prof_idx]
        if from_idx < 0:
            continue

        for to_idx in NEIGHBORS[from_idx]:
            if not _is_valid_move_destination(state, from_idx, to_idx):
                continue

            if state.levels[to_idx] == WIN_LEVEL:
                moves.append(SearchMove(prof_idx, from_idx, to_idx, None, True))
                continue

            if only_winning:
                continue

            positions_after = list(state.positions)
            positions_after[prof_idx] = to_idx
            occupied_after = tuple(positions_after)

            for build_idx in NEIGHBORS[to_idx]:
                if state.levels[build_idx] >= MAX_LEVEL:
                    continue
                if build_idx in occupied_after:
                    continue
                moves.append(SearchMove(prof_idx, from_idx, to_idx, build_idx, False))

    return moves


def has_any_legal_move(state: GameState, team_id: int) -> bool:
    for prof_idx in TEAM_TO_PROF_INDEXES[int(team_id)]:
        from_idx = state.positions[prof_idx]
        if from_idx < 0:
            continue

        for to_idx in NEIGHBORS[from_idx]:
            if not _is_valid_move_destination(state, from_idx, to_idx):
                continue

            if state.levels[to_idx] == WIN_LEVEL:
                return True

            positions_after = list(state.positions)
            positions_after[prof_idx] = to_idx
            occupied_after = tuple(positions_after)
            for build_idx in NEIGHBORS[to_idx]:
                if state.levels[build_idx] < MAX_LEVEL and build_idx not in occupied_after:
                    return True

    return False


def immediate_win_targets(state: GameState, team_id: int) -> Set[int]:
    """Casas de nivel 3 que o time consegue acessar agora."""
    targets: Set[int] = set()
    for prof_idx in TEAM_TO_PROF_INDEXES[int(team_id)]:
        from_idx = state.positions[prof_idx]
        if from_idx < 0:
            continue
        if state.levels[from_idx] < WIN_LEVEL - 1:
            continue
        for to_idx in NEIGHBORS[from_idx]:
            if state.levels[to_idx] == WIN_LEVEL and _is_valid_move_destination(state, from_idx, to_idx):
                targets.add(to_idx)
    return targets


def has_immediate_win(state: GameState, team_id: int) -> bool:
    return bool(immediate_win_targets(state, team_id))


def apply_move(state: GameState, move: SearchMove) -> GameState:
    """Aplica jogada nao-terminal. Jogadas de vitoria sao tratadas antes."""
    positions = list(state.positions)
    positions[move.prof_idx] = move.to_idx

    if move.build_idx is None:
        return GameState(levels=state.levels, positions=tuple(positions))

    levels = list(state.levels)
    levels[move.build_idx] += 1
    return GameState(levels=tuple(levels), positions=tuple(positions))


# ---------------------------------------------------------------------------
# Heuristicas de avaliacao
# ---------------------------------------------------------------------------


def _count_reachable_destinations(state: GameState, prof_idx: int) -> int:
    from_idx = state.positions[prof_idx]
    if from_idx < 0:
        return 0
    count = 0
    for to_idx in NEIGHBORS[from_idx]:
        if _is_valid_move_destination(state, from_idx, to_idx):
            count += 1
    return count


def _count_full_legal_moves_capped(state: GameState, team_id: int, cap: int = 80) -> int:
    """Conta jogadas completas com limite para manter a avaliacao barata."""
    count = 0
    for prof_idx in TEAM_TO_PROF_INDEXES[int(team_id)]:
        from_idx = state.positions[prof_idx]
        if from_idx < 0:
            continue

        for to_idx in NEIGHBORS[from_idx]:
            if not _is_valid_move_destination(state, from_idx, to_idx):
                continue
            if state.levels[to_idx] == WIN_LEVEL:
                return cap

            positions_after = list(state.positions)
            positions_after[prof_idx] = to_idx
            occupied_after = tuple(positions_after)
            for build_idx in NEIGHBORS[to_idx]:
                if state.levels[build_idx] < MAX_LEVEL and build_idx not in occupied_after:
                    count += 1
                    if count >= cap:
                        return cap
    return count


def _worker_features(state: GameState, prof_idx: int) -> int:
    pos = state.positions[prof_idx]
    if pos < 0:
        return 0

    level = state.levels[pos]
    row, col = _row_col(pos)
    score = 0

    # Altura: nivel 2 e o mais valioso antes da vitoria, porque ameaca subir para 3.
    level_score = (0, 180, 900, 5000, -10000)
    score += level_score[level]

    # Centro aumenta mobilidade e reduz chance de ficar preso.
    score += CENTER_BONUS[pos] * 45

    # Mobilidade direta.
    reachable = _count_reachable_destinations(state, prof_idx)
    score += reachable * 65
    if reachable == 0:
        score -= 6000
    elif reachable <= 2:
        score -= 900

    # Potenciais de subida e ameacas.
    for n in NEIGHBORS[pos]:
        if _is_occupied(state, n) or state.levels[n] >= MAX_LEVEL:
            continue

        target_level = state.levels[n]
        if target_level <= level + 1:
            if target_level == WIN_LEVEL and level >= WIN_LEVEL - 1:
                score += 80_000  # ameaca de vitoria imediata
            elif target_level == 2 and level >= 1:
                score += 2_200   # prepara ameaca de vitoria
            elif target_level == level + 1:
                score += 420     # progresso vertical
            elif target_level == level:
                score += 120

        # Casa nivel 3 perto de professor baixo ainda e util como objetivo futuro,
        # mas nao tanto quanto uma ameaca real.
        if target_level == WIN_LEVEL and level < 2:
            score += 250

    # Canto e borda sao ruins se o professor ainda esta baixo.
    if level <= 1:
        if (row in (0, 4)) and (col in (0, 4)):
            score -= 450
        elif row in (0, 4) or col in (0, 4):
            score -= 180

    return score


def _team_features(state: GameState, team_id: int) -> int:
    prof_a, prof_b = TEAM_TO_PROF_INDEXES[int(team_id)]
    positions = [state.positions[prof_a], state.positions[prof_b]]

    score = _worker_features(state, prof_a) + _worker_features(state, prof_b)

    # Mobilidade completa do time: inclui possibilidade de construir.
    full_moves = _count_full_legal_moves_capped(state, team_id)
    score += full_moves * 18
    if full_moves == 0:
        score -= 100_000
    elif full_moves <= 8:
        score -= 2_500

    # Coordenacao entre professores: separados demais perdem controle; colados demais se bloqueiam.
    if positions[0] >= 0 and positions[1] >= 0:
        r1, c1 = _row_col(positions[0])
        r2, c2 = _row_col(positions[1])
        cheb = max(abs(r1 - r2), abs(c1 - c2))
        manh = abs(r1 - r2) + abs(c1 - c2)
        if cheb == 1:
            score -= 120
        elif cheb == 2:
            score += 220
        elif cheb == 3:
            score += 80
        else:
            score -= 260
        if manh >= 5:
            score -= 180

    return score


def evaluate_state(state: GameState, perspective_team: int) -> int:
    """
    Avaliacao estatica do tabuleiro.

    Retorna positivo se o estado e bom para perspective_team e negativo se e bom
    para o adversario. Terminais sao tratados no negamax; aqui avaliamos perigo,
    pressao, mobilidade e altura.
    """
    my_team = int(perspective_team)
    enemy_team = _opponent(my_team)

    my_threats = immediate_win_targets(state, my_team)
    enemy_threats = immediate_win_targets(state, enemy_team)

    score = 0
    score += _team_features(state, my_team)
    score -= _team_features(state, enemy_team)

    # Ameacas imediatas valem muito. A ameaca inimiga pesa mais para a IA ser conservadora.
    score += len(my_threats) * 140_000
    score -= len(enemy_threats) * 180_000

    # Duas ou mais ameacas costumam ser quase uma vitoria forcada.
    if len(my_threats) >= 2:
        score += 160_000
    if len(enemy_threats) >= 2:
        score -= 220_000

    return score


# ---------------------------------------------------------------------------
# Ordenacao de jogadas
# ---------------------------------------------------------------------------


def _build_gives_enemy_win(state: GameState, move: SearchMove, enemy_team: int) -> bool:
    """
    Detecta um erro classico: construir de nivel 2 para 3 ao lado de inimigo em nivel 2,
    entregando uma casa de vitoria para ele no proximo turno.
    """
    if move.build_idx is None:
        return False
    if state.levels[move.build_idx] + 1 != WIN_LEVEL:
        return False

    next_state = apply_move(state, move)
    return move.build_idx in immediate_win_targets(next_state, enemy_team)


def _move_blocks_enemy_threat(state: GameState, move: SearchMove, enemy_team: int) -> bool:
    if move.build_idx is None:
        return False
    enemy_targets = immediate_win_targets(state, enemy_team)
    return bool(enemy_targets) and move.build_idx in enemy_targets and state.levels[move.build_idx] == WIN_LEVEL


def _move_order_score(state: GameState, move: SearchMove, team_id: int, tt_best: Optional[SearchMove] = None) -> int:
    if tt_best is not None and move == tt_best:
        return 10_000_000

    enemy_team = _opponent(team_id)
    score = 0

    if move.is_win:
        return 9_000_000

    from_level = state.levels[move.from_idx]
    to_level = state.levels[move.to_idx]
    build_level_before = state.levels[move.build_idx] if move.build_idx is not None else 0
    build_level_after = build_level_before + 1 if move.build_idx is not None else 0

    if _move_blocks_enemy_threat(state, move, enemy_team):
        score += 4_500_000

    if _build_gives_enemy_win(state, move, enemy_team):
        score -= 3_000_000

    # Subir e chegar ao nivel 2 e muito forte.
    score += to_level * 4_000
    score += (to_level - from_level) * 1_500
    if to_level == 2:
        score += 7_500

    # Centro e mobilidade.
    score += CENTER_BONUS[move.to_idx] * 160
    score += len(NEIGHBORS[move.to_idx]) * 50

    # Construcoes: dome em nivel 3 bloqueia; nivel 3 nosso cria ameaca, mas e perigoso perto do inimigo.
    if move.build_idx is not None:
        score += build_level_after * 350
        if build_level_after == MAX_LEVEL:
            score += 4_000
        elif build_level_after == WIN_LEVEL:
            score += 900

        # Construir perto do inimigo pode ser bloqueio/pressao; perto de mim pode criar escada.
        for enemy_idx in TEAM_TO_PROF_INDEXES[enemy_team]:
            enemy_pos = state.positions[enemy_idx]
            if enemy_pos >= 0 and move.build_idx in NEIGHBORS[enemy_pos]:
                score += 250
                if state.levels[enemy_pos] == 2 and build_level_after == MAX_LEVEL:
                    score += 8_000
                if state.levels[enemy_pos] == 2 and build_level_after == WIN_LEVEL:
                    score -= 10_000

        if move.build_idx in NEIGHBORS[move.to_idx] and build_level_after <= to_level + 1:
            score += 450

    return score


def ordered_moves(
    state: GameState,
    team_id: int,
    *,
    depth: int,
    tt_best: Optional[SearchMove] = None,
    limit: Optional[int] = None,
) -> List[SearchMove]:
    moves = generate_moves(state, team_id)
    moves.sort(key=lambda m: _move_order_score(state, m, team_id, tt_best), reverse=True)

    if limit is not None and len(moves) > limit:
        return moves[:limit]
    return moves


# ---------------------------------------------------------------------------
# Busca adversarial Negamax + alfa-beta + aprofundamento iterativo
# ---------------------------------------------------------------------------


class SearchEngine:
    def __init__(self, time_limit_seconds: float = SEARCH_TIME_LIMIT_SECONDS):
        self.deadline = time.perf_counter() + time_limit_seconds
        self.nodes = 0
        self.tt: Dict[Tuple[Tuple[int, ...], Tuple[int, int, int, int], int, int], TTEntry] = {}

    def _check_time(self) -> None:
        self.nodes += 1
        if (self.nodes & 1023) == 0 and time.perf_counter() >= self.deadline:
            raise SearchTimeout

    def negamax(
        self,
        state: GameState,
        team_id: int,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
    ) -> int:
        self._check_time()

        # Terminal: se o jogador da vez pode vencer agora, esse estado e ganhador.
        if has_immediate_win(state, team_id):
            return WIN_SCORE - ply

        # Terminal: sem jogada legal, perde por travamento.
        if not has_any_legal_move(state, team_id):
            return -WIN_SCORE + ply

        if depth <= 0:
            return evaluate_state(state, team_id)

        key = (state.levels, state.positions, int(team_id), int(depth))
        alpha_original = alpha
        tt_entry = self.tt.get(key)
        tt_best: Optional[SearchMove] = None
        if tt_entry is not None and tt_entry.depth >= depth:
            tt_best = tt_entry.best_move
            if tt_entry.flag == "EXACT":
                return tt_entry.score
            if tt_entry.flag == "LOWER":
                alpha = max(alpha, tt_entry.score)
            elif tt_entry.flag == "UPPER":
                beta = min(beta, tt_entry.score)
            if alpha >= beta:
                return tt_entry.score

        limit = CANDIDATE_LIMIT_BY_DEPTH.get(depth)
        moves = ordered_moves(state, team_id, depth=depth, tt_best=tt_best, limit=limit)
        if not moves:
            return -WIN_SCORE + ply

        best_score = -INF
        best_move: Optional[SearchMove] = None
        next_team = _opponent(team_id)

        for move in moves:
            if move.is_win:
                score = WIN_SCORE - ply
            else:
                child = apply_move(state, move)
                score = -self.negamax(child, next_team, depth - 1, -beta, -alpha, ply + 1)

            if score > best_score:
                best_score = score
                best_move = move

            alpha = max(alpha, score)
            if alpha >= beta:
                break

        if best_score <= alpha_original:
            flag = "UPPER"
        elif best_score >= beta:
            flag = "LOWER"
        else:
            flag = "EXACT"

        self.tt[key] = TTEntry(depth=depth, score=int(best_score), flag=flag, best_move=best_move)
        return int(best_score)

    def best_move(self, state: GameState, team_id: int) -> Optional[SearchMove]:
        root_moves = ordered_moves(state, team_id, depth=MAX_SEARCH_DEPTH, limit=None)
        if not root_moves:
            return None

        # Vitoria imediata: nao pensa duas vezes.
        for move in root_moves:
            if move.is_win:
                return move

        # Fallback rapido: melhor jogada por avaliacao de 1 lance.
        best_move = self._fallback_move(state, team_id, root_moves)
        best_score = -INF

        # Aprofundamento iterativo: profundidades completas substituem o fallback.
        for depth in range(1, MAX_SEARCH_DEPTH + 1):
            try:
                current_best = best_move
                current_best_score = -INF
                alpha = -INF
                beta = INF

                # Principal variation primeiro: acelera cortes na proxima profundidade.
                moves = list(root_moves)
                if best_move in moves:
                    moves.remove(best_move)
                    moves.insert(0, best_move)

                for move in moves:
                    self._check_time()

                    if move.is_win:
                        score = WIN_SCORE
                    else:
                        child = apply_move(state, move)
                        score = -self.negamax(child, _opponent(team_id), depth - 1, -beta, -alpha, 1)

                    if score > current_best_score:
                        current_best_score = score
                        current_best = move

                    alpha = max(alpha, score)

                best_move = current_best
                best_score = current_best_score

                # Se achou uma vitoria forcada, nao precisa gastar mais tempo.
                if best_score >= WIN_SCORE - 1000:
                    break

            except SearchTimeout:
                break

        return best_move

    def _fallback_move(self, state: GameState, team_id: int, moves: Sequence[SearchMove]) -> SearchMove:
        """
        Jogada segura caso a busca profunda nao complete a tempo.
        Avalia o estado apos a nossa jogada e penaliza fortemente entregar vitoria imediata.
        """
        enemy_team = _opponent(team_id)
        best = moves[0]
        best_score = -INF

        for move in moves:
            if move.is_win:
                return move

            child = apply_move(state, move)
            score = evaluate_state(child, team_id)

            if has_immediate_win(child, enemy_team):
                score -= 900_000_000
            if has_immediate_win(child, team_id):
                score += 600_000
            if _move_blocks_enemy_threat(state, move, enemy_team):
                score += 700_000
            if _build_gives_enemy_win(state, move, enemy_team):
                score -= 700_000

            score += _move_order_score(state, move, team_id) // 10

            if score > best_score:
                best_score = score
                best = move

        return best


# ---------------------------------------------------------------------------
# Funcoes publicas chamadas pela API
# ---------------------------------------------------------------------------


def choose_setup(board: List[List[Cell]], team_id: int = 1) -> SetupResponse:
    """
    Posicionamento inicial competitivo.

    A ideia nao e simplesmente ocupar o centro absoluto sempre. Em torneio, o setup
    costuma ser alternado; entao a segunda peca precisa complementar a primeira.

    Criterios:
    - preferir centro e anel interno;
    - manter boa mobilidade;
    - se ja existe um aliado, ficar a distancia 2 ou 3 dele;
    - evitar canto/borda quando houver opcoes melhores;
    - nao grudar nos inimigos durante a abertura.
    """
    state = _board_to_state(board)
    team_id = int(team_id)
    enemy_team = _opponent(team_id)

    my_positions = [state.positions[i] for i in TEAM_TO_PROF_INDEXES[team_id] if state.positions[i] >= 0]
    enemy_positions = [state.positions[i] for i in TEAM_TO_PROF_INDEXES[enemy_team] if state.positions[i] >= 0]

    candidates: List[int] = []
    for index in range(CELL_COUNT):
        if state.levels[index] == 0 and not _is_occupied(state, index):
            candidates.append(index)

    if not candidates:
        raise ValueError("Nao ha casas livres para posicionamento inicial.")

    def setup_score(index: int) -> int:
        row, col = _row_col(index)
        score = 0

        # Centro e anel interno dominam o comeco.
        score += CENTER_BONUS[index] * 1_000
        score += len(NEIGHBORS[index]) * 80

        if (row in (0, 4)) and (col in (0, 4)):
            score -= 1_200
        elif row in (0, 4) or col in (0, 4):
            score -= 450

        # Complementa o aliado: distancia 2 costuma dar cobertura sem bloquear.
        for ally in my_positions:
            ar, ac = _row_col(ally)
            cheb = max(abs(row - ar), abs(col - ac))
            manh = abs(row - ar) + abs(col - ac)
            if cheb == 1:
                score -= 650
            elif cheb == 2:
                score += 950
            elif cheb == 3:
                score += 250
            else:
                score -= 250
            if 2 <= manh <= 4:
                score += 200

        # Evita entregar bloqueio facil ao inimigo no setup.
        for enemy in enemy_positions:
            er, ec = _row_col(enemy)
            cheb = max(abs(row - er), abs(col - ec))
            if cheb == 1:
                score -= 300
            elif cheb == 2:
                score += 120

        # Desempate deterministico por ordem de abertura boa.
        opening_preference = {
            _idx(2, 2): 90,
            _idx(1, 1): 70,
            _idx(1, 3): 68,
            _idx(3, 1): 66,
            _idx(3, 3): 64,
            _idx(1, 2): 55,
            _idx(2, 1): 54,
            _idx(2, 3): 53,
            _idx(3, 2): 52,
        }
        score += opening_preference.get(index, 0)
        return score

    best_index = max(candidates, key=setup_score)
    row, col = _row_col(best_index)
    return SetupResponse(row=row, col=col)


def choose_turn(board: List[List[Cell]], team_id: int) -> Optional[PlayerTurnResponse]:
    """
    Escolhe a jogada usando busca adversarial.

    Retorna None apenas se nao houver nenhuma jogada legal.
    """
    state = _board_to_state(board)
    engine = SearchEngine()
    move = engine.best_move(state, int(team_id))
    if move is None:
        return None
    return _response_from_move(move)


# ---------------------------------------------------------------------------
# Funcao antiga mantida como compatibilidade externa, agora redirecionada para
# a avaliacao nova. Se algum teste/import antigo chamar avaliar_estado, nao quebra.
# ---------------------------------------------------------------------------


def avaliar_estado(
    lvl_antigo: int,
    mov_r: int,
    mov_c: int,
    lvl_novo: int,
    bld_r: int,
    bld_c: int,
    bld_lvl: int,
    inimigos: List[dict],
) -> int:
    pontos = 0
    pontos += lvl_novo * 1_000
    pontos += (lvl_novo - lvl_antigo) * 500
    pontos += (4 - (abs(mov_r - 2) + abs(mov_c - 2))) * 80

    for inimigo in inimigos:
        dist_build = max(abs(inimigo["r"] - bld_r), abs(inimigo["c"] - bld_c))
        dist_move = max(abs(inimigo["r"] - mov_r), abs(inimigo["c"] - mov_c))

        if inimigo["lvl"] == 2 and dist_build <= 1:
            if bld_lvl + 1 == 4:
                pontos += 8_000
            elif bld_lvl + 1 == 3:
                pontos -= 6_000

        if dist_move <= 1 and inimigo["lvl"] >= lvl_novo - 1:
            pontos -= 500

    return pontos

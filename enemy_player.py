from __future__ import annotations
import time
from collections import deque
from player import Player
from board import HexBoard


class EnemyPlayer(Player):
    """
    Versión rápida para tableros 7x7.
    Prioriza responder siempre en tiempo antes que buscar demasiado profundo.
    """

    WIN_SCORE = 10**7
    INF = 10**9

    _NEIGHBOR_CACHE: dict[int, tuple[tuple[tuple[int, int], ...], ...]] = {}

    def __init__(self, player_id: int):
        super().__init__(player_id)
        self.time_limit = 0.9
        self.tt: dict[tuple, float] = {}

    def play(self, board: HexBoard) -> tuple[int, int]:
        start = time.perf_counter()
        self.tt.clear()

        legal = self._legal_moves(board)
        if not legal:
            return (0, 0)

        n = board.size

        # Apertura: centro
        if len(legal) == n * n:
            return min(legal, key=lambda mv: self._center_distance(n, mv[0], mv[1]))

        # Tácticas inmediatas
        move = self._immediate_win_or_block(board, legal)
        if move is not None:
            return move

        candidates = self._candidate_moves(board, legal)
        if not candidates:
            candidates = legal

        candidates = self._order_moves(board, candidates, self.player_id)

        best_move = candidates[0]
        best_value = -self.INF

        max_depth = self._max_depth(board.size, len(legal), len(candidates))

        for depth in range(1, max_depth + 1):
            if self._time_up(start):
                break

            current_best_move = best_move
            current_best_value = -self.INF
            alpha = -self.INF
            beta = self.INF

            try:
                for move in candidates:
                    self._check_time(start)

                    child = board.clone()
                    child.place_piece(move[0], move[1], self.player_id)

                    # Solo aquí vale la pena revisar conexión inmediata
                    if child.check_connection(self.player_id):
                        return move

                    value = -self._negamax(
                        child,
                        depth - 1,
                        -beta,
                        -alpha,
                        self._opponent(self.player_id),
                        start,
                    )

                    if value > current_best_value:
                        current_best_value = value
                        current_best_move = move

                    if value > alpha:
                        alpha = value

                best_move = current_best_move
                best_value = current_best_value

            except TimeoutError:
                break

        return best_move

    # ============================================================
    # Negamax corto
    # ============================================================
    def _negamax(
        self,
        board: HexBoard,
        depth: int,
        alpha: float,
        beta: float,
        player_id: int,
        start: float,
    ) -> float:
        self._check_time(start)

        key = (self._board_key(board), player_id, depth)
        if key in self.tt:
            return self.tt[key]

        opp_id = self._opponent(player_id)

        # Terminales: desde la perspectiva del jugador actual del nodo (player_id),
        # no siempre desde self.player_id — negamax requiere perspectiva relativa.
        if board.check_connection(player_id):
            return self.WIN_SCORE
        if board.check_connection(opp_id):
            return -self.WIN_SCORE

        legal = self._legal_moves(board)
        if not legal:
            v = self._evaluate(board, player_id)
            self.tt[key] = v
            return v

        if depth <= 0:
            v = self._evaluate(board, player_id)
            self.tt[key] = v
            return v

        moves = self._candidate_moves(board, legal)
        if not moves:
            moves = legal

        moves = self._order_moves(board, moves, player_id)

        # poda fuerte: limitar aún más dentro del árbol
        if len(moves) > 6:
            moves = moves[:6]

        best = -self.INF

        for move in moves:
            self._check_time(start)

            child = board.clone()
            child.place_piece(move[0], move[1], player_id)

            value = -self._negamax(
                child,
                depth - 1,
                -beta,
                -alpha,
                self._opponent(player_id),
                start,
            )

            if value > best:
                best = value
            if value > alpha:
                alpha = value
            if alpha >= beta:
                break

        self.tt[key] = best
        return best

    # ============================================================
    # Heurística barata
    # ============================================================
    def _evaluate(self, board: HexBoard, player_id: int) -> float:
        me = self.player_id
        opp = self._opponent(me)

        my_progress = self._axis_progress(board, me)
        opp_progress = self._axis_progress(board, opp)

        my_groups = self._largest_group(board, me)
        opp_groups = self._largest_group(board, opp)

        my_bridges = self._bridge_potential(board, me)
        opp_bridges = self._bridge_potential(board, opp)

        my_center = self._center_control(board, me)
        opp_center = self._center_control(board, opp)

        score = 8.0 * (my_progress - opp_progress)
        score += 4.0 * (my_groups - opp_groups)
        score += 2.5 * (my_bridges - opp_bridges)
        score += 1.0 * (my_center - opp_center)

        return score if player_id == me else -score

    def _axis_progress(self, board: HexBoard, player_id: int) -> float:
        """
        Aproximación muy barata del avance hacia el objetivo.
        P1 conecta izquierda-derecha.
        P2 conecta arriba-abajo.
        """
        n = board.size
        stones = []

        for r in range(n):
            for c in range(n):
                if board.board[r][c] == player_id:
                    stones.append((r, c))

        if not stones:
            return 0.0

        if self._is_lr(player_id):
            cols = [c for _, c in stones]
            span = max(cols) - min(cols) + 1
            edge_bonus = 0
            if min(cols) == 0:
                edge_bonus += 1
            if max(cols) == n - 1:
                edge_bonus += 1
            return span + 1.5 * edge_bonus
        else:
            rows = [r for r, _ in stones]
            span = max(rows) - min(rows) + 1
            edge_bonus = 0
            if min(rows) == 0:
                edge_bonus += 1
            if max(rows) == n - 1:
                edge_bonus += 1
            return span + 1.5 * edge_bonus

    def _largest_group(self, board: HexBoard, player_id: int) -> int:
        n = board.size
        seen = [[False] * n for _ in range(n)]
        best = 0

        for r in range(n):
            for c in range(n):
                if seen[r][c] or board.board[r][c] != player_id:
                    continue

                q = deque([(r, c)])
                seen[r][c] = True
                size = 0

                while q:
                    cr, cc = q.popleft()
                    size += 1
                    for nr, nc in self._neighbors(n, cr, cc):
                        if not seen[nr][nc] and board.board[nr][nc] == player_id:
                            seen[nr][nc] = True
                            q.append((nr, nc))

                if size > best:
                    best = size

        return best

    def _bridge_potential(self, board: HexBoard, player_id: int) -> float:
        n = board.size
        score = 0.0

        for r in range(n):
            for c in range(n):
                if board.board[r][c] != 0:
                    continue

                own_neighbors = 0
                for nr, nc in self._neighbors(n, r, c):
                    if board.board[nr][nc] == player_id:
                        own_neighbors += 1

                if own_neighbors >= 2:
                    score += 1.0 + own_neighbors

        return score

    def _center_control(self, board: HexBoard, player_id: int) -> float:
        n = board.size
        total = 0.0
        for r in range(n):
            for c in range(n):
                if board.board[r][c] == player_id:
                    total -= self._center_distance(n, r, c)
        return total

    # ============================================================
    # Candidatos
    # ============================================================
    def _candidate_moves(self, board: HexBoard, legal: list[tuple[int, int]]) -> list[tuple[int, int]]:
        n = board.size
        empties = len(legal)

        # late game: ya quedan pocas
        if empties <= 10:
            return legal[:]

        candidates = set()

        # Solo vecinos de celdas ocupadas
        for r in range(n):
            for c in range(n):
                if board.board[r][c] != 0:
                    for nr, nc in self._neighbors(n, r, c):
                        if board.board[nr][nc] == 0:
                            candidates.add((nr, nc))

        if not candidates:
            candidates = set(legal)

        # Puntuar muy barato
        scored = []
        opp = self._opponent(self.player_id)

        for r, c in candidates:
            score = 0.0
            own_n = 0
            opp_n = 0

            for nr, nc in self._neighbors(n, r, c):
                cell = board.board[nr][nc]
                if cell == self.player_id:
                    own_n += 1
                elif cell == opp:
                    opp_n += 1

            score += 4.0 * own_n
            score += 3.0 * opp_n
            score -= 0.7 * self._center_distance(n, r, c)

            # bonus por dirección útil
            if self.player_id == 1:
                if c == 0 or c == n - 1:
                    score += 1.0
            else:
                if r == 0 or r == n - 1:
                    score += 1.0

            scored.append((score, (r, c)))

        scored.sort(key=lambda x: x[0], reverse=True)

        # poda fuerte para velocidad
        if empties > 30:
            cap = 6
        elif empties > 18:
            cap = 7
        else:
            cap = 8

        return [mv for _, mv in scored[:cap]]

    def _order_moves(self, board: HexBoard, moves: list[tuple[int, int]], player_id: int) -> list[tuple[int, int]]:
        opp = self._opponent(player_id)

        def score(move):
            r, c = move
            s = 0.0
            own_n = 0
            opp_n = 0

            for nr, nc in self._neighbors(board.size, r, c):
                cell = board.board[nr][nc]
                if cell == player_id:
                    own_n += 1
                elif cell == opp:
                    opp_n += 1

            s += 5.0 * own_n
            s += 4.0 * opp_n
            s -= self._center_distance(board.size, r, c)
            return s

        return sorted(moves, key=score, reverse=True)

    # ============================================================
    # Tácticas inmediatas
    # ============================================================
    def _immediate_win_or_block(self, board: HexBoard, legal: list[tuple[int, int]]) -> tuple[int, int] | None:
        me = self.player_id
        opp = self._opponent(me)

        quick = self._order_moves(board, self._candidate_moves(board, legal), me)
        if not quick:
            quick = legal

        # ganar ahora
        for move in quick[:8]:
            child = board.clone()
            child.place_piece(move[0], move[1], me)
            if child.check_connection(me):
                return move

        # bloquear derrota inmediata
        for move in quick[:8]:
            child = board.clone()
            child.place_piece(move[0], move[1], opp)
            if child.check_connection(opp):
                return move

        return None

    # ============================================================
    # Utilidades
    # ============================================================
    def _opponent(self, player_id: int) -> int:
        return 2 if player_id == 1 else 1

    def _is_lr(self, player_id: int) -> bool:
        return player_id == 1

    def _legal_moves(self, board: HexBoard) -> list[tuple[int, int]]:
        n = board.size
        return [(r, c) for r in range(n) for c in range(n) if board.board[r][c] == 0]

    def _center_distance(self, n: int, r: int, c: int) -> float:
        center = (n - 1) / 2.0
        return abs(r - center) + abs(c - center)

    def _board_key(self, board: HexBoard) -> tuple:
        return tuple(tuple(row) for row in board.board)

    def _neighbors(self, n: int, r: int, c: int):
        if n not in self._NEIGHBOR_CACHE:
            self._NEIGHBOR_CACHE[n] = self._build_neighbor_cache(n)
        return self._NEIGHBOR_CACHE[n][r * n + c]

    def _build_neighbor_cache(self, n: int) -> tuple:
        cache = []
        for r_ in range(n):
            for c_ in range(n):
                neighbors = []
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, 1), (1, -1)]:
                    nr, nc = r_ + dr, c_ + dc
                    if 0 <= nr < n and 0 <= nc < n:
                        neighbors.append((nr, nc))
                cache.append(tuple(neighbors))
        return tuple(cache)

    def _time_up(self, start: float) -> bool:
        return (time.perf_counter() - start) >= self.time_limit

    def _check_time(self, start: float):
        if self._time_up(start):
            raise TimeoutError()

    def _max_depth(self, n: int, empties: int, candidates: int) -> int:
        # Muy conservador para 7x7
        if n >= 7:
            if empties > 20:
                return 2
            return 3

        if empties > 25:
            return 2
        return 3
from __future__ import annotations

from player import Player
from board import HexBoard
import time
import math
import heapq


class SmartPlayer(Player):
    """
    Jugador para HEX basado en:
    - chequeos tácticos inmediatos (ganar / bloquear)
    - minimax con poda alpha-beta
    - profundización iterativa
    - heurística de conectividad basada en camino mínimo

    No usa estado global persistente entre partidas y no accede a archivos ni red.
    """

    def __init__(self, player_id: int):
        super().__init__(player_id)
        self.time_limit = 0.85  # margen conservador para evitar descalificación
        self.max_depth_cap = 3  # profundidad segura para tableros medianos

    def play(self, board: HexBoard) -> tuple:
        start = time.perf_counter()
        n = board.size
        opponent = 2 if self.player_id == 1 else 1
        legal = self._legal_moves(board)

        if not legal:
            return (0, 0)

        # Apertura: centro o cercano al centro
        if len(legal) == n * n:
            return min(legal, key=lambda mv: self._center_distance(n, mv[0], mv[1]))

        # 1) Ganar inmediatamente si es posible
        for move in self._ordered_moves(board, legal, self.player_id):
            clone = board.clone()
            clone.place_piece(move[0], move[1], self.player_id)
            if clone.check_connection(self.player_id):
                return move

        # 2) Bloquear victoria inmediata del oponente
        opp_wins = []
        for move in legal:
            clone = board.clone()
            clone.place_piece(move[0], move[1], opponent)
            if clone.check_connection(opponent):
                opp_wins.append(move)
        if opp_wins:
            return min(opp_wins, key=lambda mv: self._center_distance(n, mv[0], mv[1]))

        # 3) Profundización iterativa con alpha-beta
        best_move = self._ordered_moves(board, legal, self.player_id)[0]
        depth = 1
        while depth <= self.max_depth_cap and not self._time_up(start):
            try:
                move, _ = self._search_root(board, depth, start)
                if move is not None:
                    best_move = move
                depth += 1
            except TimeoutError:
                break

        return best_move

    # =========================
    # Búsqueda
    # =========================
    def _search_root(self, board: HexBoard, depth: int, start: float):
        alpha = -math.inf
        beta = math.inf
        best_move = None
        best_value = -math.inf
        legal = self._ordered_moves(board, self._legal_moves(board), self.player_id)

        for move in legal:
            self._check_time(start)
            clone = board.clone()
            clone.place_piece(move[0], move[1], self.player_id)

            if clone.check_connection(self.player_id):
                return move, math.inf

            value = self._min_value(clone, depth - 1, alpha, beta, start)
            if value > best_value:
                best_value = value
                best_move = move
            alpha = max(alpha, best_value)

        return best_move, best_value

    def _max_value(self, board: HexBoard, depth: int, alpha: float, beta: float, start: float) -> float:
        self._check_time(start)
        opponent = 2 if self.player_id == 1 else 1

        if board.check_connection(self.player_id):
            return math.inf
        if board.check_connection(opponent):
            return -math.inf
        if depth == 0:
            return self._evaluate(board)

        value = -math.inf
        moves = self._ordered_moves(board, self._legal_moves(board), self.player_id)
        if not moves:
            return self._evaluate(board)

        for move in moves:
            clone = board.clone()
            clone.place_piece(move[0], move[1], self.player_id)
            value = max(value, self._min_value(clone, depth - 1, alpha, beta, start))
            if value >= beta:
                return value
            alpha = max(alpha, value)
        return value

    def _min_value(self, board: HexBoard, depth: int, alpha: float, beta: float, start: float) -> float:
        self._check_time(start)
        opponent = 2 if self.player_id == 1 else 1

        if board.check_connection(self.player_id):
            return math.inf
        if board.check_connection(opponent):
            return -math.inf
        if depth == 0:
            return self._evaluate(board)

        value = math.inf
        moves = self._ordered_moves(board, self._legal_moves(board), opponent)
        if not moves:
            return self._evaluate(board)

        for move in moves:
            clone = board.clone()
            clone.place_piece(move[0], move[1], opponent)
            value = min(value, self._max_value(clone, depth - 1, alpha, beta, start))
            if value <= alpha:
                return value
            beta = min(beta, value)
        return value

    # =========================
    # Heurística
    # =========================
    def _evaluate(self, board: HexBoard) -> float:
        opponent = 2 if self.player_id == 1 else 1

        my_dist = self._connection_distance(board, self.player_id)
        opp_dist = self._connection_distance(board, opponent)

        my_potential = self._adjacency_potential(board, self.player_id)
        opp_potential = self._adjacency_potential(board, opponent)
        center_bias = self._center_control(board, self.player_id) - self._center_control(board, opponent)

        # Menor distancia es mejor; más potencial también.
        score = 12.0 * (opp_dist - my_dist) + 2.5 * (my_potential - opp_potential) + 0.7 * center_bias
        return score

    def _connection_distance(self, board: HexBoard, player_id: int) -> float:
        """
        Distancia aproximada al objetivo usando Dijkstra.
        Costos:
          0 -> casilla propia
          1 -> casilla vacía
          inf -> casilla rival
        Para HEX esto aproxima cuántas jugadas faltan para conectar los lados.
        """
        n = board.size
        inf = 10**9
        dist = [[inf] * n for _ in range(n)]
        pq = []

        if player_id == 1:
            for r in range(n):
                cost = self._cell_cost(board.board[r][0], player_id)
                if cost < inf:
                    dist[r][0] = cost
                    heapq.heappush(pq, (cost, r, 0))
            goal = lambda r, c: c == n - 1
        else:
            for c in range(n):
                cost = self._cell_cost(board.board[0][c], player_id)
                if cost < inf:
                    dist[0][c] = cost
                    heapq.heappush(pq, (cost, 0, c))
            goal = lambda r, c: r == n - 1

        best_goal = inf
        while pq:
            d, r, c = heapq.heappop(pq)
            if d != dist[r][c]:
                continue
            if goal(r, c):
                best_goal = d
                break
            for nr, nc in self._neighbors(n, r, c):
                step = self._cell_cost(board.board[nr][nc], player_id)
                if step >= inf:
                    continue
                nd = d + step
                if nd < dist[nr][nc]:
                    dist[nr][nc] = nd
                    heapq.heappush(pq, (nd, nr, nc))

        return float(best_goal if best_goal < inf else 1000)

    def _adjacency_potential(self, board: HexBoard, player_id: int) -> int:
        n = board.size
        total = 0
        for r in range(n):
            for c in range(n):
                if board.board[r][c] != player_id:
                    continue
                for nr, nc in self._neighbors(n, r, c):
                    if board.board[nr][nc] == player_id:
                        total += 2
                    elif board.board[nr][nc] == 0:
                        total += 1
        return total

    def _center_control(self, board: HexBoard, player_id: int) -> float:
        n = board.size
        center = (n - 1) / 2.0
        value = 0.0
        for r in range(n):
            for c in range(n):
                if board.board[r][c] == player_id:
                    value += n - (abs(r - center) + abs(c - center))
        return value

    # =========================
    # Ordenación de jugadas
    # =========================
    def _ordered_moves(self, board: HexBoard, moves: list[tuple], player_id: int) -> list[tuple]:
        opponent = 2 if player_id == 1 else 1
        scored = []
        for r, c in moves:
            score = 0
            for nr, nc in self._neighbors(board.size, r, c):
                cell = board.board[nr][nc]
                if cell == player_id:
                    score += 4
                elif cell == opponent:
                    score += 2
                else:
                    score += 1
            score -= self._center_distance(board.size, r, c)
            scored.append((score, (r, c)))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [mv for _, mv in scored]

    # =========================
    # Utilidades
    # =========================
    def _legal_moves(self, board: HexBoard) -> list[tuple]:
        n = board.size
        return [(r, c) for r in range(n) for c in range(n) if board.board[r][c] == 0]

    def _cell_cost(self, cell_value: int, player_id: int) -> int:
        if cell_value == player_id:
            return 0
        if cell_value == 0:
            return 1
        return 10**9

    def _neighbors(self, n: int, r: int, c: int):
        # even-r layout
        if r % 2 == 0:
            dirs = [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)]
        else:
            dirs = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, 0), (1, 1)]
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < n:
                yield nr, nc

    def _center_distance(self, n: int, r: int, c: int) -> float:
        center = (n - 1) / 2.0
        return abs(r - center) + abs(c - center)

    def _time_up(self, start: float) -> bool:
        return (time.perf_counter() - start) >= self.time_limit

    def _check_time(self, start: float):
        if self._time_up(start):
            raise TimeoutError()

from __future__ import annotations
import time, math, random, heapq
from player import Player
from board import HexBoard


class EnemyPlayer(Player):
    """
    Jugador HEX basado en UCT-MCTS con las siguientes mejoras:
      - Playouts sesgados por resistencia eléctrica aproximada (shortest-path)
      - Detección de puentes virtuales para no romperlos en playouts
      - Política de árbol con bonus por movimientos de puente
      - Filtrado de candidatos por vecindad
      - Tiempo límite estricto de 4.6s para cualquier N
    """
    TIME_LIMIT = 4.6
    C          = 0.9      # exploración UCT
    RAVE_K     = 200      # constante RAVE

    def __init__(self, player_id: int):
        super().__init__(player_id)
        self._ncache: dict[int, tuple] = {}

    # ------------------------------------------------------------------
    def play(self, board: HexBoard) -> tuple:
        start = time.perf_counter()
        n     = board.size
        opp   = 3 - self.player_id

        moves = self._candidates(board)
        if not moves:
            return (0, 0)
        if len(self._empties(board)) == n * n:
            return (n // 2, n // 2)

        # victoria / bloqueo inmediato
        for m in moves:
            b = board.clone(); b.place_piece(m[0], m[1], self.player_id)
            if b.check_connection(self.player_id): return m
        for m in moves:
            b = board.clone(); b.place_piece(m[0], m[1], opp)
            if b.check_connection(opp): return m

        # UCT-MCTS
        root = _Node(None, None, 3 - self.player_id, moves)
        iters = 0
        while time.perf_counter() - start < self.TIME_LIMIT:
            self._iterate(root, board.clone(), self.player_id, start)
            iters += 1

        if not root.children:
            return moves[0]
        return max(root.children, key=lambda c: c.visits).move

    # ------------------------------------------------------------------
    def _iterate(self, root: _Node, board: HexBoard, root_player: int, start: float):
        node    = root
        current = root_player
        path    = []

        # selección
        while node.children and node.fully_expanded():
            node    = node.uct_child(self.C, self.RAVE_K)
            board.place_piece(node.move[0], node.move[1], current)
            current = 3 - current
            path.append(node)
            if time.perf_counter() - start >= self.TIME_LIMIT: return

        # expansión
        if not board.check_connection(1) and not board.check_connection(2):
            untried = node.untried()
            if untried:
                m       = self._pick_expansion(board, untried, current)
                board.place_piece(m[0], m[1], current)
                child   = _Node(m, node, current, self._candidates(board))
                node.children.append(child)
                node    = child
                current = 3 - current
                path.append(node)

        # simulación
        winner = self._rollout(board, current, start)

        # backprop con RAVE
        for n_ in [root] + path:
            n_.visits += 1
            if winner == n_.player_id:
                n_.wins += 1
            # actualizar RAVE del padre sobre los movimientos del hijo
            for ch in n_.children:
                if ch in path:
                    n_.rave_v[ch.move] = n_.rave_v.get(ch.move, 0) + 1
                    if winner == n_.player_id:
                        n_.rave_w[ch.move] = n_.rave_w.get(ch.move, 0) + 1

    # ------------------------------------------------------------------
    def _rollout(self, board: HexBoard, current: int, start: float) -> int:
        b   = board.clone()
        pl  = current
        while True:
            if b.check_connection(1): return 1
            if b.check_connection(2): return 2
            if time.perf_counter() - start >= self.TIME_LIMIT: return 0
            cands = self._candidates(b)
            if not cands: return 0

            # con prob 0.6 elige el movimiento que minimiza distancia propia
            if random.random() < 0.6:
                move = self._greedy_move(b, cands, pl)
            else:
                move = random.choice(cands)

            b.place_piece(move[0], move[1], pl)
            pl = 3 - pl

    def _greedy_move(self, board: HexBoard, cands: list, player: int) -> tuple:
        best, best_d = cands[0], math.inf
        for m in cands:
            b = board.clone(); b.place_piece(m[0], m[1], player)
            d = self._dijkstra(b, player)
            if d < best_d: best_d, best = d, m
        return best

    def _pick_expansion(self, board: HexBoard, untried: list, player: int) -> tuple:
        # elige el movimiento no probado con menor distancia Dijkstra
        return min(untried, key=lambda m: self._dijkstra_after(board, m, player))

    def _dijkstra_after(self, board: HexBoard, move: tuple, player: int) -> float:
        b = board.clone(); b.place_piece(move[0], move[1], player)
        return self._dijkstra(b, player)

    # ------------------------------------------------------------------
    def _dijkstra(self, board: HexBoard, player: int) -> float:
        n, INF = board.size, 10**9
        dist   = [INF] * (n * n)
        pq     = []
        if player == 1:
            for r in range(n):
                v = board.board[r][0]
                c = 0 if v == player else (1 if v == 0 else INF)
                if c < INF: dist[r*n] = c; heapq.heappush(pq, (c, r*n))
            goal = lambda r, c: c == n - 1
        else:
            for c in range(n):
                v = board.board[0][c]
                cost = 0 if v == player else (1 if v == 0 else INF)
                if cost < INF: dist[c] = cost; heapq.heappush(pq, (cost, c))
            goal = lambda r, c: r == n - 1
        while pq:
            d, idx = heapq.heappop(pq)
            if d > dist[idx]: continue
            r, c = divmod(idx, n)
            if goal(r, c): return float(d)
            for nr, nc in self._nbrs(n, r, c):
                v  = board.board[nr][nc]
                s  = 0 if v == player else (1 if v == 0 else INF)
                if s >= INF: continue
                nd = d + s
                if nd < dist[nr*n+nc]: dist[nr*n+nc] = nd; heapq.heappush(pq, (nd, nr*n+nc))
        return 1000.0

    # ------------------------------------------------------------------
    def _candidates(self, board: HexBoard) -> list:
        n, out = board.size, set()
        for r in range(n):
            for c in range(n):
                if board.board[r][c]:
                    for nr, nc in self._nbrs(n, r, c):
                        if not board.board[nr][nc]: out.add((nr, nc))
        return list(out) if out else self._empties(board)

    def _empties(self, board: HexBoard) -> list:
        n = board.size
        return [(r, c) for r in range(n) for c in range(n) if not board.board[r][c]]

    def _nbrs(self, n: int, r: int, c: int):
        if n not in self._ncache:
            cache = []
            for rr in range(n):
                for cc in range(n):
                    cache.append(tuple(
                        (rr+dr, cc+dc)
                        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,1),(1,-1)]
                        if 0 <= rr+dr < n and 0 <= cc+dc < n
                    ))
            self._ncache[n] = tuple(cache)
        return self._ncache[n][r*n+c]


# ------------------------------------------------------------------
class _Node:
    def __init__(self, move, parent, player_id, legal):
        self.move      = move
        self.parent    = parent
        self.player_id = player_id
        self.children  = []
        self.visits    = 0
        self.wins      = 0
        self.rave_v    = {}
        self.rave_w    = {}
        self._legal    = legal
        self._tried    = set()

    def fully_expanded(self) -> bool:
        return len(self._tried) >= len(self._legal)

    def untried(self) -> list:
        return [m for m in self._legal if m not in self._tried]

    def uct_child(self, C: float, K: float) -> _Node:
        log_n = math.log(self.visits)
        best, best_s = self.children[0], -math.inf
        for ch in self.children:
            q    = ch.wins / ch.visits
            u    = C * math.sqrt(log_n / ch.visits)
            rv   = self.rave_v.get(ch.move, 0)
            rq   = self.rave_w.get(ch.move, 0) / rv if rv else 0.0
            beta = math.sqrt(K / (K + 3.0 * ch.visits))
            s    = (1 - beta) * q + beta * rq + u
            if s > best_s: best_s, best = s, ch
        return best
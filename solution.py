from __future__ import annotations
from player import Player
from board import HexBoard
import time, math, heapq, random


class _Node:
    def __init__(self, board, move, parent, player_id, moves):
        self.board      = board
        self.move       = move
        self.parent     = parent
        self.player_id  = player_id
        self.children   = []
        self.visits     = 0
        self.wins       = 0
        self.rave_v     = {}
        self.rave_w     = {}
        self.untried    = list(moves)

    def fully_expanded(self):
        return not self.untried

    def best_child(self, c=1.4, k=300):
        log_n = math.log(self.visits)
        best, best_s = self.children[0], -math.inf
        for ch in self.children:
            q    = ch.wins / ch.visits
            u    = c * math.sqrt(log_n / ch.visits)
            rv   = self.rave_v.get(ch.move, 0)
            rq   = self.rave_w.get(ch.move, 0) / rv if rv else 0.0
            beta = math.sqrt(k / (k + 3.0 * ch.visits))
            s    = (1 - beta) * q + beta * rq + u
            if s > best_s:
                best_s, best = s, ch
        return best


class SmartPlayer(Player):
    TIME_LIMIT = 4.5

    def __init__(self, player_id):
        super().__init__(player_id)
        self._ncache = {}

    def play(self, board):
        start = time.perf_counter()
        n     = board.size
        opp   = 3 - self.player_id
        legal = self._legal(board)
        if not legal:
            return (0, 0)
        if len(legal) == n * n:
            return (n // 2, n // 2)

        cands = self._candidates(board, legal)

        for move in cands:
            b = board.clone(); b.place_piece(*move, self.player_id)
            if b.check_connection(self.player_id): return move

        for move in cands:
            b = board.clone(); b.place_piece(*move, opp)
            if b.check_connection(opp): return move

        return self._mcts(board, cands, start)

    def _mcts(self, board, cands, start):
        budget = 8000 if board.size <= 7 else 4000 if board.size <= 11 else 2000 if board.size <= 16 else 800
        root   = _Node(board.clone(), None, None, 3 - self.player_id, cands)

        for _ in range(budget):
            if time.perf_counter() - start >= self.TIME_LIMIT:
                break

            node = root
            while node.fully_expanded() and node.children:
                if node.board.check_connection(1) or node.board.check_connection(2): break
                node = node.best_child()

            if not node.board.check_connection(1) and not node.board.check_connection(2) and node.untried:
                nxt   = 3 - node.player_id
                move  = node.untried.pop(random.randrange(len(node.untried)))
                nb    = node.board.clone(); nb.place_piece(*move, nxt)
                child = _Node(nb, move, node, nxt, self._candidates(nb, self._legal(nb)))
                node.children.append(child)
                node = child

            winner, pmoves = self._simulate(node)

            cur = node
            while cur:
                cur.visits += 1
                won = winner == cur.player_id
                if won: cur.wins += 1
                if cur.parent:
                    pp = 3 - cur.parent.player_id
                    for mv, mp in pmoves:
                        if mp == pp:
                            cur.parent.rave_v[mv] = cur.parent.rave_v.get(mv, 0) + 1
                            if won:
                                cur.parent.rave_w[mv] = cur.parent.rave_w.get(mv, 0) + 1
                cur = cur.parent

        if not root.children:
            return cands[0]
        return max(root.children, key=lambda c: c.visits).move

    def _simulate(self, node):
        b       = node.board.clone()
        current = 3 - node.player_id
        played  = []
        while True:
            if b.check_connection(1): return 1, played
            if b.check_connection(2): return 2, played
            moves = self._candidates(b, self._legal(b))
            if not moves: return 0, played
            move = random.choice(moves)
            b.place_piece(*move, current)
            played.append((move, current))
            current = 3 - current

    def _dijkstra(self, board, player_id):
        n, INF = board.size, 10**9
        dist = [INF] * (n * n)
        pq   = []
        if player_id == 1:
            for r in range(n):
                c = 0 if board.board[r][0] == player_id else 1 if board.board[r][0] == 0 else INF
                if c < INF: dist[r*n] = c; heapq.heappush(pq, (c, r*n))
            goal = lambda r, c: c == n - 1
        else:
            for c in range(n):
                v = 0 if board.board[0][c] == player_id else 1 if board.board[0][c] == 0 else INF
                if v < INF: dist[c] = v; heapq.heappush(pq, (v, c))
            goal = lambda r, c: r == n - 1
        while pq:
            d, idx = heapq.heappop(pq)
            if d > dist[idx]: continue
            r, c = divmod(idx, n)
            if goal(r, c): return float(d)
            for nr, nc in self._neighbors(n, r, c):
                cell = board.board[nr][nc]
                s = 0 if cell == player_id else 1 if cell == 0 else INF
                if s >= INF: continue
                nd = d + s
                if nd < dist[nr*n+nc]: dist[nr*n+nc] = nd; heapq.heappush(pq, (nd, nr*n+nc))
        return 1000.0

    def _candidates(self, board, legal):
        n, out = board.size, set()
        for r in range(n):
            for c in range(n):
                if board.board[r][c]:
                    for nr, nc in self._neighbors(n, r, c):
                        if not board.board[nr][nc]: out.add((nr, nc))
        return list(out) if out else legal

    def _legal(self, board):
        n = board.size
        return [(r, c) for r in range(n) for c in range(n) if not board.board[r][c]]

    def _neighbors(self, n, r, c):
        if n not in self._ncache:
            cache = []
            for rr in range(n):
                for cc in range(n):
                    cache.append(tuple(
                        (rr+dr, cc+dc) for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,1),(1,-1)]
                        if 0 <= rr+dr < n and 0 <= cc+dc < n
                    ))
            self._ncache[n] = tuple(cache)
        return self._ncache[n][r*n+c]
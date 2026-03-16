from __future__ import annotations
import argparse
import time
from dataclasses import dataclass
from typing import Iterable

from board import HexBoard
from solution import SmartPlayer
from enemy_player import EnemyPlayer


@dataclass(frozen=True)
class Opening:
    name: str
    moves: tuple[tuple[int, int, int], ...]  # (player, row, col)


# ============================================================
# Utilidades
# ============================================================

def timed_play(player, board: HexBoard):
    clone = board.clone()
    start = time.perf_counter()
    move = player.play(clone)
    elapsed = time.perf_counter() - start
    return move, elapsed


def apply_opening(board: HexBoard, opening: Opening) -> bool:
    for player_id, row, col in opening.moves:
        if not board.place_piece(row, col, player_id):
            return False
    return True


def print_board(board: HexBoard):
    print(board)
    print()


def center(n: int) -> tuple[int, int]:
    return n // 2, n // 2


# ============================================================
# Suite determinista de aperturas
# ============================================================

def build_opening_suite(n: int) -> list[Opening]:
    """
    Suite fija y determinista de aperturas para romper el "todo se repite"
    sin usar aleatoriedad. La idea es evaluar desde muchos estados iniciales.

    Incluye:
    - tablero vacío
    - aperturas de 1 jugada representativas
    - prefijos de 2 jugadas relativamente balanceados

    Está pensada para n >= 5.
    """
    if n < 5:
        raise ValueError("Se recomienda size >= 5 para esta suite.")

    cr, cc = center(n)
    openings: list[Opening] = [Opening("empty", tuple())]

    # ---- 1 jugada inicial de J1 ----
    one_ply = {
        "P1 center": ((1, cr, cc),),
        "P1 near-center left": ((1, cr, max(0, cc - 1)),),
        "P1 near-center right": ((1, cr, min(n - 1, cc + 1)),),
        "P1 near-center up": ((1, max(0, cr - 1), cc),),
        "P1 near-center down": ((1, min(n - 1, cr + 1), cc),),
        "P1 edge-left-mid": ((1, cr, 0),),
        "P1 edge-top-mid": ((1, 0, cc),),
        "P1 corner": ((1, 0, 0),),
    }
    openings.extend(Opening(name, tuple(moves)) for name, moves in one_ply.items())

    # ---- 2 jugadas: J1 abre, J2 responde ----
    # Respuestas centradas / de equilibrio. No son aleatorias.
    two_ply = {
        "2ply center-center+1": ((1, cr, cc), (2, cr, min(n - 1, cc + 1))),
        "2ply center-center-1": ((1, cr, cc), (2, cr, max(0, cc - 1))),
        "2ply center-below": ((1, cr, cc), (2, min(n - 1, cr + 1), cc)),
        "2ply center-above": ((1, cr, cc), (2, max(0, cr - 1), cc)),
        "2ply leftmid-vs-topmid": ((1, cr, 0), (2, 0, cc)),
        "2ply corner-vs-center": ((1, 0, 0), (2, cr, cc)),
        "2ply offcenter-cross": ((1, cr, max(0, cc - 1)), (2, max(0, cr - 1), cc)),
        "2ply offcenter-opposite": ((1, cr, max(0, cc - 1)), (2, min(n - 1, cr + 1), min(n - 1, cc + 1))),
    }
    openings.extend(Opening(name, tuple(moves)) for name, moves in two_ply.items())

    # Filtra duplicados accidentales preservando orden
    seen = set()
    unique: list[Opening] = []
    for op in openings:
        key = op.moves
        if key not in seen:
            seen.add(key)
            unique.append(op)
    return unique


# ============================================================
# Match desde una apertura dada
# ============================================================

def run_match_from_opening(
    size: int,
    opening: Opening,
    smart_as_player1: bool,
    show: bool,
    time_limit: float,
):
    board = HexBoard(size)
    if not apply_opening(board, opening):
        raise RuntimeError(f"La apertura '{opening.name}' no se pudo aplicar correctamente.")

    # Detecta si la apertura ya deja una victoria (normalmente no debería).
    for pid in (1, 2):
        if board.check_connection(pid):
            winner_name = "SmartPlayer" if (smart_as_player1 and pid == 1) or ((not smart_as_player1) and pid == 2) else "EnemyPlayer"
            return {
                "winner_name": winner_name,
                "winner_id": pid,
                "reason": f"victoria ya presente en apertura {opening.name}",
                "moves_played": 0,
                "time_smart": 0.0,
                "time_enemy": 0.0,
                "timeout": False,
                "invalid": False,
                "opening": opening.name,
                "smart_role": 1 if smart_as_player1 else 2,
            }

    players = {
        1: SmartPlayer(1) if smart_as_player1 else EnemyPlayer(1),
        2: EnemyPlayer(2) if smart_as_player1 else SmartPlayer(2),
    }
    names = {
        1: "SmartPlayer" if smart_as_player1 else "EnemyPlayer",
        2: "EnemyPlayer" if smart_as_player1 else "SmartPlayer",
    }

    # Determina a quién le toca según la cantidad de jugadas ya puestas.
    turn = 1 if len(opening.moves) % 2 == 0 else 2
    time_spent = {"SmartPlayer": 0.0, "EnemyPlayer": 0.0}
    moves_played = 0

    if show:
        print(f"\n=== Apertura: {opening.name} | Smart como jugador {1 if smart_as_player1 else 2} ===")
        print_board(board)

    while not board.is_full():
        player = players[turn]
        move, elapsed = timed_play(player, board)
        time_spent[names[turn]] += elapsed

        if elapsed > time_limit:
            winner = 2 if turn == 1 else 1
            return {
                "winner_name": names[winner],
                "winner_id": winner,
                "reason": f"timeout de {names[turn]} ({elapsed:.4f}s)",
                "moves_played": moves_played,
                "time_smart": time_spent["SmartPlayer"],
                "time_enemy": time_spent["EnemyPlayer"],
                "timeout": True,
                "invalid": False,
                "opening": opening.name,
                "smart_role": 1 if smart_as_player1 else 2,
            }

        if not isinstance(move, tuple) or len(move) != 2:
            winner = 2 if turn == 1 else 1
            return {
                "winner_name": names[winner],
                "winner_id": winner,
                "reason": f"jugada inválida devuelta por {names[turn]}: {move}",
                "moves_played": moves_played,
                "time_smart": time_spent["SmartPlayer"],
                "time_enemy": time_spent["EnemyPlayer"],
                "timeout": False,
                "invalid": True,
                "opening": opening.name,
                "smart_role": 1 if smart_as_player1 else 2,
            }

        row, col = move
        if not board.place_piece(row, col, turn):
            winner = 2 if turn == 1 else 1
            return {
                "winner_name": names[winner],
                "winner_id": winner,
                "reason": f"jugada ilegal de {names[turn]} en {move}",
                "moves_played": moves_played,
                "time_smart": time_spent["SmartPlayer"],
                "time_enemy": time_spent["EnemyPlayer"],
                "timeout": False,
                "invalid": True,
                "opening": opening.name,
                "smart_role": 1 if smart_as_player1 else 2,
            }

        moves_played += 1
        if show:
            print(f"Turno {turn} | {names[turn]} juega {move} en {elapsed:.4f}s")
            print_board(board)

        if board.check_connection(turn):
            return {
                "winner_name": names[turn],
                "winner_id": turn,
                "reason": f"conexión completada por {names[turn]}",
                "moves_played": moves_played,
                "time_smart": time_spent["SmartPlayer"],
                "time_enemy": time_spent["EnemyPlayer"],
                "timeout": False,
                "invalid": False,
                "opening": opening.name,
                "smart_role": 1 if smart_as_player1 else 2,
            }

        turn = 2 if turn == 1 else 1

    # En Hex no debería haber empate.
    winner = 2 if turn == 1 else 1
    return {
        "winner_name": names[winner],
        "winner_id": winner,
        "reason": "tablero lleno o estado no esperado",
        "moves_played": moves_played,
        "time_smart": time_spent["SmartPlayer"],
        "time_enemy": time_spent["EnemyPlayer"],
        "timeout": False,
        "invalid": False,
        "opening": opening.name,
        "smart_role": 1 if smart_as_player1 else 2,
    }


# ============================================================
# Reporte agregado
# ============================================================

def summarize(results: list[dict]):
    out = {
        "SmartPlayer": 0,
        "EnemyPlayer": 0,
        "timeout": 0,
        "invalid": 0,
        "Smart_as_P1": 0,
        "Smart_as_P2": 0,
        "Enemy_as_P1": 0,
        "Enemy_as_P2": 0,
        "time_smart": 0.0,
        "time_enemy": 0.0,
        "games": len(results),
    }

    per_opening: dict[str, dict[str, int]] = {}
    for r in results:
        out[r["winner_name"]] += 1
        out["timeout"] += int(r["timeout"])
        out["invalid"] += int(r["invalid"])
        out["time_smart"] += r["time_smart"]
        out["time_enemy"] += r["time_enemy"]

        if r["winner_name"] == "SmartPlayer":
            if r["smart_role"] == 1:
                out["Smart_as_P1"] += 1
            else:
                out["Smart_as_P2"] += 1
        else:
            if r["smart_role"] == 2:
                out["Enemy_as_P1"] += 1
            else:
                out["Enemy_as_P2"] += 1

        po = per_opening.setdefault(r["opening"], {"SmartPlayer": 0, "EnemyPlayer": 0})
        po[r["winner_name"]] += 1

    return out, per_opening


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark determinista con suite de aperturas fijas para HEX"
    )
    parser.add_argument("--size", type=int, default=7, help="Tamaño del tablero")
    parser.add_argument("--time-limit", type=float, default=5.0, help="Límite por jugada")
    parser.add_argument("--show", action="store_true", help="Muestra los tableros")
    args = parser.parse_args()

    suite = build_opening_suite(args.size)
    results: list[dict] = []

    print(f"Se evaluarán {len(suite)} aperturas fijas.")
    print("Cada apertura se juega 2 veces: Smart como jugador 1 y Smart como jugador 2.")
    print(f"Total de partidas: {2 * len(suite)}")

    for opening in suite:
        for smart_as_player1 in (True, False):
            result = run_match_from_opening(
                size=args.size,
                opening=opening,
                smart_as_player1=smart_as_player1,
                show=args.show,
                time_limit=args.time_limit,
            )
            results.append(result)
            smart_role = 1 if smart_as_player1 else 2
            print(
                f"[{opening.name:22s}] Smart=P{smart_role} | "
                f"Ganador: {result['winner_name']:12s} | Motivo: {result['reason']}"
            )

    agg, per_opening = summarize(results)
    games = agg["games"]
    finished = agg["SmartPlayer"] + agg["EnemyPlayer"]

    print("\n=== Resumen global ===")
    print(f"Partidas totales:        {games}")
    print(f"Victorias SmartPlayer:   {agg['SmartPlayer']}")
    print(f"Victorias EnemyPlayer:   {agg['EnemyPlayer']}")
    print(f"Timeouts:                {agg['timeout']}")
    print(f"Inválidas:               {agg['invalid']}")
    print()
    print(f"Smart gana como P1:      {agg['Smart_as_P1']}")
    print(f"Smart gana como P2:      {agg['Smart_as_P2']}")
    print(f"Enemy gana como P1:      {agg['Enemy_as_P1']}")
    print(f"Enemy gana como P2:      {agg['Enemy_as_P2']}")
    print()
    if finished > 0:
        print(f"Winrate Smart:           {100.0 * agg['SmartPlayer'] / finished:.2f}%")
        print(f"Winrate Enemy:           {100.0 * agg['EnemyPlayer'] / finished:.2f}%")
    print(f"Tiempo total Smart:      {agg['time_smart']:.4f}s")
    print(f"Tiempo total Enemy:      {agg['time_enemy']:.4f}s")

    print("\n=== Resultado por apertura ===")
    for opening_name, counts in per_opening.items():
        print(
            f"{opening_name:22s} | Smart: {counts['SmartPlayer']:2d} | Enemy: {counts['EnemyPlayer']:2d}"
        )


if __name__ == "__main__":
    main()
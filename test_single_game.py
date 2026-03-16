"""
test_single_game.py
-------------------
Corre una sola partida entre SmartPlayer y EnemyPlayer,
mostrando el tablero actualizado tras cada jugada y un
resumen de tiempos por jugada al final.

Uso:
    python test_single_game.py --size 7
    python test_single_game.py --size 11 --smart-first false
    python test_single_game.py --size 7 --delay 0.3
"""
from __future__ import annotations
import argparse
import os
import time

from board import HexBoard
from solution import SmartPlayer
from enemy_player import EnemyPlayer

TIME_LIMIT = 5.0
BAR_WIDTH  = 30           # ancho de la barra de tiempo


# ─────────────────────────────────────────
# Utilidades de visualización
# ─────────────────────────────────────────

def clear():
    os.system("cls" if os.name == "nt" else "clear")


def time_bar(elapsed: float, limit: float = TIME_LIMIT) -> str:
    """Barra de progreso del tiempo consumido."""
    ratio  = min(elapsed / limit, 1.0)
    filled = int(BAR_WIDTH * ratio)
    bar    = "█" * filled + "░" * (BAR_WIDTH - filled)
    color  = "\033[92m" if ratio < 0.6 else "\033[93m" if ratio < 0.9 else "\033[91m"
    reset  = "\033[0m"
    return f"{color}[{bar}]{reset} {elapsed:.3f}s / {limit:.1f}s"


def render(board: HexBoard, move_log: list[dict], turn: int,
           names: dict, move_num: int):
    """Imprime el estado completo de la partida."""
    clear()
    n = board.size

    # encabezado
    print("=" * 60)
    print(f"  PARTIDA HEX {n}x{n}  |  Jugada #{move_num}")
    print(f"  P1 = {names[1]}   P2 = {names[2]}")
    print("=" * 60)

    # tablero
    print(board)
    print()

    # log de jugadas con barra de tiempo
    print(f"  {'#':>3}  {'Jugador':<14} {'Movimiento':<12} {'Tiempo':>8}  Barra")
    print(f"  {'-'*3}  {'-'*14} {'-'*12} {'-'*8}  {'-'*(BAR_WIDTH+4)}")
    for entry in move_log[-15:]:          # mostrar últimas 15 jugadas
        flag = "  ⚠️ VIOLA" if entry["elapsed"] > TIME_LIMIT else ""
        print(
            f"  {entry['num']:>3}  {entry['name']:<14} "
            f"{str(entry['move']):<12} {entry['elapsed']:>7.3f}s  "
            f"{time_bar(entry['elapsed'])}{flag}"
        )


def print_summary(move_log: list[dict], names: dict, winner_name: str,
                  reason: str, n: int):
    """Imprime el resumen final de tiempos."""
    print("\n" + "=" * 60)
    print(f"  RESULTADO: {winner_name} gana  ({reason})")
    print("=" * 60)

    for pid, name in names.items():
        entries = [e for e in move_log if e["name"] == name]
        if not entries:
            continue
        times   = [e["elapsed"] for e in entries]
        viols   = [t for t in times if t > TIME_LIMIT]
        print(f"\n  ── {name} (P{pid}) ──")
        print(f"     Jugadas:          {len(times)}")
        print(f"     Tiempo total:     {sum(times):.3f}s")
        print(f"     Tiempo máximo:    {max(times):.3f}s")
        print(f"     Tiempo promedio:  {sum(times)/len(times):.3f}s")
        print(f"     Tiempo mínimo:    {min(times):.3f}s")
        print(f"     Violaciones >5s:  {len(viols)}", end="")
        print("  ✅" if not viols else "  ❌")

    print()
    # distribución de tiempos de SmartPlayer
    smart_entries = [e for e in move_log if e["name"] == "SmartPlayer"]
    if smart_entries:
        buckets = {"0-1s": 0, "1-2s": 0, "2-3s": 0, "3-4s": 0, "4-5s": 0, ">5s": 0}
        for e in smart_entries:
            t = e["elapsed"]
            if   t < 1: buckets["0-1s"] += 1
            elif t < 2: buckets["1-2s"] += 1
            elif t < 3: buckets["2-3s"] += 1
            elif t < 4: buckets["3-4s"] += 1
            elif t < 5: buckets["4-5s"] += 1
            else:        buckets[">5s"]  += 1
        print("  Distribución de tiempos (SmartPlayer):")
        for bucket, count in buckets.items():
            bar = "▓" * count
            print(f"     {bucket:>6}  {bar} ({count})")
    print()


# ─────────────────────────────────────────
# Partida principal
# ─────────────────────────────────────────

def run_game(n: int, smart_as_p1: bool, delay: float):
    board = HexBoard(n)

    if smart_as_p1:
        players = {1: SmartPlayer(1), 2: EnemyPlayer(2)}
        names   = {1: "SmartPlayer",  2: "EnemyPlayer"}
    else:
        players = {1: EnemyPlayer(1), 2: SmartPlayer(2)}
        names   = {1: "EnemyPlayer",  2: "SmartPlayer"}

    turn     = 1
    move_log = []
    move_num = 0

    render(board, move_log, turn, names, move_num)
    print(f"\n  Turno de {names[turn]}... ", end="", flush=True)

    while not board.is_full():
        player = players[turn]

        start   = time.perf_counter()
        move    = player.play(board.clone())
        elapsed = time.perf_counter() - start

        entry = {
            "num":     move_num + 1,
            "name":    names[turn],
            "move":    move,
            "elapsed": elapsed,
        }
        move_log.append(entry)
        move_num += 1

        # validar jugada
        if not isinstance(move, tuple) or len(move) != 2:
            print(f"\n  ❌ Jugada inválida de {names[turn]}: {move}")
            break

        row, col = move
        if not board.place_piece(row, col, turn):
            print(f"\n  ❌ Posición ilegal de {names[turn]}: {move}")
            break

        render(board, move_log, turn, names, move_num)

        if board.check_connection(turn):
            print_summary(move_log, names, names[turn],
                          "conexión completada", n)
            return

        turn = 3 - turn
        if delay > 0:
            time.sleep(delay)

        print(f"\n  Turno de {names[turn]}... ", end="", flush=True)

    print_summary(move_log, names, "?", "partida terminada sin ganador", n)


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Test de una sola partida HEX con tracker de tiempo")
    parser.add_argument("--size",        type=int,   default=7,
                        help="Tamaño del tablero NxN (default: 7)")
    parser.add_argument("--smart-first", type=str,   default="true",
                        help="'true' = Smart es P1, 'false' = Smart es P2 (default: true)")
    parser.add_argument("--delay",       type=float, default=0.0,
                        help="Segundos de pausa entre jugadas para ver el tablero (default: 0)")
    args = parser.parse_args()

    smart_first = args.smart_first.lower() not in ("false", "0", "no")
    run_game(args.size, smart_first, args.delay)


if __name__ == "__main__":
    main()
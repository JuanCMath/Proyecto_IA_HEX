from __future__ import annotations

import argparse
import time
from board import HexBoard
from random_player import RandomPlayer
from solution import SmartPlayer


def print_board(board: HexBoard):
    print(board)
    print()


def timed_play(player, board: HexBoard):
    clone = board.clone()  # se le pasa una copia, como dice la orientación
    start = time.perf_counter()
    move = player.play(clone)
    elapsed = time.perf_counter() - start
    return move, elapsed


def main():
    parser = argparse.ArgumentParser(description="Entorno local de prueba para HEX")
    parser.add_argument("--size", type=int, default=5, help="Tamaño del tablero")
    parser.add_argument("--games", type=int, default=1, help="Cantidad de partidas")
    parser.add_argument("--show", action="store_true", help="Mostrar tablero en cada turno")
    parser.add_argument("--time-limit", type=float, default=5.0, help="Límite por jugada")
    args = parser.parse_args()

    results = {1: 0, 2: 0, "invalid": 0, "timeout": 0}

    for game in range(args.games):
        board = HexBoard(args.size)

        # alternar quién empieza
        if game % 2 == 0:
            players = {1: SmartPlayer(1), 2: RandomPlayer(2)}
            names = {1: "SmartPlayer", 2: "RandomPlayer"}
        else:
            players = {1: RandomPlayer(1), 2: SmartPlayer(2)}
            names = {1: "RandomPlayer", 2: "SmartPlayer"}

        turn = 1
        winner = None

        while not board.is_full():
            player = players[turn]
            move, elapsed = timed_play(player, board)

            if elapsed > args.time_limit:
                print(f"[Partida {game + 1}] {names[turn]} excedió el tiempo: {elapsed:.4f}s")
                results["timeout"] += 1
                winner = 2 if turn == 1 else 1
                break

            if not isinstance(move, tuple) or len(move) != 2:
                print(f"[Partida {game + 1}] {names[turn]} devolvió una jugada inválida: {move}")
                results["invalid"] += 1
                winner = 2 if turn == 1 else 1
                break

            row, col = move
            ok = board.place_piece(row, col, turn)
            if not ok:
                print(f"[Partida {game + 1}] {names[turn]} intentó jugar ilegalmente en {move}")
                results["invalid"] += 1
                winner = 2 if turn == 1 else 1
                break

            if args.show:
                print(f"Partida {game + 1} | {names[turn]} ({turn}) juega {move} en {elapsed:.4f}s")
                print_board(board)

            if board.check_connection(turn):
                winner = turn
                break

            turn = 2 if turn == 1 else 1

        if winner is None:
            # En HEX no debe haber empates, pero esto evita dejar la partida sin resultado.
            winner = 2 if turn == 1 else 1

        results[winner] += 1
        print(f"[Partida {game + 1}] Ganador: {names[winner]} (jugador {winner})")

    print("\nResumen:")
    print(results)


if __name__ == "__main__":
    main()

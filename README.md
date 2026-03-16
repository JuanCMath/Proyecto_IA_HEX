# Entorno local de prueba para HEX

Este entorno **no garantiza ser idéntico** al de los profesores, pero está hecho para respetar lo que aparece en la orientación:

- `player.py` con la clase base `Player`
- `board.py` con la clase `HexBoard`
- modelación del tablero como matriz `NxN`
- ids `1` y `2`
- adyacencias con **even-r layout**
- `play(board)` recibe un tablero y devuelve `(fila, columna)`

## Archivos

- `player.py`
- `board.py`
- `random_player.py`
- `run_match.py`
- `solution.py` (tu jugador)

## Uso

Copia tu `solution.py` dentro de esta carpeta y ejecuta:

```bash
python run_match.py --size 5 --games 3 --show
```

## Qué comprueba

- que `solution.py` importe bien `Player` y `HexBoard`
- que `play()` devuelva una tupla `(fila, columna)`
- que la jugada sea legal
- que no se pase del tiempo por jugada
- que se pueda jugar una partida completa contra un rival aleatorio

## Nota importante

La orientación solo describe la interfaz mínima y algunas reglas del torneo. Por eso este entorno es una **aproximación razonable para pruebas locales**, no una copia oficial del entorno docente.

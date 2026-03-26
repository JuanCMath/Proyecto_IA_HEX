# HEX AI — SmartPlayer

Jugador inteligente para el juego HEX

---

## Estrategia general

El algoritmo combina **chequeos tácticos inmediatos** con una búsqueda **Monte Carlo Tree Search (MCTS)** potenciada con **RAVE** (Rapid Action Value Estimation). La decisión de cada turno sigue este orden de prioridad:

1. **Apertura:** si el tablero está vacío, juega directamente en el centro `(n//2, n//2)`.
2. **Ganar en uno:** si algún movimiento candidato completa la conexión propia, se juega de inmediato.
3. **Bloquear en uno:** si el rival puede ganar en su próximo turno, se bloquea.
4. **MCTS + RAVE:** si ninguna táctica inmediata aplica, se lanza la búsqueda.

---

## MCTS con RAVE

### Árbol de búsqueda (`_Node`)

Cada nodo del árbol guarda:
- El estado del tablero en ese punto.
- Estadísticas clásicas de MCTS: `visits` y `wins`.
- Estadísticas RAVE por movimiento: `rave_v` (visitas) y `rave_w` (victorias), que permiten reutilizar información de simulaciones en las que ese movimiento apareció en *cualquier* posición, no solo como jugada inmediata.
- Lista `untried` de movimientos aún no explorados.

### Selección

Se usa la fórmula UCB1 mezclada con el valor RAVE:

```
score = (1 - β) · Q(nodo) + β · Q_RAVE(movimiento) + C · √(ln N / n)
```

donde `β` decrece a medida que el nodo acumula visitas, dando cada vez más peso a la estadística real frente a la RAVE.

### Expansión

Se elige al azar un movimiento no explorado de `untried` y se crea un nodo hijo con el estado resultante.

### Simulación (`_simulate`)

Se juega una partida aleatoria desde el nodo expandido usando **movimientos candidatos** (vecinos de casillas ocupadas) hasta que algún jugador completa su conexión. Se devuelve el ganador y la lista de movimientos jugados durante la simulación.

### Retropropagación

Se actualizan `visits` y `wins` en todos los nodos del camino hacia la raíz. Además, cada movimiento que apareció durante la simulación actualiza las estadísticas RAVE del nodo padre correspondiente.

### Presupuesto adaptativo

El número máximo de iteraciones se ajusta al tamaño del tablero:

| Tamaño | Iteraciones |
|--------|-------------|
| ≤ 7×7  | 8 000       |
| ≤ 11×11| 4 000       |
| ≤ 16×16| 2 000       |
| mayor  | 800         |

La búsqueda se detiene también si se supera el límite de tiempo de **4.5 segundos**.

---

## Movimientos candidatos (`_candidates`)

En lugar de considerar todas las casillas vacías, el algoritmo restringe la búsqueda a los **vecinos inmediatos de casillas ya ocupadas**. Esto reduce drásticamente el factor de ramificación sin descartar movimientos relevantes. Solo si el tablero está completamente vacío se usan todos los movimientos legales.

---

## Distancia de conexión (`_dijkstra`)

Aunque no se usa directamente en la selección MCTS de esta versión, la función `_dijkstra` implementa una estimación de cuántos movimientos faltan para que un jugador complete su conexión:

- **Jugador 1** conecta de izquierda a derecha (columna 0 → columna n-1).
- **Jugador 2** conecta de arriba a abajo (fila 0 → fila n-1).

El coste de cada celda es `0` si ya pertenece al jugador evaluado, `1` si está vacía, e infinito si pertenece al rival.

---

## Caché de vecinos

Los 6 vecinos hexagonales de cada celda se precalculan una sola vez por tamaño de tablero y se almacenan en `_ncache`, evitando recalcularlos en cada iteración de la búsqueda.

---

## Resumen de componentes

| Componente | Descripción |
|---|---|
| `play()` | Punto de entrada: apertura, táctica inmediata y MCTS |
| `_mcts()` | Bucle principal MCTS con RAVE |
| `_simulate()` | Simulación aleatoria hasta terminal |
| `_candidates()` | Movimientos relevantes (vecinos de ocupadas) |
| `_dijkstra()` | Distancia mínima de conexión por Dijkstra |
| `_neighbors()` | Vecinos hex con caché por tamaño |
| `_Node` | Nodo del árbol con estadísticas MCTS y RAVE |
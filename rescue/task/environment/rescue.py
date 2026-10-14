"""Delivery routes backed by python-pathfinding; caches repeated requests."""
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
from pathfinding.core.diagonal_movement import DiagonalMovement

_cache = {}

def plan_route(matrix, start, goal, blocked=()):
    """Return (x,y) cells, endpoints included, or [] if delivery is impossible.

    Positive cells are traversal costs; 0 is a wall. Movement is cardinal.
    Temporary closures in blocked apply only to this request. Inputs must not
    be mutated. Calls in the same process may use different maps or closures.
    """
    key = (tuple(start), tuple(goal))
    if key in _cache:
        return list(_cache[key])
    weights = [list(row) for row in matrix]
    for x, y in blocked:
        weights[y][x] = 0
    sx, sy = start
    gx, gy = goal
    if weights[sy][sx] <= 0 or weights[gy][gx] <= 0:
        return []
    grid = Grid(matrix=weights)
    path, _ = AStarFinder(diagonal_movement=DiagonalMovement.never).find_path(
        grid.node(sx, sy), grid.node(gx, gy), grid)
    route = [(n.x, n.y) for n in path]
    _cache[key] = route
    return list(route)

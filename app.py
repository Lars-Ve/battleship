import random
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Global game state
# ---------------------------------------------------------------------------

game = None  # None means no active game


# ---------------------------------------------------------------------------
# Game logic helpers
# ---------------------------------------------------------------------------

# Ship definitions: (size, id)
# Two cruisers get id 3 and -3; the rest are unique.
SHIPS = [
    (5,  5),
    (4,  4),
    (3,  3),
    (3, -3),
    (2,  2),
]


def empty_grid(rows, cols, fill=-1):
    return [[fill] * cols for _ in range(rows)]


def place_ship(full_grid, rows, cols, size):
    """Try to place a ship randomly. Returns the list of (r, c) cells, or None on failure."""
    for _ in range(1000):  # retry limit
        horizontal = random.choice([True, False])
        if horizontal:
            r = random.randrange(rows)
            c = random.randrange(cols - size + 1)
            cells = [(r, c + i) for i in range(size)]
        else:
            r = random.randrange(rows - size + 1)
            c = random.randrange(cols)
            cells = [(r + i, c) for i in range(size)]

        if all(full_grid[r][c] == 0 for r, c in cells):
            return cells

    return None  # shouldn't happen on a sufficiently large board


def build_full_grid(rows, cols):
    """Place all ships on the full grid. Returns (grid, ships_info)."""
    grid = empty_grid(rows, cols, fill=0)
    ships_info = []  # list of {"cells": [...], "id": int, "hits": set()}

    for size, ship_id in SHIPS:
        cells = place_ship(grid, rows, cols, size)
        for r, c in cells:
            grid[r][c] = ship_id
        ships_info.append({"cells": cells, "id": ship_id, "hits": set()})

    return grid, ships_info


def new_game(rows, cols):
    full_grid, ships_info = build_full_grid(rows, cols)
    return {
        "rows": rows,
        "cols": cols,
        "full_grid": full_grid,
        "visible_grid": empty_grid(rows, cols, fill=-1),
        "ships": ships_info,
    }


def in_bounds(game_state, row, col):
    return 0 <= row < game_state["rows"] and 0 <= col < game_state["cols"]


def already_shot(game_state, row, col):
    return game_state["visible_grid"][row][col] != -1


def find_ship(game_state, row, col):
    """Return the ship dict that occupies (row, col), or None."""
    for ship in game_state["ships"]:
        if (row, col) in [tuple(cell) for cell in ship["cells"]]:
            return ship
    return None


def shoot(game_state, row, col):
    """
    Process a shot. Updates visible_grid and ship hit tracking.
    Returns result: 0 (miss), 1 (hit), or the ship id (sunk).
    """
    cell_value = game_state["full_grid"][row][col]

    if cell_value == 0:
        # Miss
        game_state["visible_grid"][row][col] = 0
        return 0

    # Hit — find which ship
    ship = find_ship(game_state, row, col)
    ship["hits"].add((row, col))
    game_state["visible_grid"][row][col] = 1

    if len(ship["hits"]) == len(ship["cells"]):
        # Ship sunk — mark all its cells with the ship id
        for r, c in ship["cells"]:
            game_state["visible_grid"][r][c] = ship["id"]
        return ship["id"]

    return 1


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/game/new", methods=["POST"])
def route_new_game():
    global game

    data = request.get_json(silent=True) or {}
    rows = data.get("rows")
    cols = data.get("cols")

    if not isinstance(rows, int) or not isinstance(cols, int):
        return jsonify({"error": "rows and cols must be integers."}), 400

    if rows <= 7 or cols <= 7:
        return jsonify({"error": "Board dimensions must both be greater than 7."}), 400

    game = new_game(rows, cols)
    return jsonify({"message": "New game started.", "rows": rows, "cols": cols})


@app.route("/game/shoot", methods=["POST"])
def route_shoot():
    global game

    if game is None:
        return jsonify({"error": "No active game. Start a new game first via POST /game/new."}), 400

    data = request.get_json(silent=True) or {}
    row = data.get("row")
    col = data.get("col")

    if not isinstance(row, int) or not isinstance(col, int):
        return jsonify({"error": "row and col must be integers."}), 400

    if not in_bounds(game, row, col):
        return jsonify({"error": "Invalid coordinates. Row and column must be within the board."}), 400

    if already_shot(game, row, col):
        return jsonify({"error": f"Cell ({row}, {col}) has already been shot."}), 400

    result = shoot(game, row, col)
    won = not any(cell in (-1, 1) for row_ in game["visible_grid"] for cell in row_)
    return jsonify({"result": result, "board": game["visible_grid"], "won": won})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
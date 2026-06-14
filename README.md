# battleship
A stateful HTTP API for playing a single game of Battleship. The server keeps all game state in memory. It is single-player (against a random field). It is designed to be hosted locally as a backend you can build on top of: hook up a frontend, let an AI agent play against it, run automated experiments, or anything else you can think of.

## Table of Contents
 
- [Game Rules](#game-rules)
- [Board Representation](#board-representation)
- [Endpoints](#endpoints)
  - [POST /game/new](#post-gamenew)
  - [POST /game/shoot](#post-gameshoot)
- [Error Handling](#error-handling)
- [Examples](#examples)
---
 
## Game Rules
 
Standard Battleship rules apply. The fleet consists of **5 ships** placed randomly on an **M×N grid** that you define when starting a new game:
 
| Ship | Size | Count |
|------|------|-------|
| Carrier | 5 | ×1 |
| Battleship | 4 | ×1 |
| Cruiser | 3 | ×2 |
| Destroyer | 2 | ×1 |
 
Ships are placed randomly when a new game is started. The player fires shots one at a time and receives feedback after each shot.
 
---
 
## Board Representation
 
The server maintains two internal grids:
 
- **Full grid**: the server's truth; tracks all ship positions and hits.
- **Visible grid**: what the player sees; revealed incrementally through shots.
### Visible grid cell values
 
| Value | Meaning |
|-------|---------|
| `-1` | Not yet shot |
| `0` | Miss |
| `1` | Hit (ship not yet sunk) |
| `2` | Part of the **sunk Destroyer** (size 2) |
| `3` | Part of the **sunk Cruiser #1** (size 3) |
| `-3` | Part of the **sunk Cruiser #2** (size 3) |
| `4` | Part of the **sunk Battleship** (size 4) |
| `5` | Part of the **sunk Carrier** (size 5) |
 
Cells belonging to a sunk ship are retroactively updated to their ship identifier once the ship goes down.
 
### Coordinates
 
Rows and columns are **0-indexed**. The top-left corner is `(0, 0)`, the bottom-right corner is `(M-1, N-1)`.
 
---
 
## Endpoints
 
### POST `/game/new`
 
Starts a new game. Any existing game state is cleared and a fresh board is generated with ships placed randomly.
 
#### Request body
 
```json
{
  "rows": 10,
  "cols": 10
}
```
 
| Field | Type | Description |
|-------|------|-------------|
| `rows` | integer | Number of rows (M). Must be **greater than 7**. |
| `cols` | integer | Number of columns (N). Must be **greater than 7**. |
 
#### Response `200 OK`
 
```json
{
  "message": "New game started.",
  "rows": 10,
  "cols": 10
}
```
 
---
 
### POST `/game/shoot`
 
Fires a shot at the given coordinates.
 
#### Request body
 
```json
{
  "row": 3,
  "col": 7
}
```
 
| Field | Type | Description |
|-------|------|-------------|
| `row` | integer | Row index (0 to M-1) |
| `col` | integer | Column index (0 to N-1) |
 
#### Response `200 OK`
 
```json
{
  "result": 1,
  "board": [
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1,  1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1]
  ]
}
```
 
### `result` values
 
| Value | Meaning |
|-------|---------|
| `0` | Miss |
| `1` | Hit (ship not yet sunk) |
| `2`, `3`, `-3`, `4`, `5` | Hit **and** sunk a ship: the value is the ship's identifier (see [Visible grid cell values](#visible-grid-cell-values)) |
 
When a ship is sunk, `result` carries the ship's identifier instead of a generic value, and all cells of that ship in `board` are updated to that same identifier.

won: boolean, included in every shoot response. true if all ships have been sunk and the game is over, false otherwise.

---
 
## Error Handling
 
All errors return a `400 Bad Request` with a JSON body describing the problem.
 
### Board dimensions too small
 
```json
{
  "error": "Board dimensions must both be greater than 7."
}
```
 
### Shooting outside the grid
 
```json
{
  "error": "Invalid coordinates. Row and column must be within the board."
}
```
 
### Shooting a cell that has already been shot
 
```json
{
  "error": "Cell (3, 7) has already been shot."
}
```
 
### Shooting when no game is active
 
```json
{
  "error": "No active game. Start a new game first via POST /game/new."
}
```
 
---
 
## Examples
 
### Start a new game
 
```http
POST /game/new
Content-Type: application/json
 
{ "rows": 10, "cols": 12 }
```
 
```json
{
  "message": "New game started.",
  "rows": 10,
  "cols": 12
}
```
 
### Fire a shot → miss
 
```http
POST /game/shoot
Content-Type: application/json
 
{ "row": 0, "col": 0 }
```
 
```json
{
  "result": 0,
  "board": [
    [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    ...
  ]
}
```
 
### Fire a shot → hit (ship still afloat)
 
```http
POST /game/shoot
Content-Type: application/json
 
{ "row": 4, "col": 5 }
```
 
```json
{
  "result": 1,
  "board": [
    [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1,  1, -1, -1, -1, -1, -1, -1],
    ...
  ]
}
```
 
### Fire a shot → ship sunk
 
```http
POST /game/shoot
Content-Type: application/json
 
{ "row": 4, "col": 6 }
```
 
```json
{
  "result": 2,
  "board": [
    [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1,  2,  2, -1, -1, -1, -1, -1],
    ...
  ]
}
```
 
`result: 2` means the Destroyer (size 2) was sunk. Both its cells are now marked `2` on the board.
 

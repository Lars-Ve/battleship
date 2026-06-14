import requests

BASE_URL = "http://localhost:5000"


def start_game():
    while True:
        try:
            rows = int(input("Number of rows (> 7): "))
            cols = int(input("Number of cols (> 7): "))
        except ValueError:
            print("Please enter valid integers.\n")
            continue

        resp = requests.post(f"{BASE_URL}/game/new", json={"rows": rows, "cols": cols})
        if resp.status_code == 200:
            print(f"\nGame started on a {rows}x{cols} board!\n")
            return rows, cols
        else:
            print(f"Error: {resp.json().get('error')}\n")


def print_board(board):
    cols = len(board[0])

    # Column header
    print("    " + "  ".join(f"{c:2}" for c in range(cols)))
    print("    " + "----" * cols)

    for r, row in enumerate(board):
        print(f"{r:2} | " + "  ".join(f"{cell:2}" for cell in row))
    print()


def take_shot():
    while True:
        try:
            row = int(input("Row: "))
            col = int(input("Col: "))
        except ValueError:
            print("Please enter valid integers.\n")
            continue

        resp = requests.post(f"{BASE_URL}/game/shoot", json={"row": row, "col": col})
        data = resp.json()

        if resp.status_code != 200:
            print(f"Error: {data.get('error')}\n")
            continue

        result = data["result"]
        if result == 0:
            print("Miss!\n")
        elif result == 1:
            print("Hit!\n")
        else:
            print(f"Hit and sunk! (ship id: {result})\n")

        return data["board"], data["won"]


def main():
    rows, cols = start_game()
    board = [[-1] * cols for _ in range(rows)]

    while True:
        print_board(board)
        board, won = take_shot()

        if won:
            print_board(board)
            print("All ships sunk — you win!")
            break


if __name__ == "__main__":
    main()
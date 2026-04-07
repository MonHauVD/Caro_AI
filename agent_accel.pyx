# cython: language_level=3

def compute_sequences(
    sequences,
    str current_xo,
    long long TWO,
    long long TWO_OBSTACLE,
    long long THREE,
    long long THREE_OBSTACLE,
    long long FOUR,
    long long FOUR_OBSTACLE,
    long long WINNING,
    long long TWO_OPPONENT,
    long long TWO_OBSTACLE_OPPONENT,
    long long THREE_OPPONENT,
    long long THREE_OBSTACLE_OPPONENT,
    long long FOUR_OPPONENT,
    long long FOUR_OBSTACLE_OPPONENT,
    long long LOSING,
):
    cdef long long result = 0
    cdef long long player, opponent, obstacle, obstacle_player, obstacle_opponent
    cdef str c
    cdef list sequence

    for sequence in sequences:
        player = 0
        opponent = 0
        obstacle = 1
        obstacle_player = 0
        obstacle_opponent = 0

        for c in sequence:
            if c == current_xo:
                player += 1

                if opponent != 0:
                    if opponent == 2 and obstacle_player == 0 and obstacle == 0:
                        result += TWO_OBSTACLE_OPPONENT
                    elif opponent == 3 and obstacle_player == 0 and obstacle == 0:
                        result += THREE_OBSTACLE_OPPONENT
                    elif opponent == 4 and obstacle_player == 0 and obstacle == 0:
                        result += FOUR_OBSTACLE_OPPONENT
                    elif opponent == 5:
                        result += LOSING

                opponent = 0
                obstacle_player = 1

            elif c != '.':
                opponent += 1

                if player != 0:
                    if player == 2 and obstacle_opponent == 0 and obstacle == 0:
                        result += TWO_OBSTACLE
                    elif player == 3 and obstacle_opponent == 0 and obstacle == 0:
                        result += THREE_OBSTACLE
                    elif player == 4 and obstacle_opponent == 0 and obstacle == 0:
                        result += FOUR_OBSTACLE
                    elif player == 5:
                        result += WINNING

                player = 0
                obstacle_opponent = 1

            else:
                if player != 0:
                    if player == 2:
                        if obstacle_opponent == 1 or obstacle == 1:
                            result += TWO_OBSTACLE
                        else:
                            result += TWO
                    elif player == 3:
                        if obstacle_opponent == 1 or obstacle == 1:
                            result += THREE_OBSTACLE
                        else:
                            result += THREE
                    elif player == 4:
                        if obstacle_opponent == 1 or obstacle == 1:
                            result += FOUR_OBSTACLE
                        else:
                            result += FOUR
                    elif player == 5:
                        result += WINNING
                player = 0

                if opponent != 0:
                    if opponent == 2:
                        if obstacle_player == 1 or obstacle == 1:
                            result += TWO_OBSTACLE_OPPONENT
                        else:
                            result += TWO_OPPONENT
                    elif opponent == 3:
                        if obstacle_player == 1 or obstacle == 1:
                            result += THREE_OBSTACLE_OPPONENT
                        else:
                            result += THREE_OPPONENT
                    elif opponent == 4:
                        if obstacle_player == 1 or obstacle == 1:
                            result += FOUR_OBSTACLE_OPPONENT
                        else:
                            result += FOUR_OPPONENT
                    elif opponent == 5:
                        result += LOSING

                    opponent = 0

                obstacle = 0
                obstacle_player = 0
                obstacle_opponent = 0

        if opponent != 0:
            if opponent == 2 and obstacle_player == 0 and obstacle == 0:
                result += TWO_OBSTACLE_OPPONENT
            elif opponent == 3 and obstacle_player == 0 and obstacle == 0:
                result += THREE_OBSTACLE_OPPONENT
            elif opponent == 4 and obstacle_player == 0 and obstacle == 0:
                result += FOUR_OBSTACLE_OPPONENT
            elif opponent == 5:
                result += LOSING

        if player != 0:
            if player == 2 and obstacle_opponent == 0 and obstacle == 0:
                result += TWO_OBSTACLE
            elif player == 3 and obstacle_opponent == 0 and obstacle == 0:
                result += THREE_OBSTACLE
            elif player == 4 and obstacle_opponent == 0 and obstacle == 0:
                result += FOUR_OBSTACLE
            elif player == 5:
                result += WINNING

    return result

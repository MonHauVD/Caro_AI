# cython: language_level=3, boundscheck=False, wraparound=False, initializedcheck=False, cdivision=True

cdef inline int _idx(int x, int y, int cols):
    return x * cols + y


cdef int _check_winner(int[:] board, int rows, int cols):
    cdef int x, y, k, nx, ny, player
    cdef int dx[4]
    cdef int dy[4]
    dx[0], dy[0] = 1, 0
    dx[1], dy[1] = 0, 1
    dx[2], dy[2] = 1, 1
    dx[3], dy[3] = 1, -1

    for x in range(rows):
        for y in range(cols):
            player = board[_idx(x, y, cols)]
            if player == 0:
                continue
            for k in range(4):
                nx = x + 4 * dx[k]
                ny = y + 4 * dy[k]
                if nx < 0 or ny < 0 or nx >= rows or ny >= cols:
                    continue
                if (board[_idx(x + 1 * dx[k], y + 1 * dy[k], cols)] == player and
                    board[_idx(x + 2 * dx[k], y + 2 * dy[k], cols)] == player and
                    board[_idx(x + 3 * dx[k], y + 3 * dy[k], cols)] == player and
                    board[_idx(x + 4 * dx[k], y + 4 * dy[k], cols)] == player):
                    return player
    return 0


cdef long long _evaluate_board(int[:] board, int rows, int cols, int me, int opp):
    cdef int x, y, k, nx, ny, i
    cdef int dx[4]
    cdef int dy[4]
    cdef int my_cnt, op_cnt, cell
    cdef long long score = 0
    dx[0], dy[0] = 1, 0
    dx[1], dy[1] = 0, 1
    dx[2], dy[2] = 1, 1
    dx[3], dy[3] = 1, -1

    for x in range(rows):
        for y in range(cols):
            for k in range(4):
                nx = x + 4 * dx[k]
                ny = y + 4 * dy[k]
                if nx < 0 or ny < 0 or nx >= rows or ny >= cols:
                    continue
                my_cnt = 0
                op_cnt = 0
                for i in range(5):
                    cell = board[_idx(x + i * dx[k], y + i * dy[k], cols)]
                    if cell == me:
                        my_cnt += 1
                    elif cell == opp:
                        op_cnt += 1
                if my_cnt > 0 and op_cnt > 0:
                    continue
                if my_cnt == 5:
                    score += 1000000000
                elif op_cnt == 5:
                    score -= 1000000000
                elif my_cnt == 4:
                    score += 10000000
                elif op_cnt == 4:
                    score -= 12000000
                elif my_cnt == 3:
                    score += 150000
                elif op_cnt == 3:
                    score -= 180000
                elif my_cnt == 2:
                    score += 2000
                elif op_cnt == 2:
                    score -= 2500
    return score


cdef list _generate_moves(int[:] board, int rows, int cols):
    cdef int x, y, k, nx, ny
    cdef int dx8[8]
    cdef int dy8[8]
    cdef int has_stone = 0
    cdef int pos
    cdef list moves = []
    cdef list mark = [0] * (rows * cols)
    dx8[0], dy8[0] = 1, 1
    dx8[1], dy8[1] = 1, -1
    dx8[2], dy8[2] = 1, 0
    dx8[3], dy8[3] = -1, 1
    dx8[4], dy8[4] = -1, -1
    dx8[5], dy8[5] = -1, 0
    dx8[6], dy8[6] = 0, 1
    dx8[7], dy8[7] = 0, -1

    for x in range(rows):
        for y in range(cols):
            if board[_idx(x, y, cols)] != 0:
                has_stone = 1
                for k in range(8):
                    nx = x + dx8[k]
                    ny = y + dy8[k]
                    if 0 <= nx < rows and 0 <= ny < cols and board[_idx(nx, ny, cols)] == 0:
                        pos = _idx(nx, ny, cols)
                        if mark[pos] == 0:
                            mark[pos] = 1
                            moves.append(pos)

    if not has_stone:
        moves.append(_idx(rows // 2, cols // 2, cols))
    return moves


cdef int _adj_score(int[:] board, int rows, int cols, int pos, int player):
    cdef int x = pos // cols
    cdef int y = pos % cols
    cdef int dx8[8]
    cdef int dy8[8]
    cdef int k, nx, ny, sc = 0
    dx8[0], dy8[0] = 1, 1
    dx8[1], dy8[1] = 1, -1
    dx8[2], dy8[2] = 1, 0
    dx8[3], dy8[3] = -1, 1
    dx8[4], dy8[4] = -1, -1
    dx8[5], dy8[5] = -1, 0
    dx8[6], dy8[6] = 0, 1
    dx8[7], dy8[7] = 0, -1
    for k in range(8):
        nx = x + dx8[k]
        ny = y + dy8[k]
        if 0 <= nx < rows and 0 <= ny < cols:
            if board[_idx(nx, ny, cols)] == player:
                sc += 3
            elif board[_idx(nx, ny, cols)] != 0:
                sc += 1
    return sc


cdef long long _negamax(int[:] board, int rows, int cols, int me, int player, int depth, long long alpha, long long beta, int beam):
    cdef int winner = _check_winner(board, rows, cols)
    cdef int opp = 1 if player == 2 else 2
    cdef int my_opp = 1 if me == 2 else 2
    cdef long long val, score
    cdef list moves
    cdef list scored
    cdef int pos, i, lim

    if winner != 0:
        if winner == me:
            return 2000000000 + depth
        return -2000000000 - depth
    if depth == 0:
        return _evaluate_board(board, rows, cols, me, my_opp)

    moves = _generate_moves(board, rows, cols)
    if not moves:
        return _evaluate_board(board, rows, cols, me, my_opp)

    scored = []
    for pos in moves:
        scored.append((_adj_score(board, rows, cols, pos, player), pos))
    scored.sort(reverse=True)

    lim = beam if beam > 0 else len(scored)
    if lim > len(scored):
        lim = len(scored)

    val = -9223372036854775807
    for i in range(lim):
        pos = scored[i][1]
        board[pos] = player
        score = -_negamax(board, rows, cols, me, opp, depth - 1, -beta, -alpha, beam)
        board[pos] = 0
        if score > val:
            val = score
        if val > alpha:
            alpha = val
        if alpha >= beta:
            break
    return val


def search_best_move(object board_data, int rows, int cols, int current_player, int depth, int beam_width):
    cdef int[:] board = board_data
    cdef int opp = 1 if current_player == 2 else 2
    cdef list moves = _generate_moves(board, rows, cols)
    cdef list scored = []
    cdef int pos, i, lim, best_pos = -1
    cdef long long best_score = -9223372036854775807
    cdef long long score

    for pos in moves:
        scored.append((_adj_score(board, rows, cols, pos, current_player), pos))
    scored.sort(reverse=True)

    lim = beam_width if beam_width > 0 else len(scored)
    if lim > len(scored):
        lim = len(scored)

    for i in range(lim):
        pos = scored[i][1]
        board[pos] = current_player
        score = -_negamax(board, rows, cols, current_player, opp, depth - 1, -9223372036854775807, 9223372036854775807, beam_width)
        board[pos] = 0
        if score > best_score:
            best_score = score
            best_pos = pos

    if best_pos < 0:
        return None
    return (best_pos // cols, best_pos % cols, best_score)

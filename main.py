"""Điểm vào: chạy `python main.py` từ thư mục gốc project."""

import multiprocessing


if __name__ == '__main__':
    multiprocessing.freeze_support()
    from caro_ai.app import main

    main()

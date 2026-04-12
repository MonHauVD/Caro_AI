import multiprocessing

from caro_ai.app import main

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()

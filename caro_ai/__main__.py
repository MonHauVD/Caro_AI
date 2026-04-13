import multiprocessing
import sys

if __name__ == "__main__":
    if "--bench-export-merge" in sys.argv[1:]:
        from caro_ai.benchmark.merge_cli import main as bench_merge_main

        merge_argv = [a for a in sys.argv[1:] if a != "--bench-export-merge"]
        raise SystemExit(bench_merge_main(merge_argv))
    multiprocessing.freeze_support()
    from caro_ai.app import main

    main()

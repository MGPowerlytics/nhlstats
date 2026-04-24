#!/home/matthew/anaconda3/bin/python
import sys
sys.path.insert(0, '/mnt/data2/nhlstats/plugins')
sys.path.insert(0, '/mnt/data2/nhlstats')
sys.path.insert(0, '/mnt/data2/nhlstats/scripts')

try:
    from backtest_from_results import main
    print("Imported main successfully")

    # Run main
    sys.exit(main())
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

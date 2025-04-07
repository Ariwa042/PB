import time
from functools import wraps
from collections import defaultdict

# Keep track of function statistics
stats = defaultdict(lambda: {"calls": 0, "errors": 0, "total_time": 0})

def time_function(func):
    """
    Decorator to measure the execution time of a function and track errors.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            stats[func.__name__]["calls"] += 1
            stats[func.__name__]["total_time"] += elapsed_time
            print(f"✅ Function '{func.__name__}' succeeded in {elapsed_time:.4f} seconds")
            return result
        except Exception as e:
            elapsed_time = time.time() - start_time
            stats[func.__name__]["calls"] += 1
            stats[func.__name__]["errors"] += 1
            stats[func.__name__]["total_time"] += elapsed_time
            print(f"❌ Function '{func.__name__}' failed after {elapsed_time:.4f} seconds")
            print(f"🔍 Error: {str(e)}")
            raise  # Re-raise the exception
    return wrapper

def print_stats():
    """Print collected timing and error statistics."""
    print("\n📊 Function Statistics:")
    for func_name, data in stats.items():
        calls = data["calls"]
        errors = data["errors"]
        total_time = data["total_time"]
        avg_time = total_time / calls if calls > 0 else 0
        success_rate = ((calls - errors) / calls * 100) if calls > 0 else 0
        
        print(f"\n{func_name}:")
        print(f"  Calls: {calls}")
        print(f"  Errors: {errors}")
        print(f"  Success Rate: {success_rate:.1f}%")
        print(f"  Average Time: {avg_time:.4f}s")
        print(f"  Total Time: {total_time:.4fs}")

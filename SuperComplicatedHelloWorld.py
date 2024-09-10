import functools
import time
import threading

# Step 1: Create a class that does nothing but holds the string
class HelloWorld:
    def __init__(self):
        self.message = "Hello World"

# Step 2: Create a decorator that wraps the print function
def complicated_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Simulate complex processing
        time.sleep(1)  # Artificial delay
        print("Processing...")  # Fake processing step
        result = func(*args, **kwargs)
        print("Done processing!")
        return result
    return wrapper

# Step 3: Use a thread to print the message
def threaded_hello(obj):
    time.sleep(2)  # Delay to pretend it's hard to print
    print(obj.message)

@complicated_decorator
def print_hello():
    # Create the HelloWorld object
    hello_obj = HelloWorld()
    
    # Step 4: Use threading for extra complexity
    t = threading.Thread(target=threaded_hello, args=(hello_obj,))
    t.start()
    t.join()  # Wait for thread to finish

# Step 5: Add more useless layers
def main():
    print("Starting program...")
    time.sleep(1)  # Another delay for no reason
    print_hello()

if __name__ == "__main__":
    main()

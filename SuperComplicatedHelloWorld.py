import functools
import time
import threading


class HelloWorld:
    def __init__(self):
        self.message = "Hello World"


def complicated_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        time.sleep(1)
        print("Processing...")  
        result = func(*args, **kwargs)
        print("Done processing!")
        return result
    return wrapper


def threaded_hello(obj):
    time.sleep(2) 
    print(obj.message)

@complicated_decorator
def print_hello():
    hello_obj = HelloWorld()
    
    t = threading.Thread(target=threaded_hello, args=(hello_obj,))
    t.start()
    t.join()  


def main():
    print("Starting program...")
    time.sleep(1)  
    print_hello()

if __name__ == "__main__":
    main()

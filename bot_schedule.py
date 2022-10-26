import time
from functools import wraps

import schedule


def mult_threading(func):
    @wraps(func)
    def wrapper(*args_, **kwargs_):
        import threading
        func_thread = threading.Thread(target=func,
                                       args=tuple(args_),
                                       kwargs=kwargs_)
        func_thread.start()
        return func_thread

    return wrapper


@mult_threading
def do_schedule(func):
    schedule.every().hour.do(func)
    #schedule.every().minute.do(func)
    while 1:
        schedule.run_pending()
        time.sleep(1)




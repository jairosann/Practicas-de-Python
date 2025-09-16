import threading
import queue
import random
import time

class Worker(threading.Thread):
    def __init__(self, task_queue, result_queue, worker_id):
        super().__init__()
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.worker_id = worker_id

    def run(self):
        while True:
            try:
                task = self.task_queue.get(timeout=1)
            except queue.Empty:
                break
            result = self.process_task(task)
            self.result_queue.put((self.worker_id, task, result))
            self.task_queue.task_done()

    def process_task(self, task):
        time.sleep(random.uniform(0.1, 0.5))  # Simula procesamiento
        return task ** 2 + random.randint(1, 100)

def main():
    num_workers = 4
    tasks = [random.randint(1, 20) for _ in range(10)]
    task_queue = queue.Queue()
    result_queue = queue.Queue()

    for task in tasks:
        task_queue.put(task)

    workers = [Worker(task_queue, result_queue, i) for i in range(num_workers)]
    for w in workers:
        w.start()

    task_queue.join()

    results = []
    while not result_queue.empty():
        worker_id, task, result = result_queue.get()
        results.append((worker_id, task, result))

    print("Resultados:")
    for worker_id, task, result in results:
        print(f"Worker {worker_id} procesó {task} -> {result}")

if __name__ == "__main__":
    main()
import multiprocessing
import subprocess

def run_robo_rsi():
    subprocess.run(["python", "robo_rsi.py"])

def run_robo_feargreed():
    subprocess.run(["python", "robo_feargreed.py"])

if __name__ == "__main__":
    p1 = multiprocessing.Process(target=run_robo_rsi)
    p2 = multiprocessing.Process(target=run_robo_feargreed)

    p1.start()
    p2.start()

    p1.join()
    p2.join() 
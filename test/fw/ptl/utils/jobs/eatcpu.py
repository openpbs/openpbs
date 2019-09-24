#!/usr/bin/python3
import signal
import sys

# Usage: eatcpu.py [seconds]
# Eats CPU resources for the time specified by user

x = 0


def receive_alarm(signum, stack):
    sys.exit()

signal.signal(signal.SIGALRM, receive_alarm)

if (len(sys.argv) > 1):
    input_time = sys.argv[1]
    print('Terminating after %s seconds' % input_time)
    signal.alarm(int(input_time))
else:
    print('Running indefinitely')

while True:
    x += 1

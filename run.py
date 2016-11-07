#!/usr/bin/env python

import time
import subprocess

from src.Runner import Runner


if __name__ == '__main__':
    pid = subprocess.Popen(['java', '-Xms512m', '-Xmx1G', '-server', '-jar', "local-runner.jar",
                            'local-runner-sync.properties', '&']).pid
    time.sleep(3)
    Runner().run(pid)

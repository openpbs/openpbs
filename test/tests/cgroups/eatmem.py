#!/usr/bin/env python

import os
import subprocess
from subprocess import Popen, PIPE
import time

eat_mem_c = """
#include <stdio.h>
#include <stdlib.h>
#include <string.h>


#define ONE_GB (0x40000000L)
#define ONE_MB (0x100000L)

void
eatmem(total_mb, block_mb)
{
	int i;
	char *buf;
	size_t block;

	for (i=1, buf=NULL, block=(block_mb*ONE_MB); (i*block) < (total_mb*ONE_MB); i++) {
		buf = realloc((void *)buf, (i*block));
		memset(buf+((i-1)*block), 0, block);
	}
	return;
}

int
main(int argc, char *argv[])
{
	int total_mb = 8;
	int block_mb = 1;

	if (argc > 1)
		total_mb = atoi(argv[1]);

	if (argc > 2)
		block_mb = atoi(argv[2]);

	eatmem(total_mb, block_mb);
	printf("Initialized %dMB in blocks of %dMB\\n", total_mb, block_mb);
}
"""

fname = "/tmp/pbs_pp325_eat_mem.c"
fname_exe = "/tmp/pbs_pp325_eat_mem"
fout = open(fname, "w")
fout.write(eat_mem_c)
fout.close()

print os.getppid()

p = Popen(["gcc", "-o", fname_exe, fname], stdout=PIPE, stderr=PIPE)
(output, error) = p.communicate()
print output
print error

p = Popen([fname_exe, "400", "10"], stdout=PIPE, stderr=PIPE)
(output, error) = p.communicate()
print output
print error

os.remove(fname)
os.remove(fname_exe)
time.sleep(1)

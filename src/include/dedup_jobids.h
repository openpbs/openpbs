/*
 * Copyright (C) 2003-2022 Altair Engineering, Inc. All rights reserved.
 * Copyright notice does not imply publication.
 *
 * ALTAIR ENGINEERING INC. Proprietary and Confidential. Contains Trade Secret
 * Information. Not for use or disclosure outside of Licensee's organization.
 * The software and information contained herein may only be used internally and
 * is provided on a non-exclusive, non-transferable basis. License may not
 * sublicense, sell, lend, assign, rent, distribute, publicly display or
 * publicly perform the software or other information provided herein,
 * nor is Licensee permitted to decompile, reverse engineer, or
 * disassemble the software. Usage of the software and other information
 * provided by Altair(or its resellers) is only as explicitly stated in the
 * applicable end user license agreement between Altair and Licensee.
 * In the absence of such agreement, the Altair standard end user
 * license agreement terms shall govern.
 */


#include <ctype.h>
#include "list_link.h"

struct array_job_range_list {
	char *range;
	struct array_job_range_list *next;
};
typedef struct array_job_range_list array_job_range_list;

int is_array_job(char *id);
array_job_range_list * new_job_range(void);
void free_array_job_range_list(array_job_range_list *head);
int dedup_jobids(char **jobids, int *numjids, char *malloc_track);

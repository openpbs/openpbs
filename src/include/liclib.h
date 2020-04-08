/*
 * Copyright (C) 2003-2020 Altair Engineering, Inc. All rights reserved.
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
 *
 */

typedef struct license_info {
	int licenses_min;
	int licenses_max;
	int licenses_global;
	int licenses_local;
	int licenses_used;
	int licenses_high_used;
	int license_linger_time;
	int checkout_time;
	int total_checked_out;
	int total_needed;
} license_info;

extern license_info *init_licensing(char *lic_location);
extern int get_licenses(license_info *lic_info);
extern char *get_lic_error();
extern void init_lic_info(license_info *lic_info);
extern int checkkey(char **cred_list, char *nd_name, time_t expiry);

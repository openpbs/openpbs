/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * PBS Pro is free software. You can redistribute it and/or modify it under the
 * terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any
 * later version.
 *
 * PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.
 * See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * For a copy of the commercial license terms and conditions,
 * go to: (http://www.pbspro.com/UserArea/agreement.html)
 * or contact the Altair Legal Department.
 *
 * Altair’s dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of PBS Pro and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair’s trademarks, including but not limited to "PBS™",
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
 * trademark licensing policies.
 *
 */
#include <stdio.h>
#include <stdlib.h>
#include <direct.h>
#include <windows.h>
#include <lm.h>
#include <lmcons.h>
#include <lmserver.h>
#include <sys/types.h>
#include <sys/stat.h>
#include "win.h"
#include "log.h"
#include "pbs_ifl.h"
#include "list_link.h"
#include <winbase.h>
#include <ntsecapi.h>
#include <Winnetwk.h>
#include <dsgetdc.h>
#include <Userenv.h>
#include <WtsApi32.h>
#include <TlHelp32.h>
#include <shlobj.h>
#include "ticket.h"

#define	NETWORK_DRIVE_PATHLEN 4  /* Example: "Z:\" */
#ifndef SECURITY_WIN32
#define SECURITY_WIN32 1
#endif
#include <Security.h>

/* Global variable */
char    winlog_buffer[WINLOG_BUF_SIZE] = {'\0'};

#define DESKTOP_ALL (	DESKTOP_CREATEMENU      | DESKTOP_CREATEWINDOW  | \
			DESKTOP_ENUMERATE       | DESKTOP_HOOKCONTROL   | \
			DESKTOP_JOURNALPLAYBACK | DESKTOP_JOURNALRECORD | \
			DESKTOP_READOBJECTS     | DESKTOP_SWITCHDESKTOP | \
			DESKTOP_WRITEOBJECTS    | DELETE                | \
			READ_CONTROL            | WRITE_DAC             | \
			WRITE_OWNER )

typedef NTSTATUS(NTAPI *NtCreateToken_t)
(PHANDLE, /* newly created token handle */
	ACCESS_MASK, /* desired access granted to object */
	PLSA_OBJECT_ATTRIBUTES,
	TOKEN_TYPE, /* (TokenPrimary or TokenImpersonation) */
	PLUID, /* Authentication Id */
	PLARGE_INTEGER, /* expiration time */
	PTOKEN_USER,        /* Owner SID */
	PTOKEN_GROUPS, /* Group SIDs */
	PTOKEN_PRIVILEGES, /* List of privileges for this user */
	PTOKEN_OWNER, /* Default owner for created objects */
	PTOKEN_PRIMARY_GROUP, /* Default group for created objects */
	PTOKEN_DEFAULT_DACL, /* Default DACL for created objects */
	PTOKEN_SOURCE /* identifies creator of token*/
	);

static NtCreateToken_t NtCreateToken=NULL;

#define	WAIT_TIME_FOR_ACTIVE_SESSION	100	/* While waiting for an active session in loop, sleep for 100 seconds */

/*
 * Caching-related Items - use for caching return values
 * of certain functions which run expensive windows calls.
 */

#define	NUM_SECONDS_VALID 1800 /* # of seconds that cached value is good for */
#define	CACHE_NELEM		30 /* # elements in cache */
#define CACHE_VALUE_NELEM	10 /* # of cache value elements */
#define CACHE_STR_SIZE    	80 /* length of strings in caches (inc null) */

struct	cache {
	char	func[CACHE_STR_SIZE]; /* name of function needing cache */
	char	key[CACHE_STR_SIZE];  /* unique key to value being cached */
	char	value[CACHE_VALUE_NELEM][CACHE_STR_SIZE]; /* fixed 2-d array */
	time_t	time_taken;	      /* when value was cached */
};

static int 	passwd_cache_init = 0;
pbs_list_head	passwd_cache_ll;

/* the actual array of cached values */
static struct cache cache_array[CACHE_NELEM] = {0};

/* sdbm: sdbm hash function
 * Found this under: http://www.cse.yorku.ca/~oz/hash.html. It says:
 *
 * "This algorithm was created for sdbm (a public-domain reimplementation of
 * ndbm) database library. it was found to do well in scrambling bits,
 * causing better distribution of the keys and fewer splits. it also
 * happens to be a good general hashing function with good distribution.
 * the actual function is hash(i) = hash(i - 1) * 65599 + str[i]; what is
 * included below is the faster version used in gawk. [there is even a faster,
 * duff-device version] the magic constant 65599 was picked out of thin
 * air while experimenting with different constants, and turns out to be a
 * prime. this is one of the algorithms used in berkeley db (see sleepycat)
 * and elsewhere."
 *
 * Notice of Intellectual Property (from author):
 *
 * "The entire sdbm  library package, as authored by me, Ozan S.
 * Yigit,  is  hereby placed in the public domain. As such, the
 * author is not responsible for the  consequences  of  use  of
 * this  software, no matter how awful, even if they arise from
 * defects in it. There is no expressed or implied warranty for
 * the sdbm library.
 *
 * Since the sdbm library package is in the public domain,
 * this   original  release  or  any  additional  public-domain
 * releases of the modified original cannot possibly (by defin-
 * ition) be withheld from you. Also by definition, You (singu-
 * lar) have all the rights to this code (including  the  right
 * to sell without permission, the right to  hoard[3]  and  the
 * right  to  do  other  icky  things as you see fit) but those
 * rights are also granted to everyone else."
 *
 * Arash Partow talked about sdbm hash function as part of
 * the General Hash Functions Algorithm Library
 * (http://www.partow.net/programming/hashfunctions/), adding:
 *
 * "Free use of the General Hash Functions Algorithm Library available
 * on this site is permitted under the guidelines and in accordance
 * with the most current version of the "Common Public License." "
 *
 */

/**
 * @brief
 *	manipulate and return the input string using hash function algorithm.
 *
 * @param[in] str - input string
 *
 * @return	unsigned long
 * @retval	hashed val
 *
 */
static unsigned long
sdbm(unsigned char *str)
{
	unsigned long hash = 0;
	int c;

	while (c = *str++)
		hash = c + (hash << 6) + (hash << 16) - hash;

	return hash;
}

/**
 * @brief
 * 	copy_to_cache_slot: copy 'value_array' (ending pointer is 'end_varray',
 * 	value_array size of 'value_array_strsize') into 'slot' of cache_array,
 * 	giving it a timestamp of 'now'.
 *
 * @param[in] value_array - array whose size to be copied
 * @param[in] value_array_strsize - size of array
 * @param[in] end_varray - ending pointer
 * @param[out] slot - to hold size
 * @param[in] now - timestamp
 *
 * @return	Void
 *
 */

static void
copy_to_cache_slot(char *value_array,
	int value_array_strsize,
	char *end_varray,
	int slot, time_t now)
{
	char	*varray = NULL;
	int	j;

	varray = value_array;
	j = 0;
	while ((varray < end_varray) && (j < CACHE_VALUE_NELEM)) {
		strcpy(cache_array[slot].value[j], varray);
		varray += value_array_strsize;
		j++;
	}
	/* clear the remaining value elements */
	for (j; j < CACHE_VALUE_NELEM; j++) {
		cache_array[slot].value[j][0] = '\0';
	}
	cache_array[slot].time_taken = now;
}

/**
 * @brief
 * 	Given the unique keys 'func' name (i.e. function where caching is needed)
 * 	and a 'key' (unique to the value), put into cache, the 'value_array' of
 * 	size 'value_array_nelem' whose elements are strings of fixed size
 * 	'value_array_strsize' (includes null character).
 * @par	NOTE:
 *     'value_array' must look like:
 *		value_array[value_array_nelem][value_array_strsize]
 *	'func' name and 'key' name are NOT case sensitive.
 *
 * @param[in] func - function where caching is needed
 * @param[in] key - unique to the value
 * @param[in] value_array - array of str
 * @param[in] value_array_nelem - num of elements in array
 * @param[in] value_array_strsize - str size in array
 *
 * @return	Void
 */
void
cache_data(char *func, char *key, char *value_array,
	int value_array_nelem, int value_array_strsize)
{
	int	i, k;
	int	reuse_slot = -1;
	int	free_slot = -1;
	int	oldest_slot = -1;
	time_t	now;
	char	func_key[CACHE_STR_SIZE*2 + 1] = {'\0'};
	char	*varray = NULL;	   	/* pointer to value_array */
	char	*end_varray = NULL;   /* pointer to end of value_array */


	if ((func == NULL) || (key == NULL) || (value_array == NULL) ||
		(value_array_nelem < 0) || (value_array_nelem > CACHE_VALUE_NELEM) ||
		(value_array_strsize < 0) ||
		(func[0] == '\0') || (strlen(func) >= CACHE_STR_SIZE) ||
		(key[0] == '\0') || (strlen(key) >= CACHE_STR_SIZE) ||
		(CACHE_NELEM <= 0)) {
		return;
	}

	end_varray = value_array + (value_array_nelem*value_array_strsize);

	/* Let's check if we can store all value_array elements */
	varray = value_array;
	while (varray < end_varray) {

		if (strlen(varray) >= CACHE_STR_SIZE) {
			return;	/* won't fit */
		}
		varray += value_array_strsize;

	}
	now = time(0);

	sprintf(func_key, "%s%s", func, key);
	k = sdbm(func_key) % CACHE_NELEM;

	i = k;
	do {
		/* replace an existing entry with the same key value */
		if ((stricmp(func, cache_array[i].func) == 0) &&
			(stricmp(key, cache_array[i].key) == 0)) {

			copy_to_cache_slot(value_array, value_array_strsize,
				end_varray, i, now);
			return;
		}

		/* did not find an existing entry to use,	*/
		/* so let's go set our oldest_slot, free_slot	*/

		if ((oldest_slot == -1) ||
			(cache_array[i].time_taken <
			cache_array[oldest_slot].time_taken)) {
			oldest_slot = i;
		}

		/* set free_slot to the first free slot we find */
		if ((free_slot == -1) &&
			((cache_array[i].func[0] == '\0') ||
			(cache_array[i].key[0] == '\0') ||
			((now - cache_array[i].time_taken) > NUM_SECONDS_VALID))) {
			free_slot = i;
		}


	} while ((i = ((i+1) % CACHE_NELEM)) != k);

	if (free_slot != -1) {
		reuse_slot = free_slot;
	} else { /* cache is full, replace oldest entry */
		reuse_slot = oldest_slot;
	}

	strcpy(cache_array[reuse_slot].func, func);
	strcpy(cache_array[reuse_slot].key, key);
	copy_to_cache_slot(value_array, value_array_strsize,
		end_varray, reuse_slot, now);

}
/**
 * @brief
 *	Returns the value array corresponding to 'func' name and 'key' name.
 * 	This returns NULL  if none was found.
 *
 * NOTE: The elements of the returned value can be accessed as:
 *	c_data = find_cache_data(func, name);
 * 	if( c_data != NULL ) {
 *		printf("%s\n", c_data); 		   -> 1st element
 *		printf("%s\n", c_data+CACHE_STR_SIZE);	   -> 2nd element
 *		printf("%s\n", c_data+(2*CACHE_STR_SIZE)); -> 3rd element
 *		...
 *		printf("%s\n", c_data+(CACHE_VALUE_NELEM*CACHE_STR_SIZE));
 *	}
 *	'func' and 'key' are NOT case-sensitive.
 *
 * @param[in] func - function where caching is needed
 * @param[in] key - unique to the value
 *
 * @return	string
 * @retval	value array corresponding to 'func' name and 'key' name		success
 * @retval	NULL								error
 *
 */
char *
find_cache_data(char *func, char *key)
{
	int	i, k;
	time_t	now;
	char	func_key[CACHE_STR_SIZE*2 + 1];

	if ((func == NULL) || (key == NULL) ||
		(func[0] == '\0') || (key[0] == '\0')) {
		return NULL;
	}

	now = time(0);
	sprintf(func_key, "%s%s", func, key);
	k = sdbm(func_key) % CACHE_NELEM;
	i = k;
	do {

		if ((stricmp(cache_array[i].func, func) == 0) &&
			(stricmp(cache_array[i].key, key) == 0) &&
			((now - cache_array[i].time_taken) <= NUM_SECONDS_VALID)) {
			return ((char *)&cache_array[i].value);
		}
	} while ((i = ((i+1) % CACHE_NELEM)) != k);

	return NULL;
}

/**
 * @brief
 *	sid_dup: duplicates a SID value 'src_sid' to a form that can be freed
 *	later by LocalFree() and not FreeSid()
 *
 * @param[in] src_sid - SID
 *
 * @return 	pointer to SID
 * @retval	duplicated sid		success
 * @retval	NULL			error
 *
 */
SID*
sid_dup(SID *src_sid)
{
	DWORD	sid_len_need;
	SID	*dest_sid = NULL;

	if ((src_sid == NULL) || (!IsValidSid(src_sid)))
		return NULL;	/* nothing happens */

	sid_len_need = GetLengthSid(src_sid);

	if ((dest_sid = (SID *)LocalAlloc(LPTR, sid_len_need)) == NULL) {
		return NULL;
	}

	if (CopySid(sid_len_need, dest_sid, src_sid) == 0) {
		LocalFree(dest_sid);
		return NULL;
	}

	return (dest_sid);
}

/**
 * @brief
 * 	create_administrators_sid: creates a well-known SID value for the
 *	Administrators account.
 *
 * @return	pointer to SID
 * @retval	SID for admin acct	success
 * @retval	NULL			error
 *
 * @par Note:
 *	Return value must be LocalFree() later.
 */
SID *
create_administrators_sid(void)
{
	SID_IDENTIFIER_AUTHORITY	sid_auth = SECURITY_NT_AUTHORITY;
	SID				*sid = NULL;
	SID                             *sid_tmp = NULL;

	if (AllocateAndInitializeSid(&sid_auth, 2, SECURITY_BUILTIN_DOMAIN_RID,
		DOMAIN_ALIAS_RID_ADMINS, 0, 0, 0, 0, 0, 0, &sid_tmp) == 0)
		return NULL;

	/* Need to make a duplicate that is freeable by LocalFree() */
	/* (and not FreeSid) for consistency throughout the code */
	/* FreeSid() onlyif one returned by AllocateAndInitializeSid() */
	sid = sid_dup(sid_tmp);
	FreeSid(sid_tmp);

	return (sid);

}

/**
 * @brief
 *	create_everyone_sid: creates a well-known SID value for the
 *	Everyone account.
 *
 * @return      pointer to SID
 * @retval      SID for evryone acct	success
 * @retval      NULL                    error
 *
 * @par Note:
 *      Return value must be LocalFree() later.
 */

SID *
create_everyone_sid(void)
{
	SID_IDENTIFIER_AUTHORITY	sid_auth = SECURITY_WORLD_SID_AUTHORITY;
	SID				*sid;
	SID                             *sid_tmp = NULL;


	if (AllocateAndInitializeSid(&sid_auth, 1, SECURITY_WORLD_RID,
		0, 0, 0, 0, 0, 0, 0, &sid_tmp) == 0)
		return NULL;

	/* Need to make a duplicate that is freeable by LocalFree() */
	/* (and not FreeSid) for consistency throughout the code */
	/* FreeSid() only if returned by AllocateAndInitializeSid() */
	sid = sid_dup(sid_tmp);
	FreeSid(sid_tmp);

	return (sid);

}

/**
 * @brief
 *	create_domain_users_sid: creates a well-known SID value for the
 *	"Domain Users" group.
 *
 * @return      pointer to SID
 * @retval      SID for domain users group      success
 * @retval      NULL                    	error
 *
 * @par Note:
 *      Return value must be LocalFree() later.
 */


SID *
create_domain_users_sid(void)
{

	SID_IDENTIFIER_AUTHORITY        sid_auth = SECURITY_NT_AUTHORITY;
	SID                             *sid = NULL;
	SID                             *sid_tmp = NULL;
	SID                             *usid = NULL;
	BYTE				auth_ct = 0;

	usid = getusersid(getlogin());
	if (usid == NULL)
		return NULL;

	auth_ct = *GetSidSubAuthorityCount(usid);

	AllocateAndInitializeSid(&sid_auth, auth_ct,
		(auth_ct == 1) ? DOMAIN_GROUP_RID_USERS:
		((auth_ct > 1) ? *GetSidSubAuthority(usid, 0) : 0),
		(auth_ct == 2) ? DOMAIN_GROUP_RID_USERS:
		((auth_ct > 2) ? *GetSidSubAuthority(usid, 1) : 0),
		(auth_ct == 3) ? DOMAIN_GROUP_RID_USERS:
		((auth_ct > 3) ? *GetSidSubAuthority(usid, 2) : 0),
		(auth_ct == 4) ? DOMAIN_GROUP_RID_USERS:
		((auth_ct > 4) ? *GetSidSubAuthority(usid, 3) : 0),
		(auth_ct == 5) ? DOMAIN_GROUP_RID_USERS:
		((auth_ct > 5) ? *GetSidSubAuthority(usid, 4) : 0),
		(auth_ct == 6) ? DOMAIN_GROUP_RID_USERS:
		((auth_ct > 6) ? *GetSidSubAuthority(usid, 5) : 0),
		(auth_ct == 7) ? DOMAIN_GROUP_RID_USERS:
		((auth_ct > 7) ? *GetSidSubAuthority(usid, 6) : 0),
		(auth_ct == 8) ? DOMAIN_GROUP_RID_USERS:
		((auth_ct > 8) ? *GetSidSubAuthority(usid, 7) : 0),
		&sid_tmp);

	LocalFree(usid);
	/* Need to make a duplicate that is freeable by LocalFree() */
	/* (and not FreeSid) for consistency throughout the code */
	/* FreeSid() only if returned by AllocateAndInitializeSid() */
	sid = sid_dup(sid_tmp);
	FreeSid(sid_tmp);

	return (sid);
}

/**
 * @brief
 *	get_full_username: given a <username>, returns in 'realname' either
 *	<username> if corresponding local account exists, or <domain>\<username> if
 *	a domain account was found instead.
 *	This also returns the corresponding SID value to be LocalFree()d later
 *	on, or NULL if account does not exist. The type of the account is returned
 *	in *psid_type
 *
 *
 * NOTE: This function has also been extended so that a <username> of the
 * form "\domain\username" can be passed to it. In turn, the returned
 * fullname may be "domain\domain\username" of which can be thrown
 * away.
 * Be sure to not manipulate fullname with strncpy() as the passed
 * buffer size may be fewer than what is declared.
 *
 */
static SID *
get_full_username(char *username,
	char fullname[(2*PBS_MAXHOSTNAME)+UNLEN+3], /* could be dom\dom\user0 */
	SID_NAME_USE *psid_type)
{
	SID		*sid = NULL;
	DWORD		sid_sz = 0;
	TCHAR		domain[PBS_MAXHOSTNAME+1] = "";
	DWORD		domain_sz;
	char		tryname[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'};	/* dom\user0 */
	char		actual_name[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'};	/* dom\user0 */

	if (username == NULL)
		return NULL;

	sid_sz = 0;
	domain_sz = sizeof(domain);

	/* if username does not contain domain info, we'll try domain first */
	if (strstr((const char *)username, "\\") == NULL) {
		sprintf(tryname, "%s\\%s", get_saved_env("USERDOMAIN"),
			username);
		strcpy(actual_name, tryname);
		LookupAccountName(0, tryname, sid, &sid_sz, domain,
			&domain_sz, psid_type);
	}

	if (sid_sz <= 0) {
		strcpy(actual_name, username);
		LookupAccountName(0, username, sid, &sid_sz, domain,
			&domain_sz, psid_type);
	}

	if (sid_sz <= 0)
		return NULL;

	if ((sid = (SID *)LocalAlloc(LPTR, sid_sz)) == NULL) {
		return NULL;
	}

	if (LookupAccountName(0, actual_name, sid, &sid_sz, domain,
		&domain_sz, psid_type) == 0) {
		LocalFree(sid);
		return NULL;
	}

	if (strlen(domain) > 0)
		sprintf(fullname, "%s\\%s", domain, username);
	else
		strcpy(fullname, username);

	return (sid);
}

/**
 * @brief
 * 	GetComputerDomainName: return 1 if local computer is part of a domain.
 *	and returns  the actual domain name in 'domain_name'. Otherwise, this
 *	return 0 and return the local computer name in 'domain_name'.
 * @par	WARNING: This will be acurate if this function is called from an
 *	Administrators or SYSTEM type of account.
 * @par	NOTE: This now caches the domain_name info, so that
 *	the value would be obtained only once, and not keep re-querying the
 *	system for a value that does not change while the system is up.
 *	If a machine changed domain name, then the machine
 *	would have to be rebooted.
 */
int
GetComputerDomainName(char domain_name[PBS_MAXHOSTNAME+1])
{
	static	char		*the_domain_name = NULL;
	static	int		in_the_domain = 0;

	LSA_OBJECT_ATTRIBUTES  obj_attrs;
	LSA_HANDLE h_policy = INVALID_HANDLE_VALUE;
	NTSTATUS ntsResult = ERROR_SUCCESS;
	PPOLICY_DNS_DOMAIN_INFO pPADInfo = NULL;

	PWCHAR name = NULL;
	char local_name[MAX_COMPUTERNAME_LENGTH+1];
	DWORD local_sz;

	int	rval = 0;

	if (the_domain_name != NULL) {	/* used the cached value */
		strncpy(domain_name, the_domain_name, PBS_MAXHOSTNAME);
		return (in_the_domain);
	}

	strcpy(local_name, "");
	local_sz = sizeof(local_name);
	GetComputerName(local_name, &local_sz);
	strncpy(domain_name, local_name, PBS_MAXHOSTNAME);

	ZeroMemory(&obj_attrs, sizeof(obj_attrs));
	if (LsaOpenPolicy(NULL, &obj_attrs, POLICY_VIEW_LOCAL_INFORMATION,
	&h_policy) \
                                                        != ERROR_SUCCESS )
		goto get_computer_domain_name_end;


	ntsResult = LsaQueryInformationPolicy(
		h_policy,    // Open handle to a Policy object.
		PolicyDnsDomainInformation,  // The information to get.
		(PVOID *)&pPADInfo               // Storage for the information.
		);
	if (ntsResult == ERROR_SUCCESS) {
		// There is no guarantee that the LSA_UNICODE_STRING buffer
		// is null terminated, so copy the name to a buffer that is.
		name = (WCHAR *) LocalAlloc(LPTR,
			(pPADInfo->Name.Length + 1) * sizeof(WCHAR));
		if (!name)
			goto get_computer_domain_name_end;

		if( pPADInfo->DnsDomainName.Length == 0 && \
		    pPADInfo->DnsForestName.Length == 0 && \
		    pPADInfo->Sid ==  NULL )
			goto get_computer_domain_name_end;

		wcsncpy(name,
			pPADInfo->Name.Buffer, pPADInfo->Name.Length);

		if (wcslen(name) > PBS_MAXHOSTNAME) {
			goto get_computer_domain_name_end;
		}
		wcstombs(domain_name, name, PBS_MAXHOSTNAME);
		rval = 1;
	}

get_computer_domain_name_end:
	if (name)
		LocalFree(name);

	if (pPADInfo)
		LsaFreeMemory(pPADInfo);

	if (h_policy != INVALID_HANDLE_VALUE)
		LsaClose(h_policy);

	/* cache the return values so that they can just be returned on */
	/* the next call						*/
	in_the_domain = rval;
	the_domain_name = strdup(domain_name);

	return (rval);

}

/**
 * @brief
 * 	Given some network entity 'net_name' which could be a domain
 * 	name or computer name, return the  domain info such as
 * 	'domain_name' and 'domain_ctrl' (domain controller hostname) that
 * 	references entity.
 *
 * @return	int
 * @retval	1 	if info was obtained
 * @retval	0 	if unsuccessful.
 *
 * @par	NOTE: Returned values are CACHED.
 */
int
get_dcinfo(char *net_name,
	char domain_name[PBS_MAXHOSTNAME+1],
	char domain_ctrl[PBS_MAXHOSTNAME+1])
{
	static	char *id  = "get_dcinfo";
	DOMAIN_CONTROLLER_INFO *dctrl = NULL;

	/* c_data holds the cached data found.			*/
	/* c_data_[][] is used to put values into cache:	*/
	/* c_data_[0] is the returned value of this function;   */
	/* c_data_[1] is the domain_name; 			*/
	/* c_data_[2] is the domain controller hostname.  	*/
	char	*c_data = NULL;	/* returned cached data */
	char	c_data_[3][PBS_MAXHOSTNAME+1] = {0};

	if (net_name == NULL)
		return (0);

	c_data = find_cache_data(id, net_name);
	if (c_data != NULL) {
		if (strcmp(c_data, "1") == 0) {
			/* return "success" cached values */
			strcpy(domain_name, c_data+CACHE_STR_SIZE);
			strcpy(domain_ctrl, c_data+(2*CACHE_STR_SIZE));
			return (1);
		} else {
			/* return "fail" cached value */
			return (0);
		}
	}
	if ((DsGetDcName(NULL, net_name, NULL, NULL, DS_IS_FLAT_NAME, &dctrl)
	== NO_ERROR) || \
	   (DsGetDcName(net_name, NULL, NULL, NULL, DS_IS_FLAT_NAME, &dctrl)
		== NO_ERROR)) {
		if (dctrl) {
			strncpy(domain_name, dctrl->DomainName, PBS_MAXHOSTNAME);
			strncpy(domain_ctrl, dctrl->DomainControllerName, PBS_MAXHOSTNAME);
			NetApiBufferFree(dctrl);

			/* cache "success" case */
			strcpy(c_data_[0], "1");
			strcpy(c_data_[1], domain_name);
			strcpy(c_data_[2], domain_ctrl);
			cache_data(id, net_name, (char *)c_data_, 3, PBS_MAXHOSTNAME);

			return (1);	/* success */
		}
	}

	/* cache "fail" case */
	strcpy(c_data_[0], "0");
	c_data_[1][0] = '\0';
	c_data_[2][0] = '\0';
	cache_data(id, net_name, (char *)c_data_, 3, PBS_MAXHOSTNAME);

	return (0); /* fail */

}

/**
 * @brief
 *	resolve_username: Given a username of the form "ref_domain_name\username",
 *	resolve "ref_domain_name" to an "actual" domain name. The ref_domain_name
 *	may be the name of a local host in which we would want the domain name
 *	that list that host as a member. So the username string might get modified
 *	to return:
 *	"actual_domain_name\username"
 */
static void
resolve_username(char *username[PBS_MAXHOSTNAME+UNLEN+2]) /* domain\user0 */
{
	char uname[UNLEN+1] = {'\0'};
	char dname[PBS_MAXHOSTNAME+1] = {'\0'};
	char actual_dname[PBS_MAXHOSTNAME+1] = {'\0'};
	char domain_ctrl[PBS_MAXHOSTNAME+1] = {'\0'};
	char *p;

	if (username == NULL)
		return;

	dname[0] = '\0';
	uname[0] = '\0';
	actual_dname[0] = '\0';
	domain_ctrl[0] = '\0';
	if ((p=strstr((const char *)username, "\\"))) {

		*p = '\0';
		strncpy(dname, (const char *)username, (sizeof(dname) - 1));
		*p = '\\';
		strncpy(uname, p+1, UNLEN);

		if (get_dcinfo(dname, actual_dname, domain_ctrl) == 1)
			snprintf((char *)username, PBS_MAXHOSTNAME+UNLEN+1,
				"%s\\%s", actual_dname, uname);
	}
	return;
}

/**
 * @brief
 *	resolve_grpname: Given a groupname of the form "ref_domain_name\grpname",
 *	resolve "ref_domain_name" to an "actual" domain name. The ref_domain_name
 *	may be the name of a local host in which we would want the domain name
 *	that list that host as a member. So the grpname string might get modified
 *	to return:
 *	"actual_domain_name\grpname"
 */
static void
resolve_grpname(char *grpname[PBS_MAXHOSTNAME+GNLEN+2]) /* domain\user0 */
{
	char gname[GNLEN+1] = {'\0'};
	char dname[PBS_MAXHOSTNAME+1] = {'\0'};
	char actual_dname[PBS_MAXHOSTNAME+1] = {'\0'};
	char domain_ctrl[PBS_MAXHOSTNAME+1] = {'\0'};
	char *p;

	if (grpname == NULL)
		return;

	dname[0] = '\0';
	gname[0] = '\0';
	actual_dname[0] = '\0';
	domain_ctrl[0] = '\0';
	if ((p=strstr((const char *)grpname, "\\"))) {

		*p = '\0';
		strncpy(dname, (const char *)grpname, (sizeof(dname) - 1));
		*p = '\\';
		strncpy(gname, p+1, GNLEN);

		if (get_dcinfo(dname, actual_dname, domain_ctrl) == 1)
			snprintf((char *)grpname, PBS_MAXHOSTNAME+GNLEN+1,
				"%s\\%s", actual_dname, gname);
	}
	return;
}

/**
 * @brief
 *	getusersid: Given a usernam, return the machine readable SID value.
 *
 * NOTE: This returns a pointer to a malloc-ed area. Thus, need to free afterwards via LocalFree()
 *
 * @param[in] uname - username
 *
 * @return      pointer to SID
 * @retval      user sid		success
 * @retval      NULL                    error
 *
 */

SID *
getusersid(char *uname)
{
	SID			*sid = NULL;
	SID_NAME_USE		type = 0;

	if (uname == NULL)
		return NULL;

	/* a well-known SID could have a different name depending on locality */
	/* for instance, Administrators in US but Administrateurs in France */
	if( stricmp(uname, "Administrators") == 0 || \
	    stricmp(uname, "\\Administrators") == 0 ) {
		sid = create_administrators_sid();
		type = SidTypeWellKnownGroup;
	} else if( stricmp(uname, "Everyone") == 0 || \
	    	   stricmp(uname, "\\Everyone") == 0 ) {
		sid = create_everyone_sid();
		type = SidTypeWellKnownGroup;
	} else {
		char username[PBS_MAXHOSTNAME+UNLEN+2]; /* dom\user0 */

		username[0] = '\0';
		/* we may have a domain account */
		sid = get_full_username(uname, username, &type);

		if ((sid != NULL) && (type == SidTypeDomain)) {
			char username2[(2*PBS_MAXHOSTNAME)+UNLEN+3];
			/* dom\dom\user0 */
			LocalFree(sid);
			sid = NULL;
			resolve_username(username);
			/* try again with resolved name */
			username2[0] = '\0';
			sid = get_full_username(username, username2, &type);
		}

	}

	if (sid == NULL) {
		return NULL;
	}

	if( type != SidTypeUser && type != SidTypeWellKnownGroup && \
						type != SidTypeAlias) {
		LocalFree(sid);
		return NULL;
	}

	return (sid);

}

SID *
getusersid2(char *uname,
	char realuser[PBS_MAXHOSTNAME+UNLEN+2]) /* dom\user0 */
{
	SID		*sid = NULL;
	SID_NAME_USE	type = 0;
	char 		username[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'}; /* domain\user0 */
	char		*p = NULL;
	HANDLE		hToken = INVALID_HANDLE_VALUE;
	DWORD		dwBufferSize = 0;
	PTOKEN_USER	pTokenUser = NULL;
	char		*login_full = NULL;
	char		logb[LOG_BUF_SIZE] = {'\0' } ;

	if (uname == NULL)
		return NULL;

	username[0] = '\0';

	/* a well-known SID could have a different name depending on locality */
	/* for instance, Administrators in US but Administrateurs in France */
	if( stricmp(uname, "Administrators") == 0 || \
	    stricmp(uname, "\\Administrators") == 0 ) {
		sid = create_administrators_sid();
		p = getusername(sid);
		if (p) {
			strcpy(username, p);
			(void)free(p);
		}
		type = SidTypeWellKnownGroup;
	} else if( stricmp(uname, "Everyone") == 0 || \
	    	   stricmp(uname, "\\Everyone") == 0 ) {
		sid = create_everyone_sid();
		p = getgrpname(sid);
		if (p) {
			strcpy(username, p);
			(void)free(p);
		}
		type = SidTypeWellKnownGroup;
	} else {
		/* we may have a domain account */
		if ((strcmp(uname, getlogin()) != 0)) {

			sid = get_full_username(uname, username, &type);
			if ((sid != NULL) && (type == SidTypeDomain)) {
				char username2[(2*PBS_MAXHOSTNAME)+UNLEN+3];
				/* dom\dom\user\0 */
				LocalFree(sid);
				sid = NULL;
				resolve_username(username);
				/* try again with resolved username */
				username2[0] = '\0';
				sid = get_full_username(username, username2, &type);
			}
			if (sid == NULL) {
				return NULL;
			}

			if (type != SidTypeUser && type != SidTypeWellKnownGroup &&
				type != SidTypeAlias) {
				LocalFree(sid);
				return NULL;
			}
			strcpy(realuser, username);
		} else {
			/*determine sid of current user without making query to the domain.*/
			/* Open the access token associated with the calling process. */
			if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &hToken)) {
				sprintf(logb,"OpenProcessToken failed. GetLastError returned: %d", GetLastError());
				log_err(-1, "getusersid2", logb);
				return NULL;
				/**     this function returns SID. **/
			}

			/* get the size of the memory buffer needed for the SID */
			GetTokenInformation(hToken, TokenUser, NULL, 0, &dwBufferSize);
			if (GetLastError() == ERROR_INSUFFICIENT_BUFFER) {

				pTokenUser = (PTOKEN_USER)malloc(dwBufferSize);
				if (pTokenUser == NULL) {
					fprintf(stderr, "malloc failed");
					CloseHandle(hToken);
					return NULL;
				}

			} else { /* actual error */
				CloseHandle(hToken);
				return NULL;
			}

			memset(pTokenUser, 0, dwBufferSize);

			/* Retrieve the token information in a TOKEN_USER structure. */
			if (!GetTokenInformation(hToken, TokenUser, pTokenUser, dwBufferSize,
				&dwBufferSize)) {
				sprintf(logb,"GetTokenInformation failed. GetLastError returned: %d", GetLastError());
				log_err(-1, "getusersid2", logb);
				CloseHandle(hToken);
				free(pTokenUser);
				return NULL;
			}
			if (!IsValidSid(pTokenUser->User.Sid)) {
				sprintf(logb,"The owner SID is invalid.");
				log_err(-1, "getusersid2", logb);
				CloseHandle(hToken);
				free(pTokenUser);
				return NULL;
			}

			sid = sid_dup(pTokenUser->User.Sid);
			login_full = getlogin_full();
			strncpy(realuser, login_full, strlen(login_full));

			CloseHandle(hToken);
			free(pTokenUser);
		}
	}
	return (sid);

}

/**
 * @brief
 *	getuserpname: Given a SID value, return the human readable username
 *
 * @par NOTE:
 *	This returns a pointer to a malloc-ed area. Thus, need to free afterwards
 *
 * @param[in] sid - SID val
 *
 * @return	string
 * @retval	username	success
 * @retval	NULL		error
 *
 */
char *
getusername(SID *sid)
{
	TCHAR			*name = NULL;
	DWORD			name_sz;
	TCHAR			domain[PBS_MAXHOSTNAME+1] = "";
	DWORD			domain_sz;
	SID_NAME_USE	type;

	name_sz = 0;
	domain_sz = sizeof(domain);

	if (LookupAccountSid(0, sid, name, &name_sz, domain, &domain_sz, &type) != 0) {
		return NULL;
	}

	if ((name = malloc(name_sz)) == NULL) {
		return NULL;
	}

	if (LookupAccountSid(0, sid, name, &name_sz, domain, &domain_sz, &type) == 0) {
		(void)free(name);
		return NULL;
	}

	if (type != SidTypeUser && type != SidTypeAlias && type != SidTypeWellKnownGroup) {
		(void)free(name);
		return NULL;
	}

	return (name);

}


/**
 * @brief
 *	getusername_full: Given a SID value, return the human readable "full"
 *  	username: <domain_name>\<user>.
 *
 * @par NOTE:
 *	This returns a pointer to a malloc-ed area. Thus, need to free afterwards
 *
 * @return	string
 * @retval	full username	success
 * @retval	NULL		error
 *
 */
char *
getusername_full(SID *sid)
{
	TCHAR			*name = NULL;
	DWORD			name_sz;
	TCHAR			domain[PBS_MAXHOSTNAME+1] = "";
	DWORD			domain_sz;
	SID_NAME_USE		type;
	char			*fullname = NULL;

	name_sz = 0;
	domain_sz = sizeof(domain);

	if (LookupAccountSid(0, sid, name, &name_sz, domain, &domain_sz, &type) != 0) {
		return NULL;
	}

	if ((name = malloc(name_sz)) == NULL) {
		return NULL;
	}

	if (LookupAccountSid(0, sid, name, &name_sz, domain, &domain_sz, &type) == 0) {
		(void)free(name);
		return NULL;
	}

	if (type != SidTypeUser && type != SidTypeAlias && type != SidTypeWellKnownGroup) {
		(void)free(name);
		return NULL;
	}

	fullname = (char *)malloc(domain_sz + 1 + name_sz + 1);
	if (fullname == NULL) {
		(void)free(name);
		return NULL;
	}
	sprintf(fullname, "%s\\%s", domain, name);
	(void)free(name);
	return (fullname);
}

/**
 * @brief
 *	getgroupsid: Given a grpnam, return the machine readable SID value.
 *
 * @par NOTE:
 *	This returns a pointer to a malloc-ed area. Thus, need to free afterwards
 *
 * @param[in] grpnam - group name
 *
 * @return	pointer to SID
 * @retval	SID val			success
 * @retval	NULL			error
 *
 */
SID *
getgrpsid(char *grpnam)
{
	SID		*sid = NULL;
	SID_NAME_USE	type;

	if (grpnam == NULL)
		return NULL;

	/* a well-known SID could have a different name depending on locality */
	/* for instance, Administrators in US but Administrateurs in France */
	if( stricmp(grpnam, "Administrators") == 0 || \
	    stricmp(grpnam, "\\Administrators") == 0 ) {

		sid = create_administrators_sid();

		type = SidTypeWellKnownGroup;
	} else if( stricmp(grpnam, "Everyone") == 0 || \
	    	   stricmp(grpnam, "\\Everyone") == 0 ) {
		sid = create_everyone_sid();
		type = SidTypeWellKnownGroup;
	} else {
		DWORD  sid_sz;
		TCHAR  domain[PBS_MAXHOSTNAME+1] = "";
		DWORD  domain_sz;
		char   grpnam2[PBS_MAXHOSTNAME+GNLEN+2];    /* dom\grp\0 */
		int    pass;
		int    max_len;

		sid_sz = 0;
		domain_sz = sizeof(domain);
		max_len = (sizeof(grpnam2) - 1);


		/* will pass through twice at most */
		strncpy(grpnam2, grpnam, max_len);
		for (pass=0; pass < 2; pass++) {

			if (LookupAccountName(0, grpnam2, sid, &sid_sz,
				domain, &domain_sz, &type) != 0) {
				return NULL;
			}

			if ((sid = (SID *)LocalAlloc(LPTR, sid_sz)) == NULL) {
				return NULL;
			}

			if (LookupAccountName(0, grpnam2, sid, &sid_sz,
				domain, &domain_sz, &type) == 0) {
				LocalFree(sid);
				return NULL;
			}


			if ((sid != NULL) && (type == SidTypeDomain)) {
				snprintf(grpnam2, max_len,
					"%s\\%s", domain, grpnam);
				resolve_grpname(grpnam2);
				LocalFree(sid);
				sid = NULL;
				continue;
			}
			break;
		}
	}

	if (type != SidTypeGroup && type != SidTypeAlias && type != SidTypeWellKnownGroup) {
		LocalFree(sid);
		return NULL;
	}

	return (sid);

}

/**
 * @brief
 *	getgrpname: Given a SID value, return the human readable name
 *
 * @par NOTE:
 *	This returns a pointer to a malloc-ed area. Thus, need to free afterwards
 *
 * @param[in] sid - SID val
 *
 * @return	string
 * @retval	name	success
 * @retval	NULL	error
 *
 */
char *
getgrpname(SID *sid)
{
	TCHAR			*name = NULL;
	DWORD			name_sz;
	TCHAR			domain[PBS_MAXHOSTNAME+1] = "";
	DWORD			domain_sz;
	SID_NAME_USE	type;

	name_sz = 0;
	domain_sz = sizeof(domain);

	if (LookupAccountSid(0, sid, name, &name_sz, domain, &domain_sz, &type) != 0) {
		return NULL;
	}

	if ((name = malloc(name_sz)) == NULL) {
		return NULL;
	}

	if (LookupAccountSid(0, sid, name, &name_sz, domain, &domain_sz, &type) == 0) {
		(void)free(name);
		return NULL;
	}

	if (type != SidTypeGroup && type != SidTypeAlias && type != SidTypeWellKnownGroup) {
		(void)free(name);
		return NULL;
	}

	return (name);

}

/**
 * @brief
 *	getgrpname_full: like getgrpname() except the domainname of the group is also prefixed.
 *
 * @par	NOTE:
 *	This returns a pointer to a malloc-ed area. Thus, need to free afterwards
 *
 * @param[in] sid - SID value
 *
 * @return	string
 * @retval	full grp name	success
 * @retval	NULL		error
 *
 */
char *
getgrpname_full(SID *sid)
{
	TCHAR			*name = NULL;
	DWORD			name_sz;
	TCHAR			domain[PBS_MAXHOSTNAME+1] = "";
	DWORD			domain_sz;
	SID_NAME_USE	type;
	char			*fullname;

	name_sz = 0;
	domain_sz = sizeof(domain);

	if (LookupAccountSid(0, sid, name, &name_sz, domain, &domain_sz, &type) != 0) {
		return NULL;
	}

	if ((name = malloc(name_sz)) == NULL) {
		return NULL;
	}

	if (LookupAccountSid(0, sid, name, &name_sz, domain, &domain_sz, &type) == 0) {
		(void)free(name);
		return NULL;
	}

	if (type != SidTypeGroup && type != SidTypeAlias && type != SidTypeWellKnownGroup) {
		(void)free(name);
		return NULL;
	}

	fullname = (char *)malloc(domain_sz + 1 + name_sz + 1);
	if (fullname == NULL) {
		(void)free(name);
		return NULL;
	}

	sprintf(fullname, "%s\\%s", domain, name);
	(void)free(name);
	return (fullname);

}

/**
 * @brief
 * 	returns the # of global groups found for user, with the list places in groupsp.
 *
 * @par NOTE:
 *	groupsp must be freed by NetApiBufferFree()
 *
 * @param[in] user - user name
 * @param[out] groupsp - groups
 *
 * @return	int
 * @retval	num of groups	success
 * @retval	0		error
 *
 */
static int
getGlobalGroups(char *user, GROUP_USERS_INFO_0 **groupsp)
{

	GROUP_USERS_INFO_0 *groups = NULL;

	DWORD nread, total;
	DWORD pref = 16;
	DWORD rc;
	wchar_t userw[UNLEN+1] = {'\0'};

	char    dname[PBS_MAXHOSTNAME+1] = {'\0'};

	char    domain_name[PBS_MAXHOSTNAME+1] = {'\0'};
	char    user_name[PBS_MAXHOSTNAME+1] = {'\0'};

	char    dctrl[PBS_MAXHOSTNAME+1] = {'\0'};
	wchar_t dctrlw[PBS_MAXHOSTNAME+1] = {'\0'};
	char	*p = NULL;

	/* user: <domain_name>\<user_name> */
	if ((p=strrchr(user, '\\'))) {
		*p = '\0';
		strcpy(domain_name, user);
		*p = '\\';
		strcpy(user_name, p+1);
	} else {	/* user: <user_name> */
		strcpy(domain_name, "");
		strcpy(user_name, user);
	}

	strcpy(dctrl, domain_name);
	if (GetComputerDomainName(dname) == 1) {
		char    dname_a[PBS_MAXHOSTNAME+1];

		get_dcinfo(domain_name, dname_a, dctrl);
	}

	mbstowcs(dctrlw, dctrl, PBS_MAXHOSTNAME);
	mbstowcs(userw, user_name, UNLEN);

	/* Search Global groups */
	do {
		pref *= 4096;
		if (groups) {
			NetApiBufferFree(groups);
			groups = NULL;
		}

		if ((wcslen(dctrlw) == 0)) {
			rc = wrap_NetUserGetGroups(NULL, userw, 0,
				(LPBYTE *)&groups, pref, &nread, &total);
		} else {
			rc = wrap_NetUserGetGroups(dctrlw, userw, 0,
				(LPBYTE *)&groups, pref, &nread, &total);
		}
	} while (rc == NERR_BufTooSmall || rc == ERROR_MORE_DATA);

	if (rc != NERR_Success) {
		if (groups) {
			NetApiBufferFree(groups);
			groups = NULL;
			nread = 0;
		}
	}
	*groupsp = groups;
	return (nread);
}

/**
 * @brief
 *	returns the # of local groups found for user, with the list places in groupsp.
 *
 * @par	NOTE: *groupsp must be freed by NetApiBufferFree()
 *
 * @param[in] user - username
 * @param[in] groupsp - pointer to groups
 *
 * @return	int
 * @retval	num of local grps	success
 * @retval	0			error
 *
 */
static int
getLocalGroups(char *user, GROUP_USERS_INFO_0 **groupsp)
{

	GROUP_USERS_INFO_0 *groups = NULL;

	DWORD nread, total;
	DWORD pref = 16;
	DWORD rc;
	wchar_t userw[UNLEN+1] = {'\0'};

	char    dname[PBS_MAXHOSTNAME+1] = {'\0'};

	char    domain_name[PBS_MAXHOSTNAME+1] = {'\0'};
	char    user_name[PBS_MAXHOSTNAME+1] = {'\0'};

	char    dctrl[PBS_MAXHOSTNAME+1] = {'\0'};
	wchar_t dctrlw[PBS_MAXHOSTNAME+1] = {'\0'};
	char	*p = NULL;

	/* user: <domain_name>\<user_name> */
	if ((p=strrchr(user, '\\'))) {
		*p = '\0';
		strcpy(domain_name, user);
		*p = '\\';
		strcpy(user_name, p+1);
	} else {	/* user: <user_name> */
		strcpy(domain_name, "");
		strcpy(user_name, user);
	}

	strcpy(dctrl, domain_name);
	if (GetComputerDomainName(dname) == 1) {
		char    dname_a[PBS_MAXHOSTNAME+1] = {'\0'};

		get_dcinfo(domain_name, dname_a, dctrl);
	}

	mbstowcs(dctrlw, dctrl, PBS_MAXHOSTNAME);
	mbstowcs(userw, user_name, UNLEN);

	/* Search Local groups */
	do {
		pref *= 4096;
		if (groups) {
			NetApiBufferFree(groups);
			groups = NULL;
		}

		if ((wcslen(dctrlw) == 0))
			rc = wrap_NetUserGetLocalGroups(NULL, userw, 0,
				LG_INCLUDE_INDIRECT, (LPBYTE *)&groups, pref,
				&nread, &total);
		else
			rc = wrap_NetUserGetLocalGroups(dctrlw, userw, 0,
				LG_INCLUDE_INDIRECT, (LPBYTE *)&groups, pref,
				&nread, &total);
	} while (rc == NERR_BufTooSmall || rc == ERROR_MORE_DATA);

	if (rc != NERR_Success) {
		if (groups) {
			NetApiBufferFree(groups);
			groups = NULL;
			nread = 0;
		}
	}
	*groupsp = groups;
	return (nread);
}


/**
 * @brief
 *	isLocalAdminMember: returns TRUE if user belongs to the local
 * 	Administrators group on the local computer. Otherwise, returns
 * 	0 for FALSE.
 *
 * @param[in] user - username
 *
 * @par NOTE: 'user' can be of the form "<domain_name>\<user_name>".
 *
 * @return	int
 * @retval	TRUE	success
 * @retval	FALSE	error
 *
 */
int
isLocalAdminMember(char *user)
{
	SID	*sid = NULL;
	char	*gname = NULL;
	wchar_t	userw[PBS_MAXHOSTNAME+UNLEN+2]=L""; /* domain\user0 */
	wchar_t	 gnamew[GNLEN+1]=L"";
	LOCALGROUP_MEMBERS_INFO_2 *members = NULL;
	DWORD	nread = 0;
	DWORD	totentries = 0;
	DWORD	i = 0;
	int	ret = 0;

	sid = create_administrators_sid();

	if (sid == NULL) {
		return (0);	/* can't figure out Administrators sid */
	}
	if ((gname=getgrpname(sid)) == NULL) {
		goto isLocalAdminMember_end;
	}
	mbstowcs(userw, user, PBS_MAXHOSTNAME+UNLEN+1);
	mbstowcs(gnamew, gname, GNLEN);

	if (NetLocalGroupGetMembers(NULL, gnamew, 2, (LPBYTE *)&members,
		MAX_PREFERRED_LENGTH, &nread, &totentries, NULL) != NERR_Success) {
		goto isLocalAdminMember_end;
	}

	for (i=0; i < nread; i++) {
		if (wcsicmp(members[i].lgrmi2_domainandname, userw) == 0) {
			ret = 1;
			break;
		}
	}

isLocalAdminMember_end:
	if (sid) {
		LocalFree(sid);
	}
	if (gname) {
		(void)free(gname);
	}
	if (members) {
		NetApiBufferFree(members);
	}

	return (ret);
}

/**
 * @brief
 *	returns TRUE if user belongs to group where that group is local or global (network). Otherwise,
 *	FALSE.
 *
 * @param[in] user - username
 * @param[in] group - groupname
 *
 * @return	int
 * @retval	TRUE	user belongs to group
 * @retval	FALSE	user doesn belong to group
 *
 */
int
isMember(char *user, char *group)
{

	GROUP_USERS_INFO_0 *groups = NULL;
	DWORD	nread;
	DWORD	i;
	wchar_t groupw[GNLEN+1] = {'\0'};
	char		realuser[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'}; /* dom\user0 */
	SID_NAME_USE	sid_type;
	SID		*sid = NULL;

	sid = get_full_username(user, realuser, &sid_type);

	if (sid == NULL)
		return (FALSE);

	LocalFree(sid);

	if (isLocalAdminMember(realuser))
		return (TRUE);

	mbstowcs(groupw, group, GNLEN);
	/* Search Global groups */
	if ((nread=getGlobalGroups(realuser, &groups)) > 0 && groups) {

		for (i=0; i < nread; i++) {
			if (wcscmp(groups[i].grui0_name, groupw) == 0) {
				NetApiBufferFree(groups);
				return (TRUE);
			}
		}
		NetApiBufferFree(groups);
		groups = NULL;
	}

	/* Search Local groups */
	if ((nread=getLocalGroups(realuser, &groups)) > 0 && groups) {

		for (i=0; i < nread; i++) {
			if (wcscmp(groups[i].grui0_name, groupw) == 0) {
				NetApiBufferFree(groups);
				return (TRUE);
			}
		}
		NetApiBufferFree(groups);
		groups = NULL;
	}
	return (FALSE);
}

DWORD
sid2rid(SID *sid)
{
	DWORD	*rid;

	if (sid == NULL)
		return (-1);

	/* The last sub-authority of the machine SID is always -1, so use the
	 second to last. */

	rid = GetSidSubAuthority(sid, *GetSidSubAuthorityCount(sid)-1);

	if (rid)
		return (*rid);
	return (-1);
}

/**
 * @brief
 *	Is current process running under LOCALSYSTEM?
 *
 *
 * @return      BOOL
 * @retval	TRUE - Process running with LOCALSYSTEM account
 * @retval	FALSE - Process NOT running with LOCALSYSTEM account
 *
 */
BOOL
isLocalSystem()
{
  HANDLE			hToken_currentproc = INVALID_HANDLE_VALUE;
  PSID				pls_sid;
  BOOL				is_local_system = FALSE;
  UCHAR				usertoken[sizeof(TOKEN_USER) + sizeof(SID) + sizeof(DWORD) * SID_MAX_SUB_AUTHORITIES];
  PTOKEN_USER			pusertoken = (PTOKEN_USER)usertoken;
  ULONG				usertoken_returnlen;
  SID_IDENTIFIER_AUTHORITY	sid_ia_NT = SECURITY_NT_AUTHORITY;

  /*
   * Open current process token
   * and get user sid
   */
  if (!OpenProcessToken(GetCurrentProcess(),
	  TOKEN_QUERY,
	  &hToken_currentproc))
	  return FALSE;
  if (!GetTokenInformation(hToken_currentproc, TokenUser, pusertoken,
	  sizeof(usertoken), &usertoken_returnlen))
  {
	  CloseHandle(hToken_currentproc);
	  return FALSE;
  }
  CloseHandle(hToken_currentproc);

  /* See if user sid is Local System SID */
  if (!AllocateAndInitializeSid(&sid_ia_NT, 1, SECURITY_LOCAL_SYSTEM_RID,
	  0, 0, 0, 0, 0, 0, 0, &pls_sid))
	  return FALSE;

  is_local_system = EqualSid(pusertoken->User.Sid, pls_sid);
  FreeSid(pls_sid);

  return is_local_system;
}

/**
 *
 * @brief       Determines if a user has local Administrator privilege.
 *
 * @param[in]   user - user being looked up.
 *
 * @return      int
 * @retval	TRUE if 'user' has local Administrator privilege.
 * @retval	FALSE; otherwise.
 *
 *
 * @note
 *	This returns TRUE if one of the following conditions is satisfied:
 *		1) user is a member of the local Administrators group on the
 *		   local computer.
 *		2) user  is a member of Domain Admins, Enterprise Admins,
 *		   Schema Admins, or domain Administrators group.
 *		3) user is a member of a global/domain group that is a member
 *		   of the local Administrators group on the local computer.
 *
 *	The returned value is CACHED for faster future lookups.
 *	The value is not expected to change often, and if it does, warrants a
 *	restart of the program/service calling this function.
 *
 */
int
isAdminPrivilege(char *user)
{
	GROUP_USERS_INFO_0 *groups = NULL;
	DWORD	nread;
	DWORD	i;
	char	realuser[UNLEN+1]={'\0'};
	char	group[GNLEN+1]={'\0'};
	SID		*usid;
	SID		*gsid;
	DWORD	grid;
	DWORD	urid;

	char	*c_data = NULL;
	char	c_data_[1][6] = {0};/* 6 is for length of MAX("TRUE","FALSE") */

	char *gfull = NULL;

	if (user == NULL)
		return (FALSE);

	c_data = find_cache_data(__func__, user);
	if (c_data != NULL) {
		if (strcmp(c_data, "TRUE") == 0)
			return (TRUE);
		else
			return (FALSE);
	}

	/* is user an Administrator account ? */
	if ((usid=getusersid2(user, realuser)) && (urid=sid2rid(usid))) {
		LocalFree(usid);
		if (urid == DOMAIN_USER_RID_ADMIN ||
			(urid == SECURITY_LOCAL_SYSTEM_RID)) {

			strcpy(c_data_[0], "TRUE");
			cache_data(__func__, user, (char *)c_data_, 1, 6);

			return (TRUE);
		}
	}

	if (isLocalAdminMember(realuser)) {

		strcpy(c_data_[0], "TRUE");
		cache_data(__func__, user, (char *)c_data_, 1, 6);

		return (TRUE);
	}

	/* Search Global groups */
	if ((nread=getGlobalGroups(realuser, &groups)) > 0 && groups) {

		for (i=0; i < nread; i++) {
			wcstombs(group, groups[i].grui0_name, GNLEN);
			if ((gsid=getgrpsid(group)) && (grid=sid2rid(gsid))) {

				if ((grid == DOMAIN_GROUP_RID_ADMINS) ||
					(grid == DOMAIN_ALIAS_RID_ADMINS) ||
					(grid == DOMAIN_ALIAS_RID_SYSTEM_OPS) ||
					(grid == DOMAIN_GROUP_RID_ENTERPRISE_ADMINS) ||
					(grid == DOMAIN_GROUP_RID_SCHEMA_ADMINS)) {
					NetApiBufferFree(groups);
					LocalFree(gsid);

					strcpy(c_data_[0], "TRUE");
					cache_data(__func__, user, (char *)c_data_,
						1, 6);

					return (TRUE);
				}
			}
			if (gsid != NULL) {
				if ((gfull=getgrpname_full(gsid)) != NULL) {

					if (isLocalAdminMember(gfull)) {
						strcpy(c_data_[0], "TRUE");
						cache_data(__func__, user, (char *)c_data_,
							1, 6);
						NetApiBufferFree(groups);
						LocalFree(gsid);
						free(gfull);
						return (TRUE);
					}
					free(gfull);
				}
				LocalFree(gsid);
			}
		}
		NetApiBufferFree(groups);
		groups = NULL;
	}

	/* Search Local groups */
	if ((nread=getLocalGroups(realuser, &groups)) > 0 && groups) {

		for (i=0; i < nread; i++) {
			wcstombs(group, groups[i].grui0_name, GNLEN);

			if ((gsid=getgrpsid(group)) && (grid=sid2rid(gsid))) {

				LocalFree(gsid);
				if ((grid == DOMAIN_GROUP_RID_ADMINS) ||
					(grid == DOMAIN_ALIAS_RID_ADMINS) ||
					(grid == DOMAIN_ALIAS_RID_SYSTEM_OPS) ||
					(grid == DOMAIN_GROUP_RID_ENTERPRISE_ADMINS) ||
					(grid == DOMAIN_GROUP_RID_SCHEMA_ADMINS)) {
					NetApiBufferFree(groups);

					strcpy(c_data_[0], "TRUE");
					cache_data(__func__, user, (char *)c_data_,
						1, 6);

					return (TRUE);
				}
			}
		}
		NetApiBufferFree(groups);
		groups = NULL;
	}

	strcpy(c_data_[0], "FALSE");
	cache_data(__func__, user, (char *)c_data_, 1, 6);

	return (FALSE);
}

/* returns 1 if sid is an admin alias or group, or is a member of an admin group. Otherwise, return 0. */
int
sidIsAdminPrivilege(SID *sid)
{
	char	*user;
	int		ret;
	int		rid;

	rid = sid2rid(sid);

	/* assume it's a group sid */
	if( rid == DOMAIN_ALIAS_RID_ADMINS || \
	    rid == DOMAIN_GROUP_RID_ADMINS || \
	    rid == DOMAIN_ALIAS_RID_SYSTEM_OPS || \
	    rid == SECURITY_LOCAL_SYSTEM_RID) {
		return (1);
	}

	/* then maybe it's a user sid */
	user = getusername(sid);
	if (user == NULL)
		return (0);

	ret = isAdminPrivilege(user);

	(void)free(user);

	return (ret);
}

/*
 * Returns the default group name. Return value must be freed!
 *
 * NOTE: Returned value is CACHED.
 */
char *
getdefgrpname(char *user)
{

	GROUP_USERS_INFO_0 *groups = NULL;
	char	*group;
	char	realuser[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'}; /* dom\user0 */
	DWORD	sid_sz = 0;
	SID_NAME_USE	sid_type;
	SID		*sid = NULL;

	char	*c_data = NULL;
	char	c_data_[1][GNLEN+1] = {0};

	if (user == NULL)
		return NULL;

	c_data = find_cache_data(__func__, user);
	if (c_data != NULL) {
		return (strdup(c_data)); /* malloced value expected for return */
	}

	sid = get_full_username(user, realuser, &sid_type);

	if (sid == NULL)
		return NULL;

	LocalFree(sid);

	if ((group=malloc(GNLEN+1)) == NULL)
		return NULL;

	/* Search Local groups */
	if (getLocalGroups(realuser, &groups) > 0 && groups) {
		wcstombs(group, groups[0].grui0_name, GNLEN);
		NetApiBufferFree(groups);

		strcpy(c_data_[0], group);
		cache_data(__func__, user, (char *)c_data_, 1, GNLEN);

		return (group);
	}

	/* Search Global groups */
	if (getGlobalGroups(realuser, &groups) > 0 && groups) {
		wcstombs(group, groups[0].grui0_name, GNLEN);
		NetApiBufferFree(groups);

		strcpy(c_data_[0], group);
		cache_data(__func__, user, (char *)c_data_, 1, GNLEN);

		return (group);
	}
	/* No groups detected but 'group' has been malloced in advance */
	(void)free(group);

	strcpy(c_data_[0], "Everyone");
	cache_data(__func__, user, (char *)c_data_, 1, GNLEN);

	return (strdup("Everyone"));
}

/* getdefgrpsid: returns the default group sid. LocalFree() the return value */
SID *
getdefgrpsid(char *user)
{
	char *gname = NULL;
	SID  *gsid = NULL;

	if (gname=getdefgrpname(user))
		gsid=getgrpsid(gname);

	if (gname)
		(void)free(gname);

	return (gsid);

}

/* Returns the user name of the current thread. This returns a statically-allocated buffer. */
char *
getlogin(void)
{
	static char	usern[UNLEN+1] = {'\0'};
	int		sz;
	int		ret;

	sz = UNLEN+1;
	ret = GetUserName(usern, &sz);
	if (ret == 0) {
		HANDLE	token = INVALID_HANDLE_VALUE;
		char	*buf = NULL;
		DWORD	cb;

		if (OpenThreadToken(GetCurrentThread(), TOKEN_ALL_ACCESS,
			TRUE, &token)  == 0) {
			OpenProcessToken(GetCurrentProcess(), TOKEN_ALL_ACCESS,
				&token);
		}
		if (token == INVALID_HANDLE_VALUE) {
			strcpy(usern, "");
			return (usern);
		}

		cb = 0;
		if (GetTokenInformation(token, TokenUser, buf, cb, &cb)) {
			CloseHandle(token);
			strcpy(usern, "");
			return (usern);
		} else {

			buf = (char *) malloc(cb);
			if (buf == NULL) {
				CloseHandle(token);
				strcpy(usern, "");
				return (usern);
			}

			if (GetTokenInformation(token, TokenUser, buf, cb,
				&cb)) {

				TOKEN_USER      *ptu = (TOKEN_USER *)buf;
				char	*user;

				user = getusername(ptu->User.Sid);
				if (user) {
					strncpy(usern, user, UNLEN);
					(void)free(user);
				}
				else {
					strcpy(usern, "");
				}
			}
			(void)free(buf);
		}
		CloseHandle(token);
	}

	return (usern);
}

/* Returns the "full" user name (format: <domain>\<user>) of the current   */
/* thread. This returns a statically-allocated buffer. This return empy "" */
/* if error encountered.  						   */
char *
getlogin_full(void)
{
	static char	usern[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'};
	int		sz;
	int		ret;

	sz = UNLEN+1;
	ret = GetUserNameEx(NameSamCompatible, usern, &sz);
	if (ret == 0) {
		HANDLE	token = INVALID_HANDLE_VALUE;
		char	*buf = NULL;
		DWORD	cb;

		if (OpenThreadToken(GetCurrentThread(), TOKEN_ALL_ACCESS,
			TRUE, &token)  == 0) {
			OpenProcessToken(GetCurrentProcess(), TOKEN_ALL_ACCESS,
				&token);
		}
		if (token == INVALID_HANDLE_VALUE) {
			strcpy(usern, "");
			return (usern);
		}

		cb = 0;
		if (GetTokenInformation(token, TokenUser, buf, cb, &cb)) {
			CloseHandle(token);
			strcpy(usern, "");
			return (usern);
		} else {

			buf = (char *) malloc(cb);
			if (buf == NULL) {
				CloseHandle(token);
				strcpy(usern, "");
				return (usern);
			}

			if (GetTokenInformation(token, TokenUser, buf, cb,
				&cb)) {

				TOKEN_USER      *ptu = (TOKEN_USER *)buf;
				char	*user;

				user = getusername_full(ptu->User.Sid);
				if (user) {
					strncpy(usern, user, UNLEN);
					(void)free(user);
				}
				else {
					strcpy(usern, "");
				}
			}
			(void)free(buf);
		}
		CloseHandle(token);
	}

	return (usern);
}

/* Returns the user id (SID) of the current thread/process.                  */
/* The return value is a malloced piece of memory that is kept               */
/* around (cached). Calling this function multiple times will return the     */
/* the same value that was initially obtained.                               */
/* If you wish to recreate the returned value, for instance if the current   */
/* thread impersonates a different user, then simply free up the return      */
/* value of getuid(), and then  call it again:                               */
/*           Ex.                                                             */
/*		   usid=getuid();  <-- returns sid of say ADMIN     	     */
/*                 ImpersonateLoggedOnUser(logonuser); <-- impersonate USER  */
/*                 cached_sid = getuid();                                    */
/*                 if( cached_sid ) {                                        */
/*			LocalFree(cached_sid);                               */
/*                      usid=getuid();  <-- now return sid of USER           */
/* NOTE: Do not LocalFree() on the return value unless you want it           */
/*	 regenerated on subsequent calls.                                    */
SID *
getuid(void)
{
	char	*uname;
	static  SID *usid = NULL;


	if (usid != NULL) {

		if (IsValidSid(usid))
			return (usid);	/* use cached value */

		usid = NULL;		/* prepare to regenerate */
	}

	uname = getlogin();

	if (uname == NULL)
		return NULL;

	usid   = getusersid(uname);

	return (usid);
}

/* Returns the group id (SID) of the current thread/process.                 */
/* The return value is a malloced piece of memory that is kept               */
/* around (cached). Calling this function multiple times will return the     */
/* the same value that was initially obtained.                               */
/* If you wish to recreate the returned value, for instance if the current   */
/* thread impersonates a different user, then simply free up the return      */
/* value of getgid(), and then  call it again:                               */
/*           Ex.                                                             */
/*		   gsid=getgid();  <-- returns default group sid of ADMIN    */
/*                 ImpersonateLoggedOnUser(logonuser); <-- impersonate USER  */
/*                 cached_gsid = getgid();                                   */
/*                 if( cached_gsid ) {                                       */
/*			LocalFree(cached_gsid);                              */
/*                      gsid=getgid();  <-- return default group sid of USER */
/* NOTE: Do not LocalFree() on the return value unless you want it           */
/*	 regenerated on subsequent calls.                                    */
SID *
getgid(void)
{
	char	*gname;
	static  SID   *gsid = NULL;

	if (gsid != NULL) {

		if (IsValidSid(gsid))
			return (gsid);	/* use cached value */

		gsid = NULL;	/* prepare to re-generate */
	}

	gname = getdefgrpname(getlogin());
	if (gname == NULL)
		return NULL;

	gsid   = getgrpsid(gname);

	(void)free(gname);

	return (gsid);
}

/*
 * Given a user, return a list of its group sids in 'grp'. Each sid must later
 * be LocalFree()d.
 *
 * This returns the # of groups found. To restrict the groups of a certain
 * type, then use thethe rids parameter.
 *
 * NOTE: Returned values are CACHED.
 * return groups that matches the rids found here. Set rids[0]=0 to skip
 */
int
getgids(char *user, SID *grp[], DWORD rids[])
{

	GROUP_USERS_INFO_0 *groups = NULL;
	DWORD	nread;
	DWORD	i, j, k;
	char	group[GNLEN+1] = {'\0'};
	SID		*g;
	int		found;
	char    realuser[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'}; /* dom\user0 */
	SID_NAME_USE    sid_type;
	SID             *sid = NULL;

	char		*c_data = NULL;
	char		c_data_[_MAX_GROUPS][GNLEN+1] = {0};

	if (user == NULL)
		return (0);

	c_data = find_cache_data(__func__, user);
	if (c_data != NULL) {
		char *end_c_data = c_data + (CACHE_VALUE_NELEM*CACHE_STR_SIZE);
		SID  *gsid = NULL;

		j = 0;
		while (c_data < end_c_data) {
			if (c_data[0] == '\0')
				break;
			gsid = getgrpsid(c_data);
			if (gsid == NULL)
				break;
			grp[j] = gsid;
			j++;
			c_data += CACHE_STR_SIZE;
		}
		return (j);
	}

	sid = get_full_username(user, realuser, &sid_type);

	if (sid == NULL)
		return (0);

	LocalFree(sid);

	j=0;
	/* Search Global groups */
	if ((nread=getGlobalGroups(realuser, &groups)) > 0 && groups) {

		for (i=0; (i < nread) && (j < _MAX_GROUPS); i++) {
			wcstombs(group, groups[i].grui0_name, GNLEN);
			g = getgrpsid(group);
			if (g == NULL) /* bad group */
				continue;

			found = 0;
			if (rids[0] == 0)
				found = 1;
			else {
				for (k=0; k < sizeof(rids); k++) {
					if (sid2rid(g) == rids[k]) {
						found = 1;
						break;
					}
				}
			}
			if (found) {
				grp[j] = g;

				strcpy(c_data_[j], group);

				j++;
			} else {
				LocalFree(g);
			}
		}
		NetApiBufferFree(groups);
		groups = NULL;
	}

	/* Search Local groups */
	if ((nread=getLocalGroups(realuser, &groups)) > 0 && groups) {

		for (i=0; (i < nread) && (j < _MAX_GROUPS); i++) {
			wcstombs(group, groups[i].grui0_name, GNLEN);
			g = getgrpsid(group);
			if (g == NULL) /* bad group */
				continue;
			found = 0;
			if (rids[0] == 0)
				found = 1;
			else {
				for (k=0; k < sizeof(rids); k++) {
					if (sid2rid(g) == rids[k]) {
						found = 1;
						break;
					}
				}
			}

			if (found) {
				grp[j] = g;

				strcpy(c_data_[j], group);

				j++;
			} else {
				LocalFree(g);
			}

		}
		NetApiBufferFree(groups);
		groups = NULL;
	}
	cache_data(__func__, user, (char *)c_data_, j, GNLEN);

	return (j);
}

/* Returns 1 if gname matches one of the SIDS in gidlist[len]; 0 otherwise */
int
inGroups(char *gname, SID *gidlist[], int len)
{

	int	i, ret;
	char *gname2;

	ret = 0;
	for (i=0; i < len; i++) {
		gname2 = getgrpname_full(gidlist[i]);
		if (gname2 == NULL)
			gname2 = getusername(gidlist[i]);

		if (strcmp(gname, gname2) == 0) {
			ret = 1;
			break;
		}
	}
	(void)free(gname2);
	return (ret);
}

/** @fn default_local_homedir
 * @brief       return the default local HomeDirectory of a 'username'.
 *
 * @param[in]   username - the owning user of the home directory.
 * @param[in]   usertoken - the security token of 'username',
 *			    to help determine home directory info.
 * @param[in]	ret_profile_path - set to 1 if requesting for the user's
 *			     profile path to be returned; 0 otherwise.
 *
 * @return      string
 *
 *		If 'ret_profile_path' is 1, then return the user's profile
 *		path: example: C:\Documents and Settings\<username>.
 *		If 'ret_profile_path' is 0, then return the default local
 *		home directory under PBS:
 *			example:
 *		       C:\Documents and Settings\<username>\My Documents\PBS Pro
 *
 * @par MT-Safe:        no
 * @par Side Effects:
 *      None
 *
 * @par Note:
 * 	Returns the default local HomeDirectory  of  'username' whose
 * 	security token is given by 'usertoken'.
 */
char *
default_local_homedir(char *username, HANDLE usertoken, int ret_profile_path)
{
	static  char 	homestr[MAXPATHLEN+1] = {'\0'};
	char		profilepath[MAXPATHLEN+1] = {'\0'};
	char		personal_path[MAX_PATH] = {'\0'};
	char		logb[LOG_BUF_SIZE] = {'\0' } ;
	DWORD		profsz;
	HANDLE		userlogin;
	int		became_admin = 0;
	int		token_created_here = 0;
	PROFILEINFO	pi;
	HANDLE		ht = NULL;

	pi.dwSize = sizeof(PROFILEINFO);
	pi.dwFlags = PI_NOUI;
	pi.lpUserName = username;
	pi.lpProfilePath = NULL;
	pi.lpDefaultPath = NULL;
	pi.lpServerName = NULL;
	pi.lpPolicyPath = NULL;
	pi.hProfile = INVALID_HANDLE_VALUE;

	userlogin = usertoken;
	strcpy(homestr, "");

	if (strcmpi(getlogin(), username) == 0) {
		/* temporarily revert to ADMIN to do system stuff like */
		/* LoadUserProfile() or LogonUserNoPass() */
		(void)revert_impersonated_user();
		became_admin = 1;
	}

	if (userlogin == INVALID_HANDLE_VALUE) {
		if (strcmpi(getlogin(), username) == 0) {
			/* temporarily revert to ADMIN to do system stuff like */
			/* LoadUserProfile() or LogonUserNoPass() */
			if (! OpenProcessToken(GetCurrentProcess(),
				TOKEN_ADJUST_PRIVILEGES|TOKEN_QUERY, &ht)) {
				sprintf(logb,"OpenProcessToken error : %d", GetLastError);
				log_err(-1, "default_local_homedir", logb);
				return NULL;
			}
			userlogin = ht;
		} else {
			userlogin = LogonUserNoPass(username);
		}
		token_created_here = 1;
	}

	/* if none exists */
	profsz = MAXPATHLEN+1;
	profilepath[0] = '\0';
	if (GetUserProfileDirectory(userlogin, profilepath,
		&profsz) == 0) {
		if (LoadUserProfile(userlogin, &pi) == 0)
			goto default_local_homedir_end;

		if (GetUserProfileDirectory(userlogin, profilepath,
			&profsz) == 0)
			goto default_local_homedir_end;
	}

	if (ret_profile_path) {
		strncpy(homestr, profilepath, MAXPATHLEN);
		goto default_local_homedir_end;
	}

	/* For internationalization, obtain "[PROFILE_PATH]\My Documents" */
	/* to formulate default "[PROFILE PATH]\My Documents\PBS Pro" dir */
	/* via a function call. */
	/* "My Documents" in Portuguese is actually "Meu Documentos" */

	strcpy(personal_path, "");
	SHGetFolderPath(NULL, CSIDL_PERSONAL, userlogin,
		SHGFP_TYPE_DEFAULT, personal_path);

	sprintf(homestr, "%s\\PBS Pro", personal_path);


	default_local_homedir_end:

	if (userlogin != INVALID_HANDLE_VALUE) {
		if (pi.hProfile != INVALID_HANDLE_VALUE)
			UnloadUserProfile(userlogin, pi.hProfile);

		if (token_created_here)
			CloseHandle(userlogin);

		/* The following must be done last */
		if (became_admin)
			(void)impersonate_user(userlogin);
	}

	return (homestr);
}

/* Given a path, if it is of the form, "\\computer_name\share_name" (UNC path),
 then map to a local drive using 'pw' for authentication. If
 unable to map or access the drive, then return a local path alternative for
 the user.  if path is not in UNC format, then return path as is.
 The returned string is in  a static area.
 /* this must be run under user (pw->pw_userlogin).
 */

char *
map_unc_path(char *path, struct passwd *pw)
{

	DWORD       ret;
	NETRESOURCE nr;
	static char local_drive[MAXPATHLEN+1] = {'\0'};
	int	    lsize = MAXPATHLEN+1;

	strcpy(local_drive, "");
	if (path == NULL)
		return (local_drive);

	if (strstr(path, "\\\\") == NULL) /* not a unc path */
		return (path);

	/* a unc path */
	nr.lpLocalName  = NULL;
	nr.lpRemoteName = (char *) malloc(lsize);
	if (nr.lpRemoteName == NULL) {
		fprintf(stderr, "Unable to allocate memory!");
		return (local_drive);
	}
	nr.dwType = RESOURCETYPE_DISK;
	strncpy(nr.lpRemoteName, path, lsize);
	nr.lpProvider = NULL;


	/* No need to pass pw->pw_name and pw->pw_passwd when mapping. */
	/* - a consequence of running PBS under SERVICE_ACCOUNT */
	ret= WNetUseConnection(NULL,
		&nr,  //connection details
		NULL,
		NULL,
		CONNECT_REDIRECT,
		local_drive,
		&lsize,
		0
		);

	if (nr.lpRemoteName)
		(void)free(nr.lpRemoteName);

	if (ret != 0) { /* unc path failed to map */

		strncpy(local_drive,
			default_local_homedir(pw->pw_name, pw->pw_userlogin, 0),
			MAXPATHLEN+1);
		return (local_drive);
	}

	return (local_drive);
}

/* @fn			is_network_drive_path
 * @brief       Does the path contain network mapped drive?
 *
 * @param[in]   path - given path
 * @return      int
 * @retval		1 if path contains a network mapped drive
 *				0 otherwise
 */
int
is_network_drive_path(char *path)
{
	char drive_path[NETWORK_DRIVE_PATHLEN] = {'\0'};

	if (path == NULL || path[0] == '\0')
		return 0;

	if (path[1] != ':')
		return 0;

	snprintf(drive_path, NETWORK_DRIVE_PATHLEN - 1, "%s\\", path);

	if(GetDriveType(drive_path) == DRIVE_REMOTE)
		return 1;
	else
		return 0;
}

void
unmap_unc_path(char *path)
{
	if (path == NULL || path[0] == '\0')
		return;

	if (path[strlen(path)-1] != ':')
		return;

	WNetCancelConnection2(path, CONNECT_UPDATE_PROFILE, TRUE);
}


/*
 * Returns the home directory of user as returned by NetUserGetInfo().
 * NULL is returned if none was explicitly assigned.
 * The return value to this function must be freed!
 *
 * NOTE: Returned value is CACHED.
 */
static char *
getAssignedHomeDirectory(char *user)
{
	USER_INFO_1	*uinfo = NULL;

	wchar_t userw[UNLEN+1];
	char	*homedir = NULL;
	char	*sysdrv = NULL;
	int	len;
	char	realuser[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'}; /* dom\user0 */
	wchar_t	realuserw[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'}; /* dom\user0 */
	SID_NAME_USE sid_type;
	SID	*sid = NULL;
	char	*p;
	char	dn[PBS_MAXHOSTNAME+1] = "";
	char	dname[PBS_MAXHOSTNAME+1] = "";
	wchar_t	dnamew[PBS_MAXHOSTNAME+1] = L"";
	LPWSTR	dcw = NULL;

	char	*c_data = NULL;
	char	c_data_[1][CACHE_STR_SIZE] = {0};

	if (user == NULL)
		return NULL;

	c_data = find_cache_data(__func__, user);
	if (c_data != NULL) {
		if (c_data[0] == '\0') {
			return NULL;
		}
		return (strdup(c_data)); /* malloced value expected as return */
	}

	sid = get_full_username(user, realuser, &sid_type);

	mbstowcs(userw, user, UNLEN);
	mbstowcs(realuserw, realuser, UNLEN);

	if (sid) LocalFree(sid);

	/* check if user is a domain user  and that local computer is */
	/* part of a domain */
	if( (p=strrchr(realuser, '\\')) && \
			(GetComputerDomainName(dn) == 1) ) {
		*p = '\0';
		strcpy(dname, realuser);
		*p = '\\';
		mbstowcs(dnamew, dname, PBS_MAXHOSTNAME);

		NetGetDCName(NULL, dnamew, (LPBYTE *)&dcw);
	}

	if ((wrap_NetUserGetInfo(0, realuserw, 1,
	(LPBYTE *)&uinfo) == NERR_Success) || \
	    (dcw && \
	    	(wrap_NetUserGetInfo(dcw, userw, 1,
	(LPBYTE *)&uinfo) == NERR_Success)) || \
	    (wrap_NetUserGetInfo(0, userw, 1, (LPBYTE *)&uinfo) == NERR_Success)) {
		if (uinfo->usri1_home_dir) {
			len = wcslen(uinfo->usri1_home_dir);

			if (len > 0) {

				homedir = (char *)malloc(len+1);

				if (homedir == NULL) {
					NetApiBufferFree(uinfo);
					if (dcw) NetApiBufferFree(dcw);

					c_data_[0][0] = '\0';
					cache_data(__func__, user, (char *)c_data_,
						1, CACHE_STR_SIZE);

					return NULL;
				}
				wcstombs(homedir, uinfo->usri1_home_dir, len);
				NetApiBufferFree(uinfo);
				if (dcw) NetApiBufferFree(dcw);

				if (strlen(homedir) < CACHE_STR_SIZE) {
					strcpy(c_data_[0], homedir);
					cache_data(__func__, user, (char *)c_data_,
						1, CACHE_STR_SIZE);
				}

				return (homedir);
			}
		}

		NetApiBufferFree(uinfo);
	}

	if (dcw) NetApiBufferFree(dcw);

	if (homedir == NULL) {
		c_data_[0][0] = '\0';
		cache_data(__func__, user, (char *)c_data_, 1, CACHE_STR_SIZE);
	} else if (strlen(homedir) < CACHE_STR_SIZE) {
		strcpy(c_data_[0], homedir);
		cache_data(__func__, user, (char *)c_data_, 1, CACHE_STR_SIZE);
	}

	return (homedir);
}

/* Returns the directory of user that will be used by PBS for job output  */
/* files, and resolving relative pathnames during file transfer requests. */
/* This may return a homedir that does not exist yet which should be created */
/* under the security context of the user!				   */
/*									   */
/* The Algorithm is as follows:						   */
/* 	if [HOME DIRECTORY] is set, use it.                                */
/*      else                                                               */
/*          use [PROFILE PATH]\My Documents\PBS Pro                        */
/*									   */
/* NOTE: The returned path may not exist yet, so better to pass result to  */
/*        CreateDirectory() under user context.                            */
/* The return value to this function must be freed! 			   */
char *
getHomedir(char *user)
{

	char	*homedir = NULL;
	HANDLE	userlogin = INVALID_HANDLE_VALUE;
	int	i;
	struct passwd *pwdp = NULL;


	homedir = getAssignedHomeDirectory(user);

	if (homedir)
		return (homedir);

	if (passwd_cache_init == 0) {
		CLEAR_HEAD(passwd_cache_ll);
		passwd_cache_init = 1;
	}

	/* look for a user login handle */
	for (pwdp = (struct passwd*) GET_NEXT(passwd_cache_ll);
		pwdp; pwdp = (struct passwd*) GET_NEXT(pwdp->pw_allpasswds)) {
		if (strcmp(pwdp->pw_name, user) == 0) {
			userlogin = pwdp->pw_userlogin;
			break;
		}
	}
	homedir = strdup(default_local_homedir(user, userlogin, 0));
	return (homedir);
}

/* Returns the user's .rhosts file path					*/
/* The username and user logon handle must be given as input.           */
/* 									*/
/* Algorithm:								*/
/*									*/
/*	if [HOME DIRECTORY]\.rhosts exists, returns it.			*/
/*	else if [PROFILE PATH]\.rhosts exists, returns it.		*/
/*	else no .rhosts file. (return "")				*/
/*									*/
/* NOTE: Please call this function under the user's security context.   */

char *
getRhostsFile(char *user, HANDLE userlogin)
{

	struct  stat sbuf;
	static char rhosts_file[MAXPATHLEN+1] = {'\0'};
	char	*homedir = NULL;
	char	profilepath[MAXPATHLEN+1] = {'\0'};


	homedir = getAssignedHomeDirectory(user);

	if (homedir) {
		sprintf(rhosts_file, "%s\\.rhosts", homedir);
		(void)free(homedir);
		homedir = NULL;

		if (lstat(rhosts_file, &sbuf) == 0)
			return (rhosts_file);
	}

	/* Let's call default_local_homedir() to force */
	/* creation of [PROFILE PATH] if it doesn't exist. */

	strncpy(profilepath, default_local_homedir(user, userlogin, 1), MAXPATHLEN);

	sprintf(rhosts_file, "%s\\.rhosts", profilepath);

	if (lstat(rhosts_file, &sbuf) == 0)
		return (rhosts_file);

	return ("");
}

/* returns 1 if privname is enabled for current process; otherwise, returns
 0. */
int
has_privilege(char *privname)
{
	LUID	luid;
	HANDLE	procToken = INVALID_HANDLE_VALUE;
	TOKEN_PRIVILEGES *toke = NULL;
	int 	tokelen;
	int	i;
	int	stat = 0;

	if (!LookupPrivilegeValue(NULL, privname, &luid)) {
		goto has_privilege_end;
	}

	if (!OpenProcessToken(GetCurrentProcess(),
		TOKEN_QUERY|TOKEN_ADJUST_PRIVILEGES, &procToken)) {
		goto has_privilege_end;
	}
	GetTokenInformation(procToken, TokenPrivileges, toke, 0, &tokelen);

	toke = (TOKEN_PRIVILEGES *)malloc(tokelen);
	if (toke == NULL) {
		goto has_privilege_end;
	}
	GetTokenInformation(procToken, TokenPrivileges, toke, tokelen,
		&tokelen);
	for (i=0; i< (int)toke->PrivilegeCount; i++) {
		if (memcmp(&toke->Privileges[i].Luid, &luid,
			sizeof(LUID)) == 0) {
			toke->Privileges[i].Attributes |= SE_PRIVILEGE_ENABLED;
			break;
		}
	}

	if (i == (int)toke->PrivilegeCount) {
		goto has_privilege_end;
	}

	if (!AdjustTokenPrivileges(procToken, FALSE, toke, 0, NULL, 0)) {
		goto has_privilege_end;
	}
	stat = 1;

has_privilege_end:
	if (procToken != INVALID_HANDLE_VALUE) {
		CloseHandle(procToken);
	}
	if (toke) {
		(void)free(toke);
	}
	return (stat);
}

/* returns 1 if privname has been enabled for current process; otherwise, 0. */
int
ena_privilege(char *privname)
{
	LUID	luid;
	HANDLE	procToken = INVALID_HANDLE_VALUE;
	TOKEN_PRIVILEGES toke;
	int	stat = 0;

	if (!LookupPrivilegeValue(NULL, privname, &luid)) {
		goto ena_privilege_end;
	}

	if (!OpenProcessToken(GetCurrentProcess(),
		TOKEN_QUERY|TOKEN_ADJUST_PRIVILEGES, &procToken)) {
		goto ena_privilege_end;
	}

	toke.PrivilegeCount = 1;
	toke.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;
	toke.Privileges[0].Luid = luid;

	if (!AdjustTokenPrivileges(procToken, FALSE, &toke, 0, NULL, 0)) {
		goto ena_privilege_end;
	}
	stat = 1;

ena_privilege_end:
	if (procToken != INVALID_HANDLE_VALUE) {
		CloseHandle(procToken);
	}
	return (stat);
}

/* restrict security access to to specified groups on 'list'. */
/* This will make sure that SE_TAKE_OWNERSHIP_NAME and SE_RESTORE_NAME */
/* privileges is enabled in current process. */
/* Returns 0 upon success; -1 on fail */
int
setgroups(int size, SID *grp[])
{

	HANDLE	htok, htok2, ntok;
	SID_AND_ATTRIBUTES	groups[_MAX_GROUPS+1];
	int i;

	(void)ena_privilege(SE_TAKE_OWNERSHIP_NAME);
	(void)ena_privilege(SE_RESTORE_NAME);

	if (size == 0)
		return (-1);

	for (i=0; (i < size) && (i < _MAX_GROUPS); i++) {
		groups[i].Sid = grp[i];
		groups[i].Attributes = 0;
	}

	/* get the process token */
	if (OpenProcessToken(GetCurrentProcess(), TOKEN_ALL_ACCESS, &htok) == 0) {
		return (-1);
	}

	/* convert process token to impersonation token */
	if (DuplicateTokenEx(htok, TOKEN_ALL_ACCESS, 0, DEFAULT_IMPERSONATION_LEVEL,
		TokenImpersonation, &htok2) == 0) {
		return (-1);
	}

	if (CreateRestrictedToken(htok2, 0, 0, NULL, 0, NULL, i, groups, &ntok) == 0) {
		return (-1);
	}
	/* attach the impersonation token to thread (not process token!) */
	if (SetThreadToken(0, ntok) == 0) {
		return (-1);
	}

	return (0);
}


/* return a TOKEN_GROUPS representing the groups to which 'user' is a member
 of. Specify 'attrib' for every group added.
 NOTE: The TOKEN_GROUPS structure returned by this call must be freed, as
 well as each SID appearing on the list must be LocalFree()d. */
static TOKEN_GROUPS *
create_token_groups(char *user, DWORD attrib)
{
	DWORD	rids[1];
	SID	*gids[_MAX_GROUPS];
	int	i, n;
	int	len;
	TOKEN_GROUPS *token_groups = NULL;

	rids[0] = 0;

	n = getgids(user, gids, rids);
	if (n <= 0)
		return NULL;

	len = sizeof(TOKEN_GROUPS) + \
			((n-ANYSIZE_ARRAY)*sizeof(SID_AND_ATTRIBUTES));

	token_groups = (TOKEN_GROUPS *)malloc(len);
	if (token_groups == NULL)
		return NULL;

	token_groups->GroupCount = n;

	for (i=0; i < n; i++) {
		token_groups->Groups[i].Attributes = attrib;
		token_groups->Groups[i].Sid=gids[i];
	}
	return (token_groups);
}

/* add_token_groups: can add a 'grpname' or 'grpsid' to the list of groups.
 If grpname is NULL then it uses 'grpsid'. If both arguments are NULL, then
 nothing happens. */
static TOKEN_GROUPS *
add_token_groups(TOKEN_GROUPS *token_groups,
	char *grpname,
	SID *grpsid,
	DWORD attrib)
{
	SID	*sid;
	int	len, n;
	TOKEN_GROUPS *tg;
	int	newtoken  =  0;	/* if 1, means creates new token */

	if (token_groups == NULL)
		newtoken = 1;

	if (grpname != NULL) {
		if ((sid=getgrpsid(grpname)) == NULL) {
			if ((sid=getusersid(grpname)) == NULL) {
				return (token_groups);	/* no change */
			}
		}
	} else {
		sid = grpsid;
		if (sid == NULL) {
			return (token_groups);	/* no change */
		}
	}
	len = sizeof(TOKEN_GROUPS) + \
	   (( (token_groups?token_groups->GroupCount:0) - ANYSIZE_ARRAY + 1)*sizeof(SID_AND_ATTRIBUTES));

	if ((tg=(TOKEN_GROUPS *)realloc((TOKEN_GROUPS *)token_groups,
		len)) == NULL) {
		return (token_groups);	/* no change */
	} else {
		token_groups = tg;
	}

	if (newtoken)
		token_groups->GroupCount = 1;
	else
		token_groups->GroupCount++;

	n = token_groups->GroupCount;

	token_groups->Groups[n-1].Attributes =  attrib;
	token_groups->Groups[n-1].Sid =  sid;

	return (token_groups);
}

static void
free_token_groups(TOKEN_GROUPS *token_groups)
{
	int	i;

	for (i=0; i < (int)token_groups->GroupCount; i++) {
		if (token_groups->Groups[i].Sid) {
			LocalFree(token_groups->Groups[i].Sid);
		}
	}
	(void)free(token_groups);
}

static void
print_token_groups(TOKEN_GROUPS *token_groups)
{
	int	i;
	char	*gname = NULL;
	char	buf[80] = {'\0'};
	char	logb[LOG_BUF_SIZE] = {'\0' } ;

	strcpy(logb, "");
	for (i=0; i < (int)token_groups->GroupCount; i++) {
		gname = getgrpname(token_groups->Groups[i].Sid);
		if (gname == NULL)
			gname = getusername(token_groups->Groups[i].Sid);
		if (gname == NULL) {
			sprintf(buf, "<sid=%d>", token_groups->Groups[i].Sid);
			gname = (char *)buf;
		}

		strcat(logb, gname);
		strcat(logb, " ");

		(void)free(gname);
	}
	sprintf(logb,"print_token_groups: %s", logb);
	log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG,PBS_EVENTCLASS_FILE, LOG_NOTICE, "", logb);
}


/* return value must be FreeSid() */
static SID *
luid2sid(LUID luid)
{
	SID	*sid;
	SID_IDENTIFIER_AUTHORITY nt_auth = SECURITY_NT_AUTHORITY;

	AllocateAndInitializeSid(&nt_auth, 3, SECURITY_LOGON_IDS_RID,
		luid.HighPart, luid.LowPart, 0, 0, 0, 0, 0, &sid);

	return (sid);
}

/* Load current user rights and return a TOKEN_PRIVILEGES structure. This
 structure mst later be freed if not needed anymore. */
static TOKEN_PRIVILEGES *
create_token_privs_byuser(SID *usid, DWORD attrib, HANDLE hLsa)
{
	TOKEN_PRIVILEGES *token_privs = NULL;
	LSA_UNICODE_STRING *lsaRights = NULL;
	ULONG numRights = 0;
	int	len, i;
	char privname[GNLEN+1] = {'\0'};

	if (hLsa == INVALID_HANDLE_VALUE || usid == NULL)
		return NULL;

	/* get user rights and add to list of user token privileges */
	LsaEnumerateAccountRights(hLsa, usid, &lsaRights, &numRights);

	len = sizeof(TOKEN_PRIVILEGES) + \
		((numRights-ANYSIZE_ARRAY)*sizeof(LUID_AND_ATTRIBUTES));

	token_privs = (TOKEN_PRIVILEGES *)malloc(len);

	if (token_privs == NULL)
		return NULL;

	token_privs->PrivilegeCount = numRights;

	for (i=0; i< (int)numRights; i++) {
		token_privs->Privileges[i].Attributes = attrib;
		wcstombs(privname, lsaRights[i].Buffer, sizeof(privname));
		LookupPrivilegeValue(NULL, privname,
			&token_privs->Privileges[i].Luid);
	}

	LsaFreeMemory(lsaRights);

	return (token_privs);
}

static TOKEN_PRIVILEGES *
create_token_privs_bygroups(TOKEN_GROUPS *token_groups, DWORD attrib, HANDLE hLsa)
{
	TOKEN_PRIVILEGES *token_privs = NULL;
	TOKEN_PRIVILEGES *tp = NULL;
	LSA_UNICODE_STRING *lsaRights = NULL;
	ULONG numRights = 0;
	int	len, i, j, k;
	char privname[GNLEN+1] = {'\0'};
	LUID	luid;
	BOOL	found_match;

	if (hLsa == INVALID_HANDLE_VALUE)
		return NULL;

	len = sizeof(TOKEN_PRIVILEGES) - \
		(ANYSIZE_ARRAY*sizeof(LUID_AND_ATTRIBUTES));
	token_privs = (TOKEN_PRIVILEGES *)malloc(len);

	if (token_privs == NULL)
		return NULL;

	token_privs->PrivilegeCount = 0;
	for (i=0; i < (int)token_groups->GroupCount; i++) {

		if (LsaEnumerateAccountRights(hLsa,
			token_groups->Groups[i].Sid,
			(LSA_UNICODE_STRING **)&lsaRights, &numRights) != ERROR_SUCCESS)
			continue;

		len += sizeof(LUID_AND_ATTRIBUTES)*numRights;

		tp = realloc(token_privs, len);
		if (tp == NULL)	/* couldn't realloc! */
			return (token_privs);
		else
			token_privs = tp;

		for (j=0; j < (int)numRights; j++) {
			wcstombs(privname, lsaRights[j].Buffer,
				sizeof(privname));
			LookupPrivilegeValue(NULL, privname, &luid);
			/* check to see if this luid already in list */
			found_match = FALSE;
			for (k=0; k < (int)token_privs->PrivilegeCount; k++) {
				if (memcmp(&luid,
					&token_privs->Privileges[k].Luid,
					sizeof(luid)) == 0) {
					found_match = TRUE;
					break;
				}
			}
			if (!found_match) {
				token_privs->Privileges[token_privs->PrivilegeCount].Attributes = attrib;
				token_privs->Privileges[token_privs->PrivilegeCount].Luid = luid;
				token_privs->PrivilegeCount++;
			}

		}
		LsaFreeMemory(lsaRights);
	}
	len = sizeof(TOKEN_PRIVILEGES) + \
		((token_privs->PrivilegeCount - \
			ANYSIZE_ARRAY)*sizeof(LUID_AND_ATTRIBUTES));

	tp = (TOKEN_PRIVILEGES *)realloc(token_privs, len);
	if (tp)
		token_privs = tp;

	return (token_privs);

}

static TOKEN_PRIVILEGES *
merge_token_privs(TOKEN_PRIVILEGES *token_privs1, TOKEN_PRIVILEGES *token_privs2)
{
	TOKEN_PRIVILEGES *token_privs = NULL;
	TOKEN_PRIVILEGES *tp = NULL;

	int	len, i, j;
	BOOL	found_match;

	if (token_privs1 == NULL || token_privs2 == NULL) {
		return NULL;
	}

	len = sizeof(TOKEN_PRIVILEGES) + \
		((token_privs1->PrivilegeCount + \
		 token_privs2->PrivilegeCount - \
		 ANYSIZE_ARRAY)*sizeof(LUID_AND_ATTRIBUTES));

	token_privs = (TOKEN_PRIVILEGES *)malloc(len);
	if (token_privs == NULL)
		return NULL;
	token_privs->PrivilegeCount = token_privs1->PrivilegeCount;

	for (i=0; i < (int)token_privs->PrivilegeCount; i++) {
		token_privs->Privileges[i].Attributes = \
			token_privs1->Privileges[i].Attributes;
		token_privs->Privileges[i].Luid = \
			token_privs1->Privileges[i].Luid;
	}

	for (j=0; j < (int)token_privs2->PrivilegeCount; j++) {
		found_match = FALSE;
		for (i=0; i < (int)token_privs->PrivilegeCount; i++) {
			if (memcmp(&token_privs2->Privileges[j].Luid,
				&token_privs->Privileges[i].Luid,
				sizeof(LUID)) == 0) {
				found_match = TRUE;
				break;
			}
		}
		if (!found_match) {
			token_privs->Privileges[token_privs->PrivilegeCount].Attributes = token_privs2->Privileges[j].Attributes;
			token_privs->Privileges[token_privs->PrivilegeCount].Luid = token_privs2->Privileges[j].Luid;
			token_privs->PrivilegeCount++;
		}
	}

	len = sizeof(TOKEN_PRIVILEGES) + \
		((token_privs->PrivilegeCount - ANYSIZE_ARRAY)*sizeof(LUID_AND_ATTRIBUTES));
	tp = (TOKEN_PRIVILEGES *)realloc(token_privs, len);
	if (tp)
		token_privs = tp;

	return (token_privs);

}

static void
print_token_privs(TOKEN_PRIVILEGES *token_privs)
{
	int i;
	LUID luid;
	DWORD cb;
	char  buf[512] = {'\0'};
	char  buf2[512] = {'\0'};
	char  logb[LOG_BUF_SIZE] = {'\0' } ;

	if (token_privs == NULL)
		return;

	strcpy(logb, "");
	for (i=0; i < (int)token_privs->PrivilegeCount; i++) {
		luid = token_privs->Privileges[i].Luid;
		cb = sizeof(buf);
		if (LookupPrivilegeName(NULL, &luid, buf, &cb) == 0) {
			sprintf(logb, "lookup for %d failed", luid);
			log_err(-1, "print_token_privs", logb);
			continue;
		}

		sprintf(buf2, "(%s[%d] =", buf, luid);
		strcat(buf2, ")");
		sprintf(logb,"print_token_privs: %s", buf2);
		log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", logb);
		strcat(logb, buf2);
		strcat(logb, " ");
	}
	strcat(logb, "<END>");

	sprintf(logb,"print_token_privs: %s", logb);
	log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", logb);
}

static TOKEN_SOURCE *
create_token_source(char *name)
{
	TOKEN_SOURCE	*token_source;

	if (name == NULL)
		return NULL;

	token_source = (TOKEN_SOURCE *)malloc(sizeof(TOKEN_SOURCE));
	if (token_source == NULL)
		return NULL;

	memset(token_source, 0, sizeof(TOKEN_SOURCE));
	strcpy(token_source->SourceName, name);
	token_source->SourceIdentifier.HighPart = 0;
	token_source->SourceIdentifier.LowPart = 0x0101;
	return (token_source);
}


static ACL *
create_default_dacl(SID *usid, TOKEN_GROUPS *token_groups)
{
	int	i;
	DWORD	rid;
	int     cbAcl, cbAce;
	ACL     *ndacl;
	SID	*ssid;

	cbAcl = sizeof(ACL);

	for (i=0; i < (int)token_groups->GroupCount; i++) {
		rid = sid2rid(token_groups->Groups[i].Sid);
		if( rid == DOMAIN_ALIAS_RID_ADMINS || \
		    rid == DOMAIN_GROUP_RID_ADMINS ) {
			/* subract ACE.SidStart from the size */
			cbAce = sizeof(ACCESS_ALLOWED_ACE) - sizeof(DWORD);
			/* add this ACE's SID length */
			cbAce += GetLengthSid(token_groups->Groups[i].Sid);
			/* add the length of each ACE to the total ACL length */
			cbAcl += cbAce;
		}

	}

	/* add 2 extra entries for 'usid' and SYSTEM sid */
	cbAce = sizeof(ACCESS_ALLOWED_ACE) - sizeof(DWORD);
	cbAce += GetLengthSid(usid);
	cbAcl += cbAce;

	cbAce = sizeof(ACCESS_ALLOWED_ACE) - sizeof(DWORD);
	ssid = getusersid("SYSTEM");
	if (ssid == NULL)
		return NULL;

	cbAce += GetLengthSid(ssid);
	cbAcl += cbAce;

	ndacl = (ACL *)malloc(cbAcl);
	if (ndacl == NULL)
		return NULL;

	InitializeAcl(ndacl, cbAcl, ACL_REVISION);
	for (i=0; i < (int)token_groups->GroupCount; i++) {
		rid = sid2rid(token_groups->Groups[i].Sid);
		if( rid == DOMAIN_ALIAS_RID_ADMINS || \
		    rid == DOMAIN_GROUP_RID_ADMINS ) {

			if (AddAccessAllowedAce(ndacl, ACL_REVISION,
				SPECIFIC_RIGHTS_ALL|STANDARD_RIGHTS_ALL,
				token_groups->Groups[i].Sid) == 0) {
				(void)free(ndacl);
				return NULL;

			}
		}
	}
	if (AddAccessAllowedAce(ndacl, ACL_REVISION,
		SPECIFIC_RIGHTS_ALL|STANDARD_RIGHTS_ALL, usid) == 0) {
		(void)free(ndacl);
		return NULL;
	}

	if (AddAccessAllowedAce(ndacl, ACL_REVISION,
		SPECIFIC_RIGHTS_ALL|STANDARD_RIGHTS_ALL, ssid) == 0) {
		(void)free(ndacl);
		return NULL;
	}

	return (ndacl);
}


static ACL *
create_dacl(SID *usid, TOKEN_GROUPS *token_groups)
{
	int	i;
	int     cbAcl, cbAce;
	ACL     *ndacl;
	SID	*ssid;

	cbAcl = sizeof(ACL);

	for (i=0; i < (int)token_groups->GroupCount; i++) {
		/* subract ACE.SidStart from the size */
		cbAce = sizeof(ACCESS_ALLOWED_ACE) - sizeof(DWORD);
		/* add this ACE's SID length */
		cbAce += GetLengthSid(token_groups->Groups[i].Sid);
		/* add the length of each ACE to the total ACL length */
		cbAcl += cbAce;
	}

	/* add 2 extra entries for 'usid' and SYSTEM sid */
	cbAce = sizeof(ACCESS_ALLOWED_ACE) - sizeof(DWORD);
	cbAce += GetLengthSid(usid);
	cbAcl += cbAce;

	cbAce = sizeof(ACCESS_ALLOWED_ACE) - sizeof(DWORD);
	ssid = getusersid("SYSTEM");
	if (ssid == NULL)
		return NULL;

	cbAce += GetLengthSid(ssid);
	cbAcl += cbAce;

	ndacl = (ACL *)malloc(cbAcl);
	if (ndacl == NULL)
		return NULL;

	InitializeAcl(ndacl, cbAcl, ACL_REVISION);
	for (i=0; i < (int)token_groups->GroupCount; i++) {
		if (AddAccessAllowedAce(ndacl, ACL_REVISION,
			SPECIFIC_RIGHTS_ALL|STANDARD_RIGHTS_ALL,
			token_groups->Groups[i].Sid) == 0) {
			(void)free(ndacl);
			return NULL;
		}
	}
	if (AddAccessAllowedAce(ndacl, ACL_REVISION,
		SPECIFIC_RIGHTS_ALL|STANDARD_RIGHTS_ALL, usid) == 0) {
		(void)free(ndacl);
		return NULL;
	}

	if (AddAccessAllowedAce(ndacl, ACL_REVISION,
		SPECIFIC_RIGHTS_ALL|STANDARD_RIGHTS_ALL, ssid) == 0) {
		(void)free(ndacl);
		return NULL;
	}

	return (ndacl);
}

/* print_dacl: returns as a string the list of entries in 'pdacl'.
 Return value must be freed! */
static char *
print_dacl(ACL *pdacl)
{
	ACL_SIZE_INFORMATION    sizeInfo;
	ACCESS_ALLOWED_ACE      *pace;
	int                     i;
	char			bigbuf[1024] = {'\0'};
	char			buf2[80] = {'\0'};
	char			*secname;

	GetAclInformation(pdacl, &sizeInfo, sizeof(sizeInfo), AclSizeInformation);
	strcpy(bigbuf, "");
	for (i=0; i < (int)sizeInfo.AceCount; i++) {
		GetAce(pdacl, i, (void **)&pace);
		secname = getgrpname_full((SID*)&pace->SidStart);
		if (secname == NULL)
			secname = getusername((SID*)&pace->SidStart);
		if (secname == NULL)
			continue;

		if (pace->Header.AceType == ACCESS_ALLOWED_ACE_TYPE) {
			sprintf(buf2, "<ALLOW %s privilege=%d>", secname,
				(pace->Mask & 0xFFFF));
		} else if (pace->Header.AceType == ACCESS_DENIED_ACE_TYPE) {
			sprintf(buf2, "<DENY %s privilege=%d>", secname,
				(pace->Mask & 0xFFFF));
		}
		strcat(bigbuf, buf2);
		strcat(bigbuf, " ");
		(void)free(secname);
	}
	strcat(bigbuf, "<END>");
	return (strdup(bigbuf));
}

/* get_token_info: if token is INVALID_HANDLE_VALUE, then determines the
 security token of the current thread or current process */
void
get_token_info(HANDLE token,
	char **user,
	char **owner,
	char **prigrp,
	char **altgrps,
	char **privs,
	char **dacl,
	char **source,
	char **type)
{
	char logb[LOG_BUF_SIZE] = {'\0' } ;
	char *buf = NULL;
	int cb = sizeof(buf);

	cb = 0;

	if (token == INVALID_HANDLE_VALUE) {

		if (OpenThreadToken(GetCurrentThread(), TOKEN_ALL_ACCESS,
			TRUE, &token)  == 0)
			OpenProcessToken(GetCurrentProcess(), TOKEN_ALL_ACCESS,
				&token);

	}

	if (GetTokenInformation(token, TokenUser, buf, cb, &cb)) {
		log_err(-1, "get_token_info", "User: 1st GetTokenInformation failed!");
		return;
	} else {

		buf = (char *) malloc(cb);
		if (buf == NULL) {
			fprintf(stderr, "Unable to allocate memory!\n");
			return;
		}
		if (GetTokenInformation(token, TokenUser, buf, cb, &cb)) {

			TOKEN_USER      *ptu = (TOKEN_USER *)buf;

			*user = getusername(ptu->User.Sid);
			free(buf);
		} else {
			sprintf(logb, "GetTokenInformation of Primary token failed with error=%d", GetLastError());
			log_err(-1, "get_token_info", logb);
		}
	}
	cb = 0;
	if (GetTokenInformation(token, TokenOwner, buf, cb, &cb)) {
		log_err(-1, "get_token_info", "Owner: 1st GetTokenInformation failed!");
	} else {

		buf = (char *) malloc(cb);
		if (buf == NULL) {
			fprintf(stderr, "Unable to allocate memory!\n");
			return;
		}
		if (GetTokenInformation(token, TokenOwner, buf, cb, &cb)) {

			TOKEN_OWNER	*ptu = (TOKEN_OWNER *)buf;

			*owner = getusername(ptu->Owner);
			free(buf);
		} else {
			sprintf(logb, "Owner: GetTokenInformation failed with error=%d", GetLastError());
			log_err(-1, "get_token_info", logb);
		}
	}
	cb = 0;
	if (GetTokenInformation(token, TokenPrimaryGroup, buf, cb, &cb)) {
		log_err(-1, "get_token_info", "Group: 1st GetTokenInformation failed!");
	} else {

		buf = (char *) malloc(cb);
		if (buf == NULL) {
			fprintf(stderr, "Unable to allocate memory!\n");
			return;
		}
		if (GetTokenInformation(token, TokenPrimaryGroup, buf, cb, &cb)) {

			TOKEN_PRIMARY_GROUP *ptu = (TOKEN_PRIMARY_GROUP *)buf;

			*prigrp= getgrpname(ptu->PrimaryGroup);
			free(buf);
		} else {
			sprintf(logb, "Group: GetTokenInformation failed with error=%d", GetLastError());
			log_err(-1, "get_token_info", logb);
		}
	}
	cb = 0;
	if (GetTokenInformation(token, TokenGroups, buf, cb, &cb)) {
		log_err(-1, "get_token_info", "Groups: 1st GetTokenInformation failed!");
	} else {
		int l;
		char	bigbuf[512];
		char	*gname;
		buf = (char *) malloc(cb);
		if (buf == NULL) {
			fprintf(stderr, "Unable to allocate memory!\n");
			return;
		}

		if (GetTokenInformation(token, TokenGroups, buf, cb, &cb)) {

			TOKEN_GROUPS *ptu = (TOKEN_GROUPS *)buf;
			sprintf(logb, "get_token_info: # of groups=%d", ptu->GroupCount);
			log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", logb);
			strcpy(bigbuf, "");
			for (l=0; l < (int)ptu->GroupCount; l++) {
				gname = getgrpname(ptu->Groups[l].Sid);
				if (gname == NULL)
					gname = getusername(ptu->Groups[l].Sid);
				if (gname) {
					strcat(bigbuf, gname);
					strcat(bigbuf, " ");
				}
			}
			if ((*altgrps = strdup(bigbuf)) == NULL) {
				free(buf);
				fprintf(stderr, "Unable to allocate memory!\n");
				return;
			}
			free(buf);
		} else {
			sprintf(logb, "Groups: GetTokenInformation failed with error=%d", GetLastError());
			log_err(-1, "get_token_info", logb);
		}
	}

	cb = 0;
	if (GetTokenInformation(token, TokenPrivileges, buf, cb, &cb)) {
		log_err(-1, "get_token_info", "Groups: 1st GetTokenInformation failed!");
	} else {
		int l;
		char	bigbuf[3000];
		char	buf2[1040];
		char	buf3[512];
		char	buf4[80];
		int	cb3;
		LUID	luid;
		DWORD	att;
		buf = (char *) malloc(cb);
		if (buf == NULL) {
			fprintf(stderr, "Unable to allocate memory!\n");
			return;
		}

		if (GetTokenInformation(token, TokenPrivileges, buf, cb, &cb)) {

			TOKEN_PRIVILEGES *ptu = (TOKEN_PRIVILEGES *)buf;
			sprintf(logb, "get_token_info: # of privs=%d", ptu->PrivilegeCount);
			log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", logb);
			strcpy(bigbuf, "");
			for (l=0; l < (int)ptu->PrivilegeCount; l++) {
				cb3 = 512;
				luid = ptu->Privileges[l].Luid;
				if (LookupPrivilegeName(NULL,
					&luid,
					buf3,
					&cb3) == 0) {
					sprintf(logb, "nt_suid: lookup for %d failed", luid);
					log_err(-1, "get_token_info", logb);
					continue;
				}

				sprintf(buf2, "(%s[%d] =", buf3, luid);
				att = ptu->Privileges[l].Attributes;
				if (att & SE_PRIVILEGE_ENABLED_BY_DEFAULT)
					strcat(buf2, "SE_PRIVILEGE_ENABLED_BY_DEFAULT,");
				if (att & SE_PRIVILEGE_ENABLED)
					strcat(buf2, "SE_PRIVILEGE_ENABLED,");

				if (att & SE_PRIVILEGE_USED_FOR_ACCESS)
					strcat(buf2, "SE_USED_FOR_ACCESS,");
				sprintf(buf4, "%d", att);
				strcat(buf2, buf4);
				strcat(buf2, ")");
				strcat(bigbuf, buf2);
				strcat(bigbuf, " ");
			}
			strcat(bigbuf, "<END>");
			if ((*privs = strdup(bigbuf)) == NULL) {
				free(buf);
				fprintf(stderr, "Unable to allocate memory!\n");
				return;
			}
			free(buf);
		} else {
			sprintf(logb, "Privs: GetTokenInformation failed with error=%d", GetLastError());
			log_err(-1, "get_token_info", logb);
		}
	}
	cb = 0;
	if (GetTokenInformation(token, TokenDefaultDacl, buf, cb, &cb)) {
		log_err(-1, "get_token_info", "DACL: 1st GetTokenInformation failed!");
	} else {
		buf = (char *) malloc(cb);
		if (buf == NULL) {
			fprintf(stderr, "Unable to allocate memory!\n");
			return;
		}

		if (GetTokenInformation(token, TokenDefaultDacl, buf, cb, &cb)) {

			TOKEN_DEFAULT_DACL *ptu = (TOKEN_DEFAULT_DACL *)buf;
			*dacl = print_dacl(ptu->DefaultDacl);
			free(buf);
		} else {
			sprintf(logb, "DACL: GetTokenInformation failed with error=%d", GetLastError());
			log_err(-1, "get_token_info", logb);
		}
	}
	cb = 0;
	if (GetTokenInformation(token, TokenSource, buf, cb, &cb)) {
		log_err(-1, "get_token_info", "Source: 1st GetTokenInformation failed!");
	} else {
		buf = (char *) malloc(cb);
		if (buf == NULL) {
			fprintf(stderr, "Unable to allocate memory!\n");
			return;
		}

		if (GetTokenInformation(token, TokenSource, buf, cb, &cb)) {

			TOKEN_SOURCE *ptu = (TOKEN_SOURCE *)buf;
			if ((*source = strdup(ptu->SourceName)) == NULL) {
				fprintf(stderr, "Unable to allocate memory!\n");
				free(buf);
				return;
			}
			free(buf);
		} else {
			sprintf(logb, "Source: GetTokenInformation failed with error=%d", GetLastError());
			log_err(-1, "get_token_info", logb);
		}
	}
	cb = 0;
	if (GetTokenInformation(token, TokenType, buf, cb, &cb)) {
		log_err(-1, "get_token_info", "Source: 1st GetTokenInformation failed!");
	} else {
		buf = (char *) malloc(cb);
		if (buf == NULL) {
			fprintf(stderr, "Unable to allocate memory!\n");
			return;
		}

		if (GetTokenInformation(token, TokenType, buf, cb, &cb)) {
			TOKEN_TYPE *ptu = (TOKEN_TYPE *)buf;
			if (*ptu == TokenPrimary) {
				if ((*type = strdup("TokenPrimary")) == NULL) {
					fprintf(stderr, "Unable to allocate memory!\n");
					free(buf);
					return;
				}
			} else if (*ptu == TokenImpersonation) {
				if ((*type = strdup("TokenImpersonation")) == NULL) {
					fprintf(stderr, "Unable to allocate memory!\n");
					free(buf);
					return;
				}
			} else {
				sprintf(logb, "Source: GetTokenInformation failed with error=%d", GetLastError());
				log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", logb);

			}
		}
	}
	CloseHandle(token);
}

static void
get_auth_luid(LUID *pluid)
{
	HANDLE	htok;
	TOKEN_STATISTICS stat;
	int	tokelen;
	char	logb[LOG_BUF_SIZE] = {'\0' } ;

	/* get the process token */
	if (OpenProcessToken(GetCurrentProcess(), TOKEN_ALL_ACCESS, &htok)) {

		if (GetTokenInformation(htok, TokenStatistics, &stat, sizeof(stat),
			&tokelen)) {
			sprintf(logb, "get_auth_luid: returning id=%d\n", stat.AuthenticationId);
			log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", logb);
			*pluid = stat.AuthenticationId;
		}
	}

	if (htok != INVALID_HANDLE_VALUE)
		CloseHandle(htok);

}
/* returns the handle value to the impersonation security token that can be
 passed on to ImpersonateLoggedOnUser(). */
HANDLE
LogonUserNoPass(char *user)
{
	TOKEN_USER token_user;
	TOKEN_OWNER token_owner;
	TOKEN_GROUPS *token_groups = NULL;
	TOKEN_GROUPS *tg = NULL;
	TOKEN_PRIMARY_GROUP token_prigrp;
	TOKEN_PRIVILEGES *token_privs = NULL;
	TOKEN_PRIVILEGES *token_privs_user = NULL;
	TOKEN_PRIVILEGES *token_privs_groups = NULL;
	TOKEN_SOURCE *token_source = NULL;
	TOKEN_DEFAULT_DACL token_dacl;
	char	logb[LOG_BUF_SIZE] = {'\0'} ;

	SID	*usid = NULL;
	LUID	authLuid = ANONYMOUS_LOGON_LUID;
	LSA_OBJECT_ATTRIBUTES lsa = { sizeof(LSA_OBJECT_ATTRIBUTES) };
	LSA_HANDLE hLsa = INVALID_HANDLE_VALUE;
	HANDLE hToken = INVALID_HANDLE_VALUE;
	HANDLE hPrimaryToken = INVALID_HANDLE_VALUE;
	SECURITY_QUALITY_OF_SERVICE sqos = \
               { sizeof(sqos), SecurityImpersonation, SECURITY_STATIC_TRACKING,
		FALSE };
	LSA_OBJECT_ATTRIBUTES oa =
		{ sizeof(oa), 0, 0, 0, 0, &sqos };

	SECURITY_ATTRIBUTES sa = { sizeof(sa), NULL, TRUE };
	LARGE_INTEGER expire = { 0xffffffff, 0x7fffffff } ;
	HANDLE retval = INVALID_HANDLE_VALUE;

	token_dacl.DefaultDacl = NULL;
	token_prigrp.PrimaryGroup = NULL;

	if (NtCreateToken == NULL) {
		HMODULE hNtDll;
		hNtDll=LoadLibrary("ntdll.dll");
		NtCreateToken = (NtCreateToken_t)GetProcAddress(hNtDll,
			"NtCreateToken");
		if (NtCreateToken == NULL)
			return (0);
	}

	if (!has_privilege(SE_CREATE_TOKEN_NAME)) {
		if (!ena_privilege(SE_CREATE_TOKEN_NAME)) {
			goto setuser_end;
		}
	}

	if (LsaOpenPolicy(NULL, &lsa, POLICY_ALL_ACCESS, &hLsa) != ERROR_SUCCESS)
		goto setuser_end;

	if ((usid=getusersid(user)) == NULL)
		goto setuser_end;

	token_owner.Owner = usid;

	token_user.User.Sid = usid;
	token_user.User.Attributes=0;

	if ((token_prigrp.PrimaryGroup=getdefgrpsid(user)) == NULL)
		goto setuser_end;

	token_groups = create_token_groups(user,
		SE_GROUP_ENABLED|SE_GROUP_ENABLED_BY_DEFAULT);

	tg = add_token_groups(token_groups, "LOCAL", NULL,
		SE_GROUP_ENABLED|SE_GROUP_ENABLED_BY_DEFAULT|SE_GROUP_MANDATORY);
	if (tg != NULL) {
		token_groups = tg;
	}

	tg = add_token_groups(token_groups, "INTERACTIVE", NULL,
		SE_GROUP_ENABLED|SE_GROUP_ENABLED_BY_DEFAULT|SE_GROUP_MANDATORY);
	if (tg != NULL) {
		token_groups = tg;
	}

	tg = add_token_groups(token_groups, "Authenticated Users", NULL,
		SE_GROUP_ENABLED|SE_GROUP_ENABLED_BY_DEFAULT|SE_GROUP_MANDATORY);
	if (tg != NULL) {
		token_groups = tg;
	}

	tg = add_token_groups(token_groups, "Everyone", NULL,
		SE_GROUP_ENABLED|SE_GROUP_ENABLED_BY_DEFAULT|SE_GROUP_MANDATORY);
	if (tg != NULL) {
		token_groups = tg;
	}

	/* The following is needed to mimic a regular user token */
	tg = add_token_groups(token_groups, "USERS", NULL,
		SE_GROUP_ENABLED|SE_GROUP_ENABLED_BY_DEFAULT|SE_GROUP_MANDATORY);

	if (tg != NULL) {
		token_groups = tg;
	}

	tg = add_token_groups(token_groups, NULL, luid2sid(authLuid),
		SE_GROUP_LOGON_ID|SE_GROUP_ENABLED|SE_GROUP_ENABLED_BY_DEFAULT|SE_GROUP_MANDATORY);
	if (tg != NULL) {
		token_groups = tg;
	}

	token_privs_user = create_token_privs_byuser(usid,
		SE_PRIVILEGE_ENABLED|SE_PRIVILEGE_ENABLED_BY_DEFAULT, hLsa);

	if (token_privs_user == NULL) {
		sprintf(logb,"token_privs_user is NULL");
		log_err(-1, "LogonUserNoPass", logb);
		goto setuser_end;
	}

	token_privs_groups = create_token_privs_bygroups(token_groups,
		SE_PRIVILEGE_ENABLED|SE_PRIVILEGE_ENABLED_BY_DEFAULT, hLsa);

	if (token_privs_groups == NULL)
		goto setuser_end;

	token_privs = merge_token_privs(token_privs_groups, token_privs_user);

	if (token_privs == NULL)
		goto setuser_end;

	token_source = create_token_source("pbs");

	if (token_source == NULL)
		goto setuser_end;

	token_dacl.DefaultDacl = create_default_dacl(usid, token_groups);
	if (token_dacl.DefaultDacl == NULL)
		goto setuser_end;

	if (NtCreateToken(&hToken, TOKEN_ALL_ACCESS, &oa, TokenImpersonation,
		&authLuid, &expire, &token_user, token_groups, token_privs,
		&token_owner, &token_prigrp, &token_dacl,
		token_source) != ERROR_SUCCESS)
		goto setuser_end;
	hPrimaryToken = hToken;

	if (DuplicateTokenEx(hToken, TOKEN_ALL_ACCESS, &sa,
		SecurityImpersonation,
		TokenPrimary, &hPrimaryToken) == 0)
		goto setuser_end;

	retval = hPrimaryToken;

setuser_end:
	if (usid)
		LocalFree(usid);

	if (token_prigrp.PrimaryGroup)
		LocalFree(token_prigrp.PrimaryGroup);

	if (token_groups)
		(void)free_token_groups(token_groups);

	if (token_privs)
		(void)free(token_privs);

	if (token_privs_user)
		(void)free(token_privs_user);

	if (token_privs_groups)
		(void)free(token_privs_groups);

	if (token_source)
		free(token_source);

	if (hToken != INVALID_HANDLE_VALUE)
		CloseHandle(hToken);

	if (token_dacl.DefaultDacl)
		(void)free(token_dacl.DefaultDacl);

	if (hLsa != INVALID_HANDLE_VALUE)
		LsaClose(hLsa);

	return (retval);
}

static HANDLE setuser_hdle = INVALID_HANDLE_VALUE;

/* returns 0 for fail and non-zero for success */
/* records internally the current user handle */
int
setuser(char *user)
{
	int	retval;

	if (user == NULL)
		return (0);

	setuser_hdle = LogonUserNoPass(user);

	if (setuser_hdle != INVALID_HANDLE_VALUE) {
		retval = impersonate_user(setuser_hdle);
	} else
		retval =0;

	return (retval);
}


/* setuser_with_password: like setuser() but with password cred_buf
 * and cred_len. If cred_buf is NULL, then it defaults to calling
 * setuser().
 * Returns: 0 for fail; non-zero for success
 */
int
setuser_with_password(char *user,
	char *cred_buf,
	size_t cred_len,
	int (*decrypt_func)(char *, int, size_t, char **))
{

	SID     *usid;
	char    thepass[PWLEN+1] = {'\0'};
	char    realname[UNLEN+1] = {'\0'};
	char    domain[PBS_MAXHOSTNAME+1] = "";
	struct	passwd *pwdp = NULL;
	int	i;

	if ((user == NULL) || (decrypt_func == NULL))
		return (0);

	if (passwd_cache_init == 0) {
		CLEAR_HEAD(passwd_cache_ll);
		passwd_cache_init = 1;
	}

	/* look in internal cache for saved usertoken handle */
	for (pwdp = (struct passwd*) GET_NEXT(passwd_cache_ll);
		pwdp; pwdp = (struct passwd*) GET_NEXT(pwdp->pw_allpasswds)) {
		if ( (strcmp(pwdp->pw_name, user) == 0) && \
			(pwdp->pw_userlogin != INVALID_HANDLE_VALUE) ) {
			setuser_hdle = pwdp->pw_userlogin;
			return (impersonate_user(setuser_hdle));
		}
	}

	usid = getusersid2(user, realname);
	if (usid == NULL) {
		return (0);
	}
	LocalFree(usid);

	if (cred_buf) { /* there's password supplied */
		char *pass = NULL;
		char *p = NULL;

		if (decrypt_func(cred_buf, PBS_CREDTYPE_AES, cred_len, &pass) != 0) {/* fails */
			return (0);
		}
		strncpy(thepass, pass, cred_len);
		thepass[cred_len] = '\0';

		if (pass) {
			memset(pass, 0, cred_len);
			(void)free(pass);
		}

		strcpy(domain, ".");
		if (p=strrchr(realname, '\\')) {
			*p = '\0';
			strcpy(domain, realname);
			*p = '\\';
		}

		/* clear handle if previously set */
		if (setuser_hdle != INVALID_HANDLE_VALUE) {
			CloseHandle(setuser_hdle);
			setuser_hdle = INVALID_HANDLE_VALUE;
		}

		if (LogonUser(user, domain, thepass,
			LOGON32_LOGON_BATCH, LOGON32_PROVIDER_DEFAULT,
			&setuser_hdle) == 0) {
			LogonUser(user, domain, thepass,
				LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT,
				&setuser_hdle);
		}
		memset(thepass, 0, cred_len);

		return (impersonate_user(setuser_hdle));
	}

	/* no password */

	return (setuser(user));
}

/* returns the current user handle */
HANDLE
setuser_handle()
{
	return (setuser_hdle);
}

/* closes the current user handle */
void
setuser_close_handle()
{
	struct passwd *pwdp = NULL;
	int	i;

	if (passwd_cache_init == 0) {
		CLEAR_HEAD(passwd_cache_ll);
		passwd_cache_init = 1;
	}

	if (setuser_hdle != INVALID_HANDLE_VALUE) {
		CloseHandle(setuser_hdle);

		/* look in internal cache for saved usertoken handle */
		for (pwdp = (struct passwd*) GET_NEXT(passwd_cache_ll);
			pwdp; pwdp = (struct passwd*) GET_NEXT(pwdp->pw_allpasswds)) {
			if (pwdp->pw_userlogin == setuser_hdle) {
				pwdp->pw_userlogin = INVALID_HANDLE_VALUE;
			}
		}
		setuser_hdle = INVALID_HANDLE_VALUE;
	}

}

/* setuid: mimics the setuid() call in UNIX */
/* Return: 0 for success; -1 otherwise.	    */
int
setuid(uid_t uid)
{
	int ret = 0;
	struct passwd *pw = NULL;

	if ((pw=getpwuid(uid)) == NULL)
		return (-1);

	if (setuser(pw->pw_name) == 0) { /* fail */
		ret = -1;
	}
	setuser_close_handle();
	return (ret);
}

/**
 * @brief       Execute cmdline as user using the impersonation token user_handle.
 *              If user_handle is INVALID_HANDLE_VALUE, then use CreateProcess()
 *              Returns the exit code from 'cmdline' process if sucessfully run, or
 *              the GetLastError() code if CreateProcess() fails to launch 'cmdline'.
 *
 * @param[in]   cmdline             : The command line to be executed
 * @param[in]   user_handle         : impersonated user token
 *
 * @return      int
 * @retval      0 for success
 * @retval      error code for failure
 */
int
wsystem(char *cmdline, HANDLE user_handle)
{

	STARTUPINFO             si = { 0 };
	PROCESS_INFORMATION     pi = { 0 };
	int			flags = CREATE_DEFAULT_ERROR_MODE| CREATE_NEW_PROCESS_GROUP;
	int			rc = 0;
	int			run_exit = 0;
	char			cmd[PBS_CMDLINE_LENGTH] = {'\0'};
	char			cmd_shell[MAX_PATH + 1] = {'\0'};
	char			current_dir[MAX_PATH+1] = {'\0'};
	char			*temp_dir = NULL;
	int			changed_dir = 0;

	si.cb = sizeof(si);
	si.lpDesktop = NULL;

	/* If we fail to get cmd shell(unlikely), use "cmd.exe" as shell */
	if (0 != get_cmd_shell(cmd_shell, sizeof(cmd_shell)))
		(void)snprintf(cmd_shell, sizeof(cmd_shell) - 1, "cmd.exe");
	(void)snprintf(cmd, PBS_CMDLINE_LENGTH - 1, "%s /c %s", cmd_shell, cmdline);


	/* cmd.exe doesn't like UNC path for a current directory. */
	/* We can be cd-ed to it like in a server failover setup. */
	/* In such a case, need to temporarily cd to a local path, */
	/* before executing cmd.exe */

	current_dir[0] = '\0';
	_getcwd(current_dir, MAX_PATH+1);
	if (IS_UNCPATH(current_dir)) {     /* \\host\share */
		temp_dir = get_win_rootdir();
		if (chdir(temp_dir?temp_dir:"C:\\") == 0)
			changed_dir = 1;
	}
	if (user_handle == NULL || user_handle == INVALID_HANDLE_VALUE) {
		rc=CreateProcess(NULL, cmd,
			NULL, NULL, TRUE, flags,
			NULL, NULL, &si, &pi);
	} else {
		rc=CreateProcessAsUser(user_handle, NULL, cmd,
			NULL, NULL, TRUE, flags,
			NULL, NULL, &si, &pi);
	}

	run_exit = GetLastError();

	/* restore current working directory */
	if (changed_dir)
		chdir(current_dir);

	if (rc) { /* CreateProcess* successful */

		WaitForSingleObject(pi.hProcess, INFINITE);

		if (GetExitCodeProcess(pi.hProcess, &run_exit) == 0)
			run_exit = GetLastError();

		CloseHandle(pi.hProcess);
		CloseHandle(pi.hThread);
	}

	return (run_exit);
}

/* add_window_station_ace: add a window station allowed access permission for
 user represented by 'usid'. Returns 0 for success; 1 for failure. */
static int
add_window_station_ace(HWINSTA hwin, SID *usid)
{
	int			ret = 1;
	SECURITY_INFORMATION	si;
	SECURITY_DESCRIPTOR	*sd = NULL;
	SECURITY_DESCRIPTOR	*sd_new = NULL;
	DWORD			sd_sz;
	DWORD			sd_sz_need;

	BOOL			hasDacl = 0;
	BOOL			defDacl = 0;
	ACL			*acl = NULL;
	ACL			*acl_new = NULL;
	ACL_SIZE_INFORMATION	acl_szinfo;
	DWORD			acl_new_sz;

	DWORD			i;
	VOID			*ace_temp;
	ACCESS_ALLOWED_ACE	*ace = NULL;

	si = DACL_SECURITY_INFORMATION;
	sd = NULL;
	sd_sz = 0;
	sd_sz_need = 0;
	if (GetUserObjectSecurity(hwin, &si, sd, sd_sz, &sd_sz_need) == 0) {

		if (GetLastError() == ERROR_INSUFFICIENT_BUFFER) {
			if ((sd=(SECURITY_DESCRIPTOR *)malloc(sd_sz_need)) == NULL) {
				errno = GetLastError();
				goto fail;
			}
			memset((SECURITY_DESCRIPTOR *)sd, 0, sd_sz_need);
		}

		sd_sz = sd_sz_need;
		if (GetUserObjectSecurity(hwin, &si, sd, sd_sz,
			&sd_sz_need) == 0) {

			errno = GetLastError();
			goto fail;
		}
	}

	acl = NULL;
	if (GetSecurityDescriptorDacl(sd, &hasDacl, &acl, &defDacl) == 0) {
		errno = GetLastError();
		goto fail;
	}

	ZeroMemory(&acl_szinfo, sizeof(ACL_SIZE_INFORMATION));
	acl_szinfo.AclBytesInUse = sizeof(ACL);
	/* compute new acl size */
	acl_new_sz = acl_szinfo.AclBytesInUse +
		(2 * sizeof(ACCESS_ALLOWED_ACE)) +
	(2 * GetLengthSid(usid)) -
	(2 * sizeof(DWORD));

	if ((acl_new=(ACL *)malloc(acl_new_sz)) == NULL) {
		errno = GetLastError();
		goto fail;
	}
	memset((ACL *)acl_new, 0, acl_new_sz);


	if (InitializeAcl(acl_new, acl_new_sz, ACL_REVISION) == 0) {
		goto fail;
	}


	if (acl != NULL) {
		if (GetAclInformation(acl,
			(VOID *)&acl_szinfo, sizeof(ACL_SIZE_INFORMATION),
			AclSizeInformation) == 0) {
			errno = GetLastError();
			goto fail;
		}

		if (hasDacl) {
			ACL *acl_new_tmp;

			for (i=0; i < acl_szinfo.AceCount; i++) {

				if (GetAce(acl, i, (VOID **)&ace_temp) == 0) {
					errno  = GetLastError();
					goto fail;
				}
				acl_new_sz += ((ACE_HEADER *)ace_temp)->AceSize;
			}
			if( (acl_new_tmp=(ACL *)realloc(acl_new, acl_new_sz)) \
								     == NULL ) {
				errno = GetLastError();
				goto fail;
			}

			acl_new = acl_new_tmp;
			memset((ACL *)acl_new, 0, acl_new_sz);

			if( InitializeAcl(acl_new, acl_new_sz, ACL_REVISION) \
									== 0 ) {

				goto fail;
			}

			for (i=0; i < acl_szinfo.AceCount; i++) {
				if (GetAce(acl, i, (VOID **)&ace_temp) == 0) {
					errno  = GetLastError();
					goto fail;
				}

				/* add the ACE to the new  ACL */
				if (AddAce(acl_new, ACL_REVISION, MAXDWORD,
					ace_temp,
					((ACE_HEADER *)ace_temp)->AceSize) == 0) {
					errno = GetLastError();
					goto fail;
				}
			}
		}
	}


	/* add the first ACE to the windowstation */
	if( (ace=(ACCESS_ALLOWED_ACE *)\
			malloc(	sizeof(ACCESS_ALLOWED_ACE) +
		GetLengthSid(usid) -
		sizeof(DWORD))) == NULL) {
		errno = GetLastError();
		goto fail;
	}

	ace->Header.AceType  = ACCESS_ALLOWED_ACE_TYPE;
	ace->Header.AceFlags = CONTAINER_INHERIT_ACE |
		INHERIT_ONLY_ACE     |
	OBJECT_INHERIT_ACE;

	ace->Header.AceSize  = (WORD)(sizeof(ACCESS_ALLOWED_ACE) +
		GetLengthSid(usid) - sizeof(DWORD));
	ace->Mask            = 	GENERIC_READ |
		GENERIC_WRITE |
	GENERIC_EXECUTE |
	GENERIC_ALL;

	if (CopySid(GetLengthSid(usid), &ace->SidStart, usid) == 0) {
		errno = GetLastError();
		goto fail;
	}

	if (AddAce(acl_new, ACL_REVISION, MAXDWORD, (VOID *)ace,
		ace->Header.AceSize) == 0) {
		errno = GetLastError();
		goto fail;
	}


	/* add the second ACE to the windowstation */
	ace->Header.AceFlags = NO_PROPAGATE_INHERIT_ACE;
	ace->Mask            = 	WINSTA_ACCESSCLIPBOARD 	|
		WINSTA_ACCESSGLOBALATOMS|
	WINSTA_CREATEDESKTOP    |
	WINSTA_ENUMDESKTOPS	|
	WINSTA_ENUMERATE        |
	WINSTA_EXITWINDOWS      |
	WINSTA_READATTRIBUTES   |
	WINSTA_READSCREEN       |
	WINSTA_WRITEATTRIBUTES  |
	DELETE                  |
	READ_CONTROL            |
	WRITE_DAC               |
	WRITE_OWNER;
	if (AddAce(acl_new, ACL_REVISION, MAXDWORD, (VOID *)ace, ace->Header.AceSize) == 0) {
		errno = GetLastError();
		goto fail;
	}

	if ((sd_new=(SECURITY_DESCRIPTOR *)malloc(sd_sz)) == NULL) {
		errno = GetLastError();
		goto fail;
	}

	if (InitializeSecurityDescriptor(sd_new,
		SECURITY_DESCRIPTOR_REVISION) == 0) {
		errno = GetLastError();
		goto fail;
	}

	/* set new dacl for the security descriptor */
	if (SetSecurityDescriptorDacl(sd_new, TRUE, acl_new, FALSE) == 0) {
		errno = GetLastError();
		goto fail;
	}
	if (SetUserObjectSecurity(hwin, &si, sd_new) == 0) {
		goto fail;
	}


	ret = 0;
fail:

	if (ace) {
		(void)free(ace);
	}

	if (acl_new) {
		(void)free(acl_new);
	}

	if (sd) {
		(void)free(sd);
	}

	if (sd_new) {
		(void)free(sd_new);
	}

	return (ret);

}

/* add_desktop_ace: add a desktop allowed access permission for
 user represented by 'usid'. Returns 0 for success; 1 for failure. */
static int
add_desktop_ace(HDESK hdesk, SID *usid)
{
	int			ret = 1;
	SECURITY_INFORMATION	si = 0;
	SECURITY_DESCRIPTOR	*sd = NULL;
	SECURITY_DESCRIPTOR	*sd_new = NULL;
	DWORD			sd_sz = 0;
	DWORD			sd_sz_need = 0;

	BOOL			hasDacl = 0;
	BOOL			defDacl = 0;
	ACL			*acl = NULL;
	ACL			*acl_new = NULL;
	ACL_SIZE_INFORMATION	acl_szinfo = {0};
	DWORD			acl_new_sz = 0;

	DWORD			i = 0;
	VOID			*ace_temp = NULL;
	ACCESS_ALLOWED_ACE	*ace = NULL;

	si = DACL_SECURITY_INFORMATION;
	sd = NULL;
	sd_sz = 0;
	sd_sz_need = 0;
	if (GetUserObjectSecurity(hdesk, &si, sd, sd_sz, &sd_sz_need) == 0) {

		if (GetLastError() == ERROR_INSUFFICIENT_BUFFER) {

			if ((sd=(SECURITY_DESCRIPTOR *)malloc(sd_sz_need)) == NULL) {
				errno = GetLastError();
				goto fail;
			}
			memset((SECURITY_DESCRIPTOR *)sd, 0, sd_sz_need);
		}

		sd_sz = sd_sz_need;
		if (GetUserObjectSecurity(hdesk, &si, sd, sd_sz,
			&sd_sz_need) == 0) {
			errno = GetLastError();
			goto fail;
		}
	}

	acl = NULL;
	if (GetSecurityDescriptorDacl(sd, &hasDacl, &acl, &defDacl) == 0) {
		errno = GetLastError();
		goto fail;
	}

	ZeroMemory(&acl_szinfo, sizeof(ACL_SIZE_INFORMATION));
	acl_szinfo.AclBytesInUse = sizeof(ACL);
	/* compute new acl size */

	acl_new_sz = acl_szinfo.AclBytesInUse +
		sizeof(ACCESS_ALLOWED_ACE) +
	GetLengthSid(usid) -
	sizeof(DWORD);

	if ((acl_new=(ACL *)malloc(acl_new_sz)) == NULL) {
		errno = GetLastError();
		goto fail;
	}
	memset((ACL *)acl_new, 0, acl_new_sz);

	if (InitializeAcl(acl_new, acl_new_sz, ACL_REVISION) == 0) {
		goto fail;
	}


	if (acl != NULL) {

		if (GetAclInformation(acl,
			(VOID *)&acl_szinfo, sizeof(ACL_SIZE_INFORMATION),
			AclSizeInformation) == 0) {
			errno = GetLastError();
			goto fail;
		}

		if (hasDacl) {
			ACL	*acl_new_tmp = NULL;

			for (i=0; i < acl_szinfo.AceCount; i++) {
				if (GetAce(acl, i, &ace_temp) == 0) {
					errno  = GetLastError();
					goto fail;
				}
				acl_new_sz += ((ACE_HEADER *)ace_temp)->AceSize;
			}

			if( (acl_new_tmp=(ACL *)realloc(acl_new,acl_new_sz)) \
								     == NULL ) {
				errno = GetLastError();
				goto fail;
			}
			acl_new = acl_new_tmp;

			memset((ACL *)acl_new, 0, acl_new_sz);

			if (InitializeAcl(acl_new, acl_new_sz, ACL_REVISION) == 0) {
				goto fail;
			}

			for (i=0; i < acl_szinfo.AceCount; i++) {
				if (GetAce(acl, i, &ace_temp) == 0) {
					errno  = GetLastError();
					goto fail;
				}

				/* add the ACE to the new  ACL */
				if (AddAce(acl_new, ACL_REVISION, MAXDWORD,
					ace_temp,
					((ACE_HEADER *)ace_temp)->AceSize) == 0) {
					errno = GetLastError();
					goto fail;
				}
			}
		}
	}

	/* add ace to the dacl */

	if (AddAccessAllowedAce(acl_new, ACL_REVISION, DESKTOP_ALL,
		usid) == 0) {
		errno = GetLastError();
		goto fail;
	}

	if ((sd_new=(SECURITY_DESCRIPTOR *)malloc(sd_sz)) == NULL) {
		errno = GetLastError();
		goto fail;
	}

	if (InitializeSecurityDescriptor(sd_new,
		SECURITY_DESCRIPTOR_REVISION) == 0) {
		errno = GetLastError();
		goto fail;
	}

	/* set new dacl for the security descriptor */

	if (SetSecurityDescriptorDacl(sd_new, TRUE, acl_new, FALSE) == 0) {
		errno = GetLastError();
		goto fail;
	}

	if (SetUserObjectSecurity(hdesk, &si, sd_new) == 0) {
		goto fail;
	}

	ret = 0;	/* success */
fail:

	if (acl_new)(void)free(acl_new);

	if (sd)(void)free(sd);

	if (sd_new)(void)free(sd_new);

	return (ret);

}

/* use_window_station_desktop: add 'usid' to list of SIDS allowed access
 to calling process' window station and desktop.
 returns 0 for success; 1 for fail. */
int
use_window_station_desktop(SID *usid)
{
	HWINSTA	hwin;
	HDESK	hdesk;
	int	ret = 1;

	if ((hwin=GetProcessWindowStation()) == NULL) {
		errno = GetLastError();
		goto end;
	}

	if ((hdesk=GetThreadDesktop(GetCurrentThreadId())) == NULL) {
		errno = GetLastError();
		goto end;
	}

	if (add_window_station_ace(hwin, usid)) {
		goto end;
	}

	if (add_desktop_ace(hdesk, usid)) {
		goto end;
	}

	ret = 0;

	end:  	if (hwin)
		CloseWindowStation(hwin);

	if (hdesk)
		CloseDesktop(hdesk);

	return (ret);

}

/* use_window_station_desktop2: add 'user' to list of users allowed access
 to calling process' window station and desktop.
 Returns 0 for success; 1 for fail. */
int
use_window_station_desktop2(char *user)
{
	HWINSTA	hwin;
	HDESK	hdesk;
	SID	*usid;
	int	ret = 1;

	if ((hwin=GetProcessWindowStation()) == NULL) {
		errno = GetLastError();
		goto end;
	}

	if ((hdesk=GetThreadDesktop(GetCurrentThreadId())) == NULL) {
		errno = GetLastError();
		goto end;
	}

	if ((usid=getusersid(user)) == NULL) {
		errno = GetLastError();
		goto end;
	}

	if (add_window_station_ace(hwin, usid)) {
		goto end;
	}

	if (add_desktop_ace(hdesk, usid)) {
		goto end;
	}


	ret = 0;
	end:  	if (hwin)
		CloseWindowStation(hwin);

	if (hdesk)
		CloseDesktop(hdesk);

	if (usid)
		LocalFree(usid);

	return (ret);
}

static void
print_pwentries(void)
{
	int i = 0;
	/* look for a password */
	struct passwd* pwdp = NULL;

	if (passwd_cache_init == 0) {
		CLEAR_HEAD(passwd_cache_ll);
		passwd_cache_init = 1;
	}

	for (pwdp = (struct passwd*) GET_NEXT(passwd_cache_ll);
		pwdp; pwdp = (struct passwd*) GET_NEXT(pwdp->pw_allpasswds)) {
		printf("[%d] (user=%s, pass=%s, uid=%ld, gid=%ld, gecos=%s, dir=%s shell=%s userlogin=%ld\n", i++,
			pwdp->pw_name,
			pwdp->pw_passwd? pwdp->pw_passwd : "null",
			pwdp->pw_uid,
			pwdp->pw_gid,
			pwdp->pw_gecos? pwdp->pw_gecos : "null",
			pwdp->pw_dir? pwdp->pw_dir : "null",
			pwdp->pw_shell? pwdp->pw_shell : "null",
			pwdp->pw_userlogin);
	}
}

/* add_pwentry: adds an entry for user 'name' in user_array and returning */
/*		the corresponding entry. */
/*		if user already exists then on updates are done but */
/*		corresponding entry returned. */

static struct passwd *
add_pwentry(char *name,
	char *passwd,
	uid_t uid,
	gid_t gid,
	char *gecos,
	char *dir,
	char *shell,
	HANDLE ulogin)
{

	struct  passwd *pwdp = NULL, *pwdn = NULL;
	DWORD	sid_len_need;

	if (name == NULL)
		return NULL;

	/* look for a password */
	for (pwdp = (struct passwd*) GET_NEXT(passwd_cache_ll);
		pwdp; pwdp = (struct passwd*) GET_NEXT(pwdp->pw_allpasswds)) {
		if (strcmp(pwdp->pw_name, name) == 0)
			return pwdp;			/* already recognized */
	}

	pwdn = (struct passwd *)calloc(1, sizeof(struct passwd));
	if (pwdn == NULL) {
		log_err(errno, __func__, "no memory");
		return NULL;
	}
	
	if ((pwdn->pw_name = strdup(name)) == NULL) {
		goto err;
	}

	if ((passwd == NULL) || strcmp(passwd, "*") == 0) {
		pwdn->pw_passwd = NULL;
	} else {
		if ((pwdn->pw_passwd = strdup(passwd)) == NULL) {
			goto err;
		}
	}

	pwdn->pw_uid = NULL;
	if (uid != NULL) {
		sid_len_need = GetLengthSid(uid);

		pwdn->pw_uid = (uid_t)malloc(sid_len_need);
		if (pwdn->pw_uid) {
			CopySid(sid_len_need, pwdn->pw_uid, uid);
		} else {
			goto err;
		}
	}

	pwdn->pw_gid = NULL;
	if (gid != NULL) {
		sid_len_need = GetLengthSid(gid);

		pwdn->pw_gid = (gid_t)malloc(sid_len_need);
		if (pwdn->pw_gid) {
			CopySid(sid_len_need, pwdn->pw_gid, gid);
		} else {
			goto err;
		}
	}

	pwdn->pw_gecos = NULL;
	if (gecos) {
		if ((pwdn->pw_gecos = strdup(gecos)) == NULL) {
			goto err;
		}
	}

	pwdn->pw_dir = NULL;
	if (dir) {
		if ((pwdn->pw_dir = strdup(dir)) == NULL) {
			goto err;
		}
	}

	pwdn->pw_shell = NULL;
	if (shell) {
		if ((pwdn->pw_shell = strdup(shell)) == NULL) {
			goto err;
		}
	}

	pwdn->pw_userlogin = ulogin;

	CLEAR_LINK(pwdn->pw_allpasswds);
	append_link(&passwd_cache_ll, &pwdn->pw_allpasswds, pwdn);

	return pwdn;
err:
	if (pwdn->pw_name)
		free(pwdn->pw_name);
	if (pwdn->pw_passwd)
		free(pwdn->pw_passwd);
	if (pwdn->pw_uid)
		free(pwdn->pw_uid);
	if (pwdn->pw_gid)
		free(pwdn->pw_gid);
	if (pwdn->pw_gecos)
		free(pwdn->pw_gecos);
	if (pwdn->pw_dir)
		free(pwdn->pw_dir);
	if (pwdn->pw_shell)
		free(pwdn->pw_shell);
	if (pwdn)
		free(pwdn);
	fprintf(stderr, "Unable to allocate memory!\n");
	return NULL;
}

/* logon_pw: creates a logon handle for 'username' with any output or logging */
/* 	     messages stored on 'msg'. The logon handle is created from       */
/* 	     'cred' if one exists, and adds 'username' to window station      */
/*	     permission access if use_winsta is set.                          */
/* NEW MOD for Single, Signon Password Scheme:                                */
/* This will only return NULL if username was not found in the                */
/*           the system, or user  has no homedir.                             */
/*           The failure case where the logon  handle returned is             */
/*           invalid due to bad  password will easily be known when the       */
/*           logon handle is fed to ImpersonateLoggedOnUser.                  */
/* NOTE: This function caches in some internal array the values for           */
/*       for usertoken and HomeDirectory.                                     */

struct	passwd *
logon_pw(char *username,
	char *credb,
	size_t credl,
	int (*decrypt_func)(char *, int, size_t, char **),
	int use_winsta,
	char *msg)
{
	int		found = 0;
	struct	passwd *pwdp = NULL;
	SID	*usid = NULL;
	char	*homedir = NULL;
	char  	thepass[PWLEN+1] = {'\0'};
	char 	realname[UNLEN+1] = {'\0'};
	char	domain[PBS_MAXHOSTNAME+1] = {'\0'};
	char	*p = {'\0'};
	char	msg2[LOG_BUF_SIZE] = {'\0'};

	if(!msg)
		return NULL;
	*msg = '\0';

	usid = getusersid2(username, realname);
	if (usid == NULL) {
		sprintf(msg2, "No entry for User %s", username);
		strcat(msg, msg2);
		return NULL;
	}
	
	if (passwd_cache_init == 0) {
		CLEAR_HEAD(passwd_cache_ll);
		passwd_cache_init = 1;
	}

	/* look for a password */
	for (pwdp = (struct passwd*) GET_NEXT(passwd_cache_ll);
		pwdp; pwdp = (struct passwd*) GET_NEXT(pwdp->pw_allpasswds)) {
		if (strcmp(pwdp->pw_name, username) == 0) {
			/*
			 * If an entry for user is found and
			 * there pwdp_pwdir is NULL.
			 * Fill the pwdp_pwdir with user home directory.
			 */
			if (pwdp->pw_dir == NULL)
				pwdp->pw_dir = getHomedir(username);
			found = 1;
			break;
		}
	}

	if (!found) {	/* no entry in database */

		homedir = getHomedir(username);
		if (homedir == NULL) {
			sprintf(msg2, "No homedir for User %s", username);
			strcat(msg, msg2);
			(void)LocalFree(usid);
			return NULL;
		}

		pwdp = add_pwentry(username, "*", usid, NULL, username, homedir,
			NULL, INVALID_HANDLE_VALUE);

		(void)free(homedir);

		if (pwdp == NULL) {	/* this should not happen */
			sprintf(msg2,
				"Could not create a passwd entry for User %s",
				username);
			strcat(msg, msg2);
			(void)LocalFree(usid);
			return NULL;
		}
	}

	if (use_winsta && (use_window_station_desktop(usid) == 0)) {
		sprintf(msg2, "allowed %s to access window station and desktop, ",
			username);
		strcat(msg, msg2);
	}

	(void)LocalFree(usid);

	if (credb) { /* there's password supplied via qsub -Wpwd="" */
		char *pass = NULL;

		if (decrypt_func(credb, PBS_CREDTYPE_AES, credl, &pass) != 0) { /* fails */
			sprintf(msg2, "decrypt_func for User %s failed!",
				username);
			strcat(msg, msg2);
			if ((pass = strdup(pwdp->pw_passwd)) == NULL) {
				fprintf(stderr, "Unable to allocate Memory!\n");
				return NULL;
			}
		}
		strncpy(thepass, pass, credl);
		thepass[credl] = '\0';

		if (pass) {
			memset(pass, 0, credl);
			free(pass);
		}

	} else if (pwdp->pw_passwd) {
		strcpy(thepass, pwdp->pw_passwd);
	}

	if (credb || pwdp->pw_passwd) {

		/* with password supplied, always regenerate logon handle*/
		if (pwdp->pw_userlogin != INVALID_HANDLE_VALUE) {
			CloseHandle(pwdp->pw_userlogin);
			pwdp->pw_userlogin = INVALID_HANDLE_VALUE;
		}
		sprintf(msg2, "User %s passworded", username);
		strcat(msg, msg2);

		strcpy(domain, ".");
		if (p=strrchr(realname, '\\')) {
			*p = '\0';
			strncpy(domain, realname, sizeof(domain)- 1);
			domain[sizeof(domain) - 1] = '\0';
			*p = '\\';
		}
		if (LogonUser(pwdp->pw_name, domain, thepass,
			LOGON32_LOGON_BATCH, LOGON32_PROVIDER_DEFAULT,
			&pwdp->pw_userlogin) == 0) {
			LogonUser(pwdp->pw_name, domain, thepass,
				LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT,
				&pwdp->pw_userlogin);
		}
		memset(thepass, 0, credl);
		if (pwdp->pw_userlogin != INVALID_HANDLE_VALUE) {
			if (impersonate_user(pwdp->pw_userlogin) != 0) {

				/* re-obtain homedir info under context of user */
				if (pwdp->pw_dir)
					(void)free(pwdp->pw_dir);
				pwdp->pw_dir = getHomedir(username);
				(void)revert_impersonated_user();
			}
		}

	} else {

		/* check if userlogin handle is stale */
		if (pwdp->pw_userlogin != INVALID_HANDLE_VALUE) {
			if (!impersonate_user(pwdp->pw_userlogin)) {

				CloseHandle(pwdp->pw_userlogin);
				pwdp->pw_userlogin = LogonUserNoPass(username);
			} else {
				RevertToSelf();
			}
		}
	}

	return pwdp;
}


struct passwd *
getpwnam(const char *name)
{
	SID	*usid;
	struct  passwd *pwdp = NULL;
	int found = 0;

	if (passwd_cache_init == 0) {
		CLEAR_HEAD(passwd_cache_ll);
		passwd_cache_init = 1;
	}

	/* look for a password */
	for (pwdp = (struct passwd*) GET_NEXT(passwd_cache_ll);
		pwdp; pwdp = (struct passwd*) GET_NEXT(pwdp->pw_allpasswds)) {
		if (strcmp(pwdp->pw_name, name) == 0){
			found = 1;
			break;
		}
	}

	if (!found) {	/* no entry in database */
		if ((usid=getusersid((char *)name)) != NULL) {
			pwdp = add_pwentry((char *)name, "*", usid, NULL,
				(char *)name, NULL, NULL,
				INVALID_HANDLE_VALUE);
			LocalFree(usid);
		} else {
			return NULL;
		}
	}

	return (pwdp);
}

struct passwd *
getpwuid(uid_t uid)
{
	struct  passwd *pwdp = NULL;
	char	*username = NULL;
	int	found = 0;

	if (uid == NULL)
		return NULL;


	if (passwd_cache_init == 0) {
		CLEAR_HEAD(passwd_cache_ll);
		passwd_cache_init = 1;
	}

	/* look for a password */
	for (pwdp = (struct passwd*) GET_NEXT(passwd_cache_ll);
		pwdp; pwdp = (struct passwd*) GET_NEXT(pwdp->pw_allpasswds)) {
		if (EqualSid(pwdp->pw_uid, uid)) {
			found = 1;
			break;
		}
	}


	if (!found) {	/* no entry in database */

		if ((username=getusername(uid)) != NULL) {
			pwdp = add_pwentry(username, "*", uid, NULL, username,
				NULL, NULL, INVALID_HANDLE_VALUE);
			if (username)(void)free(username);
		}
	}

	return (pwdp);

}

/**
 * @brief
 * 	This function must be executed by ADMIN
 */
void
cache_usertoken_and_homedir(char *user,
	char *pass,
	size_t passl,
	int (*read_password_func)(void *, char **, size_t *),
	void *param,
	int (*decrypt_func)(char *, int, size_t, char **),
	int force)
{
	char	msg[4096] = {'\0'};
	char	*credb = NULL;
	size_t	credl = 0;
	struct passwd *pwdp = NULL;
	int	i;

	if (user == NULL)
		return;

	if (passwd_cache_init == 0) {
		CLEAR_HEAD(passwd_cache_ll);
		passwd_cache_init = 1;
	}

	/* look for cached values if not forced to re-save values */
	if (!force) {
		for (pwdp = (struct passwd*) GET_NEXT(passwd_cache_ll);
			pwdp; pwdp = (struct passwd*) GET_NEXT(pwdp->pw_allpasswds)) {
			if( (strcmp(pwdp->pw_name, user) == 0) && \
		   	(pwdp->pw_userlogin != INVALID_HANDLE_VALUE) && \
			  ( (pwdp->pw_dir != NULL) && \
				(strcmp(pwdp->pw_dir, "") != 0) ) ) {
				return;
			}
		}
	}

	credb = pass;
	credl = passl;

	if ((credb == NULL) && (credl == 0) && (read_password_func != NULL)) {
		/* use the other method */
		read_password_func(param, &credb, &credl);
	}

	logon_pw(user, credb, credl, decrypt_func, 0, msg);

}

/**
 * @brief
 * 	wrap_NetUserGetGroups: wrapped "NetUserGetGroups()" that attempts to
 * 	correct failures due to ERROR_ACCESS_DENIED or ERROR_LOGON_FAILURE by
 * 	executing the call in the context of the user.
 *
 * @par	NOTE: uses 'winlog_buffer" for logging messages.
 */
NET_API_STATUS
wrap_NetUserGetGroups(LPCWSTR servername,
	LPCWSTR username,
	DWORD level,
	LPBYTE *bufptr,
	DWORD prefmaxlen,
	LPDWORD entriesread,
	LPDWORD totalentries)
{
	NET_API_STATUS	netst;

	winlog_buffer[0] = '\0';

	netst = NetUserGetGroups(servername, username, level, bufptr,
		prefmaxlen, entriesread, totalentries);

	if ((netst == ERROR_LOGON_FAILURE) || (netst == ERROR_ACCESS_DENIED)) {
		struct passwd *pw = NULL;
		char	user_name[UNLEN+1];
		int	found = 0;

		wcstombs(user_name, username, UNLEN);

		if (passwd_cache_init == 0) {
			CLEAR_HEAD(passwd_cache_ll);
			passwd_cache_init = 1;
		}

		for (pw = (struct passwd*) GET_NEXT(passwd_cache_ll);
			pw; pw = (struct passwd*) GET_NEXT(pw->pw_allpasswds)) {
			if (strcmp(pw->pw_name, user_name) == 0){
				found = 1;
				break;
			}
		}
		if (!found) {
			sprintf(winlog_buffer, "No user token found for %s",
				user_name);
			return (netst);

		}


		if (pw && (pw->pw_userlogin != INVALID_HANDLE_VALUE)) {

			if (impersonate_user(pw->pw_userlogin) != 0) {
				netst = NetUserGetGroups(servername, username,
					level, bufptr,
					prefmaxlen, entriesread, totalentries);

				(void)revert_impersonated_user();
			} else {
				sprintf(winlog_buffer, "Failed to impersonate user %s error %d", user_name, GetLastError());
			}

		} else {
			sprintf(winlog_buffer, "Did not find a security token for user %s, perhaps no cached password found!", user_name);
		}
	}

	return (netst);
}



/**
 * @brief
 *	wrap_NetUserGetLocalGroups: wrapped "NetUserGetLocalGroups()" that attempts
 *	to correct failures due to ERROR_ACCESS_DENIED or ERROR_LOGON_FAILURE
 *	by executing the call in the context of the user.
 *
 * @par	NOTE: uses 'winlog_buffer' for logging messages
 */
NET_API_STATUS
wrap_NetUserGetLocalGroups(LPCWSTR servername,
	LPCWSTR username,
	DWORD level,
	DWORD flags,
	LPBYTE *bufptr,
	DWORD prefmaxlen,
	LPDWORD entriesread,
	LPDWORD totalentries)
{
	NET_API_STATUS	netst;

	winlog_buffer[0] = '\0';

	netst = NetUserGetLocalGroups(servername, username, level, flags,
		bufptr, prefmaxlen, entriesread, totalentries);

	if ((netst == ERROR_LOGON_FAILURE) || (netst == ERROR_ACCESS_DENIED)) {
		struct passwd *pw = NULL;
		char	user_name[UNLEN+1];
		int 	found = 0;

		wcstombs(user_name, username, UNLEN);
		if (passwd_cache_init == 0) {
			CLEAR_HEAD(passwd_cache_ll);
			passwd_cache_init = 1;
		}

		for (pw = (struct passwd*) GET_NEXT(passwd_cache_ll);
			pw; pw = (struct passwd*) GET_NEXT(pw->pw_allpasswds)) {
			if (strcmp(pw->pw_name, user_name) == 0){
				found = 1;
				break;
			}
		}
		if (!found) {
			sprintf(winlog_buffer, "No user token found for %s",
				user_name);
			return (netst);
		}


		if (pw && (pw->pw_userlogin != INVALID_HANDLE_VALUE)) {

			if (impersonate_user(pw->pw_userlogin) != 0) {
				netst = NetUserGetLocalGroups(servername,
					username, level, flags, bufptr,
					prefmaxlen, entriesread, totalentries);
				(void)revert_impersonated_user();
			} else {
				sprintf(winlog_buffer, "Failed to impersonate user %s error %d", user_name, GetLastError());
			}

		} else {
			sprintf(winlog_buffer, "Did not find a security token for user %s, perhaps no cached password found!", user_name);
		}
	}

	return (netst);
}



/**
 * @brief
 *	wrap_NetUserGetInfo: wrapped "NetUserGetInfo()" that attempts
 *	to correct failures due to ERROR_ACCESS_DENIED or ERROR_LOGON_FAILURE
 *	by executing the call in the context of the user.
 *
 */
/* NOTE: uses 'winlog_buffer' for logging messages */
NET_API_STATUS
wrap_NetUserGetInfo(LPCWSTR servername,
	LPCWSTR username,
	DWORD level,
	LPBYTE *bufptr)
{
	NET_API_STATUS	netst;

	winlog_buffer[0] = '\0';

	netst = NetUserGetInfo(servername, username, level, bufptr);


	if ((netst == ERROR_LOGON_FAILURE) || (netst == ERROR_ACCESS_DENIED)) {
		struct passwd *pw = NULL;
		char	user_name[UNLEN+1] = {'\0'};
		int	found = 0;

		wcstombs(user_name, username, UNLEN);

		if (passwd_cache_init == 0) {
			CLEAR_HEAD(passwd_cache_ll);
			passwd_cache_init = 1;
		}

		for (pw = (struct passwd*) GET_NEXT(passwd_cache_ll);
			pw; pw = (struct passwd*) GET_NEXT(pw->pw_allpasswds)) {
			if (strcmp(pw->pw_name, user_name) == 0){
				found = 1;
				break;
			}
		}
		if (!found) {
			sprintf(winlog_buffer, "No user token found for %s",
				user_name);
			return (netst);
		}

		if (pw && (pw->pw_userlogin != INVALID_HANDLE_VALUE)) {

			if (impersonate_user(pw->pw_userlogin) != 0) {
				netst = NetUserGetInfo(servername,
					username, level, bufptr);
				(void)revert_impersonated_user();
			} else {
				sprintf(winlog_buffer, "Failed to impersonate user %s error %d", user_name, GetLastError());
			}

		} else {
			sprintf(winlog_buffer, "Did not find a security token for user %s, perhaps no cached password found!", user_name);
		}

	}

	return (netst);
}


/**
 * @brief
 * 	has_read_access_domain_users: returns 1 (TRUE) if executing account
 * 	has read access to all users information in the domain served by domain
 * 	controller 'dctrlw'; otherwise, returns 0 (FALSE).
 * NOTE: Heuristic: we'll only attempt to query up to NUM_USERS_TO_CHECK
 *
 */
#define NUM_USERS_TO_CHECK	5

static int
has_read_access_domain_users(wchar_t dctrlw[PBS_MAXHOSTNAME+1])
{
	SID	*sid = NULL;
	char	*gname = NULL;
	wchar_t	 gnamew[GNLEN+1] = {0};
	GROUP_USERS_INFO_0 *members = NULL;
	DWORD	nread = 0;
	DWORD	totentries = 0;
	DWORD	i = 0;
	int	ret = 0;
	USER_INFO_1     *ui1_ptr = NULL;
	NET_API_STATUS  netst = 0;
	int	ncheck = 0;

	sid = create_domain_users_sid();

	if (sid == NULL) {
		return (0);	/* can't figure out Domain Users sid */
	}
	if ((gname=getgrpname(sid)) == NULL) {
		goto has_read_access_domain_users_end;
	}

	mbstowcs(gnamew, gname, GNLEN);

	if ((netst=NetGroupGetUsers(dctrlw, gnamew, 0, (LPBYTE *)&members,
		MAX_PREFERRED_LENGTH, &nread, &totentries, NULL)) != NERR_Success) {
		goto has_read_access_domain_users_end;
	}

	for (i=0; i < nread && ncheck < NUM_USERS_TO_CHECK; i++) {

		netst = NetUserGetInfo(dctrlw,
			members[i].grui0_name, 1, (LPBYTE *)&ui1_ptr);

		if (ui1_ptr) {
			NetApiBufferFree(ui1_ptr);
		}

		if ((netst == ERROR_ACCESS_DENIED) ||
			(netst == ERROR_LOGON_FAILURE)) {
			goto has_read_access_domain_users_end;
		}
		ncheck++;
	}

	ret = 1;	/* success */
has_read_access_domain_users_end:
	if (sid) {
		LocalFree(sid);
	}
	if (gname) {
		(void)free(gname);
	}
	if (members) {
		NetApiBufferFree(members);
	}

	return (ret);
}

/**
 * @brief
 *	check_executor: validates the executing user account against some set of
 *
 * @par	criteria:
 *	(a) account is a member of an admin-type of group,\n
 *      (b) if in a domained environment, account is a domain account.\n
 *      (c) if in a domained environment, account can read all users
 *           				    information in the domain.
 * @return	int
 * @retval	0 	if the 3 criteria have been satisfied, or returns:
 * @retval	1 	if (a) is not satisfied,
 * @retval	2 	if (b) is not satisfied, and
 * @retval	3	if (c) is not satisfied.
 *	     		and 'winlog_buffer" will be filled with the
 *           		message that can be used to output to some log file.
 * Idea is based on return value, execution of PBS service account would
 * either proceed or abort.
 */

int
check_executor(void)
{
	char 	dname[PBS_MAXHOSTNAME+1] = {'\0'};
	char 	exec_unamef[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'}; /* <dom>\<user>0 */
	char 	exec_uname[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'};
	char	exec_dname[PBS_MAXHOSTNAME+1] = {'\0'};
	char	*p = NULL;
	int	ret = 0;

	/* Local System account is a valid service account */
	if(TRUE == isLocalSystem())
		return 0;

	winlog_buffer[0] = '\0';

	strcpy(exec_unamef, getlogin_full());
	strcpy(exec_uname, exec_unamef);
	strcpy(exec_dname, ".");

	if ((p=strchr(exec_unamef, '\\'))) {
		strcpy(exec_uname, p+1);
		*p = '\0';
		strcpy(exec_dname, exec_unamef);
		*p = '\\';
	}

	if (GetComputerDomainName(dname)) {
		char    	dname_a[PBS_MAXHOSTNAME+1] = {'\0'};
		char    	dctrl[PBS_MAXHOSTNAME+1] = {'\0'};
		wchar_t 	dctrlw[PBS_MAXHOSTNAME+1] = {'\0'};


		if (stricmp(exec_dname, dname) != 0) {
			sprintf(winlog_buffer,
				"%s: Executing user %s must be a domain account in domain %s", __func__, exec_uname, dname);
			return (2);
		}

		/* this test must occur first before the "read access" test */
		if (!isAdminPrivilege(exec_uname)) {
			sprintf(winlog_buffer,
				"%s: executing user %s should be an admin account", __func__, exec_uname);
			return (1);
		}

		strcpy(dctrl, dname);
		get_dcinfo(dname, dname_a, dctrl);

		/* convert strings to "wide" format */
		mbstowcs(dctrlw, dctrl, PBS_MAXHOSTNAME);

		if (!has_read_access_domain_users(dctrlw)) {
			sprintf(winlog_buffer,
				"%s: executing user %s cannot read all users info in %s (DC is %S)", __func__, exec_uname, dname, dctrlw);
			return (3);
		}
	} else {
		if (!isAdminPrivilege(exec_uname)) {
			sprintf(winlog_buffer,
				"%s: executing user %s should be an admin account", __func__, exec_uname);
			return (1);
		}
	}

	return (0);
}

/**
 * @brief
 *		Get active session id for the given user by enumerating all the sessions. If the user name is NULL, return the first active session.
 *
 * @param[in]	return_on_no_active_session - should the function return if no actvie session found
 * @param[in]	username - username for which the active session needs to be found.
 * @return
 *		DWORD
 *
 * @retval
 *		On Success - active user session id
 *		On Error   - -1 (it means no active session)
 *
 */
DWORD
get_activesessionid(int return_on_no_active_session, char *username)
{
	WTS_SESSION_INFO	WinSessionInfo;
	PWTS_SESSION_INFO	PWinSessionInfo = 0;
	DWORD				dwCount = 0;
	DWORD				i = 0;
	DWORD ret = -1;
	char  *active_user = NULL;
	/* Keep running the loop untill an active session is found */
	while(1)
	{
		/* Get information of all sessions */
		WTSEnumerateSessions(WTS_CURRENT_SERVER_HANDLE, 0, 1, &PWinSessionInfo, &dwCount);

		/* Find active session from all sessions */
		for (i = 0; i < dwCount; ++i) {
			WinSessionInfo = PWinSessionInfo[i];
			if (WinSessionInfo.State == WTSActive) {
				/* Active session found */
				/* If username is NULL, store the active session id, break the loop */
				/* If username is not NULL, return the active session id if it belongs to the user, else continue the loop */
				(void)get_usernamefromsessionid(WinSessionInfo.SessionId, &active_user);
				if((username == NULL) || ((active_user != NULL) && stricmp(active_user, username) == 0)) {
					ret = WinSessionInfo.SessionId;
					break;
				}
			}
		}

		/* Free session info structure and return active session id */
		WTSFreeMemory(PWinSessionInfo);
		if(ret != -1 || return_on_no_active_session)
			break;
		else
			Sleep(WAIT_TIME_FOR_ACTIVE_SESSION);
	}
	return ret;
}

/**
 * @brief
 *		Get the active user's token using active session id
 *
 * @param[in]
 *		activesessionid - active session id to get it's user token
 *
 * @return
 *		HANDLE
 *
 * @retval
 *		On Success - User's token handle
 *		On Error   - INVALID_HANDLE_VALUE
 *
 */
/* NOTE: This function must be called as LocalSystem Account, and return value must be freed! */
HANDLE
get_activeusertoken(DWORD activesessionid)
{
	HANDLE hUserToken = INVALID_HANDLE_VALUE;

	if (activesessionid == -1) /* No active user session, just return INVALID_HANDLE_VALUE */
		return INVALID_HANDLE_VALUE;

	/* Get user's token */
	if (!WTSQueryUserToken(activesessionid, &hUserToken)) {
		return INVALID_HANDLE_VALUE;
	}

	/* Token successfully created, return created user's token */
	return hUserToken;
}

/**
 * @brief
 *		Get the full username by using given session id
 *
 * @param[in] sessionid - session id to find it's owner's name
 * @param[out]	p_username - pointer to the short user name. If short name is not required provide NULL.
 *
 * @return
 *		char *
 *
 * @retval
 *		On Success - Username
 *		On Error   - NULL
 *
 */
/* NOTE: This function must be called as LocalSystem Account, and return value must be freed! */
char*
get_usernamefromsessionid(DWORD sessionid, char** p_username)
{
	HANDLE hUserToken = INVALID_HANDLE_VALUE;
	HANDLE hDupUserToken = INVALID_HANDLE_VALUE;
	char *username = NULL;
	char *temp_username = NULL;

	if (sessionid == -1)
		return NULL;

	if (!WTSQueryUserToken(sessionid, &hUserToken)) {
		return NULL;
	}

	if (!DuplicateToken(hUserToken, SecurityImpersonation, &hDupUserToken)) {
		CloseHandle(hUserToken);
		return NULL;
	}

	CloseHandle(hUserToken);
	if (!impersonate_user(hDupUserToken)) {
		CloseHandle(hDupUserToken);
		return NULL;
	}

	temp_username = getlogin_full();
	username = (char *)malloc(strlen(temp_username)+1);
	if (temp_username != NULL) {
		strcpy(username, temp_username);
	}
	if(p_username != NULL)
		*p_username = getlogin();

	(void)revert_impersonated_user();
	CloseHandle(hDupUserToken);
	return username;
}

#if (_WIN32_WINNT < 0x0501)
/**
 * @brief
 *		Find the full process image name with given process handle.
 *
 * @param[in]   hProcess - process handle
 * @param[out]  exe_name - full process image name
 * @param[out]  exe_namelen - length of full process image name
 * @return
 *		BOOL
 *
 * @retval
 *		If process found  - TRUE
 *		If process not found - FALSE
 *
 * @note	This function should be removed when Windows Server 2003 support is dropped.
 */
BOOL PBS_QueryFullProcessImageName(HANDLE hProcess, char *exe_name, int *exe_namelen)
{
	HANDLE	hprocessSnap = INVALID_HANDLE_VALUE;
	DWORD	proc_id = 0;
	BOOL	ret = FALSE;
	BOOL	proc_found = FALSE;
	PROCESSENTRY32 pe32 = { sizeof(pe32) };

	proc_id = GetProcessId(hProcess);
	hprocessSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, proc_id);

	if(hprocessSnap)
	{
		BOOL nextProcess = Process32First(hprocessSnap, &pe32);

		while(nextProcess)
		{
			if(pe32.th32ProcessID == proc_id)
			{
				proc_found = TRUE;
				break;
			}
			nextProcess = Process32Next(hprocessSnap, &pe32);
		}
		if(proc_found)
		{
			*exe_namelen = strlen(pe32.szExeFile);
			if(exe_name != NULL)
				strncpy(exe_name, pe32.szExeFile, *exe_namelen);
			ret = TRUE;
		}
		else
			ret = FALSE;
		CloseHandle(hprocessSnap);
	}
	return ret;
}
#endif /* _WIN32_WINNT < 0x0501 */

/**
 * @brief
 *		Find the process owner of given process id.
 *
 * @param[in]   processid - process id to find it's process owner
 * @param[out]  puid - pointer to SID of the process owner
 * @param[out]  puname - pointer to short user name(without domain)
 * @param[in]   uname_len - size of puname buffer
 * @param[out]  comm - executable file name of the process
 * @param[in]   comm_len - size of comm buffer
 *
 * @return
 *		char *
 *
 * @retval
 *		On Error  - NULL
 *		On Sucess - FQDN of process owner of given process id
 *
 */
char *
get_processowner(DWORD processid, uid_t *puid, char *puname, size_t uname_len, char *comm, size_t comm_len)
{
#define buf_size 512
	HANDLE hToken = INVALID_HANDLE_VALUE;
	HANDLE hProcess = INVALID_HANDLE_VALUE;
	TOKEN_USER *hUser = NULL;
	DWORD username_len = 0;
	DWORD domainname_len = 0;
	char username[UNLEN + 1] = {'\0'};
	char domainname[PBS_MAXHOSTNAME] = "";
	char *owner_fqdn = 0;
	char sid_buf[buf_size] = {'\0'};
	char owner_fqdn_buf[buf_size] = {'\0'};
	int rc = -1;

	hProcess = OpenProcess(PROCESS_ALL_ACCESS, FALSE, processid);
	if (hProcess == INVALID_HANDLE_VALUE) {
		CloseHandle(hProcess);
		return NULL;
	}

	if (!OpenProcessToken(hProcess, TOKEN_QUERY, &hToken)) {
		CloseHandle(hProcess);
		return NULL;
	}


	hUser = (TOKEN_USER *) owner_fqdn_buf;
	if (!GetTokenInformation(hToken, TokenUser, hUser, buf_size, &username_len)) {
		CloseHandle(hToken);
		CloseHandle(hProcess);
		return NULL;
	}

	domainname_len = PBS_MAXHOSTNAME;
	username_len = UNLEN;
	if (puid)
		*puid = hUser->User.Sid;

	if (!LookupAccountSid(0, hUser->User.Sid, username, &username_len, domainname, &domainname_len, (PSID_NAME_USE)&sid_buf)) {
		CloseHandle(hToken);
		CloseHandle(hProcess);
		return NULL;
	}

	if (puname != NULL)
		strncpy_s(puname, uname_len, username, _TRUNCATE);

	if (comm != NULL) {
		BOOL query_image = FALSE;
		/*
		 * This special code is written just to support Windows Server 2003.
		 * We should use QueryFullProcessImageName() for Vista and later.
		 * For Windows < Vista, we write a new function named PBS_QueryFullProcessImageName().
		 * Once we drop Server 2003, we will use QueryFullProcessImageName() for all Windows.
		 */
#if (_WIN32_WINNT < 0x0501)
		query_image = PBS_QueryFullProcessImageName(hProcess, comm, &comm_len);
#else
		query_image = QueryFullProcessImageName(hProcess, 0, comm, &comm_len);
#endif
		if (query_image == FALSE) {
			rc = GetLastError();
			*comm = '\0';
		}
	}

	strcpy_s(owner_fqdn_buf, buf_size, domainname);
	strcat_s(owner_fqdn_buf, buf_size, "\\");
	strcat_s(owner_fqdn_buf, buf_size, username);
	owner_fqdn = owner_fqdn_buf;


	CloseHandle(hToken);
	CloseHandle(hProcess);

	return owner_fqdn;
}

/**
 * @brief
 *		wrapper fuction of stat to support for UNC path
 * @param[in]
 *		path - path to stat
 * @param[in/out]
 *		psb   - pointer to stat structure
 * @return
 *		int
 * @retval
 *		On Error   - -1
 *		On success - >0
 */

int
stat_uncpath(char *path, struct stat *psb)
{
	char map_drive[MAXPATHLEN+1] = {'\0'};
	char path_temp_buf[MAXPATHLEN+1] = {'\0'};
	int ret = 0;
	int unmap = 0;

	if (path != NULL && *path != '\0' && psb != NULL) {
		/*
		 * convert "\ " (escaped space) with " "
		 * because "\" (escape char) in "\ "
		 * is valid path seperator in Windows
		 * and also "/" with "\"
		 */
		replace(path, "\\ ", " ", path_temp_buf);
		forward2back_slash(path_temp_buf);
	} else {
		return -1;
	}

	unmap = get_localpath(path_temp_buf, map_drive);
	ret = stat(path_temp_buf, psb);
	if (unmap)
		unmap_unc_path(map_drive);
	return ret;
}

/**
 * @brief
 *		wrapper fuction of access to support for UNC path
 * @param[in]
 *		path - path to check
 *		mode - mode to check on <path>
 * @return
 *		int
 * @retval
 *		On Error   - -1
 *		On success - >0
 */
int
access_uncpath(char *path, int mode)
{
	char map_drive[MAXPATHLEN+1] = {'\0'};
	char path_temp_buf[MAXPATHLEN+1] = {'\0'};
	int ret = 0;
	int unmap = 0;

	if (path != NULL && *path != '\0') {
		/*
		 * convert "\ " (escaped space) with " "
		 * because "\" (escape char) in "\ "
		 * is valid path seperator in Windows
		 * and also "/" with "\"
		 */
		replace(path, "\\ ", " ", path_temp_buf);
		forward2back_slash(path_temp_buf);
	} else {
		return -1;
	}

	unmap = get_localpath(path_temp_buf, map_drive);
	ret = _access(path_temp_buf, mode);
	if (unmap)
		unmap_unc_path(map_drive);
	return ret;
}

/**
 * @brief
 *		get UNC path of given <path> if available
 * @param[in/out]
 *		path - path to check
 * @return
 *		void
 */
void
get_uncpath(char *path)
{
	DWORD buf_len = MAXPATHLEN;
	UNIVERSAL_NAME_INFO *uni_name = NULL;
	char uni_name_info_buf[MAXPATHLEN+1] = {0};
	int endslash = 0;
	size_t path_len = 0;
	char path_temp_buf[MAXPATHLEN+1] = {'\0'};

	if (path == NULL ||
		*path == '\0' ||
		IS_UNCPATH(path))
		return;

	/*
	 * convert "\ " (escaped space) with " " and
	 * "\," (escaped comma) with "," because "\" (escape char) in "\ " or "\,"
	 * is valid path seperator in Windows
	 * and also "/" with "\"
	 */
	replace(path, "\\ ", " ", path_temp_buf);
	replace(path_temp_buf, "\\,", ",", path_temp_buf);
	forward2back_slash(path_temp_buf);
	path_len = strlen(path_temp_buf);

	if (path_temp_buf[path_len-1] == '\\') {
		endslash = 1;
		path_temp_buf[path_len-1] = '\0';
	}

	uni_name = (UNIVERSAL_NAME_INFO *) &uni_name_info_buf;
	if (WNetGetUniversalName(path_temp_buf, UNIVERSAL_NAME_INFO_LEVEL, (LPVOID) uni_name, &buf_len) == NO_ERROR) {
		strncpy(path, uni_name->lpUniversalName, MAXPATHLEN);
		/* append '\' if it is removed here */
		if (endslash) {
			strncat(path, "\\", 1);
		}
	}
}

/**
 * @brief
 *		get local mapped path of given <unc_path>
 * @param[in]
 *		unc_path - path
 * @param[in/out]
 *		map_drive - mapped path (if any)
 * @return
 *		int
 * @retval
 *		0 - Error or <unc_path> is not an UNC path
 *		1 - Successfully mapped given path and changed <unc_path> to local mapped path
 */
int
get_localpath(char *unc_path, char *map_drive)
{
	char given_path[MAXPATHLEN+1] = {'\0'};
	size_t len = 0;
	char *filename = NULL;
	struct passwd *userpw = NULL;

	if (unc_path == NULL ||
		*unc_path == '\0' ||
		map_drive == NULL ||
		!IS_UNCPATH(given_path))
		return 0;
	else
		strncpy_s(given_path, _countof(given_path), unc_path, _TRUNCATE);

	if ((userpw = getpwnam(getlogin())) == NULL)
		return -1;

	len = strlen(given_path);
	if (given_path[len-1] == '\\')
		given_path[len-1] = '\0';

	if (filename = strrchr(given_path, '\\'))
		*filename++ = 0;

	map_drive = map_unc_path(given_path, userpw);
	if (map_drive != NULL && *map_drive != '\0') {
		if (filename)
			snprintf(given_path, sizeof(given_path), "%s%s%s", map_drive, "\\", filename);
		else
			snprintf(given_path, sizeof(given_path), "%s%s", map_drive, "\\");
		strncpy(unc_path, given_path, strlen(given_path));
		return 1;
	}

	return 0;
}

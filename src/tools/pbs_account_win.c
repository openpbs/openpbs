/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
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

/**
 *  @file    pbs_account_win.c
 *
 *  @brief
 *		pbs_account_win - Functions related to the initialization of pbs acount on Windows.
 *
 * Functions included are:
 * 	init_lsa_string()
 * 	add_privilege()
 * 	register_scm()
 * 	unregister_scm()
 * 	prompt_to_get_password()
 * 	validate_account_password()
 * 	set_account_expiration()
 * 	set_account_primary_group()
 * 	add_to_administrators_group()
 * 	read_sa_password()
 * 	decrypt_sa_password()
 * 	add_service_account()
 * 	usage()
 * 	main()
 *
 */
#include <pbs_config.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <fcntl.h>
#include <string.h>
#include <netdb.h>
#include <ntsecapi.h>
#include "pbs_ifl.h"
#include "pbs_version.h"
#include <lmaccess.h>
#include <lm.h>
#include <conio.h>
#include <ctype.h>

#define	 WAIT_RETRY_MAX	10

int for_info_only = 0;
char	sa_password[LM20_PWLEN+1];
char	service_accountname[1024] = "pbsadmin";
char    exec_unamef[PBS_MAXHOSTNAME+UNLEN+2]; /* installer acct=<dom>\<user>0 */
char    exec_dname[PBS_MAXHOSTNAME+1];	      /* installer acct's domain */
/**
 * @brief
 * 		init_lsa_string - initialize lsa string.
 *
 * @param[in]	lsa_str	-	lsa string
 * @param[in]	str	-	Pointer to a wide character string.
 */
static void
init_lsa_string(LSA_UNICODE_STRING *lsa_str, LPWSTR str)
{
	USHORT	str_len;

	if (str == NULL) {
		lsa_str->Buffer = NULL;
		lsa_str->Length = 0;
		lsa_str->MaximumLength = 0;
		return;
	}

	/* Get the length of the string without null terminator */
	str_len = wcslen(str);
	lsa_str->Buffer = str;
	lsa_str->Length = str_len * sizeof(WCHAR);
	lsa_str->MaximumLength = (str_len+1) * sizeof(WCHAR);
}

/**
 * @brief
 * 		add_privilege - add_privilege: returns 0 if privname has been added for account
 * 		referenced by sid; otherwise, 1.
 *
 * @param[in]	sid	-	The security identifier (SID) structure is a variable-length structure
 * 						 used to uniquely identify users or groups.
 * @param[in]	privname	-	privilege name
 *
 * @return	int
 * @retval	1	: if privname has not been added for account referenced by sid
 * @retval	0	: if privname has been added for account referenced by sid
 */
int
add_privilege(SID *sid, char *privname)
{
	LSA_UNICODE_STRING rights;
	LSA_HANDLE h_policy = INVALID_HANDLE_VALUE;
	LSA_OBJECT_ATTRIBUTES  obj_attrs;
	NTSTATUS lsa_stat;
	BOOL	rval = 1;
	WCHAR	*privnameW = NULL;
	int	priv_len = 0;

	if (privname == NULL) {
		fprintf(stderr, "add_privilege: NULL privname\n");
		return (1);
	}

	if (!IsValidSid(sid)) {
		fprintf(stderr, "add_privilege: Not a valid sid\n");
		return (1);
	}

	priv_len = strlen(privname) + 1;
	privnameW = (WCHAR *)malloc(priv_len * sizeof(WCHAR));

	if (privnameW == NULL) {
		fprintf(stderr, "add_privilege: malloc failed\n");
		return (1);
	}

	mbstowcs(privnameW, privname, priv_len);
	init_lsa_string(&rights, privnameW);

	ZeroMemory(&obj_attrs, sizeof(obj_attrs));
	if( LsaOpenPolicy(NULL, &obj_attrs, POLICY_ALL_ACCESS, &h_policy) \
							!= ERROR_SUCCESS ) {
		fprintf(stderr, "add_privilege: Unable to open policy!\n");
		goto add_privilege_end;
	}

	if( (lsa_stat=LsaAddAccountRights( h_policy, sid, &rights, 1 )) != \
							ERROR_SUCCESS ) {
		fprintf(stderr,
			"add_privilege: adding privilege %s failed! - err %d\n",
			privname, LsaNtStatusToWinError(lsa_stat));
		goto add_privilege_end;
	}

	printf("\tadded %s\n", privname);
	rval = 0;

add_privilege_end:
	if (h_policy != INVALID_HANDLE_VALUE)
		LsaClose(h_policy);

	if (privnameW != NULL)
		(void)free(privnameW);

	return (rval);
}

/**
 * @brief
 *  	register_scm - return 0 for success; non-zero for fail
 *
 * @param[in]	svc_name	-	service name
 * @param[in]	svc_exec	-	service executable path
 * @param[in]	svc_account	-	service account
 * @param[in]	svc_password	-	service password
 *
 * @return	int
 * @retval	0	: good to go!
 * @retval	1	: something bad happened.
 */
int
register_scm(char *svc_name, char *svc_exec, char *svc_account, char *svc_password)
{
	SC_LOCK   sclLock = NULL;
	SC_HANDLE schService = NULL;
	SC_HANDLE schSCManager = NULL;
	int	ret = 1;

	schSCManager = OpenSCManager(0, 0, SC_MANAGER_ALL_ACCESS);

	if (!schSCManager) {
		fprintf(stderr, "OpenSCManager failed - %d\n",
			GetLastError());
		goto register_scm_cleanup;
	}

	/* Get the SCM database lock before changing the password. */
	sclLock = LockServiceDatabase(schSCManager);
	if (sclLock == NULL) {
		fprintf(stderr, "LockServiceDatabase failed - %d\n",
			GetLastError());
		goto register_scm_cleanup;
	}
	/* Set the account and password that the service uses at */
	/* startup. */


	schService = CreateService(schSCManager, svc_name, __TEXT(svc_name),
		SERVICE_ALL_ACCESS,
		SERVICE_WIN32_OWN_PROCESS,
		SERVICE_AUTO_START, SERVICE_ERROR_NORMAL,
		replace_space(svc_exec, ""), 0, 0, 0,
		svc_account,
		svc_password);

	if (!schService) {
		fprintf(stderr,
			"CreateService(%s, path=%s, account=%s) failed - %d\n",
			svc_name, svc_exec, svc_account, GetLastError());
		goto register_scm_cleanup;
	}
	printf("\nCreated service %s with path=%s and account=%s\n",
		svc_name, svc_exec, svc_account);

	if (strcmpi(svc_name, "PBS_SCHED") == 0) {

		SERVICE_FAILURE_ACTIONS sfa;
		SC_ACTION               sca[1];


		sca[0].Type = SC_ACTION_RESTART;
		sca[0].Delay = 60*1000;
		sfa.dwResetPeriod = INFINITE;
		sfa.lpRebootMsg = NULL;
		sfa.lpCommand = NULL;
		sfa.cActions = 1;
		sfa.lpsaActions = sca;
		ChangeServiceConfig2(schService,
			SERVICE_CONFIG_FAILURE_ACTIONS, &sfa);

		printf("\nConfigured %s to restart on failure\n", svc_name);
	}
	ret = 0;
register_scm_cleanup:

	if (sclLock)
		UnlockServiceDatabase(sclLock);

	if (schService)
		CloseServiceHandle(schService);

	if (schSCManager)
		CloseServiceHandle(schSCManager);

	return (ret);
}


/**
 * @brief
 * 		unregister_scm - unregister_scm: return 0 for success; non-zero for fail
 *
 * @param[in]	svc_name	-	service name.
 *
 * @return	int
 * @retval	0	: success
 * @retval	non-zero	: fail
 */
int
unregister_scm(char *svc_name)
{
	SC_LOCK   sclLock = NULL;
	SC_HANDLE schService = NULL;
	SC_HANDLE schSCManager = NULL;
	int    	  ret = 1;
	SERVICE_STATUS ss;
	int	  try;

	schSCManager = OpenSCManager(0, 0, SC_MANAGER_ALL_ACCESS);

	if (!schSCManager) {
		fprintf(stderr, "OpenSCManager failed - %d\n",
			GetLastError());
		goto unregister_scm_cleanup;
	}

	/* Open a handle to the service instance. */
	schService = OpenService(schSCManager, svc_name,
		SERVICE_ALL_ACCESS);

	if (!schService) {
		fprintf(stderr, "OpenService %s failed - %d\n",
			svc_name, GetLastError());
		goto unregister_scm_cleanup;
	}

	/* Get the SCM database lock before changing the password. */
	sclLock = LockServiceDatabase(schSCManager);
	if (sclLock == NULL) {
		fprintf(stderr, "LockServiceDatabase failed - %d\n",
			GetLastError());
		goto unregister_scm_cleanup;
	}

	/* Stop the service first */
	ControlService(schService, SERVICE_CONTROL_STOP, &ss);

	try = 0;
	ss.dwCurrentState = SERVICE_RUNNING;
	while ((try < WAIT_RETRY_MAX) && ss.dwCurrentState != SERVICE_STOPPED) {
		printf("[try %d] waiting for service %s to die\n", try,
			svc_name);
		sleep(3);
		if (!QueryServiceStatus(schService, &ss))
			break;
		try++;
	}

	if (!DeleteService(schService)) {
		fprintf(stderr,
			"DeleteService(%s) failed - %d\n",
			svc_name, GetLastError());
		goto unregister_scm_cleanup;
	}
	printf("\nDeleted service %s\n", svc_name);
	ret = 0;

unregister_scm_cleanup:

	if (sclLock)
		UnlockServiceDatabase(sclLock);

	if (schService)
		CloseServiceHandle(schService);

	if (schSCManager)
		CloseServiceHandle(schSCManager);

	return (ret);
}
/**
 * @brief
 * 		prompt_to_get_password - prompt for password.
 *
 * @param[out]	pass	-	password.
 */
void
prompt_to_get_password(char pass[LM20_PWLEN+1])
{
	int ch, j;
	printf("Please enter password: ");
	j = 0;
	do {
		ch = _getch();
		if (ch == '\r' || ch == '\n')
			break;
		pass[j] = ch;
		j++;
	} while (j < LM20_PWLEN);

	pass[j] = '\0';
}
/**
 * @brief
 *  	validate_account_password: returns 1 if 'account's password is valid; 0
 *	 	 otherwise.
 *
 * @param[in]	account	-	account to be verified.
 * @param[in]	password	-	password for the account.
 *
 * @return	valid or not.
 * @retval	0	: account's password is invalid
 * @retval	1	: account's password is valid
 */
int
validate_account_password(char *account, char *password)
{
	STARTUPINFOW             si = { 0 };
	PROCESS_INFORMATION     pi = { 0 };
	int            		flags = CREATE_DEFAULT_ERROR_MODE|\
				CREATE_NEW_CONSOLE|CREATE_NEW_PROCESS_GROUP;
	int			rc;
	char			uname[UNLEN+1];
	char 			dname[PBS_MAXHOSTNAME+1];
	char 			*p = NULL;

	wchar_t			unamew[UNLEN+1];
	wchar_t			dnamew[PBS_MAXHOSTNAME+1];
	wchar_t			passwordw[LM20_PWLEN+1];


	strcpy(uname, account);
	strcpy(dname, "");

	if ((p=strstr((const char *)account, "\\"))) {
		*p = '\0';
		strcpy(dname, (const char *)account);
		*p = '\\';
		strcpy(uname, p+1);
	}

	mbstowcs(unamew, uname, UNLEN+1);
	mbstowcs(dnamew, dname, PBS_MAXHOSTNAME+1);
	mbstowcs(passwordw, password, LM20_PWLEN+1);

	si.cb = sizeof(si);
	si.lpDesktop = L"";

	if( !for_info_only && \
	     ((rc=CreateProcessWithLogonW(unamew, dnamew,
		passwordw, 0, NULL, L"cmd /c echo okay", flags,
		NULL, NULL, &si, &pi)) == 0)) {

		fprintf(stderr,
			"Password did not validate against %s err=%d\n\nClick BACK button to retry a different password.\nClick NEXT button to abort installation.", account, GetLastError());
		wcsset(passwordw, 0);
		return (0);
	}

	WaitForSingleObject(pi.hProcess, INFINITE);
	CloseHandle(pi.hProcess);
	CloseHandle(pi.hThread);

	printf("%s password for %s\n",
		(for_info_only?"Validating":"Validated"), account);

	wcsset(passwordw, 0);
	return (1);
}
/**
 * @brief
 * 		set_account_expiration - sets the expiry period for the account on the
 * 		specidied server.
 *
 * @param[in]	dnamew	-	account name
 * @param[in]	dctrlw	-	A pointer to a constant string that specifies
 * 							the DNS or NetBIOS name of the remote server
 * 							on which the function is to execute.
 * 							If this parameter is NULL, the local computer
 * 							is used.
 * @param[in]	unamew	-	A pointer to a constant string that specifies
 * 							the name of the user account for which to set
 * 							information.
 * @param[in]	expire	-	Specifies a DWORD value that indicates when the
 * 							user account expires.
 *
 * @return	int
 * @retval	0	: Set the account expiration date.
 * @retval	1	: Setting account expiration failed.
 */
int
set_account_expiration(wchar_t *dnamew, wchar_t *dctrlw, wchar_t *unamew, DWORD expire)
{
	USER_INFO_1017 ui;
	NET_API_STATUS nstatus;


	ui.usri1017_acct_expires = expire;

	if (for_info_only)
		nstatus = NERR_Success;
	else
		nstatus = NetUserSetInfo(dctrlw, unamew, 1017, (LPBYTE)&ui,
			NULL);

	if (nstatus == NERR_Success) {
		if (!for_info_only)
			fprintf(stderr,
				"Set account %S\\%S's expiration date\n",
				dnamew, unamew);
		return (0);
	}

	fprintf(stderr,
		"Setting account %S\\%S expiration failed = %d\n",
		dnamew, unamew, nstatus);
	return (1);

}

/**
 * @brief
 * 		set_account_primary_group - set the primary group for the account.
 *
 * @param[in]	dnamew	-	account name
 * @param[in]	dctrlw	-	A pointer to a constant string that specifies
 * 							the DNS or NetBIOS name of the remote server
 * 							on which the function is to execute.
 * 							If this parameter is NULL, the local computer
 * 							is used.
 * @param[in]	unamew	-	A pointer to a constant string that specifies
 * 							the name of the user account for which to set
 * 							information.
 * @param[in]	group_rid	-	Specifies a DWORD value that contains the
 * 							RID of the Primary Global Group for the user
 * 							specified in the username parameter to the
 * 							NetUserSetInfo function. This member must be
 * 							the RID of a global group that represents the
 * 							enrolled user.
 *
 * @return	int
 * @retval	0	: Set the account primary group.
 * @retval	1	: Setting account primary group failed.
 */
int
set_account_primary_group(wchar_t *dnamew, wchar_t *dctrlw, wchar_t *unamew, DWORD group_rid)
{
	USER_INFO_1051 ui;
	NET_API_STATUS nstatus;


	ui.usri1051_primary_group_id = group_rid;

	if (for_info_only)
		nstatus = NERR_Success;
	else
		nstatus = NetUserSetInfo(dctrlw, unamew, 1051, (LPBYTE)&ui,
			NULL);

	if (nstatus == NERR_Success) {
		if (!for_info_only)
			fprintf(stderr,
				"Set account %S\\%S's primary group\n",
				dnamew, unamew);
		return (0);
	}

	fprintf(stderr,
		"setting account %S\\%S's primary group failed = %d\n",
		dnamew, unamew, nstatus);
	return (1);

}

/**
 * @brief
 * 		add_to_administrators_group: returns 0 if 'dnamew\unamew' has been added
 *		to local "Administrators" group; 1 otherwise.
 *
 * @param[in]	dnamew	-	account name
 * @param[in]	unamew	-	A pointer to a constant string that specifies
 * 							the name of the user account for which to set
 * 							information.
 *
 * @return	int
 * @retval	0	: 'dnamew\unamew' has been added to local "Administrators" group.
 * @retval	1	: 'dnamew\unamew' could not add to local "Administrators" group.
 */
int
add_to_administrators_group(wchar_t *dnamew, wchar_t *unamew)
{
	SID	*gsid = NULL;
	char	*gname = NULL;	/* special group to add service account to */
	wchar_t full_unamew[PBS_MAXHOSTNAME+UNLEN+2]; /* domain\user\0 */
	int	ret_val = 1;

	gsid = create_administrators_sid();
	if (gsid && (gname=getgrpname(gsid))) {
		LOCALGROUP_MEMBERS_INFO_3 member;
		NET_API_STATUS nstatus;
		wchar_t gnamew[GNLEN+1];

		mbstowcs(gnamew, gname, GNLEN+1);

#if _MSC_VER >= 1400
		swprintf(full_unamew, PBS_MAXHOSTNAME+UNLEN+2, L"%s\\%s", dnamew, unamew);

#else
		swprintf(full_unamew, L"%s\\%s", dnamew, unamew);
#endif
		member.lgrmi3_domainandname = (wchar_t *)full_unamew;

		if (for_info_only)
			nstatus = NERR_Success;
		else
			nstatus=NetLocalGroupAddMembers(NULL, gnamew, 3,
				(LPBYTE)&member, 1);
		if( (nstatus == NERR_Success) || \
			(nstatus == ERROR_MEMBER_IN_ALIAS) ) {

			printf("%s %S to group \"%S\"\n",
				(for_info_only?"Adding":"Added"), full_unamew, gnamew);
			ret_val = 0;
		} else {
			fprintf(stderr,
				"Failed to add %S to group \"%S\": error status =%d\n",
				full_unamew, gnamew, nstatus);
		}
	}

	if (strlen(winlog_buffer) > 0) { /* any error in getdefgrpname() */
		fprintf(stderr, "%s\n", winlog_buffer);
	}

	if (gsid)
		LocalFree(gsid);
	else
		fprintf(stderr,
			"Failed to add %S\\%S to Administrators group: bad SID\n",
			dnamew, unamew);

	if (gname)
		(void)free(gname);
	else
		fprintf(stderr,
			"Failed to get Administrators's actual group name\n");



	return (ret_val);
}

/**
 * @brief
 *  	read_sa_password: callback "read" function to
 * 		cache_usertoken_and_homedir()
 * @param[in]	param	-	'param' is ignored here in purpose, but expected in arguments list
 *  						by some function that will call this.
 *
 * @param[out]	cred	-	sa_password
 * @param[out]	len	-	length of sa_password
 *
 * @return	int
 * @retval	0	: success
 */
int
read_sa_password(void *param, char **cred, size_t *len)
{
	*cred = sa_password;
	*len = strlen(sa_password);

	return (0);
}

/**
 * @brief
 * 		decrypt_sa_password: callback "decrypt" function to
 * 		cache_usertoken_and_homedir().
 * 		NOTE: *passwd expected to point to a malloced string  which must be
 * 		later freed.
 *
 * @param[in]	crypted	-	encrypted password
 * @param[in]	len	-	length of the password (not used here)
 * @param[out]	passwd	-	copy of crypted password.
 *
 * @return	int
 * @retval	0	: operation succeed.
 * @retval	1	: failed
 */
int
decrypt_sa_password(char *crypted, int credtype, size_t len, char **passwd)
{

	if ((*passwd=strdup(crypted)) == NULL) {
		return (1);
	}

	return (0);
}

/**
 * @brief
 * 		add_service_account: creates the PBS service account if it doesn't exist,
 *	 	otherwise, validate the password against the existing the service
 *		account.
 *
 * @param[in]	password	-	The password to be validated.
 *
 * @return	int
 */
int
add_service_account(char *password)
{
	char 	dname[PBS_MAXHOSTNAME+1] = {'\0'};
	char	dctrl[PBS_MAXHOSTNAME+1] = {'\0'};
	wchar_t	unamew[UNLEN+1] = {L'\0'};
	wchar_t	dnamew[UNLEN+1] = {L'\0'};
	wchar_t	dctrlw[PBS_MAXHOSTNAME+1] = {L'\0'};
	LPWSTR	dcw = NULL;
	char	dctrl_buf[PBS_MAXHOSTNAME+1] = {'\0'};

	NET_API_STATUS nstatus = 0;
	USER_INFO_1	*ui1_ptr = NULL; /* better indicator of lookup */
	/*  permission */
	struct passwd	*pw = NULL;

	char 	sa_name[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'}; /* service account fullname */
	/* domain\user\0 */
	int	ret_val = 0;
	int	in_domain_environment = 0;
	USER_INFO_1	ui = {0};
	wchar_t	passwordw[LM20_PWLEN+1] = {L'\0'};

	/* find domain name, group name to add service account to */
	in_domain_environment = GetComputerDomainName(dname);

	strcpy(dctrl, dname);
	if (in_domain_environment) {
		char	dname_a[PBS_MAXHOSTNAME+1] = {'\0'};

		get_dcinfo(dname, dname_a, dctrl);
	}

	mbstowcs(unamew, service_accountname, UNLEN+1);
	mbstowcs(dnamew, dname, PBS_MAXHOSTNAME+1);
	mbstowcs(dctrlw, dctrl, PBS_MAXHOSTNAME+1);

	if (in_domain_environment && dctrlw[0] == '\0' ) {
		if (NERR_Success == NetGetDCName(NULL, dnamew, (LPBYTE *)&dcw)) {
			wcstombs(dctrl_buf, dcw, PBS_MAXHOSTNAME + 1);
			mbstowcs(dctrlw, dctrl_buf, PBS_MAXHOSTNAME + 1);
			
		} else {	
			fprintf(stderr, "Failed to fetch domain controller name");
			goto end_add_service_account;
		}
	}

	/* create account if it doesn't exist */

	/* FIX: Perform the following "if action" if either           */
	/*   1) in a domain environment, and the 		      */
	/*      executing account (i.e. intaller) is an account in    */
	/*      the domain,            				      */
	/*   2) in a standalone environment, and the                  */
	/*      executing account (i.e. installer) is a local account */
	/*      in the local computer.                                */
	/* This fix is needed as during testing, I was finding that   */
	/* the local "Administrator" account itself has permission    */
	/* to query the domain, and to create accounts on the domain. */
	/* However, the created domain "pbsadmin" account would have  */
	/* weirdness to it in that attempts to impersonate it would   */
	/* initially fail, and even after adding the account to the   */
	/* local "Administrators" group, that user entry on the group */
	/* would  suddenly disappear.                                 */

	if ((stricmp(exec_dname, dname) == 0) &&
		((nstatus=wrap_NetUserGetInfo(dctrlw, unamew, 1,
		(LPBYTE *)&ui1_ptr)) == NERR_UserNotFound)) {
		mbstowcs(passwordw, password, LM20_PWLEN+1);
		ui.usri1_name = (wchar_t *)unamew;
		ui.usri1_password = (wchar_t *)passwordw;
		ui.usri1_password_age = 0;
		ui.usri1_priv = USER_PRIV_USER;
		ui.usri1_home_dir = NULL;
		ui.usri1_comment = NULL;
		ui.usri1_flags = UF_PASSWD_CANT_CHANGE|UF_DONT_EXPIRE_PASSWD;
		ui.usri1_script_path = NULL;

		if (for_info_only)
			nstatus = NERR_Success;
		else
			nstatus=NetUserAdd(dctrlw, 1, (LPBYTE)&ui, NULL);

		if ((nstatus != NERR_Success) && (nstatus != NERR_UserExists)) {
			fprintf(stderr,
				"Failed to create %s\\%S: error status=%d\n", dname,
				unamew, nstatus);
			goto end_add_service_account;
		}
		printf("%s account %s\\%S\n",
			(for_info_only?"Creating":"Created"), dname, unamew);

		set_account_expiration(dnamew, dctrlw, unamew,
			TIMEQ_FOREVER);

		/* cache new token since the account was just created */
		cache_usertoken_and_homedir(service_accountname, NULL,
			0, read_sa_password, (char *)service_accountname,

			decrypt_sa_password, 1);

		if (add_to_administrators_group(dnamew, unamew) != 0)
			goto end_add_service_account;


	}

	/* Verify password */

	if (pw == NULL) {
		pw = getpwnam(service_accountname);
		if (pw == NULL) {
			fprintf(stderr, "Password could not be validated against %s\\%s.\n", dname, service_accountname);
			goto end_add_service_account;
		}
	}
	/* validate password */
	sprintf(sa_name, "%s\\%s", dname, service_accountname);

	if (!for_info_only) {

		if (pw->pw_userlogin != INVALID_HANDLE_VALUE) {
			if (ImpersonateLoggedOnUser(pw->pw_userlogin) == 0) { /* fail */
				if (validate_account_password(sa_name, password) == 0) {

					/* we still call validate_account_password() as backup since  */
					/* under Windows 2000, LogonUser(), called from		      */
					/* cache_usertoken_and_homedir(), might fail due to not       */
					/* having the  SE_TCB_NAME privilege. This must be            */
					/* already set before calling the "cmd" process that 	      */
					/* executes the install program.		     	      */

					fprintf(stderr, "Password did not validate against %s\\%s err=%d\n\nClick BACK button to retry a different password.\nClick NEXT button to abort installation.", dname, service_accountname, GetLastError());
					goto end_add_service_account;
				}
			} else {
				printf("Validated password for %s\n", sa_name);
				RevertToSelf();
			}
		}
	} else {
		printf("Validating password for %s\n", sa_name);
	}

	/* add service account to appropriate Admin group */
	if (!for_info_only && !isLocalAdminMember(service_accountname)) {

		if (add_to_administrators_group(dnamew, unamew) != 0)
			goto end_add_service_account;

	}


	wcsset(passwordw, 0);
	ret_val = 1;

	if (for_info_only) {
		printf("%s will need the following privileges:\n", sa_name);
		printf("\n\tCreate Token Object\n");
		printf("\n\tReplace Process Level Token\n");
		printf("\n\tLogon On As a Service\n");
		printf("\n\tAct As Part of the Operating System\n");
	}

end_add_service_account:

	if (ui1_ptr != NULL)
		NetApiBufferFree(ui1_ptr);

	return (ret_val);

}
/**
 * @brief
 * 		usage - shows the usage of the module
 *
 * @param[in]	prog	-	Program name
 */
void
usage(char *prog)
{
	fprintf(stderr,
		"%s [-c] [-s] [-a service_account_name] [-p password] [--instid instance_name] [--reg service_path] [--unreg service_path] [-o output_path] [--ci]\n", prog);

	fprintf(stderr,
		"\n\twhere\t-c is for creating the service account\n");

	fprintf(stderr,
		"\n\t\t-s is for adding necessary privileges to the service account\n");

	fprintf(stderr,
		"\n\t\t-a is for specifying a service account name\n");

	fprintf(stderr,
		"\n\t\t-p is for specifying the service account password\n");
	fprintf(stderr,
		"\n\t\t--instid is for specifying the instance id\n");
	fprintf(stderr,
		"\n\t\t--reg to register the service_path program with SCM\n");
	fprintf(stderr,
		"\n\t\t--unreg to unregister the service path program with SCM\n");
	fprintf(stderr,
		"\n\t\t-o to print stdout and stderr messages in output_path\n");
	fprintf(stderr,
		"\n\t\t--ci to print %s's -c actions (informational only)\n", prog);
	fprintf(stderr,
		"\n\tNOTE: Without any arguments, %s prints out name\n\t\tof service account (if it exists) with exit value of 0\n", prog);
	fprintf(stderr,
		"\nExamples:\n");
	fprintf(stderr,
		"\tTo create the PBSADMIN account:\n\t\t%s -c -s -p password\n\n",
		prog);
	fprintf(stderr,
		"\tTo register a service with SCM:\n\t\t%s --reg service_path -p password\n\n",
		prog);
	fprintf(stderr,
		"\tTo un-register a service with SCM:\n\t\t%s --unreg service_path\n\n",
		prog);
}
/**
 * @brief
 * 		main - the entry point in pbs_account_win.c
 *
 * @param[in]	argc	-	argument count
 * @param[in]	argv	-	argument variables.
 * @param[in]	env	-	environment values.
 *
 * @return	int
 * @retval	0	: success
 * @retval	!=0	: error code
 */
main(int argc, char *argv[])
{

	SID 	*sa_sid = NULL;	/* service account SID */
	char 	sa_name[PBS_MAXHOSTNAME+UNLEN+2] = {'\0'}; /* service account name */
	/* domain\user\0 */

	int	ret_val = 0;
	int 	c_opt = 0;
	int	s_opt = 0;
	int	a_opt = 0;
	int	p_opt = 0;
	int	R_opt = 0;
	int	U_opt = 0;
	int instid_opt = 0;
	char	service_bin_path[MAXPATHLEN+1] = {'\0'};
	char	service_name[MAXPATHLEN+1] = {'\0'};
	int	i = 0;
	char	outputfile[MAXPATHLEN+1] = {'\0'};
	char	instanceName[MAXPATHLEN+1] = {'\0'};
	int	output_fd = -1;
	struct	passwd	*pw = NULL;
	char	*p = NULL;

	winsock_init();

	/*test for real deal or just version and exit*/
	execution_mode(argc, argv);

	strcpy(exec_unamef, getlogin_full());
	strcpy(exec_dname, ".");

	if ((p=strchr(exec_unamef, '\\'))) {
		*p = '\0';
		strcpy(exec_dname, exec_unamef);
		*p = '\\';
	}

	strcpy(sa_password, "");
	strcpy(outputfile, "");

	/* with no option, check only if service account exists */
	if (argc == 1) {
		int     in_domain_environment = 0;
		char    dname[PBS_MAXHOSTNAME+1] = {'\0'};
		char    dctrl[PBS_MAXHOSTNAME+1] = {'\0'};
		wchar_t unamew[UNLEN+1] = {'\0'};
		wchar_t dctrlw[PBS_MAXHOSTNAME+1] = {'\0'};
		USER_INFO_0     *ui1_ptr = NULL;
		NET_API_STATUS	netst = 0;

		/* figure out the domain controller hostname (dctrl) */
		/* in domain environment,                            */
		/*         domain name (dname) != domain controller hostname */
		/* in standalone environment,                                */
		/*         domain name (dname) == domain controller hostname */

		in_domain_environment = GetComputerDomainName(dname);
		strcpy(dctrl, dname);
		if (in_domain_environment) {
			char    dname_a[PBS_MAXHOSTNAME+1];

			get_dcinfo(dname, dname_a, dctrl);
		}
		/* convert strings to "wide" format */

		mbstowcs(unamew, service_accountname, UNLEN+1);
		mbstowcs(dctrlw, dctrl, PBS_MAXHOSTNAME+1);

		netst = wrap_NetUserGetInfo(dctrlw, unamew, 1,
			(LPBYTE *)&ui1_ptr);

		if (strlen(winlog_buffer) > 0) {
			fprintf(stderr, "%s\n", winlog_buffer);
		}
		if (netst == NERR_UserNotFound) {
			fprintf(stderr, "%s not found!\n", service_accountname);
			if (in_domain_environment &&
				stricmp(exec_dname, dname) != 0) {
				fprintf(stderr,
					"But no privilege to create service account %s\\%s!\n",
					dname, service_accountname);
				ret_val=2;
			} else {
				ret_val=1;
			}
		} else if ((netst == ERROR_ACCESS_DENIED) ||
			(netst == ERROR_LOGON_FAILURE)) {
			fprintf(stderr,
				"no privilege to obtain info for service account %s\\%s!\n",
				dname, service_accountname);
			ret_val= 2;
		} else {
			fprintf(stderr, "service account is %s\\%s!\n",
				dname, service_accountname);

			ret_val = 0;
		}

		if (ui1_ptr != NULL)
			NetApiBufferFree(ui1_ptr);

		goto end_pbs_account;
	}

	i = 1;
	while (i < argc) {

		if (strcmp(argv[i], "-c") == 0) {
			c_opt = 1;
			i++;
		} else if (strcmp(argv[i], "--ci") == 0) {
			c_opt = 1;
			for_info_only = 1;
			i++;
		} else if (strcmp(argv[i], "-s") == 0) {
			s_opt = 1;
			i++;
		} else if (strcmp(argv[i], "-a") == 0) {
			if ((argv[i+1] == NULL) || (argv[i+1][0] == '-')) {
				fprintf(stderr, "No service account name argument supplied!\n");
				usage(argv[0]);
				exit(1);
			}
			a_opt = 1;
			strcpy(service_accountname, argv[i+1]);
			i+=2;
		} else if (strcmp(argv[i], "-p") == 0) {
			if ((argv[i+1] == NULL) || (argv[i+1][0] == '-')) {
				fprintf(stderr, "No password argument supplied!\n");
				usage(argv[0]);
				exit(1);
			}

			p_opt = 1;
			strcpy(sa_password, argv[i+1]);
			cache_usertoken_and_homedir(service_accountname, NULL, 0,
				read_sa_password, (char*)service_accountname,
				decrypt_sa_password, 1);
			i+=2;
		} else if (strcmp(argv[i], "--reg") == 0) {
			if ((argv[i+1] == NULL) || (argv[i+1][0] == '-')) {
				fprintf(stderr, "No service binary path given\n");
				usage(argv[0]);
				exit(1);
			}

			R_opt = 1;
			strcpy(service_bin_path, argv[i+1]);
			i+=2;
		} else if (strcmp(argv[i], "--unreg") == 0) {
			if ((argv[i+1] == NULL) || (argv[i+1][0] == '-')) {
				fprintf(stderr, "No service binary path given\n");
				usage(argv[0]);
				exit(1);
			}

			U_opt = 1;
			strcpy(service_bin_path, argv[i+1]);
			i+=2;
		} else if (strcmp(argv[i], "-o") == 0) {
			if ((argv[i+1] == NULL) || (argv[i+1][0] == '-')) {
				fprintf(stderr, "No output path argument supplied!\n");
				usage(argv[0]);
				exit(1);
			}

			p_opt = 1;
			strcpy(outputfile, argv[i+1]);
			i+=2;
		} else if (strncmp(argv[i], "--instid", strlen("--instid")) == 0) {
			if ((argv[i+1] == NULL) || (argv[i+1][0] == '-')) {
				fprintf(stderr, "No instance id supplied!\n");
				usage(argv[0]);
				exit(1);
			}

			instid_opt = 1;
			strncpy(instanceName, argv[i+1], MAXPATHLEN);
			i+=2;
		} else {
			fprintf(stderr, "Unknown option %s\n", argv[i]);
			usage(argv[0]);
			exit(1);
		}
	}

	if (strlen(outputfile) > 0) {

		if ((output_fd=open(outputfile, O_RDWR|O_CREAT, 0600)) != -1) {
			_dup2(output_fd, 1);	/* put stdout in file */
			_dup2(output_fd, 2);	/* put stderr in file */
		}
	}



	/* prompt for password if not supplied with -p */
	if ((c_opt || R_opt) && (strcmp(sa_password, "") == 0)) {
		prompt_to_get_password(sa_password);
		cache_usertoken_and_homedir(service_accountname, NULL, 0,
			read_sa_password, (char *)service_accountname,
			decrypt_sa_password, 1);
	}

	/* Need to  get service_name */
	if (R_opt || U_opt) {
		char *p = NULL;
		int  k = 0;

		strcpy(service_name, service_bin_path);
		if ((p=strrchr(service_bin_path, '\\'))) {
			strcpy(service_name, p+1);
		}
		if ((p=strrchr(service_name, '.'))) {/*remove .exe portion*/
			*p = '\0';
		}
		/* translate from lower-case to upper-case */
		for (k=0; k < strlen(service_name); k++) {
			service_name[k] = toupper(service_name[k]);
		}

		if (instid_opt) {
			strcat_s(service_name, MAXPATHLEN, "_");
			strcat_s(service_name, MAXPATHLEN, instanceName);
		}
	}

	if (c_opt) {
		if (add_service_account(sa_password) == 0) {
			ret_val = 3;
			goto end_pbs_account;
		}
	}

	if (s_opt || R_opt) { /* need service account name */
		sa_sid = getusersid2(service_accountname, sa_name);
		if (sa_sid == NULL) {
			fprintf(stderr, "%s not found!\n", service_accountname);
			ret_val= 1;
			goto end_pbs_account;
		}

		if (!isAdminPrivilege(service_accountname)) {
			fprintf(stderr, "%s is not ADMIN! - %s\n",
				service_accountname, winlog_buffer);
			ret_val = 2;
			goto end_pbs_account;
		}

	}


	if (s_opt) {
		int r1, r2, r3, r4;

		printf("Setting the following privileges to %s:\n", sa_name);

		r1 = add_privilege(sa_sid, SE_CREATE_TOKEN_NAME);

		r2 = add_privilege(sa_sid, SE_ASSIGNPRIMARYTOKEN_NAME);

		r3 = add_privilege(sa_sid, SE_SERVICE_LOGON_NAME);

		r4 = add_privilege(sa_sid, SE_TCB_NAME);

		if ((r1 != 0) || (r2 != 0) || (r3 != 0) || (r4 != 0)) {
			ret_val = 4;
			goto end_pbs_account;
		}
	}

	if (R_opt) {

		ret_val = register_scm(__TEXT(service_name), service_bin_path,
			sa_name, sa_password);
	}

	if (U_opt) {
		ret_val = unregister_scm(__TEXT(service_name));
	}

end_pbs_account:
	if (sa_sid != NULL)
		LocalFree(sa_sid);

	if (strlen(sa_password) > 0)
		memset((char *)sa_password, 0, strlen(sa_password));

	if (output_fd != -1)
		(void)close(output_fd);

	exit(ret_val);
}

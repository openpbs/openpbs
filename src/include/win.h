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
/* windows 2000 specific */
#ifndef	_PBS_WIN_H
#define _PBS_WIN_H

#include "windows.h"
#include "list_link.h"
#include <lm.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/locking.h>
#include <share.h>
#include <fcntl.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <io.h>
#include <process.h>
#include <stdarg.h>
#include <stdio.h>
#include <wtypes.h>
#include <varargs.h>
#include <stddef.h>

#ifdef _timezone
#define _zonetime _timezone
#undef _timezone
#endif

#define F_DUPFD         0       /* dup */
#define _POSIX_PATH_MAX _MAX_PATH

#define uint		UINT
#define sleep(x)	(Sleep(x*1000))	/* in Win32, Sleep parameter is in milliseconds */
#define	strcasecmp	stricmp
#define strncasecmp	strnicmp
#ifndef HAVE_SNPRINTF
#define HAVE_SNPRINTF 1
#endif
#define snprintf	_snprintf
#define isatty		_isatty
#define getpid		_getpid
#define close		_close
#define getcwd		_getcwd
#define strdup		_strdup
#define unlink		_unlink
#define setmode		_setmode
#define strtok		win_strtok
#define write		_write
#define read		_read
#define fileno		_fileno
#define strnicmp	_strnicmp
#define umask		win_umask
#define stricmp		_stricmp
#define strcmpi		_strcmpi
#define rmdir		_rmdir
#define mktemp		win_mktemp
#define mkstemp		win_mktemp
#define _mktemp		win_mktemp
#define lseek		_lseek
#define dup2		_dup2
#define access		_access
#define chmod		_chmod
#define dup		_dup
#define open		win_open
#define _open		win_open
#define sscanf		sscanf_s
#define fopen		win_fopen
#define freopen		win_freopen
#define	fscanf		fscanf_s
#define fdopen		_fdopen
#define strerror	win_strerror
#define wcsicmp		_wcsicmp
#define localtime	win_localtime
#define ctime		win_ctime
#define chdir		_chdir
#define popen		_popen
#define pclose		_pclose
#define pipe(h)		_pipe((h), 256, O_BINARY)
#undef	mkdir
#define mkdir(a, b)	_mkdir(a)
#define	strtok_r	strtok_s
#define creat(path, mode)	win_open((path), O_CREAT|O_WRONLY|O_TRUNC, (mode))
#define _creat(path, mode)	win_open((path), O_CREAT|O_WRONLY|O_TRUNC, (mode))
#define strtoll _strtoi64
#define strtoull _strtoui64

#pragma warning(disable:4996) /* disable CRT secure warning */

#define SIGKILL	0
#define SIGSTOP	17
#define SIGCONT	18
#ifdef _CRT_NO_POSIX_ERROR_CODES
#define EADDRINUSE WSAEADDRINUSE
#define ETIMEDOUT WSAETIMEDOUT
#define ECONNREFUSED WSAECONNREFUSED
#define ENETUNREACH WSAENETUNREACH
#define EWOULDBLOCK WSAEWOULDBLOCK
#define ENOTCONN WSAENOTCONN
#define ENOBUFS WSAENOBUFS
#define EADDRNOTAVAIL WSAEADDRNOTAVAIL
#endif
#define PBS_CMDLINE_LENGTH 4096
enum operation {
	RESUME=0,	/* Resume Process Operation */
	SUSPEND,	/* Suspend Process Operation */
	TERMINATE,	/* Terminate Process Operation */
	UNKNOWN		/* Unknown Process Operation */
};

extern int processtree_op_by_id(DWORD process_ID, enum operation op, int exitcode);
extern int processtree_op_by_handle(HANDLE hProcess, enum operation op, int exitcode);

/* on windows its __FUNCTION__ instead of __func__ */
#define __func__ __FUNCTION__

/*
 **	Put stat macros here for now.
 */

#define S_IRUSR	0400		/* Read by owner.  */
#define S_IWUSR	0200		/* Write by owner.  */
#define S_IXUSR	0100		/* Execute by owner.  */
/* Read, write, and execute by owner.  */
#define S_IRWXU (S_IRUSR|S_IWUSR|S_IXUSR)

#define S_IRGRP (S_IRUSR >> 3)  /* Read by group.  */
#define S_IWGRP (S_IWUSR >> 3)  /* Write by group.  */
#define S_IXGRP (S_IXUSR >> 3)  /* Execute by group.  */

/* Read, write, and execute by group.  */
#define S_IRWXG (S_IRWXU >> 3)

#define S_IROTH (S_IRGRP >> 3)  /* Read by others.  */
#define S_IWOTH (S_IWGRP >> 3)  /* Write by others.  */
#define S_IXOTH (S_IXGRP >> 3)  /* Execute by others.  */
/* Read, write, and execute by others.  */
#define S_IRWXO (S_IRWXG >> 3)

#define S_ISDIR(m)	((m & _S_IFMT) == _S_IFDIR)	/* directory */
#define S_ISREG(m)	((m & _S_IFMT) == _S_IFREG)	/* regular file */
#define S_ISLNK(m)	(0)

#define STDIN_FILENO _fileno(stdin)
#define STDERR_FILENO _fileno(stderr)

#define F_WRLCK _LK_NBLCK
#define F_RDLCK _LK_NBRLCK
#define F_UNLCK _LK_UNLCK

extern int link(const char *oldpath, const char *newpath);
long int gethostid(void);
#define crypt(b, s) DES_crypt((b), (s))

/* getopt() mimic */
extern char	*optarg;
extern int 	optind;
extern int	opterr;
extern int	optopt;
extern int getopt(int, char **, const char *);

/* mimic popen stuff */
typedef struct pio_handles {
	HANDLE hWritePipe_out;
	HANDLE hReadPipe_out;
	HANDLE hWritePipe_err;
	HANDLE hReadPipe_err;
	HANDLE hWritePipe_in;
	HANDLE hReadPipe_in;
	HANDLE hJob;
	PROCESS_INFORMATION pi; /* process information */
} pio_handles;
/* control the process created by win_popen() */
typedef struct proc_ctrl {
	BOOL need_ptree_termination; /* if TRUE, the process tree needs to be terminated along-with the process */
	/* Note: if this flag is set to TRUE, you can't put the process into another job object */
	BOOL bInheritHandle; /* if TRUE, the child process should inherit handles from the parent */
	BOOL bnowait; /* if TRUE, after creating the process, don't wait for the process to finish  */
	BOOL buse_cmd; /* if TRUE, open a new command shell to launch the process */
	DWORD flags; /* specify process flags */
	int  is_current_path_network;
} proc_ctrl;

/* returns nonzero for success; 0 otherwise */
extern int win_popen(char *cmd, const char *type, pio_handles *pio, proc_ctrl *proc_info);
extern int win_pread(pio_handles *pio, char *output, int len);
extern int win_pread2(pio_handles *pio);
extern int win_pwrite(pio_handles *pio, char *output, int len);
extern void win_pclose(pio_handles *pio);	/* closes all handles */
extern void win_pclose2(pio_handles *pio);	/* closes all handles except process handle */
/*Secure Functions */
extern char* win_strtok(char *strToken, const char *strDelimit);
extern FILE* win_fopen(const char *filename, const char *mode);
extern int win_open(const char *filename, int oflag, ...);
extern char* win_getenv(const char *varname);
extern int win_putenv(const char *varname);
extern int win_umask(int pmode);
extern char* win_strerror(int errnum);
extern struct tm *win_localtime(const time_t *timer);
extern char* win_ctime(const time_t *timer);
extern wchar_t* win_wcsset(wchar_t *str, wchar_t c);
extern char* win_mktemp(char *fname_pattern);
extern FILE* win_freopen(const char *path, const char *mode, FILE *stream);


/* account - related stuff */
#ifndef _MAX_GROUPS
#define	_MAX_GROUPS	50		/* default # of groups (local or global) a user can belong to */
#endif

#define uid_t	SID *
#define gid_t	SID *

struct passwd {
	char	*pw_name;
	char	*pw_passwd;
	uid_t	pw_uid;
	gid_t	pw_gid;
	char	*pw_gecos;
	char	*pw_dir;
	char	*pw_shell;
	HANDLE	pw_userlogin;		/* special under windows */
	pbs_list_link pw_allpasswds;
};

extern struct passwd *getpwnam(const char *name);
extern struct passwd *getpwuid(uid_t uid);
extern struct passwd *logon_pw(char *username, char *credb, size_t credl,
	int (*decrypt_func)(char *, int, size_t, char **), int use_winsta,  char msg[]);

extern void cache_usertoken_and_homedir(char *user, char *pass,
	size_t passl, int (*read_password_func)(void *, char **, size_t *),
	void *param, int (*decrypt_func)(char *, int, size_t, char **), int force);

extern SID	*getusersid(char *uname);	/* free this with LocalFree() */
extern SID	*getusersid2(char *uname, char realuser[]); /* free this with LocalFree() */
extern char *getusername(SID *sid);	/* free with free() */
extern char *getusername_full(SID *sid);/* returns <domain>\<user>; free with free() */
extern SID	*getgrpsid(char *name);	/* free this with LocalFree() */
extern char *getgrpname(SID *sid);	/* free with free() */
extern char *getgrpname_full(SID *sid); /* returns <domain>\<group>; free with free() */
extern char     *getlogin(void);                /* chars are in a static area */
/* returns <user>	      */
extern char     *getlogin_full(void);           /* chars are in a static area */
/* returns <domain>\<user>    */
extern char	*getHomedir(char *user);	/* return the homedir of user */
/* return value must be free()*/
extern char	*getRhostsFile(char *user, HANDLE userlogin);
/* returns .rhosts file path */
/* return value is static */
extern char	*map_unc_path(char *path, struct passwd *pw);
extern void	unmap_unc_path(char *path);
extern int is_network_drive_path(char *path);
extern char	*default_local_homedir(char *user, HANDLE usertoken,
	int ret_profile_path);
extern char	*get_profile_path(char *username, HANDLE userlogin);

extern SID *sid_dup(SID *src_sid);
extern char *getdefgrpname(char *username);	/* free with free() */
extern SID  *getdefgrpsid(char *username);	/* free with LocalFree() */
extern SID	*getuid(void);			/* do not LocalFree() return */
/* value unless you want it */
/* regenerated. */
extern SID  *getgid(void);			/* do not LocalFree() return */
/* value unless you want it  */
/* regenerated */
extern int	getgids(char *user, SID *grp[], DWORD rids[]);	/* each member of grp must be LocalFree() */
extern int	setgroups(int size, SID *grp[]);	/* each member of grp must be LocalFree() */
extern int	isMember(char *user, char *group);
extern int	isLocalAdminMember(char *user);
extern DWORD 	sid2rid(SID *sid);
extern int	isAdminPrivilege(char *user);
extern int	sidIsAdminPrivilege(SID *sid);
extern int	inGroups(char *gname, SID *gidlist[], int len);
extern SID	*create_domain_admins_sid(void);  /* must free with LocalFree() */
extern SID	*create_domain_users_sid(void);  /* must free with LocalFree() */
extern SID	*create_administrators_sid(void); /* must free with LocalFree() */
extern int	GetComputerDomainName(char domain_name[]);
extern int	get_dcinfo(char *net_name, char domain_name[], char domain_ctrl[]);
extern SID*	create_everyone_sid(void);
extern HANDLE LogonUserNoPass(char *username);
extern BOOL impersonate_user(HANDLE hlogintoken);
extern BOOL revert_impersonated_user();
extern int setuser(char *username);
extern int setuser_with_password(char *username, char *cred_buf,
	size_t cred_len, int (*decrypt_func)(char *, int, size_t, char **));
extern HANDLE setuser_handle(void);
extern void setuser_close_handle(void);
extern int setuid(uid_t uid);	/* mimics UNIX call */

extern DWORD get_activesessionid(int return_on_no_active_session, char *username);
extern HANDLE get_activeusertoken(DWORD activesessionid);
extern char *get_usernamefromsessionid(DWORD sessionid, char** p_username);
extern char *get_processowner(DWORD processid, uid_t *puid, char *puname, size_t uname_len, char *comm, size_t comm_len);


#define WRITES_MASK (FILE_WRITE_DATA|FILE_ADD_FILE|FILE_APPEND_DATA|FILE_ADD_SUBDIRECTORY|FILE_WRITE_EA|FILE_DELETE_CHILD|FILE_WRITE_ATTRIBUTES)
#define READS_MASK	(FILE_READ_DATA|FILE_LIST_DIRECTORY|FILE_READ_EA|FILE_EXECUTE|FILE_TRAVERSE|FILE_READ_ATTRIBUTES)

struct accessinfo {
	char *group;
	ACCESS_MASK	mask;
};

extern void accessinfo_init(struct accessinfo *acc, int len);
extern int accessinfo_add(struct accessinfo *acc, int len, char *group, int mask);
extern int  accessinfo_mask_allzero(struct accessinfo *acc, int len);
extern void accessinfo_free(struct accessinfo *acc, int len);
extern char *accessinfo_values(struct accessinfo *acc, int len);
extern int perm_granted_admin_and_owner(char *path, int mask, char *owner, char *errmsg);
extern int perm_granted(char *path, int mask, char *user, char realuser[]);
extern int secure_file(char *path, char *user, ACCESS_MASK mask);
extern int secure_file2(char *path, char *user, ACCESS_MASK mask, char *user2, ACCESS_MASK mask2);
extern void fix_perms(char *fname);
extern void fix_perms2(char *fname1, char *fname2);
extern void make_dir_files_service_account_read(char *path);

extern int fcntl(int fd, int cmd, long arg);
extern char *realpath(const char *path, char *resolved_path);
extern int lstat(const char *file_name, struct stat *buf);


/* refers to windows - net functions */
extern int winsock_init(void);
extern void winsock_cleanup(void);

/* refers to directory manipulation routines */
#define	DIR_BEGIN	0
#define	DIR_MIDDLE	1
#define	DIR_END		2

/*
 **	Misc stuff left out of WIN32
 */
#define R_OK	04	/* Test for Read permission */
#define W_OK	02	/* Test for Write permission */
#define X_OK	01	/* Test for eXecute permission */
#define F_OK	00	/* Test for existence of File */


struct dirent {
	char	d_name[_MAX_PATH];
};

struct dir {
	HANDLE			handle;
	int			   pos;
	struct	dirent *entry;
};

typedef struct dir DIR;

extern DIR *opendir(const char *name);
extern struct dirent *readdir(DIR *);
extern int closedir(DIR *dir);

/* pid related stuff */
#define WNOHANG 1
#ifndef LINKS_PYTHON
#define pid_t	int
#else
#include "python.h"
#endif
#define WIFEXITED(s)		(s >= 0)
#define WEXITSTATUS(s)		(s)
#define BASE_SIGEXIT_CODE      256
#define kill		killpid

extern int initpids(void);
extern int addpid(HANDLE pid);
extern int closepid(HANDLE pid);
extern void destroypids(void);
extern HANDLE waitpid(HANDLE pid, int *statp, int opt);
extern int	killpid(HANDLE pid, UINT sig);

/* ruserok mimic */
extern int ruserok(const char *rhost, int superuser, const char *ruser, const char *luser);
extern int rcmd(char **ahost, unsigned short rport, const char *locuser, const char *remuser, const char *cmd, int *fd2p);
extern int rcmd2(char **ahost, unsigned short rport, const char *locuser, const char *remuser, char *passb, size_t passl, const char *cmd, int *fd2p);

/* slash translators - to be used particularly with results of environment variables */
extern void back2forward_slash(char *str);
extern void back2forward_slash2(char *str);
extern void forward2back_slash(char *str);
extern char *replace_space(char *str, char *repl);
extern char *lpath2short(char *str);	/* static area returned */
extern void lpath2short_B(char *str);
extern char *shorten_and_cleanup_path(char *path);

extern void fix_temp_path(char tmp_name[]);
/* stuff that makes life easier for creating the daemons into a service */

struct arg_param {
	int	argc;
	char **argv;
};
extern BOOL is_64bit_Windows(void);
extern int get_cmd_shell(char *cmd, int cmd_len);
extern char *get_win_rootdir(void);
extern void ErrorMessage(char *str);
extern struct arg_param *create_arg_param(void);
extern void free_arg_param(struct arg_param *p);
extern void print_arg_param(struct arg_param *p);

/* win_alarm: calls func() after specified # of timeout_secs have expired.
 Specify 0 for timeout_secs to reset alarm */
extern unsigned int win_alarm(unsigned int timeout_secs, void (*func)(void));

extern void get_token_info(HANDLE htok,
	char **user,
	char **owner,
	char **group,
	char **groups,
	char **privs,
	char **dacl,
	char **source,
	char **type);


extern int wsystem(char *cmdline, HANDLE user_handle);

/* Saving/restoring environment */
#define ENV_BUF_SIZE            32767 /* max size of buffer for return value of GetEnvironmentVariable */

#define getenv _getenv_win
#define setenv _setenv_win

extern void save_env(void);
extern int _setenv_win(char *key, char *value, int overwrite);
extern char *_getenv_win(char *key);
extern char *get_saved_env(char *e);
extern int create_env_avltree();
extern void update_env_avltree();
extern void destroy_env_avltree();

/* Privileges */
extern int has_privilege(char *);
extern int ena_privilege(char *);

/* Modify window staiion and desktop privilege */
extern int use_window_station_desktop(SID *usid);

extern int use_window_station_desktop2(char *user);

/* Services related routine */
#define SERVICE_ACCOUNT "pbsadmin"

extern void make_server_auto_restart(int confirm);


typedef struct {

	int	fd;
	char	*pos;	 /* current position in buffer */
	char	*end;	 /* last position in buffer */
	char	*content;
} MY_FILE;

extern MY_FILE *my_fopen(const char *filename, const char * mode);
extern char *my_fgets(char *buf, int n, MY_FILE *stream);
extern int my_fclose(MY_FILE *stream);

/* Various routines related to securing PBS files */

void secure_server_files();
void secure_mom_files();
void secure_sched_files();
void secure_rshd_files();
void secure_misc_files();
void secure_exec_files();

/* Mimic file-specific information */

#define _PC_PATH_MAX 4

/* Get file-specific configuration information about PATH.  */
extern long int pathconf(const char *__path, int __name);

/* Get file-specific configuration about descriptor FD.  */
extern long int fpathconf(int __fd, int __name);


/* Special wrapped functions  - call these instead of their windows equivalents */

extern NET_API_STATUS wrap_NetUserGetGroups(LPCWSTR servername,
	LPCWSTR username, DWORD level, LPBYTE* bufptr, DWORD prefmaxlen,
	LPDWORD entriesread, LPDWORD totalentries);


extern NET_API_STATUS wrap_NetUserGetLocalGroups(LPCWSTR servername,
	LPCWSTR username, DWORD level, DWORD flags, LPBYTE* bufptr,
	DWORD prefmaxlen, LPDWORD entriesread, LPDWORD totalentries);

extern NET_API_STATUS wrap_NetUserGetInfo(LPCWSTR servername,
	LPCWSTR username, DWORD level, LPBYTE* bufptr);

/* The following are for storing special pbs windows messages for logging */
#define WINLOG_BUF_SIZE	4096

extern char winlog_buffer[WINLOG_BUF_SIZE];  /* contains a special message */
/* to log */
extern int check_executor(void);
extern void close_valid_handle(HANDLE *p_handle);
#define IS_UNCPATH(x)	((!(strncmp(x, "\\\\", 2)) || !(strncmp(x, "//", 2))))
extern void get_uncpath(char *path);
extern int get_localpath(char *unc_path, char *map_drive);
extern int stat_uncpath(char *path, struct stat *sb);
extern int access_uncpath(char *path, int mode);
#endif

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
#include <pbs_config.h>
#include <io.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/timeb.h>
#include <errno.h>
#include <stdio.h>
#include <stdarg.h>
#include <wtypes.h>
#include <varargs.h>
#include <fcntl.h>
#include "log.h"
#include "pbs_ifl.h"
#include "pbs_internal.h"
#include <avltree.h>

#define TIME_SIZE 26 /*String length of time string is 26*/
#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

BOOL is_user_impersonated = FALSE;
static AVL_IX_DESC *env_avltree = NULL;
typedef BOOL(WINAPI *LPFN_ISWOW64PROCESS)(HANDLE, PBOOL);

LPFN_ISWOW64PROCESS fnIsWow64Process;
/**
 * @file	util.c
 */
/**
 * @brief
 *	Determine if this is a Wow64 process
 *      e.g. 32-bit process running on 64-bit Windows
 *
 * @return      BOOL
 * @retval	True - is a Wow64 process
 * @retval	False - is not a Wow64 process
 *
 */
BOOL
is_64bit_Windows(void)
{
	BOOL bIsWow64 = FALSE;

	/* IsWow64Process is not available on all supported versions of Windows.
	 * Use GetModuleHandle to get a handle to the DLL that contains the function
	 * and GetProcAddress to get a pointer to the function if available.
	 */

	fnIsWow64Process = (LPFN_ISWOW64PROCESS) GetProcAddress(
		GetModuleHandle("kernel32"), "IsWow64Process");

	if (NULL != fnIsWow64Process) {
		if (!fnIsWow64Process(GetCurrentProcess(), &bIsWow64)) {
			return bIsWow64;
		}
	}
	return bIsWow64;
}

/**
 * @brief
 *	prints error message to stderr file.
 *
 * @param[in] str - error msg
 *
 * @return	Void
 *
 */
void
ErrorMessage(char *str)
{
	char buf[LOG_BUF_SIZE];
	LPVOID	lpMsgBuf;
	int	err = GetLastError();
	int		len;

	FormatMessage(
		FORMAT_MESSAGE_ALLOCATE_BUFFER |
		FORMAT_MESSAGE_FROM_SYSTEM |
		FORMAT_MESSAGE_IGNORE_INSERTS,
		NULL, err,
		MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
		(LPTSTR)&lpMsgBuf, 0, NULL);
	strncpy(buf, lpMsgBuf, sizeof(buf));
	LocalFree(lpMsgBuf);
	buf[sizeof(buf)-1] = '\0';
	len = strlen(buf);
	if (buf[len-1] == '\n')
		len--;
	if (buf[len-1] == '.')
		len--;
	buf[len-1] = '\0';

	fprintf(stderr, "%s: %s\n", str, buf);
}

/**
 * @brief
 *	allocate space for argument parameters and return pointer to it.
 *
 * @return	structure handle
 * @retval	pointer to arg_param struct	success
 * @retval	NULL				error
 *
 */
struct arg_param *create_arg_param(void)
{
	struct arg_param *pap;

	pap = (struct arg_param *)malloc(sizeof(struct arg_param));
	
	if (pap == NULL)
		return NULL;

	pap->argv = (char **)malloc(50 * sizeof(char *));	/* should be sufficient */
	if (pap->argv == NULL) {
		(void)free(pap);
		return NULL;
	}
	return (pap);
}

/**
 * @brief
 *	frees the argument parameters.
 *
 * @param[in] p - pointer to arg_param structure
 *
 * @return	Void
 *
 */
void
free_arg_param(struct arg_param *p)
{
	int	i;

	if (p == NULL)
		return;

	for (i=0; i < p->argc; i++) {
		if (p->argv[i])
			(void)free(p->argv[i]);
	}

	(void)free(p->argv);
	(void)free(p);
}

/**
 * @brief
 *	prints the argument parameters.
 *
 * @param[in] p - pointer to arg_param structure
 *
 * @return      Void
 *
 */

void
print_arg_param(struct arg_param *p)
{
	int	i;
	char	logb[LOG_BUF_SIZE] = {'\0' } ;

	if (p == NULL)
		return;

	for (i=0; i < p->argc; i++) {
		sprintf(logb, "print_arg_param: p->argv[%d]=%s", i, p->argv[i]);
		log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", logb);
	}

}

/**
 * @brief
 *	manipulates the file descriptor fd.
 *
 * @param[in] fd - file descriptor
 * @param[in] cmd - operation to be performed
 * @param[in] arg - new fd
 *
 * @return	int
 * @retval	0	success
 * @retval	-2	error
 *
 */
int
fcntl(int fd, int cmd, long arg)
{

	if (cmd == F_DUPFD) {
		/* dup2 is deprecated POSIX function. Hence using the ISO C++ conformant
		 * _dup2 instead. _dup2 functions associate a second file descriptor with
		 * a currently open file and returns 0 to indicate success.
		 */

		if (_dup2(fd, arg)== 0)
			return (arg);
	}
	return (-2);
}

/**
 * @brief
 * 	just a placeholder for the unix equivalent function.
 *
 * @param[in] path - file path
 * @param[out] resolved_path - resolved path, if NULL is passed in, then
 *     this function will allocate PATH_MAX bytes of memory and return the
 *     address as return value. It is the caller's responsibility to free
 *     this memory.
 *
 * @return	string
 * @retval	resolved path	succees
 *
 */
char *
realpath(const char *path, char *resolved_path)
{
	if (resolved_path == NULL) {
		if ((resolved_path = malloc(PATH_MAX)) == NULL) {
			fprintf(stderr, "realpath() failed to allocate memory\n");
			return NULL;
		}
	}
	strcpy(resolved_path, path);
	back2forward_slash(resolved_path);
	return (resolved_path);
}

/**
 * @brief
 * 	mimics the unix equivalent, with minimum output
 *
 * @param[in] file_name - filename to be stat-ed
 * @param[out] buf - stat of file
 *
 * @return	int
 * @retval	-1	error
 * @retval	0	success
 *
*/
int
lstat(const char *file_name, struct stat *buf)
{
	int mode;

	if ((mode=GetFileAttributes(file_name)) == 0xFFFFFFFF) {
		errno = GetLastError();
		return (-1);
	}
	buf->st_mode = 0;
	if (mode & FILE_ATTRIBUTE_DIRECTORY)
		buf->st_mode |= _S_IFDIR;
	else
		buf->st_mode |= _S_IFREG;

	if (mode & FILE_ATTRIBUTE_READONLY)
		buf->st_mode |= _S_IREAD;
	else {
		buf->st_mode |= _S_IREAD;
		buf->st_mode |= _S_IWRITE;
		buf->st_mode |= _S_IEXEC;
	}

	return (0);

}

/**
 * @brief
 *	fix_temp_path: given a dynamically generated temporary filename 'tmp_name',
 *	if this refers to a file that is located in top-level dir
 *	"\", then modify the input string so that the location
 *	is in TMP as specified in environment.
 *
 * @param[in] tmp_name - temporary file name.
 *
 */
void
fix_temp_path(char tmp_name[MAXPATHLEN+1])
{
	char *p, *p2;
	char tmp_name2[MAXPATHLEN+1];

	if (p = strrchr(tmp_name, '\\')) {
		*p = '\0';
		if (strlen(tmp_name) == 0) { /* dir prefix is root slash */
			*p = '\\';
			p2 = getenv("TMP");
			_snprintf(tmp_name2, MAXPATHLEN, "%s%s", (p2?p2:""),
				tmp_name);
			strncpy(tmp_name, tmp_name2, MAXPATHLEN);
		} else {
			*p = '\\';
		}
	}
}

/**
 * @brief
 *	function to open a file .
 *
 * @param[in] filename - filename to be opened
 * @param[in] mode - mode in which file to be opened
 *
 * @return	MY_FILE
 * @retval	file fd		success
 * @retval	NULL		error
 *
 */
MY_FILE *
my_fopen(const char *filename, const char *mode)
{
	int fd;
	struct stat sbuf;
	char	*content, *contentp;
	MY_FILE *mfp;
	int	ct;

	if (strcmp(mode, "r") != 0) {
		return NULL;
	}

	if ((fd=open(filename, O_RDONLY|O_TEXT)) == -1) {
		return NULL;
	}

	if (fstat(fd, &sbuf) == -1) {
		return NULL;
	}

	if ((content=(char *)malloc((size_t)sbuf.st_size+1)) == NULL) {
		return NULL;
	}

	if ((mfp=(MY_FILE *)malloc(sizeof(MY_FILE))) == NULL) {
		(void)free(content);
		return NULL;
	}

	ct = 0;
	contentp = content;
	while ((ct=read(fd, contentp, sbuf.st_size)) > 0) {
		contentp+=ct;
	}

	*contentp = '\0';

	mfp->fd = fd;
	mfp->content = content;
	mfp->pos = content;
	mfp->end = contentp;

	return (mfp);
}

/**
 * @brief
 *	reads specified size of characters from stream and stores them into buffer.
 *
 * @param[out] buf - to store read chars
 * @param[in] n - size of characters
 * @param[in] stream - file descriptor
 *
 * @return	string
 * @retval	read data	success
 * @retval	NULL		error
 *
 */
char *
my_fgets(char *buf, int n, MY_FILE *stream)
{

	int i;
	char *bufp;

	if (stream == NULL || (n <= 0) || (buf == NULL)) {
		return NULL;
	}

	bufp = buf;

	for (i=0; i < (n-1) && (stream->pos < stream->end); i++) {
		*bufp = *stream->pos;
		bufp++;
		stream->pos++;

		if (*((stream->pos)-1) == '\n')
			break;
	}

	if (bufp == buf) 	/* it never advanced, then no output */
		return NULL;

	*bufp = '\0';

	return (buf);
}

/**
 * @brief
 *	function to close file
 *
 * @param[in] stream - file descriptor to be closed
 *
 * @return	int
 * @retval	0	success
 * @retval	EOF	error
 *
 */
int
my_fclose(MY_FILE *stream)
{
	if ((stream == NULL) || stream->fd < 0)
		return (EOF);

	close(stream->fd);

	if (stream->content)
		(void)free(stream->content);

	(void)free(stream);

	return (0);
}

/**
 * @brief
 *	gets a value for configuration option __name for the filename __path.
 *
 * @param[in] __path - path name
 * @param[in] __name - file name
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	error
 *
 */
long int
pathconf(const char *__path, int __name)
{

	if (__name == _PC_PATH_MAX)
		return (_MAX_PATH);
	return (-1);
}

/**
 * @brief
 *	gets a value for the configuration option __name for the open file descriptor __fd.
 *
 * @param[in] __name - file name
 * @param[in] __fd - file descriptor
 *
 * @return	int
 * @retval	-1	error
 * @retval	256	success
 *
 */

long int
fpathconf(int __fd, int __name)
{
	if (__name == _PC_PATH_MAX)
		return (_MAX_PATH);
	return (-1);
}

/* Secure Functions */
/**
 * @brief
 *	A Windows version of strtok.
 *
 * @param[in] strToken- String containing token or tokens.
 * @param[in] strDelimit - Set of delimiter characters.
 *
 * @return	pointer to string
 * @retval	pointer to the next token found in strToken.
 * @retval	NULL	when no more tokens are found. Each call modifies strToken by substituting
 *          	a NULL character for each delimiter that is encountered.
 * @see strok() on MSDN.
 */
char *
win_strtok(char *strToken, const char *strDelimit)
{
	static char *next_token;
	char *token;

	token = strtok_s(strToken, strDelimit, &next_token);

	return (token);
}
/**
 * @brief A secure version of Windows fopen.
 *
 * @param[in] filename - Filename.
 * @param[in] mode - Type of access permitted.
 *
 * @return Each of these functions returns a pointer to the open file.
 *          A null pointer value indicates an error.
 * @see fopen() on MSDN.
 */
FILE  *
win_fopen(const char *filename, const char *mode)
{
	FILE *fp;
	/*
	 * Files opened by fopen_s and _wfopen_s are not sharable.
	 * If you require that a file be sharable, use _fsopen, _wfsopen
	 * with the appropriate sharing mode constant
	 */

	fp =  _fsopen(filename, mode, _SH_DENYNO);

	return (fp);
}

/**
 * @brief A secure version of Windows freopen.
 *
 * @param[in] path - Path of new file.
 * @param[in] mode - Type of access permitted.
 * @param[in] stream - Pointer to FILE structure.
 *
 * @return  Sucess - A pointer to FILE structure for the newly open file.
 *          Fail - NULL
 * @see freopen_s() on MSDN
 */
FILE*
win_freopen(const char *path, const char *mode, FILE *stream)
{
	FILE *out_stream = NULL;
	errno_t ret = -1;

	if (path == NULL || mode == NULL || stream == NULL)
		return NULL;

	ret = freopen_s(&out_stream, path, mode, stream);
	if (ret != 0) {
		return NULL;
	} else {
		return out_stream;
	}
}

/**
 * @brief	Create and initilize AVL tree for environment variables
 *			in global variable called "env_avltree"
 *
 * @return	error code
 * @retval	1	Failure
 * @retval	0	Success
 */
int
create_env_avltree()
{
	int i = 0;
	char varname_tmp[_MAX_ENV] = {'\0'};
	char *name = NULL;
	char *value = NULL;
	AVL_IX_REC *pe = NULL;
	extern char **environ;

	if (env_avltree == NULL) {
		if ((env_avltree = malloc(sizeof(AVL_IX_DESC))) != NULL) {
			if (avl_create_index(env_avltree, AVL_NO_DUP_KEYS, 0))
				return 1;
		}
	}

	if (env_avltree != NULL) {
		for (i=0; environ[i] != NULL; i++) {
			(void)strncpy_s(varname_tmp, sizeof(varname_tmp), environ[i], _TRUNCATE);
			if ((name = strtok_s(varname_tmp, "=", &value)) != NULL) {
				if ((pe = malloc(sizeof(AVL_IX_REC) + WINLOG_BUF_SIZE + 1)) != NULL) {
					strncpy(pe->key, name, WINLOG_BUF_SIZE);
					if ((pe->recptr = (void *)strdup(value)) != NULL)
						avl_add_key(pe, env_avltree);
					free(pe);
					pe = NULL;
				}
			}
		}
	}
	return 0;
}

/**
 * @brief	Update the AVL tree in global variable
 *			called "env_avltree" for environment variables
 *
 * @return	void
 *
 * @retval	None
 */
void
update_env_avltree()
{
	int i = 0;
	int found = 0;
	int ret = 0;
	char varname_tmp[_MAX_ENV] = {'\0'};
	char *name = NULL;
	char *value = NULL;
	AVL_IX_REC *pe = NULL;
	extern char **environ;

	if (env_avltree != NULL) {
		avl_first_key(env_avltree);
		if ((pe = malloc(sizeof(AVL_IX_REC) + WINLOG_BUF_SIZE + 1)) != NULL) {
			while ((ret = avl_next_key(pe, env_avltree)) == AVL_IX_OK) {
				found = 0;
				for (i=0; environ[i] != NULL; i++) {
					if (!strncmp(environ[i], pe->key, strlen(pe->key))) {
						found = 1;
						break;
					}
				}
				if (!found) {
					free(pe->recptr);
					pe->recptr = NULL;
					avl_delete_key(pe, env_avltree);
				}
			}
			free(pe);
			pe = NULL;
		}

		for (i=0; environ[i] != NULL; i++) {
			(void)strncpy_s(varname_tmp, sizeof(varname_tmp), environ[i], _TRUNCATE);
			if ((name = strtok_s(varname_tmp, "=", &value)) != NULL) {
				if ((pe = malloc(sizeof(AVL_IX_REC) + WINLOG_BUF_SIZE + 1)) != NULL) {
					strncpy(pe->key, name, WINLOG_BUF_SIZE);
					if (avl_find_key(pe, env_avltree) != AVL_IX_OK) {
						if ((pe->recptr = (void *)strdup(value)) != NULL)
							avl_add_key(pe, env_avltree);
					}
					free(pe);
					pe = NULL;
				}
			}
		}
	}
}

/**
 * @brief	Destroy the global AVL tree of environment  variables created by
 *			create_env_avltree in global variable called "env_avltree"
 *
 * @return	void
 *
 * @retval	None
 */
void
destroy_env_avltree()
{
	AVL_IX_REC *pe = NULL;
	int ret = 0;

	if (env_avltree != NULL) {
		avl_first_key(env_avltree);
		if ((pe = malloc(sizeof(AVL_IX_REC) + WINLOG_BUF_SIZE + 1)) != NULL) {
			while ((ret = avl_next_key(pe, env_avltree)) == AVL_IX_OK) {
				free(pe->recptr);
				pe->recptr = NULL;
				avl_delete_key(pe, env_avltree);
			}
			free(pe);
			pe = NULL;
		}
		avl_destroy_index(env_avltree);
		free(env_avltree);
		env_avltree = NULL;
	}
}


/**
 * @brief A secure version of Windows open.
 *
 * @param[in] filename - File name.
 * @param[in] oflag - Type of operations allowed.
 * @param[in] pmode - Permission mode.
 *
 * @return	int
 * @retval	a file descriptor for the opened file.	success
 * @retval	-1 					indicates an error.
 *
 * @ see open() on MSDN.
 */
int
win_open(const char *filename, int oflag, ...)
{
	int fd = -1;
	errno_t err = 0;
	int pmode = -1;
	va_list vl = NULL;

	va_start(vl, oflag);
	pmode = va_arg(vl, int) & (S_IREAD | S_IWRITE);
	err = _sopen_s(&fd, filename, oflag, _SH_DENYNO, pmode);
	va_end(vl);

	if ((err) || (fd == -1)) {
		errno = err;
		return (-1);
	}

	return fd;
}
/**
 * @brief A Windows version of mktemp().
 *
 * @param[in] fname_pattern - File name pattern.
 *
 * @return Returns a pointer to the modified template or NULL indicates an error.
 *
 */
char *
win_mktemp(char *fname_pattern)
{
	size_t sizeInChars = -1;
	errno_t ret = -1;

	if ((fname_pattern != NULL) && (*fname_pattern != '\0')) {
		sizeInChars = strlen(fname_pattern)+1;
	} else {
		errno = EINVAL;
		return NULL;
	}

	ret = _mktemp_s(fname_pattern, sizeInChars);
	if (ret != 0) {
		return NULL;
	}

	return fname_pattern;
}
/**
 * @Brief A secure version of Windows umask().
 *       Sets the default file-permission mask.
 * @param[in] pmode: Default permission setting.
 *
 * @return int
 *
 * @retval Success - the previous value of file-permisstion mask
 *         Fail   - EINVAL
 * @see umask() on MSDN.
 */
int
win_umask(int pmode)
{
	int oldmask = -1;
	errno_t ret = -1;

	if (!(pmode & (S_IREAD | S_IWRITE))) {
		errno = EINVAL;
		return EINVAL;
	}
	if ((ret = _umask_s(pmode, &oldmask)) == EINVAL) {
		errno = EINVAL;
		return EINVAL;
	}
	return oldmask;
}
/**
 * @brief: A secure version of Windows strerror.
 *
 * @param[in] errnum Error number.
 * @param[in] strErrMsg User-supplied message.
 *
 * @returns a pointer to the error-message string.
 * @see strerror on MSDN.
 */
char *
win_strerror(int errnum)
{
	static char buffer[MAXPATHLEN+1] = {'\0'};
	strerror_s(buffer, sizeof(buffer)-1, errnum);
	return buffer;
}
/**
 * @brief A Windows version of localtime().
 *
 *	@param[in] timer Pointer to stored time.
 *
 *   @returns Return a pointer to the structure result.
 *   @see localtime () on MSDN.
 */

struct tm *win_localtime(const time_t *timer)
{
	static struct tm newtime ;
	localtime_s(&newtime, timer);
	return (&newtime);
}

/**
 * @brief A Windows version of localtime().
 *
 *	@param[in] timer Pointer to stored time.
 *
 *   @returns Return a  pointer to the character string
 *   @see ctime() on MSDN.
 */
char*
win_ctime(const time_t *timer)
{
	static char time_value [TIME_SIZE]= "";
	ctime_s(time_value, TIME_SIZE, timer);
	return time_value;
}
/**
 * @ brief A secure version of Windows wcsset.
 *
 * @param[in] str : Null-terminated string to be set.
 * @param[in] c : Character setting.
 *
 * @returns Returns a pointer to the altered string.
 * @see wcsset() on MSDN.
 */
wchar_t *win_wcsset(wchar_t *str, wchar_t c)
{
	_wcsset_s(str, wcslen(str)+1, c);
	return str;
}
/**
 * @ brief Close a valid handle
 *
 * @param[in] p_handle : pointer to a Windows HANDLE
 *
 * @returns void
 */
void
close_valid_handle(HANDLE *p_handle)
{
	if (p_handle == NULL)
		return;
	if (*p_handle != INVALID_HANDLE_VALUE && *p_handle != NULL)
		CloseHandle(*p_handle);
	*p_handle = INVALID_HANDLE_VALUE;
}
/**
 * @ brief get Windows system root directory.
 *
 * @returns a pointer to the Windows root directory.
 */
char *
get_win_rootdir(void)
{
	char    *root_dir = NULL;
	root_dir = get_saved_env("SYSTEMROOT");
	if (root_dir == NULL)
		root_dir = get_saved_env("WINDIR");
	return root_dir;
}
/**
 * @brief
 *	get command shell.
 *
 * @param[in] cmd : sufficiently allocated buffer to hold the command shell path.
 * @param[in] cmd_len : size of cmd buffer
 *  			Should be large enough to hold MAX_PATH characters.
 *
 * @return 	int
 * @retval 	0 	for success,
 * @retval 	!0 	for failure
 * @retval 	-1 	if buffer size (cmd_len), is insufficent.
 */
int
get_cmd_shell(char *cmd, int cmd_len)
{
	char *temp_dir = NULL;
	char cmd_x64_path[MAX_PATH] = {'\0'};

	if (cmd_len < MAX_PATH)
		return -1;
	memset(cmd, '\0', cmd_len);
	temp_dir = get_win_rootdir();
	/*
	 * If it is a SYSWOW64 process i.e. a 32-bit process running inside a 64-bit Windows OS,
	 * run a 64-bit cmd.exe.
	 */
	if (TRUE == is_64bit_Windows() && temp_dir) {
		(void)snprintf(cmd_x64_path, _countof(cmd_x64_path) - 1, "%s\\Sysnative\\cmd.exe", temp_dir);
		(void)snprintf(cmd, cmd_len - 1, "%s", cmd_x64_path);
	}
	/*
	 * If it is 32-bit Windows OS, run 32-bit cmd shell.
	 * Just to be safe, included the check for existence of synative/cmd.exe on 64-bit Windows
	 */
	if (TRUE != is_64bit_Windows() || !(file_exists(cmd_x64_path))) {
		(void)snprintf(cmd, cmd_len - 1, "cmd.exe");
	}
	return 0;
}

/* @brief
 *  	Impersonate a user, a wrapper to ImpersonateLoggedOnUser() API.
 *  	if impersonation fails, sets the errno
 *
 * @param[in]   hlogintoken : user login
 *
 * @return      BOOL
 * @retval      whether impersonation succeded, return value of ImpersonateLoggedOnUser() API
 */
BOOL
impersonate_user(HANDLE hlogintoken)
{
	is_user_impersonated = FALSE;

	if (hlogintoken == NULL || hlogintoken == INVALID_HANDLE_VALUE)
		return FALSE;

	is_user_impersonated = ImpersonateLoggedOnUser(hlogintoken);
	if (is_user_impersonated == FALSE)
		errno = GetLastError();
	return is_user_impersonated;
}

/* @brief
 *  	Revert an impersonated user, a wrapper to RevertToSelf() API
 *  	If revert fails, sets the errno.
 *
 *  @return     BOOL
 *  @retval     whether revert succeded, return value of RevertToSelf() API
 */
BOOL
revert_impersonated_user()
{
	BOOL result = FALSE;
	if (is_user_impersonated == TRUE) {
		result = RevertToSelf();
		if (result == TRUE)
			is_user_impersonated = FALSE;
		else
			errno = GetLastError();
	}
	return result;
}

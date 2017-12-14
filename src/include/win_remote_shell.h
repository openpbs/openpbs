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
/* windows 2000 specific */
#ifndef	_WIN_RSHELL_H
#define _WIN_RSHELL_H

#define INTERACT_STDOUT         "Interact_stdout"
#define INTERACT_STDIN          "Interact_stdin"
#define INTERACT_STDERR         "Interact_stderr"
#define READBUF_SIZE 8192 /* Size of pipe read buffer */
#define CONSOLE_BUFSIZE 2048 /* Size of Console input buffer */
#define CONSOLE_TITLE_BUFSIZE 2048 /* Size of Console title */
#define PIPENAME_MAX_LENGTH     256 /* Maximum length of pipe name */

extern void std_output(char *buf);
extern void std_error(char *buf);
extern void disconnect_close_pipe(HANDLE hPipe);
extern int create_std_pipes(STARTUPINFO* psi, char *pipename_append, int is_interactive);
extern int do_ConnectNamedPipe(HANDLE hPipe, LPOVERLAPPED pOverlapped);
extern HANDLE do_WaitNamedPipe(char *szPipeName, DWORD nTimeOut, DWORD readwrite_accessflags);
extern int connectstdpipes(STARTUPINFO* psi, int is_interactive);
extern DWORD run_command_si_blocking(STARTUPINFO *psi, char *command, DWORD *pReturnCode, int is_gui, int show_window, char *username);
extern BOOL connect_remote_resource(const char *remote_host, const char *remote_resourcename, BOOL bEstablish);
extern int handle_stdoe_pipe(HANDLE hPipe_remote_std, void (*oe_handler)(char*));
extern void listen_remote_stdouterr_pipes(HANDLE hpipe_remote_stdout, HANDLE hpipe_remote_stderr);
extern void listen_remote_stdinpipe_thread(void *p);
extern void listen_remote_stdpipes(HANDLE *phout, HANDLE *pherror, HANDLE *phin);
extern BOOL execute_remote_shell_command(char *remote_host, char *pipename_append, BOOL connect_stdin);
extern int remote_shell_command(char *remote_host, char *pipename_append, BOOL connect_stdin);
#endif

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
 * @file	tpp_dis.c
 *
 * @brief	DIS interface for the TPP library
 *
 * @par		Functionality:
 *
 *		TPP = TCP based Packet Protocol. This layer uses TCP in a multi-
 *		hop router based network topology to deliver packets to desired
 *		destinations. LEAF (end) nodes are connected to ROUTERS via
 *		persistent TCP connections. The ROUTER has intelligence to route
 *		packets to appropriate destination leaves or other routers.
 *
 *		The dis library requires a buffer each for the read and write
 *		sides of the connection. It uses this buffer to encode and
 *		decode information that goes out/gets into the APP.
 *
 *		The APP calls the dis library routines to encode and decode
 *		messages, which uses functions in this file to achieve the
 *		send/receive and buffering functionlity on top of tpp_client.c
 *
 */

#include <pbs_config.h>

#include <errno.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/time.h>
#include <sys/types.h>
#include <stdlib.h>
#include <assert.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include "libpbs.h"
#include "libsec.h"
#include "rpp.h"
#include "tpp_common.h"
#include "tpp_platform.h"

#include "dis.h"
#include "dis_init.h"

#define DIS_BUF_SIZE 4096 /* default DIS buffer size */

/* default keepalive values */
#define DEFAULT_TCP_KEEPALIVE_TIME 30
#define DEFAULT_TCP_KEEPALIVE_INTVL 10
#define DEFAULT_TCP_KEEPALIVE_PROBES 3

#define PBS_TCP_KEEPALIVE "PBS_TCP_KEEPALIVE" /* environment string to search for */

/*
 * The structure that the DIS routines use to manage the encode/decode buffer
 * for each side of the connection.
 */
struct tppdisbuf {
	size_t tdis_lead; /* pointer to the lead of the data */
	size_t tdis_trail; /* pointer to the trailing char of the data */
	size_t tdis_eod; /* variable to use to calculate end of data */
	size_t tdis_bufsize;/* size of this dis buffer */
	char *tdis_thebuf; /* pointer to the dis buffer space */
};

/*
 * Each tpp connection basically has a read and write end and thus needs a
 * dis buffer for each of the read and write ends. This structure contains
 * both the read and write buffer for each "channel".
 */
struct tppdis_chan {
	struct tppdisbuf readbuf; /* the dis read buffer */
	struct tppdisbuf writebuf; /* the dis write buffer */
};

/* extern functions called from this file into the tpp_transport.c */
extern void *tppdis_get_user_data(int sd);
extern void DIS_tpp_destroy(int fd);

/**
 * @brief
 *	Pack existing data into front of buffer
 *
 *	Moves "uncommited" data to front of buffer and adjusts pointers.
 *	Does a character by character move since data may over lap.
 *
 * @param[in] - tp - the tpp dis buffer pointer to pack
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
tppdis_pack_buff(struct tppdisbuf *tp)
{
	size_t amt;
	size_t start;
	size_t i;

	start = tp->tdis_trail;
	if (start != 0) {
		amt = tp->tdis_eod - start;
		for (i = 0; i < amt; ++i) {
			*(tp->tdis_thebuf + i) = *(tp->tdis_thebuf + i + start);
		}
		tp->tdis_lead -= start;
		tp->tdis_trail -= start;
		tp->tdis_eod -= start;
	}
}

/**
 * @brief
 *	Read data from tpp stream to "fill" the buffer
 *	Update the various buffer pointers.
 *
 * @param[in] - fd - The tpp channel from which to do DIS reads
 *
 * @return	 number of chars read
 * @retval	>0 number of characters read
 * @retval	 0 if EOD (no data currently available)
 * @retval	-1 if error
 * @retval	-2 if EOF (stream closed)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
tppdis_read(int fd)
{
	int i;
	struct tppdisbuf *tp;
	char *tmcp;
	int len;
	struct tppdis_chan *chan;

	chan = (struct tppdis_chan *) tppdis_get_user_data(fd);
	if (chan == NULL)
		return -2;

	tp = &(chan->readbuf);
	if (!tp)
		return -1;

	/* compact (move to the front) the uncommitted data */
	tppdis_pack_buff(tp);

	len = tp->tdis_bufsize - tp->tdis_eod;

	if (len < DIS_BUF_SIZE) {
		tp->tdis_bufsize += DIS_BUF_SIZE;
		tmcp = (char *) realloc(tp->tdis_thebuf, sizeof(char) * tp->tdis_bufsize);
		if (tmcp == NULL) {
			/* realloc failed */
			return -1;
		}
		tp->tdis_thebuf = tmcp;
		len = tp->tdis_bufsize - tp->tdis_eod;
	}

	i = tpp_recv(fd, &tp->tdis_thebuf[tp->tdis_eod], len);
	if (i > 0)
		tp->tdis_eod += i;

	return ((i == 0) ? -2 : i);
}

/**
 * @brief
 *	flush tpp/dis write buffer
 *
 *	Writes "committed" data in buffer to file descriptor,
 *	packs remaining data (if any), resets pointers
 *
 * @param[in] - fd - The tpp channel whose DIS buffers need to be flushed
 *
 * @return Error code
 * @retval  0 on success
 * @retval -1 on error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
DIS_tpp_wflush(int fd)
{
	size_t ct;
	char *pb;
	struct tppdisbuf *tp;
	struct tppdis_chan *chan;

	chan = (struct tppdis_chan *) tppdis_get_user_data(fd);
	if (chan == NULL)
		return -1;

	tp = &(chan->writebuf);
	if (!tp)
		return -1;

	pb = tp->tdis_thebuf;

	ct = tp->tdis_trail;
	if (ct == 0)
		return 0;

	if (tpp_send(fd, pb, ct) == -1) {
		return (-1);
	}
	tp->tdis_eod = tp->tdis_lead;
	tppdis_pack_buff(tp);
	return 0;
}

/**
 * @brief
 *	Wrapper function that calls DIS_tpp_wflush
 *
 * @param[in] - index - The tpp channel whose DIS buffers need to be flushed
 *
 * @return Errorcode
 * @retval  0 on success
 * @retval -1 on error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_flush(int index)
{
	return (DIS_tpp_wflush(index));
}

/**
 * @brief
 *	reset tpc/dis buffer to empty
 *
 * @param[in] - tp - The dis buffer to clear
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
DIS_tpp_clear(struct tppdisbuf *tp)
{
	tp->tdis_lead = 0;
	tp->tdis_trail = 0;
	tp->tdis_eod = 0;
}

/**
 * @brief
 *	tpp/dis support routine to skip over data in read buffer
 *
 * @param[in] - fd - Tpp channel from whose dis buffer bytes are to be skipped
 * @param[in] - ct - Count of bytes that is to be skipped
 *
 * @return Count of bytes that were actually skipped
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
tppdis_rskip(int fd, size_t ct)
{
	struct tppdisbuf *tp;
	struct tppdis_chan *chan;

	chan = (struct tppdis_chan *) tppdis_get_user_data(fd);
	if (chan == NULL)
		return -2;

	tp = &(chan->readbuf);
	if (tp->tdis_lead - tp->tdis_eod < ct)
		ct = tp->tdis_lead - tp->tdis_eod;
	tp->tdis_lead += ct;
	return (int) ct;
}

/**
 * @brief
 *	tpp/dis support routine to get next character from read buffer
 *
 * @param[in] - fd - Tpp channel from whose dis buffer bytes are to be read
 *
 * @retval	>0 number of characters read
 * @retval	-1 if EOD or error
 * @retval	-2 if EOF (stream closed)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
tppdis_getc(int fd)
{
	int x;
	struct tppdisbuf *tp;
	struct tppdis_chan *chan;

	chan = (struct tppdis_chan *) tppdis_get_user_data(fd);
	if (chan == NULL)
		return -2;

	tp = &(chan->readbuf);
	if (tp->tdis_lead >= tp->tdis_eod) {
		/* not enought data, try to get more */
		x = tppdis_read(fd);
		if (x <= 0)
			return ((x == -2) ? -2 : -1); /* Error or EOF */
	}
	return ((int) tp->tdis_thebuf[tp->tdis_lead++]);
}

/**
 * @brief
 *	tpp/dis support routine to get a string from read buffer
 *
 * @param[in] - fd - Tpp channel from whose dis buffer bytes are to be read
 * @param[in] - str - The string address to which data is to be read into
 * @param[in] - ct - The count of bytes of room available in str
 *
 * @retval	>0 number of characters read
 * @retval	-1 if EOD or error
 * @retval	-2 if EOF (stream closed)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
tppdis_gets(int fd, char *str, size_t ct)
{
	int x;
	struct tppdisbuf *tp;
	struct tppdis_chan *chan;

	chan = (struct tppdis_chan *) tppdis_get_user_data(fd);
	if (chan == NULL)
		return -2;

	tp = &(chan->readbuf);
	while (tp->tdis_eod - tp->tdis_lead < ct) {
		/* not enought data, try to get more */
		x = tppdis_read(fd);
		if (x <= 0)
			return x; /* Error or EOF */
	}
	(void) memcpy(str, &tp->tdis_thebuf[tp->tdis_lead], ct);
	tp->tdis_lead += ct;
	return (int) ct;
}

/**
 * @brief
 *	tpp/dis support routine to put a counted string of characters
 *	into the write buffer.
 *
 * @param[in] - fd - Tpp channel from whose dis buffer bytes are to be written
 * @param[in] - str - The string address to which data is to be written from
 * @param[in] - ct - The count of bytes available in str
 *
 * @retval	>0 number of characters written
 * @retval	-1 error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
tppdis_puts(int fd, const char *str, size_t ct)
{
	struct tppdisbuf *tp;
	char *tmcp;
	struct tppdis_chan *chan;

	chan = (struct tppdis_chan *) tppdis_get_user_data(fd);
	if (chan == NULL)
		return -1;

	tp = &(chan->writebuf);

	if ((tp->tdis_bufsize - tp->tdis_lead) < ct) { /* add room */
		/* no need to lock mutex here, per fd resize */
		size_t ru = (ct + tp->tdis_lead) / DIS_BUF_SIZE;
		tp->tdis_bufsize = (ru + 1) * DIS_BUF_SIZE;
		tmcp = (char *) realloc(tp->tdis_thebuf, sizeof(char) * tp->tdis_bufsize);
		if (tmcp != NULL)
			tp->tdis_thebuf = tmcp;
		else
			return -1; /* realloc failed */
	}
	(void) memcpy(&tp->tdis_thebuf[tp->tdis_lead], str, ct);
	tp->tdis_lead += ct;
	return ct;
}

/**
 * @brief
 *	tpp/dis support routine to commit/uncommit read data
 *
 * @param[in] - fd - Tpp channel whose dis read buffer bytes to be committed
 * @param[in] - commit_flag - Commit data or not?
 *
 * @retval	0 Success
 * @retval	-1 error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
tppdis_rcommit(int fd, int commit_flag)
{
	struct tppdisbuf *tp;
	struct tppdis_chan *chan;

	chan = (struct tppdis_chan *) tppdis_get_user_data(fd);
	if (chan == NULL)
		return -1;

	tp = &(chan->readbuf);
	if (commit_flag) {
		/* commit by moving trailing up */
		tp->tdis_trail = tp->tdis_lead;
	} else {
		/* uncommit by moving leading back */
		tp->tdis_lead = tp->tdis_trail;
	}
	return 0;
}

/**
 * @brief
 *	tpp/dis support routine to commit/uncommit write data
 *
 * @param[in] - fd - Tpp channel whose dis write buffer bytes to be committed
 * @param[in] - commit_flag - Commit data or not?
 *
 * @retval	0 Success
 * @retval	-1 error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
tppdis_wcommit(int fd, int commit_flag)
{
	struct tppdisbuf *tp;
	struct tppdis_chan *chan;

	chan = (struct tppdis_chan *) tppdis_get_user_data(fd);
	if (chan == NULL)
		return -1;

	tp = &(chan->writebuf);
	if (commit_flag) {
		/* commit by moving trailing up */
		tp->tdis_trail = tp->tdis_lead;
	} else {
		/* uncommit by moving leading back */
		tp->tdis_lead = tp->tdis_trail;
	}
	return 0;
}

/**
 * @brief
 *	tpp/dis support routine for ending a message that was read
 *	Skips over decoding to the next message
 *	Calls tpp_inner_eom to purge currently accessed packet
 *
 * @param[in] - fd - Tpp channel whose dis read packet has to be purged
 *
 * @retval	0 Success
 * @retval	-1 error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_eom(int fd)
{
	struct tppdis_chan *tpp;

	/* check for bad file descriptor */
	if (fd < 0)
		return -1;

	TPP_DBPRT(("sd=%d", fd));
	tpp_inner_eom(fd);
	tpp = tpp_get_user_data(fd);
	if (tpp != NULL) {
		/* initialize read and write buffers */
		DIS_tpp_clear(&tpp->readbuf);
	}
	return 0;
}

/**
 * @brief
 *	Setup dis function pointers to point to tpp_dis routines
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
DIS_tpp_reset()
{
	if (dis_getc != tppdis_getc) {
		dis_getc = tppdis_getc;
		dis_puts = tppdis_puts;
		dis_gets = tppdis_gets;
		disr_skip = tppdis_rskip;
		disr_commit = tppdis_rcommit;
		disw_commit = tppdis_wcommit;
	}
}

/**
 * @brief
 *	Get the user buffer associated with the tpp channel. If no buffer has
 *	been set, then allocate a tppdis_chan structure and associate with
 *	the given tpp channel
 *
 * @param[in] - fd - Tpp channel to which to get/associate a user buffer
 *
 * @retval	NULL - Failure
 * @retval	!NULL - Buffer associated with the tpp channel
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void *
tppdis_get_user_data(int fd)
{
	void *data = tpp_get_user_data(fd);
	if (data == NULL) {
		if (errno != ENOTCONN) {

			/* fd connected, but first time - so call setup */
			DIS_tpp_setup(fd);

			/* get the buffer again*/
			data = tpp_get_user_data(fd);
		}
	}
	return data;
}

/**
 * @brief
 *	setup supports routines for dis, "data is strings", to
 * 	use tpp stream I/O.  Also initializes an array of pointers to
 *	buffers and a buffer to be used for the given fd.
 *
 * @param[in] - fd - Tpp channel to whose buffers is to be set
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
DIS_tpp_setup(int fd)
{
	struct tppdis_chan *tpp;
	int rc;

	/* check for bad file descriptor */
	if (fd < 0)
		return;

	TPP_DBPRT(("sd=%d", fd));

	/* set DIS function pointers */
	DIS_tpp_reset();
	tpp = tpp_get_user_data(fd);
	if (tpp == NULL) {
		if (errno == ENOTCONN)
			return;

		tpp = (struct tppdis_chan *) malloc(sizeof(struct tppdis_chan));
		assert(tpp != NULL);
		tpp->readbuf.tdis_thebuf = malloc(DIS_BUF_SIZE);
		assert(tpp->readbuf.tdis_thebuf != NULL);
		tpp->readbuf.tdis_bufsize = DIS_BUF_SIZE;
		tpp->writebuf.tdis_thebuf = malloc(DIS_BUF_SIZE);
		assert(tpp->writebuf.tdis_thebuf != NULL);
		tpp->writebuf.tdis_bufsize = DIS_BUF_SIZE;
		rc = tpp_set_user_data(fd, tpp);
		assert(rc == 0);
		tpp_set_user_data_del_fnc(fd, DIS_tpp_destroy);
	}

	/* initialize read and write buffers */
	DIS_tpp_clear(&tpp->readbuf);
	DIS_tpp_clear(&tpp->writebuf);
}

/**
 * @brief
 *	Destroy a tpp channel - basically free all the DIS buffers previously
 *	allocated to the tpp channel
 *
 * @param[in] - fd - Tpp channel to whose buffers is to be set
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
DIS_tpp_destroy(int fd)
{
	struct tppdis_chan *tpp;

	/* check for bad file descriptor */
	if (fd < 0)
		return;

	TPP_DBPRT(("sd=%d", fd));

	tpp = tpp_get_user_data(fd);
	if (tpp != NULL) {
		if (tpp->readbuf.tdis_thebuf) {
			free(tpp->readbuf.tdis_thebuf);
			tpp->readbuf.tdis_thebuf = NULL;
		}
		if (tpp->writebuf.tdis_thebuf) {
			free(tpp->writebuf.tdis_thebuf);
			tpp->writebuf.tdis_thebuf = NULL;
		}
		DIS_tpp_clear(&tpp->readbuf);
		DIS_tpp_clear(&tpp->writebuf);
		free(tpp);
		tpp_set_user_data(fd, NULL);
	}
}


/**
 * @brief
 *	Helper function called by PBS daemons to set the tpp configuration to
 *	be later used during tpp_init() call.
 *
 * @param[in] pbs_conf - Pointer to the Pbs_config structure
 * @param[out] tpp_conf - The tpp configuration structure duly filled based on
 *			  the input parameters
 * @param[in] nodenames - The comma separated list of name of this side of the communication.
 * @param[in] port     - The port at which this side is identified.
 * @param[in] routers  - Array of router addresses ended by a null entry
 *			 router addresses are of the form "host:port"
 * @param[in] compress - Whether compression of data must be done
 *
 *
 * @retval Error code
 * @return -1 - Failure
 * @return  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
set_tpp_config(struct pbs_config *pbs_conf,
	struct tpp_config *tpp_conf,
	char *nodenames,
	int port,
	char *r,
	int compress,
	int auth_type,
	void* (*cb_get_ext_auth_data)(int auth_type, int *data_len, char *ebuf, int ebufsz),
	int (*cb_validate_ext_auth_data) (int auth_type, void *data, int data_len, char *ebuf, int ebufsz))
{
	int i;
	int num_routers = 0;
	char *routers = NULL;
	char *s, *t, *ctx;
	char *nm;
	int len, hlen;
	char *token, *saveptr, *tmp;
	char *formatted_names = NULL;

	/* before doing anything else, initialize the key to the tls
	 * its okay to call this function multiple times since it
	 * uses a pthread_once functionality to initialize key only once
	 */
	if (tpp_init_tls_key() != 0) {
		/* can only use prints since tpp key init failed */
		fprintf(stderr, "Failed to initialize tls key\n");
		return -1;
	}

	if (r) {
		routers = strdup(r);
		if (!routers) {
			snprintf(log_buffer, TPP_LOGBUF_SZ, "Out of memory allocating routers");
			fprintf(stderr, "%s\n", log_buffer);
			tpp_log_func(LOG_CRIT, __func__, log_buffer);
			return -1;
		}
	}

	if (!nodenames) {
		snprintf(log_buffer, TPP_LOGBUF_SZ, "TPP node name not set");
		fprintf(stderr, "%s\n", log_buffer);
		tpp_log_func(LOG_CRIT, NULL, log_buffer);
		return -1;
	}

	if (port == -1) {
		struct sockaddr_in in;
		int sd;
		int rc;
		tpp_addr_t *addr;

		if ((sd = tpp_sock_socket(AF_INET, SOCK_STREAM, 0)) == -1) {
			snprintf(log_buffer, TPP_LOGBUF_SZ, "tpp_sock_socket() error, errno=%d", errno);
			fprintf(stderr, "%s\n", log_buffer);
			tpp_log_func(LOG_ERR, __func__, log_buffer);
			return -1;
		}

		/* bind this socket to a reserved port */
		in.sin_family = AF_INET;
		in.sin_addr.s_addr = INADDR_ANY;
		in.sin_port = 0;
		memset(&(in.sin_zero), '\0', sizeof(in.sin_zero));
		if ((rc = tpp_sock_bind(sd, (struct sockaddr *) &in, sizeof(in))) == -1) {
			snprintf(log_buffer, TPP_LOGBUF_SZ, "tpp_sock_bind() error, errno=%d", errno);
			fprintf(stderr, "%s\n", log_buffer);
			tpp_log_func(LOG_ERR, __func__, log_buffer);
			tpp_sock_close(sd);
			return -1;
		}

		addr = tpp_get_local_host(sd);
		if (addr) {
			port = addr->port;
			free(addr);
		}

		if (port == -1) {
			snprintf(log_buffer, TPP_LOGBUF_SZ, "TPP client could not detect port to use");
			fprintf(stderr, "%s\n", log_buffer);
			tpp_log_func(LOG_ERR, __func__, log_buffer);
			tpp_sock_close(sd);
			return -1;
		}
		/* don't close this socket */
		tpp_set_close_on_exec(sd);
	}

	/* add port information to the node names and format into a single string as desired by TPP */
	len = 0;
	token = strtok_r(nodenames, ",", &saveptr);
	while (token) {
		nm = mk_hostname(token, port);
		if (!nm) {
			snprintf(log_buffer, TPP_LOGBUF_SZ, "Failed to make node name");
			fprintf(stderr, "%s\n", log_buffer);
			tpp_log_func(LOG_CRIT, NULL, log_buffer);
			return -1;
		}

		hlen = strlen(nm);
		if ((tmp = realloc(formatted_names, len + hlen + 2)) == NULL) { /* 2 for command and null char */
			snprintf(log_buffer, TPP_LOGBUF_SZ, "Failed to make formatted node name");
			fprintf(stderr, "%s\n", log_buffer);
			tpp_log_func(LOG_CRIT, NULL, log_buffer);
			return -1;
		}

		formatted_names = tmp;

		if (len == 0) {
			strcpy(formatted_names, nm);
		} else {
			strcat(formatted_names, ",");
			strcat(formatted_names, nm);
		}
		free(nm);

		len += hlen + 2;

		token = strtok_r(NULL, ",", &saveptr);
	}

	tpp_conf->node_name = formatted_names;
	tpp_conf->node_type = TPP_LEAF_NODE;
	tpp_conf->numthreads = 1;

	/* set authentication method and routines */
	tpp_conf->auth_type = auth_type;
	tpp_conf->get_ext_auth_data = cb_get_ext_auth_data;
	tpp_conf->validate_ext_auth_data = cb_validate_ext_auth_data;

	if (auth_type == TPP_AUTH_RESV_PORT) {
		snprintf(log_buffer, TPP_LOGBUF_SZ, "TPP set to use reserved port authentication");
	} else {
		snprintf(log_buffer, TPP_LOGBUF_SZ, "TPP set to use external authentication");
	}
	tpp_log_func(LOG_INFO, NULL, log_buffer);

#ifdef PBS_COMPRESSION_ENABLED
	tpp_conf->compress = compress;
#else
	tpp_conf->compress = 0;
#endif

	/* set default parameters for keepalive */
	tpp_conf->tcp_keepalive = 1;
	tpp_conf->tcp_keep_idle = DEFAULT_TCP_KEEPALIVE_TIME;
	tpp_conf->tcp_keep_intvl = DEFAULT_TCP_KEEPALIVE_INTVL;
	tpp_conf->tcp_keep_probes = DEFAULT_TCP_KEEPALIVE_PROBES;

	/* if set, read them from environment variable PBS_TCP_KEEPALIVE */
	if ((s = getenv(PBS_TCP_KEEPALIVE))) {
		/*
		 * The format is a comma separated list of values in order, for the following variables,
		 * tcp_keepalive_enable,tcp_keepalive_time,tcp_keepalive_intvl,tcp_keepalive_probes
		 */
		tpp_conf->tcp_keepalive = 0;
		t = strtok_r(s, ",", &ctx);
		if (t) {
			/* this has to be the tcp_keepalive_enable value */
			if (atol(t) == 1) {
				tpp_conf->tcp_keepalive = 1;

				/* parse other values only if this is enabled */
				if ((t = strtok_r(NULL, ",", &ctx))) {
					/* tcp_keepalive_time */
					tpp_conf->tcp_keep_idle = (int) atol(t);
				}

				if (t && (t = strtok_r(NULL, ",", &ctx))) {
					/* tcp_keepalive_intvl */
					tpp_conf->tcp_keep_intvl = (int) atol(t);
				}

				if (t && (t = strtok_r(NULL, ",", &ctx))) {
					/* tcp_keepalive_probes */
					tpp_conf->tcp_keep_probes = (int) atol(t);
				}

				/* emit a log depicting what we are going to use as keepalive */
				snprintf(log_buffer, TPP_LOGBUF_SZ,
						"Using tcp_keepalive_time=%d, tcp_keepalive_intvl=%d, tcp_keepalive_probes=%d",
						tpp_conf->tcp_keep_idle, tpp_conf->tcp_keep_intvl, tpp_conf->tcp_keep_probes);
			} else {
				snprintf(log_buffer, TPP_LOGBUF_SZ, "tcp keepalive disabled");
			}
		}
		tpp_log_func(LOG_CRIT, NULL, log_buffer);
	}

	tpp_conf->buf_limit_per_conn = 5000; /* size in KB, TODO: load from pbs.conf */

	if (pbs_conf->pbs_use_ft == 1)
		tpp_conf->force_fault_tolerance = 1;
	else
		tpp_conf->force_fault_tolerance = 0;

	if (routers && routers[0] != '\0') {
		char *p = routers;
		char *q;

		num_routers = 1;

		while (*p) {
			if (*p == ',')
				num_routers++;
			p++;
		}

		tpp_conf->routers = malloc(sizeof(char *) * (num_routers + 1));
		if (!tpp_conf->routers) {
			tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating routers array");
			if (routers)
				free(routers);
			return -1;
		}

		p = routers;

		/* trim leading spaces, if any */
		while (*p && (*p == ' ' || *p == '\t'))
			p++;

		q = p;
		i = 0;
		while (*p) {
			if (*p == ',') {
				*p = 0;
				tpp_conf->routers[i++] = strdup(q);

				p++; /* go past the null char and trim any spaces */
				while (*p && (*p == ' ' || *p == '\t'))
					p++;

				q = p;
			}
			p++;
		}

		nm = mk_hostname(q, TPP_DEF_ROUTER_PORT);
		if (!nm) {
			snprintf(log_buffer, TPP_LOGBUF_SZ, "Failed to make router name");
			fprintf(stderr, "%s\n", log_buffer);
			tpp_log_func(LOG_CRIT, NULL, log_buffer);
			return -1;
		}
		tpp_conf->routers[i++] = nm;
		tpp_conf->routers[i++] = NULL;

	} else {
		tpp_conf->routers = NULL;
	}

	for (i = 0; i < num_routers; i++) {
		if (tpp_conf->routers[i] == NULL || strcmp(tpp_conf->routers[i], tpp_conf->node_name) == 0) {
			snprintf(log_buffer, TPP_LOGBUF_SZ, "Router name NULL or points to same node endpoint %s",
				(tpp_conf->routers[i]) ?(tpp_conf->routers[i]) : "");
			fprintf(stderr, "%s\n", log_buffer);
			tpp_log_func(LOG_CRIT, NULL, log_buffer);

			if (tpp_conf->routers)
				free(tpp_conf->routers);
			return -1;
		}
	}

	if (routers)
		free(routers);

	return 0;
}

/**
 * @brief
 *	Setup tpp function pointers (used to dynamically interchange code to use
 *	either TPP or RPP
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
set_tpp_funcs(void (*log_fn)(int, const char *, char *))
{
	pfn_rpp_open = tpp_open;
	pfn_rpp_bind = tpp_bind;
	pfn_rpp_poll = tpp_poll;
	pfn_rpp_io = tpp_io;
	pfn_rpp_read = tpp_recv;
	pfn_rpp_write = tpp_send;
	pfn_rpp_close = tpp_close;
	pfn_rpp_destroy = (void (*)(int)) &tpp_close;
	pfn_rpp_localaddr = tpp_localaddr;
	pfn_rpp_getaddr = tpp_getaddr;
	pfn_rpp_flush = tpp_flush;
	pfn_rpp_shutdown = tpp_shutdown;
	pfn_rpp_terminate = tpp_terminate;
	pfn_rpp_rcommit = tppdis_rcommit;
	pfn_rpp_wcommit = tppdis_wcommit;
	pfn_rpp_skip = tppdis_rskip;
	pfn_rpp_eom = tpp_eom;
	pfn_rpp_getc = tppdis_getc;
	pfn_rpp_putc = NULL;
	pfn_DIS_rpp_reset = DIS_tpp_reset;
	pfn_DIS_rpp_setup = DIS_tpp_setup;
	pfn_rpp_add_close_func = tpp_add_close_func;
	tpp_log_func = log_fn;
}

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
#include <errno.h>
#include <assert.h>
#include <stdlib.h>
#include <arpa/inet.h>
#ifdef WIN32
#include <winsock.h>
#endif
#include "dis.h"
#include "pbs_error.h"
#include "pbs_internal.h"
#include "auth.h"

static pbs_dis_buf_t * dis_get_readbuf(int);
static pbs_dis_buf_t * dis_get_writebuf(int);
static int __transport_read(int fd);
static void dis_pack_buf(pbs_dis_buf_t *);
static int dis_resize_buf(pbs_dis_buf_t *, size_t, size_t);
static int transport_chan_is_encrypted(int);
static int dis_encrypt_and_send(int, void *, size_t);
static int dis_recv_and_decrypt(int, void **, size_t *);

/**
 * @brief
 * 	transport_chan_set_ctx_status - set auth context status tcp chan assosiated with given fd
 *
 * @param[in] fd - file descriptor
 * @param[in] status - auth ctx status
 * @param[in] for_encrypt - is authctx for encrypt/decrypt?
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
transport_chan_set_ctx_status(int fd, int status, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);
	if (chan == NULL)
		return;
	chan->auths[for_encrypt].ctx_status = status;
}

/**
 * @brief
 * 	transport_chan_get_ctx_status - get auth context status tcp chan assosiated with given fd
 *
 * @param[in] fd - file descriptor
 * @param[in] for_encrypt - whether to get encrypt/decrypt authctx status or for authentication
 *
 * @return int
 *
 * @retval -1 - error
 * @retval !-1 - status
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
transport_chan_get_ctx_status(int fd, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);
	if (chan == NULL)
		return -1;
	return chan->auths[for_encrypt].ctx_status;
}

/**
 * @brief
 * 	transport_chan_set_authctx - associates authenticaion context with connection
 *
 * @param[in] fd - file descriptor
 * @param[in] authctx - the context
 * @param[in] for_encrypt - is authctx for encrypt/decrypt?
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
transport_chan_set_authctx(int fd, void *authctx, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);
	if (chan == NULL)
		return;
	chan->auths[for_encrypt].ctx = authctx;
}

/**
 * @brief
 * 	transport_chan_get_authctx - gets authentication context associated with connection
 *
 * @param[in] fd - file descriptor
 * @param[in] for_encrypt - whether to get encrypt/decrypt authctx or for authentication
 *
 * @return void *
 *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void *
transport_chan_get_authctx(int fd, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);
	if (chan == NULL)
		return NULL;
	return chan->auths[for_encrypt].ctx;
}

/**
 * @brief
 * 	transport_chan_set_authdef - associates authdef structure with connection
 *
 * @param[in] fd - file descriptor
 * @param[in] authdef - the authdef structure for association
 * @param[in] for_encrypt - is authdef for encrypt/decrypt?
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
transport_chan_set_authdef(int fd, auth_def_t *authdef, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);
	if (chan == NULL)
		return;
	chan->auths[for_encrypt].def = authdef;
}

/**
 * @brief
 * 	transport_chan_get_authdef - gets authdef structure associated with connection
 *
 * @param[in] fd - file descriptor
 * @param[in] for_encrypt - whether to get encrypt/decrypt authdef or for authentication
 *
 * @return auth_def_t *
 *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
auth_def_t *
transport_chan_get_authdef(int fd, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);
	if (chan == NULL)
		return NULL;
	return chan->auths[for_encrypt].def;
}


/**
 * @brief
 * 	transport_chan_is_encrypted - is chan assosiated with given fd is encrypted?
 *
 * @param[in] fd - file descriptor
 *
 * @return int
 *
 * @retval 0 - not encrypted
 * @retval 1 - encrypted
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
transport_chan_is_encrypted(int fd)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);
	if (chan == NULL)
		return 0;
	return (chan->auths[FOR_ENCRYPT].def != NULL && chan->auths[FOR_ENCRYPT].ctx_status == AUTH_STATUS_CTX_READY);
}

int
transport_send_pkt(int fd, int type, void *data_in, size_t len_in)
{
	int i = 0;
	int ndlen = 0;
	void *pkt = NULL;
	char *pos = NULL;
	size_t pktlen = 1 + sizeof(int) + len_in;

	pkt = malloc(pktlen);
	if (pkt == NULL)
		return -1;
	pos = (char *)pkt;
	*pos++ = (char)type;
	ndlen = htonl(len_in);
	memcpy(pos, &ndlen, sizeof(int));
	pos += sizeof(int);

	memcpy(pos, data_in, len_in);

	i = transport_send(fd, pkt, pktlen);
	free(pkt);
	if (i > 0 && i != pktlen)
		return -1;
	return i;
}

int
transport_recv_pkt(int fd, int *type, void **data_out, size_t *len_out)
{
	int i = 0;
	char ndbuf[sizeof(int)];
	int ndlen = 0;
	size_t datasz = 0;
	void *data = NULL;

	*type = 0;
	*data_out = NULL;
	*len_out = 0;

	i = transport_recv(fd, (void *)type, 1);
	if (i != 1)
		return i;

	i = transport_recv(fd, (void *)&ndbuf, sizeof(int));
	if (i != sizeof(int))
		return i;
	memcpy(&ndlen, (void *)&ndbuf, sizeof(int));
	datasz = ntohl(ndlen);
	if (datasz <= 0) {
		return -1;
	}

	data = malloc(datasz);
	if (data == NULL) {
		return -1;
	}
	i = transport_recv(fd, data, datasz);
	if (i != datasz) {
		free(data);
		return i;
	}

	*data_out = data;
	*len_out = datasz;

	return i;
}

/**
 * @brief
 * 	dis_encrypt_and_send - encrypt given data, assemble and send auth token
 *
 * @param[in] fd - file descriptor
 * @param[in] data_in - clear text data to send
 * @param[in] len_in - length of clear text data
 *
 * @return	int
 * @retval	>0	number of characters send
 * @retval	0	if EOD (no data currently avalable)
 * @retval	-1	if error
 * @retval	-2	if EOF (stream closed)
 *
 */
static int
dis_encrypt_and_send(int fd, void *data_in, size_t len_in)
{
	void *authctx = transport_chan_get_authctx(fd, FOR_ENCRYPT);
	auth_def_t *authdef = transport_chan_get_authdef(fd, FOR_ENCRYPT);
	void *data_out = NULL;
	size_t len_out = 0;
	int rc = 0;

	if (data_in == NULL || len_in == 0 || authdef == NULL || authdef->encrypt_data == NULL)
		return -1;

	if (authdef->encrypt_data(authctx, data_in, len_in, &data_out, &len_out) != 0)
		return -1;

	if (len_out <= 0)
		return -1;

	rc = transport_send_pkt(fd, AUTH_ENCRYPTED_DATA, data_out, len_out);
	if (rc <= 0) {
		free(data_out);
		return rc;
	}

	free(data_out);

	return len_out;
}

/**
 * @brief
 * 	dis_recv_and_decrypt - recv and decrypt auth token
 *
 * @param[in] fd - file descriptor
 * @param[out] data_out - received (after decrypt) clear text
 * @param[out] len_out - length of clear text data
 *
 * @return	int
 * @retval	>0	number of characters read
 * @retval	0	if EOD (no data currently avalable)
 * @retval	-1	if error
 * @retval	-2	if EOF (stream closed)
 *
 */
static int
dis_recv_and_decrypt(int fd, void **data_out, size_t *len_out)
{
	void *authctx = transport_chan_get_authctx(fd, FOR_ENCRYPT);
	auth_def_t *authdef = transport_chan_get_authdef(fd, FOR_ENCRYPT);
	void *data_in = NULL;
	size_t len_in = 0;
	int type = 0;
	int rc = 0;

	*data_out = NULL;
	*len_out = 0;

	if (authdef == NULL || authdef->decrypt_data == NULL)
		return -1;

	rc = transport_recv_pkt(fd, &type, &data_in, &len_in);
	if (rc <= 0)
		return rc;

	if (type != AUTH_ENCRYPTED_DATA)
		return -1;

	if (len_in == 0)
		return -2;

	if (authdef->decrypt_data(authctx, data_in, len_in, data_out, len_out) != 0) {
		free(data_in);
		return -1;
	}

	free(data_in);

	return *len_out;
}

/**
 * @brief
 * 	dis_get_readbuf - get dis read buffer associated with connection
 *
 * @return pbs_dis_but_t *
 *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static pbs_dis_buf_t *
dis_get_readbuf(int fd)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);
	if (chan == NULL)
		return NULL;
	return &(chan->readbuf);
}

/**
 * @brief
 * 	dis_get_writebuf - get dis write buffer associated with connection
 *
 * @return pbs_dis_but_t *
 *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static pbs_dis_buf_t *
dis_get_writebuf(int fd)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);
	if (chan == NULL)
		return NULL;
	return &(chan->writebuf);
}

/**
 * @brief
 * 	dis_pack_buf - pack existing data into front of dis buffer
 *
 *	Moves "uncommited" data to front of dis buffer and adjusts counters.
 *	Does a character by character move since data may over lap.
 *
 * @param[in] tp - dis buffer to pack
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static void
dis_pack_buf(pbs_dis_buf_t *tp)
{
	size_t amt = 0;
	size_t start = 0;
	size_t i = 0;

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
 * 	dis_resize_buf - resize given dis buffer to appropriate size based on given needed
 *
 * 	if use_lead is true then it will use tdis_lead to calculate new size else tdis_eod
 *
 * @param[in] tp - dis buffer to pack
 * @param[in] needed - min needed buffer size
 * @param[in] use_lead - use tdis_lead or tdis_eod to calculate new size
 *
 * @return int
 *
 * @retval 0 - success
 * @retval -1 - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
dis_resize_buf(pbs_dis_buf_t *tp, size_t needed, size_t use_lead)
{
	size_t len = 0;
	size_t dlen = 0;
	char *tmpcp = NULL;

	if (use_lead)
		dlen = tp->tdis_lead;
	else
		dlen = tp->tdis_eod;
	len = tp->tdis_bufsize - dlen;
	if (needed > len) {
		size_t ru = 0;
		size_t newsz = 0;
		if (use_lead) {
			ru = needed + tp->tdis_lead;
		} else {
			ru = needed + tp->tdis_lead + tp->tdis_eod;
		}
		ru = ru / PBS_DIS_BUFSZ;
		newsz = (ru + 1) * PBS_DIS_BUFSZ;
		tmpcp = (char *) realloc(tp->tdis_thebuf, sizeof(char) * newsz);
		if (tmpcp == NULL) {
			return -1; /* realloc failed */
		} else {
			tp->tdis_thebuf = tmpcp;
			tp->tdis_bufsize = newsz;
		}
	}
	return 0;
}

/**
 * @brief
 * 	dis_clear_buf - reset dis buffer to empty by updating its counter
 *
 *
 * @param[in] tp - dis buffer to clear
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
dis_clear_buf(pbs_dis_buf_t *tp)
{
	tp->tdis_lead = 0;
	tp->tdis_trail = 0;
	tp->tdis_eod = 0;
}

/**
 * @brief
 * 	dis_reset_buf - reset appropriate dis buffer associated with connection
 *
 * @param[in] fd - file descriptor
 * @param[in] rw - reset write buffer if true else read buffer
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
dis_reset_buf(int fd, int rw)
{
	dis_clear_buf((rw == DIS_WRITE_BUF) ? dis_get_writebuf(fd) : dis_get_readbuf(fd));
}

/**
 * @brief
 * 	disr_skip - dis suport routine to skip over data in read buffer
 *
 * @param[in] fd - file descriptor
 * @param[in] ct - count
 *
 * @return	int
 *
 * @retval	number of characters skipped
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
disr_skip(int fd, size_t ct)
{
	pbs_dis_buf_t *tp = dis_get_readbuf(fd);
	if (tp == NULL)
		return 0;
	if (tp->tdis_lead - tp->tdis_eod < ct)
		ct = tp->tdis_lead - tp->tdis_eod;
	tp->tdis_lead += ct;
	return (int)ct;
}

/**
 * @brief
 * 	__transport_read - read data from connection to "fill" the buffer
 *	Update the various buffer pointers.
 *
 * @param[in] fd - socket descriptor
 *
 * @return	int
 *
 * @retval	>0 	number of characters read
 * @retval	0 	if EOD (no data currently avalable)
 * @retval	-1 	if error
 * @retval	-2 	if EOF (stream closed)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
__transport_read(int fd)
{
	int i;
	void *data = NULL;
	size_t len = 0;
	pbs_dis_buf_t *tp = dis_get_readbuf(fd);

	if (tp == NULL)
		return -1;
	dis_pack_buf(tp);
	if (transport_chan_is_encrypted(fd)) {
		i = dis_recv_and_decrypt(fd, &data, &len);
	} else {
		int type; /* unused */
		i = transport_recv_pkt(fd, &type, &data, &len);
	}
	if (i <= 0)
		return i;
	dis_resize_buf(tp, len, 0);
	memcpy(&(tp->tdis_thebuf[tp->tdis_eod]), data, len);
	tp->tdis_eod += len;
	free(data);
	return len;
}

/**
 * @brief
 * 	dis_getc - dis support routine to get next character from read buffer
 *
 * @param[in] fd - file descriptor
 *
 * @return	int
 *
 * @retval	>0 	number of characters read
 * @retval	-1 	if EOD or error
 * @retval	-2 	if EOF (stream closed)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
dis_getc(int fd)
{
	int x = 0;
	pbs_dis_buf_t *tp = dis_get_readbuf(fd);

	if (tp == NULL)
		return -1;
	if (tp->tdis_lead >= tp->tdis_eod) {
		/* not enought data, try to get more */
		x = __transport_read(fd);
		if (x <= 0)
			return ((x == -2) ? -2 : -1);	/* Error or EOF */
	}
	return ((int)tp->tdis_thebuf[tp->tdis_lead++]);
}

/**
 * @brief
 * 	dis_gets - dis support routine to get a string from read buffer
 *
 * @param[in] fd - file descriptor
 * @param[in] str - string to be written
 * @param[in] ct - count
 *
 * @return	int
 *
 * @retval	>0 	number of characters read
 * @retval	0 	if EOD (no data currently avalable)
 * @retval	-1 	if error
 * @retval	-2 	if EOF (stream closed)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
dis_gets(int fd, char *str, size_t ct)
{
	int x = 0;
	pbs_dis_buf_t *tp = dis_get_readbuf(fd);

	if (tp == NULL) {
		*str = '\0';
		return -1;
	}
	while (tp->tdis_eod - tp->tdis_lead < ct) {
		/* not enought data, try to get more */
		x = __transport_read(fd);
		if (x <= 0)
			return x;	/* Error or EOF */
	}
	(void)memcpy(str, &tp->tdis_thebuf[tp->tdis_lead], ct);
	tp->tdis_lead += ct;
	return (int)ct;
}

/**
 * @brief
 * 	dis_puts - dis support routine to put a counted string of characters
 *	into the write buffer.
 *
 * @param[in] fd - file descriptor
 * @param[in] str - string to be written
 * @param[in] ct - count
 *
 * @return	int
 *
 * @retval	>= 0	the number of characters placed
 * @retval	-1 	if error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
dis_puts(int fd, const char *str, size_t ct)
{
	pbs_dis_buf_t *tp = dis_get_writebuf(fd);
	if (tp == NULL)
		return -1;
	if (dis_resize_buf(tp, ct, 1) != 0)
		return -1;
	(void)memcpy(&tp->tdis_thebuf[tp->tdis_lead], str, ct);
	tp->tdis_lead += ct;
	return ct;
}

/**
 * @brief
 * 	disr_commit - dis support routine to commit/uncommit read data
 *
 * @param[in] fd - file descriptor
 * @param[in] commit_flag - indication for commit or uncommit
 *
 * @return int
 *
 * @retval 0 - success
 * @retval -1 - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
disr_commit(int fd, int commit_flag)
{
	pbs_dis_buf_t *tp = dis_get_readbuf(fd);
	if (tp == NULL)
		return -1;
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
 * 	disw_commit - dis support routine to commit/uncommit write data
 *
 * @param[in] fd - file descriptor
 * @param[in] commit_flag - indication for commit or uncommit
 *
 * @return int
 *
 * @retval 0 - success
 * @retval -1 - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
disw_commit(int fd, int commit_flag)
{
	pbs_dis_buf_t *tp = dis_get_writebuf(fd);
	if (tp == NULL)
		return -1;
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
 *	flush dis write buffer
 *
 *	Writes "committed" data in buffer to file descriptor,
 *	packs remaining data (if any), resets pointers
 *
 * @param[in] - fd - file descriptor
 *
 * @return int
 *
 * @retval  0 on success
 * @retval -1 on error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
dis_flush(int fd)
{
	pbs_dis_buf_t *tp = dis_get_writebuf(fd);

	if (tp == NULL)
		return -1;
	if (tp->tdis_trail == 0)
		return 0;
	if (transport_chan_is_encrypted(fd)) {
		if (dis_encrypt_and_send(fd, (void *)tp->tdis_thebuf, tp->tdis_trail) <= 0)
			return -1;
	} else {
		/* DIS doesn't have pkt type, pass 0 always for type in transport_send_pkt */
		if (transport_send_pkt(fd, 0, (void *)tp->tdis_thebuf, tp->tdis_trail) <= 0)
			return -1;
	}
	tp->tdis_eod = tp->tdis_lead;
	dis_pack_buf(tp);
	return 0;
}

/**
 * @brief
 * 	dis_destroy_chan - release structures associated with fd
 *
 * @param[in] fd - socket descriptor
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
dis_destroy_chan(int fd)
{
	pbs_tcp_chan_t *chan = NULL;

	if (pfn_transport_get_chan == NULL)
		return;
	chan = transport_get_chan(fd);
	if (chan != NULL) {
		if (chan->auths[FOR_AUTH].ctx || chan->auths[FOR_ENCRYPT].ctx) {
			/* DO NOT free authdef here, it will be done in unload_auths() */
			if (chan->auths[FOR_AUTH].ctx && chan->auths[FOR_AUTH].def) {
				chan->auths[FOR_AUTH].def->destroy_ctx(chan->auths[FOR_AUTH].ctx);
			}
			if (chan->auths[FOR_ENCRYPT].def != chan->auths[FOR_AUTH].def &&
				chan->auths[FOR_ENCRYPT].ctx &&
				chan->auths[FOR_ENCRYPT].def) {
				chan->auths[FOR_ENCRYPT].def->destroy_ctx(chan->auths[FOR_ENCRYPT].ctx);
			}
			chan->auths[FOR_AUTH].ctx = NULL;
			chan->auths[FOR_AUTH].def = NULL;
			chan->auths[FOR_AUTH].ctx_status = AUTH_STATUS_UNKNOWN;
			chan->auths[FOR_ENCRYPT].ctx = NULL;
			chan->auths[FOR_ENCRYPT].def = NULL;
			chan->auths[FOR_ENCRYPT].ctx_status = AUTH_STATUS_UNKNOWN;
		}
		if (chan->readbuf.tdis_thebuf) {
			free(chan->readbuf.tdis_thebuf);
			chan->readbuf.tdis_thebuf = NULL;
		}
		if (chan->writebuf.tdis_thebuf) {
			free(chan->writebuf.tdis_thebuf);
			chan->writebuf.tdis_thebuf = NULL;
		}
		free(chan);
		transport_set_chan(fd, NULL);
	}
}


/**
 * @brief
 *	allocate dis buffers associated with connection, if already allocated then clear it
 *
 * @param[in] fd - file descriptor
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
dis_setup_chan(int fd, pbs_tcp_chan_t * (*inner_transport_get_chan)(int))
{
	pbs_tcp_chan_t *chan;
	int rc;

	/* check for bad file descriptor */
	if (fd < 0)
		return;
	chan = (pbs_tcp_chan_t *)(*inner_transport_get_chan)(fd);
	if (chan == NULL) {
		if (errno == ENOTCONN)
			return;
		chan = (pbs_tcp_chan_t *) calloc(1, sizeof(pbs_tcp_chan_t));
		assert(chan != NULL);
		chan->readbuf.tdis_thebuf = calloc(1, PBS_DIS_BUFSZ);
		assert(chan->readbuf.tdis_thebuf != NULL);
		chan->readbuf.tdis_bufsize = PBS_DIS_BUFSZ;
		chan->writebuf.tdis_thebuf = calloc(1, PBS_DIS_BUFSZ);
		assert(chan->writebuf.tdis_thebuf != NULL);
		chan->writebuf.tdis_bufsize = PBS_DIS_BUFSZ;
		rc = transport_set_chan(fd, chan);
		assert(rc == 0);
	}

	/* initialize read and write buffers */
	dis_clear_buf(&(chan->readbuf));
	dis_clear_buf(&(chan->writebuf));
}

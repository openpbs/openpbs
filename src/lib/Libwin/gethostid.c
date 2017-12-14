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

#include <stdio.h>
#include <windows.h>
#include <win.h>

/**
 * @file	gethostid.c
 */
/**
 * @brief
 *	get_loworder_macaddr: get the lower 4 bytes of the ethernet mac address for
 *	adapter 0 if it exists, or the next ethernet adapter found.
 *	
 * @return	unsigned long
 * @retval	0		if no adapter was found. 
 * @retval	lower 4 bytes	success
 *
 */

static unsigned long
get_loworder_macaddr(void)
{

	NCB Ncb;
	unsigned char ret_code;
	struct ASTAT {
		ADAPTER_STATUS adapt;
		NAME_BUFFER namebuf[30];
	} Adapter;
	LANA_ENUM lenum;
	int i;

	union {
		unsigned long whole;
		unsigned char part[4];
	} addr0, addr;

	addr0.whole= 0;
	addr.whole = 0;

	memset(&Ncb, 0, sizeof(Ncb));
	Ncb.ncb_command = NCBENUM;
	Ncb.ncb_buffer = (unsigned char *)&lenum;
	Ncb.ncb_length = sizeof((lenum));
	ret_code = Netbios(&Ncb);

	if (ret_code != NRC_GOODRET)
		return (0);

	for (i=0; i < lenum.length; i++) {
		memset(&Ncb, 0, sizeof(Ncb));
		Ncb.ncb_command = NCBRESET;
		Ncb.ncb_lana_num = lenum.lana[i];
		Netbios(&Ncb);

		memset(&Ncb, 0, sizeof(Ncb));
		Ncb.ncb_command = NCBASTAT;
		Ncb.ncb_lana_num = lenum.lana[i];
		strcpy((char*)Ncb.ncb_callname,  "*               ");
		Ncb.ncb_buffer = (unsigned char *) &Adapter;
		Ncb.ncb_length = sizeof(Adapter);
		ret_code = Netbios(&Ncb);

		if (ret_code == NRC_GOODRET) {

			if (lenum.lana[i] == 0) {
				addr0.part[3] = Adapter.adapt.adapter_address[2];
				addr0.part[2] = Adapter.adapt.adapter_address[3];
				addr0.part[1] = Adapter.adapt.adapter_address[4];
				addr0.part[0] = Adapter.adapt.adapter_address[5];
			} else {
				if (addr.whole == 0) {
					addr.part[3] = Adapter.adapt.adapter_address[2];
					addr.part[2] = Adapter.adapt.adapter_address[3];
					addr.part[1] = Adapter.adapt.adapter_address[4];
					addr.part[0] = Adapter.adapt.adapter_address[5];
				}
			}
		}

	}
	if (addr0.whole != 0)
		return (addr0.whole);

	if (addr.whole != 0)
		return (addr.whole);

	return (0);
}

/**
 * @brief 
 *	gethostid: returns host's SID if one is assigned, or the loworder 4 bytes
 *	if the ethernet MAC address. 
 * 
 * @return	int
 * @retval	0 	means a hostid could not be determined. 
 *
 */
long int
gethostid(void)
{
	char	cname[80];
	char	domain[80];
	SID		*sid;
	SID_NAME_USE use;
	DWORD	*rid;
	DWORD	sz, sz1, sz2;
	long int	ret = 0;

	sz = sizeof(cname);

	if (GetComputerName(cname, &sz) == 0)
		return (ret);

	sz1 = 0;
	sz2 = sizeof(domain);

	if (LookupAccountName(NULL, cname, &sid, &sz1, domain, &sz2, &use) != 0)
		return (ret);

	sid = malloc(sz1);
	if (sid == NULL) {
		return (ret);
	}

	if (LookupAccountName(NULL, cname, sid, &sz1, domain, &sz2, &use) == 0) {
		(void)free(sid);

		ret = get_loworder_macaddr();
		return (ret);
	}

	/* The last sub-authority of the machine SID is always -1, so use the
	 second to last. */

	rid = GetSidSubAuthority(sid, *GetSidSubAuthorityCount(sid) - 1);
	if (rid)
		ret = *rid;

	(void)free(sid);
	return (ret);
}

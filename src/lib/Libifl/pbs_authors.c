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
#include "pbs_version.h"

void
pbs_authors()
{
	printf("\n\tVersion %s of PBS Professional is brought to you by Altair Engineering, Inc.\n\n", pbs_version);
	printf("\t Copyright (C) 1994-2019 Altair Engineering, Inc.\n");
	printf("\t For more information, contact Altair at www.altair.com.\n\n");
	printf("\t This file is part of the PBS Professional(\"PBS Pro\") software.\n\n");
	printf("\t Open Source License Information:\n");
	printf("\t PBS Pro is free software. You can redistribute it and/or modify it under the\n");
	printf("\t terms of the GNU Affero General Public License as published by the Free \n");
	printf("\t Software Foundation, either version 3 of the License, or (at your option) any\n");
	printf("\t later version.\n\n");
	printf("\t PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY\n");
	printf("\t WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS\n");
	printf("\t FOR A PARTICULAR PURPOSE.\n\n");
	printf("\t See the GNU Affero General Public License for more details.\n");
	printf("\t You should have received a copy of the GNU Affero General Public License\n\n");
	printf("\t along with this program.  If not, see <http://www.gnu.org/licenses/>.\n");
	printf("\t Commercial License Information:\n");
	printf("\t For a copy of the commercial license terms and conditions,\n");
	printf("\t go to: (http://www.pbspro.com/UserArea/agreement.html)\n\n");
	printf("\t or contact the Altair Legal Department.\n");
	printf("\t Altair’s dual-license business model allows companies, individuals, and\n");
	printf("\t organizations to create proprietary derivative works of PBS Pro and\n");
	printf("\t under a commercial license agreement.\n");
        printf("\t Use of Altair’s trademarks, including but not limited to \"PBS™\",\n");
        printf("\t \"PBS Professional®\", and \"PBS Pro™\" and Altair’s logos is subject to Altair's\n");
        printf("\t trademark licensing policies.\n\n");
        
}

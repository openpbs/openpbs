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
 *  @file    pbs_config_add_win.c
 *
 *  @brief
 *		pbs_config_add_win - Add the pbs configurations on Windows.
 *
 * Functions included are:
 * 	main()
 */
#include <pbs_config.h>
#include <stdio.h>
#include <pbs_ifl.h>
#include <windows.h>
#include <time.h>
#include "win.h"
#include "log.h"
/**
 * @brief
 * 		main - the entry point in pbs_config_add_win.c
 *
 * @param[in]	argc	-	argument count
 * @param[in]	argv	-	argument variables.
 *
 * @return	int
 */
main(int argc, char **argv)
{
	char	conf_filename2[MAX_PATH+1];
	char	*conf_filename;
	FILE	*fp, *fp2;
	char	buf[1024];
	char	arg_cname[1024];
	char	conf_name[1024];
	char	*p;

	if(set_msgdaemonname("pbs-config-add")) {
		fprintf(stderr, "Out of memory\n");
		return 1;
	}
	if (argc != 2) {
		fprintf(stderr, "%s: <entry>\n", argv[0]);
		exit(1);
	}

	srand((unsigned)time(NULL));

	if ((conf_filename=getenv("PBS_CONF_FILE")) == NULL)
		conf_filename = PBS_CONF_FILE;

	sprintf(conf_filename2, "%s.%d", conf_filename, rand());
	if ((fp2=fopen(conf_filename2, "w")) == NULL) {
		fprintf(stderr, "failed to open temp file %s",
			conf_filename2);
		exit(1);
	}
	arg_cname[0] = '\0';
	if (p=strchr(argv[1], '=')) {
		*p = '\0';
		strcpy(arg_cname, argv[1]);
		*p = '=';
	}

	if (fp = fopen(conf_filename, "r")) {

		while (fgets(buf, 1024, fp) != NULL) {
			conf_name[0] = '\0';
			if (p = strchr(buf, '=')) {
				*p = '\0';
				strcpy(conf_name, buf);
				*p = '=';
			}
			if (strlen(conf_name) == 0) {
				printf("%s: bad conf line\n", buf);
				continue;
			}

			if (stricmp(conf_name, arg_cname) != 0)
				fputs(buf, fp2);
			else
				printf("Replacing entry %s\n", buf);

		}
		fclose(fp);
	}

	fputs(argv[1], fp2);
	fputs("\n", fp2);
	fclose(fp2);

	unlink(conf_filename);
	rename(conf_filename2, conf_filename);
	printf("added entry %s to %s file\n", argv[1], conf_filename);
	secure_file(conf_filename, "\\Everyone", READS_MASK | READ_CONTROL);

}

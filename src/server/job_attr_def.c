/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

      #include <pbs_config.h>   
      #include <sys/types.h>
      #include "pbs_ifl.h"
      #include "list_link.h"
      #include "attribute.h"
      #include "job.h"
      #include "server_limits.h"
   
      attribute_def job_attr_def[] = {


      /* JOB_ATR_jobname */

	{
		ATTR_N,
		decode_jobname,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "Job_Owner" */

	{
		ATTR_owner,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SSET | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_resc_used" */

	{
		ATTR_used,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SvWR | ATR_DFLAG_NOSAVM,
		ATR_TYPE_RESC,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_state" */

	{
		ATTR_state,
		decode_c,
		encode_c,
		set_c,
		comp_c,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_CHAR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_in_queue" */

	{
		ATTR_queue,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_at_server" */

	{
		ATTR_server,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_account" */

	{
		ATTR_A,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM | ATR_DFLAG_SCGALT,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_chkpnt" */

	{
		ATTR_c,
		decode_str,
		encode_str,
		set_str,
		#ifdef PBS_MOM
			comp_str,
		#else
			comp_chkpnt,
		#endif
		free_str,
		#ifdef PBS_MOM
			NULL_FUNC,
		#else
			ck_chkpnt,
		#endif
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_ALTRUN,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_ctime" */

	{
		ATTR_ctime,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_depend" */

	{
		ATTR_depend,
		#ifndef PBS_MOM
			decode_depend,
		#else
			decode_str,
		#endif
		#ifndef PBS_MOM
			encode_depend,
		#else
			encode_str,
		#endif
		#ifndef PBS_MOM
			set_depend,
		#else
			set_str,
		#endif
		#ifndef PBS_MOM
			comp_depend,
		#else
			comp_str,
		#endif
		#ifndef PBS_MOM
			free_depend,
		#else
			free_str,
		#endif
		#ifndef PBS_MOM
			depend_on_que,
		#else
			NULL_FUNC,
		#endif
		READ_WRITE,
		ATR_TYPE_LIST,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_errpath" */

	{
		ATTR_e,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_exec_host" */

	{
		ATTR_exechost,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		#ifdef PBS_MOM
			READ_ONLY | ATR_DFLAG_MOM,
		#else
			READ_ONLY,
		#endif
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_exec_host2" */

	{
		ATTR_exechost2,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_exec_vnode" */

	{
		ATTR_execvnode,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_exectime" */

	{
		ATTR_a,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		#ifndef PBS_MOM
			job_set_wait,
		#else
			NULL_FUNC,
		#endif
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_grouplst" */

	{
		ATTR_g,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM | ATR_DFLAG_SCGALT,
		ATR_TYPE_ARST,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_hold" */

	{
		ATTR_h,
		decode_hold,
		encode_hold,
		set_b,
		comp_hold,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_interactive" */

	{
		ATTR_inter,
		decode_l,
		encode_inter,
		set_l,
		comp_b,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_join" */

	{
		ATTR_j,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_keep" */

	{
		ATTR_k,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_mailpnts" */

	{
		ATTR_m,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_mailuser" */

	{
		ATTR_M,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		PARENT_TYPE_JOB
	},

      /* JOB_ATR_mtime */

	{
		ATTR_mtime,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_nodemux" */

	{
		ATTR_nodemux,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_SELEQ,
		ATR_TYPE_BOOL,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_outpath" */

	{
		ATTR_o,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_priority" */

	{
		ATTR_p,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_qtime"  (time entered queue) */

	{
		ATTR_qtime,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_rerunable" */

	{
		ATTR_r,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ,
		ATR_TYPE_BOOL,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_resource" */

	{
		ATTR_l,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		action_resc_job,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_MOM | ATR_DFLAG_SCGALT,
		ATR_TYPE_RESC,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_SchedSelect" */

	{
		ATTR_SchedSelect,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_MGRD | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_stime"  (time started execution)  */

	{
		ATTR_stime,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_session_id"  */

	{
		ATTR_session,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_shell"  */

	{
		ATTR_S,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_ARST,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_sandbox"  */

	{
		ATTR_sandbox,
		decode_sandbox,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_jobdir"  */

	{
		ATTR_jobdir,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_stagein "  */

	{
		ATTR_stagein,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_ARST,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_stageout"  */

	{
		ATTR_stageout,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_ARST,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_substate"  */

	{
		ATTR_substate,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_USRD | ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_userlst"  */

	{
		ATTR_u,
		decode_arst,
		encode_arst,
		#ifndef PBS_MOM
			set_uacl,
		#else
			set_arst,
		#endif
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_SCGALT,
		ATR_TYPE_ARST,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_variables"  */

	{
		ATTR_v,
		decode_arst_bs,
		encode_arst_bs,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_ARST,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_euser"  */

	{
		ATTR_euser,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_MGRD | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_egroup"  */

	{
		ATTR_egroup,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_MGRD | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_hashname"  */

	{
		ATTR_hashname,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_MGRD | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_hopcount"  */

	{
		ATTR_hopcount,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_queuerank"  */

	{
		ATTR_qrank,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_MGRD,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_queuetype"  */

	{
		ATTR_qtype,
		decode_c,
		encode_c,
		set_c,
		comp_c,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_MGRD | ATR_DFLAG_SELEQ,
		ATR_TYPE_CHAR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_sched_hint"  */

	{
		ATTR_sched_hint,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_MGRD | ATR_DFLAG_MGWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_security"  */

	{
		ATTR_security,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_SSET,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_Comment"  */

	{
		ATTR_comment,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		NO_USER_SET | ATR_DFLAG_SvWR | ATR_DFLAG_ALTRUN | ATR_DFLAG_NOSAVM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_Cookie"  */

	{
		ATTR_cookie,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_SvRD | ATR_DFLAG_SvWR | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_altid"  */

	{
		ATTR_altid,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_altid2"  */

	{
		ATTR_altid2,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_etime"  */

	{
		ATTR_etime,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_reserve_start"  */

	{
		ATTR_resv_start,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvWR | ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_reserve_end"  */

	{
		ATTR_resv_end,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvWR | ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_reserve_duration"  */

	{
		ATTR_resv_duration,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvWR | ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_reserve_state"  */

	{
		ATTR_resv_state,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_reserve_Tag"  */

	{
		ATTR_resvTag,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_reserve_ID"  */

	{
		ATTR_resv_ID,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_Creat | ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_refresh "  */

	{
		ATTR_refresh,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvRD | ATR_DFLAG_SvWR | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_gridname "  */

	{
		ATTR_gridname,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_umask "  */

	{
		ATTR_umask,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_block"  */

	{
		ATTR_block,
		decode_l,
		encode_inter,
		set_l,
		comp_b,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | ATR_DFLAG_SELEQ,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* JOB_ATR_cred  */

	{
		ATTR_cred,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | ATR_DFLAG_SELEQ,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_runcount "  */

	{
		ATTR_runcount,
		decode_l,
		encode_l,
		set_l,
		comp_b,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_acct_id "  */

	{
		ATTR_acct_id,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_eligible_time"  */

	{
		ATTR_eligible_time,
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		#ifndef PBS_MOM
			alter_eligibletime,
		#else
			NULL_FUNC,
		#endif
		NO_USER_SET | ATR_DFLAG_SSET | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_accrue_type "  */

	{
		ATTR_accrue_type,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_none,
		NULL_FUNC,
		ATR_DFLAG_MGRD | ATR_DFLAG_ALTRUN | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_sample_starttime"  */

	{
		ATTR_sample_starttime,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_job_kill_delay"  */

	{
		ATTR_job_kill_delay,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_stageout_status"  */

	{
		ATTR_stageout_status,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_exit_status"  */

	{
		ATTR_exit_status,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* JOB_ATR_submit_arguments */

	{
		ATTR_submit_arguments,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_SvWR | READ_WRITE,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_executable"  */

	{
		ATTR_executable,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_SvWR | READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_Arglist"  */

	{
		ATTR_Arglist,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_SvWR | READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_prov_vnode"  */

	{
		ATTR_prov_vnode,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_SvRD | ATR_DFLAG_SvWR,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_array"  */

	{
		ATTR_array,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvWR | ATR_DFLAG_Creat | READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_BOOL,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_array_id"  */

	{
		ATTR_array_id,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_array_index"  */

	{
		ATTR_array_index,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_MOM | READ_ONLY,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_array_state_count"  */

	{
		ATTR_array_state_count,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_SvWR | READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_array_indices_submitted"  */

	{
		ATTR_array_indices_submitted,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		#ifndef PBS_MOM
			setup_arrayjob_attrs,
		#else
			NULL_FUNC,
		#endif
		ATR_DFLAG_SvWR | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_array_indices_remaining"  */

	{
		ATTR_array_indices_remaining,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		#ifndef PBS_MOM
			fixup_arrayindicies,
		#else
			NULL_FUNC,
		#endif
		ATR_DFLAG_SvWR | ATR_DFLAG_SvRD | READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_pset"  */

	{
		ATTR_pset,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_SvWR | ATR_DFLAG_MGWR | READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_estimated"  */

	{
		ATTR_estimated,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		action_resc_job,
		MGR_ONLY_SET | ATR_DFLAG_ALTRUN,
		ATR_TYPE_RESC,
		PARENT_TYPE_JOB
	},


      /* "JOB_ATR_node_set" */

	{
		ATTR_node_set,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		ATR_DFLAG_SvWR|ATR_DFLAG_MGWR,
		ATR_TYPE_ARST,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_history_timestamp"  */

	{
		ATTR_history_timestamp,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY|ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_project"  */

	{
		ATTR_project,
		decode_project,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM | ATR_DFLAG_SCGALT,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_X11_cookie"  */

	{
		ATTR_X11_cookie,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_USWR | ATR_DFLAG_MGRD | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_X11_port"  */

	{
		ATTR_X11_port,
		decode_l,
		encode_inter,
		set_l,
		comp_b,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "ATTR_sched_preempted"  */

	{
		ATTR_sched_preempted,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvWR | ATR_DFLAG_MGWR | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

      /* "JOB_ATR_run_version"  */

	{
		ATTR_run_version,
		decode_l,
		encode_l,
		set_l,
		comp_b,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_MGRD | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PARENT_TYPE_JOB
	},

     /* "JOB_ATR_GUI" */

	{
		ATTR_GUI,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_BOOL,
		PARENT_TYPE_JOB
	},

      /* "topjob_ineligible" */

	{
		ATTR_topjob_ineligible,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_MGRD | ATR_DFLAG_MGWR | ATR_DFLAG_ALTRUN,
		ATR_TYPE_BOOL,
		PARENT_TYPE_JOB
	},

       #include "site_job_attr_def.h"
      /* "JOB_ATR_UNKN - THIS MUST BE THE LAST ENTRY"  */

	{
		"_other_",
		decode_unkn,
		encode_unkn,
		set_unkn,
		comp_unkn,
		free_unkn,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ,
		ATR_TYPE_LIST,
		PARENT_TYPE_JOB
	},
};
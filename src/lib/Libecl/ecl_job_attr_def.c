/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

      #include <pbs_config.h> 
      #include <sys/types.h>
      #include "pbs_ifl.h"
      #include "pbs_ecl.h"
      ecl_attribute_def ecl_job_attr_def[] = {

      /* JOB_ATR_jobname */

	{
		ATTR_N,
		READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_jobname	
	},
      /* "Job_Owner" */

	{
		ATTR_owner,
		READ_ONLY | ATR_DFLAG_SSET | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_resc_used" */

	{
		ATTR_used,
		READ_ONLY | ATR_DFLAG_SvWR | ATR_DFLAG_NOSAVM,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_state" */

	{
		ATTR_state,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_CHAR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_state	
	},
      /* "JOB_ATR_in_queue" */

	{
		ATTR_queue,
		READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_at_server" */

	{
		ATTR_server,
		READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_account" */

	{
		ATTR_A,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM | ATR_DFLAG_SCGALT,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_chkpnt" */

	{
		ATTR_c,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_ALTRUN,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_checkpoint	
	},
      /* "JOB_ATR_ctime" */

	{
		ATTR_ctime,
		READ_ONLY | ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_depend" */

	{
		ATTR_depend,
		READ_WRITE,
		ATR_TYPE_LIST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_dependlist	
	},
      /* "JOB_ATR_errpath" */

	{
		ATTR_e,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_path	
	},
      /* "JOB_ATR_exec_host" */

	{
		ATTR_exechost,
		READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_exec_host2" */

	{
		ATTR_exechost2,
		ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_exec_vnode" */

	{
		ATTR_execvnode,
		READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_exectime" */

	{
		ATTR_a,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_grouplst" */

	{
		ATTR_g,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM | ATR_DFLAG_SCGALT,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_user_list	
	},
      /* "JOB_ATR_hold" */

	{
		ATTR_h,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_hold	
	},
      /* "JOB_ATR_interactive" */

	{
		ATTR_inter,
		READ_ONLY | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_join" */

	{
		ATTR_j,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_joinpath	
	},
      /* "JOB_ATR_keep" */

	{
		ATTR_k,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_keepfiles	
	},
      /* "JOB_ATR_mailpnts" */

	{
		ATTR_m,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_mailpoints	
	},
      /* "JOB_ATR_mailuser" */

	{
		ATTR_M,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_mailusers	
	},
      /* JOB_ATR_mtime */

	{
		ATTR_mtime,
		READ_ONLY | ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_nodemux" */

	{
		ATTR_nodemux,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_SELEQ,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_outpath" */

	{
		ATTR_o,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_path	
	},
      /* "JOB_ATR_priority" */

	{
		ATTR_p,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_priority	
	},
      /* "JOB_ATR_qtime"  (time entered queue) */

	{
		ATTR_qtime,
		READ_ONLY,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_rerunable" */

	{
		ATTR_r,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_resource" */

	{
		ATTR_l,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_MOM | ATR_DFLAG_SCGALT,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
      /* "JOB_ATR_SchedSelect" */

	{
		ATTR_SchedSelect,
		ATR_DFLAG_MGRD | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_stime"  (time started execution)  */

	{
		ATTR_stime,
		READ_ONLY,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_session_id"  */

	{
		ATTR_session,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_shell"  */

	{
		ATTR_S,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_shellpathlist	
	},
      /* "JOB_ATR_sandbox"  */

	{
		ATTR_sandbox,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_sandbox	
	},
      /* "JOB_ATR_jobdir"  */

	{
		ATTR_jobdir,
		ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_stagein "  */

	{
		ATTR_stagein,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_stagelist	
	},
      /* "JOB_ATR_stageout"  */

	{
		ATTR_stageout,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_stagelist	
	},
      /* "JOB_ATR_substate"  */

	{
		ATTR_substate,
		ATR_DFLAG_USRD | ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_userlst"  */

	{
		ATTR_u,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_SCGALT,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_user_list	
	},
      /* "JOB_ATR_variables"  */

	{
		ATTR_v,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_euser"  */

	{
		ATTR_euser,
		ATR_DFLAG_MGRD | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_egroup"  */

	{
		ATTR_egroup,
		ATR_DFLAG_MGRD | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_hashname"  */

	{
		ATTR_hashname,
		ATR_DFLAG_MGRD | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_hopcount"  */

	{
		ATTR_hopcount,
		ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_queuerank"  */

	{
		ATTR_qrank,
		ATR_DFLAG_MGRD,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_queuetype"  */

	{
		ATTR_qtype,
		ATR_DFLAG_MGRD | ATR_DFLAG_SELEQ,
		ATR_TYPE_CHAR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_sched_hint"  */

	{
		ATTR_sched_hint,
		ATR_DFLAG_MGRD | ATR_DFLAG_MGWR,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_security"  */

	{
		ATTR_security,
		ATR_DFLAG_SSET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_Comment"  */

	{
		ATTR_comment,
		NO_USER_SET | ATR_DFLAG_SvWR | ATR_DFLAG_ALTRUN | ATR_DFLAG_NOSAVM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_Cookie"  */

	{
		ATTR_cookie,
		ATR_DFLAG_SvRD | ATR_DFLAG_SvWR | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_altid"  */

	{
		ATTR_altid,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_altid2"  */

	{
		ATTR_altid2,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_etime"  */

	{
		ATTR_etime,
		READ_ONLY | ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_reserve_start"  */

	{
		ATTR_resv_start,
		ATR_DFLAG_SvWR | ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_reserve_end"  */

	{
		ATTR_resv_end,
		ATR_DFLAG_SvWR | ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_reserve_duration"  */

	{
		ATTR_resv_duration,
		ATR_DFLAG_SvWR | ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_reserve_state"  */

	{
		ATTR_resv_state,
		ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_reserve_Tag"  */

	{
		ATTR_resvTag,
		ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_reserve_ID"  */

	{
		ATTR_resv_ID,
		ATR_DFLAG_Creat | ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_refresh "  */

	{
		ATTR_refresh,
		ATR_DFLAG_SvRD | ATR_DFLAG_SvWR | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_gridname "  */

	{
		ATTR_gridname,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_umask "  */

	{
		ATTR_umask,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_block"  */

	{
		ATTR_block,
		READ_ONLY | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | ATR_DFLAG_SELEQ,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* JOB_ATR_cred  */

	{
		ATTR_cred,
		READ_ONLY | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | ATR_DFLAG_SELEQ,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_runcount "  */

	{
		ATTR_runcount,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},
      /* "JOB_ATR_acct_id "  */

	{
		ATTR_acct_id,
		ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_eligible_time"  */

	{
		ATTR_eligible_time,
		NO_USER_SET | ATR_DFLAG_SSET | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_time,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_accrue_type "  */

	{
		ATTR_accrue_type,
		ATR_DFLAG_MGRD | ATR_DFLAG_ALTRUN | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_sample_starttime"  */

	{
		ATTR_sample_starttime,
		ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_job_kill_delay"  */

	{
		ATTR_job_kill_delay,
		ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_stageout_status"  */

	{
		ATTR_stageout_status,
		ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_exit_status"  */

	{
		ATTR_exit_status,
		ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* JOB_ATR_submit_arguments */

	{
		ATTR_submit_arguments,
		ATR_DFLAG_SvWR | READ_WRITE,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_executable"  */

	{
		ATTR_executable,
		ATR_DFLAG_SvWR | READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_Arglist"  */

	{
		ATTR_Arglist,
		ATR_DFLAG_SvWR | READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_prov_vnode"  */

	{
		ATTR_prov_vnode,
		ATR_DFLAG_SvRD | ATR_DFLAG_SvWR,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_array"  */

	{
		ATTR_array,
		ATR_DFLAG_SvWR | ATR_DFLAG_Creat | READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_array_id"  */

	{
		ATTR_array_id,
		READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_array_index"  */

	{
		ATTR_array_index,
		ATR_DFLAG_MOM | READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_array_state_count"  */

	{
		ATTR_array_state_count,
		ATR_DFLAG_SvWR | READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_array_indices_submitted"  */

	{
		ATTR_array_indices_submitted,
		ATR_DFLAG_SvWR | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_jrange	
	},
      /* "JOB_ATR_array_indices_remaining"  */

	{
		ATTR_array_indices_remaining,
		ATR_DFLAG_SvWR | ATR_DFLAG_SvRD | READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_pset"  */

	{
		ATTR_pset,
		ATR_DFLAG_SvWR | ATR_DFLAG_MGWR | READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_estimated"  */

	{
		ATTR_estimated,
		MGR_ONLY_SET | ATR_DFLAG_ALTRUN,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
      /* "ATTR_q" */

	{
		ATTR_q,
		ATR_DFLAG_SvWR|ATR_DFLAG_MGWR,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_node_set" */

	{
		ATTR_node_set,
		ATR_DFLAG_SvWR|ATR_DFLAG_MGWR,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_history_timestamp"  */

	{
		ATTR_history_timestamp,
		READ_ONLY|ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_project"  */

	{
		ATTR_project,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM | ATR_DFLAG_SCGALT,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_X11_cookie"  */

	{
		ATTR_X11_cookie,
		ATR_DFLAG_USWR | ATR_DFLAG_MGRD | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "JOB_ATR_X11_port"  */

	{
		ATTR_X11_port,
		READ_ONLY | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "ATTR_sched_preempted"  */

	{
		ATTR_sched_preempted,
		ATR_DFLAG_SvWR | ATR_DFLAG_MGWR | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},
      /* "JOB_ATR_run_version"  */

	{
		ATTR_run_version,
		ATR_DFLAG_MGRD | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
     /* "JOB_ATR_GUI" */

	{
		ATTR_GUI,
		READ_ONLY | ATR_DFLAG_SvRD | ATR_DFLAG_Creat | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
      /* "topjob_ineligible" */

	{
		ATTR_topjob_ineligible,
		ATR_DFLAG_MGRD | ATR_DFLAG_MGWR | ATR_DFLAG_ALTRUN,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
};
		int   ecl_job_attr_size = sizeof(ecl_job_attr_def) / sizeof(ecl_attribute_def);
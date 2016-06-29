/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

     #include <pbs_config.h>   
     #include <fcntl.h>
     #include <sys/types.h>
     #include "pbs_ifl.h"
     #include "list_link.h"
     #include "attribute.h"
     #include "server_limits.h"
     #include "job.h"
     #include "reservation.h"


     attribute_def resv_attr_def[] = {


   /*RESV_ATR_resv_name*/

	{
		ATTR_resv_name,
		decode_jobname,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_RESV
	},

   /*RESV_ATR_resv_owner*/

	{
		ATTR_resv_owner,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SSET | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_RESV
	},

   /*RESV_ATR_resv_type*/

	{
		ATTR_resv_type,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_MGRD | ATR_DFLAG_SELEQ,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /*RESV_ATR_state*/	

	{
		ATTR_resv_state,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_RDACC | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /*RESV_ATR_substate*/	

	{
		ATTR_resv_substate,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_RDACC | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /*RESV_ATR_reserve_Tag*/

	{
		ATTR_resv_Tag,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /*RESV_ATR_reserveID*/

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
		PARENT_TYPE_RESV
	},

   /*RESV_ATR_start*/

	{
		ATTR_resv_start,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /*RESV_ATR_end*/

	{
		ATTR_resv_end,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /*RESV_ATR_duration*/

	{
		ATTR_resv_duration,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /*RESV_ATR_queue*/

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
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_resource */	

	{
		ATTR_l,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		action_resc_resv,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_MOM,
		ATR_TYPE_RESC,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_SchedSelect */

	{
		ATTR_SchedSelect,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_MGRD,
		ATR_TYPE_STR,
		PARENT_TYPE_JOB
	},

   /* RESV_ATR_resc_used */

	{
		ATTR_used,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_RESC,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_resv_nodes */

	{
		ATTR_resv_nodes,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_STR,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_userlst */

	{
		ATTR_u,
		decode_arst,
		encode_arst,
		set_uacl,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_grouplst */

	{
		ATTR_g,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_auth_u */

	{
		ATTR_auth_u,
		decode_arst,
		encode_arst,
		set_uacl,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_auth_g */

	{
		ATTR_auth_g,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_auth_h */	

	{
		ATTR_auth_h,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_at_server */

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
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_account */

	{
		ATTR_A,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_ctime */

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
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_mailpnts */

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
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_mailuser */

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
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_mtime */

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
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_hashname */

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
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_hopcount */

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
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_priority */

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
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_interactive */

	{
		ATTR_inter,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_variables */	

	{
		ATTR_v,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_ARST,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_euser */

	{
		ATTR_euser,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_MGRD,
		ATR_TYPE_STR,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_egroup */

	{
		ATTR_egroup,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_MGRD,
		ATR_TYPE_STR,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_convert  */ 

	{
		ATTR_convert,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE,
		ATR_TYPE_STR,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_resv_standing */ 

	{
		ATTR_resv_standing,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_resv_rrule */ 

	{
		ATTR_resv_rrule,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE,
		ATR_TYPE_STR,
		PARENT_TYPE_RESV
	},

   /*RESV_ATR_resv_idx*/

	{
		ATTR_resv_idx,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_resv_count */ 

	{
		ATTR_resv_count,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_resv_execvnodes */

	{
		ATTR_resv_execvnodes,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE,
		ATR_TYPE_STR,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_resv_timezone */

	{
		ATTR_resv_timezone,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE,
		ATR_TYPE_STR,
		PARENT_TYPE_RESV
	},

   /* RESV_ATR_retry */

	{
		ATTR_resv_retry,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE,
		ATR_TYPE_LONG,
		PARENT_TYPE_RESV
	},

   /*"node_set" */

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

    #include "site_resv_attr_def.h"
   /* RESV_ATR_UNKN - THIS MUST BE THE LAST ENTRY */

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
		PARENT_TYPE_RESV
	},

	};

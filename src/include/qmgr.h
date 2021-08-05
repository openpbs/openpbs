/*
 * Copyright (C) 1994-2021 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of both the OpenPBS software ("OpenPBS")
 * and the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * OpenPBS is free software. You can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the
 * Free Software Foundation, either version 3 of the License, or (at your
 * option) any later version.
 *
 * OpenPBS is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * PBS Pro is commercially licensed software that shares a common core with
 * the OpenPBS software.  For a copy of the commercial license terms and
 * conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
 * Altair Legal Department.
 *
 * Altair's dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of OpenPBS and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair's trademarks, including but not limited to "PBS™",
 * "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
 * subject to Altair's trademark licensing policies.
 */



/* $I$ */


/* symbolic constants */
#define ALL_SERVERS -1  /* all servers for connect_servers() */
/* server name used for the default PBS server ("") */
#define DEFAULT_SERVER "default"
/* server name used for all the active servers */
#define ACTIVE_SERVER "active"
/* max word length in the reqest */
#define MAX_REQ_WORD_LEN 10240

/* there can be three words before the attribute list
 * command object name <attribute list> */
#define MAX_REQ_WORDS 3
#define IND_CMD         0
#define IND_OBJ         1
#define IND_NAME        2
#define IND_FIRST       IND_CMD
#define IND_LAST        IND_NAME

/* Macros */

/* This macro will determine if the char it is passed is a qmgr operator. */
#define Oper(x)         ( ( *(x) == '=') || \
                          ( *(x) == '+' && *( (x) + 1 ) == '=' ) || \
                          ( *(x) == '-' && *( (x) + 1 ) == '=' ) \
                        )

/* This macro will determine if the char it is passed is white space. */
#define White(x)        (isspace((int)(x)))

/* This macro will determine if the char is the end of a line. */
#define EOL(x)          ((unsigned long)(x) == (unsigned long)'\0')

/* This macro will allocate memory for a character string */
#define Mstring(x,y)    if ( (x=(char *)malloc(y)) == NULL ) { \
                            pstderr("qmgr: Out of memory\n"); \
                            clean_up_and_exit(5); \
                        }
/* This macro will duplicate string */
#define Mstrdup(x,y)    if ( (x=strdup(y)) == NULL ) { \
                            pstderr("qmgr: Out of memory\n"); \
                            clean_up_and_exit(5); \
                        }
/* This macro will allocate memory for some fixed size object */
#define Mstruct(x,y)    if ( (x=(y *)malloc(sizeof(y))) == NULL ) { \
                            pstderr("qmgr: Out of memory\n"); \
                            clean_up_and_exit(5); \
                        }
/* server name: "" is the default server and NULL is all active servers */
#define Svrname(x)      ( ( (x) == NULL ) ? ACTIVE_SERVER : \
                        ( ( strlen((x) -> s_name) ) ? \
                        (x) -> s_name : DEFAULT_SERVER) )
/*
 *
 *	PSTDERR1 - print error message to stdard error with one argument.
 *		   Message will not be printed if "-z" option was specifed
 *
 *	  string - format string to fprintf
 *	  arg    - argument to be printed
 *
 */
#define PSTDERR1(fmt, parm) if (!zopt) fprintf(stderr, fmt, parm);
/* print an input line and then a caret under where the error has occured */
#define CaretErr(x, y)  PSTDERR1("%s\n", (x)); blanks((y)); pstderr("^\n");
#define CLEAN_UP_REQ(x)  { \
                             int i;\
                             for(i=0;i<MAX_REQ_WORDS;i++) { \
                                     free(x[i]); \
                             } \
                             free(x); \
                         }

#define QMGR_HIST_SIZE 500   /* size of the qmgr history area */

/* structures */

/* this struct is for the open servers */
struct server {
	char *s_name;               /* name of server */
	int s_connect;              /* PBS connection descriptor to server */
	int ref;                    /* number of references to server */
	struct batch_status *s_rsc;	/* ptr to status of resources on server */
	struct server *next;        /* next server in list */
};

/* objname - name of an object with a possible server associated with it
 * i.e. batch@server1   -> queue batch at server server1
 */
struct objname
{
	int obj_type;                 /* type of object */
	char *obj_name;               /* name of object */
	char *svr_name;               /* name of server associated with object */
	struct server *svr;           /* short cut to server associated with object */
	struct objname *next;         /* next object in list */
};



/* prototypes */
struct objname *commalist2objname(char *, int);
struct server *find_server(char *);
struct server *make_connection();
struct server *new_server();
struct objname *new_objname();
struct objname *strings2objname(char **, int, int);
struct objname *default_server_name();
struct objname *temp_objname(char *, char *, struct server *);
int parse_request(char *, char ***);
void clean_up_and_exit(int);
void freeattropl(struct attropl *);
void pstderr(const char *);
void pstderr_big(char *, char *, char *);
void free_objname_list(struct objname *);
void free_server(struct server *);
void free_objname(struct objname *);
void close_non_ref_servers();
int connect_servers(struct objname *, int);
int set_active(int, struct objname *);
int get_request(char **);
int parse(char *, int *, int *, char **, struct attropl **);
int execute(int, int, int, char *, struct attropl *);
int is_valid_object(struct objname *, int);


/* help messages */

#define HELP_DEFAULT \
"General syntax: command [object][@server] [name attribute[.resource] OP value]\n" \
"To get help on any topic or subtopic, type help <topic>\n" \
"Help is available on all commands and topics.\n" \
"Available commands: \n" \
"active                 The active command will set the active objects.\n" \
"create                 The create command will create the specified object on the PBS server(s).\n" \
"delete                 The delete command will delete the specified object from the PBS server(s).\n" \
"set                    The set command sets the value for an attribute on the specified object.\n" \
"unset                  The unset command will unset an attribute on the specified object.\n" \
"list                   The list command will list out all the attributes for the specified object.\n" \
"print                  The print command's output can be fed back into qmgr as input.\n" \
"import                 This takes hook script contents.\n" \
"export                 Dumps output of hook script into.\n" \
"quit                   The quit command will exit from qmgr.\n" \
"history                The history command will show qmgr command history.\n" \
"Other topics: \n" \
"attributes             type help or ? <attributes>.\n" \
"operators              type help or ? <operators>.\n" \
"names                  type help or ? <names>.\n" \
"values                 type help or ? <values>.\n" \

#define HELP_ACTIVE \
"Syntax active object [name [,name...]]\n" \
"Objects can be \"server\" \"queue\" \"resource\" or \"node\"\n" \
"The active command will set the active objects.  The active objects are used\n" \
"when no name is specified for different commands.\n" \
"If no server is specified for nodes or queues, the command will be sent\n" \
"to all active servers.\n" \
"Examples:\n" \
"active queue q1,batch@server1\n" \
"active server server2,server3\n" \
"Now if the following command is typed:\n" \
"set queue max_running = 10\n" \
"The attribute max_running will be set to ten on the batch queue on server1\n" \
"and the q1 queue on server2 and server3.\n\n" \
"active server s1, s2\n" \
"active node @active\n" \
"This would specify all nodes at all servers.\n\n" \
"active queue @s2\n" \
"This would specify all queues at server s2\n"

#define HELP_CREATE \
"Syntax: create object name[,name...] \n" \
"Objects can be \"queue\", \"node\", \"resource\" or \"hook\"\n" \
"The create command will create the specified object on the PBS server(s).\n" \
"For multiple names, use a comma seperated list with no intervening whitespace.\n" \
"A hook object can only be created by the Administrator, and only on the \n" \
"host on which the server runs.\n" \
"\nExamples:\n" \
"create queue q1,q2,q3\n" \
"create resource r1,r2,r3 type=long,flag=nh\n"

#define HELP_DELETE \
"Syntax: delete object name[,name...]\n" \
"Objects can be \"queue\", \"node\", \"resource\" or \"hook\"\n" \
"The delete command will delete the specified object from the PBS server(s).\n"\
"A hook object can only be deleted by the Administrator, and only on the \n" \
"host on which the server runs.\n"\
"\nExamples:\n" \
"delete queue q1\n"

#define HELP_SET \
"Syntax: set object [name,][,name...] attribute[.resource] OP value\n" \
"Objects can be \"server\", \"queue\", \"node\", \"hook\", \"resource\" or \"pbshook\"\n" \
"The \"set\" command sets the value for an attribute on the specified object.\n" \
"If the object is \"server\" and name is not specified, the attribute will be\n" \
"set on all the servers specified on the command line.\n" \
"For multiple names, use a comma seperated list with no intervening whitespace.\n" \
"A hook object can only be set by the Administrator, and only on the \n" \
"host on which the server runs.\n"\
"Examples:\n" \
"set server s1 max_running = 5\n" \
"set server managers = root@host.domain.com\n" \
"set server managers += susan@*.domain.com\n" \
"set node n1,n2 state=offline\n" \
"set queue q1@s3 resources_max.mem += 5mb\n" \
"set queue @s3 default_queue = batch\n"\
"set server default_qdel_arguments = \"-Wsuppress_email = 1000\"\n"\
"set server default_qsub_arguments = \"-m n -r n\"\n"\
"set resource r1 type=long\n"

#define HELP_UNSET \
"Syntax: unset object [name][,name...]\n" \
"Objects can be \"server\", \"queue\", \"node\", \"hook\", \"resource\" or \"pbshook\"\n" \
"The unset command will unset an attribute on the specified object except resource type.\n" \
"If the object is \"server\" and name is not specified, the attribute will be\n" \
"unset on all the servers specified on the command line.\n" \
"For multiple names, use a comma seperated list with no intervening whitespace.\n" \
"A hook object can only be unset by the Administrator, and only on the \n" \
"host on which the server runs.\n"\
"Examples:\n" \
"unset server s1 max_running\n" \
"unset server managers\n" \
"unset queue enabled\n" \
"unset resource r1 flag\n"

#define HELP_LIST \
"Syntax: list object [name][,name...]\n" \
"Object can be \"server\", \"queue\", \"node\", \"resource\", \"hook\", or \"pbshook\"\n" \
"The list command will list out all the attributes for the specified object.\n" \
"If the object is \"server\" and name is not specified, all the servers\n" \
"specified on the command line will be listed.\n" \
"For multiple names, use a comma seperated list with no intervening whitespace.\n" \
"Hooks can only be listed by the Administrator, and only on the \n" \
"host on which the server runs.\n"\
"Examples:\n" \
"list server\n" \
"list queue q1\n" \
"list node n1,n2,n3\n"

#define HELP_PRINT \
"Syntax: print object [name][,...]\n" \
"Object can be \"server\", \"queue\", \"node\", \"resource\" or \"hook\"\n" \
"The print command's output can be fed back into qmgr as input.\n" \
"If the object is \"server\", all the queues and nodes associated \n" \
"with the server are printed as well as the server information.\n" \
"For multiple names, use a comma seperated list with no intervening whitespace.\n" \
"Hooks can only be printed via \"print hook [name][,...]\" \n"\
"and by the Administrator, and only on the host on which the server runs.\n"\
"Examples:\n" \
"print server\n" \
"print node n1\n" \
"print queue q3\n" \

#define HELP_IMPORT \
"Syntax: import hook hook_name content-type content-encoding {input_file|-}\n" \
"This takes hook script contents from \"input_file\" or STDIN (-)\n" \
"\"content-type\" is currently \"application/x-python\" only. \n" \
"\"content-encoding\" is currently \"default\" (7bit/ASCII), or \"base64\".\n" \
"Hooks can only be imported by the Administrator, and only on the \n" \
"host on which the server runs.\n"

#define HELP_EXPORT \
"Syntax: export hook hook_name content-type content-encoding [output_file]\n"\
"Dumps output of hook script into \"output_file\" if specified, or to STDOUT.\n" \
"\"content-type\" is currently \"application/x-python\" only.\n" \
"\"content-encoding\" is currently \"default\" (7bit/ASCII), or \"base64\".\n" \
"Hooks can only be exported by the Administrator, and only on the \n" \
"host on which the server runs.\n"

/* HELP_QUIT macro name changed to HELP_QUIT0 here, as it clashes with one */
/* defined under Windows' winuser.h */
#define HELP_QUIT0 \
"Syntax: quit\n" \
"The quit command will exit from qmgr.\n"

#define HELP_EXIT \
"Syntax: exit\n" \
"The exit command will exit from qmgr.\n"

#define HELP_OPERATOR \
"Syntax: ... attribute OP new value\n" \
"Qmgr accepts three different operators for its commands.\n" \
"\t=\tAssign value into attribute.\n" \
"\t+=\tAdd new value and old value together and assign into attribute.\n" \
"\t-=\tSubtract new value from old value and assign into attribute.\n" \
"These operators are used in the \"set\" and the \"unset\" commands\n"

#define HELP_VALUE \
"Syntax ... OP value[multiplier]\n" \
"A multipler can be added to the end of a size in bytes or words.\n" \
"The multipliers are: tb, gb, mb, kb, b, tw, gw, mw, kw, w.  The second letter\n" \
"stands for bytes or words.  b is the default multiplier.\n" \
"The multipliers are case insensitive i.e. gw is the same as GW.\n" \
"Examples:\n" \
"100mb\n" \
"2gw\n" \
"10\n"

#define HELP_NAME \
"Syntax: [name][@server]\n" \
"Names can be in several parts.  There can be the name of an object, \n" \
"the name of an object at a server, or just at a server.\n" \
"The name of an object specifys a name.  A name of an object at a server\n" \
"specifys the name of an object at a specific server.  Lastly, at a server\n" \
"specifys all objects of a type at a server\n" \
"Examples:\n" \
"batch     - An object called batch\n" \
"batch@s1  - An object called batch at the server s1\n" \
"@s1       - All the objects of a cirtain type at the server s1\n"

#define HELP_ATTRIBUTE \
"The help for attributes are broken up into the following help subtopics:\n" \
"\tserverpublic\t- Public server attributes\n" \
"\tserverro\t- Read only server attributes\n" \
"\tqueuepublic\t- Public queue attributes\n" \
"\tqueueexec\t- Attributes specific to execution queues\n" \
"\tqueueroute\t- Attributes specified to routing queues\n" \
"\tqueuero \t- Read only queue attributes\n" \
"\tnodeattr\t- Node Attributes\n"

#define HELP_SERVERPUBLIC \
"Server Public Attributes:\n" \
"acl_host_enable - enables host level access control\n" \
"acl_user_enable - enables user level access control\n" \
"acl_users - list of users allowed/denied access to server\n" \
"comment - informational text string about the server\n" \
"default_queue - default queue used when a queue is not specified\n" \
"log_events - a bit string which specfiies what is logged\n" \
"mail_uid - uid of sender of mail which is sent by the server\n" \
"managers - list of users granted administrator privledges\n" \
"max_running - maximum number of jobs that can run on the server\n" \
"max_user_run - maximum number of jobs that a user can run on the server\n" \
"max_group_run - maximum number of jobs a UNIX group can run on the server\n" \
"max_queued - set of enqueued-count based limits to control futher job enqueueing\n" \
"max_queued_res - set of resource count based limits to control futher job enqueueing\n" \
"queued_jobs_threshold - set of resource count based limits to control futher job enqueueing\n" \
"queued_jobs_threshold_res - set of resource count based limits to control futher job enqueueing\n" \
"max_run - set of running-count based limits to control job scheduling\n" \
"max_run_soft - set of soft running-count based limits to control job scheduling\n" \
"max_run_res - set of resource based limits to control job scheduling\n" \
"max_run_soft_res - set of soft resource based limits to control job scheduling\n" \
"operators - list of users granted operator privledges\n" \
"query_other_jobs - when true users can query jobs owned by other users\n" \
"resources_available - ammount of resources which are available to the server\n" \
"resources_cost - the cost factors of resources.  Used for sync. job starting\n" \
"resources_default - the default resource value when the job does not specify\n" \
"resource_max - the maximum ammount of resources that are on the system\n" \
"scheduler_iteration - the amount of seconds between timed scheduler iterations\n" \
"scheduling - when true the server should tell the scheduler to run\n" \
"system_cost - arbitirary value factored into resource costs\n" \
"default_qdel_arguments - default arguments for qdel command\n" \
"default_qsub_arguments - default arguments for qsub command\n"

#define HELP_SERVERRO \
"Server Read Only Attributes:\n" \
"resources_assigned - total ammount of resources allocated to running jobs\n" \
"server_name - the name of the server and possibly a port number\n" \
"server_state - the current state of the server\n" \
"state_count - total number of jobs in each state\n" \
"total_jobs - total number of jobs managed by the server\n" \
"PBS_version - the release version of PBS\n" \

#define HELP_QUEUEPUBLIC \
"Queue Public Attributes:\n" \
"acl_group_enable - enables group level access control on the queue\n" \
"acl_groups - list of groups which have been allowed or denied access\n" \
"acl_host_enable - enables host level access control on the queue\n" \
"acl_hosts - list of hosts which have been allowed or denied access\n" \
"acl_user_enable - enables user level access control on the queue\n" \
"acl_users - list of users which have been allowed or denied access\n" \
"enabled - when true users can enqueue jobs\n" \
"from_route_only - when true queue only accepts jobs when routed by servers\n" \
"max_queuable - maximum number of jobs allowed to reside in the queue\n" \
"max_running - maximum number of jobs in the queue that can be routed or running\n" \
"max_queued - set of enqueued-count based limits to control futher job enqueueing\n" \
"max_queued_res - set of resource count based limits to control futher job enqueueing\n" \
"max_run - set of running-count based limits to control job scheduling\n" \
"max_run_soft - set of soft running-count based limits to control job scheduling\n" \
"max_run_res - set of resource based limits to control job scheduling\n" \
"max_run_soft_res - set of soft resource based limits to control job scheduling\n" \
"priority - the priority of the queue\n" \
"queue_type - type of queue: execution or routing\n" \
"resources_max - maximum ammount of a resource which can be requested by a job\n" \
"resources_min - minimum ammount of a resource which can be requested by a job\n" \
"resources_default - the default resource value when the job does not specify\n" \
"started - when true jobs can be scheduled for execution\n"

#define HELP_QUEUEEXEC \
"Attributes for Execution queues only:\n" \
"checkpoint_min - min. number of mins. of CPU time allowed bwtween checkpointing\n" \
"resources_available - ammount of resources which are available to the queue\n" \
"kill_delay - ammount of time between SIGTERM and SIGKILL when deleting a job\n" \
"max_user_run - maximum number of jobs a user can run in the queue\n" \
"max_group_run - maximum number of jobs a UNIX group can run in a queue\n"

#define HELP_QUEUEROUTE \
"Attributes for Routing queues only:\n" \
"route_destinations - list of destinations which jobs may be routed to\n" \
"alt_router - when true a alternate routing function is used to route jobs\n" \
"route_held_jobs - when true held jobs may be routed from this queue\n" \
"route_waiting_jobs - when true waiting jobs may be routed from this queue\n" \
"route_retry_time - time delay between route retries.\n" \
"route_lifetime - maximum ammount of time a job can be in this routing queue\n"

#define HELP_QUEUERO \
"Queue read only attributes:\n" \
"total_jobs - total number of jobs in queue\n" \
"state_count - total number of jobs in each state in the queue\n" \
"resources_assigned - ammount of resources allocated to jobs running in queue\n"

#define HELP_NODEATTR \
"Node attributes:\n" \
"state - the current state of a node\n" \
"properties - the properties the node has\n"

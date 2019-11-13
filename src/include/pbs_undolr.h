#ifdef PBS_UNDOLR_ENABLED
extern int sigusr1_flag;
extern void catch_sigusr1(int);
extern void undolr();
#endif

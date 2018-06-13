AC_DEFUN([PBS_AC_WITH_LIBZ],
[
  AC_ARG_WITH([libz],
    AS_HELP_STRING([--with-libz=DIR],
      [Specify the directory where libz is installed.]
    )
)
AS_IF([test "x$with_libz" != "x"],
    libz_dir=["$with_libz"],
    libz_dir=["/lib64"]
  )
  AC_MSG_CHECKING([for libz])
AS_IF([test "$libz_dir" = "/lib64"],
AS_IF([test -r "/lib64/libz.so" -o -r "/usr/lib64/libz.so" -o -r "/usr/lib/x86_64-linux-gnu/libz.so"],
    [libz_lib="-lz"],
      AC_MSG_ERROR([libz shared object library not found.])))

AC_MSG_RESULT([$libz_dir])
AC_SUBST(libz_lib)
AC_DEFINE([PBS_COMPRESSION_ENABLED], [], [Defined when libz is available])
])

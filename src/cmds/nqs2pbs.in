#!/bin/sh
#  Copyright (C) 1994-2017 Altair Engineering, Inc.
#  For more information, contact Altair at www.altair.com.
#   
#  This file is part of the PBS Professional ("PBS Pro") software.
#  
#  Open Source License Information:
#   
#  PBS Pro is free software. You can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License as published by the Free 
#  Software Foundation, either version 3 of the License, or (at your option) any 
#  later version.
#   
#  PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY 
#  WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
#  PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#   
#  You should have received a copy of the GNU Affero General Public License along 
#  with this program.  If not, see <http://www.gnu.org/licenses/>.
#   
#  Commercial License Information: 
#  
#  The PBS Pro software is licensed under the terms of the GNU Affero General 
#  Public License agreement ("AGPL"), except where a separate commercial license 
#  agreement for PBS Pro version 14 or later has been executed in writing with Altair.
#   
#  Altair’s dual-license business model allows companies, individuals, and 
#  organizations to create proprietary derivative works of PBS Pro and distribute 
#  them - whether embedded or bundled with other software - under a commercial 
#  license agreement.
#  
#  Use of Altair’s trademarks, including but not limited to "PBS™", 
#  "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
#  trademark licensing policies.
#

if [ $# -eq 1 ] && [ $1 = "--version" ]; then
   echo pbs_version = @PBS_VERSION@
   exit 0
fi

if [ \( $# -eq 0 \) -o \( $# -gt 2 \) ]
then
	echo Usage: $0 --version
	echo Usage: $0 NQSscript \[PBSscript\]
	exit 1
fi
if [ $# -eq 2 ]
then
	OUT=$2
else
	OUT=$1.new
fi
echo Converting NQS script \"$1\" into \"$OUT\"
nawk  '
#
# Rule 0 - Initialize a few variables
#

BEGIN {
	suffix = "  kKmMgGtT"
	err_ct  = 0
	cvn_ct  = 0
	warn_ct	= 0
	line_ct = 1
}

#
# Rule 1 - Make copy of line
#

{
	copy_of_line = $0
}

#
# Rule 2 - if line starts with either #QSUB or #@$ , convert it
#

($0 ~ /^[ \t]*#[ \t]*QSUB/) || ($0 ~ /^[ \t]*#[ \t]*\@\$/) {
    if (donedate == 0 ) {
	"date" | getline today_is
	print "# This script converted on " today_is
	donedate = 1
    }
    i = 1
    if ($1 ~ /#$/)  i = 2
    if (($i ~ /QSUB-/) || ($i ~ /\@\$-/)) {
	$i = substr($i, index($i, "-"))
    } else {
	++i;
    }
    printf ("#PBS ");
    for ( ; i <= NF; ++i ) {

	if ($i ~ /-a/ ) {			# -a date
		# treat multiple words from a quoted string as separate
		# words and process them as a date
		date["CC"] = ""
		date["YY"] = ""
		date["MM"] = ""
		date["DD"] = ""
		date["hh"] = "00"
		date["mm"] = "00"
		date["ss"] = ""
		should_be_date = 0
	
		if ($(++i) ~ /^["\047]/) 
			quote = 1
		else
			quote = 0
		do {
			start = 1
			if ($i ~ /^["\047]/ )	
				start = 2
			len  = length($i) + 1 - start
			if ($i ~ /["\047]$/ ) {
				--len
				quote = 0
			}
			word = substr($i, start, len)
			
			# process the date word here...
			crackdate(word)
	
		} while (quote && (++i <= NF))
		if (date["ss"] == "")
			printf("-a %s%s%s%s%s%s ",date["CC"],date["YY"],date["MM"],date["DD"],date["hh"],date["mm"] )
		else
			printf("-a %s%s%s%s%s%s.%s ", date["CC"],date["YY"],date["MM"],date["DD"],date["hh"],date["mm"],date["ss"])

	} else if ($i ~ /-A/ ) {		# -A account
		printf("-A %s ",$(++i))

	} else if ($i ~ /-C/ ) {		# -C compartment
		prt_warning(sprintf("NQS %s option not supported", $i))
		++i

	} else if ($i ~ /-e$/ ) {		# -e file
		printf("-e %s ",$(++i))

	} else if ($i ~ /-eo/ ) {		# -eo 
		printf("-j oe ")

	} else if ($i ~ /-j|J/ ) {		# -j
		prt_warning("NQS joblog options not supported")
		++i

	} else if ($i ~ /-ke/ ) {		# -ke
		if (have_ke == 0) {
			if (have_ko == 1)
				printf("-keo ")
			else
				printf("-ke ")
			have_ke = 1
		}

	} else if ($i ~ /-ko/ ) {		# -ke
		if (have_ko == 0) {
			if (have_ke == 1)
				printf("-keo ")
			else
				printf("-ko ")
			have_ko = 1
		}

	} else if ($i ~ /-kj/ ) {		# -kj
		prt_warning("NQS joblog options not supported")

	} else if ($i ~ /-l$/ ) {		# -l
		++i
		if ($i ~ /^"/ ) {
			word = cat_qstring()
		} else {
			word = $i
		}
		sub(/mpp_p/,   "mppe", word)
		sub(/p_mpp_t/, "pmppt", word)
		sub(/mpp_t/,   "mppt", word)
		printf("-l \"%s\"", word)

	} else if ($i ~ /-l[acdsw]/ ) {		# -la -lc -ld -ls -lw
		prt_warning(sprintf("NQS %s options not supported",$i))
		++i

	} else if ($i ~ /-lf/ ) {		# -lf limit
		printf("-l ppf=")
		cnv_limit($(++i))

	} else if ($i ~ /-lF/ ) {		# -lF limit
		printf("-l pf=")
		cnv_limit($(++i))

	} else if ($i ~ /-lm/ ) {		# -lm limit
		printf("-l pmem=")
		cnv_limit($(++i))

	} else if ($i ~ /-lM/ ) {		# -lM limit
		printf("-l mem=")
		cnv_limit($(++i))

	} else if ($i ~ /-ln/ ) {		# -ln nice
		printf("-l nice=%s ",$(++i))

	} else if ($i ~ /-lr/ ) {		# -lr srfs
		++i
		cnv_srfs()

	} else if ($i ~ /-lQ/ ) {		# -lQ sds
		printf("-l sds=")
		cnv_limit($(++i))

	} else if ($i ~ /-lt/ ) {		# -lt time
		printf("-l pcput=%s ",$(++i))

	} else if ($i ~ /-lT/ ) {		# -lT time
		printf("-l cput=%s ",$(++i))

	} else if ($i ~ /-lU[a-h]/ ) {		# -lUmttype
		printf("-l mt%s=%s ", substr($(i), 4, 1), $(++i))

	} else if ($i ~ /-L/ ) {		# -L level
		prt_warning(sprintf("NQS %s option not supported", $i))
		++i

	} else if ($i ~ /-mb/ ) {		# -mb
		if (have_mb == 0) {
			if (have_me == 0)
				printf("-mb ")
			else
				printf("-mbe ")
			have_mb = 1
		}

	} else if ($i ~ /-me/ ) {		# -mb
		if (have_me == 0) {
			if (have_mb == 0)
				printf("-me ")
			else
				printf("-mbe ")
			have_me = 1
		}

	} else if ($i ~ /-m[rt]/ ) {		# -mr -mt
		prt_warning(sprintf("NQS %s option not supported", $i))

	} else if ($i ~ /-mu/ ) {		#-mu user
		printf("-M %s ", $(++i))

	} else if ($i ~ /-nc/ ) {		# -nc
		printf("-cn ")

	} else if ($i ~ /-nr/ ) {		# -nr
		printf("-rn ")

	} else if ($i ~ /-o/ ) {		# -o file
		printf("-o %s ",$(++i))

	} else if ($i ~ /-p/ ) {		# -p priority
		prior = $(++i)
		if (prior > 1023)
			prior = 1023
		else if (prior < -1024)
			prior = -1024
		printf("-p %s ", prior)

	} else if ($i ~ /-q/ ) {		# -q queue
		printf("-q %s ",$(++i))

	} else if ($i ~ /-r$/ ) {		# -r name

		printf("-N %s ",$(++i))
	} else if ($i ~ /-r[eo]/ ) {		# -re -ro
		prt_warning(sprintf("NQS %s option not supported, you may wish to use -k%c", $i, substr($i, 3, 3)))

	} else if ($i ~ /-Rf/ ) {		# -Rf
		prt_warning("NQS -Rf option not supported")
		++i

	} else if ($i ~ /^-s$/ ) {		# -s shell
		printf("-S %s ",$(++i))

	} else if ($i ~ /-u/ ) {		# -u user
		printf("-u %s ",$(++i))

	} else if ($i ~ /-x/ ) {		# -x
		printf("-V ")

	} else if ($i ~ /-z/ ) {		# -z
		printf("-z ")

	} else if ($i ~ /^#/ ) {		# #comment
		break
	} else if ($i ~ /^-/ ) 	{		# -any_thing_else
		prt_warning(sprintf("Unknown NQS option \"%s\"\n\tabove option was not converted", $i))
	} else {
		prt_error("unknown option/parameter ", $i)
	}
    }
    printf("\n");
}

#
# Rule 3 - for every line, print it
#

{
	print copy_of_line
	++line_ct
}

#
# END Rule - print number of warnings and errors, if errors exit non-zero
#

END {
	if ( cvn_ct > 0 ) {
		printf("\nFractional size values, i.e. \"23.4mw\" are not supported in PBS.\n") > "/dev/tty"
		printf("In %d occurrence in this conversion, a fractonal size value was converted\nto the corresponding integeral value of the next small unit.\n", cvn_ct) > "/dev/tty"
		printf("For example, \"23.4mw\" converted to \"23962kw\"\n") > "/dev/tty"
	}
	printf("\nIn converting the script, %d errors and %d warnings occurred\n", err_ct, warn_ct) > "/dev/tty"
	exit err_ct
}

#
# function prt_warning - print a warning message and the script line causing it
#

function prt_warning(text) {
	print "\nWarning on line #" line_ct " of NQS script" > "/dev/tty"
	print "\t" text > "/dev/tty"
	print "\tinput line:  " substr($0, 1, 40) > "/dev/tty"
	++warn_ct
}

#
# function prt_error - print a error message and the script line causing it
#

function prt_error(text, word) {
	print "\nError on line #" line_ct " of NQS script" > "/dev/tty"
	print "\t" text " \""word "\"" > "/dev/tty"
	print "\tinput line:  " substr($0, 1, 40) > "/dev/tty"
	++err_ct
}

#
# function crackdate - convert NQS complex date/time to PBSs
#	[[[[YY]CC]MM]DD]hhmm[.ss]
#

function crackdate(word) {
	# noon
	if (word ~ /noon$/) {
		date["hh"] = "12"
		date["mm"] = "00"

	# midnight
	} else if (word ~ /midnight$/) {
		date["hh"] = "00"
		date["mm"] = "00"

	# day of week, today, tomorrow - all bad news
	} else if ( (word ~ /^[Mm][Oo][Nn][a-zA-Z]*[.,]*$/ ) ||
		    (word ~ /^[Tt][Uu][Ee][a-zA-Z]*[.,]*$/ ) ||
		    (word ~ /^[Ww][Ee][Dd][a-zA-Z]*[.,]*$/ ) ||
		    (word ~ /^[Tt][Hh][Uu][a-zA-Z]*[.,]*$/ ) ||
		    (word ~ /^[Ff][Rr][Ii][a-zA-Z]*[.,]*$/ ) ||
		    (word ~ /^[Ss][Aa][Tt][a-zA-Z]*[.,]*$/ ) ||
		    (word ~ /^[Ss][Uu][Nn][a-zA-Z]*[.,]*$/ ) ||
		    (word ~ /^today,*$/  ) ||
		    (word ~ /^Today,*$/  ) ||
		    (word ~ /^TODAY,*$/  ) ||
		    (word ~ /^tomorrow,*$/ ) ||
		    (word ~ /^Tomorrow,*$/ ) ||
		    (word ~ /^TOMORROW,*$/ ) ) {
		prt_warning(sprintf("PBS does not support a date form of \"%s\".\n\Recommend use of -a option on command line rather than in the script.", word))

	# Time Zone specifier
	} else if ( word ~ /^[ACEGMP][DMPS]T,?$/ ) {
		prt_warning("PBS does not support time zone in a date specification,\n\tdefaulting to local time.")

	# MM/DD
	} else if ( word ~ /^[01][0-9]\/[0-3][0-9]$/ ) {
		date["MM"] = substr(word, 1, 2)
		date["DD"] = substr(word, 4, 2)

	# MM/DD/YY
	}else if (word ~ /^[01][0-9]\/[0-3][0-9]\/[0-9][0-9]$/ ) {
		date["MM"] = substr(word, 1, 2)
		date["DD"] = substr(word, 4, 5)
		date["YY"] = substr(word, 7, 2)

	# MM/DD/YYYY
	} else if (word ~ /^[01][0-9]\/[0-3][0-9]\/[0-9][0-9][0-9][0-9]$/ ) {
		date["MM"] = substr(word, 1, 2)
		date["DD"] = substr(word, 4, 2)
		date["YY"] = substr(word, 9, 2)
		date["CC"] = substr(word, 7, 2)

	# YYYY
	}else if (word ~ /^[0-9][0-9][0-9][0-9]$/ ) {
		date["CC"] = substr(word, 1, 2)
		date["YY"] = substr(word, 3, 2)
		should_be_date = 1

	# YYYY-MM-DD
	} else if (word ~ /^[0-9][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]$/ ) {
		date["CC"] = substr(word, 1, 2)
		date["YY"] = substr(word, 3, 2)
		date["MM"] = substr(word, 6, 2)
		date["DD"] = substr(word, 9, 2)

	# month 
	} else if (word ~ /^[a-zA-Z][a-zA-Z][a-zA-Z]*$/ ) {
		get_month(word)
		should_be_date = 1

	# either DD or HH
	} else if (word ~ /^[0-3][0-9],?$/ ) {
		if (should_be_date == 1) {
			date["DD"] = substr(word, 1, 2)
			should_be_date = 0
		} else {
			date["hh"] = substr(word, 1, 2)
			date["mm"] = "00"
		}

	# either D or H
	} else if (word ~ /^[0-9],?$/) {
		if (should_be_date == 1) {
			date["DD"] = "0" substr(word, 1, 1)
			should_be_date = 0
		} else {
			date["hh"] = "0" substr(word, 1, 1)
			date["mm"] = "00"
		}

	# H[[a|p]m]
	} else if (word ~ /^[0-9][ap]?m?,?$/ ) {
		date["hh"] = "0" substr(word, 1, 1)
		adj_hour(word)

	# HH[[a|p]m]
	} else if (word ~ /^[0-2][0-9][ap]?m?,?$/ ) {
		date["hh"] = substr(word, 1, 2)
		adj_hour(word)

	# HHtimezone
	} else if (word ~ /^[0-2][0-9][ACEGMP][DMPS]T,?$/ ) {
		date["hh"] = substr(word, 1, 2)
		adj_hour(word)
		prt_warning("PBS does not support time zone in a date specification,\n\tdefaulting to local time.")

	# H:MM[[a|p]m]
	} else if (word ~ /^[0-9]:[0-5][0-9][ap]?m?$/ ) {
		date["hh"] = substr(word, 1, 1)
		date["mm"] = substr(word, 3, 2)
		adj_hour(word)

	# H:MMtimezone
	} else if (word ~ /^[0-9]:[0-5][0-9][ACEGMP][DMPS]T,?$/ ) {
		date["hh"] = substr(word, 1, 1)
		date["mm"] = substr(word, 3, 2)
		adj_hour(word)
		prt_warning("PBS does not support time zone in a date specification,\n\tdefaulting to local time.")


	# HH:MM[[a|p]m]
	} else if (word ~ /^[0-2][0-9]:[0-5][0-9][ap]?m?$/ ) {
		date["hh"] = substr(word, 1, 2)
		date["mm"] = substr(word, 4, 2)
		adj_hour(word)

	# HH:MMtimezone
	} else if (word ~ /^[0-2][0-9]:[0-5][0-9][ACEGMP][DMPS]T,?$/ ) {
		date["hh"] = substr(word, 1, 2)
		date["mm"] = substr(word, 4, 2)
		adj_hour(word)
		prt_warning("PBS does not support time zone in a date specification,\n\tdefaulting to local time.")

	# H:MM:SS[[a|p]m]
	} else if (word ~ /^[0-9]:[0-5][0-9]:[0-5][0-9][ap]?m?$/ ) {
		date["hh"] = substr(word, 1, 1)
		date["mm"] = substr(word, 3, 2)
		date["ss"] = substr(word, 6, 2)
		adj_hour(word)

	# H:MM:SStimezone
	} else if (word ~ /^[0-9]:[0-5][0-9]:[0-5][0-9][ACEGMP][DMPS]T,?$/ ) {
		date["hh"] = substr(word, 1, 1)
		date["mm"] = substr(word, 3, 2)
		date["ss"] = substr(word, 6, 2)
		adj_hour(word)
		prt_warning("PBS does not support time zone in a date specification,\n\tdefaulting to local time.")

	# HH:MM:SS[[a|p]m]
	} else if (word ~ /^[0-2][0-9]:[0-5][0-9]:[0-5][0-9][ap]?m?$/ ) {
		date["hh"] = substr(word, 1, 2)
		date["mm"] = substr(word, 4, 2)
		date["ss"] = substr(word, 7, 2)
		adj_hour(word)

	# HH:MM:SStimezone
	} else if (word ~ /^[0-2][0-9]:[0-5][0-9]:[0-5][0-9][ACEGMP][DMPS]T,?$/ ) {
		date["hh"] = substr(word, 1, 2)
		date["mm"] = substr(word, 4, 2)
		date["ss"] = substr(word, 7, 2)
		adj_hour(word)
		prt_warning("PBS does not support time zone in a date specification,\n\tdefaulting to local time.")

	# DD-month
	} else if (word ~ /^[0-3][0-9]-[a-zA-Z][a-zA-Z][a-zA-Z]*$/ ) {
		date["DD"] = substr(word, 1, 2)
		get_month(substr(word, 4))

	# DD-month-YY  DD-month-YYYY
	} else if (word ~ /^[0-3][0-9]-[a-zA-Z][a-zA-Z][a-zA-Z]*-[0-9][0-9]*$/) {
		date["DD"] = substr(word, 1, 2)
		get_month(substr(word, 4, 3))
		if (word ~ /.*-[0-9][0-9]$/ )	{	# -YY
			date["YY"] = substr(word, length(word)-1, 2)
		} else {				# -YYYY
			date["CC"] = substr(word, length(word)-3, 2)
			date["YY"] = substr(word, length(word)-1, 2)
		}
	} else {
		prt_error("unrecognized date syntax: ", word) > "/dev/tty"
	}
}

#
# function get_month - convert abbrev of a month to numerical index 01-12
#

function get_month(word) {
	if      (word ~ /[Jj][Aa][Nn].*/ ) date["MM"] = "01"
	else if (word ~ /[Ff][Ee][Bb].*/ ) date["MM"] = "02"
	else if (word ~ /[Mm][Aa][Rr].*/ ) date["MM"] = "03"
	else if (word ~ /[Aa][Pp][Rr].*/ ) date["MM"] = "04"
	else if (word ~ /[Mm][Aa][Yy]/ )   date["MM"] = "05"
	else if (word ~ /[Jj][Uu][Nn].*/ ) date["MM"] = "06"
	else if (word ~ /[Jj][Uu][Ll].*/ ) date["MM"] = "07"
	else if (word ~ /[Aa][Uu][Gg].*/ ) date["MM"] = "08"
	else if (word ~ /[Ss][Ee][Pp].*/ ) date["MM"] = "09"
	else if (word ~ /[Oo][Cc][Tt].*/ ) date["MM"] = "10"
	else if (word ~ /[Nn][Oo][Vv].*/ ) date["MM"] = "11"
	else if (word ~ /[Dd][Ee][Cc].*/ ) date["MM"] = "12"
	else {
		prt_error("Bad month specification ", word) > "/dev/tty"
	}
}

#
# function adj_hour - adjust 12 hour clock to 24 hour 
#

function adj_hour(word) {
	if (((word ~ /pm,?$/ ) || (word ~ /[0-9]m,?$/)) && (date["hh"] < 12)) {
		date["hh"] = substr(word, 1, 2) + 12;
	} else if (word ~ /am,?$/) {
 		if (date["hh"] == 12) {
			date["hh"] = "00"
		}
	}
}

#
# function cnv_srfs - convert NQS srfs request to PBS srfs request
#

function cnv_srfs() {
	if ($i ~ /^[\047"]/)
		val = cat_qstring()	# pull parameters into one string
	else
		val = $i
	nele = split(val, parts, ",")	# split into 2,3,or 4 parts
	if (nele < 2) {
		prt_error("incorrect SRFS syntax in ", $0)
		return
	}

	if (parts[1] ~ /\$FASTDIR/) {		# $FASTDIR
		dir = "srfs_fast"
	} else if (parts[1] ~ /\/fast/) {
		dir = "srfs_fast"
	} else if (parts[1] ~ /\$BIGDIR/) {	# $BIGDIR
		dir = "srfs_big"
	} else if (parts[1] ~ /\$TMPDIR/) {	# $TMPDIR
		dir = "srfs_tmp"
	} else if (parts[1] ~ /\$WRKDIR/) {	# $WRKDIR
		dir = "srfs_wrk"
	} else {
		prt_error("cannot convert this srfs request\n\t", $0)
		return
	}
	printf("-l %s=", dir)
	cnv_limit(parts[2])
	if (nele > 2) {
		prt_warning("GID/ACID not supported on SRFS request")
	}
}

#
# function cat_qstring - concat quoted words into a single string
#	"abc def ghi "	-> abcdefghi
#

function cat_qstring() {

	if ($i ~ /^[\047"]..*/) {	# start of quoted words
		tmp = $i
		while ( tmp !~ /[\047"]$/) tmp = tmp $(++i)
	} else if ($i ~ /^[\047"]$/ ) {
		tmp = $i $(++i)
		while ( tmp !~ /[\047"]$/) tmp = tmp $(++i)
	}
	tmp = substr(tmp, 2, length(tmp)-2)
	return tmp
}

#
# function cnv_limit - convert NQS limit value ###[.###][[kmg]wb] to 
#	PBSs ###[kmgt][wb]
#
#	if NQS has fraction, mutiple by 1024 and drop suffix to next lower
#	magnitude, e.g "4.5MW"  ->  "4608KW"
#

function cnv_limit(word) {
	len = length(word)

	# nnn
	if (word ~ /^[0-9][0-9]*$/) {
		val = word
		suf = ""
		byte= "b"

	# nnnMB
	} else if (word ~ /^[0-9][0-9]*[kKmMgGtT][wWbB]$/) {
		val  = substr(word, 1, len-2)
		suf  = substr(word, len-1, 1)
		byte = substr(word, len, 1)

	# nnnW
	} else if (word ~ /^[0-9][0-9]*[wWbB]$/) {
		val  = substr(word, 1, len-1)
		suf  = ""
		byte = substr(word, len, 1)
		
	# nnn.nnMW
	} else if (word ~ /^[0-9]*\.[0-9]*[kKmMgGtT][wWbB]$/) {
		++cvn_ct
		val = sprintf("%.0f", (substr(word, 1, len-2) * 1024)+1)
		ind = index(suffix, substr(word, length(word)-1, 1))
		suf = substr(suffix, ind-2, 1)
		if (suf == " ") suf = ""
		byte = substr(word, length(word), 1)

	} else {
		prt_error("unrecognized limit ", word)
	}
	printf("%s%s%s ", val, suf, byte)
} ' < $1 > $OUT
if [ $? -ne 0 ]
then
	echo Because of errors in converting the script,
	echo $OUT is being removed.
	rm $OUT
	exit 1
else
	echo Script conversion complete, new PBS script in $OUT
	exit 0
fi


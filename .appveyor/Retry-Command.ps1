# Copyright (C) 1994-2018 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# PBS Pro is free software. You can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# For a copy of the commercial license terms and conditions,
# go to: (http://www.pbspro.com/UserArea/agreement.html)
# or contact the Altair Legal Department.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

Function Retry-Command {
    [CmdletBinding()]
    Param
    (
        [Parameter(Mandatory = $true, Position = 1, ValueFromPipeline = $true)]
        [ScriptBlock]$Command,

        [Parameter(Mandatory = $false, Position = 2)]
        [ValidateRange(0, [UInt32]::MaxValue)]
        [UInt32]$Retry = 120,

        [Parameter(Mandatory = $false, Position = 3)]
        [ValidateRange(0, [UInt32]::MaxValue)]
        [UInt32]$Timeout = 1000

    )

    Begin {
        $StrCommand = $Command.ToString().Trim()
    }

    Process {
        $lasterr = $false
        for ($i = 1; $i -le $Retry; $i++) {
            Write-Host -ForegroundColor DarkCyan -NoNewLine ("{0} ... attempt = {1}" -f $StrCommand, $i)
            try {
                $cmdOutput = & $Command
                if ($LastExitCode -ne 0) {
                    if ($cmdOutput) {
                        throw $cmdOutput
                    } else {
                        throw "{0} exited with {1}" -f $StrCommand,$LastExitCode
                    }
                }
                Write-Host -ForegroundColor Green ' ... Ok'
                $cmdOutput
                $lasterr = $false
                Break
            } catch {
                Write-Host -ForegroundColor Red ' ... Failed'
                $lasterr = $_.Exception
                Start-Sleep -Milliseconds $Timeout
            }
        }
        if ($lasterr) {
            throw $lasterr
        }
    }
}

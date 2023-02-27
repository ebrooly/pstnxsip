@echo off
if not exist debug\ goto ERR
if not exist debug\pstnxsip.py goto ERR
if not exist debug\line.py goto ERR
if not exist debug\ip_phone.py goto ERR
if not exist debug\common.py goto ERR
if not exist live\ md live
find /V "debug(" <.\debug\pstnxsip.py >.\pstnxsip.py
echo .\debug\pstnxsip.py processed
find /V "debug(" <.\debug\line.py >.\line.py
echo .\debug\line.py processed
find /V "debug(" <.\debug\ip_phone.py >.\ip_phone.py
echo .\debug\ip_phone.py processed
copy .\debug\common.py .\common.py >NUL
echo .\debug\common.py copied
echo 'debug(' lines cleaned from files in './debug' folder (except common.py) then copied './' folder.
goto END

:ERR
echo Files with 'debug(' lines must be in the './debug' folder.

:END

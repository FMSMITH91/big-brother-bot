================================================================================
BigBrotherBot (B3) for Windows
The license of this software is in license.txt
Source, issues and releases: https://github.com/FMSMITH91/big-brother-bot
================================================================================

B3 is an in-game administration bot for game servers: commands, admin levels,
warnings, bans, statistics and more, through plugins.

This installer contains everything B3 needs: its own copy of Python (in the
"python" folder) with B3 and its libraries installed. You do not need to
install Python.

FIRST RUN
---------
1. Create your configuration with the setup wizard: Start menu > BigBrotherBot >
   B3 setup wizard (the installer offers to run it on its last page). It asks
   for your game, the game server address and RCON password, the game log file
   and the database, and writes %USERPROFILE%\.b3\b3.ini.
   Database: SQLite needs nothing installed; MySQL/MariaDB and PostgreSQL are
   supported too.
2. Start B3: Start menu > BigBrotherBot > Run B3. If B3 stops, the window stays
   open with the reason.
3. In game, type !iamgod in the chat to become super admin (works once, on a
   new database).

Every other setting (plugins, messages, time format...) is in b3.ini, with
comments: Start menu > BigBrotherBot > Edit B3 configuration.

FOLDERS
-------
  run-b3.cmd   starts B3 and keeps the window open when it stops (shortcuts)
  b3.cmd       starts B3 (b3.cmd --help lists the options), for scripts
  conf\        sample configuration files for B3 and every plugin: copy the
               ones you need next to your b3.ini before editing them
  extplugins\  put third party plugins here
  python\      the Python runtime used by B3 (do not edit)

B3 writes its log files and its SQLite database (if you use one) in
%USERPROFILE%\.b3 unless your b3.ini says otherwise.

UPGRADING
---------
Install the new version over the old one. Your b3.ini and everything else in
%USERPROFILE%\.b3 is kept (there is no need to run the setup wizard again).
================================================================================

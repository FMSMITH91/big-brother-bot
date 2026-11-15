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
1. Edit your configuration file:
      %USERPROFILE%\.b3\b3.ini
   (Start menu > BigBrotherBot > Edit B3 configuration). The installer created
   it from the sample conf\b3.distribution.ini if you did not have one yet.
   Set at least: the game parser, the game server address, RCON password and
   game log file, and the database. The comments in the file explain each
   setting.
2. Database: B3 stores players, admins, warnings and bans in a database.
   SQLite needs nothing installed (database: sqlite://C:/path/to/b3.db).
   MySQL/MariaDB and PostgreSQL are supported too.
3. Start B3: Start menu > BigBrotherBot > Run B3 (or run b3.cmd).
   Type !iamgod in the game chat to become super admin (works once, on a
   fresh database).

FOLDERS
-------
  b3.cmd       starts B3 (b3.cmd --help lists the options)
  conf\        sample configuration files for B3 and every plugin: copy the
               ones you need next to your b3.ini before editing them
  extplugins\  put third party plugins here
  python\      the Python runtime used by B3 (do not edit)

B3 writes its log files and its SQLite database (if you use one) in
%USERPROFILE%\.b3 unless your b3.ini says otherwise.

UPGRADING
---------
Install the new version over the old one. Your b3.ini and everything else in
%USERPROFILE%\.b3 is kept.
================================================================================

![BigBrotherBot](https://github.com/BigBrotherBot/ArtWork/blob/master/layered-png/logo.png)

**********

![status: seeking maintainer](https://img.shields.io/badge/status-seeking%20maintainer-yellow.svg)

```
This project is NO LONGER actively maintained. It is provided 'as is' in its current state! 
If you wish to apply as project maintainer please contact B3 development team by opening a 
topic on the B3 forums.

B3 Development Team
```

Big Brother Bot (B3) is a complete and total server administration package for online games. It is the prefered ingame
RCON Tool currently available. B3 is designed primarily to keep your server free from the derelicts of online gaming,
but offers more, much more. With the stock configuration files, B3 will keep your server free from offensive language,
and team killers alike. A completely automated and customizable warning system will warn the offending players that this
type of behavior is not allowed on your server, and ultimately kick, and or ban them for a predetermined time limit.

Game servers supported: 

- Altitude
- Arma II
- Arma III
- Battlefield 3
- Battlefield 4
- Battlefield Bad Company 2
- Battlefield Hardline
- Chivalry Medieval Warfare
- Call of Duty 1
- Call of Duty 2
- Call of Duty 4: Modern Warfare (iw3)
- Call of Duty 4: GameRanger
- Call of Duty 5: World at War
- Call of Duty 6: Modern Warfare 2 (iw5)
- Call of Duty 7: Black Ops        (t6)
- Call of Duty 8: Modern Warfare 3 (iw5)
- Counter-Strike: Global Offensive
- Enemy Territory
- Enemy Territory Pro
- Insurgency
- Urban Terror 4.1 (ioUrT)
- Urban Terror 4.2
- Urban Terror 4.3
- Medal of Honor 2010
- Medal of Honor Warfighter
- Open Arena
- Red Orchestra 2
- Smokin' Guns
- Soldier of Fortune 2
- World of Padman

## Requirements & installation (Python 3)

This fork runs on **Python 3.9 or newer** (Python 2 is no longer supported).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# optional: PostgreSQL storage and the SFTP log plugin
.venv/bin/pip install -r optional-requirements.txt
.venv/bin/python b3_run.py -c /path/to/b3.ini
```

### Running B3 as a service

- `b3_run.py --check-config -c b3.ini` checks `b3.ini` and the plugin configuration files without connecting to the
  game server or the database. It prints `OK: <file>` and exits with 0, or prints one `ERROR: <reason>` line per
  problem (the first line is the main reason) and exits with 230. Run it before restarting B3 after a change.
- `b3_run.py --version` prints the release and the git commit, for example
  `BigBrotherBot (b3) v2.0.1 (commit 920d7366)`. The commit comes from the `B3_COMMIT` environment variable, from
  `b3/COMMIT` (written when the package is built from a git checkout), or from `git` when B3 runs from a checkout.
- Exit codes (`b3/exitcodes.py`; a code never changes meaning):

  | Code | Meaning |
  |---|---|
  | 0 | normal stop (also on SIGTERM), or `--check-config` found nothing wrong |
  | 220 | fatal error with no more specific code |
  | 221 | restart requested (`!restart`); the auto-restart mode starts B3 again |
  | 222 | shutdown requested (`!die`) |
  | 223 | unexpected error during startup |
  | 230 | invalid configuration (`b3.ini` or a plugin configuration file) |
  | 231 | the game log cannot be opened or read |
  | 232 | the RCON connection cannot be set up |
  | 233 | the database cannot be set up or reached at startup |

  A wrong RCON password does not stop B3: it keeps reading the game log, and RCON also fails for a moment while the
  server changes maps.

Run the test suite with:

```bash
.venv/bin/pip install -r test-requirements.txt
.venv/bin/python -m pytest tests/core
./scripts/start-tests-plugins.sh     # each plugin's tests in their own process
.venv/bin/python -m pytest tests/functional   # end-to-end: the real bot against a fake Urban Terror server
python scripts/check_syntax.py .     # no compile warnings, valid Python 3.9 syntax everywhere
```

MySQL and PostgreSQL tests are skipped unless a server is available (see the `MYSQL_TEST_*` / `POSTGRESQL_TEST_*`
variables in `.github/workflows/tests.yml`).

### Continuous integration

GitHub Actions runs on every pull request:

- **tests**: core and plugin tests on Python 3.9–3.14 with MySQL 8 and PostgreSQL 16, the MySQL tests against
  MariaDB 11, the end-to-end smoke test, and a coverage report (kept as a build artifact).
- **lint**: ruff (syntax errors, undefined or redefined names), `scripts/check_syntax.py`, and `pip-audit` (known
  vulnerabilities in the dependencies).
- **codeql**: GitHub's security scanner (results in the repository's *Security* tab), also weekly.
- **Dependabot** opens pull requests for dependency and GitHub Actions updates.

SonarCloud currently uses *Automatic Analysis*, which cannot import test coverage. To send coverage to SonarCloud:

1. In SonarCloud, open the project's *Administration → Analysis Method* and turn off *Automatic Analysis*.
2. In SonarCloud, create a token (*My Account → Security*) and add it to this GitHub repository as the secret
   `SONAR_TOKEN` (*Settings → Secrets and variables → Actions → Secrets*).
3. Add the repository variable `SONAR_CI_ANALYSIS` with the value `true` (same page, *Variables* tab).

The `coverage` job then runs the SonarCloud analysis itself, using `sonar-project.properties`.

The `publist` plugin, which reports your server's address to the old bigbrotherbot.net master server list, is no
longer loaded automatically. To opt in, add a `publist:` line to the `[plugins]` section of `b3.ini`.

Note on encodings: game log files are read, and RCON traffic is encoded, using the `encoding` option of the `[server]`
section of `b3.ini` (default `latin-1`; the Counter-Strike: GO and Insurgency parsers default to `utf-8`).

## Links to our online presence

* [Master server](http://master.bigbrotherbot.net/)
* [Bug tracker](https://github.com/BigBrotherBot/big-brother-bot/issues)
* [Documentation](https://github.com/BigBrotherBot/big-brother-bot/wiki)


## Installation, configuration and usage

Please refer to our documentation wiki as linked above for a full manual.


## Previous and Current Developers (Hall of Fame)

_[ThorN], [xlr8or], ttlogic, [Courgette], [Fenix], [Bakes], [spacepig], [Durzo], eire.32, [grosbedo], [Freelander], [82ndAB.Bravo17], 
[Just a baka], [Ozon]_ and a big thanks to you, who has offered us snippets of code and improvements on an 
incidental basis. Without you B3 wouldn't be this intelligent!

[![Requirements Status](https://requires.io/github/BigBrotherBot/big-brother-bot/requirements.svg?branch=master)](https://requires.io/github/BigBrotherBot/big-brother-bot/requirements/?branch=master)
[![Code Health](https://landscape.io/github/BigBrotherBot/big-brother-bot/master/landscape.svg?style=flat)](https://landscape.io/github/BigBrotherBot/big-brother-bot/master)
[![Coverage Status](https://coveralls.io/repos/BigBrotherBot/big-brother-bot/badge.svg?branch=master)](https://coveralls.io/r/BigBrotherBot/big-brother-bot?branch=master)

[ThorN]: https://github.com/six8
[xlr8or]: https://github.com/markweirath
[Courgette]: https://github.com/thomasleveil
[Bakes]: https://github.com/j-baker
[spacepig]: https://github.com/spacepig
[Durzo]: https://github.com/durzo
[grosbedo]: https://github.com/grosbedo
[Freelander]: https://github.com/ozguruysal
[82ndAB.Bravo17]: https://github.com/82ndab-Bravo17
[Just a baka]: https://github.com/justabaka
[Fenix]: https://github.com/danielepantaleone
[Ozon]: https://github.com/ozon

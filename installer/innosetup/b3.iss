; BigBrotherBot (B3) Windows installer, for Inno Setup 6.
; Built by installer/windows/build_installer.py, which stages the files (embeddable Python with B3 installed,
; b3.cmd launcher, sample configs) and calls:
;   ISCC.exe /DB3_VERSION=2.0.0 /DB3_STAGE_DIR=<stage folder> b3.iss

#ifndef B3_VERSION
  #error B3_VERSION is not defined (ISCC.exe /DB3_VERSION=x.y.z)
#endif
#ifndef B3_STAGE_DIR
  #error B3_STAGE_DIR is not defined (ISCC.exe /DB3_STAGE_DIR=<folder>)
#endif

[Setup]
; identifies this application for upgrades and uninstall: never change it
AppId={{8C1F3A52-6E0B-4B7D-9A43-2F5D1C7E9B60}
AppName=BigBrotherBot
AppVersion={#B3_VERSION}
AppVerName=BigBrotherBot {#B3_VERSION}
AppPublisher=BigBrotherBot
AppPublisherURL=https://github.com/FMSMITH91/big-brother-bot
AppSupportURL=https://github.com/FMSMITH91/big-brother-bot/issues
AppUpdatesURL=https://github.com/FMSMITH91/big-brother-bot/releases
AppCopyright=Copyright (C) 2005-2026 BigBrotherBot contributors (GPL v2)
; per-user install by default (no administrator rights needed): B3 keeps its config and data in %USERPROFILE%\.b3
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\BigBrotherBot
DefaultGroupName=BigBrotherBot
DisableProgramGroupPage=auto
UsePreviousAppDir=yes
LicenseFile=..\assets_common\gpl-2.0.txt
OutputBaseFilename=b3-{#B3_VERSION}-win64-setup
SetupIconFile=..\assets_common\b3.ico
UninstallDisplayIcon={app}\b3.ico
WizardStyle=modern
WizardImageFile=..\assets_common\WizB3Image.bmp
WizardSmallImageFile=..\assets_common\WizB3SmallImage.bmp
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/ultra64
SolidCompression=yes
SetupLogging=yes
VersionInfoCompany=BigBrotherBot
VersionInfoDescription=BigBrotherBot (B3) setup
VersionInfoProductName=BigBrotherBot
VersionInfoProductTextVersion={#B3_VERSION}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; the Python runtime with B3 installed: replaced as a whole on upgrade (see [InstallDelete])
Source: "{#B3_STAGE_DIR}\python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#B3_STAGE_DIR}\b3.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#B3_STAGE_DIR}\b3.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#B3_STAGE_DIR}\b3-plugins-icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#B3_STAGE_DIR}\license.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#B3_STAGE_DIR}\readme.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "{#B3_STAGE_DIR}\conf\*"; DestDir: "{app}\conf"; Flags: ignoreversion recursesubdirs createallsubdirs
; third party plugins folder: never overwrite what the user put there
Source: "{#B3_STAGE_DIR}\extplugins\*"; DestDir: "{app}\extplugins"; Flags: onlyifdoesntexist recursesubdirs createallsubdirs uninsneveruninstall
; a starting configuration, only if the user has none yet (kept on uninstall)
Source: "{#B3_STAGE_DIR}\conf\b3.distribution.ini"; DestDir: "{%USERPROFILE}\.b3"; DestName: "b3.ini"; Flags: onlyifdoesntexist uninsneveruninstall

[InstallDelete]
; drop the previous version's Python and libraries so no stale module survives an upgrade
Type: filesandordirs; Name: "{app}\python"

[Icons]
Name: "{group}\Run B3"; Filename: "{app}\b3.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\b3.ico"; Comment: "Run BigBrotherBot {#B3_VERSION}"
Name: "{group}\Edit B3 configuration"; Filename: "notepad.exe"; Parameters: """{%USERPROFILE}\.b3\b3.ini"""; IconFilename: "{app}\b3.ico"
Name: "{group}\B3 data folder"; Filename: "{%USERPROFILE}\.b3"
Name: "{group}\Sample configurations"; Filename: "{app}\conf"
Name: "{group}\Third party plugins folder"; Filename: "{app}\extplugins"; IconFilename: "{app}\b3-plugins-icon.ico"
Name: "{group}\Readme"; Filename: "{app}\readme.txt"
Name: "{group}\B3 on GitHub"; Filename: "https://github.com/FMSMITH91/big-brother-bot"
Name: "{group}\Uninstall BigBrotherBot"; Filename: "{uninstallexe}"
Name: "{autodesktop}\BigBrotherBot"; Filename: "{app}\b3.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\b3.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"

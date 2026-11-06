; LegendsRO Helper kurulum betigi (Inno Setup 6). build.ps1 cagirir.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "LegendsRO Helper"

[Setup]
AppId={{69B57396-A0AB-4FB3-9030-79F37B7E11D9}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
; Kullanici klasorune kurulur: ayarlar yonetici izni olmadan kaydedilebilsin
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=LegendsRO-Helper-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppName}.exe

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Guncellemede kullanicinin ayarlari ve sesi korunur
Source: "dist\{#AppName}\config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "dist\{#AppName}\ses.mp3"; DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "dist\{#AppName}\*"; DestDir: "{app}"; Excludes: "config.json,ses.mp3"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppName}.exe"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; Tasks: desktopicon

[Run]
; exe yonetici izni istedigi icin shellexec ile baslatilir
Filename: "{app}\{#AppName}.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent shellexec

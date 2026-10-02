; Instalador do oculto-scan. Sem UPX. O AppId não muda: a versão nova substitui a antiga.
; UTF-8 com BOM. A versão vem do CI (/DMyAppVersion e /DMyAppVersionQuad) ou do padrão abaixo.

#ifndef MyAppVersion
#define MyAppVersion "0.1.12"
#endif
#ifndef MyAppVersionQuad
#define MyAppVersionQuad "0.1.12.0"
#endif

#define MyAppName "oculto-scan"
#define MyAppExeName "oculto-scan.exe"

[Setup]
AppId={{EC7DF64B-360E-4FE7-B685-27540C3E6978}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Henderson Gomes
AppPublisherURL=https://github.com/HendersonGomes/oculto-scan
AppSupportURL=https://github.com/HendersonGomes/oculto-scan/issues
AppUpdatesURL=https://github.com/HendersonGomes/oculto-scan/releases/latest
DefaultDirName={autopf}\oculto-scan
DefaultGroupName=oculto-scan
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=oculto-scan-setup
SetupIconFile=oculto-scan.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName=oculto-scan
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\LICENSE
ShowLanguageDialog=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion={#MyAppVersionQuad}
VersionInfoCompany=Henderson Gomes
VersionInfoDescription=Instalador do oculto-scan
VersionInfoProductName=oculto-scan
VersionInfoCopyright=Copyright 2026 Henderson Gomes. Apache-2.0
VersionInfoProductVersion={#MyAppVersion}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na área de trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\oculto-scan-cli.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; O atalho abre o .exe sem console. O de terminal fica na pasta, sem atalho.
Name: "{group}\oculto-scan"; Filename: "{app}\{#MyAppExeName}"; Comment: "Verifica se a planilha pode vazar dados antes do envio"
Name: "{autodesktop}\oculto-scan"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "Verifica se a planilha pode vazar dados antes do envio"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o oculto-scan"; Flags: nowait postinstall skipifsilent

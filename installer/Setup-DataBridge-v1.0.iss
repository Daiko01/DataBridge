; Setup-DataBridge-v1.0.iss
; Instalador oficial de DataBridge - creado por Leonardo Riveros

#define MyAppName "DataBridge"
#define MyAppVersion "1.0"
#define MyAppPublisher "Leonardo Riveros"
#define MyAppExeName "DataBridge.exe"
#define MyAppIcon "C:\Proyectos\PDF2Excel\assets\app.ico"

[Setup]
AppId={{E7A64F10-3C6B-42A4-99E3-DBB58A9B9C1F}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={pf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=Setup-DataBridge-v1.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
SetupIconFile={#MyAppIcon}

UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; Copia el ejecutable y todas las dependencias necesarias
Source: "C:\Proyectos\PDF2Excel\dist\PDF2ExcelExtractor\*"; \
    DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Accesos con el ícono personalizado
Name: "{group}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{#MyAppIcon}"

Name: "{commondesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{#MyAppIcon}"

[Run]
; Ejecutar la aplicación al finalizar la instalación
Filename: "{app}\{#MyAppExeName}"; \
    Description: "Iniciar {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent

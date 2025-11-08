; Script de Inno Setup para DataBridge
; Guarda esto como 'DataBridge_setup.iss' (por ejemplo)

[Setup]
; --- Info de la App ---
AppName=DataBridge
AppVersion=3.2.0
AppPublisher=Leonardo Riveros
; AppPublisherURL=tu-sitio-web.com
; AppSupportURL=tu-sitio-web.com

; --- Destino de Instalación ---
; {autopf} se resuelve a "C:\Program Files (x86)" o "C:\Program Files"
DefaultDirName={autopf}\DataBridge

; --- Nombres de Archivo ---
; El nombre del instalador que se generará
OutputBaseFilename=Setup-DataBridge-v3.2.0
; Dónde guardar el instalador (en tu carpeta 'installer')
OutputDir=.\
; El ícono para el instalador
SetupIconFile=..\assets\app.ico
; El ícono para Desinstalar (en Panel de Control)
UninstallDisplayIcon=..\assets\app.ico

; --- Opciones de Instalación ---
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
; Opcional: Permite al usuario crear un ícono de escritorio
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";

[Files]
; --- ¡ESTA ES LA PARTE MÁS IMPORTANTE! ---
; Le dice a Inno Setup que copie TODO el contenido de tu carpeta 'dist\DataBridge'
; al directorio de instalación del usuario.

Source: "..\dist\DataBridge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTA: "..\dist\DataBridge\*" asume que guardas este .iss dentro de la carpeta 'installer'

[Icons]
; --- Iconos del Menú Inicio ---
Name: "{autoprograms}\DataBridge"; Filename: "{app}\DataBridge.exe"
Name: "{autoprograms}\Desinstalar DataBridge"; Filename: "{uninstallexe}"

; --- Icono de Escritorio (Opcional) ---
Name: "{autodesktop}\DataBridge"; Filename: "{app}\DataBridge.exe"; Tasks: desktopicon
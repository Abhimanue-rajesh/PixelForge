
[Setup]
AppId=PixelForge
AppName=PixelForge
AppVersion=1.0.0
AppPublisher=PixelForge
DefaultDirName={autopf}\PixelForge
DefaultGroupName=PixelForge
OutputDir=dist\installer
OutputBaseFilename=PixelForge_Setup
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\PixelForge.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\PixelForge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PixelForge"; Filename: "{app}\PixelForge.exe"
Name: "{autodesktop}\PixelForge"; Filename: "{app}\PixelForge.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PixelForge.exe"; Description: "Launch PixelForge"; Flags: postinstall nowait skipifsilent

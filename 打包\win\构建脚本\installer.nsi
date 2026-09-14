; ============================================================
;  柒号收银系统 v3.2.0 - NSIS 安装向导脚本
;  生成 Windows 安装包（.exe）
;  品牌签名：ZIQI
; ============================================================

!include "MUI2.nsh"

; ── 项目品牌信息 ─────────────────────────────────────────────────
!define APP_NAME        "柒号收银系统"
!define APP_VERSION     "3.2.0"
!define APP_PUBLISHER   "ZIQI"
!define APP_DIR         "柒号收银"
!define APP_EXE         "收银系统v3.2.exe"
!define APP_INSTALLER   "ZIQI-柒号收银系统-v3.2.0-Setup.exe"
!define BUILD_DIR       "..\..\输出\收银系统v3.2"

Name "${APP_NAME} v${APP_VERSION}"
OutFile "..\..\输出\${APP_INSTALLER}"
InstallDir "$PROGRAMFILES\${APP_DIR}"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
XPStyle on
InstallColors 0x0F172A 0xF8FAFC
BrandingText "ZIQI · 智能收银系统"

; ── MUI 现代界面设置 ──────────────────────────────────────────────
!define MUI_ABORTWARNING
!define MUI_ICON      "..\..\软件源\icon.ico"
!define MUI_UNICON    "..\..\软件源\icon.ico"
!define MUI_HEADERBACKCOLOR 0x0F172A
!define MUI_HEADERTRANSPARENT
!define MUI_WELCOMEFINISHPAGE_BITMAP ""

; 页面序列
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

; ── 安装页个性化文案 ─────────────────────────────────────────────
Function .onInit
    ; 让安装包视觉风格更符合当前项目：深蓝主色 + 绿色动作色
    SetCtlColors 0 0x0F172A 0xF8FAFC
FunctionEnd

; ── 安装段 ────────────────────────────────────────────────────────
Section "安装"
    SetOutPath "$INSTDIR"

    ; 当前项目使用离线优先、跨门店协同的品牌语义
    File /r "${BUILD_DIR}\*.*"

    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\卸载.lnk" "$INSTDIR\uninstall.exe"
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"

    WriteUninstaller "$INSTDIR\uninstall.exe"

    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayName"     "${APP_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayVersion"  "${APP_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "Publisher"       "${APP_PUBLISHER}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayIcon"     "$INSTDIR\${APP_EXE}"

SectionEnd

; ── 安装完成页 ───────────────────────────────────────────────────
Section -Post
    WriteRegStr HKCU "Software\${APP_PUBLISHER}\${APP_NAME}" "InstallPath" "$INSTDIR"
    ExecShell "open" "$INSTDIR\${APP_EXE}"
SectionEnd

; ── 卸载段 ────────────────────────────────────────────────────────
Section "Uninstall"
    RMDir /r "$INSTDIR"
    RMDir /r "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    DeleteRegKey HKCU "Software\${APP_PUBLISHER}\${APP_NAME}"
SectionEnd

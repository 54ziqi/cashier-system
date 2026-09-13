; ============================================================
;  柒号收银系统 v3.2.0 - NSIS 安装向导脚本
;  生成 Windows 安装包（.exe）
; ============================================================

!include "MUI2.nsh"

; ── 基本信息 ──────────────────────────────────────────────────────
!define APP_NAME      "柒号收银系统"
!define APP_VERSION   "3.2.0"
!define APP_PUBLISHER "柒号科技"
!define APP_DIR       "柒号收银"
!define APP_EXE       "收银系统v3.2.exe"
!define BUILD_DIR     "..\..\输出\收银系统v3.2"  ; 相对于本脚本所在目录 (打包\win\构建脚本\ → 打包\win\输出\收银系统v3.2\)

Name "${APP_NAME} v${APP_VERSION}"
OutFile "..\..\输出\${APP_NAME}_v${APP_VERSION}_Setup.exe"
InstallDir "$PROGRAMFILES\${APP_DIR}"
RequestExecutionLevel admin

; ── MUI 现代界面设置 ──────────────────────────────────────────────
!define MUI_ABORTWARNING
!define MUI_ICON   "..\..\软件源\icon.ico"      ; 安装程序图标（可选）
!define MUI_UNICON "..\..\软件源\icon.ico"      ; 卸载程序图标

; 页面序列
!insertmacro MUI_PAGE_WELCOME                          ; 欢迎页
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"          ; 许可协议（如有）
!insertmacro MUI_PAGE_DIRECTORY                        ; 选择安装目录
!insertmacro MUI_PAGE_INSTFILES                        ; 安装过程
!insertmacro MUI_PAGE_FINISH                           ; 完成页

; 卸载页面
!insertmacro MUI_UNPAGE_CONFIRM                        ; 确认卸载
!insertmacro MUI_UNPAGE_INSTFILES                      ; 卸载过程

; ── 语言 ──────────────────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "SimpChinese"

; ── 安装段 ────────────────────────────────────────────────────────
Section "安装"

    SetOutPath "$INSTDIR"

    ; ── 复制 PyInstaller 构建产物 ──────────────────────────────────
    File /r "${BUILD_DIR}\*.*"

    ; ── 创建开始菜单快捷方式 ───────────────────────────────────────
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"  "$INSTDIR\${APP_EXE}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\卸载.lnk"          "$INSTDIR\uninstall.exe"

    ; ── 创建桌面快捷方式 ───────────────────────────────────────────
    CreateShortcut  "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"

    ; ── 卸载程序 ───────────────────────────────────────────────────
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; ── 注册表中添加"添加/删除程序"条目 ────────────────────────────
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

; ── 安装完成:询问是否启动 ─────────────────────────────────────────
Section -Post

    ; 自动启动程序
    ExecShell "" "$INSTDIR\${APP_EXE}"

SectionEnd

; ── 卸载段 ────────────────────────────────────────────────────────
Section "Uninstall"

    ; ── 删除文件 ───────────────────────────────────────────────────
    RMDir /r "$INSTDIR"

    ; ── 删除快捷方式 ───────────────────────────────────────────────
    RMDir /r "$SMPROGRAMS\${APP_NAME}"
    Delete  "$DESKTOP\${APP_NAME}.lnk"

    ; ── 删除注册表条目 ─────────────────────────────────────────────
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

SectionEnd

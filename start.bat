@echo off
chcp 65001 >nul
title YouTube Downloader
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set "PY_CMD=py"
    ) else (
        echo [ERROR] Python tidak ditemukan! Harap install Python dari https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

%PY_CMD% main.py %*
if %errorlevel% neq 0 pause

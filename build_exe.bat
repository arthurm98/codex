@echo off
setlocal

pyinstaller --noconfirm --onefile --windowed --name MangaDownloader main.py

echo Build finalizado. Verifique a pasta dist\MangaDownloader.exe
pause

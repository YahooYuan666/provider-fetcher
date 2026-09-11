@echo off
cd /d "%~dp0"
python -m provider_fetcher %*

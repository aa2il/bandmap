@echo off
echo %DATE% %TIME%
goto BUILD
echo.
echo Notes about how to run BANDMAP on Windoze 10
echo.
echo Already should have everything we need installed already
        pip install -r requirements.txt
echo.
echo Run the script under python:
     bandmap.py
:BUILD     
echo.
echo Compile - works on both windoz and linux:
echo This takes a long time ...
echo.
     pyinstaller --onefile bandmap.py
     copy ..\data\cty.plist dist
     copy ..\data\nodes.plist dist
echo.
echo Run the compiled version:
     dist\bandmap.exe
echo.
echo On Linux:
echo "cp ../data/cty.plist dist"
echo dist\bandmap.exe
echo.
echo Run Inno Setup Compiler and follow the prompts to create an installer.
echo This installer works on Windoz 10 and Bottles.
echo.
echo %DATE% %TIME%
echo.
   

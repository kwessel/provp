# provp
ProVP bridge between ProQA and CAD

To use, first download Python.

For Windows, Python can be downoaded from: https://www.python.org/ftp/python/3.10.7/python-3.10.7-amd64.exe

When installing, choose the standard (not custom) installation, but check the box to add Python to the path.

Once installed, run the following command to install pyinstaller which lets
you compile Python scripts into a stand-alone executeable. Open a Windows
command prompt, then run:

pip install pyinstaller

Now, download provp.py from this repository. Then, in the directory where you downloaded it, run:

pyinstaller -F provp.py

This will create a dist subdirectory of your currentdirectory which will contain provp.exe.

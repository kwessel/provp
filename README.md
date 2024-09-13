# provp
ProVP bridge between ProQA and CAD

To use, first download Python.

For Windows, Python can be downoaded from: https://www.python.org/ftp/python/3.10.7/python-3.10.7-amd64.exe

When installing, choose the standard (not custom) installation, but check the box to add Python to the path.

Once installed, run the following command to install pyinstaller which lets
you compile Python scripts into a stand-alone executeable. Open a Windows
command prompt, then run:

pip install pyinstaller

Now, download pqaclient.py from this repository. Then, in the directory where you downloaded it, run:

pyinstaller -F pqaclient.py

This will create a dist subdirectory of your currentdirectory which will contain pqaclient.exe.

To install the server:

1. Download pqaserver.py and pqaserver.service from this repository.
2. Upload pqaserver.py to $HOME/bin or wherever you want it
to live on your server.
3. Make pqaserver.py executable on your server with:
chmod 755 $HOME/bin/pqaserver.py
4. Modify pqaserver.service's execstart line to point to the path where
you put pqaserver.py:
ExecStart=/home/brownlee/services/pqaserver.py
You can also add command-line parameters here:
ExecStart=/home/brownlee/services/pqaserver.py --cad-port=12345
5. Upload pqaserver.py to $HOME/.local/share/systemd/user/pqaserver.service.
If this directory doesn't exist, you can create it with:
mkdir -p $HOME/.local/share/systemd/user
6. Tell systemd to scan for new unit files and find the one you just added:
systemctl --user daemon-reload
7. Now, you can start the server with:
systemctl --user start pqaserver
8. If you want pqaserver to run at system boot time:
systemctl --user enable pqaserver.service

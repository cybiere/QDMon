#!/usr/bin/env python3

import subprocess
import datetime
import smtplib
import requests
import json
from pathlib import Path
import sys
import socket
import ssl

verbose=False
output=False
outFileName=""

for arg in sys.argv:
    if arg == "-v":
        verbose=True
    elif arg == "-o":
        output=True
        continue
    if output and outFileName == "":
        outFileName = arg

if outFileName == "":
    outFileName="status.json"

confPath = Path("config.json")
if not confPath.is_file():
    config={
            "sshUser":"sshUser",
            "rsaKey":"/home/user/.ssh/id_rsa",
            "notifyMail":"user.to.notified@example.com",
            "notifyUser":"smtp.user@example.com",
            "notifyPass":"hunter2",
            "notifyServer":"smtp.example.com",
            "historyLen":"3",
            "servers":
            "historyLen":"3",[
                {
                    "name":"ServerName",
                    "ip":"192.168.0.1",
                    "categories":["web","mail"],
                    "sshUser":"sshUser",
                    "rsaKey":"/home/user/.ssh/id_rs",
		    "smtpPort":"587",
		    "smtpTLS":"False",
		    "imapPort":"993",
		    "imapTLS":"True",
		    "httpPort":"80",
                }
                ]
            }
    with open('config.json','w') as outfile:
        json.dump(config,outfile,indent="\t")
    print("config.json file not found, default file created.\nPlease customize it and run qdmon again.")
    exit()

with open('config.json','r') as confFile:
    conf = json.load(confFile)

if verbose:
    print("QDMon starting")

def pingCheck(server):
    res = subprocess.run(["ping","-c","1",server['ip']],stdout=subprocess.DEVNULL)
    if res.returncode != 0:
        if verbose :
            print("[ERR] Server didn't respond to ping")
        return (False,"Server didn't respond to ping")
    else:
        if verbose :
            print("[OK] Server responded to ping")
        return (True,"Server responded to ping")

def fsCheck(server):
    user = server['sshUser'] if 'sshUser' in server else conf['sshUser']
    key = server['rsaKey'] if 'rsaKey' in server else conf['rsaKey']
    res = subprocess.run(["ssh","-i",key,user+'@'+server['ip'],'touch fic && rm fic'])
    if res.returncode != 0:
        if verbose :
            print("[ERR] FS write error, return code :"+str(res.returncode))
        return (False,"FS write error, return code :"+str(res.returncode))
    else:
        if verbose :
            print("[OK] FS write ok")
        return (True,"FS write ok")

def cpuLoadCheck(server):
    user = server['sshUser'] if 'sshUser' in server else conf['sshUser']
    key = server['rsaKey'] if 'rsaKey' in server else conf['rsaKey']
    #TODO fetch stdout in var
    try:
        cpuLoad = subprocess.check_output(["ssh","-i",key,user+'@'+server['ip'],"grep 'cpu ' /proc/stat | awk '",'{usage=($2+$4)*100/($2+$4+$5)} END {print usage }',"'"])
        loadInt,loadDec = cpuLoad.decode("utf-8")[:-1].split('.')
        cpuLoad = ".".join((loadInt,loadDec[:2]))
        if verbose :
            print("[OK] CPU Load :"+cpuLoad+"%")
        return (True,cpuLoad)
    except subprocess.CalledProcessError as e:
        if verbose :
            print("[ERR] CPU Load error :"+e.output)
        return (False,e.output)

    #TODO check val against threshold and return

def httpCheck(server):
    port = server['httpPort'] if 'httpPort' in server else "80"
    try:
        r = requests.get("http://"+server['ip']+":"+port+"/", allow_redirects=False, timeout=3)
    except:
        if verbose :
            print("[ERR] HTTP request failed")
        return (False,"HTTP request failed")
    else:
        if verbose :
            print("[OK] HTTP returned code : "+str(r.status_code))
        return (True,"HTTP returned code : "+str(r.status_code))

def smtpCheck(server):
    if server["smtpTLS"] == "True":
        port = server['smtpPort'] if 'smtpPort' in server else "465"
    else:
        port = server['smtpPort'] if 'smtpPort' in server else "25"
    context = ssl.create_default_context()
    context.check_hostname = False
    try:
        sock = socket.create_connection((server['ip'],int(port)))
        if server["smtpTLS"] == "True":
            ssock = context.wrap_socket(sock)
            lsock = ssock
        else:
            lsock = sock
        lsock.settimeout(5)
        reply = lsock.recv(1024).decode("utf-8")
        if "SMTP" in reply:
            if verbose :
                print("[OK] SMTP server replied "+reply[:-2])
            if server["smtpTLS"] == "True":
                ssock.close()
            sock.close()
            return (True,"SMTP server replied "+reply[:-2])
        else:
            if verbose :
                print("No SMTP in "+reply)
    except:
        if verbose :
            print("SMTP connect failed")
    sock.close()
    if verbose :
        print("[ERR] No SMTP reply")
    return (False,"No SMTP reply")

def imapCheck(server):
    if server["imapTLS"] == "True":
        port = server['imapPort'] if 'imapPort' in server else "993"
    else:
        port = server['imapPort'] if 'imapPort' in server else "143"
    context = ssl.create_default_context()
    context.check_hostname = False
    try:
        sock = socket.create_connection((server['ip'],int(port)))
        if server["imapTLS"] == "True":
            ssock = context.wrap_socket(sock)
            lsock = ssock
        else:
            lsock = sock
        lsock.settimeout(5)
        reply = lsock.recv(1024).decode("utf-8")
        if "IMAP" in reply:
            if verbose :
                print("[OK] IMAP server replied "+reply[:-2])
            if server["imapTLS"] == "True":
                ssock.close()
            sock.close()
            return (True,"IMAP server replied "+reply[:-2])
        else:
            if verbose :
                print("No IMAP in "+reply)
    except:
        if verbose :
            print("IMAP connect failed")
    sock.close()
    if verbose :
        print("[ERR] No IMAP reply")
    return (False,"No IMAP reply")

checks={
        "basic":[fsCheck,cpuLoadCheck],
        "web":[httpCheck],
        "mail":[smtpCheck,imapCheck]
        }

errs=[]
log={}
for server in conf['servers']:
    if verbose :
        print(">",server['name'])
    log[server['name']] = {}
    cats = server['categories'] if 'categories' in server else []
    (success,message) = pingCheck(server)
    log[server['name']][pingCheck.__name__[:-5]] = {
            "success":"OK" if success else "KO",
            "msg":message
            }
    if success == False:
        errs.append((server['name'],message))
        continue
    cats.insert(0,"basic")

    for cat in cats:
        if cat in checks and checks[cat]:
            for check in checks[cat]:
                (success,message)=check(server)
                log[server['name']][check.__name__[:-5]] = {
                        "success":"OK" if success else "KO",
                        "msg":message
                        }
                if not success:
                    errs.append((server['name'],message))
        else:
            errs.append((server['name'],"No checks for "+cat+" category"))


statusPath = Path(outFileName)
if statusPath.is_file():
    with open(outFileName,'r') as outFile:
        status = json.load(outFile)
else:
    status = {}

#TODO status len as conf param
maxLen = int(conf['historyLen']) if 'historyLen' in conf else 10
keys = list(status.keys())
if len(keys) == maxLen:
    status.pop(keys[0])

now = datetime.datetime.now()
status[now.strftime("%Y-%m-%d_%H:%M:%S")] = log



with open(outFileName,'w') as outFile:
    json.dump(status,outFile,indent="\t")
    

if errs:
    if verbose :
        print(len(errs),"error(s) found. Sending email alert.")
    subject = '[QDMon] Monitoring alert !'
    body = "Errors happened during latest monitoring pass :\n"
    for srv,msg in errs:
        body = body+"\n["+srv+"] "+msg
    
    email_text = """\
From: %s
To: %s
Subject: %s

%s
""" % (conf["notifyUser"],conf["notifyMail"], subject, body)

    try:
        server = smtplib.SMTP_SSL(conf['notifyServer'], 465)
        server.ehlo()
        server.login(conf["notifyUser"], conf['notifyPass'])
        server.sendmail(conf["notifyUser"], conf["notifyMail"], email_text)
        server.close()
    except Exception as e:
        print('Email notification failed :',str(e))

if verbose :
    print("QDMon over")

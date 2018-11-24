#!/usr/bin/env python3

import subprocess
import smtplib
import requests
import json
from pathlib import Path
import sys
import socket

verbose=False
for arg in sys.argv:
    if arg == "-v":
        verbose=True

confPath = Path("config.json")
if not confPath.is_file():
    config={
            "sshUser":"sshUser",
            "rsaKey":"/home/user/.ssh/id_rsa",
            "notifyMail":"user.to.notified@example.com",
            "smtpUser":"smtp.user@example.com",
            "smtpPass":"hunter2",
            "smtpServer":"smtp.example.com",
            "servers":[
                {
                    "name":"ServerName",
                    "ip":"192.168.0.1",
                    "categories":["web"],
                    "sshUser":"sshUser",
                    "rsaKey":"/home/user/.ssh/id_rsa",
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

def httpCheck(server):
    try:
        r = requests.get("http://"+server['ip']+"/")
    except:
        if verbose :
            print("[ERR] HTTP request failed")
        return (False,"HTTP request failed")
    else:
        if verbose :
            print("[OK] HTTP returned code : "+str(r.status_code))
        return (True,"HTTP returned code : "+str(r.status_code))

def smtpCheck(server):
    try:
        sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock.connect((server['ip'],int(server['smtpPort'])))
        sock.settimeout(5)
        reply = sock.recv(1024).decode("utf-8")
        if "SMTP" in reply:
            if verbose :
                print("[OK] SMTP server replied "+reply[:-2])
            return (True,"SMTP server replied "+reply[:-2])
        else:
            if verbose :
                print("No SMTP in "+reply)
    except:
        if verbose :
            print("SMTP connect failed")
    if verbose :
        print("[ERR] No SMTP reply")
    return (False,"No SMTP reply")

    print

checks={
        "basic":[fsCheck],
        "web":[httpCheck],
        "mail":[smtpCheck]
        }

errs=[]
for server in conf['servers']:
    if verbose :
        print(">",server['name'])
    cats = server['categories'] if 'categories' in server else []
    (success,message) = pingCheck(server)
    if success == False:
        errs.append((server['name'],message))
        continue
    cats.insert(0,"basic")

    for cat in cats:
        if cat in checks and checks[cat]:
            for check in checks[cat]:
                (success,message)=check(server)
                if not success:
                    errs.append((server['name'],message))
        else:
            errs.append((server['name'],"No checks for "+cat+" category"))

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
""" % (conf["smtpUser"],conf["notifyMail"], subject, body)

    try:
        server = smtplib.SMTP_SSL(conf['smtpServer'], 465)
        server.ehlo()
        server.login(conf["smtpUser"], conf['smtpPass'])
        server.sendmail(conf["smtpUser"], conf["notifyMail"], email_text)
        server.close()
    except Exception as e:
        print('Email notification failed :',str(e))

if verbose :
    print("QDMon over")

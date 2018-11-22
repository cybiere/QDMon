#!/usr/bin/env python3

import subprocess
import smtplib
import requests
import json
from pathlib import Path

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

def pingCheck(server):
    res = subprocess.run(["ping","-c","1",server['ip']],stdout=subprocess.DEVNULL)
    if res.returncode != 0:
        return (False,"Server didn't respond to ping")
    else:
        return (True,"Server responded to ping")

def fsCheck(server):
    user = server['sshUser'] if 'sshUser' in server else conf['sshUser']
    key = server['rsaKey'] if 'rsaKey' in server else conf['rsaKey']
    res = subprocess.run(["ssh","-i",key,user+'@'+server['ip'],'touch fic && rm fic'])
    if res.returncode != 0:
        return (False,"FS write error, return code :"+str(res.returncode))
    else:
        return (True,"FS write ok")

def httpCheck(server):
    try:
        r = requests.get("http://"+server['ip']+"/")
    except:
        return (False,"HTTP request failed")
    else:
        return (True,"HTTP returned code : "+str(r.status_code))

checks={
        "basic":[fsCheck],
        "web":[httpCheck]
        }

errs=[]
for server in conf['servers']:
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


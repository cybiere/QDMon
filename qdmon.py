#!/usr/bin/env python3

import subprocess
import smtplib
import requests
import json
from pathlib import Path
import sys
import socket
import ssl
import sqlite3

verbose=False

for arg in sys.argv:
    if arg == "-v":
        verbose=True

confPath = Path("config.json")
if not confPath.is_file():
    config={
            "sshUser":"sshUser",
            "rsaKey":"/home/user/.ssh/id_rsa",
            "notifyMail":"user.to.notify@example.com",
            "notifyUser":"smtp.user@example.com",
            "notifyPass":"hunter2",
            "notifyServer":"smtp.example.com",
            "notifyFreq":"6",
            "metricsHistory":"10",
            "servers":[
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


#Open and create DB if first run
dbConn = sqlite3.connect('qdmon.db')
c = dbConn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS servers (name TEXT PRIMARY KEY);")
c.execute("CREATE TABLE IF NOT EXISTS metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, server TEXT, metric TEXT, value TEXT, checkTime DATE DEFAULT (datetime('now','localtime')), FOREIGN KEY(server) REFERENCES servers(name));")
c.execute("CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, server TEXT, checkpoint TEXT, message TEXT, checkTime DATE DEFAULT (datetime('now','localtime')), nextWarn INTEGER, ack INTEGER DEFAULT 0, FOREIGN KEY(server) REFERENCES servers(name));")
dbConn.commit()
dbServers = []
for row in c.execute('SELECT name FROM servers'):
    dbServers.append(row[0])

confServers = []
for server in conf["servers"]:
    confServers.append(server['name'])

#Purge servers removed from config
for server in dbServers:
    if server not in confServers:
        c.execute('DELETE FROM alerts WHERE server=?',(server,))
        c.execute('DELETE FROM metrics WHERE server=?',(server,))
        c.execute('DELETE FROM servers WHERE name=?',(server,))

#Insert servers added from config
for server in confServers:
    if server not in dbServers:
        c.execute('INSERT INTO servers (name) VALUES (?)',(server,))
dbConn.commit()

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

def cpuLoadMetric(server):
    user = server['sshUser'] if 'sshUser' in server else conf['sshUser']
    key = server['rsaKey'] if 'rsaKey' in server else conf['rsaKey']
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

def memAvailMetric(server):
    user = server['sshUser'] if 'sshUser' in server else conf['sshUser']
    key = server['rsaKey'] if 'rsaKey' in server else conf['rsaKey']
    try:
        memAvail = subprocess.check_output(["ssh","-i",key,user+'@'+server['ip'],"free -m | grep 'Mem' | tr -s '[:blank:]' | cut -d ' ' -f 7"])
        memAvail = memAvail.decode("utf-8")[:-1]
        if verbose :
            print("[OK] RAM available :"+memAvail)
        return (True,memAvail)
    except subprocess.CalledProcessError as e:
        if verbose :
            print("[ERR] RAM available error :"+e.output)
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
        "basic":[fsCheck],
        "web":[httpCheck],
        "mail":[smtpCheck,imapCheck]
        }

metrics=[cpuLoadMetric,memAvailMetric]

for server in conf['servers']:
    if verbose :
        print(">",server['name'])
    cats = server['categories'] if 'categories' in server else []
    (success,message) = pingCheck(server)
    if success:
        c.execute("DELETE FROM alerts WHERE server=? AND checkpoint=?",(server['name'],pingCheck.__name__))
        dbConn.commit()
    else:
        c.execute("SELECT nextWarn FROM alerts WHERE server=? AND checkpoint=?",(server['name'],pingCheck.__name__))
        alert = c.fetchone()
        if alert == None:
            c.execute("INSERT INTO alerts (server,checkpoint,message,nextWarn) VALUES (?,?,?,0)",(server['name'],pingCheck.__name__,message))
        dbConn.commit()
        continue
    cats.insert(0,"basic")

    for metric in metrics:
        (success,value)=metric(server)
        if success:
            c.execute("DELETE FROM alerts WHERE server=? AND checkpoint=?",(server['name'],metric.__name__))
            c.execute("INSERT INTO metrics (server,metric,value) VALUES (?,?,?)",(server['name'],metric.__name__,value))
            c.execute("SELECT COUNT(*),MIN(id) FROM metrics WHERE server=? AND metric=?",(server['name'],metric.__name__))
            met = c.fetchone()
            if met[0] > int(conf['metricsHistory']):
                c.execute("DELETE FROM metrics WHERE id=?",(met[1],))
            dbConn.commit()
        else:
            c.execute("SELECT nextWarn FROM alerts WHERE server=? AND checkpoint=?",(server['name'],metric.__name__))
            alert = c.fetchone()
            if alert == None:
                c.execute("INSERT INTO alerts (server,checkpoint,message,nextWarn) VALUES (?,?,?,0)",(server['name'],metric.__name__,value))
            dbConn.commit()

    for cat in cats:
        if cat in checks and checks[cat]:
            for check in checks[cat]:
                (success,message)=check(server)
                if success:
                    c.execute("DELETE FROM alerts WHERE server=? AND checkpoint=?",(server['name'],check.__name__))
                else:
                    c.execute("SELECT nextWarn FROM alerts WHERE server=? AND checkpoint=?",(server['name'],check.__name__))
                    alert = c.fetchone()
                    if alert == None:
                        c.execute("INSERT INTO alerts (server,checkpoint,message,nextWarn) VALUES (?,?,?,0)",(server['name'],check.__name__,message))
                    dbConn.commit()

errs=[]
rows = c.execute("SELECT server,message,nextWarn FROM alerts WHERE ack=0")
lastCount = 10
for row in rows:
    errs.append(row)
    lastCount = row[2];

if lastCount > 0:
    c.execute("UPDATE alerts SET nextWarn=?",(lastCount-1,))
    dbConn.commit()
else:
    c.execute("UPDATE alerts SET nextWarn=?",(int(conf['notifyFreq'])-1,))
    dbConn.commit()

    if verbose :
        print(len(errs),"error(s) found. Sending email alert.")
    subject = '[QDMon] Monitoring alert !'
    body = "Errors happened during latest monitoring pass :\n"
    for srv,msg,nextWarn in errs:
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
dbConn.close()
if verbose :
    print("QDMon over")

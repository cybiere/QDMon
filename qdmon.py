#!/usr/bin/env python3

import subprocess
import requests
import json
from pathlib import Path

confPath = Path("config.json")
if not confPath.is_file():
    config={
            "user":"sshUser",
            "rsaKey":"/home/user/.ssh/id_rsa",
            "servers":[
                {
                    "name":"ServerName",
                    "ip":"192.168.0.1",
                    "categories":["web"],
                    "user":"sshUser",
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
        print("[ERROR] Couldn't ping "+server['name'])
        return False
    else:
        print("[OK] "+server['name']+" responds to ping")
        return True

def fsCheck(server):
    user = server['user'] if 'user' in server else conf['user']
    key = server['rsaKey'] if 'rsaKey' in server else conf['rsaKey']
    res = subprocess.run(["ssh","-i",key,user+'@'+server['ip'],'touch fic && rm fic'])
    if res.returncode != 0:
        print("[ERROR] FS write error, return code :",res.returncode)
        return False
    else:
        print("[OK] FS write ok")
        return True

def httpCheck(server):
    try:
        r = requests.get("http://"+server['ip']+"/")
    except:
        print("[ERROR] HTTP request to "+server['name']+" failed")
        return False
    else:
        print("[OK] HTTP returned code :",r.status_code)
        return True

checks={
        "basic":[fsCheck],
        "web":[httpCheck]
        }


for server in conf['servers']:
    cats = server['categories'] if 'categories' in server else []
    print("Checking "+server['name']+" ("+server['ip']+")")
    if pingCheck(server) == False:
        exit()
    cats.insert(0,"basic")

    for cat in cats:
        if cat in checks and checks[cat]:
            for check in checks[cat]:
                check(server)
        else:
            print("No checks for "+cat+" category")



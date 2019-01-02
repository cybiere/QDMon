# QDMon
Quick and Dirty python3 Monitoring script for my VMs

# Usage
Run the script once to create template conf, fill conf and then run the script again to perform checks

## Command options

- `-v` activates verbose output

# What does it do

- Checks if server responds to ping
- Checks if server filesystem is writeable
- Checks if server responds to HTTP Get / request
- Checks if IMAP and SMTP services are reachable (using TLS or not)
- Measures CPU usage in percent

All measures and alerts are stored in a sqlite3 db. Alerts are also sent by email.

# What will it do

- More stuff
- Web dashboard ?

# Configuration

After first run, a blank configuration file is created. Fill it before running qdmon. Options are :

## Global options

### Notification

Parameters for the email notification

- `notifyMail` [email]: the email address to which notification email will be sent,
- `notifyUser` [email]: the email address from which notification email will be sent,
- `notifyServer` [ip/domain]: the smtp server from which notification email will be sent,
- `notifyPass` [password]: the password for the sender smtp account,
- `notifyFreq` [integer]: defines the frequency of notifications if not fixed : will warn when problem is found and every _$notifyFreq$_ run until fixed.

### Misc

- `metricsHistory` [integer]: last _$metricsHistory$_ will be saved in database,
- `sshUser` [username]: the username used to log in the monitored servers through SSH,
- `rsaKey` [path]: absolute path to the private key in order to perform authentication on monitored servers.

## Per server options

- `name` [string]: the server name in database and alert emails,
- `ip` [ip]: the servers IP address,
- `sshUser` [username]: overrides global option for given server,
- `rsaKey` [path]: overrides global option for given server,
- `categories` [json array]: the categories of checks to perform on this server. Currently availables values are :
  - `web`: checks for web server,
  - `mail`: checks for SMTP and IMAP server.
- `smtpTLS` [boolean]: true if the serveur uses SMTPS, false if no encryption or startTLS,
- `smtpPort` [integer]: overrides SMTP server port (default is 465 if TLS, 25 else),
- `imapTLS` [boolean]: true if the server uses IMAPS, false if no encryption,
- `imapPort` [integer]: overrides IMAP server port (default is 993 if TLS, 143 else),
- `httpPort` [integer]: overrides HTTP server port (default is 80)




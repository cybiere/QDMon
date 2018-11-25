# QDMon
Quick and Dirty python3 Monitoring script for my VMs

# Usage
Run the script once to create template conf, fill conf and then run the script again to perform checks

## Command options

- `-v` activates verbose output
- `-o [filename]` saves qdmon output in json file

# What does it do

- Checks if server responds to ping
- Checks if server filesystem is writeable
- Checks if server responds to HTTP Get / request
- Checks if IMAP and SMTP services are reachable (using TLS or not)

# What will it do

- More stuff

# Broadlink Scheduler

This is a basic python code to manage scheduled actions on a broadlink device.

It uses:
- the [python-broadlink](https://github.com/romelec/python-broadlink) module
- a very minimalistic Flask web server that update a JSON file that contains actions to perform
- the schedule module that triggers actions

## Usage

Simply launch the `sdheduler.py` file, it creates one thread for the web server (on port 8080) and one for the scheduler.

## Setup

Update the `data.json` file with the device configuration and the data for each RF command to send.\
For now it has no ability to learn use the broadlink cli command and copy the hexadecimal data to the file:\
`python .\broadlink_cli.py --type 0x5213 --host 192.168.0.17 --mac ec0baea05afb  --rflearn --frequency 433.92 --learnfile ../data/chambre.stop`

Example:
```
[
    {
        "name": "porte.stop", ## action name
        "data": "<hex data>"  ## action data
    },
    {
        "name": "porte.up",   ## action name
        "data": "<hex data>"  ## action data
    },
    {
        "name": "device",       ## Configuration tag
        "devtype": "0x5213",    ## identifier
        "host" : "192.168.0.1", ## IP address
        "mac" : "ec0baea05afb"  ## mac address
    }
]
```

The `jobs.json` vcontains the actions to executr, it can be edited manually or with the web interface.\
The scheduler is automatically updated when the jobs are updated via the web interface.
```
[
    {
        "name": "matin 2",                      ## Job name
        "time": "08:10",                        ## Time to execute the job
        "parameters": {
            "action1": "fenetre.up, porte.up",  ## List of commands to send (must match a command in data.json)
            "delay": 6,                         ## Delay in seconds after executing the action1 list
            "action2": "porte.stop",            ## List of commands to send after the delay
            "weekday": true,                    ## Execute it on a week day
            "weekend": false                    ## Execute it on a weekend day
        }
    },
]
```

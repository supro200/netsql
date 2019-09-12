# NetSQL

This script allows to perform SQL-like queries on a single or group of networks devices, like this:
```
select Interface,Status,Link_Status,Last_Input,Vlan,Description from interfaces where Link_Status = down and Vlan = 100
```
You can query your network as it was a SQL table, and, for example, answer these questions:

* Where is this MAC address in my network?
* How many switch ports are in use, how many ports never been used? 
* Does this route exist in my network? 
* What VLANs and IP addresses are configured and active?
* How many IP Phones do we have?

## Installation:

It is recommended to build a Python 3 virtual environment. 
Details on how to set one up can be found [here](https://docs.python.org/3/library/venv.html). 
Once your virtual environment is setup and activated, install NetSQL:
 
```
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade git+https://github.com/supro200/netsql.git
```

```
$ pip install -r requirements.txt
```

## How it works:

The script connects to the network devices using Netmiko, gathers command output, stores into text files, converts them to CSV using TextFSM and NTC templates, and then process as Pandas dataframes.
The results are device-command specific CSV files, and combined HTML report.

When processing data, the script uses/creates the following directories:

* **raw_data/<device_IP>** - raw command output from the device in .txt files and converted CSV files
* **reports/<device_IP>** - processed CSV files

The default directory for NTC tempates is **templates/**
If --html-output option is selected, the .html files are places in **reports/**

Possible sources(tables) to query and their attributes are defined in **source_definitions.json** and the corresponding commands to run **command_definition.json** 
See below for more details.

## How to use it:

Use the following CLI parameters:

Required:
 '-q', '--query'    - SQL-formatted query, see examples below
 '-s', '--source'  -  Source file or a single IP addresses to process, for example:
                      --source device_ip_addresses.txt     # file with IP addresses
                      --source 10.74.1.1                   # single IP addresses
 '-u', '--user',  help="Username to connect to network devices",

Optional:
 --no-connect - Run without connecting to network devices, processes the command output already collected.
                This is useful when you run a command and then need to query on different fields or conditions.
                Considerably improves query processing, as it simply processes text files.
  --screen-output - Prints report to screen. CVS reports are always generated. Turned on by default.
  --screen-lines  - Number of lines printed to screen. Full output is always printed to CSV files. Default is 10.
  --html-output   - Prints report to HTML. CVS reports are always generated. Turned off by default

Example:
 python netsql.py --query="select * from interfaces where Last_Input = never" --source 10.23.235.3 --user aupuser3

### IP Address Sources

Required in --source CLI option

The script can use a single IP to connect, like this:
```
--source 10.23.235.3
```
or 
```
--source=10.23.235.3
```

Im most cases a query on multiple devices is most useful, so these devices should be defined in a text file.
The file format is arbirary, the script recognises IP addresses automatically, as long as they in a separate line.
All other lines are ignored, but for better readability it is recommended to comment them with # 

####Example:
 
``` 
---- distr_switches.txt ----
# 150 Bourke St
10.71.42.65
# 89 Cleveland St
10.71.4.1
# 333 Queen St
10.71.27.97
# 901 Lonsdale St
10.71.27.197
```

Use:
```
--source distr_switches.txt
```

It is recommended to create a separate directory for source files, just for convenience.

### Username

Required in --user CLI option

Password needs to entered manually each time the script runs.

**Note** with **--no-connect** option, the script doesn't actually connect to network devices, so username and password can be anything.

## Queries

The query should be in the following format:
```
select <fields> from <data_source> where <conditions>
```
<data_source>, <fields> and <conditions> are described below, following by examples

#### Data Sources

Data Source is the the result of one or two command outputs, defined in **data_source_definitions.json** 
Used in queries in **from** clause, for example:
```
select <something> from <datasource>
```
You can add a new datasource to the JSON file, and start querying it.
The Data source definition format:
```
  {
    "data_source_name": "addresses",
    "commands": [                               <<<  List of commands
      "show ip arp",
      "show mac address-table"
    ],
    "process_dataframes": true,                 <<< Whether to convert raw command output to CSV, in some case you may want just to collect raw output
    "join_dataframes": true,                    <<< Whether to join two command output, similar to Left Join in SQL Tables, only works if process_dataframes is True. If there is one command, this parameter is ignored
    "common_column": "MAC",                     <<< Common field to join two Dataframes. If join_dataframes is False , this parameter is ignored
    "report_file_name": "addresses_report"      <<< CSV File name
  }
```
Change these parameters accordingly and paste this fragment into json file and a new entry.

If you run the script with -h or --help option, the new Data Source will be shown.

You also need to define commands, so you can include fields and conditions in your queries.

#### Commands

The actual commands to run and associated options are defined in **command_definitions.json** file

To add a new command, copy a template from here:
https://github.com/networktocode/ntc-templates/tree/master/templates
or simply create a new file in templates/ directory and copy-paste text file content from NTC template.
Use Value fields as headers

```
     {
    "command":  "show mac address-table",                   <<<  Actual command to implement
    "template": "templates/cisco_ios_show_mac-address-table.template",   <<< NTC template
    "headers": ["MAC", "Type", "Vlan", "Interface"]         <<<  CSV Headers, also used to join dataframes
   },
```
Check this repository for more awesome templates and ideas :)

https://github.com/networktocode/ntc-templates

#### Fields and Conditions

The simplest way to query a Data Source is to use * as Field and don't use any conditions, foe example:
```
select * from <data_source> 
```
This is a good way to find all the fields you can query or filter on.

In most cases, however, you may want to define conditions with **where** clause:
```
select <fields> from <data_source> where <conditions>
```
There can be one conditions, for example:
```
where Vlan = 80 
where MAC=b19f
```
Or multiple conditions separated by keyword **and**:
```
where Last_Input = never and Vlan = 80 and Description = Wireless
```
Note the **=** sign matches a substing, so Vlan = 80 returns Vlans 180, 280, 800, etc.
See Limitations section.



#### Examples 

To get started, use a simple query like this:
```
python netsql.py --query="select * from addresses" --source device_ip_addresses.txt --user aupuser3
```
which looks up for ARP-MAC addresses mapping from L3 switches

Get routing tables from devices:
```
python netsql.py --query="select * from routes" --source site_core_switches.txt --screen-output --user aupuser3 --html-output --no-connect
```
Get all MAC addresses from L2 switches
```
python netsql.py --query="select * from mac_addresses" --source device_ip_addresses.txt --screen-output --user aupuser3 --html-output
```
Let's be be more specific and select two fields with a condition.
Locate MAC address of a device in a building:
```
python netsql.py --query="select Interface, MAC from addresses where MAC=b19f" --source 111_bourke.st.txt --screen-output --user aupuser3 --no-connect --html-output
```
In many case if you need to query a device second time, and there is collected output already in directories, use --no-connect option, so the script will not connect to the actual devices and process the existing output
```
python netsql.py --query="select * from interfaces where Last_Input = never and Vlan = 80" --source cleveland_st.txt --user aupuser3 --screen-output --no-connect
``
Find all CDP neighbours
```
python netsql.py --query="select Management_ip,Platform from neighbours where Platform = ISR" --source device_ip_addresses.txt --screen-output --user aupuser3 --no-connect --html-output
```
The same query, but with a condition this time.
Find all Polycom phones:
```
python netsql.py --query="select * from neighbours where Platform=Polycom" --source device_ip_addresses.txt --screen-output --user aupuser3 --no-connect --html-output
```
Find all Cisco 7945 phones:
```
python netsql.py --query="select * from neighbours where Platform = 7945" --source device_ip_addresses.txt --screen-output --user aupuser3 --no-connect --html-output
```
Find interfaces with Admin Down status in the existing output:
```
python netsql.py --query "select Interface,Status,Link_Status,Last_Input,Vlan,Description from interfaces where Link_Status = administratively " --source device_ip_addresses.txt --user aupuser3 --screen-output --html-output --screen-lines=10 --no-connect
```
Find interfaces at Clevelad St. site which never been used:
```
python netsql.py --query="select * from interfaces where Last_Input = never" --source cleveland_st.txt --user aupuser3 --screen-output
```
or a single device:
```
python netsql.py --query="select * from interfaces where Last_Input = never" --source 10.23.235.3 --aupuser3 --screen-output --html-output
```
Check if VLAN exists across sites:
```
python netsql.py --query="select * from interfaces where Vlan = 80" --source device_ip_addresses.txt --screen-output --user aupuser3 --html-output --no-connect
```
Get routing tables from devices:
```
python netsql.py --query="select * from routes" --source site_core_switches.txt --screen-output --user aupuser3 --html-output --no-connect
```
Check if a route exists:
```
python netsql.py --query="select * from routes where network = 0.0.0.0" --source site_core_switches.txt --screen-output --user aupuser3 --html-output --no-connect
```
Get list of routed L3 interfaces (SVI or physical) from a switch:
```
python netsql.py --query="select Ip_Address,Interface,Vlan,Name from interfaces where Vlan = routed" --source cleveland_st.txt --user aupuser3 --screen-output --no-connect --html-output
```
Get a list of active VLANs:
```
python netsql.py --query="select * from vlans where Status = active " --source device_ip_addresses.txt  --user aupuser3 --screen-output --no-connect
```
Get a list of configured L3 interfaces from a device
```
python netsql.py --query="select * from ip_int" --source device_ip_addresses.txt  --user aupuser3 --screen-output
```
Get a list of configured L3 interfaces from a device with IP address containing 10 (so excluding unassigned)
```
python netsql.py --query="select * from ip_int where Ipaddr = 10" --source device_ip_addresses.txt  --user aupuser3 --screen-output --no-connect
```
```

### How to create a new data source to query it

Steps 1-3 are optional - only if CVS output is required. Otherwise go to step 4.

1. Put the required template into **templates/** directory

2. Associate command with template in <i>templates</i> dictionary
   Example:
      "show ip route": 'templates/cisco_ios_show_ip_route.template'

3. Copy Values from the template file and associate command with these values in command_headers dictionary.
   They will be the CSV headers and the fields that can be queried and filtered on
   Example:
      "show ip route":
          ["protocol", "type", "network", "mask", "distance", "metric", "nexthop_ip", "nexthop_if", "uptime"]

4. In def main() locate the  <i>if</i> clause for source and add a new condition, specifying:
     - commands to run on a device
     - report file: report_file_name
     - do_not_join_dataframes to collect command output only and convert to CSV, without processing as dataframes
     Example:
        elif source == "routes":
            commands = ["show ip route"]
            report_file_name = "show_ip_route_report"
            do_not_join_dataframes = True

5. Define query string and run query:
query_string = 'select * from routes

#### Limitations
There are more limitations than features :) but the most notable (and being worked on) ones are:
- Only Cisco IOS devices are supported so far
- Only AND conditions, OR is coming
- **=** matches a substring, not an exact match 
- Basic HTML formatting

This work is in progress :-)

Any feedback, contributions, and requests are very-very appreciated, send it to supro200@gmail.com please


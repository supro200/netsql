# NetSQL

This tool allows to perform SQL-like queries on a single device or group of networks devices, like this:
```
select Interface,Last_Input,Vlan,Description,Link_Status from interfaces where Link_Status = down and Vlan = 100
```
You can query your network as it was a SQL table, and, for example, answer these questions:

* Where is this MAC address in my network?
* How many switch ports are in use, how many ports never been used? 
* Does this route exist in my network? 
* What VLANs and IP addresses are configured and active?
* How many IP Phones do we have?

Simple examples :
```
python netsql.py --query="select * from interfaces" --source 10.23.235.3 --user aupuser3
python netsql.py -q="select Interface,Description,Mode,Access_Vlan,Native_Vlan,Link_Status,Protocol_Status from switchports" -u aupuser3 -s 10.30.3.4 -html
```
The same outcome can be achieved using other tools, such as Splunk, but this script provides a lightweight alternative.

It can connect to a group of devices, or process text files without connecting to them.

You can easily add your own Data Source and start querying it.

- [NetSQL](#netsql)
  * [Installation](#installation-)
  * [How it works](#how-it-works-)
  * [How to use it](#how-to-use-it)
    + [IP Address Sources](#ip-address-sources)
    + [Username](#username)
  * [Queries](#queries)
      - [Data Sources](#data-sources)
      - [Commands](#commands)
      - [Fields and Conditions](#fields-and-conditions)
      - [Examples](#examples)
  * [How to create a new data source to query it](#how-to-create-a-new-data-source-to-query-it)
  * [Limitations](#limitations)
  
## Installation

It is recommended to build a Python 3 virtual environment. 
Details on how to set one up can be found [here](https://docs.python.org/3/library/venv.html). 

If you use a Windows PC, follow these steps:
1. Download and install [python 3](https://www.python.org/downloads/)
2. Setup virtual environment for NetSQL
3. Activate it
4. Download NetSQL source code
5. Install requirements
6. Start querying your network or use -h for help
```
python -m venv <path>
<path>\Scripts\activate.bat
git clone https://github.com/supro200/netsql.git
cd netsql
pip install -r requirements.txt
python netsql.py -h
```

## How it works

The script connects to network devices using Netmiko, gathers command output, stores into text files, converts them to CSV using TextFSM and NTC templates, and then processes as Pandas dataframes.
The results are device-command specific CSV files, and optionally HTML report.

When processing data, the script uses/creates the following directories:

>**raw_data/<device_IP>** - raw command output from the device in .txt files to process and converted CSV files
>
>**reports/<device_IP>**  - processed CSV files

The default directory for NTC templates is **templates/**

If *--html-output option* is selected, the .html files are places in **reports/**

Possible data sources to query and their attributes are defined in **source_definitions.json** and the corresponding commands to run **command_definition.json** 

See below for more details.

## How to use it

Use the following CLI parameters:

Required:

> *'-q', '--query'*    - SQL-formatted query, see examples below
>
> *'-s', '--source'*  -  Source file or a single IP addresses to process
>
> *'-u', '--user'*    - Username to connect to network devices"

Optional:

> *--no-connect*, *-nc* - Run without connecting to network devices, processes the command output already collected.
>                This is useful after you run a query, already got output, and then need to query on different fields or conditions; or don't have access to network devices.
>                Considerably improves query processing time, as it simply processes text files.
>
>  *--screen-output* - Prints report to screen. CSV reports are always generated. Turned on by default.
>
>  *--screen-lines*  - Number of lines printed to screen. Full output is always printed to CSV files. Default is 10.
>
>  *--html-output*, *-html*   - Prints report to HTML. CSV reports are always generated. Turned off by default

### IP Address Sources

Required in *--source* command-line option

The script can use a single IP to connect, like this:
```
--source 10.23.235.3
```
or with =
```
--source=10.23.235.3
```

In most cases a query on multiple devices is needed, so these devices' IP addresses should be defined in a text file.
The file format is arbitrary, the script recognises IP addresses automatically, as long as they in a separate line.
All other lines are ignored, but for better readability it is recommended to comment them with # 
You can specify multiple source files separated with comma

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
or
--source source_files/file_site1_switches.txt,source_files/file_site1_switches.txt
```

It is recommended to create a separate directory for source files, just for convenience.

### Username

Required in *--user* CLI option

Password should be entered manually each time the script runs.

**Note** with *--no-connect* option, the script doesn't actually connect to network devices, so username and password can be anything.

## Queries

The query should be in the following format:
```
select <fields> from <data_source> where <conditions>
```
*data_source*, *fields* and *conditions* are described below, following by examples.

#### Data Sources

Data Source is the the result of one or two command outputs, defined in **data_source_definitions.json**
 
Used in queries in **from** clause, for example:
```
select * from <datasource>
```
You can add a new Datasource to the JSON file, and start querying it.

The Data source definition format:
```
  {
    "data_source_name": "addresses_to_cdp",
    "commands": [                               <<<  List of commands
      "show mac address-table",
      "show cdp neighbors detail"
    ],
    "process_dataframes": true,                 <<< Whether to convert raw command output to CSV
                                                    In some cases you may want just to collect raw text output to process in other tools, such as Splunk or AWS Athena
    "join_dataframes": true,                    <<< Whether to join two command output, similar to Left Join in SQL Tables, only works if process_dataframes is True. 
                                                     If there is a single command, this parameter is ignored                     
    "common_columns": [                        <<< Common field to join two Dataframes. If join_dataframes is False , this parameter is ignored
      "Interface",                             <<< Field name from first command output with values matching seconds command output
      "Local_port"                             <<< Field name from second command output with values matching first command output
    ],
    "report_file_name": "addresses_cdp_report"      <<< CSV File name
  }
```
Change these parameters accordingly and paste this fragment into json file as a new entry.

To test if Datasource is added successfully, run the script with *-h* or *--help* option, the new Data Source will be shown.
```
python netsql.py -h
```
You also need to define commands, so you can include fields and conditions in your queries.

#### Commands

The actual commands to run and associated options are defined in **command_definitions.json** file

To add a new command, copy a template from [here](
https://github.com/networktocode/ntc-templates/tree/master/templates)
or simply create a new file in **templates/** directory and copy-paste text file content from NTC template.

Use NTC Value fields as CSV headers, for example:

```
     {
    "command":  "show mac address-table",                                <<<  Actual command to run
    "template": "templates/cisco_ios_show_mac-address-table.template",   <<< NTC template
    "headers": ["MAC", "Type", "Vlan", "Interface"]                      <<<  CSV Headers, also used to join dataframes
   },
```
Check this repository for more awesome templates and ideas :)

https://github.com/networktocode/ntc-templates

#### Fields and Conditions

The simplest way to query a Data Source is to use * as Field and don't use any conditions, for example:
```
select * from <data_source> 
```
Using * you can find all the fields you can query or filter on.

In most cases, however, you may want to define conditions with **where** clause:
```
select <fields> from <data_source> where <conditions>
```
There can be a single condition, for example:
```
where Vlan = 80 
where MAC=b19f
```
Or multiple conditions separated by keyword **and**:
```
where Last_Input = never and Vlan = 80 and Description = Wireless
```
Note the **=** sign matches a substing, so Vlan = 80 will return Vlans 180, 280, 800, etc.
See [Limitations](#limitations) section.

#### Examples 

To get started, use a simple query like this:
```
python netsql.py --query="select * from addresses" --source 10.1.1.1 --user aupuser3
```
This query will return ARP-MAC-Port mapping from L3 switches

Find switch interfaces at Clevelad St. site which never been used:
```
python netsql.py --query="select * from interfaces where Last_Input = never" --source cleveland_st.txt --user aupuser3 --screen-output
```
or query a single device, note CLI argument *--source* is IP address:
```
python netsql.py --query="select * from interfaces where Last_Input = never" --source 10.23.23.3 --aupuser3 --screen-output --html-output
```
Get routing tables from devices:
```
python netsql.py --query="select * from routes" --source device_ip_addresses.txt --screen-output --user aupuser3 --html-output
```
Get all MAC addresses from L2 switches
```
python netsql.py --query="select * from mac-addresses" --source device_ip_addresses.txt --screen-output --user aupuser3 --html-output
```
Add a condition to the previous example and locate a MAC address of a connected device in your building or campus:
```
python netsql.py --query="select Interface, MAC from addresses where MAC=b19f" --source 111_bourke.st.txt --screen-output --user aupuser3 --no-connect --html-output
```
In many cases if you need to query a device second time, and there is collected output already in directories, use *--no-connect option*, so the script will not connect to the actual devices and process the existing output
```
python netsql.py --query="select * from interfaces where Last_Input = never and Vlan = 80" --source cleveland_st.txt --user aupuser3 --screen-output --no-connect
```
Find all CDP neighbours which are Cisco ISR routers, note condition *where Platform = ISR*:
```
python netsql.py --query="select Management_ip,Platform from neighbours where Platform = ISR" --source device_ip_addresses.txt --screen-output --user aupuser3 --html-output
```
Similar query, finds all Polycom phones:
```
python netsql.py --query="select * from neighbours where Platform=Polycom" --source device_ip_addresses.txt --screen-output --user aupuser3 --html-output
```
Find all Cisco 7945 phones:
```
python netsql.py --query="select * from neighbours where Platform = 7945" --source device_ip_addresses.txt --screen-output --user aupuser3 --html-output
```
Find interfaces with Admin Down status in the existing output, note CLI argument *--no-connect*:
```
python netsql.py --query "select Interface,Status,Link_Status,Last_Input,Vlan,Description from interfaces where Link_Status = administratively " --source device_ip_addresses.txt --user aupuser3 --screen-output --html-output --screen-lines=10 --no-connect
```
Check if VLAN exists across corporate sites:
```
python netsql.py --query="select * from interfaces where Vlan = 80" --source device_ip_addresses.txt --screen-output --user aupuser3 --html-output --no-connect
```
Get routing tables from devices:
```
python netsql.py --query="select * from routes" --source site_core_switches.txt --screen-output --user aupuser3 --html-output --no-connect
```
Check if default route exists:
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
python netsql.py --query="select * from ip_interfaces" --source device_ip_addresses.txt  --user aupuser3 --screen-output
```
Get a list of configured L3 interfaces from a device with IP address containing 10 (so excluding unassigned)
```
python netsql.py --query="select * from ip_interfaces where Ipaddr = 10" --source device_ip_addresses.txt  --user aupuser3 --screen-output --no-connect
```
Find Cisco Access Points based on a fragment of MAC address, print CDP details:
```
python netsql.py --query="select * from mac-cdp-nei where MAC=bb and Platform = AIR" -nc --source source_files/queen_st.txt,source_files/cleveland_st.txt --user aupuser3 -html
```
Prints CDP neighbour details for the device connected to a port, and the description of the port.
Can be useful to check if Networke devices, Access points, Video or IoT devices are connected to correct ports.
```
python netsql.py --query="select * from cdp-nei-port" --source source_files/queen_st.txt --user aupuser3 -html
```

## How to create a new data source to query it

1. [Create Data Source](#data-sources) by modifying **data_source_definitions.json**, associate the Data Source to device commands
2. Check the new Datasource is added by running the script with -h option:
```
python netsql.py -h
```
3. Put the required NTC template into **templates/** directory
4. Edit **command_definitions.json**, [associate](#commands) the command with the template
5. You can start querying your data source

## Limitations
There are more limitations than features :) but the most notable (and being worked on) ones are:
- Only Cisco IOS devices are supported so far
- Only AND conditions, OR is coming
- **=** matches a substring, not an exact match 

This work is in progress :-)

Any feedback, contributions, and requests are very much appreciated, send them to supro200@gmail.com


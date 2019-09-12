"""
NetSQL is a network query tool which helps to collect and filter data about your network.
Requires access to netowrk devices, but also can process raw command output.
"""
from __future__ import print_function, unicode_literals

import json
import re
import csv
import getpass
import ipaddress
import argparse
import sys
import textfsm
import os
import pandas as pd
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException, NetMikoAuthenticationException, SSHException
from colorama import init,Fore,Style

DEVICE_TYPE = "cisco_ios"
REPORT_DIR = 'reports\\'
RAW_OUTPUT_DIR = 'raw_data\\'

class CustomParser(argparse.ArgumentParser):

    def print_help(self):
        print('\n Usage examples:' +
              '\n         python netsql.py --query="select * from interfaces where Last_Input = never" --source 10.74.41.73 --user aupuser3 --screen-output --html-output' +
              '\n         python netsql.py --query="select Interface,Name,Last_Input from interfaces where Last_Input = never" --source cleveland_st.txt --user azyuzin1 --screen-output --html-output' +
              '\n         python netsql.py --query="select * from neighbours where Platform=Polycom" --source device_ip_addresses.txt --screen-output --user azyuzin1 --html-output' +
              '\n\n Query should be in the following format: ' +
              '\n     -query="select <fields to select or * > from <source> where <condition>"' +
              '\n     <fields to select or * >  and <source>  are required, <condition> is onptional ' +
              '\n\n Query examples: ' +
              '\n   - List ports which never been used:' +
              '\n         --query="select * from interfaces where Last_Input = never"' +
              '\n   - Find switch port where a device located by its MAC' +
              '\n         --query="select * from mac-addresses where MAC=3348"' +
              '\n   - Get device details from L3 switch: IP, VLAN, port:'
              '\n         --query="select * from mac-addresses where MAC=b19f"' +
              '\n   - Get device  details from L2 switch:' +
              '\n         --query="select * from addresses where MAC=b19f"' +
              '\n   - Get neighbours details:' +
              '\n         --query="select Host,Management_ip,Platform,Remote_Port,Local_port from neighbours"' +
              '\n   - Get number of Polcycom devices in building:' +
              '\n         --query="select * from neighbours where Platform=Polycom"')
        print('\n The following data sources are allowed in queries: \n')

        with open('command_definitions.json', 'r') as f:
            command_definitions = json.load(f)

        with open('data_source_definitions.json', 'r') as f:
            source_definitions = json.load(f)

        for source in source_definitions:
            print("Data source: {:<15} Actual commands {}".format(source["data_source_name"], source["commands"]))

        # print('\n The following fields are allowed in queries: \n')
        # for command in command_definitions:
        #     print(command["command"])
        #     print(command["headers"])

    def error(self, message):
        print('error: %s\n' % message)
        print('Use --help or -h for help')
        sys.exit(2)

# -------------------------------------------------------------------------------------------

def parse_args(args=sys.argv[1:]):
    """Parse arguments."""
    parser = CustomParser()
    parser._action_groups.pop()
    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('optional arguments')
    # Required arguments
    required.add_argument('-q', '--query',
                          help="Query, see usage examples",
                          type=str,
                          required=True
                          )
    required.add_argument('-s', '--source',
                          help="Source of IP addresses to process. Can be a file, or a single IP address",
                          required=True,
                          )
    required.add_argument('-u', '--user',
                          help="Username to connect to network devices",
                          required=True,
                          )
    # Optional arguments
    optional.add_argument("--no-connect",
                          default=False,
                          action="store_true",
                          help="Run without connecting to network devices, uses the output previously collected. Impoves query processing speed")
    optional.add_argument("--screen-output",
                          default=True,
                          required=False,
                          action="store_true",
                          help="Prints report to screen. CVS reports are always generated")
    optional.add_argument("--screen-lines",
                          default=10,
                          type=int,
                          required=False,
                          help="Number of lines to output for each device")
    optional.add_argument("--html-output",
                          default=False,
                          action="store_true",
                          help="Prints report to HTML. CVS reports are always generated")
    return parser.parse_args(args)

# -------------------------------------------------------------------------------------------

def command_analysis(text):
    '''
    :param text: SQL string, for example:

    select first_name,last_name from students where id = 5
    select * from students where first_name = "Mike" or "Andrew" and last_name = "Brown"
    select last_name from students where math_score = "90" or "80" and last_name = "Smith" and year = 7 or 8

    :return: Dictionary built from the input string, for example:

        {'conditions': [{'cond_field': 'math_score',
                         'cond_value': ['"90"',
                                        '"80"']},
                        {'cond_field': 'last_name',
                         'cond_value': '"Smith"'},
                        {'cond_field': 'year',
                         'cond_value': ['7',
                                        '8']}],
         'fields': ['*'],
         'source': 'students'}

    Written by Ilya Zyuzin, McKinnon Secondary College, 07K. 2019.
    '''
    fields = []
    source = ""
    conditions = []
    result = {}
    command = text.split()

    if command[0] == "select":
        # field analysis
        if "," in command[1]:
            morefields = command[1].split(",")
            for item in morefields:
                fields.append(item)
        else:
            fields.append(command[1])

        # checking whether 'from' exists
        if command[2] == "from":
            # source
            source = command[3]
        else:
            print("Error: 'from' not found!")

        try:
            if command[4] == "where":
                tempcond = " ".join(command[5:])
                # split conditions by keyword 'and'
                condition = tempcond.split("and")
                # loop until everything has been sorted
                for element in condition:
                    condition_dic = {}
                    # split every condition by keyword '='
                    val = element.split("=")
                    condition_dic['cond_field'] = val[0].strip()

                    if 'or' in val[1]:
                        # if there is an 'or' in the request
                        tempvalue = ("").join(val[1])
                        values = tempvalue.split("or")
                        condition_dic['cond_value'] = []
                        for value in values:
                            if value != " ":
                                condition_dic['cond_value'].append(value.strip())
                    else:
                        condition_dic['cond_value'] = val[1].strip()

                    conditions.append(condition_dic)
        except:
            pass
    else:
        print("Invalid Format or Command!")

    result['fields'] = fields[0:]
    result['source'] = source
    result['conditions'] = conditions[0:]
    return result

# -------------------------------------------------------------------------------------------

def run_command_and_write_to_txt(commands, a_device, no_connect):
    '''Execute IOS commands using Netmiko.
    Input parameters:
         - list of commands
         - device IP
    Writes raw output to a report file
    '''

    # If Do Not Connect flag is set, do not connect to any devices, just return True
    # The script uses the output from devices already collected
    if no_connect:
        return True

    try:
        remote_conn = ConnectHandler(**a_device)
    except NetMikoAuthenticationException as error:
        print('Authentication Exception - terminating program \n', str(error))
        exit(1)
    except NetMikoTimeoutException as error:
        print(' ===> WARNING : Timeout while connecting to: {}, error: {}  Skipping.'
              .format(a_device["host"], str(error)))
    except SSHException as error:
        print(' ===> WARNING : SSH2 protocol negotiation or logic errors while connecting to: {}, error: {}  Skipping.'
              .format(a_device["host"], str(error)))
    except Exception as error:
        # raise ValueError(' ===> Skipping - Failed to execute due to %s', error)
        print(' ===> WARNING : Unhandled exception while connecting to: {}, error: {}  Skipping.'
              .format(a_device["host"], str(error)))
    else:
        for command in commands:
            file_name = get_file_path(a_device["host"], command, "raw_output") + ".txt"
            print("Writing output to file: ", file_name)
            os.makedirs(os.path.dirname(file_name), exist_ok=True)

            with open(file_name, "w") as f:
                # execute command on a device and write to a file
                f.write(remote_conn.send_command_expect(command))
        # sucessful command execution - return True
        return True
    # failure during command execution - return False
    print("-" * 80)
    return False

# -------------------------------------------------------------------------------------------

def find_command(command, all_commands):
    """
    Looks up a command in a list of dictioraries, returns a dictionary from a list

    :param command: Command to look up
    :param all_commands: list of all commands
    :return: dictionary
    """
    for item in all_commands:
        if item['command'] == command:
            return item

# -------------------------------------------------------------------------------------------

def get_file_path(host, command, file_type):
    """
    Builds file name from input arguments

    :param host: Host ip address
    :param command: Command to run
    :param file_type: report or raw output
    :return: full path with filename
    """

    if file_type == "report":
        file_name = REPORT_DIR + host + "\\" + command.replace(" ", "_")
    else:
        file_name = RAW_OUTPUT_DIR + host + "\\" + command.replace(" ", "_")
    return file_name

# -------------------------------------------------------------------------------------------

def normalise_file(file_name):
    """
    Replaces strings to match different command output, for example, make all interface names from GigabitEnternet to Gi

    :param file_name: File Name to load and replace strings
    :return: none
    """
    with open(file_name, 'r+') as f:
        content = f.read()
        content_new = re.sub('(GigabitEthernet)(\d{1})\/(\d{1})\/(\d{1,2})',
                             r'Gi\2/\3/\4', content, flags=re.M)
        # rewriting file
        f.seek(0)
        f.truncate()
        f.write(content_new)

# -------------------------------------------------------------------------------------------

def print_to_csv_file(headers, content, file_name):
    """
    Prints text to CSV files, also changes command output where necessary, such as Gi -> GigabitEthernet

    :param headers: CSV headers
    :param content: CSV text
    :param file_name: output file name
    :return: None
    """
    try:
        with open(file_name, 'w', newline='') as out_csv:
            csvwriter = csv.writer(out_csv, delimiter=',')
            csvwriter.writerow(headers)
            for item in content:
                csvwriter.writerow(item)
        # Replace strings to match different command output, for example, make all interface names from GigabitEnternet
        # to Gi
        normalise_file(file_name)
        print ("Writing CSV",file_name)
    except Exception as e:
        print("Error while opening file", e)

# -------------------------------------------------------------------------------------------

def convert_output_to_csv(commands, a_device):
    """
    Pasres raw test with TextFSM, Converts text file to CSV and writes CSV
    :param commands: List of commands to execute
    :param a_device: Dictionary - Netmiko device format
    :return: none
    """
    for command in commands:
        # build file names - directory + host IP + command name + .txt
        file_name = get_file_path(a_device["host"], command, "raw_output") + ".txt"

        # Read the whole file
        try:
            with open(file_name, 'r') as content_file:
                raw_command_output = content_file.read()
        except Exception as e:
            # Could open file, skip the remaining processing
            print("Error while opening file", e)
            return False

        # Get headers and NTC templates for a given command - should be defined as global variables
        try:
            headers = find_command(command, command_definitions)["headers"]
            template = find_command(command, command_definitions)["template"]
        except:
            print("template not yet defined for ", command, " - skipping")
            continue
        # Parse raw output with text FSM
        text_fsm_template = textfsm.TextFSM(open(template))
        parsed_command_output = text_fsm_template.ParseText(raw_command_output)
        # print to CSV
        print_to_csv_file(headers, parsed_command_output, file_name.replace(".txt", ".csv"))
    return True

# -------------------------------------------------------------------------------------------

def process_csv_files(join_dataframes, common_column, fields_to_select, filter, file1, file2, result_file):
    """
    Joins two dataframes.
    Input parameters:
         - common_column
         - two csv files to join
    Writes raw output to a report file
    """

    if join_dataframes:
        pd1 = pd.read_csv(file1)
        pd2 = pd.read_csv(file2)

        if fields_to_select[0] == "*":
            result_pd = pd.merge(pd1, pd2, on=common_column)
        else:
            result_pd = pd.merge(pd1, pd2, on=common_column).filter(fields_to_select)
    else:
        pd1 = pd.read_csv(file1)
        if fields_to_select[0] == "*":
            result_pd = pd1
        else:
            result_pd = pd1.filter(fields_to_select)

    # see OR in strings : https://stackoverflow.com/questions/19169649/using-str-contains-in-pandas-with-dataframes
    if filter:
        for filter_item in filter:
            result_pd = result_pd[result_pd[filter_item["cond_field"]].astype(str).str.contains(filter_item["cond_value"], regex=False)]

    # Debug -print(result_file)
    os.makedirs(os.path.dirname(result_file), exist_ok=True)

    result_pd.to_csv(result_file)

# -------------------------------------------------------------------------------------------
def main():

    # init colorama
    init()

    # Check CLI arguments
    options = parse_args()

    # Set initial values
    total_number_of_devices = 0
    number_of_processed_devices = 0
    html_string = ""
    device_ip_addresses = []
    commands = ""

    screen_row_count = options.screen_lines

    # read defined commands, templates and headers, store as Global variables
    global command_definitions
    with open('command_definitions.json', 'r') as f:
        command_definitions = json.load(f)

    with open('data_source_definitions.json', 'r') as f:
        source_definitions = json.load(f)

    # Parse query from CLI input and populate parameters for Dataframe merge
    query_processed = command_analysis(options.query)
    source = query_processed["source"]

    # Check if source in the query is defined and can be handled
    for item in source_definitions:
        if item['data_source_name'] == source:
            commands = item['commands'].copy()
            process_dataframes = item["process_dataframes"]
            join_dataframes = item["join_dataframes"]
            common_column = item["common_column"]
            report_file_name = item["report_file_name"]

    # Got empty commands list at previous step, nothing to run
    if commands == "":
        # not yet implemented
        print("This source is not yet implemented:", source, "Please check source_definition file or use --help for help")
        exit(1)

    # Check if there are any conditions and include as filter for further processing with Pandas
    if query_processed["conditions"]:
        filter = query_processed["conditions"]
    else:
        filter = ""

    fields_to_select = query_processed["fields"]

    try:
        # if ipaddress.ip_address call didn't fail, it's a valid IP, handle it
        ip_address = str(ipaddress.ip_address(options.source))
        print("Processing host:", ip_address)
        # single host
        device_ip_addresses.append(ip_address)
    except:
        # if not an IP address, treat as a source file
        print("opening source file: ", options.source)
        # reading source file with IP addresses
        with open(options.source) as f:
            device_ip_addresses = f.read().splitlines()

    # ask for user's password. Note - username is configured as a Global variable
    password = getpass.getpass(prompt='Password: ', stream=None)

    # analyse each line of the source file
    for line in device_ip_addresses:
        # try to convert line into IP address format
        try:
            # if ipaddress.ip_address call didn't fail, it's a valid IP, handle it
            ip_address = str(ipaddress.ip_address(line))
            print("Processing host:", ip_address)
            device = {
                "host": ip_address,
                "username": options.user,
                "password": password,
                "device_type": DEVICE_TYPE,
            }
        except:
            # the line we've read from the text file is not an IP address, ignore it, go to next line
            # print("not IP address - ignoring line")
            continue

        # device IP detected - increase Total device counter
        total_number_of_devices += 1

        # Try to get command output from a device
        if run_command_and_write_to_txt(commands, device, options.no_connect):
            # Got some output from a device - increase Processed device counter and process the output
            number_of_processed_devices += 1

            #C onvert to CSV Files
            if not convert_output_to_csv(commands, device):
                # if current file failed to process, skip it, go to next device or file
                print(" ===> WARNING :  Could not process CSV file ")
                number_of_processed_devices -= 1
                print("-" * 80)
                continue

            # if process_dataframes flag is set, do not further process output, just keep raw text files
            if process_dataframes:

                if join_dataframes:
                     process_csv_files(True, common_column, fields_to_select, filter,
                                   get_file_path(device["host"], commands[0], "raw_output") + ".csv",
                                   get_file_path(device["host"], commands[1], "raw_output") + ".csv",
                                   get_file_path(device["host"], report_file_name, "report") + ".csv")
                else:
                     process_csv_files(False, common_column, fields_to_select, filter,
                                   get_file_path(device["host"], commands[0], "raw_output") + ".csv",
                                   "",
                                   get_file_path(device["host"], report_file_name, "report") + ".csv")

                print("Results saved as:", get_file_path(device["host"], report_file_name, "report") + ".csv")

                if options.screen_output:
                    df = pd.read_csv(get_file_path(device["host"], report_file_name, "report") + ".csv", index_col=0)

                    # Get number of rows and columns in Dataframe
                    count_row = len(df)

                    if count_row > screen_row_count:
                        print("Returned", count_row, "but printed only first", screen_row_count,
                              ". Check CVS file for full output")
                    if count_row > 0:
                        print(df.head(screen_row_count))
                        print(Fore.GREEN + "Returned", count_row, "record(s)")
                    else:
                         print(Fore.RED + "Returned 0 record(s)")

                    print(Style.RESET_ALL)
                    print("-"*80)

                if options.html_output:
                        # output to HTML
                        html_string = html_string + "\n<b>" + device['host'] + "</b>\n" + \
                                     df.to_html().replace('<th>','<th style = "background-color: #bde9ba">')

    print("Done. Completed", number_of_processed_devices, "of", total_number_of_devices, "devices")

    with open(get_file_path("",report_file_name, "report") + ".html", 'w') as f:
        f.write(html_string)

if __name__ == "__main__":
    main()

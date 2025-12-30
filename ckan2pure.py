import argparse
from urllib.request import urlopen
import json
import time
#import sys

from pure_parse import urlopen_with_basic_auth
from utils import render_package, xml_init, write_xml, validate_xml, print_stderr

__version_info__ = ('2025', '11', '12')
__version__ = '-'.join(__version_info__)

PROGRAM_DESCRIPTION = '''

A program for reading dataset metadata from a CKAN repository and translating to the Elsevier Pure XML schema.

Dataset metadata is obtained from a CKAN website through HTTP requests, so an internet connection is required.

Tested with python 3.8.

Example usage:

       python ckan2pure.py --ckan-url https://data.ucar.edu > pure.xml
       
Required arguments:

       --username         Username for Pure support servers
       --password         Password for Pure support servers
       
Optional arguments:

       --ckan-url         Base URL for CKAN repository; default is "https://data.ucar.edu"
       --test             Generate output for the first ten datasets only
       --use-namespaces   Use qualified namespaces.  Should be selected if --validate is selected.
       --validate         Perform XSD schema validation on the XML output
       --add-extra        Add extra concepts from the Pure Schema to XML output
       
       --version          Print the program version and exit.

Program Version: '''


#
#  Parse the command line options.
#
programHelp = PROGRAM_DESCRIPTION + __version__
parser = argparse.ArgumentParser(description=programHelp)
#parser.add_argument("--username", nargs=1, required=True, help="Username for Pure support servers")
#parser.add_argument("--password", nargs=1, required=True, help="Password for Pure support servers")

parser.add_argument("--ckan-url", nargs=1, help="CKAN base URL", default=['https://data.ucar.edu'])
parser.add_argument("--test", help="Produce output for at most ten datasets", action='store_const', const=True)
parser.add_argument("--use-namespaces", help="Add qualified namespaces to elements", action='store_const', const=True)
parser.add_argument("--validate", help="Perform XSD validation; use with --use-namespaces.",
                    action='store_const', const=True)
parser.add_argument("--add-extra", help="Add extra Pure concepts", action='store_const', const=True)
parser.add_argument('--version', action='version', version="%(prog)s (" + __version__ + ")")

args = parser.parse_args()

CKAN_URL = args.ckan_url[0]
TEST_OUTPUT = args.test
USE_NAMESPACES = args.use_namespaces
VALIDATE_XML = args.validate
ADD_EXTRA_CONCEPTS = args.add_extra

# Time the program's run length
start_time = time.time()

# URL for getting the list of package names
package_search_query = CKAN_URL + '/api/3/action/package_search?fq=resource-type:dataset'

with urlopen(package_search_query) as url:
    response = url.read()

json_data = json.loads(response.decode('utf-8'))

num_datasets = json_data['result']['count']
#datasets = json_data['result']['results']  # extract all the packages from the response
print_stderr(num_datasets)

max_rows = 500
if TEST_OUTPUT:
    start = num_datasets - 10
else:
    start = 0
    # num_datasets = min(10, len(datasets))
    # datasets = datasets[:num_datasets]

root = xml_init(USE_NAMESPACES)

while start < num_datasets:
    query = package_search_query + f'&start={start}&rows={max_rows}'
    with urlopen(query) as url:
        response = url.read()
    json_data = json.loads(response.decode('utf-8'))
    datasets = json_data['result']['results']  # extract all the packages from the response
    for pkg_dict in datasets:
        # package_get = CKAN_URL + '/api/3/action/package_show?id=' + dataset_name
        # with urlopen(package_get) as url:
        #     response = url.read()
        # json_data = json.loads(response.decode('utf-8'))
        # pkg_dict = json_data['result']
        print_stderr(pkg_dict['title'])
        render_package(root, pkg_dict, ADD_EXTRA_CONCEPTS)
    start = start + max_rows

xml_header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
write_xml(root, xml_header)

if VALIDATE_XML:
    validate_xml(root)
    print_stderr("\n\n  VALIDATION PASSED\n\n")

# Print out the running time.
running_time_secs = (time.time() - start_time)
print_stderr("--- %s seconds ---" % running_time_secs)
print_stderr("--- %s minutes ---" % (running_time_secs / 60))
